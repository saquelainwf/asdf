from database.connection import get_db_connection
from utils.helpers import parse_date
import json

def get_banks_categories():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id, bank_name FROM banks ORDER BY bank_name")
    banks = cursor.fetchall()
    
    cursor.execute("SELECT id, category_name FROM categories ORDER BY id")
    categories = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return banks, categories

def save_upload_session(session_id, bank_id, category_id, filename, total_rows, duplicate_count):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO upload_sessions (session_id, bank_id, category_id, filename, total_rows, duplicate_count)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (session_id, bank_id, category_id, filename, total_rows, duplicate_count))
    
    conn.commit()
    cursor.close()
    conn.close()

def save_duplicates(session_id, duplicates):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for dup in duplicates:
        cursor.execute("""
            INSERT INTO duplicate_records (session_id, row_data, duplicate_type)
            VALUES (%s, %s, %s)
        """, (session_id, json.dumps(dup['row_data']), dup['duplicate_type']))
    
    conn.commit()
    cursor.close()
    conn.close()

def get_upload_session(session_id):
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
    
    return upload_session

def get_bank_name(bank_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT bank_name FROM banks WHERE id = %s", (bank_id,))
    bank = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return bank['bank_name'] if bank else None

def check_duplicate_loan_ac_no(loan_ac_no):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM mis_data WHERE loan_ac_no = %s", (loan_ac_no,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return result is not None

def insert_mis_record(upload_session, bank_name, row_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Prepare dates
    disbursement_date = parse_date(row_data.get('disbursement_date')) if row_data.get('disbursement_date') else None
    business_month = parse_date(row_data.get('business_month')) if row_data.get('business_month') else None
    
    cursor.execute("""
        INSERT INTO mis_data (
            bank_id, bank_name, category_id, loan_ac_no, application_id, 
            customer_name, disbursement_date, business_month, disbursement_amount,
            gross_loan_amount, tenure, roi, loan_type, payout_amount, 
            processing_fee, insurance_amount, branch_name, state, city, 
            region, dsa_name, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        upload_session['bank_id'], bank_name, upload_session['category_id'],
        row_data['loan_ac_no'], row_data.get('application_id'),
        row_data['customer_name'], disbursement_date, business_month,
        row_data['disbursement_amount'], row_data.get('gross_loan_amount'), 
        row_data.get('tenure'), row_data.get('roi'), row_data.get('loan_type'),
        row_data['payout_amount'], row_data.get('processing_fee'), 
        row_data.get('insurance_amount'), row_data.get('branch_name'), 
        row_data.get('state'), row_data.get('city'), row_data.get('region'), 
        row_data.get('dsa_name'), 1
    ))
    
    conn.commit()
    cursor.close()
    conn.close()

def update_upload_session(session_id, approved_rows):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE upload_sessions 
        SET approved_rows = %s, status = 'COMPLETED'
        WHERE session_id = %s
    """, (approved_rows, session_id))
    
    conn.commit()
    cursor.close()
    conn.close()