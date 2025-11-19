from database import products_collection, sales_collection, suppliers_collection

def create_indexes():
    print("Creating database indexes for optimization...")

    # 1. Products
    # (Note: _id is indexed automatically by MongoDB, so we skip it)
    products_collection.create_index([("category_name", 1)])
    products_collection.create_index([("status", 1)])
    print(" - Product indexes created.")

    # 2. Sales
    sales_collection.create_index([("sale_date", -1)])
    sales_collection.create_index([("items_sold.product_sku", 1)])
    print(" - Sales indexes created.")

    # 3. Suppliers
    suppliers_collection.create_index([("name", 1)], unique=True)
    print(" - Supplier indexes created.")

    print("Optimization complete! Database is now indexed.")

if __name__ == "__main__":
    create_indexes()