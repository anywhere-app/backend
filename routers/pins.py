import uuid
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import Annotated, Optional
from fastapi.params import Form
from sqlalchemy import select
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Pin, LocationRequest, PinCategory, RequestMedia, RequestCategory, Wishlist, Visit
from schemas import PinRequest, PinResponse
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


@router.get("/", response_model=list[PinResponse])
async def get_all_pins(db: db_dependency, user: Optional[dict] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    pins = db.query(Pin).options(
        joinedload(Pin.categories).joinedload(PinCategory.category)
    ).all()

    if not pins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pins found")

    pin_ids = [pin.id for pin in pins]
    wishlisted_pins = None
    visited_pins = None
    if user:
        wishlisted_pins = set(
            db.execute(
                select(Wishlist.pin_id)
                .where(
                    Wishlist.pin_id.in_(pin_ids),
                    Wishlist.user_id == user["id"]
                )
            ).scalars().all()
        )
        visited_pins = set(
            db.execute(
                select(Visit.pin_id)
                .where(
                    Visit.pin_id.in_(pin_ids),
                    Visit.user_id == user["id"]
                )
            )
            .scalars().all()
        )

    return [
        {
            "id": pin.id,
            "slug": pin.slug,
            "title": pin.title,
            "title_image_url": pin.title_image_url,
            "description": pin.description,
            "coordinates": mapping(to_shape(pin.coordinates)),
            "categories": [cat.category.name for cat in pin.categories],
            "cost": pin.cost,
            "is_wishlisted": pin.id in wishlisted_pins,
            "is_visited": pin.id in visited_pins,
            "post_count": pin.posts_count,
            "created_at": pin.created_at,
            "updated_at": pin.updated_at,
        }
        for pin in pins
    ]

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=PinResponse)
async def create_pin(db: db_dependency, user: user_dependency,
                     title: str = Form(...),
                     description: str = Form(...),
                     cost: str = Form(...),
                     lat: float = Form(...),
                     lon: float = Form(...),
                     category_ids: Optional[str] = Form(None),
                     media: UploadFile = File(...)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if not title or not lon or not lat:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title, longitude, and latitude are required")
    if lon < -180 or lon > 180 or lat < -90 or lat > 90:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid coordinates")
    if db.query(Pin).filter(Pin.coordinates.like(WKTElement(f"POINT({lon} {lat})", srid=4326))).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin with these coordinates already exists")

    if media.content_type not in ["image/jpeg", "image/png", "image/gif", "video/mp4"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed types: JPEG, PNG, GIF, MP4"
        )

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    user_dir = MEDIA_DIR / str(user["id"])
    user_dir.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(media.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = user_dir / unique_name
    file_size = 0
    max_size = 20 * 1024 * 1024

    try:
        with open(file_path, "wb") as f:
            while chunk := await media.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > max_size:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File too large. Max size: {max_size / (1024 * 1024):.0f}MB"
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    media_url = f"/media/{user['id']}/{unique_name}"
    created_pin = Pin(
        slug=title.lower().replace(" ", "-"),
        title=title,
        coordinates=WKTElement(f"POINT({lon} {lat})", srid=4326),
        description=description or None,
        cost=cost or None,
        title_image_url=media_url,
    )
    db.add(created_pin)
    db.commit()
    db.refresh(created_pin)

    parsed_categories = []
    if category_ids:
        try:
            import json
            parsed_categories = json.loads(category_ids)
            if isinstance(parsed_categories, int):
                parsed_categories = [parsed_categories]
            elif not isinstance(parsed_categories, list):
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
            pin_category = PinCategory(
                pin_id=created_pin.id,
                category_id=category
            )
            db.add(pin_category)
        db.commit()
        db.refresh(created_pin)

    pin = created_pin
    return {
        "id": pin.id,
        "slug": pin.slug,
        "title": pin.title,
        "title_image_url": pin.title_image_url,
        "description": pin.description,
        "coordinates": mapping(to_shape(pin.coordinates)),
        "categories": [cat.category.name for cat in pin.categories],
        "cost": pin.cost,
        "post_count": pin.posts_count,
        "created_at": pin.created_at,
        "updated_at": pin.updated_at,
    }

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

@router.post("/requests/{request_id}/approve", status_code=status.HTTP_202_ACCEPTED, response_model=PinResponse)
async def approve_location_request(request_id: int,
                                   db: db_dependency,
                                   user: user_dependency):
    if not user["id_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    request = db.query(LocationRequest).filter(LocationRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location request not found")
    request_media = db.query(RequestMedia).filter(RequestMedia.request_id == request_id).all()
    request_categories = db.query(RequestCategory).filter(RequestCategory.request_id == request_id).all()

    new_pin = Pin(
        title=request.title,
        description=request.description,
        coordinates=request.location,
        cost=request.cost,
    )
    db.add(new_pin)
    db.commit()
    db.refresh(new_pin)

    categories = []
    for category in request_categories:
        pin_category = PinCategory(
            pin_id=new_pin.id,
            category_id=category.category_id
        )
        db.add(pin_category)
        db.commit()
        db.refresh(pin_category)
        categories.append(pin_category)


    pin = new_pin
    return {
        "id": pin.id,
        "slug": pin.title.lower().replace(" ", "-"),
            "title": pin.title,
            "description": pin.description,
            "coordinates": mapping(to_shape(pin.coordinates)),
            "categories": [cat.category.name for cat in pin.categories],
            "cost": pin.cost,
            "post_count": pin.posts_count,
            "created_at": pin.created_at,
            "updated_at": pin.updated_at,
    }


@router.get("/{pin_id_or_slug}", response_model=PinResponse)
async def get_pin_by_id(db: db_dependency, pin_id_or_slug: str, user: Optional[dict] = Depends(get_current_user)):
    try:
        pin_id = int(pin_id_or_slug)
        pin = db.query(Pin).filter(Pin.id == pin_id).first()
    except ValueError:
        pin = db.query(Pin).filter(Pin.slug == pin_id_or_slug).first()

    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")

    in_wishlist = False
    if user:
        item = db.execute(
            select(Wishlist.pin_id)
            .where(
                Wishlist.pin_id == pin.id,
                Wishlist.user_id == user["id"]
            )
        ).scalars().all()
        if item:
            in_wishlist = True

    return {
        "id": pin.id,
        "slug": pin.slug,
        "title": pin.title,
        "title_image_url": pin.title_image_url,
        "description": pin.description,
        "coordinates": mapping(to_shape(pin.coordinates)),
        "categories": [cat.category.name for cat in pin.categories],
        "cost": pin.cost,
        "is_wishlisted": in_wishlist,
        "post_count": pin.posts_count,
        "created_at": pin.created_at,
        "updated_at": pin.updated_at,
    }

@router.put("/{pin_id}", response_model=PinResponse)
async def todo_update_pin(pin_id: int, db: db_dependency, pin: PinRequest, user: user_dependency):
    pass

@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def todo_delete_pin(pin_id: int, db: db_dependency, user: user_dependency):
    pass