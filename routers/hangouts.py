from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import Annotated, List
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Hangout, HangoutParticipant, Pin, User
from schemas import HangoutRequest, HangoutUpdate, HangoutResponse, PinResponse
from routers.auth import get_current_user
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

router = APIRouter(
    prefix="/hangouts",
    tags=["hangouts"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


def serialize_hangout(hangout: Hangout, current_user_id: int = None) -> dict:
    """Helper function to serialize a Hangout to HangoutResponse format"""
    # Serialize pin coordinates
    point = to_shape(hangout.pin.coordinates)
    coordinates = mapping(point)

    # Get pin categories
    categories = [cat.category.name for cat in hangout.pin.categories]

    # Check if current user is attending
    is_attending = False
    if current_user_id:
        is_attending = any(p.user_id == current_user_id for p in hangout.participants)

    return {
        "title": hangout.title,
        "description": hangout.description,
        "catering": hangout.catering,
        "expected_participants": hangout.expected_participants,
        "max_participants": hangout.max_participants,
        "start_time": hangout.start_time,
        "duration": hangout.duration,
        "pin": {
            "id": hangout.pin.id,
            "slug": hangout.pin.slug,
            "title": hangout.pin.title,
            "title_image_url": hangout.pin.title_image_url,
            "description": hangout.pin.description,
            "coordinates": coordinates,
            "categories": categories,
            "cost": hangout.pin.cost,
            "post_count": hangout.pin.posts_count,
            "is_wishlisted": None,
            "is_visited": None
        },
        "owner_id": hangout.creator_id,
        "owner_username": hangout.user.username,
        "owner_pfp": hangout.user.pfp_url or "",
        "is_attending": is_attending
    }


@router.get("/", response_model=List[HangoutResponse])
async def get_all_hangouts(db: db_dependency, user: user_dependency = None):
    hangouts = db.query(Hangout) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories),
        joinedload(Hangout.user)
    ) \
        .all()

    if not hangouts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hangouts found")

    current_user_id = user["id"] if user else None
    return [serialize_hangout(hangout, current_user_id) for hangout in hangouts]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=HangoutResponse)
async def create_hangout(db: db_dependency, hangout: HangoutRequest, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    create_hangout = Hangout(
        title=hangout.title,
        description=hangout.description,
        catering=hangout.catering,
        pin_id=hangout.pin_id,
        creator_id=user["id"],
        expected_participants=hangout.expected_participants or None,
        max_participants=hangout.max_participants,
        start_time=hangout.start_time,
        duration=hangout.duration
    )
    db.add(create_hangout)
    db.commit()
    db.refresh(create_hangout)

    # Reload with relationships
    hangout_obj = db.query(Hangout) \
        .filter(Hangout.id == create_hangout.id) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories),
        joinedload(Hangout.user)
    ) \
        .first()

    return serialize_hangout(hangout_obj, user["id"])


@router.get("/{hangout_id}", response_model=HangoutResponse)
async def get_hangout(hangout_id: int, db: db_dependency, user: user_dependency = None):
    hangout = db.query(Hangout) \
        .filter(Hangout.id == hangout_id) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories),
        joinedload(Hangout.user)
    ) \
        .first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    current_user_id = user["id"] if user else None
    return serialize_hangout(hangout, current_user_id)


@router.put("/{hangout_id}", response_model=HangoutResponse)
async def update_hangout(hangout_id: int, updated_hangout: HangoutUpdate, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    hangout = db.query(Hangout) \
        .filter(Hangout.id == hangout_id) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories),
        joinedload(Hangout.user)
    ) \
        .first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")
    if hangout.creator_id != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # Only update fields that were provided
    if updated_hangout.title is not None:
        hangout.title = updated_hangout.title
    if updated_hangout.description is not None:
        hangout.description = updated_hangout.description
    if updated_hangout.pin_id is not None:
        hangout.pin_id = updated_hangout.pin_id
    if updated_hangout.expected_participants is not None:
        hangout.expected_participants = updated_hangout.expected_participants
    if updated_hangout.max_participants is not None:
        hangout.max_participants = updated_hangout.max_participants
    if updated_hangout.start_time is not None:
        hangout.start_time = updated_hangout.start_time
    if updated_hangout.duration is not None:
        hangout.duration = updated_hangout.duration
    if updated_hangout.catering is not None:
        hangout.catering = updated_hangout.catering

    db.commit()
    db.refresh(hangout)

    return serialize_hangout(hangout, user["id"])


@router.post("/{hangout_id}/join", status_code=status.HTTP_202_ACCEPTED)
async def join_hangout(hangout_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).first()
    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    # Check if user is already a participant
    existing = db.query(HangoutParticipant) \
        .filter(HangoutParticipant.hangout_id == hangout_id) \
        .filter(HangoutParticipant.user_id == user["id"]) \
        .first()

    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already joined this hangout")

    if len(hangout.participants) >= hangout.max_participants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hangout is full")

    participant = HangoutParticipant(
        hangout_id=hangout_id,
        user_id=user["id"]
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    return {"message": "Successfully joined hangout", "hangout_id": hangout_id}


@router.get("/{hangout_id}/participants")
async def get_hangout_participants(hangout_id: int, db: db_dependency):
    hangout = db.query(Hangout) \
        .filter(Hangout.id == hangout_id) \
        .options(joinedload(Hangout.participants)) \
        .first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    participants = db.query(HangoutParticipant) \
        .filter(HangoutParticipant.hangout_id == hangout_id) \
        .options(joinedload(HangoutParticipant.user)) \
        .all()

    if not participants:
        return []

    return [{
        "user_id": p.user.id,
        "username": p.user.username,
        "pfp_url": p.user.pfp_url
    } for p in participants]