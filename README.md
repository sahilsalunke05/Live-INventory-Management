# Live-INventory-Management
# 🛒 Supermarket Management System

The **Supermarket Management System** is a web-based application designed to manage supermarket operations efficiently.
It helps in handling product inventory, sales records, customer management, and billing processes.

This system simplifies daily supermarket operations by providing a centralized platform for managing products, transactions, and users.

---

# 🚀 Features

* 📦 **Product Management**

  * Add, update, delete, and view products.

* 🛍️ **Inventory Management**

  * Track stock availability and product quantity.

* 💳 **Billing System**

  * Generate bills for customer purchases.

* 👥 **User Authentication**

  * Login and secure access for system users.

* 📊 **Sales Tracking**

  * Record and manage daily sales transactions.

* 📈 **Reports and Data Management**

  * Monitor sales performance and inventory status.

---

# 🏗️ Project Structure

```id="tree2"
supermarket-management-system
│
├── app.py
├── database.py
├── models.py
│
├── templates
│   ├── index.html
│   ├── login.html
│   ├── dashboard.html
│   ├── products.html
│   └── billing.html
│
├── static
│   ├── css
│   ├── js
│   └── images
│
├── instance
│   └── database.db
│
└── README.md
```

---

# ⚙️ Technologies Used

* **Python**
* **Flask Framework**
* **SQLite Database**
* **HTML**
* **CSS**
* **JavaScript**

---

# 🚀 Installation

## 1️⃣ Clone the Repository

```id="clone2"
git clone https://github.com/yourusername/supermarket-management-system.git
cd supermarket-management-system
```

---

## 2️⃣ Create Virtual Environment

```id="venv4"
python -m venv venv
```

Activate environment

**Windows**

```id="venv5"
venv\Scripts\activate
```

**Linux / Mac**

```id="venv6"
source venv/bin/activate
```

---

## 3️⃣ Install Dependencies

```id="install3"
pip install flask
```

---

## 4️⃣ Run the Application

```id="run2"
python app.py
```

Open your browser and visit:

```id="url1"
http://127.0.0.1:5000
```

---

# 📊 System Modules

### 🔹 User Module

Handles login and authentication of users.

### 🔹 Product Module

Manages product information such as name, price, and quantity.

### 🔹 Billing Module

Processes customer purchases and generates bills.

### 🔹 Inventory Module

Tracks stock levels and updates inventory automatically after sales.

---

# 🔮 Future Improvements

* Barcode scanning system
* Sales analytics dashboard
* Online payment integration
* Multi-user role management (Admin / Staff)
* Cloud database integration

---

# 👨‍💻 Author

**Sahil Salunke**
Student – Information Technology & Artificial Intelligence

---

# ⭐ Contributing

Contributions are welcome.
Fork the repository and submit pull requests to improve the project.

---

# 📌 Purpose

This project is developed for educational purposes to demonstrate the implementation of a web-based management system using Python and Flask.
