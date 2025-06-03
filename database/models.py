from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean,
    Date, Time, DateTime, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """User model for end users of the system"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    name = Column(String(255), nullable=False)
    surname = Column(String(255), nullable=False)
    age = Column(Integer)
    registration_date = Column(DateTime, default=func.now())
    status = Column(String(50), default="registered")  # registered, applied, approved, rejected
    
    # Relationships
    answers = relationship("UserAnswer", back_populates="user", cascade="all, delete-orphan")
    application = relationship("Application", back_populates="user", uselist=False, cascade="all, delete-orphan")
    meeting_memberships = relationship("MeetingMember", back_populates="user", cascade="all, delete-orphan")

class City(Base):
    """City model for available meeting locations"""
    __tablename__ = "cities"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    active = Column(Boolean, default=True)
    
    # Relationships
    meetings = relationship("Meeting", back_populates="city")

class TimeSlot(Base):
    """Time slot model for available meeting times"""
    __tablename__ = "time_slots"
    
    id = Column(Integer, primary_key=True)
    day_of_week = Column(String(20), nullable=False)  # Monday, Tuesday, etc.
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Unique constraint for day and times
    __table_args__ = (UniqueConstraint('day_of_week', 'start_time', 'end_time', name='_day_time_range_uc'),)
    
    # Relationships
    meetings = relationship("Meeting", secondary="meeting_time_slots", back_populates="timeslots")

class Question(Base):
    """Question model for application questions"""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    active = Column(Boolean, default=True)
    display_order = Column(Integer, nullable=False)
    
    # Relationships
    answers = relationship("UserAnswer", back_populates="question", cascade="all, delete-orphan")

class UserAnswer(Base):
    """User answer model for storing responses to questions"""
    __tablename__ = "user_answers"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer = Column(Text, nullable=False)
    answered_at = Column(DateTime, default=func.now())
    
    # Unique constraint for user and question
    __table_args__ = (UniqueConstraint('user_id', 'question_id', name='_user_question_uc'),)
    
    # Relationships
    user = relationship("User", back_populates="answers")
    question = relationship("Question", back_populates="answers")

class Application(Base):
    """Application model for user applications"""
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected, inactive, assigned, completed
    
    # Relationships
    user = relationship("User", back_populates="application")
    timeslot = relationship("TimeSlot")

class Admin(Base):
    """Admin model for system administrators"""
    __tablename__ = "admins"
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    name = Column(String(255), nullable=False)
    added_at = Column(DateTime, default=func.now())
    is_superadmin = Column(Boolean, default=False)
    
    # Relationships
    created_meetings = relationship("Meeting", back_populates="created_by_admin", foreign_keys="Meeting.created_by")
    added_members = relationship("MeetingMember", back_populates="added_by_admin", foreign_keys="MeetingMember.added_by")

class Meeting(Base):
    """Meeting model for meeting groups"""
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    meeting_date = Column(Date, nullable=False)
    meeting_time = Column(Time, nullable=False)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    venue = Column(String(255), nullable=False)
    venue_address = Column(String(255))
    status = Column(String(50), default="planned")  # planned, confirmed, completed, cancelled
    created_by = Column(BigInteger, ForeignKey("admins.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    city = relationship("City", back_populates="meetings")
    created_by_admin = relationship("Admin", back_populates="created_meetings", foreign_keys=[created_by])
    members = relationship("MeetingMember", back_populates="meeting", cascade="all, delete-orphan")
    timeslots = relationship("TimeSlot", secondary="meeting_time_slots", back_populates="meetings")

class MeetingMember(Base):
    """Meeting member model for users in meetings"""
    __tablename__ = "meeting_members"
    
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    added_at = Column(DateTime, default=func.now())
    added_by = Column(BigInteger, ForeignKey("admins.id"), nullable=True)
    
    # Unique constraint for meeting and user
    __table_args__ = (UniqueConstraint('meeting_id', 'user_id', name='_meeting_user_uc'),)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="members")
    user = relationship("User", back_populates="meeting_memberships")
    added_by_admin = relationship("Admin", back_populates="added_members", foreign_keys=[added_by])

class Venue(Base):
    """Venue model for permanent meeting locations (restaurants, cafes, etc.)"""
    __tablename__ = "venues"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    city = relationship("City", backref="venues")

class MeetingTimeSlot(Base):
    """Meeting time slot model for linking meetings to time slots"""
    __tablename__ = "meeting_time_slots"
    
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Unique constraint to prevent duplicate assignments
    __table_args__ = (UniqueConstraint('meeting_id', 'time_slot_id', name='_meeting_timeslot_uc'),)

class AvailableDate(Base):
    """Available date model for storing actual calendar dates for time slots"""
    __tablename__ = "available_dates"
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    timeslot = relationship("TimeSlot", backref="available_dates")
    
    # Unique constraint for date and timeslot
    __table_args__ = (UniqueConstraint('date', 'time_slot_id', name='_date_timeslot_uc'),)