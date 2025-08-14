from fastapi import UploadFile
from pydantic import BaseModel
from typing import List, Optional

class CreateUserRequest(BaseModel):
    email: str
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class PinRequest(BaseModel):
    title: str
    lon: float
    lat: float
    description: Optional[str]
    category_ids: Optional[List[int]]

class CategoryRequest(BaseModel):
    name: str
    description: Optional[str] = None