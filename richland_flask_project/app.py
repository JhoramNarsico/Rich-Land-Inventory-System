# ==============================================================================
# app.py - Main Flask Application for Rich Land Auto Supply
# ==============================================================================

# --- Core Imports ---
import os
import csv
from io import BytesIO, StringIO
from datetime import datetime, timezone
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for, flash, Response, jsonify)
from dotenv import load_dotenv
from passlib.context import CryptContext
from bson.objectid import ObjectId
from xhtml2pdf import pisa

# --- Flask Extension Imports ---
from flask_login import (LoginManager, login_user, logout_user, login_required, current_user)
from flask_wtf.csrf import CSRFProtect

# --- Project-Specific Imports ---
from database import (
    users_collection, products_collection, sales_collection,
    purchase_orders_collection, suppliers_collection, product_history_collection,
    categories_collection, settings_collection # <--- Added
)
from models import User
from forms import (
    LoginForm, ProductCreateForm, ProductUpdateForm, StockTransactionForm,
    ProductFilterForm, TransactionFilterForm, SupplierForm, PurchaseOrderForm,
    ProductHistoryFilterForm, SalesReportForm, POFilterForm,
    UserRegistrationForm,
    CategoryForm, 
    UserEditForm,       
    ChangePasswordForm,
    ProductImportForm,
    MasterPasswordForm # <--- Added
)

# ==============================================================================
# Application Setup & Configuration
# ==============================================================================

load_dotenv()

app = Flask(__name__)

# Fallback secret key
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-replace-in-production')

# Initialize CSRF Protection globally
csrf = CSRFProtect(app)

# --- Password Hashing Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.find_by_id(user_id)

# ==============================================================================
# Custom Decorators & Template Filters
# ==============================================================================

def role_required(*group_names):
    """Custom decorator to restrict access based on a list of allowed groups."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.group not in group_names:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.template_filter('intcomma')
def intcomma_filter(value):
    """Custom Jinja2 filter to format numbers with commas."""
    try:
        return "{:,.0f}".format(float(value)) 
    except (ValueError, TypeError):
        return value

# Helper to verify master password
def verify_master_password(input_password):
    """Checks the input against the stored global master password."""
    settings = settings_collection.find_one({'_id': 'global_config'})
    if settings and 'master_password' in settings:
        return pwd_context.verify(input_password, settings['master_password'])
    return False

# ==============================================================================
# Authentication Routes
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.find_by_username(form.username.data)
        if user and pwd_context.verify(form.password.data, user.hashed_password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    """Allows any logged-in user to change their password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # 1. Verify the current password
        if not pwd_context.verify(form.current_password.data, current_user.hashed_password):
            flash("Incorrect current password. Please try again.", "danger")
        else:
            # 2. Hash the new password
            new_hashed_password = pwd_context.hash(form.new_password.data)
            
            # 3. Update the database
            users_collection.update_one(
                {'_id': ObjectId(current_user.id)}, 
                {'$set': {'hashed_password': new_hashed_password}}
            )
            flash("Your password has been updated successfully!", "success")
            return redirect(url_for('user_profile'))
            
    return render_template('admin/profile.html', form=form)

# ==============================================================================
# Core Application Routes (Dashboard)
# ==============================================================================

@app.route('/')
@login_required
def home():
    # 1. Low Stock Pipeline
    low_stock_pipeline = [
        {"$match": {"status": "ACTIVE"}},
        {"$match": {"$expr": {"$lte": ["$quantity", "$reorder_level"]}}},
        {"$sort": {"quantity": 1}}
    ]
    low_stock_products = list(products_collection.aggregate(low_stock_pipeline))

    # 2. Key Metrics Pipeline
    metrics_pipeline = [
        {"$match": {"status": "ACTIVE"}},
        {"$group": {"_id": None, "total_products": {"$sum": 1}, "total_stock_value": {"$sum": {"$multiply": ["$price", "$quantity"]}}}}
    ]
    metrics_data = list(products_collection.aggregate(metrics_pipeline))
    metrics = metrics_data[0] if metrics_data else {"total_products": 0, "total_stock_value": 0}

    # 3. Recent Products
    recent_products = list(products_collection.find().sort("date_created", -1).limit(5))

    # 4. Top Sellers Pipeline
    top_sellers_pipeline = [
        {"$match": {"items_sold.type": "OUT"}},
        {"$unwind": "$items_sold"},
        {"$match": {"items_sold.type": "OUT"}},
        {"$group": {"_id": "$items_sold.product_sku", "product_name": {"$first": "$items_sold.product_name"}, "total_quantity_sold": {"$sum": "$items_sold.quantity_sold"}}},
        {"$sort": {"total_quantity_sold": -1}},
        {"$limit": 5}
    ]
    top_selling_items = list(sales_collection.aggregate(top_sellers_pipeline)) 

    # 5. Sales Trend Pipeline
    sales_trend_pipeline = [
        {"$match": {"items_sold.type": "OUT"}},
        {"$project": {
            "date_str": {"$dateToString": {"format": "%Y-%m-%d", "date": "$sale_date"}},
            "total_amount": 1
        }},
        {"$group": {
            "_id": "$date_str",
            "daily_total": {"$sum": "$total_amount"}
        }},
        {"$sort": {"_id": 1}},
        {"$limit": 30}
    ]
    trend_data = list(sales_collection.aggregate(sales_trend_pipeline))
    
    trend_labels = [row['_id'] for row in trend_data]
    trend_values = [row['daily_total'] for row in trend_data]
    
    return render_template('home.html',
                           low_stock_products=low_stock_products,
                           low_stock_products_count=len(low_stock_products),
                           total_products=metrics['total_products'],
                           total_stock_value=metrics['total_stock_value'],
                           recent_products=recent_products,
                           top_selling_items=top_selling_items,
                           trend_labels=trend_labels,
                           trend_values=trend_values)

# ==============================================================================
# Product Management Routes & Internal APIs
# ==============================================================================

@app.route('/inventory/products')
@login_required
def product_list():
    form = ProductFilterForm(request.args, meta={'csrf': False})
    query = {}
    sort_by = request.args.get('sort_by', '-date_created')

    if 'product_status' in request.args:
        if form.product_status.data:
            query['status'] = form.product_status.data
    else:
        query['status'] = 'ACTIVE'

    if form.validate():
        if form.q.data:
            query['$or'] = [{'name': {'$regex': form.q.data, '$options': 'i'}}, {'_id': {'$regex': form.q.data, '$options': 'i'}}]
        if form.category.data:
            query['category_name'] = form.category.data
            
    sort_field, sort_order = (sort_by[1:], -1) if sort_by.startswith('-') else (sort_by, 1)
    products = list(products_collection.find(query).sort(sort_field, sort_order))
    return render_template('inventory/product_list.html', product_list=products, filter_form=form)

@app.route('/search/products')
@login_required
def search_products():
    search_term = request.args.get('q', '')
    query = {
        'status': 'ACTIVE',
        '$or': [
            {'_id': {'$regex': search_term, '$options': 'i'}},
            {'name': {'$regex': search_term, '$options': 'i'}}
        ]
    }
    products = products_collection.find(query).limit(50)
    results = [
        {'value': p['_id'], 'text': f"{p['name']} ({p['_id']})"} for p in products
    ]
    return jsonify(results)

@app.route('/inventory/product/<sku>', methods=['GET', 'POST'])
@login_required
def product_detail(sku):
    product = products_collection.find_one({'_id': sku})
    if not product:
        flash(f"Product {sku} not found or has been deleted.", "warning")
        return redirect(url_for('product_list'))
        
    transaction_form = StockTransactionForm()
    
    # HANDLE POST: Stock Adjustments
    if transaction_form.validate_on_submit():
        quantity = transaction_form.quantity.data
        trans_type = transaction_form.transaction_type.data
        notes = transaction_form.notes.data or "Manual Stock Adjustment"
        
        # SECURITY CHECK: 
        # If user is Salesman, they MUST provide a valid Master Password
        if current_user.group == 'Salesman':
            master_pw = transaction_form.master_password.data
            if not master_pw:
                flash("Master Password required for Salesman adjustments.", "danger")
                return redirect(url_for('product_detail', sku=sku))
            
            if not verify_master_password(master_pw):
                flash("Invalid Master Password.", "danger")
                return redirect(url_for('product_detail', sku=sku))
            
            # Append authorization note
            notes += " (Auth: Master PW)"

        if trans_type == 'OUT' and product['quantity'] < quantity:
            flash('Cannot stock out more than the available quantity.', 'danger')
            return redirect(url_for('product_detail', sku=sku))
            
        update_quantity = quantity if trans_type == 'IN' else -quantity
        
        products_collection.update_one({'_id': sku}, {'$inc': {'quantity': update_quantity}})
        
        sales_collection.insert_one({
            "sale_date": datetime.now(timezone.utc), 
            "user_username": current_user.username, 
            "total_amount": 0, 
            "items_sold": [{
                "product_sku": sku, 
                "product_name": product['name'], 
                "quantity_sold": quantity, 
                "price_per_unit": product['price'], 
                "type": trans_type, 
                "notes": notes
            }]
        })
        
        action = "Restocked" if trans_type == 'IN' else "Pulled out"
        flash(f'Successfully {action} {quantity} units.', 'success')
        return redirect(url_for('product_detail', sku=sku))
        
    recent_transactions = list(sales_collection.find({"items_sold.product_sku": sku}).sort("sale_date", -1).limit(10))
    return render_template('inventory/product_detail.html', product=product, transaction_form=transaction_form, transactions=recent_transactions)

@app.route('/inventory/product/<sku>/toggle_status', methods=['POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def toggle_product_status(sku):
    product = products_collection.find_one({'_id': sku})
    if product:
        new_status = 'DEACTIVATED' if product['status'] == 'ACTIVE' else 'ACTIVE'
        products_collection.update_one({'_id': sku}, {'$set': {'status': new_status, 'date_updated': datetime.now(timezone.utc)}})
        flash(f'Product status changed to {new_status}.', 'success')
    else:
        flash('Product not found.', 'danger')
    return redirect(url_for('product_detail', sku=sku))

@app.route('/inventory/product/add', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def add_product():
    form = ProductCreateForm()
    form.category.choices = [c['name'] for c in categories_collection.find().sort('name', 1)]
    form.category.choices.insert(0, "")

    if form.validate_on_submit():
        if products_collection.find_one({'_id': form.sku.data}):
            flash('Product with this SKU already exists.', 'danger')
            return render_template('inventory/product_form.html', form=form, title="Create Product")
            
        new_product = {
            "_id": form.sku.data, 
            "name": form.name.data, 
            "category_name": form.category.data, 
            "price": float(form.price.data), 
            "quantity": int(form.quantity.data), 
            "reorder_level": int(form.reorder_level.data), 
            "status": "ACTIVE", 
            "date_created": datetime.now(timezone.utc), 
            "date_updated": datetime.now(timezone.utc)
        }
        
        products_collection.insert_one(new_product)
        product_history_collection.insert_one({
            "product_sku": new_product['_id'], 
            "timestamp": datetime.now(timezone.utc), 
            "user_username": current_user.username, 
            "change_type": "CREATE", 
            "product_snapshot": new_product
        })
        
        if new_product['quantity'] > 0:
            sales_collection.insert_one({
                "sale_date": datetime.now(timezone.utc), 
                "user_username": current_user.username, 
                "total_amount": 0, 
                "items_sold": [{
                    "product_sku": new_product['_id'], 
                    "product_name": new_product['name'], 
                    "quantity_sold": new_product['quantity'], 
                    "price_per_unit": new_product['price'], 
                    "type": "IN", 
                    "notes": "Initial stock on product creation."
                }]
            })
            
        flash('Product created successfully!', 'success')
        return redirect(url_for('product_list'))
        
    return render_template('inventory/product_form.html', form=form, title="Create Product")

@app.route('/inventory/product/<sku>/update', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def update_product(sku):
    original_product = products_collection.find_one({'_id': sku})
    if not original_product:
        flash("Product not found.", "danger")
        return redirect(url_for('product_list'))

    form = ProductUpdateForm(data=original_product)
    form.category.choices = [c['name'] for c in categories_collection.find().sort('name', 1)]
    form.category.choices.insert(0, "")

    if form.validate_on_submit():
        updated_data = {
            'name': form.name.data, 
            'category_name': form.category.data, 
            'price': float(form.price.data), 
            'reorder_level': int(form.reorder_level.data), 
            'status': form.status.data, 
            'date_updated': datetime.now(timezone.utc)
        }
        
        products_collection.update_one({'_id': sku}, {'$set': updated_data})
        
        changes = {}
        for key, value in updated_data.items():
            if key != 'date_updated' and original_product.get(key) != value:
                changes[key] = {"old": original_product.get(key), "new": value} 
                
        if changes:
            product_history_collection.insert_one({
                "product_sku": sku, 
                "timestamp": datetime.now(timezone.utc), 
                "user_username": current_user.username, 
                "change_type": "UPDATE", 
                "changes": changes
            })
            
        flash('Product updated successfully!', 'success')
        return redirect(url_for('product_detail', sku=sku))
        
    return render_template('inventory/product_form.html', form=form, title=f"Update Product: {original_product['name']}")

@app.route('/inventory/product/<sku>/delete', methods=['POST'])
@login_required
@role_required('Owner')
def delete_product(sku):
    products_collection.delete_one({'_id': sku})
    flash('Product has been permanently deleted.', 'success')
    return redirect(url_for('product_list'))

@app.route('/inventory/products/import', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def import_products():
    """Handles bulk import of products via CSV."""
    form = ProductImportForm()
    
    if form.validate_on_submit():
        file = form.csv_file.data
        stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        for row in csv_input:
            if not row.get('SKU') or not row.get('Name') or not row.get('Price'):
                errors.append(f"Row missing required fields: {row}")
                continue
                
            sku = row['SKU'].strip()
            
            if products_collection.find_one({'_id': sku}):
                skipped_count += 1
                continue
                
            try:
                new_product = {
                    "_id": sku,
                    "name": row['Name'].strip(),
                    "category_name": row.get('Category', '').strip(),
                    "price": float(row['Price']),
                    "quantity": int(row.get('Quantity', 0)),
                    "reorder_level": int(row.get('Reorder Level', 10)),
                    "status": "ACTIVE",
                    "date_created": datetime.now(timezone.utc),
                    "date_updated": datetime.now(timezone.utc)
                }
                
                products_collection.insert_one(new_product)
                
                product_history_collection.insert_one({
                    "product_sku": sku,
                    "timestamp": datetime.now(timezone.utc),
                    "user_username": current_user.username,
                    "change_type": "CREATE (BULK)",
                    "product_snapshot": new_product
                })
                
                if new_product['quantity'] > 0:
                     sales_collection.insert_one({
                        "sale_date": datetime.now(timezone.utc), 
                        "user_username": current_user.username, 
                        "total_amount": 0, 
                        "items_sold": [{
                            "product_sku": new_product['_id'], 
                            "product_name": new_product['name'], 
                            "quantity_sold": new_product['quantity'], 
                            "price_per_unit": new_product['price'], 
                            "type": "IN", 
                            "notes": "Bulk Import Initial Stock"
                        }]
                    })
                
                added_count += 1
                
            except ValueError as e:
                errors.append(f"Invalid data for SKU {sku}: {str(e)}")
        
        flash(f"Import Complete! Added: {added_count}, Skipped (Duplicate): {skipped_count}", "success")
        if errors:
            flash(f"Errors encountered: {len(errors)}. Check logs.", "warning")
            print(errors)
            
        return redirect(url_for('product_list'))

    return render_template('inventory/import_products.html', form=form)

@app.route('/inventory/barcodes')
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def barcode_tool():
    """Generates a printable page of barcodes for all active products."""
    products = list(products_collection.find({"status": "ACTIVE"}).sort("name", 1))
    return render_template('inventory/barcode_tool.html', products=products)

# ==============================================================================
# Supplier Management Routes
# ==============================================================================

@app.route('/suppliers')
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def supplier_list():
    suppliers = list(suppliers_collection.find({}))
    return render_template('inventory/supplier_list.html', supplier_list=suppliers)

@app.route('/supplier/add', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin')
def add_supplier():
    form = SupplierForm()
    if form.validate_on_submit():
        suppliers_collection.insert_one({"name": form.name.data, "contact_person": form.contact_person.data, "email": form.email.data, "phone": form.phone.data})
        flash('Supplier added successfully!', 'success')
        return redirect(url_for('supplier_list'))
    return render_template('inventory/supplier_form.html', form=form, title="Add New Supplier")

# ==============================================================================
# Purchase Order Routes
# ==============================================================================

@app.route('/purchase-orders')
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def purchase_order_list():
    form = POFilterForm(request.args, meta={'csrf': False})
    query = {}
    if form.validate():
        start_date = form.start_date.data
        end_date = form.end_date.data
        if form.status.data:
            query['status'] = form.status.data
        if start_date:
            query["order_date"] = {"$gte": datetime.combine(start_date, datetime.min.time())}
        if end_date:
            if "order_date" in query:
                query["order_date"]["$lte"] = datetime.combine(end_date, datetime.max.time())
            else:
                query["order_date"] = {"$lte": datetime.combine(end_date, datetime.max.time())}
                
    pos = list(purchase_orders_collection.find(query).sort("order_date", -1))
    return render_template('inventory/purchase_order_list.html', po_list=pos, filter_form=form)

@app.route('/purchase-order/<po_id>')
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def purchase_order_detail(po_id):
    po = purchase_orders_collection.find_one({'_id': ObjectId(po_id)})
    if not po:
        flash("Purchase Order not found.", "danger")
        return redirect(url_for('purchase_order_list'))
    return render_template('inventory/purchase_order_detail.html', po=po)

@app.route('/purchase-order/add', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def add_purchase_order():
    form = PurchaseOrderForm() 
    form.supplier.choices = [("", "--- Select a Supplier ---")] + [(str(s['_id']), s['name']) for s in suppliers_collection.find({})]
    
    if form.validate_on_submit():
        items_list = []
        for item_form in form.items.data:
            if not item_form['product_sku']:
                continue
            product = products_collection.find_one({'_id': item_form['product_sku']})
            if not product:
                flash(f"Product with SKU '{item_form['product_sku']}' not found.", 'danger')
                return render_template('inventory/purchase_order_form.html', form=form, title="Create Purchase Order")
            items_list.append({
                "product_sku": item_form['product_sku'], 
                "product_name": product['name'], 
                "quantity_ordered": item_form['quantity']
            })
        
        if not items_list:
            flash("You must add at least one valid item.", "danger")
            return render_template('inventory/purchase_order_form.html', form=form, title="Create Purchase Order")

        supplier = suppliers_collection.find_one({'_id': ObjectId(form.supplier.data)})
        new_po = {
            "order_date": datetime.now(timezone.utc), 
            "status": "PENDING", 
            "supplier_id": ObjectId(form.supplier.data),
            "supplier_name": supplier['name'], 
            "created_by_username": current_user.username, 
            "items": items_list
        }
        purchase_orders_collection.insert_one(new_po)
        flash('Purchase Order created successfully!', 'success')
        return redirect(url_for('purchase_order_list'))

    return render_template('inventory/purchase_order_form.html', form=form, title="Create Purchase Order")

@app.route('/purchase-order/<po_id>/complete', methods=['POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def complete_purchase_order(po_id):
    po = purchase_orders_collection.find_one({'_id': ObjectId(po_id)})
    if po and po['status'] == 'PENDING':
        completion_date = datetime.now(timezone.utc)
        for item in po['items']:
            products_collection.update_one(
                {'_id': item['product_sku']},
                {
                    '$inc': {'quantity': item['quantity_ordered']},
                    '$set': {'last_purchase_date': completion_date}
                }
            )
            product = products_collection.find_one({'_id': item['product_sku']})
            sales_collection.insert_one({
                "sale_date": completion_date, 
                "user_username": current_user.username, 
                "total_amount": 0,
                "items_sold": [{
                    "product_sku": item['product_sku'], 
                    "product_name": item['product_name'], 
                    "quantity_sold": item['quantity_ordered'], 
                    "price_per_unit": product['price'], 
                    "type": "IN", 
                    "notes": f"Stock received via Purchase Order #{po_id}."
                }]
            })
        purchase_orders_collection.update_one({'_id': ObjectId(po_id)}, {'$set': {'status': 'COMPLETED'}})
        flash(f'Purchase Order #{po_id} marked as completed and stock updated.', 'success')
    else:
        flash('This Purchase Order cannot be completed.', 'danger')
    return redirect(url_for('purchase_order_detail', po_id=po_id))

# ==============================================================================
# Edit History Route
# ==============================================================================

@app.route('/history/products')
@login_required
@role_required('Owner', 'Admin')
def product_history_list():
    form = ProductHistoryFilterForm(request.args, meta={'csrf': False})
    query = {}
    if form.validate():
        if form.product_sku.data:
            query['product_sku'] = form.product_sku.data
        if form.user.data:
            query['user_username'] = form.user.data
            
    history_logs = list(product_history_collection.find(query).sort("timestamp", -1))
    return render_template('inventory/product_history_list.html', history_list=history_logs, filter_form=form)
    
# ==============================================================================
# Transaction & Reporting Routes
# ==============================================================================

@app.route('/transactions')
@login_required
def transaction_list():
    form = TransactionFilterForm(request.args, meta={'csrf': False})
    query = {}
    if form.validate():
        if form.product.data:
            query['items_sold.product_sku'] = form.product.data 
        if form.transaction_type.data:
            query['items_sold.type'] = form.transaction_type.data 
            
    transactions = list(sales_collection.find(query).sort("sale_date", -1))
    return render_template('inventory/transaction_list.html', transaction_list=transactions, filter_form=form)

@app.route('/reports')
@login_required
@role_required('Owner', 'Admin')
def reporting_hub():
    form = SalesReportForm()
    return render_template('inventory/reporting.html', form=form)

@app.route('/reports/restock')
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def restock_report():
    """Generates a report of items that need restocking."""
    pipeline = [
        {"$match": {"status": "ACTIVE"}},
        {"$match": {"$expr": {"$lte": ["$quantity", "$reorder_level"]}}},
        {"$addFields": {
            "shortage": {"$subtract": ["$reorder_level", "$quantity"]}
        }},
        {"$sort": {"quantity": 1}} 
    ]
    restock_items = list(products_collection.aggregate(pipeline))
    return render_template('inventory/restock_report.html', items=restock_items, today=datetime.now(timezone.utc))

@app.route('/reports/export/inventory_csv')
@login_required
@role_required('Owner', 'Admin')
def export_inventory_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU', 'Name', 'Category', 'Price', 'Quantity', 'Reorder Level', 'Status', 'Last Purchase Date', 'Date Updated'])
    products = products_collection.find({})
    for product in products:
        last_purchase = product.get('last_purchase_date')
        last_purchase_str = last_purchase.strftime('%Y-%m-%d') if last_purchase else 'N/A'
        writer.writerow([
            product.get('_id'),
            product.get('name'),
            product.get('category_name'),
            product.get('price'),
            product.get('quantity'),
            product.get('reorder_level'),
            product.get('status'),
            last_purchase_str,
            product.get('date_updated').strftime('%Y-%m-%d') if product.get('date_updated') else ''
        ])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=inventory_report.csv"})

@app.route('/reports/export/sales_pdf')
@login_required
@role_required('Owner', 'Admin')
def export_sales_pdf():
    form = SalesReportForm(request.args, meta={'csrf': False})
    query = { "items_sold.type": "OUT" }
    start_date = form.start_date.data
    end_date = form.end_date.data
    
    if start_date:
        query["sale_date"] = {"$gte": datetime.combine(start_date, datetime.min.time())}
    if end_date:
        if "sale_date" in query:
            query["sale_date"]["$lte"] = datetime.combine(end_date, datetime.max.time())
        else:
            query["sale_date"] = {"$lte": datetime.combine(end_date, datetime.max.time())}
            
    sales_data = list(sales_collection.find(query).sort("sale_date", 1))
    html = render_template('inventory/sales_report_pdf.html', sales=sales_data, generation_date=datetime.now(timezone.utc), start_date=start_date, end_date=end_date)
    result = BytesIO()
    pdf = pisa.CreatePDF(BytesIO(html.encode("UTF-8")), dest=result)
    if not pdf.err:
        return Response(result.getvalue(), mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=sales_report.pdf'})
    flash("There was an error generating the PDF.", "danger")
    return redirect(url_for('reporting_hub'))
    
# ==============================================================================
# Analytics
# ==============================================================================

@app.route('/analytics')
@login_required
def analytics_dashboard():
    # CUSTOM CHECK: Allow if Owner/Admin OR if user has specific permission
    if not (current_user.group in ['Owner', 'Admin'] or current_user.has_permission('view_analytics')):
        flash("You do not have permission to view Analytics.", "danger")
        return redirect(url_for('home'))

    pipeline = [
        {"$unwind": "$items_sold"}, 
        {"$match": {"items_sold.type": "OUT"}}, 
        {"$lookup": {
            "from": "products",
            "localField": "items_sold.product_sku",
            "foreignField": "_id",
            "as": "product_info"
        }},
        {"$unwind": "$product_info"},
        {"$group": {
            "_id": "$product_info.category_name",
            "total_revenue": {"$sum": {"$multiply": ["$items_sold.quantity_sold", "$items_sold.price_per_unit"]}},
            "units_sold": {"$sum": "$items_sold.quantity_sold"}
        }},
        {"$sort": {"total_revenue": -1}}
    ]
    data = list(sales_collection.aggregate(pipeline))
    labels = [row['_id'] for row in data]
    values = [row['total_revenue'] for row in data]
    return render_template('inventory/analytics.html', labels=labels, values=values, table_data=data)

# ==============================================================================
# Admin Panel Routes
# ==============================================================================

@app.route('/admin')
@login_required
def admin_panel():
    # CUSTOM CHECK: Allow if Owner/Admin OR if user has specific permission
    if not (current_user.group in ['Owner', 'Admin'] or current_user.has_permission('view_admin')):
        flash("You do not have permission to access the Admin Panel.", "danger")
        return redirect(url_for('home'))

    counts = {
        'users': users_collection.count_documents({}),
        'products': products_collection.count_documents({'status': 'ACTIVE'}),
        'suppliers': suppliers_collection.count_documents({}),
        'orders_pending': purchase_orders_collection.count_documents({'status': 'PENDING'}),
        'orders_completed': purchase_orders_collection.count_documents({'status': 'COMPLETED'}),
        'categories': categories_collection.count_documents({}),
    }
    
    # Check if Master Password is set
    settings = settings_collection.find_one({'_id': 'global_config'})
    master_password_set = bool(settings and 'master_password' in settings)
    
    recent_history = list(product_history_collection.find().sort("timestamp", -1).limit(10))
    users = list(users_collection.find({}))
    
    # Create form for the modal
    master_pw_form = MasterPasswordForm()
    
    return render_template('admin/panel.html', 
                           counts=counts, 
                           history=recent_history, 
                           users=users,
                           master_pw_set=master_password_set,
                           master_pw_form=master_pw_form)

@app.route('/admin/settings/password', methods=['POST'])
@login_required
@role_required('Owner', 'Admin')
def set_master_password():
    """Handles the form submission to set or update the Master Password."""
    form = MasterPasswordForm()
    if form.validate_on_submit():
        hashed = pwd_context.hash(form.master_password.data)
        settings_collection.update_one(
            {'_id': 'global_config'},
            {'$set': {'master_password': hashed}},
            upsert=True
        )
        flash("Master Password updated successfully.", "success")
    else:
        flash("Error updating password.", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/user/add', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin')
def add_user():
    form = UserRegistrationForm()
    if form.validate_on_submit():
        if users_collection.find_one({'username': form.username.data}):
            flash('Username already exists. Please choose another.', 'danger')
        else:
            hashed_pw = pwd_context.hash(form.password.data)
            users_collection.insert_one({
                "username": form.username.data,
                "hashed_password": hashed_pw,
                "group": form.group.data
            })
            flash(f'User {form.username.data} created successfully!', 'success')
            return redirect(url_for('admin_panel'))
    return render_template('admin/register_user.html', form=form)

@app.route('/admin/user/edit/<user_id>', methods=['GET', 'POST'])
@login_required
@role_required('Owner') # God Mode: Only Owner can edit others
def edit_user(user_id):
    """Allows the Owner to edit a user's role, permissions, or reset their password."""
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user_data:
        flash("User not found.", "danger")
        return redirect(url_for('admin_panel'))

    if user_data['username'] == 'owner' and user_data['username'] != current_user.username:
         flash("You cannot edit the Super Owner account.", "danger")
         return redirect(url_for('admin_panel'))

    form = UserEditForm(data=user_data)
    
    # Pre-fill data
    if request.method == 'GET':
        form.group.data = user_data['group']
        # Load existing permissions into checkboxes
        current_perms = user_data.get('permissions', [])
        form.perm_analytics.data = 'view_analytics' in current_perms
        form.perm_admin.data = 'view_admin' in current_perms
        form.perm_history.data = 'view_history' in current_perms
        form.perm_refund.data = 'can_refund' in current_perms

    if form.validate_on_submit():
        update_fields = {
            "username": form.username.data,
            "group": form.group.data
        }

        # Build Permissions List based on checkboxes
        new_perms = []
        if form.perm_analytics.data: new_perms.append('view_analytics')
        if form.perm_admin.data: new_perms.append('view_admin')
        if form.perm_history.data: new_perms.append('view_history')
        if form.perm_refund.data: new_perms.append('can_refund')
        
        update_fields['permissions'] = new_perms
        
        if form.password.data:
            update_fields["hashed_password"] = pwd_context.hash(form.password.data)
            
        users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
        
        flash(f"User {form.username.data} updated. Permissions: {new_perms}", "success")
        return redirect(url_for('admin_panel'))
        
    return render_template('admin/edit_user.html', form=form, user=user_data)

@app.route('/admin/user/delete/<user_id>', methods=['POST'])
@login_required
@role_required('Owner')
def delete_user(user_id):
    user_to_delete = users_collection.find_one({'_id': ObjectId(user_id)})
    if user_to_delete and user_to_delete['username'] == current_user.username:
        flash('You cannot delete your own account!', 'danger')
    else:
        if user_to_delete:
            users_collection.delete_one({'_id': ObjectId(user_id)})
            flash('User account deleted.', 'success')
        else:
            flash('User not found.', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin')
def manage_categories():
    form = CategoryForm()
    if form.validate_on_submit():
        if categories_collection.find_one({'name': form.name.data}):
            flash('Category already exists.', 'warning')
        else:
            categories_collection.insert_one({'name': form.name.data})
            flash('Category added successfully!', 'success')
            return redirect(url_for('manage_categories'))
    categories = list(categories_collection.find().sort('name', 1))
    return render_template('admin/category_list.html', categories=categories, form=form)

@app.route('/admin/categories/delete/<cat_id>', methods=['POST'])
@login_required
@role_required('Owner', 'Admin')
def delete_category(cat_id):
    categories_collection.delete_one({'_id': ObjectId(cat_id)})
    flash('Category deleted.', 'success')
    return redirect(url_for('manage_categories'))

# ==============================================================================
# Point of Sale (POS) Routes
# ==============================================================================

@app.route('/pos')
@login_required
@role_required('Owner', 'Admin', 'Salesman', 'Stock Manager')
def pos_interface():
    """Renders the Point of Sale interface."""
    products = list(products_collection.find({"status": "ACTIVE"}).sort("name", 1))
    return render_template('inventory/pos.html', products=products)

@app.route('/pos/checkout', methods=['POST'])
@login_required
@role_required('Owner', 'Admin', 'Salesman', 'Stock Manager')
def pos_checkout():
    """API endpoint to process a JSON cart from the POS page."""
    data = request.get_json()
    cart_items = data.get('items', [])
    payment_info = data.get('payment', {}) 
    
    if not cart_items:
        return jsonify({"success": False, "message": "Cart is empty"}), 400

    total_sale_amount = 0
    sold_items_log = []
    
    # 1. Validate Stock Levels First
    for item in cart_items:
        product = products_collection.find_one({"_id": item['sku']})
        if not product or product['quantity'] < int(item['qty']):
            return jsonify({"success": False, "message": f"Not enough stock for {item['name']}"}), 400

    # 2. Process Transactions
    current_time = datetime.now(timezone.utc)
    
    for item in cart_items:
        qty = int(item['qty'])
        price = float(item['price'])
        discount = float(item.get('discount', 0)) 
        
        final_price_per_unit = price - discount
        
        products_collection.update_one(
            {"_id": item['sku']},
            {"$inc": {"quantity": -qty}}
        )
        
        total_sale_amount += (final_price_per_unit * qty)
        
        sold_items_log.append({
            "product_sku": item['sku'],
            "product_name": item['name'],
            "quantity_sold": qty,
            "original_price": price,
            "discount_per_unit": discount,
            "price_per_unit": final_price_per_unit,
            "type": "OUT",
            "notes": "POS Transaction"
        })

    result = sales_collection.insert_one({
        "sale_date": current_time,
        "user_username": current_user.username,
        "total_amount": total_sale_amount,
        "items_sold": sold_items_log,
        "payment_method": payment_info.get('method', 'Cash'),
        "amount_tendered": float(payment_info.get('tendered', 0)),
        "change_due": float(payment_info.get('change', 0)),
        "status": "COMPLETED" 
    })

    return jsonify({
        "success": True, 
        "message": "Transaction completed successfully!",
        "sale_id": str(result.inserted_id),
        "date": current_time.strftime('%Y-%m-%d %I:%M %p')
    })

@app.route('/transaction/<sale_id>/refund', methods=['POST'])
@login_required
def refund_transaction(sale_id):
    """Refunds a transaction. Supports Manager Override via Master Password."""
    
    # 1. Check Permissions / Override
    authorized = False
    refund_performer = current_user.username

    # Case A: User has explicit permission or is Owner/Admin
    if current_user.group in ['Owner', 'Admin', 'Stock Manager'] or current_user.has_permission('can_refund'):
        authorized = True
    
    # Case B: Master Password Override
    else:
        master_pw = request.form.get('master_password')
        if master_pw:
            if verify_master_password(master_pw):
                authorized = True
                refund_performer = f"{current_user.username} (Auth: Master PW)"
            else:
                flash("Invalid Master Password.", "danger")
                return redirect(url_for('transaction_list'))
        else:
            flash("Refund Unauthorized.", "danger")
            return redirect(url_for('transaction_list'))

    if not authorized:
        return redirect(url_for('transaction_list'))

    # 2. Process Refund
    sale = sales_collection.find_one({'_id': ObjectId(sale_id)})
    
    if not sale:
        flash("Transaction not found.", "danger")
        return redirect(url_for('transaction_list'))
        
    if sale.get('status') == 'REFUNDED':
        flash("This transaction has already been refunded.", "warning")
        return redirect(url_for('transaction_list'))

    # Return Stock
    for item in sale['items_sold']:
        if item['type'] == "OUT": 
            products_collection.update_one(
                {'_id': item['product_sku']},
                {'$inc': {'quantity': item['quantity_sold']}}
            )

    # Update Sale Status
    sales_collection.update_one(
        {'_id': ObjectId(sale_id)},
        {
            '$set': {
                'status': 'REFUNDED',
                'refunded_by': refund_performer,
                'refund_date': datetime.now(timezone.utc)
            }
        }
    )
    
    flash(f"Transaction {sale_id} refunded successfully.", "success")
    return redirect(url_for('transaction_list'))

def create_initial_users():
    """A helper function to create initial users with group-based roles."""
    print("Checking for initial users...")
    if users_collection.count_documents({}) == 0:
        print("No users found. Creating initial group-based users...")
        users_to_create = [
            {"username": "owner", "hashed_password": pwd_context.hash("ownerpass"), "group": "Owner"},
            {"username": "admin", "hashed_password": pwd_context.hash("adminpass"), "group": "Admin"},
            {"username": "manager", "hashed_password": pwd_context.hash("managerpass"), "group": "Stock Manager"},
            {"username": "sales", "hashed_password": pwd_context.hash("salespass"), "group": "Salesman"}
        ]
        users_collection.insert_many(users_to_create)
        print("Initial users created successfully.")
    else:
        print("Users already exist.")

# ==============================================================================
# Main Execution
# ==============================================================================

if __name__ == '__main__':
    create_initial_users()
    app.run(debug=True, use_reloader=False)