from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, WebSocket
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
app.include_router(auth.router)
app.include_router(pins.router)
app.include_router(categories.router)
app.include_router(user.router)
app.include_router(hangouts.router)
app.include_router(posts.router)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@app.get("/")
async def root(user: user_dependency | None = None):
    if user:
        return {"message": f"Hello, {user['username']}!"}
    return {"message": "Hello, World!"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: db_dependency):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()