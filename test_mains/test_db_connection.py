#!/usr/bin/env python3
"""
Simple PostgreSQL database connection test program.

This program tests the database connection using the same configuration
system as your main application to help isolate connection issues.
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the src directory to Python path so we can import our modules
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import our custom modules after adding to path
import econfig  # noqa: E402

def test_database_connection():
    """Test the PostgreSQL database connection."""
    print("🔧 Testing PostgreSQL Database Connection")
    print("=" * 50)
    
    # Load environment variables
    print("📋 Loading environment configuration...")
    econfig.load_env()
    
    # Get database URL
    database_url = econfig.get(econfig.DATABASE_URL)
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        print("   Make sure your .env file contains a DATABASE_URL setting")
        return False
    
    print(f"🔗 Database URL: {database_url}")
    
    # Mask password in URL for display purposes
    display_url = database_url
    if "@" in display_url and ":" in display_url:
        parts = display_url.split("@")
        if len(parts) == 2:
            auth_part = parts[0]
            if "://" in auth_part:
                protocol_user = auth_part.split("://")[1]
                if ":" in protocol_user:
                    masked = display_url.replace(protocol_user.split(":")[1].split("@")[0], "***")
                    display_url = masked
    
    print(f"📡 Connecting to: {display_url}")
    
    try:
        # Create engine
        print("🔨 Creating SQLAlchemy engine...")
        engine = create_engine(database_url, echo=False)
        
        # Test connection
        print("🔌 Testing database connection...")
        with engine.connect() as connection:
            # Execute a simple query
            result = connection.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print("✅ Connection successful!")
            print(f"📊 PostgreSQL version: {version}")
            
            # Test a simple table query (if any tables exist)
            print("\n🔍 Testing table access...")
            try:
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    LIMIT 5
                """))
                tables = result.fetchall()
                if tables:
                    print(f"📋 Found {len(tables)} table(s) in public schema:")
                    for table in tables:
                        print(f"   - {table[0]}")
                else:
                    print("📋 No tables found in public schema (this might be expected)")
            except SQLAlchemyError as e:
                print(f"⚠️  Could not query tables: {e}")
        
        # Clean up
        engine.dispose()
        print("\n✅ Database connection test completed successfully!")
        return True
        
    except SQLAlchemyError as e:
        print("❌ Database connection failed!")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
        print("\n🔍 Troubleshooting tips:")
        print("   1. Verify the database server is running")
        print("   2. Check if the host and port are correct")
        print("   3. Verify username and password are correct")
        print("   4. Ensure the database name exists")
        print("   5. Check firewall settings")
        return False
        
    except Exception as e:
        print("❌ Unexpected error!")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
        return False


def main():
    """Main function."""
    print("🚀 PostgreSQL Connection Test Utility")
    print("=" * 50)
    
    success = test_database_connection()
    
    if success:
        print("\n🎉 Test completed successfully!")
        print("   Your database connection is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Test failed!")
        print("   There appears to be an issue with your database connection.")
        sys.exit(1)


if __name__ == "__main__":
    main()