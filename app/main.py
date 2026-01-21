# Force redeploy v1.7.0
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Annotated
import os
import cv2
import numpy as np
import base64
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from azure.storage.blob import BlobServiceClient, ContentSettings

from app.database import get_connection
from app.utils.compare import compare_images as structural_compare
from app.utils.otp import generate_otp, verify_otp

load_dotenv()

app = FastAPI()

@app.post("/auth/request-otp")
async def request_otp_endpoint(phone: str = Form(...)):
    if phone != "0123456789":
        raise HTTPException(status_code=400, detail="Only the authorized test number 0123456789 is allowed for now.")
    
    otp = generate_otp(phone)
    return {"message": "OTP sent", "otp": otp}

@app.post("/auth/verify-otp")
async def verify_otp_endpoint(phone: str = Form(...), otp: str = Form(...), name: str = Form(None)):
    if phone != "0123456789":
        raise HTTPException(status_code=403, detail="Unauthorized number.")
        
    is_valid = verify_otp(phone, otp)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Get or Create User
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT AUTO_INCREMENT PRIMARY KEY, 
                phone VARCHAR(255), 
                name VARCHAR(255),
                email VARCHAR(255),
                isVerified TINYINT DEFAULT 0,
                createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        try: cur.execute("ALTER TABLE users MODIFY COLUMN id BIGINT AUTO_INCREMENT")
        except: pass
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
        result = cur.fetchone()
        
        if result:
            user_id = result[0]
            # Update verification status, name and updatedAt
            if name:
                cur.execute("UPDATE users SET isVerified = 1, name = %s, updatedAt = CURRENT_TIMESTAMP WHERE id = %s", (name, user_id))
            else:
                cur.execute("UPDATE users SET isVerified = 1, updatedAt = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
        else:
            # Create user
            if name:
                cur.execute("INSERT INTO users (phone, name, isVerified) VALUES (%s, %s, 1)", (phone, name))
            else:
                cur.execute("INSERT INTO users (phone, isVerified) VALUES (%s, 1)", (phone,))
            user_id = cur.lastrowid
        conn.commit()
    except Exception as e:
        print(f"Database error during login: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()
    
    return {"message": "Login successful", "user_id": user_id}

@app.post("/auth/demo-login")
async def demo_login_endpoint():
    demo_phone = "1234567890"
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("CREATE TABLE IF NOT EXISTS users (id BIGINT AUTO_INCREMENT PRIMARY KEY, phone VARCHAR(255))")
        cur.execute("SELECT id FROM users WHERE phone = %s", (demo_phone,))
        result = cur.fetchone()
        
        if result:
            user_id = result[0]
        else:
            cur.execute("INSERT INTO users (phone) VALUES (%s)", (demo_phone,))
            conn.commit()
            user_id = cur.lastrowid
    except Exception as e:
        print(f"Database error during demo login: {e}")
        # Fallback if DB not ready
        user_id = 999 
    finally:
         cur.close()
         conn.close()
    
    return {"message": "Demo login successful", "user_id": user_id}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure Configuration
# Ensure we can find config.py in parent directory
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")

# Try loading from config if not in env
if not AZURE_CONNECTION_STRING or not AZURE_CONTAINER_NAME:
    try:
        import config
        if not AZURE_CONNECTION_STRING:
            AZURE_CONNECTION_STRING = getattr(config, "AZURE_CONNECTION_STRING", None)
            print("DEBUG: Loaded AZURE_CONNECTION_STRING from config.py")
        if not AZURE_CONTAINER_NAME:
            AZURE_CONTAINER_NAME = getattr(config, "AZURE_CONTAINER_NAME", "uploads")
            print(f"DEBUG: Loaded AZURE_CONTAINER_NAME from config.py: {AZURE_CONTAINER_NAME}")
    except ImportError as e:
        print(f"DEBUG: Config module not found: {e}")

if not AZURE_CONTAINER_NAME:
    AZURE_CONTAINER_NAME = "uploads" # Default fallback

if not AZURE_CONNECTION_STRING:
    print("WARNING: AZURE_CONNECTION_STRING not found. Azure uploads will fail.")

# Initialize Blob Service Client (Lazy loaded or global)
try:
    if AZURE_CONNECTION_STRING:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        print(f"DEBUG: Azure Blob Service Initialized. Account: {blob_service_client.account_name}")
    else:
        blob_service_client = None
        print("DEBUG: Blob Service Client is None (No Connection String)")
except Exception as e:
    print(f"Failed to initialize Azure Blob Service: {e}")
    blob_service_client = None

FILE_TYPE_LIST = [
    "inspections", "profiles", "documents", "others",
    "front", "back", "left", "right", "roof", "interior",
    "damage1", "damage2", "damage3",
    "png", "jpg", "jpeg" # Allow extensions as types if frontend sends them
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(BASE_DIR)
FILES_PATH = os.path.join(BACKEND_ROOT, "files")
os.makedirs(FILES_PATH, exist_ok=True)

app.mount("/files", StaticFiles(directory=FILES_PATH), name="files")

def upload_file_to_azure(file_type: str, file: UploadFile) -> str:
    if not blob_service_client:
        return None

    if file_type not in FILE_TYPE_LIST:
        raise HTTPException(status_code=400, detail="Invalid file type")

    safe_name = Path(file.filename or "unknown").name
    filename = f"{int(time.time()*1000)}_{safe_name}"

    file_bytes = file.file.read()

    local_dir = Path(FILES_PATH) / file_type
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / filename
    local_path.write_bytes(file_bytes)

    blob_path = f"{file_type}/{filename}"
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
    blob_client = container_client.get_blob_client(blob_path)

    blob_client.upload_blob(
        file_bytes,
        overwrite=True,
        content_settings=ContentSettings(
            content_type=file.content_type or "application/octet-stream"
        )
    )

    return filename

@app.post("/upload")
async def upload_file_endpoint(
    request: Request,
    fileType: Annotated[str, Form()],
    file: UploadFile = File(...)
):
    filename = await asyncio.to_thread(upload_file_to_azure, fileType, file)

    if not filename:
        raise HTTPException(status_code=500, detail="Upload failed")

    url = (
        f"https://{blob_service_client.account_name}.blob.core.windows.net/"
        f"{AZURE_CONTAINER_NAME}/{fileType}/{filename}"
    )

    return JSONResponse(
        status_code=201,
        content={
            "status": "success",
            "fileName": filename,
            "url": url
        }
    )

@app.post("/upload/{file_type}")
async def upload_file_with_path(
    file_type: str,
    file: UploadFile = File(...)
):
    # wrapper for api.ts which sends fileType in path
    # We can reuse the logic.
    return await upload_file_endpoint(None, file_type, file)


@app.post("/inspection/start")
async def start_inspection(user_id: str = Form(...)):
    conn = get_connection()
    cur = conn.cursor()
    
    # Needs 'inspections' table
    try:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        cur.execute("CREATE TABLE IF NOT EXISTS inspections (id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        try: cur.execute("ALTER TABLE inspections MODIFY COLUMN id BIGINT AUTO_INCREMENT")
        except: pass 
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        cur.execute("INSERT INTO inspections (user_id) VALUES (%s)", (user_id,))
        conn.commit()
        inspection_id = cur.lastrowid
    except Exception as e:
        print(f"DB Error starting inspection: {e}")
        # Fallback ID - using seconds fits in INT, but we use BIGINT anyway
        inspection_id = int(time.time())
    finally:
        cur.close()
        conn.close()
        
    return {"inspection_id": inspection_id}

@app.post("/submissions")
async def submit_photos(submission: Dict[str, Any]):
    print(f"Received submission: {submission}")
    import json
    
    user_id = submission.get("userId")
    raw_car_model = submission.get("carModel") or "Unknown Vehicle"
    analysis_results = submission.get("analysisResults") or []
    
    # Split car model into brand and model if possible
    brand = "Unknown"
    model = raw_car_model
    if " " in raw_car_model:
        parts = raw_car_model.split(" ", 1)
        brand = parts[0]
        model = parts[1]
    
    # Derive Summary and Score from AI results
    summary_parts = []
    total_score = 0
    damage_count = 0
    
    severity_map = {"none": 0, "low": 25, "medium": 50, "high": 75, "critical": 100}
    
    for res in analysis_results:
        summary_parts.append(f"{res.get('damageType', 'N/A')}: {res.get('description', '')}")
        sev = res.get('severity', 'none').lower()
        score = severity_map.get(sev, 0)
        total_score += score
        if res.get('hasDamage'):
            damage_count += 1
            
    final_summary = " | ".join(summary_parts)
    avg_score = total_score / len(analysis_results) if analysis_results else 0
    
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Update/Create Car record
        cur.execute("SELECT id FROM cars WHERE brand = %s AND model = %s AND userId = %s", (brand, model, user_id))
        car_row = cur.fetchone()
        if car_row:
            car_id = car_row[0]
        else:
            cur.execute("INSERT INTO cars (userId, brand, model, carType) VALUES (%s, %s, %s, %s)", (user_id, brand, model, "Sedan"))
            car_id = cur.lastrowid
            
        # 2. Create entry in 'reports' table
        # id, carId, reportStage, damageScore, summary, createdAt
        cur.execute("SELECT COUNT(*) FROM reports WHERE carId = %s", (car_id,))
        stage = cur.fetchone()[0] + 1
        
        cur.execute(
            "INSERT INTO reports (carId, reportStage, damageScore, summary) VALUES (%s, %s, %s, %s)",
            (car_id, stage, avg_score, final_summary)
        )
        report_id = cur.lastrowid
        
        # 3. Save to backup 'submissions' table
        cur.execute(
            "INSERT INTO submissions (user_id, car_model, analysis_json) VALUES (%s, %s, %s)",
            (str(user_id), raw_car_model, json.dumps(analysis_results))
        )
        
        conn.commit()
        return {"status": "success", "submission_id": cur.lastrowid, "report_id": report_id, "car_id": car_id}
    except Exception as e:
        print(f"Error saving submission: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.delete("/photos/{photo_id}")
async def delete_photo(photo_id: str):
    print(f"Requested delete photo: {photo_id}")
    # implementation specific
    return {"status": "success"}

UPLOAD_BASE = os.path.join(FILES_PATH, "inspections")
IDEAL_PATH = os.path.join(FILES_PATH, "ideal.png")
os.makedirs(UPLOAD_BASE, exist_ok=True)

@app.post("/inspection/upload-image")
async def upload_image(
    inspection_id: str = Form(...),
    image_type: str = Form(...),
    file: UploadFile = File(...)
):
    print("UPLOAD HIT FROM APP")
    print(f"DEBUG: START upload_image. inspection_id={inspection_id}, image_type={image_type}")
    
    import mimetypes

    # Validate file type
    ALLOWED_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in ALLOWED_TYPES:
        print(f"ERROR: Invalid content type {file.content_type}")
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file.content_type}. Allowed: {ALLOWED_TYPES}")

    clean_image_type = os.path.splitext(image_type)[0]
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    
    # Generate unique filename
    if len(clean_image_type) < 5 and clean_image_type.lower() in ["png", "jpg", "jpeg", "img"]:
         final_filename = f"{clean_image_type}_{int(time.time()*1000)}{ext}"
    else:
         final_filename = f"{clean_image_type}{ext}"
         
    # Read content properly for Async
    content = await file.read()

    # Use /tmp on Render (ephemeral), local files/ directory otherwise
    is_render = os.getenv("RENDER") is not None
    base_path = "/tmp/inspections" if is_render else UPLOAD_BASE
    
    try:
        folder = Path(base_path) / str(inspection_id)
        folder.mkdir(parents=True, exist_ok=True)
        local_image_path = folder / final_filename
        local_image_path.write_bytes(content)
        print(f"DEBUG: Saved local file {local_image_path}")
    except Exception as e:
        print(f"WARNING: Could not save local file: {e}. Continuing with Azure upload only.")
        local_image_path = None


    azure_url = None
    if blob_service_client:
        try:
            # Ensure container exists
            container_name = AZURE_CONTAINER_NAME
            print(f"DEBUG: Using Azure Container: '{container_name}'")
            
            # --- ASYNC AZURE LOGIC START ---
            # We need to handle the fact that we might have initialized a SYNC client globally.
            # To respect the user's request for AWAIT, we should ideally use the AsyncClient.
            # However, changing the global client might break other things if they rely on it?
            # Actually, this is the only main usage.
            
            # For now, to be safe and robust without rewriting global init which might need lifecycle events:
            # We will use run_in_executor to make the SYNC call non-blocking, effectively "awaiting" it.
            # This satisfies "function must be async" requirement of the user while validly using the existing sync client.
            
            container_client = blob_service_client.get_container_client(container_name)
            if not container_client.exists():
                print(f"DEBUG: Container {container_name} not found. Creating...")
                container_client.create_container()

            blob_name = f"inspections/{inspection_id}/{final_filename}"
            blob_client = container_client.get_blob_client(blob_name)
            
            print(f"DEBUG: Uploading blob to: {blob_name}")
            
            content_type = file.content_type or mimetypes.guess_type(final_filename)[0] or "image/jpeg"
            
            # Run blocking upload in threadpool
            import asyncio
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob_client.upload_blob(
                    content, 
                    overwrite=True, 
                    content_settings=ContentSettings(content_type=content_type)
                )
            )
            
            azure_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"
            print(f"DEBUG: Azure Upload SUCCESS: {azure_url}")
            # --- ASYNC AZURE LOGIC END ---
            
        except Exception as e:
            print(f"ERROR: Azure Upload Failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("ERROR: Blob Service Client is NONE. Chech AZURE_CONNECTION_STRING")
    
    # If Azure failed, use a placeholder or local URL? 
    # For now, if Azure fails, we still need a URL for the DB. 
    # Let's fallback to the generic generic file path if azure_url is None
    if not azure_url:
        azure_url = f"/files/inspections/{inspection_id}/{final_filename}"

    similarity = 0.0
    label = "good"
    if local_image_path and os.path.exists(IDEAL_PATH) and os.path.exists(str(local_image_path)):
        similarity = structural_compare(IDEAL_PATH, str(local_image_path))
        label = "defective" if similarity < 0.9 else "good"

    conn = get_connection()
    cur = conn.cursor()
    
    # Ensure table exists
    try:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        cur.execute("CREATE TABLE IF NOT EXISTS inspections (id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inspection_images (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                inspection_id BIGINT,
                image_type VARCHAR(50),
                image_path VARCHAR(500),
                similarity FLOAT,
                label VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            cur.execute("ALTER TABLE inspections MODIFY COLUMN id BIGINT AUTO_INCREMENT")
            cur.execute("ALTER TABLE inspection_images MODIFY COLUMN id BIGINT AUTO_INCREMENT")
            cur.execute("ALTER TABLE inspection_images MODIFY COLUMN inspection_id BIGINT")
        except:
            pass
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    except:
        pass

    
    cur.execute(
        """
        INSERT INTO inspection_images
        (inspection_id, image_type, image_path, similarity, label)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (inspection_id, clean_image_type, azure_url, similarity, label)
    )

    # --- NEW: Populate Legacy reportphotos table ---
    try:
        # Find angle_id from angleCode
        cur.execute("SELECT id FROM carphotoangles WHERE LOWER(angleCode) = %s", (clean_image_type.lower(),))
        angle_row = cur.fetchone()
        angle_id = angle_row[0] if angle_row else 1 # Fallback to first angle
        
        cur.execute(
            """
            INSERT INTO reportphotos (reportId, angleId, photoUrl, aiAnalysis)
            VALUES (%s, %s, %s, %s)
            """,
            (inspection_id, angle_id, azure_url, label)
        )
    except Exception as e:
        print(f"Legacy Sync Error (reportphotos): {e}")
    # -----------------------------------------------

    conn.commit()
    cur.close()
    conn.close()

    return {
        "image_type": clean_image_type,
        "similarity": similarity,
        "label": label,
        "url": azure_url
    }

@app.post("/compare-images")
async def compare_images_endpoint(
    old_image: UploadFile = File(...),
    new_image: UploadFile = File(...)
):
    old_bytes = await old_image.read()
    new_bytes = await new_image.read()

    old_img = cv2.imdecode(np.frombuffer(old_bytes, np.uint8), cv2.IMREAD_COLOR)
    new_img = cv2.imdecode(np.frombuffer(new_bytes, np.uint8), cv2.IMREAD_COLOR)

    if old_img is None or new_img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    if old_img.shape != new_img.shape:
        new_img = cv2.resize(new_img, (old_img.shape[1], old_img.shape[0]))

    diff = cv2.absdiff(old_img, new_img)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

    mse = float(np.mean((old_img - new_img) ** 2))
    diff_percentage = float((np.sum(thresh > 0) / thresh.size) * 100)

    highlight = new_img.copy()
    highlight[thresh > 0] = [0, 0, 255]

    _, encoded = cv2.imencode(".jpg", highlight)
    diff_base64 = base64.b64encode(encoded.tobytes()).decode()

    return {
        "mse": mse,
        "diff_percentage": diff_percentage,
        "diff_image_base64": diff_base64
    }

@app.get("/db-status")
async def db_status():
    conn = get_connection()
    status = {
        "connection_mode": "MOCK" if hasattr(conn, 'is_mock') else "REAL",
        "tables": {},
        "error": None
    }
    
    if status["connection_mode"] == "REAL":
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SHOW TABLES")
            table_rows = cur.fetchall()
            table_names = [list(row.values())[0] for row in table_rows]
            
            for table in table_names:
                cur.execute(f"DESCRIBE {table}")
                status["tables"][table] = cur.fetchall()
            cur.close()
        except Exception as e:
            status["error"] = str(e)
    
    conn.close()
    return status

@app.get("/db-view")
async def db_view():
    conn = get_connection()
    data = {}
    if hasattr(conn, 'is_mock'):
        return {"mode": "MOCK", "data": "No real data in mock mode"}
    
    try:
        cur = conn.cursor()
        for table in ["users", "inspections", "inspection_images", "submissions", "otps"]:
            try:
                cur.execute(f"SELECT * FROM {table} ORDER BY 1 DESC LIMIT 5")
                data[table] = cur.fetchall()
            except:
                data[table] = "Table error or empty"
        cur.close()
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()
    return data

@app.get("/")
def root():
    return {"status": "backend running", "version": "1.7.0"}