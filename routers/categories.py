from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from database import SessionLocal
from starlette import status
from sqlalchemy.orm import Session
from schemas import CategoryRequest, CategoryResponse
from models import Category, FavoriteCategory
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

@router.get("/", response_model=List[CategoryResponse])
async def get_all_categories(db: db_dependency):
    categories = db.query(Category).all()
    if not categories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No categories found")
    return categories

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_category(db: db_dependency, cat: CategoryRequest, user: user_dependency):
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if not cat.name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category name is required")
    categories = db.query(Category).all()
    for category in categories:
        if category.name == cat.name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category already exists")
    slug = cat.name.lower().replace(" ", "-")
    new_category = Category(
        name=cat.name
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
@router.post("/{id}/favorite", status_code=status.HTTP_202_ACCEPTED)
async def favorite_category(id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    category = db.query(Category).filter(Category.id == id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    new_favorite_category = FavoriteCategory(
        user_id=user["id"],
        category_id=id
    )
    db.add(new_favorite_category)
    db.commit()
    db.refresh(new_favorite_category)
    return {"detail": "Category favorited successfully"}
@router.delete("/{id}/favorite", status_code=status.HTTP_200_OK)
async def unfavorite_category(id: int, db: db_dependency, user: user_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    favorite_category = db.query(FavoriteCategory).filter(
        FavoriteCategory.user_id == user["id"],
        FavoriteCategory.category_id == id
    ).first()
    if not favorite_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite category not found")

    db.delete(favorite_category)
    db.commit()
    return {"detail": "Category unfavorited successfully"}