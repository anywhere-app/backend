from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import Annotated, Optional
from fastapi.params import Form
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session, joinedload
from models import Post, Pin, Comment, CommentLike, PostLike
from schemas import CommentRequest
from routers.auth import get_current_user
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv

router = APIRouter(
    prefix="/posts",
    tags=["posts"]
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
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "media"))
MEDIA_DIR = BASE_DIR / MEDIA_DIR
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = os.getenv("BASE_URL", "http://") #TODO pridat IP

MAX_IMAGE_SIZE = 20 * 1024 * 1024
MAX_VIDEO_SIZE = 400 * 1024 * 1024
MAX_MEDIA_COUNT = 10

@router.get("/")
async def get_all_posts(db: db_dependency):
    posts = db.query(Post).options(joinedload(Post.pin), joinedload(Post.user)).all()
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No posts found")
    return [serialize_post(post) for post in posts]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_post(db: db_dependency,
                      user: user_dependency,
                      title: str | None = Form(None),
                      description: str | None = Form(None),
                      pin_id: int = Form(...),
                      media: UploadFile = File(...)
                      ):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    pin = db.query(Pin).filter(Pin.id == pin_id).first()
    if not pin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pin not found")

    if media.content_type not in ["image/jpeg", "image/png", "image/gif", "video/mp4"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported media type")

    user_dir = MEDIA_DIR / str(user["id"])
    user_dir.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(media.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = user_dir / unique_name
    file_size = 0
    max_size = MAX_VIDEO_SIZE if 'video' in media.content_type else MAX_IMAGE_SIZE

    with open(file_path, "wb") as f:
        while chunk := await media.read(1024 * 1024):  # 1MB chunks
            file_size += len(chunk)
            if file_size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File too large. Max size: {max_size / (1024 * 1024):.0f}MB"
                )
            f.write(chunk)

    media_url = f"/media/{user['id']}/{unique_name}"

    new_post = Post(
        user_id=user["id"],
        pin_id=pin_id,
        title=title,
        description=description,
        media_url=media_url,
    )

    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return serialize_post(new_post)


@router.get("/{post_id}")
async def get_post(db: db_dependency, post_id: int):
    post = db.query(Post).options(joinedload(Post.pin), joinedload(Post.user)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return serialize_post(post)


@router.delete("/{post_id}")
async def delete_post(db: db_dependency, post_id: int, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user["id"]).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Post not found or you do not have permission to delete it")

    db.delete(post)
    db.commit()
    return {"detail": "Post deleted successfully"}


@router.post("/{post_id}/like", status_code=status.HTTP_202_ACCEPTED)
async def like_post(db: db_dependency,
                    post_id: int,
                    user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    existing_like = db.query(PostLike).filter(PostLike.post_id == post_id, PostLike.user_id == user["id"]).first()
    if existing_like:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already liked this post")

    post.like_count += 1
    post_like = PostLike(
        user_id=user["id"],
        post_id=post_id
    )
    db.add(post_like)
    db.commit()
    db.refresh(post)
    return serialize_post(post)



@router.get("/{post_id}/comments")
async def get_post_comments(db: db_dependency, post_id: int):
    post = db.query(Post).options(joinedload(Post.comments)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comments = post.comments
    if not comments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comments found for this post")
    return [serialize_comment(comment) for comment in comments]


@router.post("/{post_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(user: user_dependency,
                         db: db_dependency,
                         post_id: int,
                         comment_request: CommentRequest):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    new_comment = Comment(
        post_id=post_id,
        user_id=user["id"],
        content=comment_request.content,
        parent_id=comment_request.parent_id if comment_request.parent_id else None
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return serialize_comment(new_comment)


@router.delete("/comments/{comment_id}")
async def delete_comment(db: db_dependency,
                         comment_id: int,
                         user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.user_id == user["id"]).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Comment not found or you do not have permission to delete it")

    db.delete(comment)
    db.commit()
    return {"detail": "Comment deleted successfully"}


@router.post("/{post_id}/comments/{comment_id}/like", status_code=status.HTTP_202_ACCEPTED)
async def create_like(db: db_dependency,
                      post_id: int,
                      comment_id: int,
                      user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.post_id == post_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    existing_like = db.query(CommentLike).filter(CommentLike.comment_id == comment_id, CommentLike.user_id == user["id"]).first()
    if existing_like:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already liked this comment")

    comment.like_count += 1
    comment_like = CommentLike(
        user_id=user["id"],
        comment_id=comment_id
    )
    db.add(comment_like)
    db.commit()
    db.refresh(comment)
    return serialize_comment(comment)


def serialize_post(post: Post):
    return {
        "id": post.id,
        "user_id": post.user_id,
        "username": post.user.username,
        "pin_id": post.pin_id,
        "pin_title": post.pin.title,
        "title": post.title,
        "description": post.description,
        "media_url": post.media_url,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "share_count": post.share_count,
        "created_at": post.created_at,
    }


def serialize_comment(comment):
    return {
        "id": comment.id,
        "user_id": comment.user_id,
        "username": comment.user.username,
        "post_id": comment.post_id,
        "content": comment.content,
        "parent_id": comment.parent_id,
        "created_at": comment.created_at,
        "like_count": comment.like_count,
    }
