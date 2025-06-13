import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """
    Create and return a database connection
    """
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='mis_upload_system',
            user='root',
            password='',  # Update with your MySQL password
            port=3306
        )
        return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        raise e

def test_connection():
    """
    Test database connection
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        print(f"Successfully connected to database: {result[0]}")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False