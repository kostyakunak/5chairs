import asyncio
import logging
import subprocess
import sys

from database.db import init_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def setup_database():
    """Set up the database by running migrations and initializing tables"""
    try:
        # Initialize database connection
        logger.info("Initializing database connection...")
        await init_db()
        logger.info("Database connection initialized successfully.")
        
        # Close database connection
        await close_db()
        logger.info("Database connection closed.")
        
        return True
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        return False

def run_migrations():
    """Run Alembic migrations"""
    try:
        logger.info("Running database migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Migrations completed successfully.")
        logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration error: {e}")
        logger.error(f"Output: {e.stdout}")
        logger.error(f"Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return False

async def main():
    """Main function to set up the database"""
    logger.info("Starting database setup...")
    
    # Run Alembic migrations
    if not run_migrations():
        logger.error("Failed to run migrations. Exiting.")
        return
    
    # Initialize database
    if not await setup_database():
        logger.error("Failed to initialize database. Exiting.")
        return
    
    logger.info("Database setup completed successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)