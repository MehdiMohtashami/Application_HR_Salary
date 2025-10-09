from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
from functools import wraps
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
API_BASE_URL = "http://localhost:8001"
HR_API_URL = "http://localhost:8000"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'token' not in session:
            flash('Login required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        response = requests.post(f"{API_BASE_URL}/login", json={
            "username": request.form['username'],
            "password": request.form['password']
        })
        if response.status_code == 200:
            session['token'] = response.json()['access_token']
            return redirect(url_for('dashboard'))
        else:
            logger.error(f"Login failed: {response.text}")
            flash(f'Invalid credentials: {response.status_code}', 'danger')
    return render_template('login_sa.html')


@app.route('/dashboard')
@login_required
def dashboard():
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = requests.get(f"{API_BASE_URL}/employees-with-salary", headers=headers)
        if response.status_code == 200:
            return render_template('main_sa.html', employees=response.json())
        else:
            logger.error(f"Fetch failed: {response.status_code} - {response.text}")
            flash(f'Fetch failed: {response.status_code}', 'danger')
            return render_template('main_sa.html', employees=[])
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        flash(f'Error: {str(e)}', 'danger')
        return render_template('main_sa.html', employees=[])


@app.route('/add_salary', methods=['GET', 'POST'])
@login_required
def add_salary():
    if request.method == 'POST':
        headers = {"Authorization": f"Bearer {session['token']}"}
        data = {
            "employeecode": request.form['employeecode'],
            "monthsalary": float(request.form['monthsalary']),
            "yearlysalary": float(request.form['yearlysalary'])
        }
        response = requests.post(f"{API_BASE_URL}/salaries", json=data, headers=headers)
        if response.status_code == 200:
            flash('Added', 'success')
            return redirect(url_for('dashboard'))
        else:
            try:
                error = response.json().get("detail", "Unknown")
            except ValueError:
                error = response.text or "Unknown error"
            flash(f'Error: {error}', 'danger')
    return render_template('add_salary.html')


@app.route('/request_increase', methods=['GET', 'POST'])
@login_required
def request_increase():
    if request.method == 'POST':
        headers = {"Authorization": f"Bearer {session['token']}"}
        try:
            requested_salary = float(request.form['requestedsalary'])
        except ValueError:
            flash('Invalid salary', 'danger')
            return render_template('request_increase.html')
        data = {
            "employeecode": request.form['employeecode'],
            "requestedsalary": requested_salary,
            "reason": request.form['reason']
        }
        response = requests.post(f"{API_BASE_URL}/salary-requests", json=data, headers=headers)
        if response.status_code == 200:
            flash('Requested', 'success')
            return redirect(url_for('dashboard'))
        else:
            try:
                error = response.json().get("detail", "Unknown")
            except ValueError:
                error = response.text or "Unknown error"
            flash(f'Error: {error}', 'danger')
    return render_template('request_increase.html')


@app.route('/update_request/<int:request_id>', methods=['POST'])
@login_required
def update_request(request_id):
    headers = {"Authorization": f"Bearer {session['token']}"}
    status = request.form['status']
    response = requests.put(f"{API_BASE_URL}/salary-requests/{request_id}", json={"status": status}, headers=headers)
    if response.status_code == 200:
        flash('Updated', 'success')
    else:
        try:
            error = response.json().get("detail", "Unknown")
        except ValueError:
            error = response.text or "Unknown error"
        flash(f'Error updating status: {error}', 'danger')
    return redirect(url_for('salary_requests'))


@app.route('/view_employee/<employee_code>')
@login_required
def view_employee(employee_code):
    headers = {"Authorization": f"Bearer {session['token']}"}
    salary_response = requests.get(f"{API_BASE_URL}/salaries/{employee_code}", headers=headers)
    if salary_response.status_code != 200:
        flash('Salary not found', 'danger')
        return redirect(url_for('dashboard'))
    salary_data = salary_response.json()

    hr_response = requests.get(f"{HR_API_URL}/employees/{employee_code}", headers=headers)
    if hr_response.status_code == 200:
        hr_data = hr_response.json()
    else:
        logger.error(f"HR fetch failed: {hr_response.status_code}")
        hr_data = {"jobtitle": "Unknown", "departmentname": "Unknown", "hiredate": "Unknown"}

    return render_template('view_salary_employee.html', employee_code=employee_code, hr_data=hr_data,
                           salary_data=salary_data)


@app.route('/logout')
def logout():
    session.pop('token', None)
    flash('Logged out', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, port=5001)