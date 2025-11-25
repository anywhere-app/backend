from datetime import datetime, UTC
from threading import active_count
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from sqlalchemy import select
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload, selectinload
from models import Pin, Visit, Wishlist, User, Follow, Comment, Post, FavoriteCategory, PinCategory
from schemas import UserResponse, FollowResponse, SuspensionRequest, SimpleUserResponse, UserUpdateRequest
from routers.auth import get_current_user
from routers.posts import serialize_post, serialize_comment
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


@router.get("/", response_model=UserResponse)
async def get_user(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    result = db.execute(
        select(User)
        .where(User.id == user["id"])
        .options(
            selectinload(User.favorite_categories).selectinload(FavoriteCategory.category)
        )
    )
    account = result.scalars().first()
    return {
        "id": account.id,
        "username": account.username,
        "email": account.email,
        "bio": account.bio,
        "pfp_url": account.pfp_url,
        "favorite_categories": [
            {"id": fc.category.id, "name": fc.category.name}
            for fc in account.favorite_categories
        ] if account.favorite_categories else [],
        "follower_count": account.follower_count,
        "following_count": account.following_count,
        "posts_count": account.posts_count,
        "likes_count": account.likes_count,
        "visited_count": account.visited_count,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
        "is_admin": account.is_admin,
        "is_suspended": account.is_suspended,
        "suspended_at": account.suspended_at,
        "suspended_until": account.suspended_until,
        "suspended_reason": account.suspended_reason
    }
@router.put("/", response_model=UserResponse)
async def update_user(db: db_dependency, user: user_dependency, updated_user: UserUpdateRequest):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    account = db.query(User).filter(User.id == user["id"]).first()
    if updated_user.username is not None:
        account.username = updated_user.username
    if updated_user.bio is not None:
        account.bio = updated_user.bio
    if updated_user.pfp_url is not None:
        account.pfp_url = updated_user.pfp_url
    db.commit()
    db.refresh(account)
    return {
        "id": account.id,
        "username": account.username,
        "email": account.email,
        "bio": account.bio,
        "pfp_url": account.pfp_url,
        "favorite_categories": [
            {"id": fc.category.id, "name": fc.category.name}
            for fc in account.favorite_categories
        ] if account.favorite_categories else [],
        "follower_count": account.follower_count,
        "following_count": account.following_count,
        "posts_count": account.posts_count,
        "likes_count": account.likes_count,
        "visited_count": account.visited_count,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
        "is_admin": account.is_admin,
        "is_suspended": account.is_suspended,
        "suspended_at": account.suspended_at,
        "suspended_until": account.suspended_until,
        "suspended_reason": account.suspended_reason
    }

@router.get("/all", response_model=List[SimpleUserResponse])
async def get_all_users(db: db_dependency):
    result = db.execute(
        select(User)
        .options(
            selectinload(User.favorite_categories).selectinload(FavoriteCategory.category)
        )
    )
    users = result.scalars().all()
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users found")
    return [
        {
            "id": user.id,
            "username": user.username,
            "pfp_url": user.pfp_url,
            "bio": user.bio,
            "follower_count": user.follower_count,
            "following_count": user.following_count,
            "posts_count": user.posts_count,
            "likes_count": user.likes_count,
            "visited_count": user.visited_count,
            "favorite_categories": [
                {"id": fc.category.id, "name": fc.category.name}
                for fc in user.favorite_categories
            ] if user.favorite_categories else [],
            "is_suspended": user.is_suspended
        }
        for user in users
    ]
@router.get("/all", response_model=List[UserResponse])
async def get_all_users(db: db_dependency):
    users = db.query(User).all()
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users found")

    result = db.execute(
        select(User)
        .options(selectinload(User.favorite_categories).selectinload(FavoriteCategory.category))
    )
    accounts = result.scalars().all()
    return accounts

@router.get("/wishlist")
async def get_wishlist(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    vq = (
        db.query(Visit.pin_id)
        .filter(Visit.user_id == id)
        .subquery()
    )

    wishlist = (
        db.query(Wishlist, vq.c.pin_id.isnot(None).label("is_visited"))
        .options(
            joinedload(Wishlist.pin).joinedload(Pin.categories)
        )
        .outerjoin(vq, vq.c.pin_id == Wishlist.pin_id)
        .filter(Wishlist.user_id == id)
        .all()
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    return [serialize_wishlist_item(item[0], is_visited=item[1]) for item in wishlist]

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

    wq = (
        db.query(Wishlist.pin_id)
        .filter(Wishlist.user_id == user["id"])
        .subquery()
    )

    visit = (
        db.query(Visit, wq.c.pin_id.isnot(None).label("in_wishlist"))
        .options(
            joinedload(Visit.pin).joinedload(Pin.categories)
        )
        .outerjoin(wq, wq.c.pin_id == Visit.pin_id)
        .filter(Visit.user_id == user["id"])
        .all()
    )

    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No visited pins found")

    return [serialize_visit_item(item[0], is_wishlisted=item[1]) for item in visit]


@router.get("/wishlist")
async def get_wishlist(db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    vq = (
        db.query(Visit.pin_id)
        .filter(Visit.user_id == user["id"])
        .subquery()
    )

    wishlist = (
        db.query(Wishlist, vq.c.pin_id.isnot(None).label("is_visited"))
        .options(
            joinedload(Wishlist.pin).joinedload(Pin.categories)
        )
        .outerjoin(vq, vq.c.pin_id == Wishlist.pin_id)
        .filter(Wishlist.user_id == user["id"])
        .all()
    )

    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    return [serialize_wishlist_item(item[0], is_visited=item[1]) for item in wishlist]


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

    # Check if in wishlist
    is_wishlisted = db.query(Wishlist).filter(
        Wishlist.pin_id == pin_id,
        Wishlist.user_id == user["id"]
    ).first() is not None

    return serialize_visit_item(visited_item, is_wishlisted=is_wishlisted)


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

    is_visited = db.query(Visit).filter(
        Visit.pin_id == pin_id,
        Visit.user_id == user["id"]
    ).first() is not None

    return serialize_wishlist_item(wishlist_item, is_visited=is_visited)


@router.get("/{id}/visited")
async def get_visited_by_id(id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    wq = (
        db.query(Wishlist.pin_id)
        .filter(Wishlist.user_id == id)
        .subquery()
    )

    visited = (
        db.query(Visit, wq.c.pin_id.isnot(None).label("in_wishlist"))
        .options(
            joinedload(Visit.pin).joinedload(Pin.categories)
        )
        .outerjoin(wq, wq.c.pin_id == Visit.pin_id)
        .filter(Visit.user_id == id)
        .all()
    )

    if not visited:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No visited pins found")

    return [serialize_visit_item(item[0], is_wishlisted=item[1]) for item in visited]


@router.get("/{id}/wishlist")
async def get_wishlist_by_id(id: int, user: user_dependency, db: db_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    vq = (
        db.query(Visit.pin_id)
        .filter(Visit.user_id == id)
        .subquery()
    )

    wishlist = (
        db.query(Wishlist, vq.c.pin_id.isnot(None).label("is_visited"))
        .options(
            joinedload(Wishlist.pin).joinedload(Pin.categories)
        )
        .outerjoin(vq, vq.c.pin_id == Wishlist.pin_id)
        .filter(Wishlist.user_id == id)
        .all()
    )

    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    return [serialize_wishlist_item(item[0], is_visited=item[1]) for item in wishlist]


def serialize_wishlist_item(item: Wishlist, is_visited: bool = False):
    return {
        "pin_id": item.pin.id,
        "added_at": item.added_at,
        "pin": {
            "title": item.pin.title,
            "description": item.pin.description,
            "coordinates": mapping(to_shape(item.pin.coordinates)),
            "categories": [cat.name for cat in item.pin.categories] if item.pin.categories else [],
            "cost": item.pin.cost,
            "post_count": item.pin.posts_count,
        },
        "is_visited": is_visited,
    }


def serialize_visit_item(item: Visit, is_wishlisted: bool = False):
    return {
        "pin_id": item.pin.id,
        "added_at": item.visited_at,
        "pin": {
            "title": item.pin.title,
            "description": item.pin.description,
            "coordinates": mapping(to_shape(item.pin.coordinates)),
            "categories": [cat.name for cat in item.pin.categories] if item.pin.categories else [],
            "cost": item.pin.cost,
            "post_count": item.pin.posts_count,
        },
        "is_wishlisted": is_wishlisted,
    }