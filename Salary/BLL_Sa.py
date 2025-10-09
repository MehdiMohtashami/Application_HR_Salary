from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import jwt
import os
import psycopg2
from datetime import datetime, timedelta, UTC
import bcrypt
import requests
from dotenv import load_dotenv
from DataLayer_Sa import SalaryDataLayer
from fastapi.middleware.cors import CORSMiddleware
import logging
from functools import lru_cache

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

data_layer = SalaryDataLayer()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
security = HTTPBearer()

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
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(401, "Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.JWTError:
        raise HTTPException(401, "Invalid token")

@app.post("/login", response_model=Token)
async def login(request: LoginRequest):
    with data_layer.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username, password FROM users WHERE username = %s", (request.username,))
            user = cursor.fetchone()
            if user and bcrypt.checkpw(request.password.encode('utf-8'), user[1].encode('utf-8')):
                return {"access_token": create_token({"sub": user[0]}), "token_type": "bearer"}
    raise HTTPException(401, "Invalid credentials")

@app.post("/salaries", response_model=dict)
async def create_salary(salary: SalaryCreate, username: str = Depends(verify_token)):
    try:
        salary_id = data_layer.create_salary_record(salary.employeecode, salary.monthsalary, salary.yearlysalary)
        return {"id": salary_id, "message": "Created"}
    except ValueError as e:
        logger.error(f"Create salary failed: {str(e)}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Unexpected error in create_salary: {str(e)}")
        raise HTTPException(500, "Internal server error")

@app.get("/salaries/{employee_code}")
async def get_salary(employee_code: str, username: str = Depends(verify_token)):
    salary_info = data_layer.get_salary_info(employee_code)
    if salary_info:
        return {
            "employeecode": salary_info[1],
            "monthsalary": float(salary_info[2]),
            "yearlysalary": float(salary_info[3])
        }
    raise HTTPException(404, "Not found")

@app.put("/salaries/{employee_code}", response_model=dict)
async def update_salary(employee_code: str, update_data: SalaryUpdate, username: str = Depends(verify_token)):
    try:
        data_layer.update_salary(employee_code, update_data.monthsalary, update_data.yearlysalary)
        return {"message": "Updated"}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/salary-requests", response_model=dict)
async def create_salary_request(request_data: SalaryRequest, username: str = Depends(verify_token)):
    try:
        request_id = data_layer.create_salary_request(request_data.employeecode, request_data.requestedsalary, request_data.reason)
        return {"id": request_id, "message": "Created"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/salary-requests")
async def get_salary_requests(username: str = Depends(verify_token), page: int = Query(1, ge=1),
                              limit: int = Query(10, ge=1)):
    try:
        requests = data_layer.get_all_requests(page, limit)
        if not requests:
            return []

        employee_codes = [req[1] for req in requests]

        hr_token = data_layer.get_hr_token()
        if not hr_token:
            logger.error("Failed to get HR token for batch request")
            return [{
                "id": req[0], "employeecode": req[1], "employeename": "Unknown",
                "currentsalary": float(req[2]) if req[2] else 0.0,
                "requestedsalary": float(req[3]) if req[3] else 0.0,
                "reason": req[4] or "", "status": req[5] or "Pending",
                "requestdate": req[6].strftime("%Y-%m-%d") if req[6] else None
            } for req in requests]

        import requests as http_requests
        hr_response = http_requests.post(
            "http://localhost:8000/employees/batch",
            json=employee_codes,
            headers={"Authorization": f"Bearer {hr_token}"},
            timeout=10
        )

        hr_employees = {}
        if hr_response.status_code == 200:
            for emp in hr_response.json():
                hr_employees[emp['employeecode']] = emp

        results = []
        for req in requests:
            emp = hr_employees.get(req[1])
            employeename = f"{emp['firstname']} {emp['lastname']}" if emp else "Unknown"
            results.append({
                "id": req[0], "employeecode": req[1], "employeename": employeename,
                "currentsalary": float(req[2]) if req[2] else 0.0,
                "requestedsalary": float(req[3]) if req[3] else 0.0,
                "reason": req[4] or "", "status": req[5] or "Pending",
                "requestdate": req[6].strftime("%Y-%m-%d") if req[6] else None
            })
        return results
    except Exception as e:
        logger.error(f"Error in get_salary_requests: {str(e)}")
        raise HTTPException(500, "Internal server error")

@app.put("/salary-requests/{request_id}", response_model=dict)
async def update_request_status(request_id: int, update_data: RequestUpdate, username: str = Depends(verify_token)):
    try:
        data_layer.update_request_status(request_id, update_data.status)
        return {"message": "Updated"}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/employees-with-salary")
async def get_employees_with_salary(username: str = Depends(verify_token)):
    with data_layer.get_connection() as conn:
        with conn.cursor() as cursor:
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
            records = cursor.fetchall()
    hr_token = data_layer.get_hr_token()
    codes = [rec[1] for rec in records]
    hr_response = requests.post("http://localhost:8000/employees/batch", json=codes, headers={"Authorization": f"Bearer {hr_token}"})
    if hr_response.status_code != 200:
        raise HTTPException(500, "HR batch failed")
    hr_data = {emp['employeecode']: emp for emp in hr_response.json()}
    result = []
    for rec in records:
        code = rec[1]
        emp = hr_data.get(code, {})
        result.append({
            "id": rec[0], "employeecode": code,
            "firstname": emp.get("firstname", "نام"),
            "lastname": emp.get("lastname", "نام خانوادگی"),
            "jobtitle": emp.get("jobtitle", "سمت"),
            "departmentname": emp.get("departmentname", "دپارتمان"),
            "monthsalary": float(rec[2]) if rec[2] else 0,
            "yearlysalary": float(rec[3]) if rec[3] else 0,
            "requeststatus": rec[4],
            "requestedsalary": float(rec[5]) if rec[5] else None
        })
    return result

@app.delete("/salary-requests/cleanup")
async def cleanup_salary_requests(employeecode: str, username: str = Depends(verify_token)):
    try:
        with data_layer.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM salary_requests WHERE employeecode = %s", (employeecode,))
                conn.commit()
        return {"message": "Cleaned up"}
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
        raise HTTPException(500, "Cleanup failed")

@app.delete("/salaries/{employee_code}")
async def delete_salary(employee_code: str, username: str = Depends(verify_token)):
    try:
        with data_layer.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM salary WHERE employeecode = %s", (employee_code,))
                conn.commit()
        return {"message": "Deleted"}
    except Exception as e:
        logger.error(f"Delete salary error: {str(e)}")
        raise HTTPException(500, "Delete failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)