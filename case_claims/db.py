from database.connection import get_db_connection
from .matching import run_auto_matching_for_claim, find_potential_matches

def create_case_claim(agent_id, claim_data):
    """Create a new case claim and run auto-matching"""
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
    
    # Run auto-matching after creation
    try:
        matching_result = run_auto_matching_for_claim(claim_id)
        print(f"Auto-matching completed for claim {claim_id}: {matching_result}")
    except Exception as e:
        print(f"Auto-matching failed for claim {claim_id}: {e}")
    
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
            COUNT(CASE WHEN status IN ('matched', 'disputed', 'unmatched') THEN 1 END) as under_review,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_claims,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_claims,
            SUM(CASE WHEN status = 'approved' THEN final_payout_amount ELSE 0 END) as total_earnings
        FROM case_claims 
        WHERE agent_id = %s
    """, (agent_id,))
    
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return {
        'total_claims': stats['total_claims'] or 0,
        'pending_claims': stats['pending_claims'] or 0,
        'under_review': stats['under_review'] or 0,
        'approved_claims': stats['approved_claims'] or 0,
        'rejected_claims': stats['rejected_claims'] or 0,
        'total_earnings': float(stats['total_earnings'] or 0)
    }

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

def get_admin_claims_stats():
    """Get admin dashboard statistics for claims"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_claims,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_claims,
            COUNT(CASE WHEN status = 'matched' THEN 1 END) as matched_claims,
            COUNT(CASE WHEN status = 'disputed' THEN 1 END) as disputed_claims,
            COUNT(CASE WHEN status = 'unmatched' THEN 1 END) as unmatched_claims,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_claims,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_claims
        FROM case_claims
    """)
    
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return stats

def get_claim_with_matches(claim_id):
    """Get claim details with potential MIS matches"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get claim details
    cursor.execute("""
        SELECT cc.*, u.name as agent_name, u.email as agent_email
        FROM case_claims cc
        JOIN users u ON cc.agent_id = u.id
        WHERE cc.id = %s
    """, (claim_id,))
    
    claim = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not claim:
        return None
    
    # Get potential matches using matching algorithm
    matches = find_potential_matches(claim)
    
    return {
        'claim': claim,
        'matches': matches
    }

def update_claim_status(claim_id, status, admin_id, admin_remarks=None, final_payout_percentage=None):
    """Update claim status and admin decision"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate final payout amount if percentage provided
    if final_payout_percentage:
        cursor.execute("SELECT loan_amount FROM case_claims WHERE id = %s", (claim_id,))
        loan_amount = cursor.fetchone()[0]
        final_payout_amount = float(loan_amount) * float(final_payout_percentage) / 100
    else:
        final_payout_amount = None
    
    cursor.execute("""
        UPDATE case_claims 
        SET status = %s, admin_remarks = %s, final_payout_percentage = %s, 
            final_payout_amount = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (status, admin_remarks, final_payout_percentage, final_payout_amount, claim_id))
    
    conn.commit()
    cursor.close()
    conn.close()

def create_case_mis_matching(case_claim_id, mis_data_id, admin_id, confidence, final_payout_amount):
    """Create entry in case_mis_matching table for approved matched/disputed cases"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get original MIS payout amount
    cursor.execute("SELECT payout_amount FROM mis_data WHERE id = %s", (mis_data_id,))
    original_payout = cursor.fetchone()[0]
    
    cursor.execute("""
        INSERT INTO case_mis_matching (
            case_claim_id, mis_data_id, match_confidence, approved_by,
            original_payout_amount, final_payout_amount
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """, (case_claim_id, mis_data_id, confidence, admin_id, original_payout, final_payout_amount))
    
    conn.commit()
    cursor.close()
    conn.close()

def get_banks_list():
    """Get list of all banks"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT DISTINCT bank_name FROM banks ORDER BY bank_name")
    banks = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return banks

def trigger_bulk_matching():
    """Run auto-matching for all pending claims"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all pending claims
    cursor.execute("SELECT id FROM case_claims WHERE status = 'pending'")
    pending_claims = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    results = []
    for claim in pending_claims:
        try:
            result = run_auto_matching_for_claim(claim['id'])
            results.append(result)
        except Exception as e:
            print(f"Matching failed for claim {claim['id']}: {e}")
    
    return results