from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import requests
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

API_BASE_URL = "http://localhost:8000"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'token' not in session:
            flash('You need to login first', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"[APP DEBUG] Login attempt - Username: {username}")

        response = requests.post(
            f"{API_BASE_URL}/login",
            json={"username": username, "password": password}
        )

        print(f"[APP DEBUG] API Response Status: {response.status_code}")
        print(f"[APP DEBUG] API Response Content: {response.text}")

        if response.status_code == 200:
            session['token'] = response.json()['access_token']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login_hr.html')


@app.route('/dashboard')
@login_required
def dashboard():
    headers = {"Authorization": f"Bearer {session['token']}"}
    response = requests.get(f"{API_BASE_URL}/employees", headers=headers)

    if response.status_code == 200:
        employees = response.json()
        return render_template('main_hr.html', employees=employees)
    else:
        flash('Failed to fetch employees', 'danger')
        return redirect(url_for('login'))


@app.route('/salary_requests')
@login_required
def salary_requests():
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = requests.get(f"http://localhost:8001/salary-requests", headers=headers)

        if response.status_code == 200:
            requests_data = response.json()
            return render_template('salary_requests.html', requests=requests_data)
        else:
            flash('Failed to fetch salary requests', 'danger')
            return redirect(url_for('dashboard'))
    except requests.exceptions.ConnectionError:
        flash('Salary API is currently unavailable. Please try again later.', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        headers = {"Authorization": f"Bearer {session['token']}"}
        employee_data = {
            "employeecode": request.form['employeecode'],
            "firstname": request.form['firstname'],
            "lastname": request.form['lastname'],
            "jobtitle": request.form['jobtitle'],
            "departmentname": request.form['departmentname'],
            "hiredate": request.form['hiredate'],
            "username": request.form['username'],
            "password": request.form['password'],
            "role": request.form.get('role', 'User')
        }

        response = requests.post(
            f"{API_BASE_URL}/employees",
            json=employee_data,
            headers=headers
        )

        if response.status_code == 200:
            flash('Employee added successfully', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash(f'Error: {response.json().get("detail", "Unknown error")}', 'danger')

    return render_template('add_employee.html')


@app.route('/edit_employee/<employee_code>', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_code):
    headers = {"Authorization": f"Bearer {session['token']}"}

    if request.method == 'POST':
        update_data = {}
        for field in ['firstname', 'lastname', 'jobtitle', 'departmentname', 'hiredate', 'username', 'password',
                      'role']:
            if field in request.form and request.form[field].strip():
                update_data[field] = request.form[field]

        print(f"[DEBUG] Update data: {update_data}")

        try:
            response = requests.put(
                f"{API_BASE_URL}/employees/{employee_code}",
                json=update_data,
                headers=headers
            )

            print(f"[DEBUG] Response status: {response.status_code}")
            print(f"[DEBUG] Response content: {response.text}")

            if response.status_code == 200:
                flash('Employee updated successfully', 'success')
                return redirect(url_for('dashboard'))
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", "Unknown error")
                except:
                    error_message = response.text if response.text else "Empty response from server"
                flash(f'Error: {error_message}', 'danger')
        except requests.exceptions.RequestException as e:
            flash(f'Request failed: {str(e)}', 'danger')

    response = requests.get(f"{API_BASE_URL}/employees/{employee_code}", headers=headers)
    if response.status_code == 200:
        employee = response.json()
        return render_template('edit_employee.html', employee=employee)
    else:
        flash('Employee not found', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/delete_employee/<employee_code>', methods=['POST'])
@login_required
def delete_employee(employee_code):
    headers = {"Authorization": f"Bearer {session['token']}"}
    response = requests.delete(f"{API_BASE_URL}/employees/{employee_code}", headers=headers)

    if response.status_code == 200:
        flash('Employee deleted successfully', 'success')
    else:
        try:
            error_data = response.json()
            error_message = error_data.get("detail", "Unknown error")
        except ValueError:  # JSONDecodeError
            error_message = response.text if response.text else "Empty response from server"
        flash(f'Error: {error_message}', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/employees/<employee_code>')
@login_required
def view_employee(employee_code):
    headers = {"Authorization": f"Bearer {session['token']}"}

    try:
        response = requests.get(f"{API_BASE_URL}/employees/{employee_code}", headers=headers)

        if response.status_code != 200:
            flash('Employee not found', 'danger')
            return redirect(url_for('dashboard'))

        employee = response.json()

        try:
            token_response = requests.post(
                "http://localhost:8001/login",
                json={"username": "admin", "password": "admin123"}
            )

            if token_response.status_code == 200:
                salary_token = token_response.json().get("access_token")
                salary_headers = {"Authorization": f"Bearer {salary_token}"}

                salary_response = requests.get(
                    f"http://localhost:8001/salaries/{employee_code}",
                    headers=salary_headers
                )

                if salary_response.status_code == 200:
                    salary_data = salary_response.json()
                else:
                    salary_data = None
            else:
                salary_data = None
        except:
            salary_data = None

        return render_template('view_employee.html', employee=employee, salary_data=salary_data)

    except requests.exceptions.RequestException as e:
        flash(f'Request failed: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('token', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)