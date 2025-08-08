from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, Boolean, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    unique_username = Column(String, unique=True)
    username = Column(String, default=unique_username)
    email = Column(String)
    hashed_password = Column(String)
    bio = Column(String)
    pfp_url = Column(String)
    follower_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    visited_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime, default=created_at)
    is_suspended = Column(Boolean, default=False)
    suspended_at = Column(DateTime, nullable=True)
    suspended_until = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)

