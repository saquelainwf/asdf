from database.connection import get_db_connection

def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get total records
    cursor.execute("SELECT COUNT(*) as total FROM mis_data")
    total_records = cursor.fetchone()['total']
    
    # Get total by bank
    cursor.execute("""
        SELECT b.bank_name, COUNT(m.id) as count 
        FROM banks b 
        LEFT JOIN mis_data m ON b.id = m.bank_id 
        GROUP BY b.id, b.bank_name 
        ORDER BY count DESC
    """)
    bank_stats = cursor.fetchall()
    
    # Get recent uploads
    cursor.execute("""
        SELECT us.*, b.bank_name, c.category_name 
        FROM upload_sessions us
        JOIN banks b ON us.bank_id = b.id
        JOIN categories c ON us.category_id = c.id
        ORDER BY us.created_at DESC
        LIMIT 5
    """)
    recent_uploads = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'total_records': total_records,
        'bank_stats': bank_stats,
        'recent_uploads': recent_uploads
    }