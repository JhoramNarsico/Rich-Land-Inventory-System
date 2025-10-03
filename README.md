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

# Step 2: Activate the virtual environment using PowerShell
.\venv\Scripts\activate

#IF there is an error activating the virtual environment, input this
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```
3. Install Required Packages
   
```bash
pip install Django

```
```bash
pip install mysqlclient
```
```bash
pip install djangorestframework
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
5. Configure Django Settings
```bash
#Locate the settings.py file in your project (e.g., core/settings.py).
# core/settings.py

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'richland_inventory_db',
        'USER': 'your_db_user',          # The user you created
        'PASSWORD': 'your_password',      # The password you set
        'HOST': 'localhost',              # Or your DB host IP
        'PORT': '3306',                   # Default MySQL port
    }
}

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

Main Application: http://127.0.0.1:8000

Admin Panel: http://127.0.0.1:8000/admin/


Access these API endpoints in your browser or using a tool like Postman.

*   List all products (GET): http://127.0.0.1:8000/api/products/
*   Retrieve a specific product (GET): http://127.0.0.1:8000/api/products/1/
*   Create a new product (POST): http://127.0.0.1:8000/api/products/
*   Update a product (PUT/PATCH): http://127.0.0.1:8000/api/products/1/
*   Delete a product (DELETE): http://127.0.0.1:8000/api/products/1/



# How to Edit and Customize the Program
# Understanding the project structure is key to making changes.
Project Structure Overview

*   core/: This is the main project configuration directory.
*   settings.py: Contains all project settings (database, installed apps, etc.).
*   urls.py: The main URL routing file. It directs traffic to the inventory app.
*   inventory/: This is the application where all our inventory logic lives.
*   models.py: Defines the database structure. The Product table is defined here.
*   views.py: Contains the application logic. It handles what happens when a user visits a page.
*   urls.py: Defines the URLs specific to the inventory app (e.g., /product/create/).
*   templates/inventory/: Contains the HTML files that the user sees.
*   manage.py: A command-line utility for interacting with your Django project.




