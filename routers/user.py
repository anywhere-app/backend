from datetime import datetime, UTC
from threading import active_count
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from sqlalchemy import select
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload, selectinload
from models import Pin, Visit, Wishlist, User, Follow, Comment, Post, FavoriteCategory
from schemas import UserResponse, FollowResponse, SuspensionRequest, SimpleUserResponse
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
    return account
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
    return users
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

@router.get("/{id}", response_model=UserResponse)
async def get_user_by_id(id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    account = db.query(User).filter(User.id == id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return account

@router.get("/{id}/followers", response_model=list[FollowResponse])
async def get_followers_by_id(id: int, db: db_dependency, user: user_dependency):
    followers = db.query(Follow).filter(Follow.following_id == id).all()
    if not followers:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No followers found for this user")
    return followers

@router.get("/{id}/following", response_model=list[FollowResponse])
async def get_following_by_id(id: int, db: db_dependency, user: user_dependency):
    following = db.query(Follow).filter(Follow.follower_id == id).all()
    if not following:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No following found for this user")
    return following

@router.post("/{id}/follow", response_model=FollowResponse)
async def follow(db: db_dependency, id: int, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    account = db.query(User).filter(User.id == id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    follow = db.query(Follow).filter(Follow.follower_id == user["id"], Follow.following_id == id).first()
    if follow:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already following this user")
    new_follow = Follow(
        follower_id=user["id"],
        following_id=id
    )
    db.add(new_follow)
    db.commit()
    db.refresh(new_follow)
    return new_follow

@router.delete("/{id}/follow")
async def unfollow_user(id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    account = db.query(User).filter(User.id == id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    follow = db.query(Follow).filter(Follow.follower_id == user["id"], Follow.following_id == id).first()
    if not follow:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not following this user")
    db.delete(follow)
    db.commit()
    return {"message": "Unfollowed successfully"}

@router.get("/{id}/visited")
async def get_visited_by_id(id: int, db: db_dependency, user: user_dependency):
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

@router.get("/{id}/comments")
async def get_comments_by_id(id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    comments = db.query(Comment).filter(Comment.user_id == id).all()
    if not comments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comments found for this user")
    return [serialize_comment(comment) for comment in comments]

@router.get("/{id}/liked-comments")
async def get_liked_comments_by_id(id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    liked_comments = db.query(Comment).filter(Comment.likes.any(user_id=id)).all()
    if not liked_comments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No liked comments found for this user")
    return [serialize_comment(comment) for comment in liked_comments]

@router.get("/{id}/liked-posts")
async def get_liked_posts_by_id(id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    liked_posts = db.query(Post).filter(Post.likes.any(user_id=id)).all()
    return [serialize_post(post) for post in liked_posts]

@router.get("/{id}/posts")
async def get_posts_by_id(id: int, user: user_dependency, db: db_dependency):
    posts = db.query(Post).options(joinedload(Post.user), joinedload(Post.pin)).filter(Post.user_id == id).all()
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No posts found for this user")
    return [serialize_post(post) for post in posts]


@router.post("/{id}/suspend", response_model=UserResponse)
async def suspend_user(id: int, db: db_dependency, user: user_dependency, suspension_request: SuspensionRequest):
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    account = db.query(User).filter(User.id == id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if account.is_suspended:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already suspended")

    account.is_suspended = True
    account.suspended_at = datetime.now(UTC)
    account.suspended_until = account.suspended_at + suspension_request.duration
    account.suspended_reason = suspension_request.reason
    db.commit()
    db.refresh(account)
    return account




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