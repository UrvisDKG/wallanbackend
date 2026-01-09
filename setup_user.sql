
-- Run this in your MySQL Workbench or Command Line Client
-- It creates a dedicated user for the app to avoid 'root' permission issues.

CREATE DATABASE IF NOT EXISTS defects;

-- Create a user 'app_user' with password 'App123!'
-- We use % to allow connection from localhost, 127.0.0.1, etc.
CREATE USER IF NOT EXISTS 'app_user'@'%' IDENTIFIED BY 'App123!';

-- Grant specific permissions
GRANT ALL PRIVILEGES ON defects.* TO 'app_user'@'%';

-- In case you are using an older MySQL client/connector
ALTER USER 'app_user'@'%' IDENTIFIED WITH mysql_native_password BY 'App123!';

FLUSH PRIVILEGES;
