from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import Annotated
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Pin, LocationRequest, PinCategory
from schemas import PinRequest
from routers.auth import get_current_user
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
import os


router = APIRouter(
    prefix = "/pins",
    tags = ["pins"]
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
async def get_all_pins(db: db_dependency):
    pins = db.query(Pin).options(joinedload(Pin.categories)).all()
    if not pins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pins found")
    return [
        {
            "id": pin.id,
            "title": pin.title,
            "description": pin.description,
            "coordinates": mapping(to_shape(pin.coordinates)),
            "created_at": pin.created_at,
            "updated_at": pin.updated_at,
            "categories": [cat.category_id for cat in pin.categories],
            "wishlist_count": pin.wishlist_count,
            "visit_count": pin.visit_count,
            "posts_count": pin.posts_count,
        }
        for pin in pins
    ]

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_pin(db: db_dependency, pin: PinRequest, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not pin.title or not pin.lon or not pin.lat:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title, longitude, and latitude are required")
    if pin.lon < -180 or pin.lon > 180 or pin.lat < -90 or pin.lat > 90:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid coordinates")
    if db.query(Pin).filter(Pin.coordinates.like(WKTElement(f"POINT({pin.lon} {pin.lat})", srid=4326))).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin with these coordinates already exists")
    created_pin = Pin(
        title=pin.title,
        coordinates=WKTElement(f"POINT({pin.lon} {pin.lat})", srid=4326),
        description=pin.description or None,
        cost=pin.cost or None,
    )
    db.add(created_pin)
    db.commit()
    db.refresh(created_pin)
    if pin.category_ids:
        for category in pin.category_ids:
            pin_category = PinCategory(
                pin_id=created_pin.id,
                category_id=category
            )
            db.add(pin_category)
            db.commit()
            db.refresh(pin_category)
    point = to_shape(created_pin.coordinates)
    return {
        "id": created_pin.id,
        "title": created_pin.title,
        "description": created_pin.description,
        "coordinates": mapping(point),
        "cost": created_pin.cost,
        "categories": [cat.category_id for cat in created_pin.categories] if pin.category_ids else [],
    }



@router.get("/{pin_id}")
async def get_pin_by_id(pin_id: int, db: db_dependency):
    pin = db.query(Pin).filter(Pin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")
    return {
        "id": pin.id,
        "title": pin.title,
        "description": pin.description,
        "coordinates": mapping(to_shape(pin.coordinates)),
        "categories": [cat.category_id for cat in pin.categories] if pin.categories else [],
    }

@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_location_request(db: db_dependency,
                                  user: user_dependency,
                                  media: list[UploadFile] = File(None),
                                  request: PinRequest = Depends(PinRequest),
                                  ):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if request.lon < -180 or request.lon > 180 or request.lat < -90 or request.lat > 90:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid coordinates")
    if media:
        pass
    new_request = LocationRequest(
        user_id=user["id"],
        location=WKTElement(f"POINT({request.lon} {request.lat})", srid=4326),
        title=request.title,
        description=request.description or None,
        cost=request.cost or None,
    )