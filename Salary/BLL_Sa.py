import requests
from fastapi import FastAPI, HTTPException, Depends
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import jwt
import os
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta, UTC
import bcrypt
import requests
from dotenv import load_dotenv
from DataLayer_Sa import SalaryDataLayer
from fastapi.middleware.cors import CORSMiddleware


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
security = HTTPBearer()
data_layer = SalaryDataLayer()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class SalaryBase(BaseModel):
    employeecode: str
    monthsalary: float
    yearlysalary: float


class SalaryCreate(SalaryBase):
    pass


class SalaryUpdate(BaseModel):
    monthsalary: Optional[float] = None
    yearlysalary: Optional[float] = None


class SalaryRequest(BaseModel):
    employeecode: str
    requestedsalary: float
    reason: str


class RequestUpdate(BaseModel):
    status: str


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/login", response_model=Token)
async def login(request: LoginRequest):
    print(f"[DEBUG] Login attempt for username: {request.username}")

    try:
        conn = psycopg2.connect(
            dbname=os.getenv('SALARY_DB_NAME'),
            user=os.getenv('SALARY_DB_USER'),
            password=os.getenv('SALARY_DB_PASSWORD'),
            host=os.getenv('SALARY_DB_HOST'),
            port=os.getenv('SALARY_DB_PORT')
        )
        cursor = conn.cursor()
        print("[DEBUG] Connected to database successfully")

        # بررسی کاربر
        cursor.execute("SELECT username, password FROM users WHERE username = %s", (request.username,))
        user = cursor.fetchone()

        if user:
            print(f"[DEBUG] User found in database: {user[0]}")
            print(f"[DEBUG] Stored password hash: {user[1][:20]}...")

            if bcrypt.checkpw(request.password.encode('utf-8'), user[1].encode('utf-8')):
                print("[DEBUG] Password verification successful")
                access_token = create_token(data={"sub": user[0]})
                return {"access_token": access_token, "token_type": "bearer"}
            else:
                print("[DEBUG] Password verification failed")
        else:
            print(f"[DEBUG] User not found in database: {request.username}")

        raise HTTPException(status_code=401, detail="Invalid credentials")

    except Exception as e:
        print(f"[DEBUG] Error during login: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@app.post("/salaries", response_model=dict)
async def create_salary(
        salary: SalaryCreate,
        username: str = Depends(verify_token)
):
    try:
        salary_id = data_layer.create_salary_record(
            salary.employeecode,
            salary.monthsalary,
            salary.yearlysalary
        )
        return {"id": salary_id, "message": "Salary record created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/salaries/{employee_code}")
async def get_salary(
        employee_code: str,
        username: str = Depends(verify_token)
):
    try:
        logger.debug(f"Getting salary info for {employee_code}")

        # اتصال به دیتابیس
        conn = psycopg2.connect(
            dbname=os.getenv('SALARY_DB_NAME'),
            user=os.getenv('SALARY_DB_USER'),
            password=os.getenv('SALARY_DB_PASSWORD'),
            host=os.getenv('SALARY_DB_HOST'),
            port=os.getenv('SALARY_DB_PORT')
        )
        cursor = conn.cursor()

        # دریافت اطلاعات حقوق
        cursor.execute("SELECT * FROM salary WHERE employeecode = %s", (employee_code,))
        salary_info = cursor.fetchone()

        if salary_info:
            logger.debug(f"Found salary info for {employee_code}")
            return {
                "EmployeeCode": salary_info[1],
                "MonthSalary": float(salary_info[2]),
                "YearlySalary": float(salary_info[3])
            }
        else:
            logger.warning(f"Salary info not found for {employee_code}")
            raise HTTPException(status_code=404, detail="Salary record not found")

    except Exception as e:
        logger.error(f"Error getting salary info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@app.put("/salaries/{employee_code}", response_model=dict)
async def update_salary(
        employee_code: str,
        update_data: SalaryUpdate,
        username: str = Depends(verify_token)
):
    try:
        data_layer.update_salary(
            employee_code,
            update_data.monthsalary,
            update_data.yearlysalary
        )
        return {"message": "Salary updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/salary-requests", response_model=dict)
async def create_salary_request(
        request_data: SalaryRequest,
        username: str = Depends(verify_token)
):
    try:
        request_id = data_layer.create_salary_request(
            request_data.employeecode,
            request_data.requestedsalary,
            request_data.reason
        )
        return {"id": request_id, "message": "Salary request created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/salary-requests")
async def get_salary_requests(username: str = Depends(verify_token)):
    requests = data_layer.get_all_requests()
    results = []

    for req in requests:
        # req[1] = employeecode
        employeecode = req[1]

        try:
            hr_response = requests.get(f"http://localhost:8000/api/employees/{employeecode}")
            if hr_response.status_code == 200:
                hr_data = hr_response.json()
                employeename = f"{hr_data['firstname']} {hr_data['lastname']}"
            else:
                employeename = "Unknown"
        except:
            employeename = "Unknown"

        results.append({
            "ID": req[0],
            "employeecode": employeecode,
            "employeename": employeename,
            "currentsalary": float(req[2]) if req[2] else 0.0,
            "requestedsalary": float(req[3]) if req[3] else 0.0,
            "reason": req[4] if req[4] else "",
            "status": req[5] if req[5] else "Pending",
            "requestdate": req[6].strftime("%Y-%m-%d") if req[6] else None
        })

    return results



@app.put("/salary-requests/{request_id}", response_model=dict)
async def update_request_status(
        request_id: int,
        update_data: RequestUpdate,
        username: str = Depends(verify_token)
):
    try:
        data_layer.update_request_status(request_id, update_data.status)
        return {"message": "Request status updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/employees-with-salary")
async def get_employees_with_salary(username: str = Depends(verify_token)):
    try:
        logger.debug("Starting get_employees_with_salary")

        conn = psycopg2.connect(
            dbname=os.getenv('SALARY_DB_NAME'),
            user=os.getenv('SALARY_DB_USER'),
            password=os.getenv('SALARY_DB_PASSWORD'),
            host=os.getenv('SALARY_DB_HOST'),
            port=os.getenv('SALARY_DB_PORT')
        )
        cursor = conn.cursor()
        logger.debug("Connected to salary database")

        cursor.execute("""
            SELECT s.id, s.employeecode, s.monthsalary, s.yearlysalary, 
                   sr.status as request_status, sr.requestedsalary
            FROM salary s
            LEFT JOIN (
                SELECT employeecode, status, requestedsalary,
                       ROW_NUMBER() OVER (PARTITION BY employeecode ORDER BY requestdate DESC) as rn
                FROM salary_requests
            ) sr ON s.employeecode = sr.employeecode AND sr.rn = 1
        """)
        salary_records = cursor.fetchall()
        logger.debug(f"Found {len(salary_records)} salary records")

        result = []

        for record in salary_records:
            employee_code = record[1]
            month_salary = record[2]
            yearly_salary = record[3]
            request_status = record[4]
            requested_salary = record[5]

            logger.debug(f"Processing employee {employee_code}")

            employee_info = get_employee_from_hr(employee_code)

            if employee_info:
                logger.debug(f"Found employee info for {employee_code}")
                result.append({
                    "id": record[0],
                    "employeecode": employee_code,
                    "firstname": employee_info.get("firstname", ""),
                    "lastname": employee_info.get("lastname", ""),
                    "jobtitle": employee_info.get("jobtitle", ""),
                    "departmentname": employee_info.get("departmentname", ""),
                    "monthsalary": float(month_salary) if month_salary else 0,
                    "yearlysalary": float(yearly_salary) if yearly_salary else 0,
                    "requeststatus": request_status,
                    "requestedsalary": float(requested_salary) if requested_salary else None
                })
            else:
                logger.warning(f"Employee info not found for {employee_code}")
                result.append({
                    "id": record[0],
                    "employeecode": employee_code,
                    "firstname": "نام",
                    "lastname": "نام خانوادگی",
                    "jobtitle": "سمت",
                    "departmentname": "دپارتمان",
                    "monthsalary": float(month_salary) if month_salary else 0,
                    "yearlysalary": float(yearly_salary) if yearly_salary else 0,
                    "requeststatus": request_status,
                    "requestedsalary": float(requested_salary) if requested_salary else None
                })

        logger.debug(f"Returning {len(result)} employee records")
        return result
    except Exception as e:
        logger.error(f"Error in get_employees_with_salary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


def get_employee_from_hr(employee_code: str):
    try:
        logger.debug(f"Fetching employee info from HR for {employee_code}")

        token_response = requests.post(
            "http://localhost:8000/login",
            json={"username": "admin", "password": "admin123"}
        )

        if token_response.status_code != 200:
            logger.error(f"Failed to get token from HR API: {token_response.status_code}")
            return None

        token = token_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        logger.debug("Got token from HR API")

        employee_response = requests.get(
            f"http://localhost:8000/employees/{employee_code}",
            headers=headers
        )

        if employee_response.status_code == 200:
            employee_data = employee_response.json()
            logger.debug(f"Found employee info for {employee_code}: {employee_data}")
            return employee_data
        else:
            logger.error(f"Failed to get employee info: {employee_response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error in get_employee_from_hr: {str(e)}")
        return None




if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)