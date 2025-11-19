# Rich Land Auto Supply Inventory System

A comprehensive inventory and sales management system built for Rich Land Auto Supply, a specialized automotive business. This web application was developed as a course requirement for ITCC 33: Advance Database Systems, migrating a conceptual relational model to a fully functional NoSQL (MongoDB) implementation.

The system is built with a server-side rendered architecture using the Flask web framework and connects to a MongoDB database.

## Features

*   **Inventory Management:** Full CRUD (Create, Read, Update, Delete) functionality for the product catalog.
*   **Stock Control:** Real-time tracking of stock levels with low-stock alerts on the dashboard.
*   **User & Group Management:** A robust Role-Based Access Control (RBAC) system with four distinct user groups:
    *   **Owner:** Full control over the entire system.
    *   **Admin:** Manages users, products, and reports.
    *   **Stock Manager:** Manages products, suppliers, and purchase orders.
    *   **Salesman:** Can view products and record sales transactions.
*   **Supplier & Purchasing:** Functionality to add and manage suppliers and create multi-item purchase orders to replenish stock.
*   **Transaction Logging:** All stock movements (sales, new shipments) are recorded.
*   **Audit Trail:** A complete edit history is maintained for all changes made to products.
*   **Reporting:**
    *   Generate a full inventory snapshot as a downloadable **CSV file**.
    *   Generate a detailed sales report for a selected date range as a downloadable **PDF file**.

## Built With

*   **Backend:**
    *   [Python 3](https://www.python.org/)
    *   [Flask](https://flask.palletsprojects.com/) (Web Framework)
    *   [MongoDB](https://www.mongodb.com/) (NoSQL Database)
    *   [PyMongo](https://pymongo.readthedocs.io/) (Database Driver)
*   **Frontend:**
    *   [Jinja2](https://jinja.palletsprojects.com/) (Templating Engine)
    *   [Bootstrap 5](https://getbootstrap.com/) (CSS Framework)
*   **Key Libraries:**
    *   [Flask-Login](https://flask-login.readthedocs.io/) (User Session Management)
    *   [Flask-WTF](https://flask-wtf.readthedocs.io/) (Forms and CSRF Protection)
    *   [passlib](https://passlib.readthedocs.io/) (Password Hashing)
    *   [xhtml2pdf](https://xhtml2pdf.readthedocs.io/) (PDF Generation)

## Getting Started

To get a local copy up and running, follow these simple steps.

### Prerequisites

Before you begin, ensure you have the following installed on your machine:
*   **Python 3.8+** and `pip`
*   **MongoDB Community Server**. Most importantly, make sure the MongoDB service is **running** in the background.
*   **Git** (for cloning the repository)

### Installation & Setup

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

3.  **Install the required packages:**
    (First, ensure you have a `requirements.txt` file by running `pip freeze > requirements.txt` in your working project).
    ```sh
    pip install -r requirements.txt
    ```
    If you do not have a `requirements.txt` file, you can install the packages manually:
    ```sh
    pip install Flask Flask-WTF Flask-Login pymongo passlib[bcrypt] python-dotenv xhtml2pdf
    ```

4.  **Configure Environment Variables:**
    *   In the root of the project, create a new file named `.env`.
    *   Copy the contents from the example below into your new `.env` file. You can change the `SECRET_KEY` to any random string.

    ```env
    # .env file
    SECRET_KEY='a_super_secret_key_for_flask_sessions'
    MONGO_URI='mongodb://localhost:27017/'
    DB_NAME='richland_autosupply'
    ```

5.  **(First Time Only) Delete the Old Database:**
    If you have run the project before and are setting it up again with new user roles, you must drop the old database to allow the initial user creation script to run. Open `mongosh` and run:
    ```js
    use richland_autosupply;
    db.dropDatabase();
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

Congratulations! You are now running the Rich Land Auto Supply Inventory System.
