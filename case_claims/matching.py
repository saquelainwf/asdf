from database.connection import get_db_connection
import re
from difflib import SequenceMatcher

def calculate_match_confidence(claim_data, mis_record):
    """
    Calculate match confidence between case claim and MIS record
    Returns confidence score (0.0 to 1.0)
    """
    total_score = 0
    max_score = 100
    
    # 1. Loan Account Number Match (if provided) - 100 points
    if claim_data.get('loan_ac_no') and mis_record.get('loan_ac_no'):
        if claim_data['loan_ac_no'].strip().upper() == mis_record['loan_ac_no'].strip().upper():
            return 1.0  # Perfect match
        else:
            return 0.0  # No match if loan_ac_no provided but doesn't match
    
    # 2. Customer Name Match - 40 points
    if claim_data.get('customer_name') and mis_record.get('customer_name'):
        name_score = calculate_name_similarity(
            claim_data['customer_name'], 
            mis_record['customer_name']
        )
        total_score += name_score * 40
    
    # 3. Bank Match - 20 points
    if claim_data.get('bank_name') and mis_record.get('bank_name'):
        if claim_data['bank_name'].strip().upper() == mis_record['bank_name'].strip().upper():
            total_score += 20
    
    # 4. Loan Amount Match - 30 points
    if claim_data.get('loan_amount') and mis_record.get('disbursement_amount'):
        amount_score = calculate_amount_similarity(
            float(claim_data['loan_amount']), 
            float(mis_record['disbursement_amount'])
        )
        total_score += amount_score * 30
    
    # 5. Date Match - 10 points
    if claim_data.get('application_date') and mis_record.get('disbursement_date'):
        date_score = calculate_date_similarity(
            claim_data['application_date'], 
            mis_record['disbursement_date']
        )
        total_score += date_score * 10
    
    return min(total_score / max_score, 1.0)

def calculate_name_similarity(name1, name2):
    """Calculate similarity between two names (0.0 to 1.0)"""
    if not name1 or not name2:
        return 0.0
    
    # Clean and normalize names
    name1_clean = clean_name(name1)
    name2_clean = clean_name(name2)
    
    # Exact match
    if name1_clean == name2_clean:
        return 1.0
    
    # Sequence matcher for fuzzy matching
    similarity = SequenceMatcher(None, name1_clean, name2_clean).ratio()
    
    # Check if all words in one name exist in another
    words1 = set(name1_clean.split())
    words2 = set(name2_clean.split())
    
    if len(words1) > 0 and len(words2) > 0:
        word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2))
        similarity = max(similarity, word_overlap)
    
    return similarity

def clean_name(name):
    """Clean and normalize name for comparison"""
    if not name:
        return ""
    
    # Convert to uppercase, remove extra spaces and special characters
    cleaned = re.sub(r'[^\w\s]', ' ', name.upper())
    cleaned = ' '.join(cleaned.split())
    
    # Remove common prefixes/suffixes
    prefixes = ['MR', 'MRS', 'MS', 'DR', 'PROF']
    suffixes = ['JR', 'SR', 'III', 'IV']
    
    words = cleaned.split()
    words = [w for w in words if w not in prefixes and w not in suffixes]
    
    return ' '.join(words)

def calculate_amount_similarity(amount1, amount2):
    """Calculate similarity between two amounts (0.0 to 1.0)"""
    if amount1 == 0 or amount2 == 0:
        return 0.0
    
    # Calculate percentage difference
    diff_percentage = abs(amount1 - amount2) / max(amount1, amount2)
    
    # Score based on difference
    if diff_percentage <= 0.05:  # Within 5%
        return 1.0
    elif diff_percentage <= 0.10:  # Within 10%
        return 0.7
    elif diff_percentage <= 0.20:  # Within 20%
        return 0.3
    else:
        return 0.0

def calculate_date_similarity(date1, date2):
    """Calculate similarity between two dates (0.0 to 1.0)"""
    try:
        from datetime import datetime, timedelta
        
        if isinstance(date1, str):
            date1 = datetime.strptime(date1, '%Y-%m-%d').date()
        if isinstance(date2, str):
            date2 = datetime.strptime(date2, '%Y-%m-%d').date()
        
        # Calculate difference in days
        diff_days = abs((date1 - date2).days)
        
        if diff_days <= 15:  # Within 15 days
            return 1.0
        elif diff_days <= 30:  # Within 30 days
            return 0.5
        else:
            return 0.0
            
    except:
        return 0.0

def find_potential_matches(claim_data):
    """
    Find potential MIS matches for a case claim
    Returns list of matches with confidence scores
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all MIS records for the same bank
    cursor.execute("""
        SELECT * FROM mis_data 
        WHERE bank_name = %s 
        ORDER BY date_created DESC
    """, (claim_data['bank_name'],))
    
    mis_records = cursor.fetchall()
    cursor.close()
    conn.close()
    
    matches = []
    
    for mis_record in mis_records:
        confidence = calculate_match_confidence(claim_data, mis_record)
        
        if confidence >= 0.6:  # Only include matches with 60%+ confidence
            matches.append({
                'mis_record': mis_record,
                'confidence': confidence,
                'match_criteria': get_match_criteria(claim_data, mis_record, confidence)
            })
    
    # Sort by confidence (highest first)
    matches.sort(key=lambda x: x['confidence'], reverse=True)
    
    return matches

def get_match_criteria(claim_data, mis_record, confidence):
    """Get details of what criteria matched"""
    criteria = []
    
    # Check loan account number
    if claim_data.get('loan_ac_no') and mis_record.get('loan_ac_no'):
        if claim_data['loan_ac_no'].strip().upper() == mis_record['loan_ac_no'].strip().upper():
            criteria.append("Loan Account Number")
    
    # Check name similarity
    if claim_data.get('customer_name') and mis_record.get('customer_name'):
        name_sim = calculate_name_similarity(claim_data['customer_name'], mis_record['customer_name'])
        if name_sim >= 0.8:
            criteria.append("Customer Name (High)")
        elif name_sim >= 0.5:
            criteria.append("Customer Name (Partial)")
    
    # Check bank
    if claim_data.get('bank_name') and mis_record.get('bank_name'):
        if claim_data['bank_name'].strip().upper() == mis_record['bank_name'].strip().upper():
            criteria.append("Bank Name")
    
    # Check amount
    if claim_data.get('loan_amount') and mis_record.get('disbursement_amount'):
        amount_sim = calculate_amount_similarity(
            float(claim_data['loan_amount']), 
            float(mis_record['disbursement_amount'])
        )
        if amount_sim >= 0.7:
            criteria.append("Loan Amount")
    
    return criteria

def run_auto_matching_for_claim(claim_id):
    """
    Run auto-matching for a specific claim
    Updates claim status based on best match confidence
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get claim data
    cursor.execute("SELECT * FROM case_claims WHERE id = %s", (claim_id,))
    claim = cursor.fetchone()
    
    if not claim:
        cursor.close()
        conn.close()
        return None
    
    # Find potential matches
    matches = find_potential_matches(claim)
    
    if matches:
        best_match = matches[0]
        confidence = best_match['confidence']
        
        # Update claim status based on confidence
        if confidence >= 0.9:
            new_status = 'matched'
        elif confidence >= 0.6:
            new_status = 'disputed'
        else:
            new_status = 'unmatched'
        
        cursor.execute("""
            UPDATE case_claims 
            SET status = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (new_status, claim_id))
        
        conn.commit()
        
        result = {
            'claim_id': claim_id,
            'status': new_status,
            'matches': matches[:5],  # Top 5 matches
            'best_confidence': confidence
        }
    else:
        # No matches found
        cursor.execute("""
            UPDATE case_claims 
            SET status = 'unmatched', updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (claim_id,))
        
        conn.commit()
        
        result = {
            'claim_id': claim_id,
            'status': 'unmatched',
            'matches': [],
            'best_confidence': 0.0
        }
    
    cursor.close()
    conn.close()
    
    return result