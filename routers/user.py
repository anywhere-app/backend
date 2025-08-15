from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Pin, LocationRequest, PinCategory, Visit, Wishlist, User
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

@router.get("/wishlist")
async def get_wishlist(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    wishlist = db.query(Wishlist).options(joinedload(Wishlist.pin)).filter(Wishlist.user_id == user["id"]).all()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    return [serialize_wishlist_item(item) for item in wishlist]

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
    return serialize_wishlist_item(wishlist_item)


@router.get("/visited")
async def get_visited(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    visit = db.query(Visit).options(joinedload(Visit.pin)).filter(Visit.user_id == user["id"]).all()
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No visited pins found")
    return [serialize_visit_item(item) for item in visit]

@router.post("/visited")
async def add_to_visited(pin_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    pin = db.query(Pin).filter(Pin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")
    if db.query(Visit).filter(Visit.pin_id == pin_id, Visit.user_id == user["id"]).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin already visited")
    visited_item = Visit(
        pin_id=pin_id,
        user_id=user["id"]
    )
    db.add(visited_item)
    db.commit()
    db.refresh(visited_item)
    return serialize_visit_item(visited_item)

@router.delete("/visited/{pin_id}")
async def remove_from_visited(pin_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    pin = db.query(Visit).options(joinedload(Visit.pin)).filter(Pin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin not found in visited list")
    db.delete(pin)
    db.commit()
    return {"message": "Pin removed from visited list"}

@router.delete("/wishlist/{pin_id}")
async def remove_from_wishlist(pin_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    pin = db.query(Wishlist).options(joinedload(Wishlist.pin)).filter(Pin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin not found in wishlist")
    db.delete(pin)
    db.commit()
    return {"message": "Pin removed from wishlist"}

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

@router.get("/{id}/visited")
async def get_visited_by_user(id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    visited = db.query(Visit).options(joinedload(Visit.pin)).filter(Visit.user_id == id).all()
    if not visited:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No visited pins found")
    return [serialize_visit_item(item) for item in visited]


@router.get("/{id}/wishlist")
async def get_wishlist_by_id(id: int, user: user_dependency, db: db_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    wishlist = db.query(Wishlist).options(joinedload(Wishlist.pin)).filter(Wishlist.user_id == id).all()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    return [serialize_wishlist_item(item) for item in wishlist]


def serialize_wishlist_item(item: Wishlist):
    return {
        "pin_id": item.pin.id,
        "added_at": item.added_at,
        "pin": {
            "title": item.pin.title,
            "description": item.pin.description,
            "coordinates": mapping(to_shape(item.pin.coordinates)),
            "categories": [cat.category_id for cat in item.pin.categories] if item.pin.categories else [],
            "cost": item.pin.cost,
            "post_count": item.pin.posts_count,
        }
    }

def serialize_visit_item(item: Visit):
    return {
        "pin_id": item.pin.id,
        "added_at": item.visited_at,
        "pin": {
            "title": item.pin.title,
            "description": item.pin.description,
            "coordinates": mapping(to_shape(item.pin.coordinates)),
            "categories": [cat.category_id for cat in item.pin.categories] if item.pin.categories else [],
            "cost": item.pin.cost,
            "post_count": item.pin.posts_count,
        }
    }