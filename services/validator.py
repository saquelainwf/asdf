from database.connection import get_db_connection

def validate_csv_data(data):
    """
    Validate CSV data for business rules
    """
    if not data:
        return "No data found in file"
    
    errors = []
    loan_ac_nos = set()
    
    for i, row in enumerate(data):
        row_errors = []
        
        # Check required fields
        if not row.get('loan_ac_no'):
            row_errors.append("loan_ac_no is required")
        elif row['loan_ac_no'] in loan_ac_nos:
            row_errors.append(f"Duplicate loan_ac_no within file: {row['loan_ac_no']}")
        else:
            loan_ac_nos.add(row['loan_ac_no'])
            
            # Check if loan_ac_no exists in database
            if check_loan_ac_no_exists(row['loan_ac_no']):
                row_errors.append(f"loan_ac_no already exists in database: {row['loan_ac_no']}")
        
        if not row.get('customer_name'):
            row_errors.append("customer_name is required")
        
        if row.get('disbursement_amount') is None:
            row_errors.append("disbursement_amount is required")
        elif row['disbursement_amount'] <= 0:
            row_errors.append("disbursement_amount must be greater than 0")
        
        if row.get('payout_amount') is None:
            row_errors.append("payout_amount is required")
        elif row['payout_amount'] < 0:
            row_errors.append("payout_amount cannot be negative")
        
        # Add row errors to main errors list
        if row_errors:
            errors.append(f"Row {i+1}: {'; '.join(row_errors)}")
    
    # Return first few errors (don't overwhelm user)
    if errors:
        return '; '.join(errors[:5]) + (f" ... and {len(errors)-5} more errors" if len(errors) > 5 else "")
    
    return None

def check_loan_ac_no_exists(loan_ac_no):
    """
    Check if loan_ac_no already exists in database
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM mis_data WHERE loan_ac_no = %s", (loan_ac_no,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return result is not None
        
    except Exception as e:
        print(f"Error checking loan_ac_no: {e}")
        return False