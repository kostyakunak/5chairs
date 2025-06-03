import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Any

from database.db import pool, get_active_timeslots
from database.models import TimeSlot

logger = logging.getLogger(__name__)

class TimeslotService:
    """Service for managing date-based time slots with a rolling 2-week window"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def generate_available_dates(self) -> List[Dict[str, Any]]:
        """
        Generate actual calendar dates for the available time slots
        Returns a list of available date-time slots for the next 2 weeks
        """
        # Get today's date
        today = date.today()
        
        # Calculate the end date (2 weeks from today)
        end_date = today + timedelta(days=14)
        
        # Get all active time slots
        time_slots = await get_active_timeslots()
        
        if not time_slots:
            self.logger.warning("No active time slots found")
            return []
        
        # Map day names to day numbers (0 = Monday, 6 = Sunday)
        day_map = {
            'Monday': 0,
            'Tuesday': 1,
            'Wednesday': 2,
            'Thursday': 3,
            'Friday': 4,
            'Saturday': 5,
            'Sunday': 6
        }
        
        # Generate dates for each time slot
        date_slots = []
        
        current_date = today
        while current_date <= end_date:
            # Get the day of the week as an integer (0 = Monday, 6 = Sunday)
            current_weekday = current_date.weekday()
            
            # Find all time slots for this day of the week
            for slot in time_slots:
                slot_day = slot['day_of_week']
                if day_map.get(slot_day) == current_weekday:
                    date_slots.append({
                        'date': current_date,
                        'time_slot_id': slot['id'],
                        'day_of_week': slot_day,
                        'start_time': slot['start_time'],
                        'end_time': slot['end_time']
                    })
            
            # Move to the next day
            current_date += timedelta(days=1)
        
        return date_slots
    
    async def update_available_dates(self) -> bool:
        """
        Update available dates in the database
        - Add new available dates within the 2-week window
        - Remove dates that are no longer within the window
        """
        try:
            # Generate available dates
            available_dates = await self.generate_available_dates()
            
            if not available_dates:
                self.logger.warning("No available dates generated")
                return False
            
            # Get today's date
            today = date.today()
            
            async with pool.acquire() as conn:
                # Start a transaction
                async with conn.transaction():
                    # Remove old dates that are in the past or beyond the 2-week window
                    await conn.execute('''
                        DELETE FROM available_dates
                        WHERE date < $1 OR date > $2
                    ''', today, today + timedelta(days=14))
                    
                    # Insert new dates
                    for date_slot in available_dates:
                        await conn.execute('''
                            INSERT INTO available_dates
                            (date, time_slot_id, created_at)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (date, time_slot_id) DO NOTHING
                        ''', date_slot['date'], date_slot['time_slot_id'], datetime.now())
            
            self.logger.info(f"Successfully updated {len(available_dates)} available dates")
            return True
        except Exception as e:
            self.logger.error(f"Error updating available dates: {e}")
            return False
    
    async def get_available_dates(self, filter_by: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Get available dates for meetings
        
        Args:
            filter_by: Optional dictionary with filter criteria
                       (e.g., {'city_id': 1, 'time_slot_id': 2})
        
        Returns:
            List of available dates with time slot information
        """
        try:
            query = '''
                SELECT ad.id, ad.date, ad.time_slot_id, ad.is_available,
                       ts.day_of_week, ts.start_time, ts.end_time
                FROM available_dates ad
                JOIN time_slots ts ON ad.time_slot_id = ts.id
                WHERE ad.date >= $1 AND ad.date <= $2 AND ad.is_available = true
            '''
            
            params = [date.today(), date.today() + timedelta(days=14)]
            
            # Add additional filters if provided
            if filter_by:
                i = 3
                for key, value in filter_by.items():
                    query += f" AND {key} = ${i}"
                    params.append(value)
                    i += 1
            
            query += " ORDER BY ad.date, ts.start_time"
            
            async with pool.acquire() as conn:
                result = await conn.fetch(query, *params)
                
                return [dict(row) for row in result]
                
        except Exception as e:
            self.logger.error(f"Error getting available dates: {e}")
            return []
    
    async def mark_date_unavailable(self, date_id: int) -> bool:
        """Mark a specific date as unavailable"""
        try:
            async with pool.acquire() as conn:
                await conn.execute('''
                    UPDATE available_dates
                    SET is_available = false, updated_at = $2
                    WHERE id = $1
                ''', date_id, datetime.now())
                return True
        except Exception as e:
            self.logger.error(f"Error marking date unavailable: {e}")
            return False
    
    async def mark_date_available(self, date_id: int) -> bool:
        """Mark a specific date as available"""
        try:
            async with pool.acquire() as conn:
                await conn.execute('''
                    UPDATE available_dates
                    SET is_available = true, updated_at = $2
                    WHERE id = $1
                ''', date_id, datetime.now())
                return True
        except Exception as e:
            self.logger.error(f"Error marking date available: {e}")
            return False
    
    async def remove_old_available_dates(self):
        """Remove available dates that are in the past"""
        try:
            async with pool.acquire() as conn:
                await conn.execute('''
                    DELETE FROM available_dates
                    WHERE date < CURRENT_DATE
                ''')
                self.logger.info("Successfully removed old available dates")
                return True
        except Exception as e:
            self.logger.error(f"Error removing old available dates: {e}")
            return False
            
    async def run_daily_update(self):
        """Run daily update to generate new available dates and remove old ones"""
        self.logger.info("Running daily update of available dates")
        result = await self.update_available_dates()
        if result:
            await self.remove_old_available_dates()
        return result


# Create singleton instance
timeslot_service = TimeslotService()