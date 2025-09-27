import os
import psycopg2
import bcrypt
from dotenv import load_dotenv

load_dotenv()


def test_login():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('SALARY_DB_NAME'),
            user=os.getenv('SALARY_DB_USER'),
            password=os.getenv('SALARY_DB_PASSWORD'),
            host=os.getenv('SALARY_DB_HOST'),
            port=os.getenv('SALARY_DB_PORT')
        )
        cursor = conn.cursor()
        print(" اتصال به دیتابیس موفق بود")

        cursor.execute("SELECT username, password FROM users WHERE username = 'admin'")
        user = cursor.fetchone()

        if user:
            print(f" کاربر پیدا شد: {user[0]}")
            print(f" هش رمز عبور: {user[1][:20]}...")

            # تست رمز عبور صحیح
            test_password = "admin123"
            if bcrypt.checkpw(test_password.encode('utf-8'), user[1].encode('utf-8')):
                print(" رمز عبور صحیح است")
            else:
                print(" رمز عبور اشتباه است")

            wrong_password = "wrongpass"
            if bcrypt.checkpw(wrong_password.encode('utf-8'), user[1].encode('utf-8')):
                print(" رمز عبور اشتباه است")
            else:
                print(" رمز عبور اشتباه به درستی رد شد")
        else:
            print(" کاربر ادمین پیدا نشد")

    except Exception as e:
        print(f" خطا: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    test_login()