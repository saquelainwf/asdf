from database.connection import get_db_connection

def get_mis_data(limit=50):
    """Get latest MIS data records"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT m.*, b.bank_name, c.category_name 
        FROM mis_data m
        JOIN banks b ON m.bank_id = b.id
        JOIN categories c ON m.category_id = c.id
        ORDER BY m.date_created DESC
        LIMIT %s
    """, (limit,))
    
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return data

def get_duplicates_for_session(session_id):
    """Get duplicate records for a specific session"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM duplicate_records WHERE session_id = %s", (session_id,))
    duplicates = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return duplicates