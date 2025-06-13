import mysql.connector
from mysql.connector import Error
from config import Config

def get_db_connection():
    """
    Create and return a database connection
    """
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT
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