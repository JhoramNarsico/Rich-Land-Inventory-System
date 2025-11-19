# Rich Land Auto Supply Inventory System (Flask & MongoDB Edition)

A comprehensive inventory and sales management system built for Rich Land Auto Supply. This web application was developed as a course requirement for ITCC 33: Advance Database Systems, demonstrating the full migration of a conceptual relational model to a functional, feature-complete NoSQL (MongoDB) implementation.

The system is built with a server-side rendered architecture using the Flask web framework, providing a dynamic and responsive user interface for managing all core business operations.

## Key Features

*   **Group-Based Access Control:** A robust permission system with four distinct user groups:
    *   **Owner:** Full, unrestricted control over the entire system, including product deletion.
    *   **Admin:** Manages users, products, suppliers, and reporting.
    *   **Stock Manager:** Manages the lifecycle of products, including creation, updates, and purchasing.
    *   **Salesman:** Can view products and record sales transactions (stock adjustments).
*   **Comprehensive Inventory Management:** Full CRUD (Create, Read, Update, Delete) functionality for the product catalog, including status changes (Active/Deactivated).
*   **Supplier & Purchasing Workflow:**
    *   Full CRUD for managing suppliers.
    *   Create multi-item purchase orders with a user-friendly, auto-detecting product search field.
    *   Receive stock and automatically update inventory levels by marking purchase orders as "Completed".
*   **Real-time Stock Control:** All stock movements (sales, new shipments) are recorded and reflected instantly using atomic database operations.
*   **Dynamic Dashboard:** The homepage provides an at-a-glance operational overview, including:
    *   Immediate low-stock alerts.
    *   Key metrics like total stock value.
    *   A "Top 5 Selling Items" report based on sales quantity.
*   **Complete Audit Trail:**
    *   **Transaction Log:** A filterable log of all stock-in and stock-out events.
    *   **Product Edit History:** A detailed, immutable log of all changes made to any product, tracking what was changed, who changed it, and when.
*   **Reporting Engine:**
    *   Generate and download a complete inventory snapshot as a **CSV file**.
    *   Generate and download a detailed sales report for a selected date range as a professional **PDF document**.

## Technology Stack

*   **Backend:**
    *   [Python 3](https://www.python.org/)
    *   [Flask](https://flask.palletsprojects.com/) (Web Framework)
    *   [MongoDB](https://www.mongodb.com/) (NoSQL Database)
    *   [PyMongo](https://pymongo.readthedocs.io/) (Database Driver)
*   **Frontend:**
    *   [Jinja2](https://jinja.palletsprojects.com/) (Templating Engine)
    *   [Bootstrap 5](https://getbootstrap.com/) (CSS Framework)
    *   [TomSelect.js](https://tom-select.js.org/) (for searchable dropdowns)
*   **Key Libraries:**
    *   [Flask-Login](https://flask-login.readthedocs.io/) (User Session Management)
    *   [Flask-WTF](https://flask-wtf.readthedocs.io/) (Forms and CSRF Protection)
    *   [passlib](https://passlib.readthedocs.io/) (Password Hashing)
    *   [xhtml2pdf](https://xhtml2pdf.readthedocs.io/) (PDF Generation)
    *   [python-dotenv](https://github.com/theskumar/python-dotenv) (Environment Variable Management)

## Getting Started

To get a local copy up and running, follow these simple steps.

### Prerequisites

Before you begin, ensure you have the following installed and running on your machine:
*   **Python 3.8+** and `pip`
*   **MongoDB Community Server**. Crucially, make sure the MongoDB service is **actively running** in the background.
*   **Git**

### Installation and Setup

1.  **Clone the repository:**
    ```sh
    git clone https://your-repository-url/richland_flask_project.git
    cd richland_flask_project
    ```

2.  **Create and activate a virtual environment:**
    *   On macOS/Linux:
        ```sh
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   On Windows:
        ```sh
        python -m venv venv
        venv\Scripts\activate
        ```
        ```sh
         #IF there is an error activating the virtual environment, input this
         Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
        ```
        
3.  **Install the required packages:**
    (This project includes a `requirements.txt` file).
    ```sh
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    *   In the root of the project, create a new file named `.env`.
    *   Copy the contents below into your new `.env` file. Change the `SECRET_KEY` to any random string for security.

    ```env
    # .env file
    SECRET_KEY='a_very_long_and_random_secret_string_for_flask'
    MONGO_URI='mongodb://localhost:27017/'
    DB_NAME='richland_autosupply'
    ```

5.  **(First Time Only) Clean the Database:**
    To ensure the initial user accounts with the correct groups are created properly, you must drop the old database if it exists. Open `mongosh` in your terminal and run:
    ```js
    use richland_autosupply;
    db.dropDatabase();
    exit;
    ```

6.  **Initialize Database Indexes (Required):**
    Run the setup script to create MongoDB indexes. This is a specific course requirement for optimizing query performance and data integrity.
    ```sh
    python setup_indexes.py
    ```

7.  **Populate with Sample Data (Seeding):**
    **Crucial Step:** To meet the Milestone III requirement of having 30+ records and to ensure the dashboard, analytics, and reports are populated for demonstration, run the seeder script. This generates dummy products, suppliers, and sales history.
    ```sh
    python seed_data.py
    ```

## Running the Application

1.  Make sure your virtual environment is active.
2.  From the root directory of the project, run the main Python script:
    ```sh
    python app.py
    ```
3.  The terminal will confirm that the initial users have been created and the server is running on `http://127.0.0.1:5000`.

4.  Open your web browser and navigate to:
    ```
    http://127.0.0.1:5000
    ```

## Usage

The application will redirect you to the login page. You can use the following default accounts to test the different permission levels:

| Group | Username | Password |
| :--- | :--- | :--- |
| **Owner** | `owner` | `ownerpass` |
| **Admin** | `admin` | `adminpass` |
| **Stock Manager**| `manager` | `managerpass` |
| **Salesman**| `sales` | `salespass` |

You are now ready to explore all the features of the Rich Land Auto Supply Inventory System.
