from database.connection import get_db_connection

def get_agent_stats(agent_id):
    """Get statistics for specific agent"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # For now, return placeholder data
    # Later this will include actual case claims data
    stats = {
        'total_claims': 0,
        'pending_claims': 0,
        'approved_claims': 0,
        'rejected_claims': 0
    }
    
    cursor.close()
    conn.close()
    
    return stats

def get_agent_recent_activity(agent_id, limit=10):
    """Get recent activity for agent"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # For now, return empty list
    # Later this will include actual case claims activity
    activities = []
    
    cursor.close()
    conn.close()
    
    return activities