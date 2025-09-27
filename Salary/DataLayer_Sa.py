import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()


class SalaryDataLayer:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv('SALARY_DB_NAME'),
            user=os.getenv('SALARY_DB_USER'),
            password=os.getenv('SALARY_DB_PASSWORD'),
            host=os.getenv('SALARY_DB_HOST'),
            port=os.getenv('SALARY_DB_PORT')
        )
        self.cursor = self.conn.cursor()
        self.hr_api_base = "http://localhost:8000"

    def __del__(self):
        self.cursor.close()
        self.conn.close()

    def log_action(self, employee_code, action, status, message=""):
        query = sql.SQL("""
            INSERT INTO Log_Salary (employeecode, Action, Status, Message, CreatedAt)
            VALUES (%s, %s, %s, %s, %s)
        """)
        self.cursor.execute(query, (employee_code, action, status, message, datetime.now()))
        self.conn.commit()

    def get_employee_from_hr(self, employee_code):
        try:
            response = requests.get(f"{self.hr_api_base}/employees/{employee_code}")
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def get_salary_info(self, employee_code):
        query = sql.SQL("SELECT * FROM salary WHERE employeecode = %s")
        self.cursor.execute(query, (employee_code,))
        return self.cursor.fetchone()

    def create_salary_record(self, employee_code, month_salary, yearly_salary):
        try:
            if not self.get_employee_from_hr(employee_code):
                raise ValueError("Employee not found in HR system")

            if self.get_salary_info(employee_code):
                raise ValueError("Salary record already exists")

            query = sql.SQL("""
                INSERT INTO salary (employeecode, monthsalary, yearlysalary)
                VALUES (%s, %s, %s)
                RETURNING id
            """)
            self.cursor.execute(query, (employee_code, month_salary, yearly_salary))
            salary_id = self.cursor.fetchone()[0]
            self.conn.commit()
            self.log_action(employee_code, "Create", "Success")
            return salary_id
        except Exception as e:
            self.conn.rollback()
            self.log_action(employee_code, "Create", "Failed", str(e))

    def update_salary(self, employee_code, month_salary=None, yearly_salary=None):
        try:
            if not self.get_salary_info(employee_code):
                raise ValueError("Salary record not found")

            updates = []
            params = []
            if month_salary is not None:
                updates.append(sql.SQL("monthsalary = %s"))
                params.append(month_salary)
            if yearly_salary is not None:
                updates.append(sql.SQL("yearlysalary = %s"))
                params.append(yearly_salary)

            if not updates:
                return True

            query = sql.SQL("UPDATE salary SET {} WHERE employeecode = %s").format(
                sql.SQL(', ').join(updates)
            )
            params.append(employee_code)

            self.cursor.execute(query, params)
            self.conn.commit()
            self.log_action(employee_code, "Update", "Success")
            return True
        except Exception as e:
            self.conn.rollback()
            self.log_action(employee_code, "Update", "Failed", str(e))
            raise

    def create_salary_request(self, employee_code, requested_salary, reason):
        try:
            employee = self.get_employee_from_hr(employee_code)
            if not employee:
                raise ValueError("Employee not found in HR system")

            current_salary = self.get_salary_info(employee_code)
            if not current_salary:
                raise ValueError("No salary record found")

            query = sql.SQL("""
                INSERT INTO salary_request 
                (employeecode, currentsalary, requestedsalary, reason)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """)
            self.cursor.execute(query, (
                employee_code,
                current_salary[2],
                requested_salary,
                reason
            ))
            request_id = self.cursor.fetchone()[0]
            self.conn.commit()
            self.log_action(employee_code, "Request", "Success")
            return request_id
        except Exception as e:
            self.conn.rollback()
            self.log_action(employee_code, "Request", "Failed", str(e))
            raise

    def get_all_requests(self):
        query = sql.SQL("""
            SELECT id, employeecode, currentsalary, requestedsalary, reason, status, requestdate
                FROM salary_requests;
            """)
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def update_request_status(self, request_id, status):
        try:
            query = sql.SQL("""
                UPDATE Salary_Request 
                SET Status = %s 
                WHERE ID = %s
            """)
            self.cursor.execute(query, (status, request_id))

            if status == "Approved":
                self.cursor.execute("""
                    SELECT employeecode, requestedsalary 
                    FROM Salary_Request 
                    WHERE ID = %s
                """, (request_id,))
                request_data = self.cursor.fetchone()

                self.update_salary(
                    request_data[0],
                    month_salary=request_data[1],
                    yearly_salary=request_data[1] * 12
                )

            self.conn.commit()
            self.log_action(None, "Request Update", "Success", f"Request {request_id} {status}")
            return True
        except Exception as e:
            self.conn.rollback()
            self.log_action(None, "Request Update", "Failed", str(e))
            raise