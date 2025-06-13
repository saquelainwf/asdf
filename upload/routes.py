from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os
import uuid
import json
from database.connection import get_db_connection
from utils.helpers import allowed_file, REQUIRED_HEADERS, OPTIONAL_HEADERS
from services.csv_parser import parse_csv_file
from services.validator import validate_csv_data
from utils.helpers import parse_date
from .db import get_banks_categories, save_upload_session, save_duplicates, get_upload_session, update_upload_session

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/upload')
def upload_page():
    banks, categories = get_banks_categories()
    return render_template('upload.html', 
                         banks=banks, 
                         categories=categories,
                         required_headers=REQUIRED_HEADERS,
                         optional_headers=OPTIONAL_HEADERS)

@upload_bp.route('/upload', methods=['POST'])
def handle_upload():
    try:
        # Get form data
        bank_id = request.form.get('bank_id')
        category_id = request.form.get('category_id')
        
        if not bank_id or not category_id:
            flash('Please select bank and category', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('upload.upload_page'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('upload.upload_page'))
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload CSV or Excel file.', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Generate session ID and save file
        session_id = str(uuid.uuid4())
        filename = f"{session_id}_{file.filename}"
        from flask import current_app
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Parse and validate CSV
        data, error = parse_csv_file(filepath)
        if error:
            os.remove(filepath)
            flash(f'File parsing error: {error}', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Validate headers and data
        validation_error, duplicates = validate_csv_data(data)
        if validation_error:
            os.remove(filepath)
            flash(f'Validation error: {validation_error}', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Filter out duplicates from main data
        valid_data = [row for row in data if not any(dup['row_data']['loan_ac_no'] == row['loan_ac_no'] for dup in duplicates)]

        # Save upload session
        save_upload_session(session_id, bank_id, category_id, filename, len(valid_data), len(duplicates))
        
        # Save duplicates if any
        if duplicates:
            save_duplicates(session_id, duplicates)

        # Store valid data in session
        session['upload_data'] = valid_data
        session['session_id'] = session_id
        
        return redirect(url_for('upload.preview_page', session_id=session_id))
        
    except Exception as e:
        flash(f'Upload failed: {str(e)}', 'error')
        return redirect(url_for('upload.upload_page'))

@upload_bp.route('/preview/<session_id>')
def preview_page(session_id):
    upload_session = get_upload_session(session_id)
    
    if not upload_session:
        flash('Upload session not found', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # Get data from session
    data = session.get('upload_data', [])
    
    return render_template('preview.html', 
                         data=data, 
                         upload_session=upload_session,
                         session_id=session_id)

@upload_bp.route('/submit/<session_id>', methods=['POST'])
def submit_data(session_id):
    try:
        # Get approved rows from form
        approved_rows = request.form.getlist('approved_rows')
        if not approved_rows:
            flash('No rows selected for approval', 'error')
            return redirect(url_for('upload.preview_page', session_id=session_id))
        
        upload_session = get_upload_session(session_id)
        
        if not upload_session:
            flash('Upload session not found', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Get original data from session
        original_data = session.get('upload_data', [])
        
        # Process updated data from form
        updated_data = {}
        for key, value in request.form.items():
            if key.startswith('customer_name_') or key.startswith('payout_amount_') or \
               key.startswith('processing_fee_') or key.startswith('insurance_amount_') or key.startswith('dsa_name_'):
                field_name, row_index = key.rsplit('_', 1)
                row_index = int(row_index)
                if row_index not in updated_data:
                    updated_data[row_index] = {}
                updated_data[row_index][field_name] = value.strip() if value else None
        
        # Insert approved rows with updated values
        inserted_count = insert_approved_data(upload_session, original_data, approved_rows, updated_data)
        
        # Update upload session
        update_upload_session(session_id, inserted_count)
        
        # Clean up
        session.pop('upload_data', None)
        session.pop('session_id', None)
        
        # Show appropriate message
        if inserted_count > 0:
            flash(f'Successfully imported {inserted_count} records!', 'success')
        else:
            flash('No records were imported. Please check the data and try again.', 'error')
        
        return redirect(url_for('upload.success_page', count=inserted_count, duplicates=upload_session['duplicate_count'], session_id=session_id))
        
    except Exception as e:
        flash(f'Submission failed: {str(e)}', 'error')
        return redirect(url_for('upload.preview_page', session_id=session_id))

@upload_bp.route('/success')
def success_page():
    count = int(request.args.get('count', 0))
    duplicate_count = int(request.args.get('duplicates', 0))
    session_id = request.args.get('session_id', '')
    return render_template('success.html', count=count, duplicate_count=duplicate_count, session_id=session_id)

def insert_approved_data(upload_session, original_data, approved_rows, updated_data):
    from .db import get_bank_name, check_duplicate_loan_ac_no, insert_mis_record
    
    bank_name = get_bank_name(upload_session['bank_id'])
    inserted_count = 0
    
    for row_index in approved_rows:
        try:
            row_index = int(row_index)
            row_data = original_data[row_index].copy()
            
            # Apply updates from form if any
            if row_index in updated_data:
                for field, value in updated_data[row_index].items():
                    if field == 'customer_name':
                        row_data['customer_name'] = value if value else row_data['customer_name']
                    elif field == 'payout_amount':
                        try:
                            row_data['payout_amount'] = float(value) if value else row_data['payout_amount']
                        except (ValueError, TypeError):
                            pass
                    elif field == 'processing_fee':
                        try:
                            row_data['processing_fee'] = float(value) if value else row_data['processing_fee']
                        except (ValueError, TypeError):
                            pass
                    elif field == 'insurance_amount':
                        try:
                            row_data['insurance_amount'] = float(value) if value else row_data['insurance_amount']
                        except (ValueError, TypeError):
                            pass
                    elif field == 'dsa_name':
                        row_data['dsa_name'] = value if value else row_data['dsa_name']
            
            # Check if loan_ac_no already exists
            if check_duplicate_loan_ac_no(row_data['loan_ac_no']):
                print(f"Skipping duplicate loan_ac_no: {row_data['loan_ac_no']}")
                continue
            
            # Insert record
            insert_mis_record(upload_session, bank_name, row_data)
            inserted_count += 1
            
        except Exception as e:
            print(f"Error inserting row {row_index}: {e}")
            continue
    
    return inserted_count