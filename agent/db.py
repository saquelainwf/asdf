from database.connection import get_db_connection

def get_agent_stats(agent_id):
    """Get statistics for specific agent including case claims"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get case claims statistics
    cursor.execute("""
        SELECT 
            COUNT(*) as total_claims,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_claims,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_claims,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_claims,
            SUM(CASE WHEN status = 'approved' THEN final_payout_amount ELSE 0 END) as total_earnings
        FROM case_claims 
        WHERE agent_id = %s
    """, (agent_id,))
    
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # Return stats with default values if no claims exist
    return {
        'total_claims': stats['total_claims'] or 0,
        'pending_claims': stats['pending_claims'] or 0,
        'approved_claims': stats['approved_claims'] or 0,
        'rejected_claims': stats['rejected_claims'] or 0,
        'total_earnings': float(stats['total_earnings'] or 0)
    }

def get_agent_recent_activity(agent_id, limit=10):
    """Get recent case claims activity for agent"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            customer_name,
            bank_name,
            loan_amount,
            status,
            created_at,
            final_payout_amount
        FROM case_claims 
        WHERE agent_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
    """, (agent_id, limit))
    
    activities = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return activities