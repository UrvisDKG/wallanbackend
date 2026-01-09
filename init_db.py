import os
import mysql.connector
from dotenv import load_dotenv

# Get the directory of this script (e:/taxi/backend)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# .env is in e:/taxi/backend/backend/.env
ENV_PATH = os.path.join(SCRIPT_DIR, 'backend', '.env')
load_dotenv(dotenv_path=ENV_PATH)

# SQL file is in e:/taxi/backend/create_tables.sql
SQL_FILE = os.path.join(SCRIPT_DIR, 'create_tables.sql')

print(f"Loading env from: {ENV_PATH}")
print("Attempting to connect to Azure DB...")
print(f"Host: {os.getenv('DB_HOST')}")
print(f"User: {os.getenv('DB_USER')}")

try:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", 3306)),
        ssl_ca=os.getenv("DB_SSL_CA")
    )
    
    if conn.is_connected():
        print("✅ Successfully connected to Azure Database!")
        
        cursor = conn.cursor()
        
        # Read SQL file
        with open(SQL_FILE, 'r') as f:
            sql_script = f.read()
            
        # Execute statements
        statements = sql_script.split(';')
        
        for statement in statements:
            if statement.strip():
                try:
                    cursor.execute(statement)
                    print("Executed statement successfully.")
                except mysql.connector.Error as err:
                    print(f"Failed executing statement: {err}")
                    
        conn.commit()
        print("✅ Database tables initialized.")
        
        cursor.close()
        conn.close()

except mysql.connector.Error as err:
    print(f"❌ Connection failed: {err}")
