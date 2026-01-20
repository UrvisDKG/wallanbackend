import random
import time
from app.database import get_connection

def generate_otp(phone: str):
    otp = random.randint(1000, 9999)
    print(f"OTP for {phone}: {otp}", flush=True)
    
    # Store in Database for production safety (handles multi-worker/restart)
    print(f"DEBUG: Storing OTP for {phone} in database", flush=True)
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS otps (
                phone VARCHAR(20) PRIMARY KEY,
                otp VARCHAR(6),
                expires_at TIMESTAMP
            )
        """)
        
        # Calculate expiry (e.g., 5 minutes from now)
        # Using simple integer timestamp or DB expression
        expires_at = int(time.time()) + 300 # 5 minutes
        
        # Insert or Update (MySQL syntax)
        cur.execute("""
            INSERT INTO otps (phone, otp, expires_at) 
            VALUES (%s, %s, FROM_UNIXTIME(%s))
            ON DUPLICATE KEY UPDATE otp = %s, expires_at = FROM_UNIXTIME(%s)
        """, (phone, str(otp), expires_at, str(otp), expires_at))
        
        conn.commit()
    except Exception as e:
        print(f"Error storing OTP in DB: {e}")
    finally:
        cur.close()
        conn.close()
        
    return otp

def verify_otp(phone: str, otp: any):
    conn = get_connection()
    cur = conn.cursor()
    is_valid = False
    
    try:
        # Check database
        print(f"DEBUG: Verifying OTP for {phone} from database", flush=True)
        cur.execute("SELECT otp FROM otps WHERE phone = %s AND expires_at > CURRENT_TIMESTAMP", (phone,))
        result = cur.fetchone()
        
        if result:
            db_otp = result[0]
            print(f"DEBUG: Found OTP {db_otp} in DB for {phone}", flush=True)
            if str(db_otp) == str(otp):
                is_valid = True
                # Optional: Delete OTP after successful verification to prevent reuse
                cur.execute("DELETE FROM otps WHERE phone = %s", (phone,))
                conn.commit()
                print(f"DEBUG: OTP verified successfully for {phone}", flush=True)
        else:
            print(f"DEBUG: No valid OTP found in DB for {phone}", flush=True)
    except Exception as e:
        print(f"Error verifying OTP from DB: {e}")
    finally:
        cur.close()
        conn.close()
        
    return is_valid
