import os
import uuid
from datetime import datetime, UTC
from pathlib import Path
from threading import active_count
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from typing import Annotated, List, Optional
from fastapi.params import File
from sqlalchemy import select
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload, selectinload
from models import Pin, Visit, Wishlist, User, Follow, Comment, Post, FavoriteCategory, PinCategory
from schemas import UserResponse, FollowResponse, SuspensionRequest, SimpleUserResponse, VisitResponse, WishlistResponse
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
load_dotenv()
MEDIA_DIR = Path(os.getenv("MEDIA_DIR"))


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
async def update_user(db: db_dependency,
                      user: user_dependency,
                      username: Optional[str] = Form(None),
                      bio: Optional[str] = Form(None),
                      media: Optional[UploadFile] = File(None)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    account = db.query(User).filter(User.id == user["id"]).first()
    if username is not None or not "":
        account.username = username
    if bio is not None or not "":
        account.bio = bio
    if media is not None:
        if media.content_type not in ["image/jpeg", "image/png", "image/tiff", "image/webp"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Allowed types: JPEG, PNG, TIFF, WEBP"
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
        account.pfp_url = media_url

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

@router.get("/visited", response_model=list[VisitResponse])
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
            joinedload(Visit.pin).joinedload(Pin.categories).joinedload(PinCategory.category)
        )
        .outerjoin(wq, wq.c.pin_id == Visit.pin_id)
        .filter(Visit.user_id == user["id"])
        .all()
    )

    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No visited pins found")

    return [serialize_visit_item(item[0], is_wishlisted=item[1]) for item in visit]


@router.get("/wishlist", response_model=list[WishlistResponse])
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
            joinedload(Wishlist.pin).joinedload(Pin.categories).joinedload(PinCategory.category)
        )
        .outerjoin(vq, vq.c.pin_id == Wishlist.pin_id)
        .filter(Wishlist.user_id == user["id"])
        .all()
    )

    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    return [serialize_wishlist_item(item[0], is_visited=item[1]) for item in wishlist]


@router.post("/visited", response_model=VisitResponse)
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

    visited_item = db.query(Visit).options(
        joinedload(Visit.pin).joinedload(Pin.categories).joinedload(PinCategory.category)
    ).filter(Visit.user_id == user["id"], Visit.pin_id == pin_id).first()

    is_wishlisted = db.query(Wishlist).filter(
        Wishlist.pin_id == pin_id,
        Wishlist.user_id == user["id"]
    ).first() is not None

    return serialize_visit_item(visited_item, is_wishlisted=is_wishlisted)


@router.post("/wishlist", response_model=WishlistResponse)
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

    wishlist_item = db.query(Wishlist).options(
        joinedload(Wishlist.pin).joinedload(Pin.categories).joinedload(PinCategory.category)
    ).filter(Wishlist.user_id == user["id"], Wishlist.pin_id == pin_id).first()

    is_visited = db.query(Visit).filter(
        Visit.pin_id == pin_id,
        Visit.user_id == user["id"]
    ).first() is not None

    return serialize_wishlist_item(wishlist_item, is_visited=is_visited)


@router.delete("/visited/{pin_id}")
async def remove_from_visited(pin_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    visit = db.query(Visit).filter(Visit.pin_id == pin_id, Visit.user_id == user["id"]).first()
    if not visit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin not found in visited list")
    db.delete(visit)
    db.commit()
    return {"message": "Pin removed from visited list"}


@router.delete("/wishlist/{pin_id}")
async def remove_from_wishlist(pin_id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    wishlist = db.query(Wishlist).filter(Wishlist.pin_id == pin_id, Wishlist.user_id == user["id"]).first()
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin not found in wishlist")
    db.delete(wishlist)
    db.commit()
    return {"message": "Pin removed from wishlist"}


@router.get("/{id}", response_model=UserResponse)
async def get_user_by_id(id: int, db: db_dependency, user: user_dependency):
    if not user["is_admin"] and user["id"] != id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    result = db.execute(
        select(User)
        .where(User.id == id)
        .options(
            selectinload(User.favorite_categories).selectinload(FavoriteCategory.category)
        )
    )
    account = result.scalars().first()
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

@router.get("/{id}/visited", response_model=list[VisitResponse])
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
            joinedload(Visit.pin).joinedload(Pin.categories).joinedload(PinCategory.category)
        )
        .outerjoin(wq, wq.c.pin_id == Visit.pin_id)
        .filter(Visit.user_id == id)
        .all()
    )

    if not visited:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No visited pins found")

    return [serialize_visit_item(item[0], is_wishlisted=item[1]) for item in visited]


@router.get("/{id}/wishlist", response_model=list[WishlistResponse])
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
            joinedload(Wishlist.pin).joinedload(Pin.categories).joinedload(PinCategory.category)
        )
        .outerjoin(vq, vq.c.pin_id == Wishlist.pin_id)
        .filter(Wishlist.user_id == id)
        .all()
    )

    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    return [serialize_wishlist_item(item[0], is_visited=item[1]) for item in wishlist]


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


def serialize_wishlist_item(item: Wishlist, is_visited: bool = False):
    return {
        "pin_id": item.pin.id,
        "added_at": item.added_at,
        "pin": {
            "id": item.pin.id,
            "slug": item.pin.slug,
            "title": item.pin.title,
            "title_image_url": item.pin.title_image_url,
            "description": item.pin.description,
            "coordinates": mapping(to_shape(item.pin.coordinates)),
            "categories": [cat.category.name for cat in item.pin.categories] if item.pin.categories else [],
            "cost": item.pin.cost,
            "post_count": item.pin.posts_count,
            "is_wishlisted": True,
            "is_visited": is_visited,
        }
    }


def serialize_visit_item(item: Visit, is_wishlisted: bool = False):
    return {
        "pin_id": item.pin.id,
        "added_at": item.visited_at,
        "pin": {
            "id": item.pin.id,
            "slug": item.pin.slug,
            "title": item.pin.title,
            "title_image_url": item.pin.title_image_url,
            "description": item.pin.description,
            "coordinates": mapping(to_shape(item.pin.coordinates)),
            "categories": [cat.category.name for cat in item.pin.categories] if item.pin.categories else [],
            "cost": item.pin.cost,
            "post_count": item.pin.posts_count,
            "is_wishlisted": is_wishlisted,
            "is_visited": True,
        }
    }