from database.connection import get_db_connection

def create_case_claim(agent_id, claim_data):
    """Create a new case claim"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO case_claims (
            agent_id, customer_name, customer_phone, loan_ac_no, 
            product_type, bank_name, loan_amount, application_date, 
            payout_percentage
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        agent_id, claim_data['customer_name'], claim_data['customer_phone'],
        claim_data['loan_ac_no'], claim_data['product_type'], claim_data['bank_name'],
        claim_data['loan_amount'], claim_data['application_date'], 
        claim_data['payout_percentage']
    ))
    
    claim_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    
    return claim_id

def get_agent_claims(agent_id, status=None):
    """Get all claims for an agent, optionally filtered by status"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if status:
        cursor.execute("""
            SELECT * FROM case_claims 
            WHERE agent_id = %s AND status = %s 
            ORDER BY created_at DESC
        """, (agent_id, status))
    else:
        cursor.execute("""
            SELECT * FROM case_claims 
            WHERE agent_id = %s 
            ORDER BY created_at DESC
        """, (agent_id,))
    
    claims = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return claims

def get_agent_stats(agent_id):
    """Get statistics for agent claims"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_claims,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_claims,
            COUNT(CASE WHEN status IN ('matched', 'disputed') THEN 1 END) as under_review,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_claims,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_claims,
            COALESCE(SUM(CASE WHEN status = 'approved' THEN final_payout_amount ELSE 0 END), 0) as total_earnings
        FROM case_claims 
        WHERE agent_id = %s
    """, (agent_id,))
    
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return stats

def get_all_claims_for_admin(status=None):
    """Get all claims for admin review, optionally filtered by status"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if status:
        cursor.execute("""
            SELECT cc.*, u.name as agent_name, u.email as agent_email
            FROM case_claims cc
            JOIN users u ON cc.agent_id = u.id
            WHERE cc.status = %s
            ORDER BY cc.created_at DESC
        """, (status,))
    else:
        cursor.execute("""
            SELECT cc.*, u.name as agent_name, u.email as agent_email
            FROM case_claims cc
            JOIN users u ON cc.agent_id = u.id
            ORDER BY cc.created_at DESC
        """)
    
    claims = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return claims

def get_banks_list():
    """Get list of all banks"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT DISTINCT bank_name FROM banks ORDER BY bank_name")
    banks = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return banks