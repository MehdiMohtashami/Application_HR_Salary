import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import bcrypt
from datetime import datetime

load_dotenv()

class HRDataLayer:
    def __init__(self):
        self.db_params = {
            'dbname': os.getenv('HR_DB_NAME'),
            'user': os.getenv('HR_DB_USER'),
            'password': os.getenv('HR_DB_PASSWORD'),
            'host': os.getenv('HR_DB_HOST'),
            'port': os.getenv('HR_DB_PORT')
        }

    def get_connection(self):
        return psycopg2.connect(**self.db_params)

    def hash_password(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password, hashed):
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def log_action(self, employee_code, action, status, message=""):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    INSERT INTO log_hr (employeecode, action, status, message, createdat)
                    VALUES (%s, %s, %s, %s, %s)
                """)
                cursor.execute(query, (employee_code, action, status, message, datetime.now()))
                conn.commit()

    def authenticate_user(self, username, password):
        print(f"[DEBUG] Attempting login for username: {username}")
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("SELECT * FROM employee_hr WHERE username = %s")
                cursor.execute(query, (username,))
                user = cursor.fetchone()
                if user:
                    print(f"[DEBUG] User found: {user[7]} (id: {user[0]})")
                    if self.verify_password(password, user[8]):
                        print("[DEBUG] Password verified")
                        self.log_action(user[1], "Login", "Success")
                        return user
                    else:
                        print("[DEBUG] Password failed")
                        self.log_action(None, "Login", "Failed", f"Invalid password for {username}")
                else:
                    print(f"[DEBUG] User not found: {username}")
                    self.log_action(None, "Login", "Failed", f"User not found: {username}")
                return None

    def create_employee(self, employee_data):
        hiredate = datetime.strptime(employee_data['hiredate'], "%Y-%m-%d")
        if hiredate > datetime.now():
            raise ValueError("Hiredate cannot be in the future")
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("SELECT employeecode FROM employee_hr WHERE employeecode = %s", (employee_data['employeecode'],))
                    if cursor.fetchone():
                        raise ValueError("employeecode already exists")
                    cursor.execute("SELECT username FROM employee_hr WHERE username = %s", (employee_data['username'],))
                    if cursor.fetchone():
                        raise ValueError("username already exists")
                    query = sql.SQL("""
                        INSERT INTO employee_hr (employeecode, firstname, lastname, jobtitle, departmentname, hiredate, username, password, role)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING ID
                    """)
                    hashed = self.hash_password(employee_data['password'])
                    cursor.execute(query, (
                        employee_data['employeecode'], employee_data['firstname'], employee_data['lastname'],
                        employee_data['jobtitle'], employee_data['departmentname'], employee_data['hiredate'],
                        employee_data['username'], hashed, employee_data.get('role', 'User')
                    ))
                    employee_id = cursor.fetchone()[0]
                    conn.commit()
                    self.log_action(employee_data['employeecode'], "Create", "Success")
                    return employee_id
                except Exception as e:
                    conn.rollback()
                    self.log_action(employee_data.get('employeecode'), "Create", "Failed", str(e))
                    raise

    def get_all_employees(self):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    SELECT ID, employeecode, firstname, lastname, jobtitle, departmentname, hiredate, username, role
                    FROM employee_hr
                """)
                cursor.execute(query)
                return cursor.fetchall()

    def get_employee_by_code(self, employee_code):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    SELECT id, employeecode, firstname, lastname, jobtitle, departmentname, hiredate, username, role
                    FROM employee_hr WHERE employeecode = %s
                """)
                cursor.execute(query, (employee_code,))
                return cursor.fetchone()

    def update_employee(self, employee_code, update_data):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("SELECT ID FROM employee_hr WHERE employeecode = %s", (employee_code,))
                    if not cursor.fetchone():
                        raise ValueError("employee not found")
                    if 'employeecode' in update_data and update_data['employeecode'] != employee_code:
                        raise ValueError("Cannot change employeecode")
                    if 'role' in update_data:
                        cursor.execute("SELECT role FROM employee_hr WHERE employeecode = %s", (employee_code,))
                        current_role = cursor.fetchone()[0]
                        if current_role == 'Admin' and update_data['role'] != 'Admin':
                            raise ValueError("Cannot change admin role")
                    if 'hiredate' in update_data:
                        hiredate = datetime.strptime(update_data['hiredate'], "%Y-%m-%d")
                        if hiredate > datetime.now():
                            raise ValueError("Hiredate cannot be in the future")
                    set_clause = []
                    params = []
                    for key, value in update_data.items():
                        if key == 'password':
                            params.append(self.hash_password(value))
                        elif key != 'employeecode':
                            params.append(value)
                        column = key.lower()
                        set_clause.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
                    if not set_clause:
                        return True
                    query = sql.SQL("UPDATE employee_hr SET {} WHERE employeecode = %s").format(sql.SQL(', ').join(set_clause))
                    params.append(employee_code)
                    cursor.execute(query, params)
                    conn.commit()
                    self.log_action(employee_code, "Update", "Success")
                    return True
                except Exception as e:
                    conn.rollback()
                    self.log_action(employee_code, "Update", "Failed", str(e))
                    raise

    def delete_employee(self, employee_code):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("SELECT role FROM employee_hr WHERE employeecode = %s", (employee_code,))
                    result = cursor.fetchone()
                    if not result:
                        raise ValueError("employee not found")
                    if result[0] == 'Admin':
                        raise ValueError("Cannot delete admin")
                    query = sql.SQL("DELETE FROM employee_hr WHERE employeecode = %s")
                    cursor.execute(query, (employee_code,))
                    conn.commit()
                    self.log_action(employee_code, "Delete", "Success")
                    return True
                except Exception as e:
                    conn.rollback()
                    self.log_action(employee_code, "Delete", "Failed", str(e))
                    raise