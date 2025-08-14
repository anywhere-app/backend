from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, Boolean, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    bio = Column(String, nullable=True)
    pfp_url = Column(String, nullable=True)
    follower_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    visited_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    is_suspended = Column(Boolean, default=False)
    suspended_at = Column(DateTime, nullable=True)
    suspended_until = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))
    wishlists = relationship("Wishlist", back_populates="user")
    visits = relationship("Visit", back_populates="user")
    location_requests = relationship("LocationRequest", back_populates="user")

class Pin(Base):
    __tablename__ = "pins"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    coordinates = Column(Geometry(geometry_type='POINT', srid=4326))
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    wishlist_count = Column(Integer, default=0)
    visit_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    wishlists = relationship("Wishlist", back_populates="pin")
    visits = relationship("Visit", back_populates="pin")
    categories = relationship("PinCategory", back_populates="pin")

class Wishlist(Base):
    __tablename__ = "wishlists"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    pin_id = Column(Integer, ForeignKey("pins.id"), primary_key=True)
    added_at = Column(DateTime(timezone=True), default=func.now())
    user = relationship("User", back_populates="wishlists")
    pin = relationship("Pin", back_populates="wishlists")

class Visit(Base):
    __tablename__ = "visits"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    pin_id = Column(Integer, ForeignKey("pins.id"), primary_key=True)
    visited_at = Column(DateTime(timezone=True), default=func.now())
    user = relationship("User", back_populates="visits")
    pin = relationship("Pin", back_populates="visits")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    location_count = Column(Integer, default=0)
    post_count = Column(Integer, default=0)
    requests = relationship("RequestCategory", back_populates="category")
    pins = relationship("PinCategory", back_populates="category")

class PinCategory(Base):
    __tablename__ = "pin_categories"
    pin_id = Column(Integer, ForeignKey("pins.id"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)
    pin = relationship("Pin", back_populates="categories")
    category = relationship("Category", back_populates="pins")

class LocationRequest(Base):
    __tablename__ = "location_requests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    has_media = Column(Boolean, default=False)
    has_categories = Column(Boolean, default=False)
    user = relationship("User", back_populates="location_requests")
    media = relationship("RequestMedia", back_populates="request")
    categories = relationship("RequestCategory", back_populates="request")

class RequestMedia(Base):
    __tablename__ = "request_media"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("location_requests.id"))
    media_url = Column(String, nullable=False)
    media_type = Column(String, nullable=False)
    request = relationship("LocationRequest", back_populates="media")

class RequestCategory(Base):
    __tablename__ = "request_categories"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("location_requests.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    request = relationship("LocationRequest", back_populates="categories")
    category = relationship("Category", back_populates="requests")
