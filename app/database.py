
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

    try:
        host = get_config("DB_HOST")
        user = get_config("DB_USER")
        password = get_config("DB_PASSWORD")
        database = get_config("DB_NAME")
        port_raw = get_config("DB_PORT", 3306)
        
        try:
            port = int(port_raw)
        except (ValueError, TypeError):
            port = 3306

        print(f"DEBUG: Connecting to {host} as {user}...")
        
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            # connection_timeout=10, # Standard param
            # Azure flexible server often requires SSL. 
            # If your server requires it, you might need a CA cert. 
            # For testing, we can try without or add ssl_disabled=False if needed.
        )
        return conn
    except Exception as err:
        print(f"Database connection error: {err}")
        print("Providing MOCK database fallback to prevent app crash.")
        return MockConnection()
