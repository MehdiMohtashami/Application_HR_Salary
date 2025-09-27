import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import requests
from functools import wraps
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

API_BASE_URL = "http://localhost:8001"


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
        logger.debug(f"Login attempt for username: {username}")

        response = requests.post(
            f"{API_BASE_URL}/login",
            json={"username": username, "password": password}
        )

        logger.debug(f"Login response status: {response.status_code}")

        if response.status_code == 200:
            session['token'] = response.json()['access_token']
            logger.debug("Login successful")
            return redirect(url_for('dashboard'))
        else:
            logger.debug("Login failed")
            flash('Invalid username or password', 'danger')

    return render_template('login_sa.html')


@app.route('/dashboard')
@login_required
def dashboard():
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        logger.debug("Fetching employee data from API")

        response = requests.get(f"{API_BASE_URL}/employees-with-salary", headers=headers)

        logger.debug(f"API response status: {response.status_code}")
        logger.debug(f"API response content: {response.text}")

        if response.status_code == 200:
            employees = response.json()
            logger.debug(f"Received {len(employees)} employee records")
            return render_template('main_sa.html', employees=employees)
        else:
            logger.error(f"Failed to fetch employee data: {response.status_code}")
            flash('Failed to fetch employee data', 'danger')
            return render_template('main_sa.html', employees=[])
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        flash('Salary API is currently unavailable. Please try again later.', 'danger')
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
        salary_data = {
            "employeecode": request.form['employeecode'],
            "monthsalary": float(request.form['monthsalary']),
            "yearlysalary": float(request.form['yearlysalary'])
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/salaries",
                json=salary_data,
                headers=headers
            )

            print(f"[DEBUG] Response status: {response.status_code}")
            print(f"[DEBUG] Response content: {response.text}")

            if response.status_code == 200:
                flash('Salary record added successfully', 'success')
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

    return render_template('add_salary.html')


@app.route('/request_increase', methods=['GET', 'POST'])
@login_required
def request_increase():
    if request.method == 'POST':
        headers = {"Authorization": f"Bearer {session['token']}"}

        employee_code = request.form.get('EmployeeCode', '')
        requested_salary = request.form.get('RequestedSalary', '0')
        reason = request.form.get('Reason', '')

        logger.debug(f"Form data: EmployeeCode={employee_code}, RequestedSalary={requested_salary}")

        # تبدیل به عدد
        try:
            requested_salary = float(requested_salary)
        except ValueError:
            flash('مبلغ حقوق باید یک عدد معتبر باشد', 'danger')
            return render_template('request_increase.html')

        request_data = {
            "employeecode": employee_code,
            "requestedsalary": requested_salary,
            "reason": reason
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/salary-requests",
                json=request_data,
                headers=headers
            )

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response content: {response.text}")

            if response.status_code == 200:
                flash('درخواست افزایش حقوق با موفقیت ثبت شد', 'success')
                return redirect(url_for('dashboard'))
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", "Unknown error")
                except:
                    error_message = response.text if response.text else "Empty response from server"
                flash(f'Error: {error_message}', 'danger')
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            flash(f'Request failed: {str(e)}', 'danger')

    return render_template('request_increase.html')


@app.route('/update_request/<int:request_id>', methods=['POST'])
@login_required
def update_request(request_id):
    status = request.form['status']
    headers = {"Authorization": f"Bearer {session['token']}"}

    response = requests.put(
        f"{API_BASE_URL}/salary-requests/{request_id}",
        json={"Status": status},
        headers=headers
    )

    if response.status_code == 200:
        flash('Request status updated successfully', 'success')
    else:
        flash(f'Error: {response.json().get("detail", "Unknown error")}', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.pop('token', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, port=5001)