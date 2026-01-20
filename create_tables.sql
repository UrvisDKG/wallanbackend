
-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'driver'
);

-- 2. OTPS Table
CREATE TABLE IF NOT EXISTS otps (
    phone VARCHAR(20) PRIMARY KEY,
    otp VARCHAR(6),
    expires_at TIMESTAMP
);

-- 3. Inspections Table
CREATE TABLE IF NOT EXISTS inspections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY, -- Can handle Date.now() if passed as id, or auto-inc
    user_id VARCHAR(255), -- Changed to VARCHAR to match app logic and allow flexibility
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'started',
    car_model VARCHAR(50)
);

-- 4. Inspection Images Table
CREATE TABLE IF NOT EXISTS inspection_images (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    inspection_id BIGINT NOT NULL,
    image_type VARCHAR(50) NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    similarity FLOAT DEFAULT 0.0,
    label VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Submissions Table
CREATE TABLE IF NOT EXISTS submissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255),
    car_model VARCHAR(50),
    analysis_json JSON,
    comparison_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
