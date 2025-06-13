from database.connection import test_connection, get_db_connection

def test_database():
    print("Testing database connection...")
    
    # Test basic connection
    if test_connection():
        print("✅ Database connection successful!")
    else:
        print("❌ Database connection failed!")
        return False
    
    # Test table existence
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if all tables exist
        tables = ['users', 'banks', 'categories', 'mis_data', 'upload_sessions']
        
        for table in tables:
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            result = cursor.fetchone()
            if result:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
                return False
        
        # Test sample data
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"✅ Users table has {user_count} records")
        
        cursor.execute("SELECT COUNT(*) FROM banks")
        bank_count = cursor.fetchone()[0]
        print(f"✅ Banks table has {bank_count} records")
        
        cursor.execute("SELECT COUNT(*) FROM categories")
        category_count = cursor.fetchone()[0]
        print(f"✅ Categories table has {category_count} records")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Database setup is complete and working!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    test_database()