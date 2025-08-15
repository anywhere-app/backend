from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional

class CreateUserRequest(BaseModel):
    email: str
    username: str
    password: str
    admin: Optional[bool] = False

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