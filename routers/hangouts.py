from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Optional
from database import SessionLocal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from models import Hangout, HangoutParticipant, Pin
from schemas import HangoutRequest, HangoutUpdate, HangoutResponse
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


async def get_optional_user(token: str = None):
    if not token: return None
    return await get_current_user(token)


optional_user_dependency = Annotated[dict | None, Depends(get_optional_user)]


def serialize_hangout(hangout: Hangout, current_user_id: int = None) -> dict:
    coordinates = None
    if hangout.pin and hangout.pin.coordinates:
        point = to_shape(hangout.pin.coordinates)
        coordinates = mapping(point)

    categories = []
    if hangout.pin and hangout.pin.categories:
        try:
            categories = [cat.category.name for cat in hangout.pin.categories]
        except AttributeError:
            categories = [cat.name for cat in hangout.pin.categories]

    is_attending = False
    if current_user_id and hangout.participants:
        is_attending = any(p.user_id == current_user_id for p in hangout.participants)

    return {
        "title": hangout.title,
        "is_attending": is_attending
    }


@router.get("/", response_model=List[HangoutResponse])
async def get_all_hangouts(db: db_dependency, user: Optional[dict] = Depends(get_optional_user)):
    hangouts = db.query(Hangout) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories).joinedload("category"),
        joinedload(Hangout.user)
    ) \
        .all()

    if not hangouts:
        return []

    current_user_id = user["id"] if user else None
    return [serialize_hangout(h, current_user_id) for h in hangouts]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=HangoutResponse)
async def create_hangout(db: db_dependency, hangout: HangoutRequest, user: user_dependency):
    new_hangout = Hangout(
        title=hangout.title,
        description=hangout.description,
        catering=hangout.catering,
        pin_id=hangout.pin_id,
        creator_id=user["id"],
        expected_participants=hangout.expected_participants,
        max_participants=hangout.max_participants,
        start_time=hangout.start_time,
        duration=hangout.duration
    )
    db.add(new_hangout)
    db.commit()
    db.refresh(new_hangout)
    return await get_hangout(new_hangout.id, db, user)


@router.get("/{hangout_id}", response_model=HangoutResponse)
async def get_hangout(hangout_id: int, db: db_dependency, user: Optional[dict] = Depends(get_optional_user)):
    hangout = db.query(Hangout) \
        .filter(Hangout.id == hangout_id) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories).joinedload("category"),
        joinedload(Hangout.user)
    ) \
        .first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    current_user_id = user["id"] if user else None
    return serialize_hangout(hangout, current_user_id)


@router.post("/{hangout_id}/join", status_code=status.HTTP_202_ACCEPTED)
async def join_hangout(hangout_id: int, db: db_dependency, user: user_dependency):
    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).with_for_update().first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    existing = db.query(HangoutParticipant).filter(
        HangoutParticipant.hangout_id == hangout_id,
        HangoutParticipant.user_id == user["id"]
    ).first()

    if existing:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already joined")

    current_count = len(hangout.participants)
    if current_count >= hangout.max_participants:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hangout is full")

    participant = HangoutParticipant(
        hangout_id=hangout_id,
        user_id=user["id"]
    )
    db.add(participant)
    db.commit()

    return {"message": "Successfully joined hangout", "hangout_id": hangout_id}
