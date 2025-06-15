from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth.decorators import admin_required, agent_required
from .db import (
    get_final_invoice_details, approve_final_invoice, 
    get_pending_final_invoices, bulk_approve_invoices
)

invoices_bp = Blueprint('invoices', __name__)

@invoices_bp.route('/invoice/<int:invoice_id>')
@admin_required
def invoice_details(invoice_id):
    """View invoice details"""
    invoice_data = get_final_invoice_details(invoice_id)
    
    if not invoice_data:
        flash('Invoice not found', 'error')
        return redirect(url_for('payouts.dashboard'))
    
    return render_template('invoices/invoice_details.html',
                         invoice=invoice_data['invoice'],
                         items=invoice_data['items'])

@invoices_bp.route('/invoice/<int:invoice_id>/approve', methods=['POST'])
@admin_required
def approve_invoice(invoice_id):
    """Approve individual invoice"""
    try:
        admin_id = session.get('user_id')
        admin_remarks = request.form.get('admin_remarks', 'Approved by admin')
        
        success = approve_final_invoice(invoice_id, admin_id, admin_remarks)
        
        if success:
            flash('Invoice approved successfully!', 'success')
        else:
            flash('Invoice not found or already approved', 'error')
            
    except Exception as e:
        flash(f'Error approving invoice: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('payouts.dashboard'))

@invoices_bp.route('/invoices/bulk-approve', methods=['POST'])
@admin_required
def bulk_approve():
    """Bulk approve multiple invoices"""
    try:
        invoice_ids = request.form.getlist('invoice_ids')
        admin_id = session.get('user_id')
        admin_remarks = 'Bulk approved by admin'
        
        if not invoice_ids:
            flash('No invoices selected for approval', 'error')
            return redirect(request.referrer or url_for('payouts.dashboard'))
        
        # Convert to integers
        invoice_ids = [int(id) for id in invoice_ids]
        
        approved_count = bulk_approve_invoices(invoice_ids, admin_id, admin_remarks)
        
        flash(f'Successfully approved {approved_count} invoice(s)!', 'success')
        
    except Exception as e:
        flash(f'Error bulk approving invoices: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('payouts.dashboard'))