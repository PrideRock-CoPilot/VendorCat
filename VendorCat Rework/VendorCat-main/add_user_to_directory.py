#!/usr/bin/env python3
"""
Add a user to the employee directory
"""
import os
import sys
from pathlib import Path
from configparser import ConfigParser
from databricks import sql

# Read Databricks config
config_path = Path.home() / ".databrickscfg"
if not config_path.exists():
    print("❌ Error: ~/.databrickscfg not found")
    sys.exit(1)

config = ConfigParser()
config.read(config_path)

# Get profile info
profile = config["sso"]
hostname = profile.get("host", "").rstrip("/").split("https://")[-1]
token = profile.get("token", "")

if not hostname or not token:
    print("❌ Error: Missing host or token in databricks config")
    sys.exit(1)

warehouse_id = "955428814f623a0e"
login_id = "pliekhus@outlook.com"

# Create connection
try:
    connection = sql.connect(
        server_hostname=hostname,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        auth_type="pat",
        token=token,
    )
    cursor = connection.cursor()
    
    # Insert user into directory
    print(f"Adding user '{login_id}' to employee directory...")
    cursor.execute("""
        INSERT INTO a1_dlk.twvendor.app_user_directory 
        (employee_id, login_identifier, email, network_id, first_name, last_name, display_name, is_active, created_at, updated_at)
        VALUES 
        (?, ?, ?, ?, ?, ?, ?, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, ["EMP0-ADMIN", login_id, login_id, "pliekhus", "Admin", "User", "Admin User"])
    
    # Verify
    cursor.execute("""
        SELECT employee_id, login_identifier, email, display_name 
        FROM a1_dlk.twvendor.app_user_directory 
        WHERE login_identifier = ?
    """, [login_id])
    
    result = cursor.fetchone()
    if result:
        print("\n✅ User successfully added to directory!")
        print(f"   Employee ID: {result[0]}")
        print(f"   Login: {result[1]}")
        print(f"   Email: {result[2]}")
        print(f"   Display Name: {result[3]}")
        print("\n🔄 Try accessing the app again - you should now have access!")
    else:
        print("❌ User was not added (may already exist)")
    
    cursor.close()
    connection.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
