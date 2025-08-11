from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Pin, LocationRequest, PinCategory, Category
from schemas import PinRequest
from routers.auth import get_current_user
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

router = APIRouter(
    prefix = "/user",
    tags = ["user"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@router.get("/")
async def get_user(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    account = db.query(User).filter(User.id == user["id"]).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return account

@router.get("/{id}")
async def get_user_by_id(id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    account = db.query(User).filter(User.id == id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return account

@router.get("/wishlist")
async def get_wishlist(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    wishlist = db.query(Wishlist).options(joinedload(Wishlist.pin)).filter(Wishlist.user_id == user["id"]).all()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    return [
        {
            "pin_id": item.pin.id,
            "added_at": item.added_at,
            "pin": {
                "title": item.pin.title,
                "description": item.pin.description,
                "coordinates": mapping(to_shape(item.pin.coordinates)),
            }
        }
        for item in wishlist
    ]

@router.post("/wishlist")
async def add_to_wishlist(pin_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    pin = db.query(Pin).filter(Pin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")
    if db.query(Wishlist).filter(Wishlist.pin_id == pin_id, Wishlist.user_id == user["id"]).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin already in wishlist")
    wishlist_item = Wishlist(
        pin_id=pin_id,
        user_id=user["id"]
    )
    db.add(wishlist_item)
    db.commit()
    db.refresh(wishlist_item)
    return {
        "pin_id": wishlist_item.pin_id,
        "added_at": wishlist_item.added_at,
        "pin": {
            "title": pin.title,
            "description": pin.description,
            "coordinates": mapping(to_shape(pin.coordinates)),
        }
    }

