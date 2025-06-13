from database.connection import get_db_connection

def validate_csv_data(data):
    if not data:
        return None, []
    
    valid_data = []
    duplicate_data = []
    loan_ac_nos = set()
    
    for i, row in enumerate(data):
        row_errors = []
        
        # Check required fields
        if not row.get('loan_ac_no'):
            row_errors.append("loan_ac_no is required")
        elif row['loan_ac_no'] in loan_ac_nos:
            duplicate_data.append({
                'row_index': i,
                'row_data': row,
                'duplicate_type': 'within_file'
            })
            continue
        else:
            loan_ac_nos.add(row['loan_ac_no'])
            
            # Check if exists in database
            if check_loan_ac_no_exists(row['loan_ac_no']):
                duplicate_data.append({
                    'row_index': i,
                    'row_data': row,
                    'duplicate_type': 'in_database'
                })
                continue
        
        # Validate other required fields
        if not row.get('customer_name'):
            row_errors.append("customer_name is required")
        if row.get('disbursement_amount') is None or row['disbursement_amount'] <= 0:
            row_errors.append("disbursement_amount is required and must be > 0")
        if row.get('payout_amount') is None or row['payout_amount'] < 0:
            row_errors.append("payout_amount is required and cannot be negative")
        
        if row_errors:
            return f"Row {i+1}: {'; '.join(row_errors)}", []
        
        valid_data.append(row)
    
    return None, duplicate_data


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