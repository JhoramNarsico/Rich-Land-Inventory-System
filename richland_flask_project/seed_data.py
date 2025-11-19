import random
from datetime import datetime, timedelta, timezone
from database import products_collection, suppliers_collection, sales_collection, users_collection

CATEGORIES = ['Engine', 'Suspension', 'Brakes', 'Electrical', 'Body', 'Transmission']
PART_NAMES = ['Spark Plug', 'Brake Pad', 'Oil Filter', 'Alternator', 'Headlight Bulb', 'Battery', 'Timing Belt', 'Shock Absorber', 'Clutch Disc', 'Radiator']
SUPPLIERS = ['Toyota Genuine Parts', 'Bosch Automotive', 'Denso Ph', 'Motul Oils', 'NGK Spark Plugs', 'Brembo Brakes', 'KYB Shocks', 'Panasonic Batteries']

def seed_database():
    print("Generating 30+ records to meet Milestone 3 requirements...")
    
    # 1. Suppliers
    for name in SUPPLIERS:
        if not suppliers_collection.find_one({"name": name}):
            suppliers_collection.insert_one({
                "name": name, "contact_person": "Manager " + name.split()[0],
                "email": f"contact@{name.replace(' ', '').lower()}.com", "phone": f"0917-{random.randint(100,999)}-{random.randint(1000,9999)}"
            })

    # 2. Products (Target: 30+)
    if products_collection.count_documents({}) < 30:
        for i in range(35):
            cat = random.choice(CATEGORIES)
            name = f"{random.choice(PART_NAMES)} - {cat} {random.choice(['A', 'B', 'X'])}"
            sku = f"SKU-{random.randint(10000, 99999)}"
            if not products_collection.find_one({"_id": sku}):
                products_collection.insert_one({
                    "_id": sku, "name": name, "category_name": cat,
                    "price": float(random.randint(150, 5000)), "quantity": random.randint(0, 100),
                    "reorder_level": 10, "status": "ACTIVE",
                    "date_created": datetime.now(timezone.utc), "date_updated": datetime.now(timezone.utc)
                })

    # 3. Sales (Target: 50+)
    products = list(products_collection.find({"status": "ACTIVE"}))
    users = list(users_collection.find({}))
    if products and users:
        for i in range(50):
            prod = random.choice(products)
            qty = random.randint(1, 5)
            sales_collection.insert_one({
                "sale_date": datetime.now(timezone.utc) - timedelta(days=random.randint(0, 60)),
                "user_username": random.choice(users)['username'],
                "total_amount": prod['price'] * qty,
                "items_sold": [{"product_sku": prod['_id'], "product_name": prod['name'], 
                                "quantity_sold": qty, "price_per_unit": prod['price'], "type": "OUT"}]
            })
    print("Seeding Complete.")

if __name__ == "__main__":
    seed_database()