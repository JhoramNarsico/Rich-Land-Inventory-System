# ==============================================================================
# app.py - Main Flask Application for Rich Land Auto Supply
# ==============================================================================

# --- Core Imports ---
import os
import csv
from io import BytesIO, StringIO
from datetime import datetime, timezone
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for, flash, Response)
from dotenv import load_dotenv
from passlib.context import CryptContext
from bson.objectid import ObjectId
from xhtml2pdf import pisa

# --- Flask Extension Imports ---
from flask_login import (LoginManager, login_user, logout_user, login_required, current_user)

# --- Project-Specific Imports ---
from database import (
    users_collection, products_collection, sales_collection,
    purchase_orders_collection, suppliers_collection, product_history_collection
)
from models import User
from forms import (
    LoginForm, ProductCreateForm, ProductUpdateForm, StockTransactionForm,
    ProductFilterForm, TransactionFilterForm, SupplierForm, PurchaseOrderForm,
    ProductHistoryFilterForm, SalesReportForm
)

# ==============================================================================
# Application Setup & Configuration
# ==============================================================================

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

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

# ==============================================================================
# Core Application Routes (Dashboard)
# ==============================================================================

@app.route('/')
@login_required
def home():
    low_stock_pipeline = [
        {"$match": {"status": "ACTIVE"}},
        {"$match": {"$expr": {"$lte": ["$quantity", "$reorder_level"]}}},
        {"$sort": {"quantity": 1}}
    ]
    low_stock_products = list(products_collection.aggregate(low_stock_pipeline))
    metrics_pipeline = [
        {"$match": {"status": "ACTIVE"}},
        {"$group": {"_id": None, "total_products": {"$sum": 1}, "total_stock_value": {"$sum": {"$multiply": ["$price", "$quantity"]}}}}
    ]
    metrics_data = list(products_collection.aggregate(metrics_pipeline))
    metrics = metrics_data[0] if metrics_data else {"total_products": 0, "total_stock_value": 0}
    recent_products = list(products_collection.find().sort("date_created", -1).limit(5))
    return render_template('home.html', low_stock_products=low_stock_products, low_stock_products_count=len(low_stock_products), total_products=metrics['total_products'], total_stock_value=metrics['total_stock_value'], recent_products=recent_products)

# ==============================================================================
# Product Management Routes
# ==============================================================================

@app.route('/inventory/products')
@login_required
def product_list():
    form = ProductFilterForm(request.args)
    query = {"status": "ACTIVE"}
    sort_by = request.args.get('sort_by', '-date_created')
    if form.validate():
        if form.q.data:
            query['$or'] = [{'name': {'$regex': form.q.data, '$options': 'i'}}, {'_id': {'$regex': form.q.data, '$options': 'i'}}]
        if form.category.data:
            query['category_name'] = form.category.data
        if form.product_status.data:
            query['status'] = form.product_status.data
    sort_field, sort_order = (sort_by[1:], -1) if sort_by.startswith('-') else (sort_by, 1)
    products = list(products_collection.find(query).sort(sort_field, sort_order))
    return render_template('inventory/product_list.html', product_list=products, filter_form=form)

@app.route('/inventory/product/<sku>', methods=['GET', 'POST'])
@login_required
def product_detail(sku):
    product = products_collection.find_one({'_id': sku})
    transaction_form = StockTransactionForm()
    if transaction_form.validate_on_submit():
        quantity = transaction_form.quantity.data
        trans_type = transaction_form.transaction_type.data
        if trans_type == 'OUT' and product['quantity'] < quantity:
            flash('Cannot stock out more than the available quantity.', 'danger')
            return redirect(url_for('product_detail', sku=sku))
        update_quantity = quantity if trans_type == 'IN' else -quantity
        products_collection.update_one({'_id': sku}, {'$inc': {'quantity': update_quantity}})
        sales_collection.insert_one({"sale_date": datetime.now(timezone.utc), "user_username": current_user.username, "total_amount": product['price'] * quantity if trans_type == 'OUT' else 0, "items_sold": [{"product_sku": sku, "product_name": product['name'], "quantity_sold": quantity, "price_per_unit": product['price'], "type": trans_type, "notes": transaction_form.notes.data}]})
        flash('Stock adjusted successfully!', 'success')
        return redirect(url_for('product_detail', sku=sku))
    recent_transactions = list(sales_collection.find({"items_sold.product_sku": sku}).sort("sale_date", -1).limit(10))
    return render_template('inventory/product_detail.html', product=product, transaction_form=transaction_form, transactions=recent_transactions)

@app.route('/inventory/product/add', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def add_product():
    form = ProductCreateForm()
    if form.validate_on_submit():
        if products_collection.find_one({'_id': form.sku.data}):
            flash('Product with this SKU already exists.', 'danger')
            return render_template('inventory/product_form.html', form=form, title="Create Product")
        new_product = {"_id": form.sku.data, "name": form.name.data, "category_name": form.category.data, "price": float(form.price.data), "quantity": int(form.quantity.data), "reorder_level": int(form.reorder_level.data), "status": "ACTIVE", "date_created": datetime.now(timezone.utc), "date_updated": datetime.now(timezone.utc)}
        products_collection.insert_one(new_product)
        product_history_collection.insert_one({"product_sku": new_product['_id'], "timestamp": datetime.now(timezone.utc), "user_username": current_user.username, "change_type": "CREATE", "product_snapshot": new_product})
        if new_product['quantity'] > 0:
            sales_collection.insert_one({"sale_date": datetime.now(timezone.utc), "user_username": current_user.username, "total_amount": 0, "items_sold": [{"product_sku": new_product['_id'], "product_name": new_product['name'], "quantity_sold": new_product['quantity'], "price_per_unit": new_product['price'], "type": "IN", "notes": "Initial stock on product creation."}]})
        flash('Product created successfully!', 'success')
        return redirect(url_for('product_list'))
    return render_template('inventory/product_form.html', form=form, title="Create Product")

@app.route('/inventory/product/<sku>/update', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def update_product(sku):
    original_product = products_collection.find_one({'_id': sku})
    form = ProductUpdateForm(data=original_product)
    if form.validate_on_submit():
        updated_data = {'name': form.name.data, 'category_name': form.category.data, 'price': float(form.price.data), 'reorder_level': int(form.reorder_level.data), 'status': form.status.data, 'date_updated': datetime.now(timezone.utc)}
        products_collection.update_one({'_id': sku}, {'$set': updated_data})
        changes = {}
        for key, value in updated_data.items():
            if key != 'date_updated' and original_product.get(key) != value:
                changes[key] = {"old": original_product.get(key), "new": value}
        if changes:
            product_history_collection.insert_one({"product_sku": sku, "timestamp": datetime.now(timezone.utc), "user_username": current_user.username, "change_type": "UPDATE", "changes": changes})
        flash('Product updated successfully!', 'success')
        return redirect(url_for('product_detail', sku=sku))
    return render_template('inventory/product_form.html', form=form, title="Update Product")

@app.route('/inventory/product/<sku>/delete', methods=['POST'])
@login_required
@role_required('Owner')
def delete_product(sku):
    products_collection.delete_one({'_id': sku})
    flash('Product has been permanently deleted.', 'success')
    return redirect(url_for('product_list'))

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
    pos = list(purchase_orders_collection.find({}).sort("order_date", -1))
    return render_template('inventory/purchase_order_list.html', po_list=pos)

@app.route('/purchase-order/<po_id>')
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def purchase_order_detail(po_id):
    po = purchase_orders_collection.find_one({'_id': ObjectId(po_id)})
    return render_template('inventory/purchase_order_detail.html', po=po)

@app.route('/purchase-order/add', methods=['GET', 'POST'])
@login_required
@role_required('Owner', 'Admin', 'Stock Manager')
def add_purchase_order():
    form = PurchaseOrderForm()
    form.supplier.choices = [(str(s['_id']), s['name']) for s in suppliers_collection.find({})]
    if form.validate_on_submit():
        items_list = []
        for item_form in form.items.data:
            product = products_collection.find_one({'_id': item_form['product_sku']})
            if not product:
                flash(f"Product with SKU '{item_form['product_sku']}' not found.", 'danger')
                return render_template('inventory/purchase_order_form.html', form=form, title="Create Purchase Order")
            items_list.append({"product_sku": item_form['product_sku'], "product_name": product['name'], "quantity_ordered": item_form['quantity']})
        supplier = suppliers_collection.find_one({'_id': ObjectId(form.supplier.data)})
        new_po = {"order_date": datetime.now(timezone.utc), "status": "PENDING", "supplier_id": ObjectId(form.supplier.data), "supplier_name": supplier['name'], "created_by_username": current_user.username, "items": items_list}
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
        for item in po['items']:
            products_collection.update_one({'_id': item['product_sku']}, {'$inc': {'quantity': item['quantity_ordered']}})
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
    form = ProductHistoryFilterForm(request.args)
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
    form = TransactionFilterForm(request.args)
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
    """Renders the main reporting page and provides the date-picker form."""
    form = SalesReportForm()
    return render_template('inventory/reporting.html', form=form)

@app.route('/reports/export/inventory_csv')
@login_required
@role_required('Owner', 'Admin')
def export_inventory_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU', 'Name', 'Category', 'Price', 'Quantity', 'Reorder Level', 'Status', 'Date Updated'])
    products = products_collection.find({})
    for product in products:
        writer.writerow([product.get('_id'), product.get('name'), product.get('category_name'), product.get('price'), product.get('quantity'), product.get('reorder_level'), product.get('status'), product.get('date_updated').strftime('%Y-%m-%d') if product.get('date_updated') else ''])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=inventory_report.csv"})

@app.route('/reports/export/sales_pdf')
@login_required
@role_required('Owner', 'Admin')
def export_sales_pdf():
    form = SalesReportForm(request.args)
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
# Helper Script for User Creation
# ==============================================================================

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
        print("Initial users created successfully:")
        print("- owner / ownerpass (Group: Owner)")
        print("- admin / adminpass (Group: Admin)")
        print("- manager / managerpass (Group: Stock Manager)")
        print("- sales / salespass (Group: Salesman)")
    else:
        print("Users already exist.")

# ==============================================================================
# Main Execution
# ==============================================================================

if __name__ == '__main__':
    create_initial_users()
    app.run(debug=True)