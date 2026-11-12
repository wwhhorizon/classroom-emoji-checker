"""Relational domain model. All stored timestamps are naive UTC."""
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import (create_engine, event, Column, Integer, String, Text,
                        Float, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index)
from sqlalchemy.orm import declarative_base, sessionmaker


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.isoformat(timespec='seconds') + 'Z' if value else None


EMOJIS = ['happy', 'neutral', 'sad', 'surprised', 'angry', 'fearful', 'disgusted']
Path('data').mkdir(exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/emoji.db')
engine = create_engine(DATABASE_URL, pool_pre_ping=True,
    connect_args={'check_same_thread': False, 'timeout': 20} if DATABASE_URL.startswith('sqlite') else {})
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')

SessionLocal = sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(40), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(16), nullable=False)
    email = Column(String(120), default='', nullable=False)
    active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    __table_args__ = (CheckConstraint("role in ('student','teacher','admin')"),)


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    expires = Column(DateTime, nullable=False)


class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    teacher_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    __table_args__ = (UniqueConstraint('name', 'teacher_id'),)


class ClassSession(Base):
    __tablename__ = 'class_sessions'
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False, index=True)
    start_at = Column(DateTime, nullable=False, index=True)
    end_at = Column(DateTime, nullable=False)
    class_name = Column(String(80), nullable=False)
    room = Column(String(80), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    __table_args__ = (CheckConstraint('end_at > start_at'), CheckConstraint('version >= 1'))


class ScheduleUser(Base):
    __tablename__ = 'schedule_users'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('class_sessions.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    scheduled_at = Column(DateTime, default=now, nullable=False)
    __table_args__ = (UniqueConstraint('session_id', 'user_id'),)


class EmojiRecord(Base):
    __tablename__ = 'emoji_records'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey('class_sessions.id'), nullable=False, index=True)
    emoji = Column(String(16), nullable=False)
    timestamp = Column(DateTime, default=now, nullable=False, index=True)
    source = Column(String(8), nullable=False)
    confidence = Column(Float, nullable=True)
    device_id = Column(String(80), default='', nullable=False)
    model_version = Column(String(100), default='', nullable=False)
    event_id = Column(String(100), unique=True, nullable=True)
    __table_args__ = (
        CheckConstraint("emoji in ('happy','neutral','sad','surprised','angry','fearful','disgusted')"),
        CheckConstraint("source in ('MANUAL','AI')"),
        CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)'),
        CheckConstraint("source != 'AI' OR confidence IS NOT NULL"),
        CheckConstraint("source != 'MANUAL' OR user_id IS NOT NULL"),
        Index('ix_emoji_session_time', 'session_id', 'timestamp'))


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    action = Column(String(60), nullable=False, index=True)
    detail = Column(Text, default='', nullable=False)
    created_at = Column(DateTime, default=now, nullable=False, index=True)
