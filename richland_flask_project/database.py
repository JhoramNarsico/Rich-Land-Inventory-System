# database.py

import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

# Establish a connection to the MongoDB server
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# --- Define all the collections your application will use ---
# This ensures that any file importing from here can find them.

users_collection = db.users
products_collection = db.products
sales_collection = db.sales
purchase_orders_collection = db.purchase_orders
suppliers_collection = db.suppliers
product_history_collection = db.product_history

# ADD THIS LINE:
categories_collection = db.categories

print("Database collections initialized.")