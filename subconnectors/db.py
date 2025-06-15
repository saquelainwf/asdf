from database.connection import get_db_connection

def get_agent_subconnectors(agent_id):
    """Get all subconnectors for a specific agent"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM subconnectors 
        WHERE agent_id = %s AND is_active = TRUE
        ORDER BY created_at DESC
    """, (agent_id,))
    
    subconnectors = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return subconnectors

def create_subconnector(agent_id, data):
    """Create a new subconnector"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO subconnectors (
            agent_id, subconnector_name, mobile_number, 
            pan_number, gst_number, address
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        agent_id, 
        data['subconnector_name'],
        data['mobile_number'],
        data.get('pan_number'),
        data.get('gst_number'),
        data.get('address')
    ))
    
    subconnector_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    
    return subconnector_id

def get_subconnector_by_id(subconnector_id, agent_id):
    """Get subconnector by ID (with agent verification)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM subconnectors 
        WHERE id = %s AND agent_id = %s AND is_active = TRUE
    """, (subconnector_id, agent_id))
    
    subconnector = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return subconnector

def update_subconnector(subconnector_id, agent_id, data):
    """Update subconnector details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE subconnectors 
        SET subconnector_name = %s, mobile_number = %s, 
            pan_number = %s, gst_number = %s, address = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND agent_id = %s
    """, (
        data['subconnector_name'],
        data['mobile_number'],
        data.get('pan_number'),
        data.get('gst_number'),
        data.get('address'),
        subconnector_id,
        agent_id
    ))
    
    conn.commit()
    cursor.close()
    conn.close()

def deactivate_subconnector(subconnector_id, agent_id):
    """Deactivate a subconnector"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE subconnectors 
        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND agent_id = %s
    """, (subconnector_id, agent_id))
    
    conn.commit()
    cursor.close()
    conn.close()

def validate_mobile_number(mobile):
    """Validate mobile number format"""
    import re
    pattern = r'^[6-9]\d{9}$'
    return re.match(pattern, mobile) is not None

def validate_pan_number(pan):
    """Validate PAN number format"""
    if not pan:
        return True  # PAN is optional
    import re
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    return re.match(pattern, pan.upper()) is not None

def validate_gst_number(gst):
    """Validate GST number format"""
    if not gst:
        return True  # GST is optional
    import re
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return re.match(pattern, gst.upper()) is not None