from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Optional
from database import SessionLocal
from sqlalchemy.orm import Session, joinedload
from models import Hangout, HangoutParticipant, Pin, PinCategory, Follow
from schemas import HangoutRequest, HangoutUpdate, HangoutResponse, ParticipantUserResponse
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

def serialize_hangout(hangout: Hangout, current_user_id: int):
    coordinates = {}
    if hangout.pin and hangout.pin.coordinates:
        point = to_shape(hangout.pin.coordinates)
        coordinates = mapping(point)

    categories = []
    if hangout.pin and hangout.pin.categories:
        categories = [cat.category.name for cat in hangout.pin.categories]

    is_attending = False
    if current_user_id and hangout.participants:
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
        "owner_pfp": hangout.user.pfp_url,
        "is_attending": is_attending
    }


@router.get("/", response_model=List[HangoutResponse])
async def get_all_hangouts(db: db_dependency, user: user_dependency):
    hangouts = db.query(Hangout) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories).joinedload(PinCategory.category),
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
async def get_hangout(hangout_id: int, db: db_dependency, user: user_dependency):
    hangout = db.query(Hangout) \
        .filter(Hangout.id == hangout_id) \
        .options(
        joinedload(Hangout.participants),
        joinedload(Hangout.pin).joinedload(Pin.categories).joinedload(PinCategory.category),
        joinedload(Hangout.user)
    ) \
        .first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    current_user_id = user["id"] if user else None
    return serialize_hangout(hangout, current_user_id)


@router.put("/{hangout_id}", response_model=HangoutResponse)
async def update_hangout(hangout_id: int, updated_hangout: HangoutUpdate, db: db_dependency, user: user_dependency):
    hangout = db.query(Hangout) \
        .filter(Hangout.id == hangout_id) \
        .options(joinedload(Hangout.user), joinedload(Hangout.pin)) \
        .first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    if hangout.creator_id != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the owner")

    update_data = updated_hangout.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(hangout, key, value)

    db.commit()
    db.refresh(hangout)

    return await get_hangout(hangout.id, db, user)


@router.post("/{hangout_id}/join", status_code=status.HTTP_202_ACCEPTED)
async def join_hangout(hangout_id: int, db: db_dependency, user: user_dependency):
    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).with_for_update().first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    existing = db.query(HangoutParticipant) \
        .filter(HangoutParticipant.hangout_id == hangout_id, HangoutParticipant.user_id == user["id"]) \
        .first()

    if existing:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already joined")

    if hangout.max_participants is not None:
        if len(hangout.participants) >= hangout.max_participants:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hangout is full")

    participant = HangoutParticipant(
        hangout_id=hangout_id,
        user_id=user["id"]
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    return {"message": "Successfully joined hangout", "hangout_id": hangout_id}

@router.post("/{hangout_id}/leave", status_code=status.HTTP_202_ACCEPTED)
async def leave_hangout(hangout_id: int, db: db_dependency, user: user_dependency):
    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).with_for_update().first()

    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    existing = db.query(HangoutParticipant) \
        .filter(HangoutParticipant.hangout_id == hangout_id, HangoutParticipant.user_id == user["id"]) \
        .first()

    if not existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already left")

    db.delete(existing)
    db.commit()

    return {"message": "Successfully left hangout", "hangout_id": hangout_id}


@router.get("/{hangout_id}/participants", response_model=List[ParticipantUserResponse])
async def get_hangout_participants(hangout_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).first()
    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    participants = db.query(HangoutParticipant) \
        .filter(HangoutParticipant.hangout_id == hangout_id) \
        .options(joinedload(HangoutParticipant.user)) \
        .all()

    if not participants:
        return []

    participant_ids = [p.user_id for p in participants]

    followed_ids = db.query(Follow.following_id) \
        .filter(
        Follow.follower_id == user["id"],
        Follow.following_id.in_(participant_ids)
    ) \
        .all()
    followed_id_set = {id_[0] for id_ in followed_ids}

    return [{
        "user_id": p.user.id,
        "username": p.user.username,
        "pfp_url": p.user.pfp_url,
        "is_followed": p.user.id in followed_id_set
    } for p in participants]