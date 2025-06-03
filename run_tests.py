#!/usr/bin/env python3
import asyncio
import logging
import sys
import subprocess
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"tests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def run_test(test_script):
    """Run a test script and return the result"""
    try:
        logger.info(f"Running {test_script}...")
        result = subprocess.run(
            [sys.executable, test_script],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"{test_script} passed!")
            return True
        else:
            logger.error(f"{test_script} failed with exit code {result.returncode}")
            logger.error(f"Output: {result.stdout}")
            logger.error(f"Error: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error running {test_script}: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("Starting tests...")
    
    # List of test scripts to run
    test_scripts = [
        "healthcheck.py",
        "test_bot.py"
    ]
    
    # Run each test
    results = {}
    for test_script in test_scripts:
        results[test_script] = await run_test(test_script)
    
    # Print summary
    logger.info("Test results summary:")
    all_passed = True
    for test_script, passed in results.items():
        logger.info(f"{test_script}: {'PASSED' if passed else 'FAILED'}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("All tests passed!")
        return 0
    else:
        logger.error("Some tests failed")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error during tests: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)