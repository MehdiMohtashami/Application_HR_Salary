from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import jwt
import os
from datetime import datetime, timedelta, UTC
from DataLayer_HR import HRDataLayer

app = FastAPI()
security = HTTPBearer()
data_layer = HRDataLayer()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class EmployeeBase(BaseModel):
    employeecode: str
    firstname: str
    lastname: str
    jobtitle: str
    departmentname: str
    hiredate: str
    username: str
    role: Optional[str] = "User"

class EmployeeCreate(EmployeeBase):
    password: str

class EmployeeUpdate(BaseModel):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    jobtitle: Optional[str] = None
    departmentname: Optional[str] = None
    hiredate: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

class EmployeeResponse(EmployeeBase):
    id: int

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
    user = data_layer.authenticate_user(request.username, request.password)
    if user:
        return {"access_token": create_token({"sub": user[7]}), "token_type": "bearer"}
    raise HTTPException(401, "Invalid credentials")

@app.post("/employees", response_model=dict)
async def create_employee(employee: EmployeeCreate, username: str = Depends(verify_token)):
    try:
        employee_id = data_layer.create_employee(employee.model_dump())
        return {"id": employee_id, "message": "Employee created"}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/employees", response_model=List[EmployeeResponse])
async def get_employees(username: str = Depends(verify_token)):
    employees = data_layer.get_all_employees()
    return [
        EmployeeResponse(
            id=emp[0], employeecode=emp[1], firstname=emp[2], lastname=emp[3],
            jobtitle=emp[4], departmentname=emp[5], hiredate=emp[6].strftime("%Y-%m-%d"),
            username=emp[7], role=emp[8]
        ) for emp in employees
    ]

@app.get("/employees/{employee_code}", response_model=EmployeeResponse)
async def get_employee(employee_code: str, username: str = Depends(verify_token)):
    employee = data_layer.get_employee_by_code(employee_code)
    if not employee:
        raise HTTPException(404, "Employee not found")
    return EmployeeResponse(
        id=employee[0], employeecode=employee[1], firstname=employee[2], lastname=employee[3],
        jobtitle=employee[4], departmentname=employee[5], hiredate=employee[6].strftime("%Y-%m-%d"),
        username=employee[7], role=employee[8]
    )

@app.put("/employees/{employee_code}", response_model=dict)
async def update_employee(employee_code: str, update_data: EmployeeUpdate, username: str = Depends(verify_token)):
    if not update_data.model_dump(exclude_unset=True):
        raise HTTPException(400, "No data provided")
    try:
        data_layer.update_employee(employee_code, update_data.model_dump(exclude_unset=True))
        return {"message": "Updated"}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.delete("/employees/{employee_code}", response_model=dict)
async def delete_employee(employee_code: str, username: str = Depends(verify_token)):
    try:
        data_layer.delete_employee(employee_code)
        return {"message": "Deleted"}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/employees/batch", response_model=List[EmployeeResponse])
async def get_employees_batch(codes: List[str], username: str = Depends(verify_token)):
    results = []
    for code in codes:
        emp = data_layer.get_employee_by_code(code)
        if emp:
            results.append(EmployeeResponse(
                id=emp[0], employeecode=emp[1], firstname=emp[2], lastname=emp[3],
                jobtitle=emp[4], departmentname=emp[5], hiredate=emp[6].strftime("%Y-%m-%d"),
                username=emp[7], role=emp[8]
            ))
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)