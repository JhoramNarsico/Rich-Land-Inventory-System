# Rich Land Auto Supply - Inventory System

This document provides instructions on how to set up and run the Rich Land Auto Supply Inventory System project on a local development machine. This project is a web application built using the Django framework in Python.

## Prerequisites

Before you start, make sure you have the following software installed on your computer:

*   **Python (version 3.8 or newer):** [Download Python](https://www.python.org/downloads/)
*   **Git:** [Download Git](https://git-scm.com/downloads/)

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
Set-ExecutionPolicy RemoteSigned
```
3. Install Required Packages
   
```bash
pip install Django

```
4. Set Up the Database
 ```bash
python manage.py migrate

```
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
Main Application: http://127.0.0.1:8000/
Admin Panel: http://127.0.0.1:8000/admin/


# How to Edit and Customize the Program
# Understanding the project structure is key to making changes.
Project Structure Overview

core/: This is the main project configuration directory.
settings.py: Contains all project settings (database, installed apps, etc.).
urls.py: The main URL routing file. It directs traffic to the inventory app.
inventory/: This is the application where all our inventory logic lives.
models.py: Defines the database structure. The Product table is defined here.
views.py: Contains the application logic. It handles what happens when a user visits a page.
urls.py: Defines the URLs specific to the inventory app (e.g., /product/create/).
templates/inventory/: Contains the HTML files that the user sees.
manage.py: A command-line utility for interacting with your Django project.
