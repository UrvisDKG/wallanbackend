
-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'driver'
);

-- 2. Inspections Table
CREATE TABLE IF NOT EXISTS inspections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'started', -- 'started', 'completed'
    car_model VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. Inspection Images (Evidence) Table
CREATE TABLE IF NOT EXISTS inspection_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inspection_id INT NOT NULL,
    image_type VARCHAR(50) NOT NULL, -- 'front', 'back', 'damage1', etc.
    image_path VARCHAR(255) NOT NULL, -- URL or local path
    similarity FLOAT DEFAULT 0.0,
    label VARCHAR(20), -- 'good', 'defective'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE
);

-- 4. Submissions (Analysis Results) Table
-- Stores the JSON result from Gemini analysis
CREATE TABLE IF NOT EXISTS submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    car_model VARCHAR(50),
    analysis_json JSON, -- Stores the full array of Gemini results
    comparison_text TEXT, -- Stores the generated textual comparison
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
