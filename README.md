# Rich Land Auto Supply - Inventory System

Welcome to the Rich Land Auto Supply Inventory System. This is a comprehensive web application designed to manage products, track stock levels, and generate inventory reports. The system features a full-featured REST API for programmatic access.

![image](https://i.imgur.com/u4n6B5C.png)

## Tech Stack Overview

This project is built with a classic and robust Django monolithic architecture, where the backend is responsible for both business logic and rendering the user interface.

### **Backend**
*   **Language:** Python
*   **Framework:** Django
*   **Database:** MySQL
*   **API:** Django REST Framework (DRF)
*   **Key Libraries:**
    *   `django-simple-history`: For comprehensive audit trails on model changes.
    *   `drf-spectacular`: For auto-generating interactive OpenAPI/Swagger API documentation.
    *   `xhtml2pdf`: For generating PDF reports from HTML templates.
    *   `python-decouple`: For securely managing project settings and secrets.

### **Frontend**
*   **Structure:** Server-side rendered HTML via **Django Templates**.
*   **Styling:** **Bootstrap 5** CSS framework for a responsive and modern UI.
*   **Interactivity:** **Vanilla JavaScript** and **Bootstrap's JavaScript** components.

---

## Getting Started

Follow these instructions to set up and run the project on your local development machine.

### Prerequisites

Before you begin, ensure you have the following software installed:

*   [Python](https://www.python.org/downloads/) (3.10 or newer recommended)
*   [Git](https://git-scm.com/downloads/)
*   [pip](https://pip.pypa.io/en/stable/installation/) (usually comes with Python)
*   [MySQL Server](https://dev.mysql.com/downloads/mysql/)

### 1. Clone the Repository

Open your terminal or command prompt, clone the project, and navigate into the project directory.

```bash
# Replace <your-repository-url> with the actual URL from GitHub
git clone <your-repository-url>
cd richland_inventory
```

### 2. Create and Activate a Virtual Environment

It is a strong best practice to use a virtual environment to isolate project dependencies.

```bash
# Create the virtual environment
python -m venv venv

# Activate the virtual environment (Windows - PowerShell)
.\venv\Scripts\activate
```
> **PowerShell Note:** If you encounter an error activating the environment, you may need to adjust your execution policy for the current session by running:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`

### 3. Install Required Packages

Install all the necessary Python libraries using the provided command.

```bash
python -m pip install --upgrade pip Django PyMySQL djangorestframework python-decouple cryptography xhtml2pdf django-simple-history drf-spectacular
```

### 4. Set Up the MySQL Database

Log in to your MySQL server and run the following SQL commands to create the database and a dedicated user.

```sql
-- Create a new database with proper character set support
CREATE DATABASE richland_inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create a new user and grant it privileges on the new database.
-- Replace 'your_password' with a secure password of your choice.
CREATE USER 'your_db_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON richland_inventory_db.* TO 'your_db_user'@'localhost';
FLUSH PRIVILEGES;
```

### 5. Configure Environment Variables

In the project root directory (the same folder as `manage.py`), create a file named `.env`. This file will hold your secret keys and database credentials.

Copy the following content into your new `.env` file and **update the values** to match your setup.

```ini
# .env

# SECURITY WARNING: This is a default key. In production, generate a new one.
SECRET_KEY='django-insecure-eoqpafol0v1q51=nbciaya+4$2r6)(b3do$jdncm)pz81q7zl#'

# Set to False in a production environment!
DEBUG=True

# In production, set this to your domain names (e.g., 'www.yourdomain.com,yourdomain.com')
ALLOWED_HOSTS='127.0.0.1,localhost'

# -- Database Configuration --
DB_NAME='richland_inventory_db'
DB_USER='your_db_user'         # The user you created in Step 4
DB_PASSWORD='your_password'    # The password you chose in Step 4
DB_HOST='localhost'
DB_PORT='3306'
```

### 6. Apply Database Migrations

This command creates all the necessary tables in your database based on the project's models.

```bash
python manage.py migrate
```

### 7. Create an Administrator Account

Create a superuser account to access the Django Admin panel.

```bash
python manage.py createsuperuser
```
Follow the prompts to set up your username, email, and password.

---

## Running the Application

### Start the Development Server

With your virtual environment activated, run the following command:

```bash
python manage.py runserver
```

You can now access the running application at the addresses listed below.

### Available URLs

*   **Main Application:** [http://127.0.0.1:8000/inventory/](http://127.0.0.1:8000/inventory/)
*   **Admin Panel:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
*   **API Documentation (Swagger UI):** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
*   **API Documentation (ReDoc):** [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)

---

## Using the API

The API is secured with token-based authentication. To use the interactive Swagger UI for testing, follow these steps.

**1. Generate a Token**

Run the following command in a **new terminal**, replacing `<your_username>` with the superuser you created in Step 7.

```bash
python manage.py drf_create_token <your_username>
```
Copy the generated token string.

**2. Authorize in Swagger UI**

1.  Navigate to the [Swagger UI documentation](http://127.0.0.1:8000/api/docs/).
2.  Click the green **"Authorize"** button at the top right.
3.  In the popup, paste your token in the `Value` box using the format: `Token <your_copied_token>`.
    > **Example:** `Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b`
4.  Click "Authorize", then "Close".
5.  You can now use the "Try it out" feature on any endpoint.

## Project File Structure

```
richland_inventory/
├── .env
├── manage.py
├── core/
│   ├── settings.py
│   └── urls.py
├── inventory/
│   ├── admin.py
│   ├── api_urls.py
│   ├── forms.py
│   ├── models.py
│   ├── views.py
│   └── urls.py
├── static/
│   ├── css/
│   ├── js/
│   └── images/
└── templates/
    ├── base.html
    ├── home.html
    └── ...
```
