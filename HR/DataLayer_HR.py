import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import bcrypt
from datetime import datetime

load_dotenv()


class HRDataLayer:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv('HR_DB_NAME'),
            user=os.getenv('HR_DB_USER'),
            password=os.getenv('HR_DB_password'),
            host=os.getenv('HR_DB_HOST'),
            port=os.getenv('HR_DB_PORT')
        )
        self.cursor = self.conn.cursor()

    def __del__(self):
        self.cursor.close()
        self.conn.close()

    def hash_password(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password, hashed):
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def log_action(self, employee_code, action, status, message=""):
        query = sql.SQL("""
            INSERT INTO Log_HR (employeecode, Action, Status, Message, CreatedAt)
            VALUES (%s, %s, %s, %s, %s)
        """)
        self.cursor.execute(query, (employee_code, action, status, message, datetime.now()))
        self.conn.commit()

    def authenticate_user(self, username, password):
        print(f"[DEBUG] Attempting login for username: {username}")
        query = sql.SQL("SELECT * FROM employee_HR WHERE username = %s")
        self.cursor.execute(query, (username,))
        user = self.cursor.fetchone()

        if user:
            print(f"[DEBUG] User found in database: {user[7]} (id: {user[0]})")
            print(f"[DEBUG] Stored password hash: {user[8][:20]}...")

            if self.verify_password(password, user[8]):
                print("[DEBUG] password verification successful")
                self.log_action(user[1], "Login", "Success")
                return user
            else:
                print("[DEBUG] password verification failed")
                self.log_action(None, "Login", "Failed", f"Invalid password for {username}")
                return None
        else:
            print(f"[DEBUG] User not found in database: {username}")
            self.log_action(None, "Login", "Failed", f"User not found: {username}")
            return None

    def create_employee(self, employee_data):
        try:
            # Check if employeecode exists
            self.cursor.execute(
                sql.SQL("SELECT employeecode FROM employee_HR WHERE employeecode = %s"),
                (employee_data['employeecode'],)
            )
            if self.cursor.fetchone():
                raise ValueError("employeecode already exists")

            # Check if username exists
            self.cursor.execute(
                sql.SQL("SELECT username FROM employee_HR WHERE username = %s"),
                (employee_data['username'],)
            )
            if self.cursor.fetchone():
                raise ValueError("username already exists")

            query = sql.SQL("""
                INSERT INTO employee_HR 
                (employeecode, firstname, lastname, jobtitle, departmentname, hiredate, username, password, role)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING ID
            """)

            hashed_password = self.hash_password(employee_data['password'])
            self.cursor.execute(query, (
                employee_data['employeecode'],
                employee_data['firstname'],
                employee_data['lastname'],
                employee_data['jobtitle'],
                employee_data['departmentname'],
                employee_data['hiredate'],
                employee_data['username'],
                hashed_password,
                employee_data.get('role', 'User')
            ))

            employee_id = self.cursor.fetchone()[0]
            self.conn.commit()
            self.log_action(employee_data['employeecode'], "Create", "Success")
            return employee_id
        except Exception as e:
            self.conn.rollback()
            self.log_action(employee_data.get('employeecode'), "Create", "Failed", str(e))
            raise

    def get_all_employees(self):
        query = sql.SQL("""
            SELECT ID, employeecode, firstname, lastname, jobtitle, departmentname, hiredate, username, role
            FROM employee_HR
        """)
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def get_employee_by_code(self, employee_code):
        query = sql.SQL("""
            SELECT id, employeecode, firstname, lastname, jobtitle, departmentname, hiredate, username, role
            FROM employee_HR WHERE employeecode = %s
        """)
        self.cursor.execute(query, (employee_code,))
        return self.cursor.fetchone()

    def update_employee(self, employee_code, update_data):
        try:
            print(f"[DB DEBUG] Updating employee: {employee_code}")
            print(f"[DB DEBUG] Update data: {update_data}")

            self.cursor.execute(
                sql.SQL("SELECT ID FROM employee_HR WHERE employeecode = %s"),
                (employee_code,)
            )
            if not self.cursor.fetchone():
                raise ValueError("employee not found")

            if 'employeecode' in update_data and update_data['employeecode'] != employee_code:
                raise ValueError("Cannot change employeecode")

            if 'role' in update_data:
                self.cursor.execute(
                    sql.SQL("SELECT role FROM employee_HR WHERE employeecode = %s"),
                    (employee_code,)
                )
                current_role = self.cursor.fetchone()[0]
                if current_role == 'Admin' and update_data['role'] != 'Admin':
                    raise ValueError("Cannot change admin role to non-admin")

            set_clause = []
            params = []
            for key, value in update_data.items():
                column_name = key.lower()

                if key == 'password':
                    set_clause.append(sql.SQL("{} = %s").format(sql.Identifier(column_name)))
                    params.append(self.hash_password(value))
                elif key != 'employeecode':
                    set_clause.append(sql.SQL("{} = %s").format(sql.Identifier(column_name)))
                    params.append(value)

            if not set_clause:
                print("[DB DEBUG] No fields to update")
                return True

            query = sql.SQL("UPDATE employee_HR SET {} WHERE employeecode = %s").format(
                sql.SQL(', ').join(set_clause)
            )
            params.append(employee_code)

            print(f"[DB DEBUG] Executing query: {query.as_string(self.conn)}")
            print(f"[DB DEBUG] With parameters: {params}")

            self.cursor.execute(query, params)
            self.conn.commit()
            self.log_action(employee_code, "Update", "Success")
            print("[DB DEBUG] Update successful")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"[DB DEBUG] Error during update: {str(e)}")
            self.log_action(employee_code, "Update", "Failed", str(e))
            raise

    def delete_employee(self, employee_code):
        try:
            # Check if employee exists and is not admin
            self.cursor.execute(
                sql.SQL("SELECT role FROM employee_HR WHERE employeecode = %s"),
                (employee_code,)
            )
            result = self.cursor.fetchone()
            if not result:
                raise ValueError("employee not found")
            if result[0] == 'Admin':
                raise ValueError("Cannot delete admin user")

            query = sql.SQL("DELETE FROM employee_HR WHERE employeecode = %s")
            self.cursor.execute(query, (employee_code,))
            self.conn.commit()
            self.log_action(employee_code, "Delete", "Success")
            return True
        except Exception as e:
            self.conn.rollback()
            self.log_action(employee_code, "Delete", "Failed", str(e))
            raise