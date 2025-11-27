from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, field_serializer, model_validator
from typing import List, Optional, Dict, Any
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_URL = Path(os.getenv("BASE_URL"))

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
    category_ids: List[int]

class PinResponse(BaseSchema):
    id: int
    slug: str
    title: str
    title_image_url: str
    description: Optional[str] = None
    coordinates: Dict[str, Any]
    categories: List[str]
    cost: Optional[str] = None
    post_count: int
    is_wishlisted: Optional[bool] = None
    is_visited: Optional[bool] = None

    @field_serializer('title_image_url')
    def serialize_title_image_url(self, title_image_url: str | None, _info) -> str | None:
        if not title_image_url:
            return None
        if title_image_url.startswith('http://') or title_image_url.startswith('https://'):
            return title_image_url
        path = title_image_url.lstrip('/')

        return f"{BASE_URL}/{path}"


class CategoryRequest(BaseModel):
    name: str

class CategoryResponse(BaseSchema):
    id: int
    name: str

class HangoutResponse(BaseSchema):
    title: str
    description: Optional[str] = None
    catering: Optional[str] = None
    expected_participants: Optional[int] = None
    max_participants: Optional[int] = None
    start_time: datetime
    duration: Optional[timedelta] = None
    pin: PinResponse
    owner_id: int
    owner_username: str
    owner_pfp: str
    is_attending: Optional[bool] = False

class HangoutRequest(BaseModel):
    title: str
    description: str
    catering: Optional[str] = None
    pin_id: int
    expected_participants: Optional[int] = None
    max_participants: Optional[int]
    start_time: datetime
    duration: timedelta

class HangoutUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    catering: Optional[str] = None
    pin_id: Optional[int] = None
    expected_participants: Optional[int] = None
    max_participants: Optional[int] = None
    start_time: Optional[datetime] = None
    duration: Optional[timedelta] = None

class ParticipantUserResponse(BaseModel):
    user_id: int
    username: str
    pfp_url: str | None = None

    @field_serializer('pfp_url')
    def serialize_pfp_url(self, pfp_url: str | None, _info) -> str | None:
        if not pfp_url:
            return None
        if pfp_url.startswith('http://') or pfp_url.startswith('https://'):
            return pfp_url
        path = pfp_url.lstrip('/')

        return f"{BASE_URL}/{path}"

class CommentRequest(BaseModel):
    content: str
    parent_id: Optional[int] = None

class UserResponse(BaseSchema):
    id: int
    username: str
    email: str
    bio: Optional[str] = None
    pfp_url: Optional[str] = None
    follower_count: int
    following_count: int
    posts_count: int
    likes_count: int
    visited_count: int
    favorite_categories: Optional[List[CategoryResponse]] = None
    created_at: datetime
    updated_at: datetime
    is_admin: bool
    is_suspended: bool
    suspended_at: Optional[datetime] = None
    suspended_until: Optional[datetime] = None
    suspended_reason: Optional[str] = None

    @field_serializer('pfp_url')
    def serialize_pfp_url(self, pfp_url: str | None, _info) -> str | None:
        if not pfp_url:
            return None
        if pfp_url.startswith('http://') or pfp_url.startswith('https://'):
            return pfp_url
        path = pfp_url.lstrip('/')

        return f"{BASE_URL}/{path}"

class SimpleUserResponse(BaseSchema):
    id: int
    username: str
    pfp_url: str | None = None
    bio: str | None = None
    follower_count: int
    following_count: int
    posts_count: int
    likes_count: int
    visited_count: int
    favorite_categories: Optional[List[CategoryResponse]] = None
    is_suspended: bool

    @field_serializer('pfp_url')
    def serialize_pfp_url(self, pfp_url: str | None, _info) -> str | None:
        if not pfp_url:
            return None
        if pfp_url.startswith('http://') or pfp_url.startswith('https://'):
            return pfp_url
        path = pfp_url.lstrip('/')

        return f"{BASE_URL}/{path}"

class FollowResponse(BaseSchema):
    follower_id: int
    following_id: int
    followed_at: datetime

class SuspensionRequest(BaseModel):
    reason: str
    duration: Optional[timedelta] = None

class WishlistResponse(BaseSchema):
    pin_id: int
    added_at: datetime
    pin: PinResponse

class VisitResponse(BaseSchema):
    pin_id: int
    added_at: datetime
    pin: PinResponse