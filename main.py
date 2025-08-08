from contextlib import asynccontextmanager
from random import choices
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import models
from database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Hello, World!"}

@app.get("/account/{id}")
def get_account():
    pass

@app.get("/account/{id}/wishlist")
def get_wishlist():
    pass

@app.get("/account/{id}/visited")
def get_visited():
    pass

@app.get("/account/{id}/comments")
def get_comments():
    pass

@app.get("/post")
def get_posts():
    pass

@app.get("/post/{id}/comments")
def get_post_comments():
    pass

@app.get("/post/{id}/likes")
def get_post_likes():
    pass

@app.get("/post/{id}/media")
def get_post_media():
    pass

