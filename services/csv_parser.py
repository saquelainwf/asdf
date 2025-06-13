import pandas as pd
import csv
from utils.helpers import validate_csv_headers, parse_date, clean_numeric_value

def parse_csv_file(filepath):
    """
    Parse CSV file and return data with validation
    """
    try:
        # Read file based on extension
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        elif filepath.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        else:
            return None, "Unsupported file format"
        
        # Check if file is empty
        if df.empty:
            return None, "File is empty"
        
        # Get headers (column names)
        headers = df.columns.tolist()
        
        # Validate headers
        header_error = validate_csv_headers(headers)
        if header_error:
            return None, header_error
        
        # Convert DataFrame to list of dictionaries
        data = []
        for index, row in df.iterrows():
            row_data = {}
            
            # Required fields
            row_data['loan_ac_no'] = str(row.get('loan_ac_no', '')).strip()
            row_data['customer_name'] = str(row.get('customer_name', '')).strip()
            row_data['disbursement_amount'] = clean_numeric_value(row.get('disbursement_amount'))
            row_data['payout_amount'] = clean_numeric_value(row.get('payout_amount'))
            
            # Optional fields
            row_data['agreement_no'] = str(row.get('agreement_no', '')).strip() if pd.notna(row.get('agreement_no')) else None
            row_data['disbursement_date'] = parse_date(row.get('disbursement_date'))
            row_data['commission_amount'] = clean_numeric_value(row.get('commission_amount'))
            row_data['branch_name'] = str(row.get('branch_name', '')).strip() if pd.notna(row.get('branch_name')) else None
            row_data['state'] = str(row.get('state', '')).strip() if pd.notna(row.get('state')) else None
            row_data['region'] = str(row.get('region', '')).strip() if pd.notna(row.get('region')) else None
            row_data['dsa_name'] = str(row.get('dsa_name', '')).strip() if pd.notna(row.get('dsa_name')) else None
            
            # Add row index for tracking
            row_data['row_index'] = index
            
            data.append(row_data)
        
        return data, None
        
    except Exception as e:
        return None, f"Error parsing file: {str(e)}"