#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def run_command(command, description):
    """Run a command and log the result"""
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Success: {description}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error: {description} failed")
        logger.error(f"Command: {' '.join(command)}")
        logger.error(f"Output: {e.stdout}")
        logger.error(f"Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error: {description} failed - {e}")
        return False

def create_virtual_environment():
    """Create a virtual environment"""
    if os.path.exists("venv"):
        logger.info("Virtual environment already exists")
        return True
    
    return run_command(
        [sys.executable, "-m", "venv", "venv"],
        "Creating virtual environment"
    )

def install_dependencies():
    """Install dependencies"""
    # Determine the pip command based on the platform
    if sys.platform == "win32":
        pip_cmd = os.path.join("venv", "Scripts", "pip")
    else:
        pip_cmd = os.path.join("venv", "bin", "pip")
    
    # Upgrade pip
    if not run_command(
        [pip_cmd, "install", "--upgrade", "pip"],
        "Upgrading pip"
    ):
        return False
    
    # Install dependencies
    return run_command(
        [pip_cmd, "install", "-r", "requirements.txt"],
        "Installing dependencies"
    )

def make_scripts_executable():
    """Make scripts executable"""
    if sys.platform == "win32":
        logger.info("Skipping making scripts executable on Windows")
        return True
    
    # Determine the python command based on the platform
    if sys.platform == "win32":
        python_cmd = os.path.join("venv", "Scripts", "python")
    else:
        python_cmd = os.path.join("venv", "bin", "python")
    
    return run_command(
        [python_cmd, "make_executable.py"],
        "Making scripts executable"
    )

def generate_env_file():
    """Generate .env file"""
    # Determine the python command based on the platform
    if sys.platform == "win32":
        python_cmd = os.path.join("venv", "Scripts", "python")
    else:
        python_cmd = os.path.join("venv", "bin", "python")
    
    return run_command(
        [python_cmd, "generate_env.py"],
        "Generating .env file"
    )

def setup_database():
    """Set up the database"""
    # Determine the python command based on the platform
    if sys.platform == "win32":
        python_cmd = os.path.join("venv", "Scripts", "python")
    else:
        python_cmd = os.path.join("venv", "bin", "python")
    
    return run_command(
        [python_cmd, "setup_db.py"],
        "Setting up database"
    )

def run_tests():
    """Run tests"""
    # Determine the python command based on the platform
    if sys.platform == "win32":
        python_cmd = os.path.join("venv", "Scripts", "python")
    else:
        python_cmd = os.path.join("venv", "bin", "python")
    
    return run_command(
        [python_cmd, "run_tests.py"],
        "Running tests"
    )

def main():
    """Main function"""
    logger.info("Initializing 5 Chairs Telegram Bot project...")
    
    # Create virtual environment
    if not create_virtual_environment():
        logger.error("Failed to create virtual environment")
        return 1
    
    # Install dependencies
    if not install_dependencies():
        logger.error("Failed to install dependencies")
        return 1
    
    # Make scripts executable
    if not make_scripts_executable():
        logger.error("Failed to make scripts executable")
        return 1
    
    # Generate .env file
    if not generate_env_file():
        logger.error("Failed to generate .env file")
        return 1
    
    # Set up database
    if not setup_database():
        logger.error("Failed to set up database")
        return 1
    
    # Run tests
    if not run_tests():
        logger.warning("Some tests failed")
    
    logger.info("Project initialization completed successfully!")
    logger.info("You can now run the bot with: python run_bot.py")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Project initialization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)