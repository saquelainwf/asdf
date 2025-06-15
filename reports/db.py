from database.connection import get_db_connection
from datetime import datetime, timedelta

def get_reports_overview():
    """Get overview statistics for reports dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT i.agent_id) as total_agents,
            COUNT(i.id) as total_invoices,
            SUM(i.total_amount) as total_payouts,
            SUM(i.tax_amount) as total_tax
        FROM invoices i
        WHERE i.invoice_type = 'final' AND i.status = 'approved'
    """)
    
    overview = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return overview

def get_monthly_payout_report(month):
    """Get detailed monthly payout report"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all invoices for the month
    cursor.execute("""
        SELECT 
            i.*,
            u.name as agent_name,
            u.email as agent_email,
            s.subconnector_name,
            COUNT(ii.id) as items_count,
            SUM(ii.payout_amount) as items_total
        FROM invoices i
        JOIN users u ON i.agent_id = u.id
        LEFT JOIN subconnectors s ON i.subconnector_id = s.id
        LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
        WHERE DATE_FORMAT(i.invoice_month, '%%Y-%%m') = %s
            AND i.invoice_type = 'final'
            AND i.status = 'approved'
        GROUP BY i.id
        ORDER BY u.name, i.generated_at
    """, (month,))
    
    invoices = cursor.fetchall()
    
    # Get summary statistics
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT i.agent_id) as unique_agents,
            COUNT(i.id) as total_invoices,
            SUM(i.total_amount) as total_gross,
            SUM(i.tax_amount) as total_tax,
            SUM(i.net_amount) as total_net,
            COUNT(CASE WHEN i.subconnector_id IS NOT NULL THEN 1 END) as subconnector_invoices,
            COUNT(CASE WHEN i.subconnector_id IS NULL THEN 1 END) as direct_invoices
        FROM invoices i
        WHERE DATE_FORMAT(i.invoice_month, '%%Y-%%m') = %s
            AND i.invoice_type = 'final'
            AND i.status = 'approved'
    """, (month,))
    
    summary = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return {
        'month': month,
        'invoices': invoices,
        'summary': summary
    }

def get_agent_performance_report(start_date, end_date):
    """Get agent performance comparison report"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            u.id as agent_id,
            u.name as agent_name,
            u.email as agent_email,
            COUNT(DISTINCT cc.id) as total_claims,
            COUNT(CASE WHEN cc.status = 'approved' THEN 1 END) as approved_claims,
            COUNT(DISTINCT i.id) as total_invoices,
            SUM(i.total_amount) as total_earnings,
            SUM(i.tax_amount) as total_tax,
            COUNT(DISTINCT i.subconnector_id) as entities_used,
            AVG(cc.final_payout_percentage) as avg_payout_rate
        FROM users u
        LEFT JOIN case_claims cc ON u.id = cc.agent_id
        LEFT JOIN invoices i ON u.id = i.agent_id 
            AND i.invoice_type = 'final' 
            AND i.status = 'approved'
            AND i.invoice_month BETWEEN %s AND %s
        WHERE u.role = 2
        GROUP BY u.id, u.name, u.email
        HAVING total_claims > 0 OR total_invoices > 0
        ORDER BY total_earnings DESC
    """, (start_date, end_date))
    
    agents = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'agents': agents
    }

def get_tax_summary_report(year):
    """Get annual tax summary report"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get monthly breakdown
    cursor.execute("""
        SELECT 
            DATE_FORMAT(invoice_month, '%%Y-%%m') as month,
            DATE_FORMAT(invoice_month, '%%M %%Y') as month_name,
            COUNT(*) as invoice_count,
            SUM(total_amount) as gross_amount,
            SUM(tax_amount) as tax_deducted,
            SUM(net_amount) as net_amount
        FROM invoices
        WHERE YEAR(invoice_month) = %s
            AND invoice_type = 'final'
            AND status = 'approved'
        GROUP BY DATE_FORMAT(invoice_month, '%%Y-%%m')
        ORDER BY month
    """, (year,))
    
    monthly_data = cursor.fetchall()
    
    # Get agent-wise summary
    cursor.execute("""
        SELECT 
            u.name as agent_name,
            COUNT(i.id) as invoice_count,
            SUM(i.total_amount) as gross_earnings,
            SUM(i.tax_amount) as tax_deducted,
            SUM(i.net_amount) as net_earnings
        FROM users u
        JOIN invoices i ON u.id = i.agent_id
        WHERE YEAR(i.invoice_month) = %s
            AND i.invoice_type = 'final'
            AND i.status = 'approved'
        GROUP BY u.id, u.name
        ORDER BY gross_earnings DESC
    """, (year,))
    
    agent_summary = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'year': year,
        'monthly_data': monthly_data,
        'agent_summary': agent_summary
    }

def get_entity_analysis_report(period):
    """Get entity usage analysis report"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Calculate date range based on period
    end_date = datetime.now().date()
    if period == 'last_6_months':
        start_date = end_date - timedelta(days=180)
    elif period == 'last_12_months':
        start_date = end_date - timedelta(days=365)
    elif period == 'current_year':
        start_date = datetime(end_date.year, 1, 1).date()
    else:  # all_time
        start_date = datetime(2020, 1, 1).date()
    
    # Get subconnector usage statistics
    cursor.execute("""
        SELECT 
            s.id as subconnector_id,
            s.subconnector_name,
            s.pan_number,
            s.gst_number,
            u.name as agent_name,
            COUNT(i.id) as invoice_count,
            SUM(i.total_amount) as total_amount,
            SUM(i.tax_amount) as tax_saved,
            AVG(i.total_amount) as avg_invoice_amount
        FROM subconnectors s
        JOIN users u ON s.agent_id = u.id
        LEFT JOIN invoices i ON s.id = i.subconnector_id
            AND i.invoice_type = 'final'
            AND i.status = 'approved'
            AND i.invoice_month BETWEEN %s AND %s
        WHERE s.is_active = TRUE
        GROUP BY s.id, s.subconnector_name, s.pan_number, s.gst_number, u.name
        ORDER BY total_amount DESC
    """, (start_date, end_date))
    
    entities = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'entities': entities
    }