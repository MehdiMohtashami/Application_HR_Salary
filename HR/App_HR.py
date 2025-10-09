from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
API_BASE_URL = "http://localhost:8000"
SALARY_API_URL = "http://localhost:8001"

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
        flash(f'Invalid credentials: {response.status_code}', 'danger')
    return render_template('login_hr.html')

@app.route('/dashboard')
@login_required
def dashboard():
    headers = {"Authorization": f"Bearer {session['token']}"}
    response = requests.get(f"{API_BASE_URL}/employees", headers=headers)
    if response.status_code == 200:
        return render_template('main_hr.html', employees=response.json())
    flash(f'Fetch failed: {response.status_code}', 'danger')
    return redirect(url_for('login'))

@app.route('/salary_requests')
@login_required
def salary_requests():
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = requests.get(f"{SALARY_API_URL}/salary-requests", headers=headers)
        if response.status_code == 200:
            return render_template('salary_requests.html', requests=response.json())
        else:
            flash(f'Fetch failed: {response.status_code} - {response.text}', 'danger')
    except Exception as e:
        flash(f'Salary API unavailable: {str(e)}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        headers = {"Authorization": f"Bearer {session['token']}"}
        data = request.form.to_dict()
        response = requests.post(f"{API_BASE_URL}/employees", json=data, headers=headers)
        if response.status_code == 200:
            flash('Added', 'success')
            return redirect(url_for('dashboard'))
        else:
            try:
                error = response.json().get("detail", "Unknown")
            except ValueError:
                error = response.text or "Unknown error"
            flash(f'Error: {error}', 'danger')
    return render_template('add_employee.html')

@app.route('/edit_employee/<employee_code>', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_code):
    headers = {"Authorization": f"Bearer {session['token']}"}
    if request.method == 'POST':
        update_data = {k: v for k, v in request.form.items() if v.strip()}
        response = requests.put(f"{API_BASE_URL}/employees/{employee_code}", json=update_data, headers=headers)
        if response.status_code == 200:
            flash('Updated', 'success')
            return redirect(url_for('dashboard'))
        flash(f'Error: {response.json().get("detail", "Unknown")}', 'danger')
    response = requests.get(f"{API_BASE_URL}/employees/{employee_code}", headers=headers)
    if response.status_code == 200:
        return render_template('edit_employee.html', employee=response.json())
    flash('Not found', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/delete_employee/<employee_code>', methods=['POST'])
@login_required
def delete_employee(employee_code):
    headers = {"Authorization": f"Bearer {session['token']}"}
    response = requests.delete(f"{API_BASE_URL}/employees/{employee_code}", headers=headers)
    if response.status_code == 200:
        flash('Deleted', 'success')
    else:
        flash(f'Error: {response.json().get("detail", "Unknown")}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/employees/<employee_code>')
@login_required
def view_employee(employee_code):
    headers = {"Authorization": f"Bearer {session['token']}"}
    response = requests.get(f"{API_BASE_URL}/employees/{employee_code}", headers=headers)
    if response.status_code != 200:
        flash('Not found', 'danger')
        return redirect(url_for('dashboard'))
    employee = response.json()
    salary_data = None
    try:
        salary_response = requests.get(f"{SALARY_API_URL}/salaries/{employee_code}", headers=headers)
        if salary_response.status_code == 200:
            salary_data = salary_response.json()
        else:
            flash(f'Salary fetch failed: {salary_response.status_code} - {salary_response.text}', 'danger')
    except Exception as e:
        flash(f'Salary error: {str(e)}', 'danger')
    return render_template('view_employee.html', employee=employee, salary_data=salary_data)

@app.route('/update_request/<int:request_id>', methods=['POST'])
@login_required
def update_request(request_id):
    headers = {"Authorization": f"Bearer {session['token']}"}
    status = request.form['status']
    response = requests.put(f"{SALARY_API_URL}/salary-requests/{request_id}", json={"status": status}, headers=headers)
    if response.status_code == 200:
        flash('Status updated', 'success')
    else:
        flash(f'Error updating status: {response.json().get("detail", "Unknown")}', 'danger')
    return redirect(url_for('salary_requests'))

@app.route('/logout')
def logout():
    session.pop('token', None)
    flash('Logged out', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)