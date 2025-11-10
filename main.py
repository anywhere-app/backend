from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Depends, WebSocket
from database import Base, engine, SessionLocal
from sqlalchemy.orm import Session
from routers import auth, pins, categories, user, hangouts, posts
from routers.auth import get_current_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    #Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth.router, prefix="/api")
app.include_router(pins.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(hangouts.router, prefix="/api")
app.include_router(posts.router, prefix="/api")