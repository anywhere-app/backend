from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class CreateUserRequest(BaseModel):
    email: str
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class PinRequest(BaseModel):
    slug: str
    title: str
    lon: float
    lat: float
    description: Optional[str] = None
    cost: Optional[str] = None
    category_ids: List[int]

class CategoryRequest(BaseModel):
    name: str
    description: Optional[str] = None

class HangoutRequest(BaseModel):
    title: str
    description: str
    pin_id: int
    expected_participants: Optional[int] = None
    max_participants: int
    start_time: datetime
    duration: timedelta

class HangoutUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    pin_id: Optional[int] = None
    expected_participants: Optional[int] = None
    max_participants: Optional[int] = None
    start_time: Optional[datetime] = None
    duration: Optional[timedelta] = None

class CommentRequest(BaseModel):
    content: str
    parent_id: Optional[int] = None

class UserResponse(BaseSchema):
    id: int
    username: str
    email: str
    bio: Optional[str] = None
    pfp_url: Optional[str] = None
    favortie_categories: Optional[List[str]] = None
    follower_count: int
    following_count: int
    posts_count: int
    likes_count: int
    visited_count: int
    created_at: datetime
    updated_at: datetime
    is_admin: bool
    is_suspended: bool
    suspended_at: Optional[datetime] = None
    suspended_until: Optional[datetime] = None
    suspended_reason: Optional[str] = None

class SimpleUserResponse(BaseSchema):
    id: int
    username: str
    bio: Optional[str] = None
    pfp_url: Optional[str] = None
    follower_count: int
    following_count: int
    posts_count: int
    likes_count: int
    visited_count: int
    favorite_category_names: Optional[List[str]] = None

class PinResponse(BaseSchema):
    slug: str
    title: str
    description: Optional[str] = None
    coordinates: Dict[str, Any]
    categories: List[str]
    cost: Optional[str] = None
    post_count: int

class FollowResponse(BaseSchema):
    follower_id: int
    following_id: int
    followed_at: datetime

class SuspensionRequest(BaseModel):
    reason: str
    duration: Optional[timedelta] = None