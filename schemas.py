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
    title: str
    lon: float
    lat: float
    description: Optional[str] = None
    cost: Optional[str] = None
    category_ids: Optional[List[int]] = None

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
    bio: str | None = None
    pfp_url: str | None = None
    follower_count: int
    following_count: int
    posts_count: int
    likes_count: int
    visited_count: int
    created_at: datetime
    updated_at: datetime
    is_admin: bool
    is_suspended: bool
    suspended_at: datetime | None = None
    suspended_until: datetime | None = None
    suspended_reason: str | None = None

class PinResponse(BaseSchema):
    title: str
    description: str | None
    coordinates: Dict[str, Any]
    categories: List[int]
    cost: float | None
    post_count: int

class FollowResponse(BaseSchema):
    follower_id: int
    following_id: int
    followed_at: datetime

class SuspensionRequest(BaseModel):
    reason: str
    duration: Optional[timedelta] = None