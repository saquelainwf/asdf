from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import uuid
from datetime import datetime
import csv
import pandas as pd
from database.connection import get_db_connection
from utils.helpers import allowed_file, validate_csv_headers
from services.csv_parser import parse_csv_file
from services.validator import validate_csv_data, check_loan_ac_no_exists

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Routes
@app.route('/')
def index():
    # Get dashboard statistics
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get total records
    cursor.execute("SELECT COUNT(*) as total FROM mis_data")
    total_records = cursor.fetchone()['total']
    
    # Get total by bank
    cursor.execute("""
        SELECT b.bank_name, COUNT(m.id) as count 
        FROM banks b 
        LEFT JOIN mis_data m ON b.id = m.bank_id 
        GROUP BY b.id, b.bank_name 
        ORDER BY count DESC
    """)
    bank_stats = cursor.fetchall()
    
    # Get recent uploads
    cursor.execute("""
        SELECT us.*, b.bank_name, c.category_name 
        FROM upload_sessions us
        JOIN banks b ON us.bank_id = b.id
        JOIN categories c ON us.category_id = c.id
        ORDER BY us.created_at DESC
        LIMIT 5
    """)
    recent_uploads = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', 
                         total_records=total_records,
                         bank_stats=bank_stats,
                         recent_uploads=recent_uploads)

@app.route('/upload')
def upload_page():
    # Get banks and categories from database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id, bank_name FROM banks ORDER BY bank_name")
    banks = cursor.fetchall()
    
    cursor.execute("SELECT id, category_name FROM categories ORDER BY id")
    categories = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('upload.html', banks=banks, categories=categories)

@app.route('/upload', methods=['POST'])
def handle_upload():
    try:
        # Get form data
        bank_id = request.form.get('bank_id')
        category_id = request.form.get('category_id')
        
        if not bank_id or not category_id:
            flash('Please select bank and category', 'error')
            return redirect(url_for('upload_page'))
        
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('upload_page'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('upload_page'))
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload CSV or Excel file.', 'error')
            return redirect(url_for('upload_page'))
        
        # Generate session ID and save file
        session_id = str(uuid.uuid4())
        filename = f"{session_id}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Parse and validate CSV
        data, error = parse_csv_file(filepath)
        if error:
            os.remove(filepath)  # Clean up file
            flash(f'File parsing error: {error}', 'error')
            return redirect(url_for('upload_page'))
        
        # Validate headers and data
        validation_error = validate_csv_data(data)
        if validation_error:
            os.remove(filepath)  # Clean up file
            flash(f'Validation error: {validation_error}', 'error')
            return redirect(url_for('upload_page'))
        
        # Save upload session
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO upload_sessions (session_id, bank_id, category_id, filename, total_rows)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_id, bank_id, category_id, filename, len(data)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Store data in session for preview
        session['upload_data'] = data
        session['session_id'] = session_id
        
        return redirect(url_for('preview_page', session_id=session_id))
        
    except Exception as e:
        flash(f'Upload failed: {str(e)}', 'error')
        return redirect(url_for('upload_page'))

@app.route('/preview/<session_id>')
def preview_page(session_id):
    # Get upload session data
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT us.*, b.bank_name, c.category_name 
        FROM upload_sessions us
        JOIN banks b ON us.bank_id = b.id
        JOIN categories c ON us.category_id = c.id
        WHERE us.session_id = %s
    """, (session_id,))
    
    upload_session = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not upload_session:
        flash('Upload session not found', 'error')
        return redirect(url_for('upload_page'))
    
    # Get data from session
    data = session.get('upload_data', [])
    
    return render_template('preview.html', 
                         data=data, 
                         upload_session=upload_session,
                         session_id=session_id)

@app.route('/submit/<session_id>', methods=['POST'])
def submit_data(session_id):
    try:
        # Get approved rows from form
        approved_rows = request.form.getlist('approved_rows')
        if not approved_rows:
            flash('No rows selected for approval', 'error')
            return redirect(url_for('preview_page', session_id=session_id))
        
        # Get upload session
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM upload_sessions WHERE session_id = %s", (session_id,))
        upload_session = cursor.fetchone()
        
        if not upload_session:
            flash('Upload session not found', 'error')
            return redirect(url_for('upload_page'))
        
        # Get original data from session
        original_data = session.get('upload_data', [])
        
        # Get bank name
        cursor.execute("SELECT bank_name FROM banks WHERE id = %s", (upload_session['bank_id'],))
        bank = cursor.fetchone()
        
        # Process updated data from form
        updated_data = {}
        for key, value in request.form.items():
            if key.startswith('customer_name_') or key.startswith('payout_amount_') or \
               key.startswith('commission_amount_') or key.startswith('dsa_name_'):
                field_name, row_index = key.rsplit('_', 1)
                row_index = int(row_index)
                if row_index not in updated_data:
                    updated_data[row_index] = {}
                updated_data[row_index][field_name] = value.strip() if value else None
        
        # Insert approved rows with updated values
        inserted_count = 0
        error_count = 0
        for row_index in approved_rows:
            try:
                row_index = int(row_index)
                row_data = original_data[row_index].copy()  # Start with original data
                
                # Apply updates from form if any
                if row_index in updated_data:
                    for field, value in updated_data[row_index].items():
                        if field == 'customer_name':
                            row_data['customer_name'] = value if value else row_data['customer_name']
                        elif field == 'payout_amount':
                            try:
                                row_data['payout_amount'] = float(value) if value else row_data['payout_amount']
                            except (ValueError, TypeError):
                                pass  # Keep original value if conversion fails
                        elif field == 'commission_amount':
                            try:
                                row_data['commission_amount'] = float(value) if value else row_data['commission_amount']
                            except (ValueError, TypeError):
                                pass  # Keep original value if conversion fails
                        elif field == 'dsa_name':
                            row_data['dsa_name'] = value if value else row_data['dsa_name']
                
                # Check if loan_ac_no already exists
                cursor.execute("SELECT id FROM mis_data WHERE loan_ac_no = %s", (row_data['loan_ac_no'],))
                if cursor.fetchone():
                    print(f"Skipping duplicate loan_ac_no: {row_data['loan_ac_no']}")
                    continue  # Skip duplicate
                
                # Prepare data for insertion
                disbursement_date = row_data.get('disbursement_date')
                if disbursement_date and str(disbursement_date).strip():
                    # Parse date properly
                    from utils.helpers import parse_date
                    disbursement_date = parse_date(disbursement_date)
                else:
                    disbursement_date = None
                
                # Insert row with updated values
                cursor.execute("""
                    INSERT INTO mis_data (
                        bank_id, bank_name, category_id, loan_ac_no, agreement_no,
                        application_id, customer_name, disbursement_date, disbursement_amount,
                        gross_loan_amount, tenure, roi, payout_amount, commission_amount, 
                        branch_name, state, city, region, dsa_name, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    upload_session['bank_id'], bank['bank_name'], upload_session['category_id'],
                    row_data['loan_ac_no'], row_data.get('agreement_no'), row_data.get('application_id'),
                    row_data['customer_name'], disbursement_date, row_data['disbursement_amount'],
                    row_data.get('gross_loan_amount'), row_data.get('tenure'), row_data.get('roi'),
                    row_data['payout_amount'], row_data.get('commission_amount'), 
                    row_data.get('branch_name'), row_data.get('state'), row_data.get('city'),
                    row_data.get('region'), row_data.get('dsa_name'), 1  # Admin user ID
                ))
                
                inserted_count += 1
                print(f"Successfully inserted row {row_index}: {row_data['loan_ac_no']} with updated values")
                
            except Exception as e:
                error_count += 1
                print(f"Error inserting row {row_index}: {e}")
                continue
        
        # Update upload session
        cursor.execute("""
            UPDATE upload_sessions 
            SET approved_rows = %s, status = 'COMPLETED'
            WHERE session_id = %s
        """, (inserted_count, session_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Clean up
        session.pop('upload_data', None)
        session.pop('session_id', None)
        
        # Show appropriate message
        if inserted_count > 0:
            if error_count > 0:
                flash(f'Successfully imported {inserted_count} records! {error_count} records had errors and were skipped.', 'warning')
            else:
                flash(f'Successfully imported {inserted_count} records!', 'success')
        else:
            flash('No records were imported. Please check the data and try again.', 'error')
        
        return redirect(url_for('success_page', count=inserted_count))
        
    except Exception as e:
        flash(f'Submission failed: {str(e)}', 'error')
        return redirect(url_for('preview_page', session_id=session_id))

@app.route('/success')
def success_page():
    count = request.args.get('count', 0)
    return render_template('success.html', count=count)

@app.route('/view-data')
def view_data():
    """View all MIS data for verification"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT m.*, b.bank_name, c.category_name 
        FROM mis_data m
        JOIN banks b ON m.bank_id = b.id
        JOIN categories c ON m.category_id = c.id
        ORDER BY m.date_created DESC
        LIMIT 50
    """)
    
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('view_data.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)