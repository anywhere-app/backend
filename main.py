from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, status
from models import *
from database import Base, engine, SessionLocal
from sqlalchemy.orm import Session
from routers import auth, pins, categories
from routers.auth import get_current_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)
app.include_router(pins.router)
app.include_router(categories.router)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@app.get("/")
async def root(db: db_dependency, user: user_dependency | None = None):
    if user:
        return {"message": f"Hello, {user['username']}!"}
    return {"message": "Hello, World!"}

@app.get("/account/{id}")
async def get_account_by_id(id: int):
    pass

@app.get("/account")
async def get_account(user: user_dependency, db: db_dependency):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    account = db.query(User).filter_by(id=user['id']).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account

@app.get("/account/{id}/visited")
async def get_visited(id: int):
    pass

@app.get("/account/{id}/comments")
async def get_comments(id: int):
    pass


