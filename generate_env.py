#!/usr/bin/env python3
import os
import sys
import shutil

def generate_env_file():
    """Generate a .env file from .env.example if it doesn't exist"""
    env_example_path = ".env.example"
    env_path = ".env"
    
    # Check if .env.example exists
    if not os.path.exists(env_example_path):
        print(f"Error: {env_example_path} not found.")
        return False
    
    # Check if .env already exists
    if os.path.exists(env_path):
        overwrite = input(f"{env_path} already exists. Overwrite? (y/n): ")
        if overwrite.lower() != 'y':
            print("Operation cancelled.")
            return False
    
    # Copy .env.example to .env
    shutil.copy2(env_example_path, env_path)
    print(f"Created {env_path} from {env_example_path}")
    print("Please edit the .env file with your actual configuration values.")
    
    return True

def main():
    """Main function"""
    print("Generating .env file...")
    if generate_env_file():
        print("Done!")
        return 0
    else:
        print("Failed to generate .env file.")
        return 1

if __name__ == "__main__":
    sys.exit(main())