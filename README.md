# Perfect Books - Personal Financial Management

## Project Objective

![Business UI Demo](screenshots\v3reactDashboard.gif)

Perfect Books is a full-stack personal finance application designed to provide robust, accurate financial tracking based on the core principles of double-entry accounting. The backend is powered by a custom Python engine and a MySQL database, exposed through a Flask REST API. The frontend is an interactive and responsive single-page application built with React. The primary goal is to create a powerful, self-hosted, **multi-user** tool for managing accounts, tracking income and expenses, and providing a clear, real-time view of one's financial health.

## Table of Contents

* [Core Features](https://www.google.com/search?q=%23core-features)

* [Tech Stack](https://www.google.com/search?q=%23tech-stack)

* [Web Interface](https://www.google.com/search?q=%23web-interface)

* [BI-Ready Database & Analytics](https://www.google.com/search?q=%23bi-ready-database--analytics)

* [Setup Instructions](https://www.google.com/search?q=%23setup-instructions)

* [Database Schema](https://www.google.com/search?q=%23database-schema)

* [Project Structure](https://www.google.com/search?q=%23project-structure)

## Core Features

* **Secure Multi-User Architecture:** Each user's financial data is completely segregated and protected. Register and log in to access your personal books.

* **Double-Entry Accounting:** Every transaction generates corresponding debit and credit entries in an immutable ledger, ensuring a robust and auditable record of all financial activity.

* **Multi-Account Management:** Track balances across all your financial accounts, including checking, savings, credit cards, and cash.

* **Income & Expense Tracking:** Log all sources of income and every expense to get a clear picture of your cash flow.

* **Stateless REST API Backend:** A Flask-based API provides data to the frontend, with a clear separation between the core logic and the user interface. The stateless design ensures scalability and reliability.

* **Persistent State:** The application state is stored in a MySQL database, allowing you to close the application and pick up right where you left off.

## Tech Stack

* **Backend:** Python 3, Flask, Flask-Login

* **Database:** MySQL

* **Password Hashing:** bcrypt

* **Frontend:** React, Tailwind CSS

* **Data Analysis:** Microsoft Power BI (or any BI tool)

## Web Interface

## Analytics-Ready Database & Analytics

A core design philosophy of Perfect Books is data accessibility. The application's normalized MySQL database is structured to be "BI-Ready," allowing for a direct connection with business intelligence tools like Power BI, Tableau, or others. This enables the creation of live, interactive dashboards for deep financial analysis.

* **Executive Summary Dashboard:** Provides a high-level overview of net cash flow and financial trends.

* **Financial Integrity Dashboard:** Includes real-time validation of the accounting equation (Debits must equal Credits) and tracks net worth progression.

## Setup Instructions

### Prerequisites

* Python 3

* A running MySQL server

### 1. Database Setup

1. Ensure your MySQL server is running.

2. Create a `.env` file in the project's root directory and populate it with your MySQL credentials:

   ```
   DB_HOST=your_host
   DB_PORT=your_port
   DB_USER=your_user
   DB_PASSWORD=your_password
   DB_NAME=perfect_books
   
   ```

### 2. Install Dependencies

Install the required Python packages using the `requirements.txt` file:

```
pip install -r requirements.txt

```

### 3. Initialize the Database

Run the setup script **once** from your terminal. This will create the `perfect_books` database and all required tables.

```
python setup.py

```

*Note: This script will completely drop and recreate the database each time it is run.*

### 4. Running the Application

**To use the Web Interface (Recommended):**

1. Start the backend API server in a terminal:

   ```
   python api.py
   
   ```

2. Open the `index.html` file directly in your web browser.

**To use the Terminal Application:**

```
python cli.py

```

*(Note: The CLI is currently single-user and will require modifications to work with the new multi-user architecture.)*

## Database Schema

| Table Name | Description | 
 | ----- | ----- | 
| `users` | Stores user credentials for authentication. | 
| `accounts` | Stores user-defined financial accounts and their real-time balances. Segregated by `user_id`. | 
| `financial_ledger` | An immutable double-entry accounting ledger. All entries are linked to a `user_id`. | 
| `recurring_expenses` | Stores recurring bills for automated processing, linked to a `user_id`. | 
| `loans` | Tracks loan details, including principal and payment schedules, linked to a `user_id`. | 

## Project Structure

```
perfect-books/
├── src/
│   ├── engine.py      # Stateless engine with all business logic
│   ├── api.py         # Flask REST API server (user-aware)
│   ├── cli.py         # Command-line interface
│   └── setup.py       # Database initialization script
├── .env               # Stores database credentials (not committed to Git)
├── .gitignore         # Specifies files for Git to ignore
├── index.html         # React-based web interface
├── login.html         # Login page for web interface
├── register.html      # Registration page for web interface
├── requirements.txt   # List of Python dependencies
└── README.md          # This file

```
