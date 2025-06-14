from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth.decorators import agent_required, admin_required
from .db import create_case_claim, get_agent_claims, get_agent_stats, get_banks_list

case_claims_bp = Blueprint('case_claims', __name__)

@case_claims_bp.route('/agent/claim-case')
@agent_required
def claim_case_form():
    """Show case claim form for agents"""
    banks = get_banks_list()
    return render_template('case_claims/claim_form.html', banks=banks)

@case_claims_bp.route('/agent/claim-case', methods=['POST'])
@agent_required  
def submit_claim():
    """Handle case claim submission"""
    try:
        agent_id = session.get('user_id')
        
        # Get form data
        claim_data = {
            'customer_name': request.form.get('customer_name'),
            'customer_phone': request.form.get('customer_phone'),
            'loan_ac_no': request.form.get('loan_ac_no') or None,
            'product_type': request.form.get('product_type'),
            'bank_name': request.form.get('bank_name'),
            'loan_amount': float(request.form.get('loan_amount')),
            'application_date': request.form.get('application_date'),
            'payout_percentage': float(request.form.get('payout_percentage'))
        }
        
        # Validate required fields
        required_fields = ['customer_name', 'customer_phone', 'product_type', 'bank_name', 'loan_amount', 'application_date', 'payout_percentage']
        for field in required_fields:
            if not claim_data.get(field):
                flash(f'{field.replace("_", " ").title()} is required', 'error')
                return redirect(url_for('case_claims.claim_case_form'))
        
        # Create claim
        claim_id = create_case_claim(agent_id, claim_data)
        
        flash(f'Case claim submitted successfully! Claim ID: {claim_id}', 'success')
        return redirect(url_for('case_claims.my_claims'))
        
    except Exception as e:
        flash(f'Error submitting claim: {str(e)}', 'error')
        return redirect(url_for('case_claims.claim_case_form'))

@case_claims_bp.route('/agent/my-claims')
@agent_required
def my_claims():
    """Show agent's claims dashboard"""
    agent_id = session.get('user_id')
    
    # Get claims and stats
    claims = get_agent_claims(agent_id)
    stats = get_agent_stats(agent_id)
    print(f"stats: {stats}")
    
    return render_template('case_claims/my_claims.html', 
                         claims=claims, 
                         stats=stats,
                         agent_name=session.get('name'))