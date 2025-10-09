````markdown
# 🧩 FastAPI-HR-Salary Management System  

## 📘 Overview  
This project is a **three-layer HR and Salary Management System** built using **FastAPI**, **Flask**, and **PostgreSQL**.  
The architecture is based on **Clean Architecture principles**, ensuring scalability, maintainability, and strong separation of concerns.  

---

## 🏗️ Architecture  

The project follows a **3-layer architecture**:

### 1️⃣ Data Access Layer (DAL)  
- Handles all communication with **PostgreSQL** databases via `psycopg2`.  
- Includes logging tables (`log_hr`, `log_salary`) for audit and debugging.  
- Two separate databases: **HR** and **Salary**, each with its own schema and tables.  
- Secure connection parameters managed through `.env`.  

**Responsibilities:**  
- CRUD operations  
- Database connection handling  
- Logging actions (Insert, Update, Delete)  
- Isolated HR and Salary data management  

---

### 2️⃣ Business Logic Layer (BLL)  
- Implemented using **FastAPI** to handle API endpoints, data validation, and core logic.  
- Integrates authentication and authorization using **JWT tokens**.  
- Uses **Pydantic** models for input validation and serialization.  
- Communicates directly with the DAL for all database operations.  

**Key Features:**  
- JWT-based authentication  
- Token expiration and verification  
- Role-based access control  
- Centralized business logic  
- Integrated error handling and logging  

---

### 3️⃣ User Interface Layer (UI)  
- Built with **Flask**, which connects to the FastAPI backend via RESTful API calls.  
- Renders dynamic pages using Jinja2 templates.  
- Manages user sessions, login state, and frontend communication.  

**Purpose:**  
- Visual representation of HR and Salary data  
- Simple and interactive CRUD interface  
- Smooth communication with FastAPI endpoints  

---

## 🧠 Tech Stack  

| Layer | Technologies |
|-------|---------------|
| **Frontend** | Flask, HTML, CSS, JavaScript |
| **Backend** | FastAPI, Pydantic, bcrypt, JWT |
| **Database** | PostgreSQL (via psycopg2, DBeaver) |
| **Security** | JWT, bcrypt |
| **Environment** | python-dotenv |
| **Logging** | Python logging module + PostgreSQL log tables |

---

## ⚙️ Installation & Setup  

### 🔹 Prerequisites  
- Python 3.10+  
- PostgreSQL installed and configured  
- DBeaver (optional for database visualization)

---

### 🔹 Steps  

1. **Clone the repository:**  
   ```bash
   git clone (https://github.com/MehdiMohtashami/Application_HR_Salary.git)
   cd Application_HR_Salary
````

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/Mac  
   venv\Scripts\activate         # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file in the root directory:

   ```env
   # HR Database
   HR_DB_NAME=HR
   HR_DB_USER=postgres
   HR_DB_PASSWORD=your_password
   HR_DB_HOST=localhost
   HR_DB_PORT=5432

   # Salary Database
   SALARY_DB_NAME=Salary
   SALARY_DB_USER=postgres
   SALARY_DB_PASSWORD=your_password
   SALARY_DB_HOST=localhost
   SALARY_DB_PORT=5432

   # Security
   SECRET_KEY=your_secret_key
   SECURITY_PASSWORD_SALT=your_salt
   ```

5. **Run FastAPI (BLL):**

   ```bash
   uvicorn BLL_HR:app --reload
   uvicorn BLL_Sa:app --reload
   ```

6. **Run Flask (UI):**

   ```bash
   flask run
   ```

---

## 🧾 Example API Endpoints

| Endpoint                | Method | Description                            |
| ----------------------- | ------ | -------------------------------------- |
| `/api/hr/employees`     | `GET`  | Retrieve all employees                 |
| `/api/hr/employee/{id}` | `GET`  | Retrieve specific employee details     |
| `/api/salary/records`   | `GET`  | Retrieve all salary records            |
| `/api/auth/login`       | `POST` | Authenticate user and return JWT token |
| `/api/auth/verify`      | `GET`  | Verify token validity                  |

---

## 🔐 Security Features

* JWT-based authentication and token expiration
* Password hashing with **bcrypt**
* Sensitive credentials stored in `.env`
* Centralized logging for actions and errors
* CORS middleware for secure API access

---

## 🧩 Project Structure

```
FastAPI-HR-Salary/
│
├── App_HR.py
├── App_Sa.py
├── BLL_HR.py
├── BLL_Sa.py
├── DataLayer_HR.py
├── DataLayer_Sa.py
│
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── dashboard.html
│
├── static/
│   ├── css/
│   ├── js/
│
├── .env
├── requirements.txt
└── README.md
```

---

## 🚀 Future Improvements

* 🔒 Role-based access control (RBAC)
* 🧮 Redis caching layer for performance optimization
* 🧪 Unit and integration testing with `pytest`
* ⚡ Asynchronous DB operations with `asyncpg`
* 🧭 SPA frontend (React / Vue.js) integration

---

## 👨‍💻 Author

**Mehdi Mohtashami Pour**
Software Developer | Backend Engineer

📍 *Specialized in API-driven architectures, authentication systems, and data modeling with PostgreSQL.*

🔗 [LinkedIn](www.linkedin.com/in/mahdi-mohtashami-pour-30b110235)

---

```
