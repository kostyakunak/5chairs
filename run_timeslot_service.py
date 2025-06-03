#!/usr/bin/env python3
import asyncio
import logging
import signal
import sys
from datetime import datetime, time, timedelta

from database.db import init_db, close_db
from services.timeslot_service import timeslot_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/timeslot_service.log')
    ]
)

logger = logging.getLogger(__name__)

# Flag to track if the service should keep running
should_run = True

async def run_daily(hour=0, minute=0):
    """Run the timeslot service daily at the specified time"""
    global should_run
    
    logger.info("Timeslot service started")
    
    while should_run:
        # Get the current time
        now = datetime.now()
        
        # Calculate the next run time (today or tomorrow at the specified hour/minute)
        if now.hour > hour or (now.hour == hour and now.minute >= minute):
            # If we've already passed today's run time, schedule for tomorrow
            next_run = now.replace(day=now.day+1, hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # Schedule for today
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Calculate seconds until next run
        seconds_to_wait = (next_run - now).total_seconds()
        
        logger.info(f"Next timeslot update scheduled for {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Waiting for {seconds_to_wait / 3600:.2f} hours")
        
        # Wait until the scheduled time
        try:
            await asyncio.sleep(seconds_to_wait)
        except asyncio.CancelledError:
            logger.info("Task was cancelled")
            break
        
        if should_run:
            # Run the timeslot service update
            logger.info("Running scheduled timeslot update")
            result = await timeslot_service.update_available_dates()
            
            if result:
                logger.info("Timeslot update successful")
            else:
                logger.error("Timeslot update failed")
            
            # Run manual cleanup of old dates
            try:
                await timeslot_service.remove_old_available_dates()
                logger.info("Old available dates removed")
            except Exception as e:
                logger.error(f"Error removing old available dates: {e}")

async def run_now():
    """Run the timeslot service update immediately"""
    logger.info("Running immediate timeslot update")
    try:
        await init_db()
        result = await timeslot_service.update_available_dates()
        
        if result:
            logger.info("Timeslot update successful")
        else:
            logger.error("Timeslot update failed")
            
    except Exception as e:
        logger.error(f"Error in immediate update: {e}")
    finally:
        await close_db()

def handle_signal(signum, frame):
    """Handle termination signals"""
    global should_run
    logger.info(f"Received signal {signum}, shutting down...")
    should_run = False

async def main():
    """Main entry point"""
    global should_run
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # No command line arguments, run in scheduled mode
    if len(sys.argv) == 1:
        try:
            await init_db()
            # Run scheduled task at 00:30 every day
            await run_daily(hour=0, minute=30)
        finally:
            await close_db()
    
    # With --now argument, run immediately and exit
    elif len(sys.argv) == 2 and sys.argv[1] == '--now':
        await run_now()
    
    # Invalid arguments
    else:
        print("Usage: python run_timeslot_service.py [--now]")
        print("  --now: Run the update immediately and exit")
        print("  Without arguments: Run as a scheduled service")

if __name__ == "__main__":
    asyncio.run(main())