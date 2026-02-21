import random
import uuid
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from inventory.models import (
    Category, Supplier, Product, PurchaseOrder, PurchaseOrderItem, 
    StockTransaction, Customer, CustomerPayment, POSSale, 
    ExpenseCategory, Expense, HydraulicSow
)

class Command(BaseCommand):
    help = 'Populates the database with sample data for testing all features.'

    def handle(self, *args, **kwargs):
        # Clear existing data to prevent duplicates on re-seed
        self.clear_data()
        self.stdout.write("Seeding data...")

        # 1. Get or Create Admin User for logs
        user = User.objects.first()
        if not user:
            user = User.objects.create_superuser('admin', 'admin@example.com', 'password123')
            self.stdout.write("Created superuser: admin / password123")

        # 2. Create Product Categories
        categories = [
            'Engine Parts', 'Tires & Wheels', 'Braking System', 
            'Fluids & Chemicals', 'Accessories', 'Batteries'
        ]
        cat_objs = []
        for name in categories:
            cat, created = Category.objects.get_or_create(name=name)
            cat_objs.append(cat)
        self.stdout.write(f"Created {len(cat_objs)} categories.")

        # 3. Create Suppliers
        suppliers_data = [
            {'name': 'Global Auto Parts', 'contact': 'John Smith', 'email': 'john@globalauto.com', 'phone': '0917-123-4567'},
            {'name': 'Manila Rubber Corp', 'contact': 'Maria Cruz', 'email': 'maria@mrc.ph', 'phone': '0918-555-0101'},
            {'name': 'Lubricants Express', 'contact': 'David Lee', 'email': 'sales@lubex.com', 'phone': '02-8888-1234'},
        ]
        sup_objs = []
        for data in suppliers_data:
            sup, created = Supplier.objects.get_or_create(name=data['name'], defaults={
                'contact_person': data['contact'],
                'email': data['email'],
                'phone': data['phone']
            })
            sup_objs.append(sup)
        self.stdout.write(f"Created {len(sup_objs)} suppliers.")
        
        # 4. Create Customers
        self.stdout.write("Creating customers...")
        customers_data = [
            {'name': 'John Doe Garage', 'email': 'johndoe@example.com', 'phone': '0917-111-2222', 'address': '123 Main St, QC', 'credit_limit': 50000},
            {'name': 'Maria\'s Auto Repair', 'email': 'maria@repair.com', 'phone': '0918-333-4444', 'address': '456 Service Rd, Pasig', 'credit_limit': 25000},
            {'name': 'Walk-in Customer', 'address': 'Store Counter', 'credit_limit': 0},
        ]
        customer_objs = []
        for data in customers_data:
            cust, created = Customer.objects.get_or_create(name=data['name'], defaults=data)
            customer_objs.append(cust)
        self.stdout.write(f"Created {len(customer_objs)} customers.")
        walk_in_customer = Customer.objects.get(name="Walk-in Customer")
        
        # 4. Create Products
        products_data = [
            {'name': 'Motolite Gold Battery', 'sku': 'BAT-001', 'cat': 'Batteries', 'price': 4500.00, 'qty': 20},
            {'name': 'Shell Helix Ultra 5W-40', 'sku': 'OIL-SH-5W40', 'cat': 'Fluids & Chemicals', 'price': 2800.00, 'qty': 50},
            {'name': 'Brembo Brake Pads (Front)', 'sku': 'BRK-PAD-F', 'cat': 'Braking System', 'price': 3500.00, 'qty': 15},
            {'name': 'Michelin Pilot Sport 4', 'sku': 'TIRE-MICH-18', 'cat': 'Tires & Wheels', 'price': 12500.00, 'qty': 8},
            {'name': 'Spark Plug (NGK)', 'sku': 'SPK-NGK-01', 'cat': 'Engine Parts', 'price': 250.00, 'qty': 200},
            {'name': 'Car Mat Set (Universal)', 'sku': 'ACC-MAT-UNI', 'cat': 'Accessories', 'price': 1200.00, 'qty': 12},
            {'name': 'Oil Filter (Bosch)', 'sku': 'FLT-OIL-B01', 'cat': 'Engine Parts', 'price': 450.00, 'qty': 45},
            {'name': 'Brake Fluid DOT4', 'sku': 'FLD-BRK-DOT4', 'cat': 'Fluids & Chemicals', 'price': 350.00, 'qty': 60},
        ]

        prod_objs = []
        for p_data in products_data:
            cat = Category.objects.get(name=p_data['cat'])
            prod, created = Product.objects.get_or_create(
                sku=p_data['sku'],
                defaults={
                    'name': p_data['name'],
                    'category': cat,
                    'price': p_data['price'],
                    'quantity': p_data['qty'], # Initial Qty
                    'reorder_level': 10,
                    'status': 'ACTIVE'
                }
            )
            prod_objs.append(prod)
            
            # Create Initial Stock Transaction if new
            if created:
                StockTransaction.objects.create(
                    product=prod,
                    transaction_type='IN',
                    transaction_reason='INITIAL',
                    quantity=p_data['qty'],
                    user=user,
                    notes="Initial system setup"
                )
        self.stdout.write(f"Created {len(prod_objs)} products.")

        # 5. Create Expense Categories and Expenses
        self.stdout.write("Creating expense categories and expenses...")
        exp_cats_data = ['Rent', 'Utilities', 'Salaries', 'Supplies', 'Marketing']
        exp_cat_objs = []
        for name in exp_cats_data:
            cat, _ = ExpenseCategory.objects.get_or_create(name=name)
            exp_cat_objs.append(cat)
        
        for _ in range(25): # Create 25 random expenses
            random_days = random.randint(0, 30)
            exp_date = timezone.now().date() - timedelta(days=random_days)
            Expense.objects.create(
                category=random.choice(exp_cat_objs),
                description=f"Sample {random.choice(exp_cat_objs).name} expense",
                amount=Decimal(random.uniform(500, 15000)).quantize(Decimal('0.01')),
                expense_date=exp_date,
                recorded_by=user
            )
        self.stdout.write("Created 25 random expenses.")

        # 6. Create Hydraulic SOWs
        self.stdout.write("Creating Hydraulic SOWs...")
        for i in range(5):
            cust = random.choice(customer_objs)
            sow = HydraulicSow.objects.create(
                customer=cust, created_by=user, hose_type=f"Type {random.choice(['A', 'B', 'C'])}",
                diameter=f"1/{random.randint(2,8)}", application=f"Excavator Arm {i+1}",
                cost=Decimal(random.uniform(1500, 8000)).quantize(Decimal('0.01'))
            )
            POSSale.objects.create(receipt_id=sow.sow_id, customer=cust, cashier=user, payment_method='CREDIT', total_amount=sow.cost, notes=f"Hydraulic Job #{sow.id}")
        self.stdout.write("Created 5 Hydraulic SOWs with charges.")

        # PO #1: PENDING (In Transit)
        po1 = PurchaseOrder.objects.create(supplier=sup_objs[0], status='PENDING')
        PurchaseOrderItem.objects.create(purchase_order=po1, product=prod_objs[0], quantity=10, price=4000.00)
        PurchaseOrderItem.objects.create(purchase_order=po1, product=prod_objs[2], quantity=5, price=3000.00)
        
        # PO #2: COMPLETED (Arrived - Ready to Receive)
        po2 = PurchaseOrder.objects.create(supplier=sup_objs[1], status='COMPLETED')
        PurchaseOrderItem.objects.create(purchase_order=po2, product=prod_objs[3], quantity=4, price=11000.00)

        # PO #3: RECEIVED (Stock Added)
        po3 = PurchaseOrder.objects.create(supplier=sup_objs[2], status='RECEIVED')
        item = PurchaseOrderItem.objects.create(purchase_order=po3, product=prod_objs[1], quantity=20, price=2400.00)
        # Manually create the log since we bypassed the view logic
        StockTransaction.objects.create(
            product=prod_objs[1],
            transaction_type='IN',
            transaction_reason='PO',
            quantity=20,
            user=user,
            notes=f"Received from Purchase Order PO #{po3.id}",
            timestamp=timezone.now() - timedelta(days=5)
        )
        
        self.stdout.write("Created 3 Purchase Orders (Pending, Arrived, Received).")

        # 7. Generate POS History
        self.stdout.write("Generating POS transaction history...")
        end_date = timezone.now()
        for _ in range(50):
            random_days = random.randint(0, 30)
            txn_date = end_date - timedelta(days=random_days)
            
            is_walk_in = random.random() < 0.4
            customer = walk_in_customer if is_walk_in else random.choice(customer_objs[:-1])
            payment_method = 'CASH' if is_walk_in else random.choice(['CASH', 'CREDIT', 'CARD'])

            sale_record = POSSale.objects.create(
                receipt_id=f"REC-{uuid.uuid4().hex[:8].upper()}",
                cashier=user, 
                customer=customer, 
                payment_method=payment_method, 
                timestamp=txn_date
            )
            
            total_cost = Decimal('0')
            num_items = random.randint(1, 4)
            
            with transaction.atomic():
                for _ in range(num_items):
                    product = random.choice(prod_objs)
                    if product.quantity > 0:
                        qty = random.randint(1, min(3, product.quantity))
                        StockTransaction.objects.create(
                            product=product, pos_sale=sale_record, transaction_type='OUT',
                            transaction_reason='SALE', quantity=qty, selling_price=product.price,
                            user=user, timestamp=txn_date, notes=f"POS Sale: {sale_record.receipt_id}"
                        )
                        product.quantity -= qty
                        product.save()
                        total_cost += (Decimal(str(product.price)) * qty)

                if total_cost > 0:
                    sale_record.total_amount = total_cost
                    if payment_method == 'CASH':
                        sale_record.amount_paid = total_cost
                    sale_record.save()
                else:
                    sale_record.delete()
        self.stdout.write("Generated 50 POS sales.")

        # 8. Generate some payments for credit sales
        self.stdout.write("Generating customer payments for credit sales...")
        credit_sales = POSSale.objects.filter(payment_method='CREDIT')
        for sale in credit_sales:
            if random.random() < 0.5:
                payment_date = sale.timestamp + timedelta(days=random.randint(1, 15))
                payment_amount = sale.total_amount if random.random() < 0.7 else sale.total_amount / 2
                CustomerPayment.objects.create(
                    customer=sale.customer, sale_paid=sale, amount=payment_amount.quantize(Decimal('0.01')),
                    payment_date=payment_date, recorded_by=user, notes="Seed data payment"
                )
        self.stdout.write("Generated random payments.")

        # 9. Generate Returns and Damages
        self.stdout.write("Generating returns and damages...")
        for _ in range(10):
            sale_to_return = POSSale.objects.filter(items__isnull=False).order_by('?').first()
            if sale_to_return:
                item_to_return = sale_to_return.items.order_by('?').first()
                if item_to_return:
                    StockTransaction.objects.create(
                        product=item_to_return.product, transaction_type='IN', transaction_reason='RETURN',
                        quantity=1, selling_price=item_to_return.selling_price,
                        user=user,
                        timestamp=sale_to_return.timestamp + timedelta(days=random.randint(1,3)),
                        notes=f"Return for {sale_to_return.receipt_id}"
                    )
                    item_to_return.product.quantity += 1
                    item_to_return.product.save()

        for _ in range(10):
            product = random.choice(prod_objs)
            if product.quantity > 0:
                with transaction.atomic():
                    product_to_damage = Product.objects.select_for_update().get(pk=product.pk)
                    if product_to_damage.quantity > 0:
                        product_to_damage.quantity -= 1
                        product_to_damage.save()
                        StockTransaction.objects.create(
                            product=product_to_damage, transaction_type='OUT', transaction_reason='DAMAGE',
                            quantity=1, user=user, timestamp=timezone.now() - timedelta(days=random.randint(1,30)),
                            notes="Damaged during handling (seed)"
                        )
        self.stdout.write("Generated returns and damages.")
        self.stdout.write(self.style.SUCCESS('Successfully seeded database with sample data!'))

    def clear_data(self):
        """Deletes data from models to prepare for fresh seeding."""
        self.stdout.write("Clearing old data...")
        # Order is important to respect foreign key constraints
        models_to_clear = [
            StockTransaction, PurchaseOrderItem, PurchaseOrder, 
            POSSale, CustomerPayment, HydraulicSow, Customer, 
            Expense, ExpenseCategory, Product, Category, Supplier
        ]
        for model in models_to_clear:
            try:
                if model.objects.exists():
                    model.objects.all().delete()
                    self.stdout.write(f"  - Cleared {model.__name__}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error clearing {model.__name__}: {e}"))