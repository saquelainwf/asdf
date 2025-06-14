from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth.decorators import admin_required
from case_claims.db import (
    get_all_claims_for_admin, get_admin_claims_stats, get_claim_with_matches,
    update_claim_status, create_case_mis_matching, trigger_bulk_matching
)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/claims')
@admin_required
def claims_dashboard():
    """Admin dashboard for case claims management"""
    # Get filter from query params
    status_filter = request.args.get('status', '')
    
    # Get claims based on filter
    if status_filter:
        claims = get_all_claims_for_admin(status_filter)
    else:
        claims = get_all_claims_for_admin()
    
    # Get statistics
    stats = get_admin_claims_stats()
    
    return render_template('admin/claims_dashboard.html', 
                         claims=claims, 
                         stats=stats,
                         current_filter=status_filter)

@admin_bp.route('/admin/claim/<int:claim_id>')
@admin_required
def review_claim(claim_id):
    """Review individual claim with potential matches"""
    claim_data = get_claim_with_matches(claim_id)
    
    if not claim_data:
        flash('Claim not found', 'error')
        return redirect(url_for('admin.claims_dashboard'))
    
    return render_template('admin/review_claim.html', 
                         claim=claim_data['claim'],
                         matches=claim_data['matches'])

@admin_bp.route('/admin/claim/<int:claim_id>/approve', methods=['POST'])
@admin_required
def approve_claim(claim_id):
    """Approve a case claim"""
    try:
        admin_id = session.get('user_id')
        mis_data_id = request.form.get('mis_data_id')  # For matched/disputed cases
        final_percentage = request.form.get('final_payout_percentage')
        admin_remarks = request.form.get('admin_remarks', '')
        
        if not final_percentage:
            flash('Payout percentage is required', 'error')
            return redirect(url_for('admin.review_claim', claim_id=claim_id))
        
        # Update claim status
        update_claim_status(
            claim_id=claim_id,
            status='approved',
            admin_id=admin_id,
            admin_remarks=admin_remarks,
            final_payout_percentage=float(final_percentage)
        )
        
        # If MIS data ID provided, create matching entry
        if mis_data_id:
            confidence = float(request.form.get('confidence', 0))
            
            # Calculate final payout amount
            from case_claims.db import get_claim_with_matches
            claim_data = get_claim_with_matches(claim_id)
            loan_amount = claim_data['claim']['loan_amount']
            final_payout_amount = float(loan_amount) * float(final_percentage) / 100
            
            create_case_mis_matching(
                case_claim_id=claim_id,
                mis_data_id=int(mis_data_id),
                admin_id=admin_id,
                confidence=confidence,
                final_payout_amount=final_payout_amount
            )
        
        flash('Claim approved successfully!', 'success')
        return redirect(url_for('admin.claims_dashboard'))
        
    except Exception as e:
        flash(f'Error approving claim: {str(e)}', 'error')
        return redirect(url_for('admin.review_claim', claim_id=claim_id))

@admin_bp.route('/admin/claim/<int:claim_id>/reject', methods=['POST'])
@admin_required
def reject_claim(claim_id):
    """Reject a case claim"""
    try:
        admin_id = session.get('user_id')
        admin_remarks = request.form.get('admin_remarks', 'Claim rejected by admin')
        
        update_claim_status(
            claim_id=claim_id,
            status='rejected',
            admin_id=admin_id,
            admin_remarks=admin_remarks
        )
        
        flash('Claim rejected successfully!', 'success')
        return redirect(url_for('admin.claims_dashboard'))
        
    except Exception as e:
        flash(f'Error rejecting claim: {str(e)}', 'error')
        return redirect(url_for('admin.review_claim', claim_id=claim_id))

@admin_bp.route('/admin/run-matching', methods=['POST'])
@admin_required
def run_bulk_matching():
    """Manually trigger bulk matching for pending claims"""
    try:
        results = trigger_bulk_matching()
        
        if results:
            matched_count = len([r for r in results if r['status'] in ['matched', 'disputed']])
            total_processed = len(results)
            flash(f'Processed {total_processed} claims. Found {matched_count} potential matches.', 'success')
        else:
            flash('No pending claims found for matching.', 'info')
        
        return redirect(url_for('admin.claims_dashboard'))
        
    except Exception as e:
        flash(f'Error running bulk matching: {str(e)}', 'error')
        return redirect(url_for('admin.claims_dashboard'))