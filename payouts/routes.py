from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth.decorators import admin_required
from .db import (
    get_agents_with_pending_payouts, get_approved_claims_for_agent,
    get_agent_approval_months, get_payout_dashboard_stats, check_existing_proforma
)
from invoices.db import create_proforma_invoice, get_recent_proforma_invoices

payouts_bp = Blueprint('payouts', __name__)

@payouts_bp.route('/admin/payouts')
@admin_required
def dashboard():
    """Admin payout dashboard"""
    # Get agents with pending payouts
    agents = get_agents_with_pending_payouts()
    
    # Get dashboard statistics
    stats = get_payout_dashboard_stats()
    
    # Get recent proforma invoices
    recent_invoices = get_recent_proforma_invoices(10)
    
    return render_template('admin/payouts_dashboard.html',
                         agents=agents,
                         stats=stats,
                         recent_invoices=recent_invoices)

@payouts_bp.route('/admin/payouts/generate/<int:agent_id>', methods=['GET', 'POST'])
@admin_required
def generate_proforma(agent_id):
    """Generate proforma invoice for agent"""
    
    if request.method == 'POST':
        # Handle proforma generation
        month = request.form.get('month')
        admin_id = session.get('user_id')
        
        try:
            # Get claims for the month
            claims = get_approved_claims_for_agent(agent_id, month)
            
            if not claims:
                flash('No approved claims found for selected month', 'error')
                return redirect(url_for('payouts.generate_proforma', agent_id=agent_id))
            
            # Check if proforma already exists
            existing = check_existing_proforma(agent_id, month)
            if existing:
                flash('Proforma invoice already exists for this month', 'error')
                return redirect(url_for('payouts.generate_proforma', agent_id=agent_id))
            
            # Create proforma invoice
            invoice_id = create_proforma_invoice(agent_id, month, claims, admin_id)
            
            flash(f'Proforma invoice created successfully! Invoice ID: {invoice_id}', 'success')
            return redirect(url_for('payouts.allocation_form', invoice_id=invoice_id))
            
        except Exception as e:
            flash(f'Error creating proforma invoice: {str(e)}', 'error')
            return redirect(url_for('payouts.generate_proforma', agent_id=agent_id))
    
    # GET request - show form
    # Get available months for this agent
    available_months = get_agent_approval_months(agent_id)
    
    if not available_months:
        flash('No approved claims found for this agent', 'error')
        return redirect(url_for('payouts.dashboard'))
    
    # Get selected month from query params or use first available
    selected_month = request.args.get('month', available_months[0]['approval_month'])
    
    # Get claims for selected month
    claims = get_approved_claims_for_agent(agent_id, selected_month)
    
    # Calculate totals
    total_amount = sum(claim['final_payout_amount'] for claim in claims)
    
    # Get month name
    selected_month_name = next(
        (m['month_name'] for m in available_months if m['approval_month'] == selected_month),
        selected_month
    )
    
    # Get agent name
    from database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name FROM users WHERE id = %s", (agent_id,))
    agent = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not agent:
        flash('Agent not found', 'error')
        return redirect(url_for('payouts.dashboard'))
    
    # Check existing proforma
    existing_proforma = check_existing_proforma(agent_id, selected_month)
    
    return render_template('admin/generate_proforma.html',
                         agent_id=agent_id,
                         agent_name=agent['name'],
                         available_months=available_months,
                         selected_month=selected_month,
                         selected_month_name=selected_month_name,
                         claims=claims,
                         total_amount=total_amount,
                         existing_proforma=existing_proforma)

@payouts_bp.route('/admin/payouts/allocation/<int:invoice_id>', methods=['GET', 'POST'])
@admin_required
def allocation_form(invoice_id):
    """Show and handle allocation form for proforma invoice"""
    from invoices.db import get_proforma_invoice_details, get_agent_subconnectors_for_invoice
    from .db import get_existing_allocation, create_payout_allocation, calculate_allocation_amounts
    
    # Get proforma invoice details
    invoice_data = get_proforma_invoice_details(invoice_id)
    
    if not invoice_data:
        flash('Proforma invoice not found', 'error')
        return redirect(url_for('payouts.dashboard'))
    
    invoice = invoice_data['invoice']
    items = invoice_data['items']
    
    if request.method == 'POST':
        try:
            admin_id = session.get('user_id')
            strategy = request.form.get('strategy')
            total_amount = float(request.form.get('total_amount'))
            
            # Get invoice month in YYYY-MM format
            invoice_month = invoice['invoice_month'].strftime('%Y-%m')
            
            if strategy == 'single':
                # Single invoice - no split
                allocation_data = {
                    'strategy': 'single',
                    'total_amount': total_amount,
                    'allocations': [{
                        'subconnector_id': None,
                        'name': 'Main Agent',
                        'percentage': 100.0,
                        'amount': total_amount
                    }],
                    'allocation_reason': 'Single invoice - no split required'
                }
                
            else:
                # Split across subconnectors
                allocations = []
                
                # Get all allocation rows from form
                row_count = 0
                while f'subconnector_{row_count}' in request.form:
                    subconnector_id = request.form.get(f'subconnector_{row_count}')
                    percentage = float(request.form.get(f'percentage_{row_count}', 0))
                    
                    if subconnector_id and percentage > 0:
                        # Get subconnector name
                        from database.connection import get_db_connection
                        conn = get_db_connection()
                        cursor = conn.cursor(dictionary=True)
                        cursor.execute("SELECT subconnector_name FROM subconnectors WHERE id = %s", (subconnector_id,))
                        sub = cursor.fetchone()
                        cursor.close()
                        conn.close()
                        
                        allocations.append({
                            'subconnector_id': int(subconnector_id),
                            'name': sub['subconnector_name'] if sub else 'Unknown',
                            'percentage': percentage,
                            'amount': 0  # Will be calculated
                        })
                    
                    row_count += 1
                
                if not allocations:
                    flash('Please add at least one allocation', 'error')
                    return redirect(url_for('payouts.allocation_form', invoice_id=invoice_id))
                
                # Validate percentages
                total_percentage = sum(a['percentage'] for a in allocations)
                if abs(total_percentage - 100.0) > 0.01:
                    flash(f'Allocation percentages must total 100% (current: {total_percentage}%)', 'error')
                    return redirect(url_for('payouts.allocation_form', invoice_id=invoice_id))
                
                # Calculate amounts
                calculated_allocations = calculate_allocation_amounts(total_amount, allocations)
                
                allocation_data = {
                    'strategy': 'split',
                    'total_amount': total_amount,
                    'allocations': calculated_allocations,
                    'allocation_reason': f'Split across {len(calculated_allocations)} subconnectors for tax optimization'
                }
            
            # Create allocation record
            allocation_id = create_payout_allocation(
                invoice['agent_id'],
                invoice_month,
                total_amount,
                invoice_id,
                allocation_data,
                admin_id
            )
            
            flash(f'Allocation created successfully! Next: Generate final invoices', 'success')
            return redirect(url_for('payouts.generate_final_invoices', allocation_id=allocation_id))
            
        except Exception as e:
            flash(f'Error creating allocation: {str(e)}', 'error')
            return redirect(url_for('payouts.allocation_form', invoice_id=invoice_id))
    
    # GET request - show form
    # Get agent's subconnectors
    subconnectors = get_agent_subconnectors_for_invoice(invoice['agent_id'])
    
    # Check for existing allocation
    invoice_month = invoice['invoice_month'].strftime('%Y-%m')
    existing_allocation = get_existing_allocation(invoice['agent_id'], invoice_month)
    
    return render_template('admin/allocation_form.html',
                         invoice=invoice,
                         items=items,
                         subconnectors=subconnectors,
                         existing_allocation=existing_allocation)

@payouts_bp.route('/admin/payouts/generate-final/<int:allocation_id>')
@admin_required
def generate_final_invoices(allocation_id):
    """Generate final invoices based on allocation"""
    try:
        from invoices.db import create_final_invoices_from_allocation, get_final_invoices_by_allocation
        
        admin_id = session.get('user_id')
        
        # Create final invoices
        created_invoice_ids = create_final_invoices_from_allocation(allocation_id, admin_id)
        
        # Get created invoices for display
        final_invoices = get_final_invoices_by_allocation(allocation_id)
        
        flash(f'Successfully created {len(created_invoice_ids)} final invoice(s)!', 'success')
        return redirect(url_for('payouts.review_final_invoices', allocation_id=allocation_id))
        
    except Exception as e:
        flash(f'Error generating final invoices: {str(e)}', 'error')
        return redirect(url_for('payouts.dashboard'))
    
@payouts_bp.route('/admin/payouts/review-final/<int:allocation_id>')
@admin_required
def review_final_invoices(allocation_id):
    """Review generated final invoices"""
    from invoices.db import get_final_invoices_by_allocation
    
    final_invoices = get_final_invoices_by_allocation(allocation_id)
    
    if not final_invoices:
        flash('No final invoices found for this allocation', 'error')
        return redirect(url_for('payouts.dashboard'))
    
    return render_template('admin/review_final_invoices.html',
                         allocation_id=allocation_id,
                         final_invoices=final_invoices)

@payouts_bp.route('/admin/payouts/delete-allocation', methods=['POST'])
@admin_required
def delete_allocation():
    """Delete existing allocation"""
    try:
        from .db import delete_existing_allocation
        
        agent_id = request.form.get('agent_id')
        invoice_month = request.form.get('invoice_month')
        return_to = request.form.get('return_to')
        
        deleted = delete_existing_allocation(agent_id, invoice_month)
        
        if deleted:
            flash('Existing allocation deleted successfully. You can now create a new one.', 'success')
        else:
            flash('No allocation found to delete.', 'info')
            
        return redirect(return_to)
        
    except Exception as e:
        flash(f'Error deleting allocation: {str(e)}', 'error')
        return redirect(url_for('payouts.dashboard'))