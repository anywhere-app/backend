from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, Boolean, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
import datetime
from sqlalchemy.sql.sqltypes import Interval
from database import Base


class Follow(Base):
    __tablename__ = "follows"
    follower_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    following_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    followed_at = Column(DateTime(timezone=True), default=func.now())
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following = relationship("User", foreign_keys=[following_id], back_populates="followers")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user1_id", "user2_id", name="unique_user_pair"),)
    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    messages = relationship("Message", back_populates="conversation")

    @validates("user1_id", "user2_id")
    def validate_users(self, key, value):
        if key == "user2_id" and self.user1_id is not None:
            u1, u2 = sorted([self.user1_id, value])
            self.user1_id, self.user2_id = u1, u2
            return self.user2_id
        return value

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
    last_seen_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    is_suspended = Column(Boolean, default=False)
    suspended_at = Column(DateTime, nullable=True)
    suspended_until = Column(DateTime, nullable=True)
    suspended_reason = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)

    wishlists = relationship("Wishlist", back_populates="user")
    visits = relationship("Visit", back_populates="user")
    location_requests = relationship("LocationRequest", back_populates="user")
    hangouts = relationship("Hangout", back_populates="user")
    hangout_participants = relationship("HangoutParticipant", back_populates="user")
    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    post_likes = relationship("PostLike", back_populates="user")
    comment_likes = relationship("CommentLike", back_populates="user")
    following = relationship("Follow", foreign_keys=[Follow.follower_id], back_populates="follower")
    followers = relationship("Follow", foreign_keys=[Follow.following_id], back_populates="following")
    messages = relationship("Message", back_populates="sender")
    favorite_categories = relationship("FavoriteCategory", back_populates="user")

class Pin(Base):
    __tablename__ = "pins"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    title_image_url = Column(String, nullable=False)
    coordinates = Column(Geometry(geometry_type='POINT', srid=4326))
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    wishlist_count = Column(Integer, default=0)
    visit_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    cost = Column(String, nullable=True)
    view_count = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("coordinates", name="unique_pin_coordinates"),
    )

    wishlists = relationship("Wishlist", back_populates="pin")
    visits = relationship("Visit", back_populates="pin")
    categories = relationship("PinCategory", back_populates="pin")
    hangouts = relationship("Hangout", back_populates="pin")
    posts = relationship("Post", back_populates="pin")

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
    location_count = Column(Integer, default=0)
    post_count = Column(Integer, default=0)
    requests = relationship("RequestCategory", back_populates="category")
    pins = relationship("PinCategory", back_populates="category")
    favorite_categories = relationship("FavoriteCategory", back_populates="category")

class FavoriteCategory(Base):
    __tablename__ = "favorite_categories"
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    category = relationship("Category", back_populates="favorite_categories")
    user = relationship("User", back_populates="favorite_categories")

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
    cost = Column(String, nullable=True)
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

class Hangout(Base):
    __tablename__ = "hangouts"
    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    pin_id = Column(Integer, ForeignKey("pins.id"))
    expected_participants = Column(Integer, nullable=True)
    max_participants = Column(Integer, nullable=False)
    start_time = Column(DateTime(timezone=True), default=func.now())
    duration = Column(Interval, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    pin = relationship("Pin", back_populates="hangouts")
    user = relationship("User", back_populates="hangouts")
    participants = relationship("HangoutParticipant", back_populates="hangout")

class HangoutParticipant(Base):
    __tablename__ = "hangout_participants"
    hangout_id = Column(Integer, ForeignKey("hangouts.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    hangout = relationship("Hangout", back_populates="participants")
    user = relationship("User", back_populates="hangout_participants")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    pin_id = Column(Integer, ForeignKey("pins.id"))
    title = Column(String, nullable=True)
    description = Column(String, nullable=True)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    media_url = Column(String, nullable=True)
    view_count = Column(Integer, default=0)
    user = relationship("User", back_populates="posts")
    pin = relationship("Pin", back_populates="posts")
    comments = relationship("Comment", back_populates="post")
    likes = relationship("PostLike", back_populates="post")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    content = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    like_count = Column(Integer, default=0)
    user = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")
    likes = relationship("CommentLike", back_populates="comment")

class PostLike(Base):
    __tablename__ = "post_likes"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), primary_key=True)
    liked_at = Column(DateTime(timezone=True), default=func.now())
    user = relationship("User", back_populates="post_likes")
    post = relationship("Post", back_populates="likes")

class CommentLike(Base):
    __tablename__ = "comment_likes"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), primary_key=True)
    liked_at = Column(DateTime(timezone=True), default=func.now())
    user = relationship("User", back_populates="comment_likes")
    comment = relationship("Comment", back_populates="likes")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(String, nullable=True)
    media_url = Column(String, nullable=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now())
    sender = relationship("User", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")