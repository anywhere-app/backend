import uuid
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import Annotated, Optional

from fastapi.params import Form

from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Pin, LocationRequest, PinCategory, RequestMedia, RequestCategory
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

load_dotenv()
MEDIA_DIR = Path(os.getenv("MEDIA_DIR"))

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
        "cost": pin.cost,
        "wishlist_count": pin.wishlist_count,
        "visit_count": pin.visit_count,
        "posts_count": pin.posts_count,
        "views_count": pin.views_count,
        "created_at": pin.created_at,
        "updated_at": pin.updated_at,
        "categories": [cat.category_id for cat in pin.categories] if pin.categories else [],
    }

@router.put("/{pin_id}")
async def update_pin(pin_id: int, db: db_dependency, pin: PinRequest, user: user_dependency):
    pass

@router.delete("/{pin_id}")
async def delete_pin(pin_id: int, db: db_dependency, user: user_dependency):
    pass

@router.get("/requests")
async def get_location_requests(db: db_dependency, user: user_dependency):
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access location requests")
    requests = db.query(LocationRequest).all()
    if not requests:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No location requests found")
    return [
        {
            "id": req.id,
            "title": req.title,
            "user_id": req.user_id,
            "description": req.description
        }
        for req in requests
    ]

@router.get("/requests/{request_id}")
async def get_location_request(request_id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access location requests")
    request = db.query(LocationRequest).filter(LocationRequest.id == request_id).options(joinedload(LocationRequest.categories), joinedload(LocationRequest.media)).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location request not found")
    point = to_shape(request.location)
    return {
        "id": request.id,
        "user_id": request.user_id,
        "title": request.title,
        "description": request.description,
        "coordinates": mapping(point),
        "cost": request.cost,
        "has_media": request.has_media,
        "categories": [cat.category_id for cat in request.categories] if request.categories else [],
        "media_urls": [media.media_url for media in request.media] if request.media else [],
        "created_at": request.created_at,
    }

@router.delete("/requests/{request_id}")
async def delete_location_request(request_id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete location requests")
    request = db.query(LocationRequest).filter(LocationRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location request not found")
    db.delete(request)

    media = db.query(RequestMedia).filter(RequestMedia.request_id == request_id).all()
    for m in media:
        media_path = MEDIA_DIR / str(m.media_url).lstrip('/')
        if media_path.exists():
            media_path.unlink()
        db.delete(m)

    categories = db.query(RequestCategory).filter(RequestCategory.request_id == request_id).all()
    for cat in categories:
        db.delete(cat)

    db.delete(categories)
    db.commit()
    return {"detail": "Location request deleted successfully"}

@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_location_request(db: db_dependency,
                                  user: user_dependency,
                                  lat: float = Form(...),
                                  lon: float = Form(...),
                                  title: str = Form(...),
                                  description: Optional[str] = Form(None),
                                  cost: Optional[str] = Form(None),
                                  category_ids: Optional[str] = Form(None),
                                  media: list[UploadFile] = File(None),
                                  ):


    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if lon < -180 or lon > 180 or lat < -90 or lat > 90:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid coordinates")

    new_request = LocationRequest(
        user_id=user["id"],
        location=WKTElement(f"POINT({lon} {lat})", srid=4326),
        title=title,
        description=description or None,
        cost=cost or None,
        has_media= bool(media),
    )

    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    media_urls = []
    if media:
        for med in media:
            if med.content_type not in ["image/jpeg", "image/png", "image/gif", "video/mp4"]:
                continue

            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            user_dir = MEDIA_DIR / str(user["id"])
            user_dir.mkdir(parents=True, exist_ok=True)
            ext = os.path.splitext(med.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            file_path = user_dir / unique_name
            with open(file_path, "wb") as f:
                f.write(await med.read())
            media_url = f"/media/{user['id']}/{unique_name}"
            media_urls.append(media_url)

            new_media = RequestMedia(
                request_id=new_request.id,
                media_url=media_url,
                media_type=med.content_type
            )
            db.add(new_media)
            db.commit()
            db.refresh(new_media)

    parsed_categories = []
    if category_ids:
        try:
            import json
            parsed_categories = json.loads(category_ids)
            if isinstance(parsed_categories, int):  # user gave just one id
                parsed_categories = [parsed_categories]
            elif not isinstance(parsed_categories, list):  # invalid type
                raise ValueError
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid category_ids format, expected JSON list like [1,2,3]"
            )

    if parsed_categories:
        for category in parsed_categories:
            if not isinstance(category, int):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category IDs must be integers")
            request_category = RequestCategory(
                request_id=new_request.id,
                category_id=category
            )
            db.add(request_category)
            db.commit()
            db.refresh(request_category)

    point = to_shape(new_request.location)
    return {
        "id": new_request.id,
        "title": new_request.title,
        "description": new_request.description,
        "coordinates": mapping(point),
        "cost": new_request.cost,
        "user_id": new_request.user_id,
        "has_media": new_request.has_media,
        "categories": [cat.category_id for cat in new_request.categories] if category_ids else [],
        "media_urls": [url for url in media_urls] if media_urls else [],
    }