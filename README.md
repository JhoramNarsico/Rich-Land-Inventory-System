# Rich Land Auto Supply - Inventory System

This document provides instructions on how to set up and run the Rich Land Auto Supply Inventory System project on a local development machine. This project is a web application built using the Django framework in Python. It has also REST API which we use the Django REST Framework (DRF), a powerful and flexible toolkit for building Web APIs.

## Prerequisites

Before you start, make sure you have the following software installed on your computer:

*   **Python** 
*   **Git:** 
*   **pip**
*   **MySQL Server**

## Setup Instructions

Follow these steps to get the project running.

### 1. Clone the Repository

Open your terminal or command prompt and clone the project from its GitHub repository.

```bash
# Replace <your-repository-url> with the actual URL from GitHub
git clone <your-repository-url>

# Navigate into the project directory
cd richland_inventory

```
2. Create and Activate a Virtual Environment
Using a virtual environment is highly recommended to isolate project dependencies.

```bash

# Step 1: Create the virtual environment
python -m venv venv
```

```bash
# Step 2: Activate the virtual environment using PowerShell
.\venv\Scripts\activate

```
```bash
#IF there is an error activating the virtual environment, input this
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```
3. Install Required Packages
   
```bash
python -m pip install Django PyMySQL djangorestframework python-decouple cryptography
```
4. Set Up the MySQL Database

```bash
# Create a new database. We recommend using utf8mb4 for full Unicode support.
CREATE DATABASE richland_inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

#Create a new user and grant it privileges on the new database. Replace 'your_password' with a secure password.
CREATE USER 'your_db_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON richland_inventory_db.* TO 'your_db_user'@'localhost';
FLUSH PRIVILEGES;

```
6. Creating a .env file.
In the same directory as your manage.py file (the root of your project), create a new file named .env.
```bash
# .env
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY='django-insecure-eoqpafol0v1q51=nbciaya+4$2r6)(b3do$jdncm)pz81q7zl#'

# Set to False in production!
DEBUG=True

# In production, set this to your domain names e.g., 'www.yourdomain.com,yourdomain.com'
ALLOWED_HOSTS='127.0.0.1,localhost'

# -- Database Configuration --
DB_NAME='richland_inventory_db'
DB_USER='root'
DB_PASSWORD='your own password'
DB_HOST='localhost'
DB_PORT='3306'

```

6. Apply Database Migrations
   
 ```bash
python manage.py makemigrations

python manage.py migrate
```
(NOTED: You only need to run migrations when your database schema is out of sync with your Django models.)

5. Create an Administrator Account

 ```bash
python manage.py createsuperuser

```
How to Run the Application

 ```bash
python manage.py runserver

```
Access the Application:

Open your web browser and go to the following addresses:

* Main Application: http://127.0.0.1:8000

* Admin Panel: http://127.0.0.1:8000/admin/


Access these API endpoints in your browser or using a tool like Postman.

*   List all products (GET): http://127.0.0.1:8000/api/products/
*   Retrieve a specific product (GET): http://127.0.0.1:8000/api/products/1/
*   Create a new product (POST): http://127.0.0.1:8000/api/products/
*   Update a product (PUT/PATCH): http://127.0.0.1:8000/api/products/1/
*   Delete a product (DELETE): http://127.0.0.1:8000/api/products/1/







