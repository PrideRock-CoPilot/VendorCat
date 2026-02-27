%sql
-- Add admin user to employee directory
INSERT INTO a1_dlk.twvendor.app_user_directory 
(employee_id, login_identifier, email, network_id, first_name, last_name, display_name, is_active, created_at, updated_at)
VALUES 
('EMP0-ADMIN', 'pliekhus@outlook.com', 'pliekhus@outlook.com', 'pliekhus', 'Admin', 'User', 'Admin User', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

SELECT * FROM a1_dlk.twvendor.app_user_directory WHERE login_identifier = 'pliekhus@outlook.com';
