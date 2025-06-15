from database.connection import get_db_connection
import uuid
from datetime import datetime
import json

def generate_invoice_number(invoice_type, agent_id, month, subconnector_id=None):
    """Generate unique invoice number"""
    # Format: PRO-2025-01-AGT001-001 or FIN-2025-01-AGT001-SUB001-001
    year_month = month.replace('-', '')  # 202501
    agent_code = f"AGT{agent_id:03d}"
    
    # Get next sequence number for this specific combination
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if subconnector_id:
        # For final invoices with subconnector
        cursor.execute("""
            SELECT COUNT(*) + 1 as next_seq
            FROM invoices 
            WHERE invoice_type = %s 
                AND agent_id = %s 
                AND DATE_FORMAT(invoice_month, '%Y-%m') = %s
                AND subconnector_id = %s
        """, (invoice_type, agent_id, month, subconnector_id))
    else:
        # For proforma invoices or final invoices without subconnector
        cursor.execute("""
            SELECT COUNT(*) + 1 as next_seq
            FROM invoices 
            WHERE invoice_type = %s 
                AND agent_id = %s 
                AND DATE_FORMAT(invoice_month, '%Y-%m') = %s
                AND subconnector_id IS NULL
        """, (invoice_type, agent_id, month))
    
    seq = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    prefix = "PRO" if invoice_type == "proforma" else "FIN"
    
    if subconnector_id:
        sub_code = f"SUB{subconnector_id:03d}"
        return f"{prefix}-{year_month}-{agent_code}-{sub_code}-{seq:03d}"
    else:
        return f"{prefix}-{year_month}-{agent_code}-{seq:03d}"

def create_proforma_invoice(agent_id, month, claims_data, admin_id):
    """Create proforma invoice with approved claims"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Calculate totals
        total_amount = sum(claim['final_payout_amount'] for claim in claims_data)
        net_amount = total_amount  # No tax for now
        
        # Generate invoice number
        invoice_number = generate_invoice_number('proforma', agent_id, month, None)
        
        # Create invoice month date (first day of month)
        invoice_month_date = f"{month}-01"
        
        # Insert invoice
        cursor.execute("""
            INSERT INTO invoices (
                invoice_number, agent_id, subconnector_id, invoice_month,
                invoice_type, total_amount, tax_amount, net_amount,
                status, generated_by
            ) VALUES (%s, %s, NULL, %s, 'proforma', %s, 0, %s, 'generated', %s)
        """, (invoice_number, agent_id, invoice_month_date, total_amount, net_amount, admin_id))
        
        invoice_id = cursor.lastrowid
        
        # Insert invoice items
        for claim in claims_data:
            cursor.execute("""
                INSERT INTO invoice_items (
                    invoice_id, case_claim_id, customer_name, loan_ac_no,
                    bank_name, loan_amount, payout_percentage, payout_amount,
                    description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                invoice_id,
                claim['id'],
                claim['customer_name'],
                claim['loan_ac_no'],
                claim['bank_name'],
                claim['loan_amount'],
                claim['final_payout_percentage'],
                claim['final_payout_amount'],
                f"Case claim #{claim['id']} - {claim['customer_name']}"
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return invoice_id
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise e

def get_proforma_invoice_details(invoice_id):
    """Get proforma invoice with items and agent details"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get invoice details
    cursor.execute("""
        SELECT i.*, u.name as agent_name, u.email as agent_email
        FROM invoices i
        JOIN users u ON i.agent_id = u.id
        WHERE i.id = %s AND i.invoice_type = 'proforma'
    """, (invoice_id,))
    
    invoice = cursor.fetchone()
    
    if not invoice:
        cursor.close()
        conn.close()
        return None
    
    # Get invoice items
    cursor.execute("""
        SELECT ii.*, cc.application_date, cc.claim_date
        FROM invoice_items ii
        JOIN case_claims cc ON ii.case_claim_id = cc.id
        WHERE ii.invoice_id = %s
        ORDER BY ii.id
    """, (invoice_id,))
    
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'invoice': invoice,
        'items': items
    }

def get_agent_subconnectors_for_invoice(agent_id):
    """Get active subconnectors for allocation"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT id, subconnector_name, mobile_number, pan_number, gst_number
        FROM subconnectors 
        WHERE agent_id = %s AND is_active = TRUE
        ORDER BY subconnector_name
    """, (agent_id,))
    
    subconnectors = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return subconnectors

def get_recent_proforma_invoices(limit=10):
    """Get recent proforma invoices for admin dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT i.*, u.name as agent_name,
               COUNT(ii.id) as items_count
        FROM invoices i
        JOIN users u ON i.agent_id = u.id
        LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
        WHERE i.invoice_type = 'proforma'
        GROUP BY i.id
        ORDER BY i.generated_at DESC
        LIMIT %s
    """, (limit,))
    
    invoices = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return invoices

def create_final_invoices_from_allocation(allocation_id, admin_id):
    """Create final invoices based on allocation data"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get allocation details
        cursor.execute("""
            SELECT pa.*, i.invoice_month, i.agent_id, u.name as agent_name
            FROM payout_allocations pa
            JOIN invoices i ON pa.proforma_invoice_id = i.id
            JOIN users u ON pa.agent_id = u.id
            WHERE pa.id = %s
        """, (allocation_id,))
        
        allocation = cursor.fetchone()
        if not allocation:
            raise ValueError("Allocation not found")
        
        allocation_data = json.loads(allocation['allocation_data'])
        proforma_invoice_id = allocation['proforma_invoice_id']
        
        # Get proforma invoice items
        cursor.execute("""
            SELECT * FROM invoice_items 
            WHERE invoice_id = %s
            ORDER BY id
        """, (proforma_invoice_id,))
        
        proforma_items = cursor.fetchall()
        
        created_invoices = []
        
        if allocation_data['strategy'] == 'single':
            # Create single final invoice
            invoice_id = create_single_final_invoice(
                allocation, proforma_items, admin_id, cursor
            )
            created_invoices.append(invoice_id)
            
        else:
            # Create multiple final invoices based on allocation
            for alloc in allocation_data['allocations']:
                invoice_id = create_split_final_invoice(
                    allocation, alloc, proforma_items, admin_id, cursor
                )
                created_invoices.append(invoice_id)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return created_invoices
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise e

def create_single_final_invoice(allocation, proforma_items, admin_id, cursor):
    """Create single final invoice for main agent"""
    
    # Generate invoice number
    invoice_month = allocation['invoice_month'].strftime('%Y-%m')
    invoice_number = generate_invoice_number('final', allocation['agent_id'], invoice_month, None)
    
    # Create final invoice
    cursor.execute("""
        INSERT INTO invoices (
            invoice_number, agent_id, subconnector_id, invoice_month,
            invoice_type, total_amount, tax_amount, net_amount,
            status, generated_by
        ) VALUES (%s, %s, NULL, %s, 'final', %s, 0, %s, 'generated', %s)
    """, (
        invoice_number, 
        allocation['agent_id'], 
        allocation['invoice_month'],
        allocation['total_approved_amount'],
        allocation['total_approved_amount'],
        admin_id
    ))
    
    final_invoice_id = cursor.lastrowid
    
    # Copy all items from proforma to final invoice
    for item in proforma_items:
        cursor.execute("""
            INSERT INTO invoice_items (
                invoice_id, case_claim_id, customer_name, loan_ac_no,
                bank_name, loan_amount, payout_percentage, payout_amount,
                description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            final_invoice_id,
            item['case_claim_id'],
            item['customer_name'],
            item['loan_ac_no'],
            item['bank_name'],
            item['loan_amount'],
            item['payout_percentage'],
            item['payout_amount'],
            f"Final invoice - {item['description']}"
        ))
    
    return final_invoice_id

def create_split_final_invoice(allocation, alloc_data, proforma_items, admin_id, cursor):
    """Create final invoice for specific subconnector allocation"""
    
    # Generate invoice number
    invoice_month = allocation['invoice_month'].strftime('%Y-%m')
    invoice_number = generate_invoice_number('final', allocation['agent_id'], invoice_month, alloc_data['subconnector_id'])
    
    # Create final invoice
    cursor.execute("""
        INSERT INTO invoices (
            invoice_number, agent_id, subconnector_id, invoice_month,
            invoice_type, total_amount, tax_amount, net_amount,
            status, generated_by
        ) VALUES (%s, %s, %s, %s, 'final', %s, 0, %s, 'generated', %s)
    """, (
        invoice_number,
        allocation['agent_id'],
        alloc_data['subconnector_id'],
        allocation['invoice_month'],
        alloc_data['amount'],
        alloc_data['amount'],
        admin_id
    ))
    
    final_invoice_id = cursor.lastrowid
    
    # Calculate proportional distribution of items
    total_proforma_amount = sum(float(item['payout_amount']) for item in proforma_items)
    allocation_ratio = alloc_data['amount'] / total_proforma_amount
    
    # Add proportional items to final invoice
    for item in proforma_items:
        proportional_amount = float(item['payout_amount']) * allocation_ratio
        
        cursor.execute("""
            INSERT INTO invoice_items (
                invoice_id, case_claim_id, customer_name, loan_ac_no,
                bank_name, loan_amount, payout_percentage, payout_amount,
                description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            final_invoice_id,
            item['case_claim_id'],
            item['customer_name'],
            item['loan_ac_no'],
            item['bank_name'],
            item['loan_amount'],
            item['payout_percentage'],
            proportional_amount,
            f"Split allocation ({alloc_data['percentage']}%) - {item['description']}"
        ))
    
    return final_invoice_id

def get_final_invoices_by_allocation(allocation_id):
    """Get all final invoices created from an allocation"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get allocation details first
    cursor.execute("""
        SELECT invoice_month, agent_id FROM payout_allocations WHERE id = %s
    """, (allocation_id,))
    
    allocation = cursor.fetchone()
    if not allocation:
        cursor.close()
        conn.close()
        return []
    
    # Get final invoices for this agent and month
    cursor.execute("""
        SELECT i.*, s.subconnector_name,
               COUNT(ii.id) as items_count
        FROM invoices i
        LEFT JOIN subconnectors s ON i.subconnector_id = s.id
        LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
        WHERE i.agent_id = %s 
            AND i.invoice_type = 'final'
            AND DATE_FORMAT(i.invoice_month, '%Y-%m') = %s
        GROUP BY i.id
        ORDER BY i.generated_at DESC
    """, (allocation['agent_id'], allocation['invoice_month'].strftime('%Y-%m')))
    
    invoices = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return invoices

def get_final_invoice_details(invoice_id):
    """Get final invoice with items and related details"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get invoice details
    cursor.execute("""
        SELECT i.*, u.name as agent_name, u.email as agent_email,
               s.subconnector_name, s.mobile_number as sub_mobile,
               s.pan_number, s.gst_number
        FROM invoices i
        JOIN users u ON i.agent_id = u.id
        LEFT JOIN subconnectors s ON i.subconnector_id = s.id
        WHERE i.id = %s AND i.invoice_type = 'final'
    """, (invoice_id,))
    
    invoice = cursor.fetchone()
    
    if not invoice:
        cursor.close()
        conn.close()
        return None
    
    # Get invoice items
    cursor.execute("""
        SELECT ii.*, cc.application_date, cc.claim_date
        FROM invoice_items ii
        LEFT JOIN case_claims cc ON ii.case_claim_id = cc.id
        WHERE ii.invoice_id = %s
        ORDER BY ii.id
    """, (invoice_id,))
    
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'invoice': invoice,
        'items': items
    }

def approve_final_invoice(invoice_id, admin_id, admin_remarks=None):
    """Approve a final invoice"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE invoices 
        SET status = 'approved', approved_by = %s, approved_at = CURRENT_TIMESTAMP,
            admin_remarks = %s
        WHERE id = %s AND invoice_type = 'final' AND status = 'generated'
    """, (admin_id, admin_remarks, invoice_id))
    
    rows_affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    return rows_affected > 0

def get_pending_final_invoices(limit=20):
    """Get pending final invoices for admin review"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT i.*, u.name as agent_name, s.subconnector_name,
               COUNT(ii.id) as items_count
        FROM invoices i
        JOIN users u ON i.agent_id = u.id
        LEFT JOIN subconnectors s ON i.subconnector_id = s.id
        LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
        WHERE i.invoice_type = 'final' AND i.status = 'generated'
        GROUP BY i.id
        ORDER BY i.generated_at DESC
        LIMIT %s
    """, (limit,))
    
    invoices = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return invoices

def get_invoice_approval_stats():
    """Get statistics for invoice approvals"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN status = 'generated' AND invoice_type = 'final' THEN 1 END) as pending_final,
            COUNT(CASE WHEN status = 'approved' AND invoice_type = 'final' THEN 1 END) as approved_final,
            COUNT(CASE WHEN invoice_type = 'proforma' THEN 1 END) as total_proforma,
            SUM(CASE WHEN status = 'generated' AND invoice_type = 'final' THEN total_amount ELSE 0 END) as pending_amount,
            SUM(CASE WHEN status = 'approved' AND invoice_type = 'final' THEN total_amount ELSE 0 END) as approved_amount
        FROM invoices
        WHERE generated_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """)
    
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return stats

def bulk_approve_invoices(invoice_ids, admin_id, admin_remarks=None):
    """Approve multiple final invoices at once"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert list to comma-separated string for SQL IN clause
    placeholders = ','.join(['%s'] * len(invoice_ids))
    
    cursor.execute(f"""
        UPDATE invoices 
        SET status = 'approved', approved_by = %s, approved_at = CURRENT_TIMESTAMP,
            admin_remarks = %s
        WHERE id IN ({placeholders}) AND invoice_type = 'final' AND status = 'generated'
    """, [admin_id, admin_remarks] + invoice_ids)
    
    rows_affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    return rows_affected

def get_agent_final_invoices(agent_id):
    """Get all final invoices for a specific agent"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT i.*, s.subconnector_name,
               COUNT(ii.id) as items_count
        FROM invoices i
        LEFT JOIN subconnectors s ON i.subconnector_id = s.id
        LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
        WHERE i.agent_id = %s 
            AND i.invoice_type = 'final'
            AND i.status = 'approved'
        GROUP BY i.id
        ORDER BY i.invoice_month DESC, i.generated_at DESC
    """, (agent_id,))
    
    invoices = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return invoices

def get_agent_invoice_stats(agent_id):
    """Get invoice statistics for agent dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_invoices,
            COUNT(CASE WHEN status = 'generated' THEN 1 END) as pending_invoices,
            SUM(CASE WHEN status = 'approved' THEN total_amount ELSE 0 END) as total_earnings,
            COUNT(DISTINCT DATE_FORMAT(invoice_month, '%%Y-%%m')) as active_months,
            COUNT(DISTINCT subconnector_id) as entities_used
        FROM invoices 
        WHERE agent_id = %s AND invoice_type = 'final'
    """, (agent_id,))
    
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # Handle None values
    return {
        'approved_invoices': stats['approved_invoices'] or 0,
        'pending_invoices': stats['pending_invoices'] or 0,
        'total_earnings': float(stats['total_earnings'] or 0),
        'active_months': stats['active_months'] or 0,
        'entities_used': stats['entities_used'] or 0
    }

def get_agent_monthly_breakdown(agent_id):
    """Get monthly invoice breakdown for agent"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            DATE_FORMAT(invoice_month, '%Y-%m') as month,
            DATE_FORMAT(invoice_month, '%M %Y') as month_name,
            COUNT(*) as invoice_count,
            SUM(total_amount) as month_total,
            GROUP_CONCAT(
                CASE 
                    WHEN subconnector_id IS NULL THEN 'Main Agent'
                    ELSE s.subconnector_name 
                END 
                ORDER BY total_amount DESC
                SEPARATOR ', '
            ) as entities
        FROM invoices i
        LEFT JOIN subconnectors s ON i.subconnector_id = s.id
        WHERE i.agent_id = %s 
            AND i.invoice_type = 'final'
            AND i.status = 'approved'
        GROUP BY DATE_FORMAT(invoice_month, '%Y-%m'), DATE_FORMAT(invoice_month, '%M %Y')
        ORDER BY month DESC
        LIMIT 12
    """, (agent_id,))
    
    months = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return months