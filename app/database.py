
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# --- Mock Database Implementation ---
class MockCursor:
    def __init__(self, connection):
        self.connection = connection
        self.lastrowid = 1
        self._rows = []

    def execute(self, query, params=None):
        query = query.strip().upper()
        print(f"MOCK DB EXEC: {query} | Params: {params}")

        if "INSERT INTO USERS" in query:
             # Simulate creating a user
             self.lastrowid = 123  # Mock User ID
        elif "SELECT ID FROM USERS" in query:
             # Simulate finding a user
             self._rows = None      # Use this to simulate "New User" -> Insert path
        elif "INSERT INTO INSPECTIONS" in query:
             self.lastrowid = 555 # Mock Inspection ID
        elif "CREATE TABLE" in query or "ALTER TABLE" in query:
             pass 
        elif "INSERT INTO INSPECTION_IMAGES" in query:
             pass
        elif "INSERT INTO OTPS" in query:
             # Mock OTP storage
             # Params: (phone, otp, expires, otp, expires)
             phone = params[0]
             val = params[1]
             # Store in the class-level dict for persistence across connections
             MockConnection._mock_otps[phone] = val
        elif "SELECT OTP" in query and "FROM OTPS" in query:
             # Params: (phone,)
             phone = params[0]
             if phone in MockConnection._mock_otps:
                 self._rows = (MockConnection._mock_otps[phone],)
             else:
                 self._rows = None
        elif "DELETE FROM OTPS" in query:
             phone = params[0]
             if phone in MockConnection._mock_otps:
                 del MockConnection._mock_otps[phone]

    def fetchone(self):
        return self._rows

    def close(self):
        pass

class MockConnection:
    _mock_otps = {} # Shared class-level storage for Mock OTPs
    
    def cursor(self):
        return MockCursor(self)
    
    def commit(self):
        print("MOCK DB COMMIT")
        
    def close(self):
        pass
# ------------------------------------

def get_connection():
    # helper to get env or config
    def get_config(key, default=None):
        val = os.getenv(key)
        if val is None:
            try:
                import config
                val = getattr(config, key, default)
            except ImportError:
                val = default
        
        # Clean value (remove quotes and whitespace)
        if isinstance(val, str):
            val = val.strip().strip('"').strip("'")
        return val

    host = get_config("DB_HOST")
    if not host:
        print("DEBUG: No DB_HOST found, using MOCK database.")
        return MockConnection()

    try:
        user = get_config("DB_USER")
        password = get_config("DB_PASSWORD")
        database = get_config("DB_NAME")
        port_raw = get_config("DB_PORT", 3306)
        
        try:
            port = int(port_raw)
        except (ValueError, TypeError):
            port = 3306

        print(f"DEBUG: Attempting REAL DB connection to {host}...", flush=True)
        
        # Azure MySQL Flexible Server often requires SSL.
        # We try to connect. If it fails, we log why.
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            use_pure=True,  # Better compatibility for some environments
            ssl_disabled=False # Try to use SSL if available
            # If your server requires a specific CA file, it must be provided in DB_SSL_CA
            # ssl_ca=get_config("DB_SSL_CA")
        )
        
        if conn.is_connected():
            print(f"✅ CONNECTED to Real MySQL DB: {host}", flush=True)
            return conn
        else:
            raise Exception("Connection technically succeeded but is_connected() is False")

    except Exception as err:
        print(f"❌ Database connection error: {err}", flush=True)
        print("Fallback: Using MOCK database to keep app running.", flush=True)
        return MockConnection()
