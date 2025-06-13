from database.connection import get_db_connection
from werkzeug.security import check_password_hash

def get_user_by_email(email):
    """Get user by email address"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT u.*, r.role_name 
        FROM users u 
        JOIN roles r ON u.role = r.id 
        WHERE u.email = %s AND u.is_active = TRUE
    """, (email,))
    
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return user

def verify_user_credentials(email, password):
    """Verify user email and password"""
    user = get_user_by_email(email)
    
    if not user:
        return None
    
    # For testing purposes, check plain text passwords
    # TODO: Replace with proper hash checking in production
    test_passwords = {
        'admin@example.com': 'admin123',
        'agent@example.com': 'agent123'
    }
    
    if email in test_passwords and password == test_passwords[email]:
        return user
    
    return None

def update_last_login(user_id):
    """Update user's last login timestamp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET last_login = CURRENT_TIMESTAMP 
        WHERE id = %s
    """, (user_id,))
    
    conn.commit()
    cursor.close()
    conn.close()