import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from inventory.models import Category, Supplier, Product, PurchaseOrder, PurchaseOrderItem, StockTransaction

class Command(BaseCommand):
    help = 'Populates the database with sample data for testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding data...")

        # 1. Get or Create Admin User for logs
        user = User.objects.first()
        if not user:
            user = User.objects.create_superuser('admin', 'admin@example.com', 'password123')
            self.stdout.write("Created superuser: admin / password123")

        # 2. Create Categories
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

        # 5. Create Purchase Orders (Testing Workflow)
        
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

        # 6. Generate History (Sales, Damage, Returns)
        # Spread over last 30 days for Analytics
        self.stdout.write("Generating transaction history...")
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # Create 50 random transactions
        for _ in range(50):
            random_days = random.randint(0, 30)
            txn_date = end_date - timedelta(days=random_days)
            product = random.choice(prod_objs)
            
            # Determine type
            dice = random.randint(1, 100)
            
            if dice <= 80: # 80% Sales
                qty = random.randint(1, 5)
                # Ensure we don't go negative
                if product.quantity >= qty:
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type='OUT',
                        transaction_reason='SALE',
                        quantity=qty,
                        selling_price=product.price, # Revenue
                        user=user,
                        timestamp=txn_date,
                        notes=f"Walk-in customer sales"
                    )
                    product.quantity -= qty
                    product.save()
            
            elif dice <= 90: # 10% Returns
                qty = random.randint(1, 2)
                StockTransaction.objects.create(
                    product=product,
                    transaction_type='IN',
                    transaction_reason='RETURN',
                    quantity=qty,
                    selling_price=product.price, # Negative Revenue calculation
                    user=user,
                    timestamp=txn_date,
                    notes="Customer bought wrong item"
                )
                product.quantity += qty
                product.save()
                
            else: # 10% Damage
                qty = 1
                if product.quantity >= qty:
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type='OUT',
                        transaction_reason='DAMAGE',
                        quantity=qty,
                        selling_price=product.price, # Loss Value
                        user=user,
                        timestamp=txn_date,
                        notes="Damaged during handling"
                    )
                    product.quantity -= qty
                    product.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded database with sample data!'))