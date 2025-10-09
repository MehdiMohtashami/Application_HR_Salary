import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

class SalaryDataLayer:
    def __init__(self):
        self.db_params = {
            'dbname': os.getenv('SALARY_DB_NAME'),
            'user': os.getenv('SALARY_DB_USER'),
            'password': os.getenv('SALARY_DB_PASSWORD'),
            'host': os.getenv('SALARY_DB_HOST'),
            'port': os.getenv('SALARY_DB_PORT')
        }
        self.hr_api_base = "http://localhost:8000"

    def get_connection(self):
        return psycopg2.connect(**self.db_params)

    def log_action(self, employee_code, action, status, message=""):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    INSERT INTO log_salary (employeecode, action, status, message, createdat)
                    VALUES (%s, %s, %s, %s, %s)
                """)
                cursor.execute(query, (employee_code, action, status, message, datetime.now()))
                conn.commit()

    def get_employee_from_hr(self, employee_code, hr_token=None):
        if not hr_token:
            hr_token = self.get_hr_token()

        if not hr_token:
            logger.error("No HR token available")
            return None

        headers = {"Authorization": f"Bearer {hr_token}"}
        try:
            # ASCII clean
            clean_employee_code = employee_code.encode('ascii', 'ignore').decode('ascii')
            logger.debug(f"Looking for employee: '{clean_employee_code}' (original: '{employee_code}')")

            response = requests.get(
                f"{self.hr_api_base}/employees/{clean_employee_code}",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"HR API returned {response.status_code} for employee {clean_employee_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching employee from HR: {str(e)}")
            return None

    def get_salary_info(self, employee_code):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("SELECT * FROM salary WHERE employeecode = %s")
                cursor.execute(query, (employee_code,))
                return cursor.fetchone()

    def create_salary_record(self, employee_code, month_salary, yearly_salary):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    hr_token = self.get_hr_token()  # Local definition
                    if not self.get_employee_from_hr(employee_code, hr_token):
                        raise ValueError("Employee not found in HR")
                    if self.get_salary_info(employee_code):
                        raise ValueError("Salary exists")
                    query = sql.SQL("""
                        INSERT INTO salary (employeecode, monthsalary, yearlysalary)
                        VALUES (%s, %s, %s) RETURNING id
                    """)
                    cursor.execute(query, (employee_code, month_salary, yearly_salary))
                    salary_id = cursor.fetchone()[0]
                    conn.commit()
                    self.log_action(employee_code, "Create", "Success")
                    return salary_id
                except Exception as e:
                    conn.rollback()
                    self.log_action(None, "Create", "Failed", str(e))  # None for FK safe
                    raise

    def get_hr_token(self):
        try:
            response = requests.post("http://localhost:8000/login", json={
                "username": os.getenv("HR_ADMIN_USER", "admin"),
                "password": os.getenv("HR_ADMIN_PASS", "admin123")
            })
            if response.status_code == 200:
                return response.json()["access_token"]
            else:
                logger.error(f"HR login failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"HR token fetch error: {str(e)}")
            return None

    def update_salary(self, employee_code, month_salary=None, yearly_salary=None):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    if not self.get_salary_info(employee_code):
                        raise ValueError("Salary not found")
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
                    query = sql.SQL("UPDATE salary SET {} WHERE employeecode = %s").format(sql.SQL(', ').join(updates))
                    params.append(employee_code)
                    cursor.execute(query, params)
                    conn.commit()
                    self.log_action(employee_code, "Update", "Success")
                    return True
                except Exception as e:
                    conn.rollback()
                    self.log_action(employee_code, "Update", "Failed", str(e))
                    raise

    def create_salary_request(self, employee_code, requested_salary, reason):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    hr_token = self.get_hr_token()
                    if not self.get_employee_from_hr(employee_code, hr_token):
                        raise ValueError("Employee not found in HR")
                    current_salary = self.get_salary_info(employee_code)
                    if not current_salary:
                        raise ValueError("No salary record")
                    query = sql.SQL("""
                        INSERT INTO salary_requests (employeecode, currentsalary, requestedsalary, reason, status)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """)
                    cursor.execute(query, (employee_code, current_salary[2], requested_salary, reason, 'Pending'))
                    request_id = cursor.fetchone()[0]
                    conn.commit()
                    self.log_action(employee_code, "Request", "Success")
                    return request_id
                except Exception as e:
                    conn.rollback()
                    self.log_action(employee_code, "Request", "Failed", str(e))
                    raise

    def get_all_requests(self, page=1, limit=10):
        offset = (page - 1) * limit
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    SELECT id, employeecode, currentsalary, requestedsalary, reason, status, requestdate
                    FROM salary_requests ORDER BY requestdate DESC LIMIT %s OFFSET %s
                """)
                cursor.execute(query, (limit, offset))
                return cursor.fetchall()

    def update_request_status(self, request_id, status):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        "SELECT employeecode, requestedsalary, currentsalary FROM salary_requests WHERE id = %s",
                        (request_id,))
                    request_data = cursor.fetchone()
                    if not request_data:
                        raise ValueError("Request not found")

                    employee_code, requested_salary, current_salary = request_data

                    query = sql.SQL("UPDATE salary_requests SET status = %s WHERE id = %s")
                    cursor.execute(query, (status.capitalize(), request_id))

                    if status.capitalize() == "Approved":
                        update_salary_query = sql.SQL(
                            "UPDATE salary SET monthsalary = %s, yearlysalary = %s WHERE employeecode = %s")
                        cursor.execute(update_salary_query, (requested_salary, requested_salary * 12, employee_code))

                        self.log_action(employee_code, "Salary Update", "Success",
                                        f"Salary updated to {requested_salary} based on approved request {request_id}")

                    conn.commit()
                    self.log_action(employee_code, "Request Update", "Success", f"Request {request_id} {status}")
                    return True

                except Exception as e:
                    conn.rollback()
                    self.log_action(None, "Request Update", "Failed", str(e))
                    raise