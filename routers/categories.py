from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session
from schemas import CategoryRequest
from models import Category
from routers.auth import get_current_user

router = APIRouter(
    prefix = "/categories",
    tags = ["categories"]
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
async def get_all_categories(db: db_dependency):
    categories = db.query(Category).all()
    if not categories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No categories found")
    return categories

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_category(db: db_dependency, cat: CategoryRequest, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not cat.name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category name is required")
    categories = db.query(Category).all()
    for category in categories:
        if category.name == cat.name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category already exists")
    new_category = Category(
        name=cat.name,
        description=cat.description
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category

@router.get("/{id}")
async def get_category_by_id(id: int, db: db_dependency):
    category = db.query(Category).filter(Category.id == id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category