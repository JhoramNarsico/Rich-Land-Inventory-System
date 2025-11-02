# Rich Land Auto Supply - Inventory System

This document provides instructions on how to set up and run the Rich Land Auto Supply Inventory System project on a local development machine. This project is a web application built using the Django framework in Python. It has also REST API which we use the Django REST Framework (DRF), a powerful and flexible toolkit for building Web APIs.

# Backend
* Python: Core programming language.
* Django: Main web framework.
* Django REST Framework: For building APIs.
* xhtml2pdf: For PDF report generation.

# Database
* MySQL: Relational database system.
* PyMySQL: Database connector for Python.

# Frontend
* HTML: Page structure and content.
* Bootstrap: CSS framework for UI and styling.
* JavaScript: For user interactivity.
* Font Awesome: Icon set.

# Development & Tooling
* pip & venv: Package and environment management.
* python-decouple: For managing secret settings.
* cryptography: Core encryption library.

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
python -m pip install Django PyMySQL djangorestframework python-decouple cryptography xhtml2pdf
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


```bash
richland_inventory/
│
├── .env
│   └── Description: Stores environment variables and secrets, like your database password
│       and Django's SECRET_KEY. This file should NOT be committed to version control.
│
├── manage.py
│   └── Description: The command-line utility for interacting with your Django project.
│       You use it to run the development server, create migrations, and more.
│
├── inventory/ (Your core Django App)
│   ├── __init__.py      -> Marks this directory as a Python package.
│   ├── admin.py         -> Registers your models with the Django admin site, allowing you to manage data.
│   ├── api_urls.py      -> Defines the URL routes for your app's API endpoints.
│   ├── apps.py          -> Configuration for the 'inventory' app itself.
│   ├── forms.py         -> Contains the form classes (e.g., ProductForm, filters) used in your front-end.
│   ├── models.py        -> The single source of truth for your database schema. Defines tables and fields.
│   ├── serializers.py   -> Defines how your model data is converted to formats like JSON for your API.
│   ├── tests.py         -> For writing automated tests to ensure your app works correctly.
│   ├── urls.py          -> Defines the URL routes for your app's user-facing pages (e.g., /products/, /reports/).
│   ├── utils.py         -> A place for custom helper functions, like the 'render_to_pdf' utility.
│   ├── views.py         -> Contains the core logic. Handles requests, processes data, and renders templates.
│   └── templates/
│       └── inventory/   -> App-specific HTML templates are kept here, namespaced to avoid conflicts.
│
├── static/ (Source Static Files)
│   ├── css/             -> Your custom CSS files for styling the application.
│   ├── images/          -> Your image assets, such as the company logo.
│   └── js/              -> Your custom JavaScript files for front-end interactivity.
│
├── staticfiles/ (Collected Static Files for Deployment)
│   └── Description: This folder is the target for the `collectstatic` command. It gathers all static
│       files from your entire project into a single place for your web server (like Nginx) to
│       serve efficiently in a live environment. YOU SHOULD NOT edit files here directly.
│
└── templates/ (Project-Level Templates)
    ├── admin/           -> A place to put custom templates that override the default Django admin pages.
    ├── registration/    -> Holds templates for user authentication (login.html, etc.).
    ├── base.html        -> The main site layout. All other templates extend this file to maintain a consistent look.
    └── home.html        -> The template for your project's homepage.
```







