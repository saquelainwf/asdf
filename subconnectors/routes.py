from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth.decorators import agent_required
from .db import (
    get_agent_subconnectors, create_subconnector, get_subconnector_by_id,
    update_subconnector, deactivate_subconnector, validate_mobile_number,
    validate_pan_number, validate_gst_number
)

subconnectors_bp = Blueprint('subconnectors', __name__)

@subconnectors_bp.route('/agent/subconnectors')
@agent_required
def list_subconnectors():
    """List all subconnectors for the agent"""
    agent_id = session.get('user_id')
    subconnectors = get_agent_subconnectors(agent_id)
    
    return render_template('subconnectors/list.html', 
                         subconnectors=subconnectors)

@subconnectors_bp.route('/agent/subconnectors/new', methods=['GET', 'POST'])
@agent_required
def new_subconnector():
    """Create new subconnector"""
    if request.method == 'POST':
        agent_id = session.get('user_id')
        
        # Get form data
        data = {
            'subconnector_name': request.form.get('subconnector_name', '').strip(),
            'mobile_number': request.form.get('mobile_number', '').strip(),
            'pan_number': request.form.get('pan_number', '').strip().upper(),
            'gst_number': request.form.get('gst_number', '').strip().upper(),
            'address': request.form.get('address', '').strip()
        }
        
        # Validation
        errors = []
        
        if not data['subconnector_name']:
            errors.append('Subconnector name is required')
        
        if not data['mobile_number']:
            errors.append('Mobile number is required')
        elif not validate_mobile_number(data['mobile_number']):
            errors.append('Invalid mobile number format')
        
        if data['pan_number'] and not validate_pan_number(data['pan_number']):
            errors.append('Invalid PAN number format')
        
        if data['gst_number'] and not validate_gst_number(data['gst_number']):
            errors.append('Invalid GST number format')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('subconnectors/form.html', data=data)
        
        try:
            subconnector_id = create_subconnector(agent_id, data)
            flash(f'Subconnector "{data["subconnector_name"]}" created successfully!', 'success')
            return redirect(url_for('subconnectors.list_subconnectors'))
        except Exception as e:
            flash(f'Error creating subconnector: {str(e)}', 'error')
            return render_template('subconnectors/form.html', data=data)
    
    return render_template('subconnectors/form.html')

@subconnectors_bp.route('/agent/subconnectors/<int:subconnector_id>/edit', methods=['GET', 'POST'])
@agent_required
def edit_subconnector(subconnector_id):
    """Edit existing subconnector"""
    agent_id = session.get('user_id')
    subconnector = get_subconnector_by_id(subconnector_id, agent_id)
    
    if not subconnector:
        flash('Subconnector not found', 'error')
        return redirect(url_for('subconnectors.list_subconnectors'))
    
    if request.method == 'POST':
        # Get form data
        data = {
            'subconnector_name': request.form.get('subconnector_name', '').strip(),
            'mobile_number': request.form.get('mobile_number', '').strip(),
            'pan_number': request.form.get('pan_number', '').strip().upper(),
            'gst_number': request.form.get('gst_number', '').strip().upper(),
            'address': request.form.get('address', '').strip()
        }
        
        # Validation (same as create)
        errors = []
        
        if not data['subconnector_name']:
            errors.append('Subconnector name is required')
        
        if not data['mobile_number']:
            errors.append('Mobile number is required')
        elif not validate_mobile_number(data['mobile_number']):
            errors.append('Invalid mobile number format')
        
        if data['pan_number'] and not validate_pan_number(data['pan_number']):
            errors.append('Invalid PAN number format')
        
        if data['gst_number'] and not validate_gst_number(data['gst_number']):
            errors.append('Invalid GST number format')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('subconnectors/form.html', 
                                 data=data, subconnector=subconnector, edit_mode=True)
        
        try:
            update_subconnector(subconnector_id, agent_id, data)
            flash(f'Subconnector "{data["subconnector_name"]}" updated successfully!', 'success')
            return redirect(url_for('subconnectors.list_subconnectors'))
        except Exception as e:
            flash(f'Error updating subconnector: {str(e)}', 'error')
            return render_template('subconnectors/form.html', 
                                 data=data, subconnector=subconnector, edit_mode=True)
    
    return render_template('subconnectors/form.html', 
                         subconnector=subconnector, edit_mode=True)

@subconnectors_bp.route('/agent/subconnectors/<int:subconnector_id>/deactivate', methods=['POST'])
@agent_required
def deactivate_subconnector_route(subconnector_id):
    """Deactivate a subconnector"""
    agent_id = session.get('user_id')
    
    try:
        deactivate_subconnector(subconnector_id, agent_id)
        flash('Subconnector deactivated successfully!', 'success')
    except Exception as e:
        flash(f'Error deactivating subconnector: {str(e)}', 'error')
    
    return redirect(url_for('subconnectors.list_subconnectors'))