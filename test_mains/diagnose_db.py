#!/usr/bin/env python3
"""
Enhanced PostgreSQL diagnostic tool.

This program performs comprehensive testing of PostgreSQL connectivity
including network, authentication, and database-specific checks.
"""

import sys
import socket
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import psycopg

# Add the src directory to Python path so we can import our modules
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import our custom modules after adding to path
import econfig  # noqa: E402


def test_basic_connectivity(host, port):
    """Test basic TCP connectivity to the host and port."""
    print(f"🌐 Testing basic TCP connectivity to {host}:{port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✅ Basic TCP connection successful")
            return True
        else:
            print(f"❌ TCP connection failed (error code: {result})")
            return False
    except Exception as e:
        print(f"❌ TCP connection test failed: {e}")
        return False


def test_postgresql_handshake(host, port, database, username, password):
    """Test PostgreSQL-specific connection using psycopg directly."""
    print(f"🐘 Testing PostgreSQL handshake to {host}:{port}")
    
    try:
        # Try connecting with psycopg directly
        conn_str = f"host={host} port={port} dbname={database} user={username} password={password}"
        
        print("   Attempting direct psycopg connection...")
        with psycopg.connect(conn_str, connect_timeout=10) as conn:
            print("✅ Direct psycopg connection successful!")
            
            # Test basic query
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
                print(f"📊 PostgreSQL version: {version}")
                
                # Test database access
                cur.execute("SELECT current_database(), current_user")
                db_info = cur.fetchone()
                print(f"📋 Connected to database: {db_info[0]} as user: {db_info[1]}")
                
        return True
        
    except psycopg.OperationalError as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        
        # Analyze the specific error
        error_str = str(e).lower()
        if "authentication failed" in error_str:
            print("🔍 Diagnosis: Authentication issue - check username/password")
        elif "database" in error_str and "does not exist" in error_str:
            print("🔍 Diagnosis: Database does not exist")
        elif "connection refused" in error_str:
            print("🔍 Diagnosis: PostgreSQL server not running or not accepting connections")
        elif "timeout" in error_str:
            print("🔍 Diagnosis: Connection timeout - server may be overloaded")
        elif "ssl" in error_str:
            print("🔍 Diagnosis: SSL/TLS configuration issue")
        else:
            print("🔍 Diagnosis: Unknown PostgreSQL error")
            
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error during PostgreSQL test: {e}")
        return False


def test_sqlalchemy_connection(database_url):
    """Test SQLAlchemy connection with detailed error analysis."""
    print("🔧 Testing SQLAlchemy connection")
    
    try:
        # Parse the URL to get connection details
        if "://" in database_url:
            parts = database_url.split("://", 1)[1]  # Remove protocol
            if "@" in parts:
                auth_part, host_part = parts.split("@", 1)
                if ":" in auth_part:
                    username, password = auth_part.split(":", 1)
                else:
                    username, password = auth_part, ""
                    
                if "/" in host_part:
                    host_port, database = host_part.split("/", 1)
                    if ":" in host_port:
                        host, port = host_port.split(":", 1)
                        port = int(port)
                    else:
                        host, port = host_port, 5432
                else:
                    host, port, database = host_part, 5432, ""
        
        print(f"   Parsed connection: {username}@{host}:{port}/{database}")
        
        # Create engine with specific timeout settings
        engine = create_engine(
            database_url, 
            echo=False,
            pool_timeout=20,
            pool_recycle=3600,
            connect_args={
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000"
            }
        )
        
        print("   Testing SQLAlchemy engine connection...")
        with engine.connect() as connection:
            # Test basic query
            result = connection.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()[0]
            if test_result == 1:
                print("✅ SQLAlchemy connection successful!")
                
                # Additional diagnostics
                result = connection.execute(text("SELECT current_database(), current_user, inet_server_addr(), inet_server_port()"))
                info = result.fetchone()
                print(f"📋 Database: {info[0]}, User: {info[1]}, Server: {info[2]}:{info[3]}")
                
                return True
        
        engine.dispose()
        
    except SQLAlchemyError as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        
        # Provide specific guidance based on error type
        error_str = str(e).lower()
        if "operational" in error_str:
            if "authentication" in error_str:
                print("💡 Try: Check username and password in .env file")
            elif "database" in error_str and "exist" in error_str:
                print("💡 Try: Verify database name 'mountaineerdata' exists")
            elif "connection" in error_str and "refused" in error_str:
                print("💡 Try: Check if PostgreSQL server is running")
            else:
                print("💡 Try: Check network connectivity and server status")
        elif "timeout" in error_str:
            print("💡 Try: Server may be overloaded, try again later")
            
        return False
        
    except Exception as e:
        print(f"❌ Unexpected SQLAlchemy error: {e}")
        return False


def run_comprehensive_diagnostics():
    """Run all diagnostic tests."""
    print("🔍 PostgreSQL Connection Diagnostics")
    print("=" * 60)
    
    # Load environment
    print("📋 Loading configuration...")
    econfig.load_env()
    
    database_url = econfig.get(econfig.DATABASE_URL)
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return False
    
    print(f"🔗 Testing URL: {database_url}")
    
    # Parse connection details
    try:
        if "://" in database_url:
            parts = database_url.split("://", 1)[1]
            if "@" in parts:
                auth_part, host_part = parts.split("@", 1)
                if ":" in auth_part:
                    username, password = auth_part.split(":", 1)
                else:
                    username, password = auth_part, ""
                    
                if "/" in host_part:
                    host_port, database = host_part.split("/", 1)
                    if ":" in host_port:
                        host, port = host_port.split(":", 1)
                        port = int(port)
                    else:
                        host, port = host_port, 5432
                else:
                    host, port, database = host_part, 5432, ""
    except Exception as e:
        print(f"❌ Failed to parse database URL: {e}")
        return False
    
    print(f"🎯 Target: {username}@{host}:{port}/{database}")
    print("-" * 60)
    
    # Run tests in sequence
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Basic connectivity
    if test_basic_connectivity(host, port):
        tests_passed += 1
    print()
    
    # Test 2: PostgreSQL-specific connection
    if test_postgresql_handshake(host, port, database, username, password):
        tests_passed += 1
    print()
    
    # Test 3: SQLAlchemy connection
    if test_sqlalchemy_connection(database_url):
        tests_passed += 1
    print()
    
    # Summary
    print("=" * 60)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Your database connection should work.")
        return True
    elif tests_passed == 0:
        print("💥 All tests failed. Check your database server and configuration.")
        return False
    else:
        print("⚠️  Some tests failed. Review the errors above for specific issues.")
        return False


def main():
    """Main function."""
    success = run_comprehensive_diagnostics()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()