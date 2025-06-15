from database.connection import get_db_connection
import json

def get_agents_with_pending_payouts():
    """Get all agents who have approved claims without invoices"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            u.id as agent_id,
            u.name as agent_name,
            u.email as agent_email,
            COUNT(cc.id) as approved_claims_count,
            SUM(cc.final_payout_amount) as total_pending_amount,
            MIN(cc.updated_at) as oldest_approval_date,
            MAX(cc.updated_at) as latest_approval_date
        FROM users u
        JOIN case_claims cc ON u.id = cc.agent_id
        LEFT JOIN invoice_items ii ON cc.id = ii.case_claim_id
        WHERE u.role = 2 
            AND cc.status = 'approved' 
            AND cc.final_payout_amount > 0
            AND ii.case_claim_id IS NULL
        GROUP BY u.id, u.name, u.email
        ORDER BY total_pending_amount DESC
    """)
    
    agents = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return agents

def get_approved_claims_for_agent(agent_id, month=None):
    """Get approved claims for specific agent, optionally filtered by month"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if month:
        # Get claims approved in specific month
        cursor.execute("""
            SELECT cc.*, 
                   DATE_FORMAT(cc.updated_at, '%Y-%m') as approval_month
            FROM case_claims cc
            LEFT JOIN invoice_items ii ON cc.id = ii.case_claim_id
            WHERE cc.agent_id = %s 
                AND cc.status = 'approved' 
                AND cc.final_payout_amount > 0
                AND ii.case_claim_id IS NULL
                AND DATE_FORMAT(cc.updated_at, '%Y-%m') = %s
            ORDER BY cc.updated_at DESC
        """, (agent_id, month))
    else:
        # Get all approved claims without invoices
        cursor.execute("""
            SELECT cc.*, 
                   DATE_FORMAT(cc.updated_at, '%Y-%m') as approval_month
            FROM case_claims cc
            LEFT JOIN invoice_items ii ON cc.id = ii.case_claim_id
            WHERE cc.agent_id = %s 
                AND cc.status = 'approved' 
                AND cc.final_payout_amount > 0
                AND ii.case_claim_id IS NULL
            ORDER BY cc.updated_at DESC
        """, (agent_id,))
    
    claims = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return claims

def get_agent_approval_months(agent_id):
    """Get list of months where agent has approved claims"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            DATE_FORMAT(cc.updated_at, '%Y-%m') as approval_month,
            DATE_FORMAT(cc.updated_at, '%M %Y') as month_name,
            COUNT(cc.id) as claims_count,
            SUM(cc.final_payout_amount) as total_amount
        FROM case_claims cc
        LEFT JOIN invoice_items ii ON cc.id = ii.case_claim_id
        WHERE cc.agent_id = %s 
            AND cc.status = 'approved' 
            AND cc.final_payout_amount > 0
            AND ii.case_claim_id IS NULL
        GROUP BY DATE_FORMAT(cc.updated_at, '%Y-%m'), DATE_FORMAT(cc.updated_at, '%M %Y')
        ORDER BY approval_month DESC
    """, (agent_id,))
    
    months = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return months

def get_payout_dashboard_stats():
    """Get overall payout dashboard statistics"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Total pending payouts
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT cc.agent_id) as agents_with_pending,
            COUNT(cc.id) as total_pending_claims,
            SUM(cc.final_payout_amount) as total_pending_amount
        FROM case_claims cc
        LEFT JOIN invoice_items ii ON cc.id = ii.case_claim_id
        WHERE cc.status = 'approved' 
            AND cc.final_payout_amount > 0
            AND ii.case_claim_id IS NULL
    """)
    
    stats = cursor.fetchone()
    
    # Recent proforma invoices
    cursor.execute("""
        SELECT COUNT(*) as proforma_count
        FROM invoices 
        WHERE invoice_type = 'proforma' 
            AND generated_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """)
    
    recent_proforma = cursor.fetchone()
    stats['recent_proforma_count'] = recent_proforma['proforma_count']
    
    # Recent final invoices
    cursor.execute("""
        SELECT COUNT(*) as final_count
        FROM invoices 
        WHERE invoice_type = 'final' 
            AND generated_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """)
    
    recent_final = cursor.fetchone()
    stats['recent_final_count'] = recent_final['final_count']
    
    cursor.close()
    conn.close()
    
    return stats

def check_existing_proforma(agent_id, month):
    """Check if proforma invoice already exists for agent and month"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM invoices 
        WHERE agent_id = %s 
            AND invoice_type = 'proforma'
            AND DATE_FORMAT(invoice_month, '%Y-%m') = %s
    """, (agent_id, month))
    
    existing = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return existing

def create_payout_allocation(agent_id, invoice_month, total_amount, proforma_invoice_id, allocation_data, admin_id):
    """Create payout allocation record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Validate allocation data
        total_allocated = sum(allocation['amount'] for allocation in allocation_data['allocations'])
        if abs(total_allocated - total_amount) > 0.01:  # Allow small rounding differences
            raise ValueError(f"Allocation total ({total_allocated}) doesn't match invoice total ({total_amount})")
        
        # Insert allocation record
        cursor.execute("""
            INSERT INTO payout_allocations (
                agent_id, invoice_month, total_approved_amount, 
                proforma_invoice_id, allocation_data, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            agent_id, 
            f"{invoice_month}-01",  # Convert YYYY-MM to YYYY-MM-01
            total_amount,
            proforma_invoice_id,
            json.dumps(allocation_data),
            admin_id
        ))
        
        allocation_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        
        return allocation_id
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise e

def get_existing_allocation(agent_id, invoice_month):
    """Check if allocation already exists for agent and month"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM payout_allocations 
        WHERE agent_id = %s 
            AND DATE_FORMAT(invoice_month, '%Y-%m') = %s
    """, (agent_id, invoice_month))
    
    allocation = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return allocation

def validate_allocation_percentages(allocations):
    """Validate that allocation percentages sum to 100%"""
    total_percentage = sum(allocation.get('percentage', 0) for allocation in allocations)
    return abs(total_percentage - 100.0) < 0.01  # Allow small rounding differences

def calculate_allocation_amounts(total_amount, allocations):
    """Calculate actual amounts based on percentages"""
    calculated_allocations = []
    total_calculated = 0
    
    for i, allocation in enumerate(allocations):
        if i == len(allocations) - 1:  # Last allocation gets remainder
            amount = total_amount - total_calculated
        else:
            amount = round(total_amount * allocation['percentage'] / 100, 2)
            total_calculated += amount
        
        calculated_allocations.append({
            'subconnector_id': allocation['subconnector_id'],
            'name': allocation['name'],
            'percentage': allocation['percentage'],
            'amount': amount
        })
    
    return calculated_allocations

def delete_existing_allocation(agent_id, invoice_month):
    """Delete existing allocation for agent and month"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM payout_allocations 
        WHERE agent_id = %s 
            AND DATE_FORMAT(invoice_month, '%Y-%m') = %s
    """, (agent_id, invoice_month))
    
    deleted_count = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    return deleted_count