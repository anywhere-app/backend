from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import Annotated
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Hangout, HangoutParticipant
from schemas import HangoutRequest, HangoutUpdate
from routers.auth import get_current_user
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

router = APIRouter(
    prefix = "/hangouts",
    tags = ["hangouts"]
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
async def get_all_hangouts(db: db_dependency):
    hangouts = db.query(Hangout).options(joinedload(Hangout.participants)).all()
    if not hangouts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hangouts found")
    return [hangout for hangout in hangouts]

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=HangoutRequest)
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
    return create_hangout

@router.get("/{hangout_id}", response_model=HangoutRequest)
async def get_hangout(hangout_id: int, db: db_dependency):
    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).first()
    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")
    return hangout

@router.put("/{hangout_id}", response_model=HangoutRequest)
async def update_hangout(hangout_id: int, updated_hangout: HangoutUpdate, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).first()
    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")
    if hangout.creator_id != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    hangout.title = updated_hangout.title or hangout.title
    hangout.description = updated_hangout.description or hangout.description
    hangout.pin_id = updated_hangout.pin_id or hangout.pin_id
    hangout.expected_participants = updated_hangout.expected_participants or hangout.expected_participants
    hangout.max_participants = updated_hangout.max_participants or hangout.max_participants
    hangout.start_time = updated_hangout.start_time or hangout.start_time
    hangout.duration = updated_hangout.duration or hangout.duration
    hangout.catering = updated_hangout.catering or hangout.catering

    db.commit()
    db.refresh(hangout)

    return hangout

@router.post("/{hangout_id}/join", status_code=status.HTTP_202_ACCEPTED)
async def join_hangout(hangout_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).first()
    if not hangout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hangout not found")

    if len(hangout.participants) >= hangout.max_participants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hangout is full")

    participant = HangoutParticipant(
        hangout_id=hangout_id,
        user_id=user["id"]
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    return participant

@router.get("/{hangout_id}/participants")
async def get_hangout_participants(hangout_id: int, db: db_dependency):
    hangout = db.query(Hangout).filter(Hangout.id == hangout_id).options(joinedload(Hangout.participants)).first()
    participants = db.query(HangoutParticipant).filter(HangoutParticipant.hangout_id == hangout_id).options(joinedload(HangoutParticipant.user)).all()
    if not participants:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No participants found for this hangout")
    return [participant for participant in participants]