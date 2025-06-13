import os
from datetime import datetime

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

REQUIRED_HEADERS = [
    'loan_ac_no',
    'customer_name', 
    'disbursement_amount',
    'payout_amount'
]

OPTIONAL_HEADERS = [
    'agreement_no',
    'application_id',
    'disbursement_date',
    'business_month',
    'gross_loan_amount',
    'tenure',
    'roi',
    'commission_amount',
    'processing_fee',
    'insurance_amount',
    'branch_name',
    'state',
    'city',
    'region',
    'dsa_name'
]

def allowed_file(filename):
    """
    Check if uploaded file has allowed extension
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_csv_headers(headers):
    """
    Validate that all required headers are present
    """
    missing_headers = []
    
    for required_header in REQUIRED_HEADERS:
        if required_header not in headers:
            missing_headers.append(required_header)
    
    if missing_headers:
        return f"Missing required headers: {', '.join(missing_headers)}"
    
    return None

def format_currency(amount):
    """
    Format currency for display
    """
    if amount is None:
        return "0.00"
    try:
        return f"{float(amount):,.2f}"
    except (ValueError, TypeError):
        return "0.00"

def parse_date(date_str):
    """
    Parse date string to date object and return MySQL compatible format
    """
    if not date_str or str(date_str).strip() == '':
        return None
    
    try:
        # Try different date formats
        date_formats = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y']
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(str(date_str).strip(), fmt)
                # Return date in MySQL format (YYYY-MM-DD)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None
    except Exception:
        return None

def clean_numeric_value(value):
    """
    Clean and convert numeric values
    """
    if value is None or str(value).strip() == '':
        return None
    
    try:
        # Remove commas and convert to float
        cleaned = str(value).replace(',', '').strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None