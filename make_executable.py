#!/usr/bin/env python3
import os
import stat
import sys

def make_executable(file_path):
    """Make a file executable"""
    try:
        # Get current permissions
        current_permissions = os.stat(file_path).st_mode
        
        # Add executable permissions for owner, group, and others
        new_permissions = current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        
        # Set new permissions
        os.chmod(file_path, new_permissions)
        
        print(f"Made {file_path} executable")
        return True
    except Exception as e:
        print(f"Error making {file_path} executable: {e}")
        return False

def main():
    """Make all Python scripts executable"""
    print("Making Python scripts executable...")
    
    # List of scripts to make executable
    scripts = [
        "run_bot.py",
        "setup_db.py",
        "test_bot.py",
        "run_meeting_service.py",
        "run_notification_service.py",
        "healthcheck.py",
        "generate_env.py",
        "run_tests.py"
    ]
    
    # Make each script executable
    success = True
    for script in scripts:
        if not make_executable(script):
            success = False
    
    if success:
        print("All scripts made executable successfully!")
        return 0
    else:
        print("Some scripts could not be made executable")
        return 1

if __name__ == "__main__":
    sys.exit(main())