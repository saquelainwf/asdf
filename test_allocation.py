from database.connection import get_db_connection
from payouts.db import validate_allocation_percentages, calculate_allocation_amounts

def test_allocation_logic():
    """Test allocation validation and calculations"""
    
    print("Testing Allocation Logic...")
    
    # Test 1: Valid allocation percentages
    allocations1 = [
        {'percentage': 60.0, 'subconnector_id': 1, 'name': 'Sub A'},
        {'percentage': 40.0, 'subconnector_id': 2, 'name': 'Sub B'}
    ]
    
    is_valid = validate_allocation_percentages(allocations1)
    print(f"✅ Valid 100% allocation: {is_valid}")
    
    # Test 2: Invalid allocation percentages
    allocations2 = [
        {'percentage': 60.0, 'subconnector_id': 1, 'name': 'Sub A'},
        {'percentage': 50.0, 'subconnector_id': 2, 'name': 'Sub B'}
    ]
    
    is_valid2 = validate_allocation_percentages(allocations2)
    print(f"❌ Invalid 110% allocation: {is_valid2}")
    
    # Test 3: Amount calculations
    total_amount = 50000.0
    calculated = calculate_allocation_amounts(total_amount, allocations1)
    
    print(f"\n💰 Amount Calculations for ₹{total_amount}:")
    for calc in calculated:
        print(f"  {calc['name']}: {calc['percentage']}% = ₹{calc['amount']}")
    
    total_calc = sum(c['amount'] for c in calculated)
    print(f"  Total calculated: ₹{total_calc}")
    print(f"  Matches original: {abs(total_calc - total_amount) < 0.01}")

def test_database_functions():
    """Test database connectivity for allocation functions"""
    
    print("\nTesting Database Functions...")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Test subconnectors query
        cursor.execute("SELECT COUNT(*) as count FROM subconnectors WHERE is_active = TRUE")
        sub_count = cursor.fetchone()['count']
        print(f"✅ Active subconnectors: {sub_count}")
        
        # Test payout_allocations table
        cursor.execute("SELECT COUNT(*) as count FROM payout_allocations")
        alloc_count = cursor.fetchone()['count']
        print(f"✅ Existing allocations: {alloc_count}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

def test_json_handling():
    """Test JSON allocation data handling"""
    
    print("\nTesting JSON Allocation Data...")
    
    allocation_data = {
        'strategy': 'split',
        'total_amount': 50000.0,
        'allocations': [
            {'subconnector_id': 1, 'name': 'ABC Services', 'percentage': 60.0, 'amount': 30000.0},
            {'subconnector_id': 2, 'name': 'XYZ Trading', 'percentage': 40.0, 'amount': 20000.0}
        ],
        'allocation_reason': 'Tax optimization split'
    }
    
    # Test JSON serialization
    import json
    json_str = json.dumps(allocation_data)
    print(f"✅ JSON serialization: {len(json_str)} characters")
    
    # Test JSON deserialization
    parsed_data = json.loads(json_str)
    print(f"✅ JSON deserialization: {parsed_data['strategy']}")
    print(f"✅ Allocations count: {len(parsed_data['allocations'])}")

if __name__ == "__main__":
    test_allocation_logic()
    test_database_functions()
    test_json_handling()
    print("\n🎉 All allocation tests completed!")