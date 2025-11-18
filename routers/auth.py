from datetime import timedelta, datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from database import SessionLocal
from models import User
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from schemas import CreateUserRequest, Token
import os
from dotenv import load_dotenv
import redis
import json

router = APIRouter(
    prefix = "/auth",
    tags = ["auth"]
)

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION_MINUTES = 1
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
except redis.ConnectionError as e:
    print(f"Redis connection failed: {e}")
    redis_client = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]


def check_login_attempts(email: str):
    if not redis_client:
        return

    key = f"login_attempts:{email}"

    try:
        data = redis_client.get(key)
        if data:
            attempts_data = json.loads(data)

            if attempts_data.get("locked"):
                ttl = redis_client.ttl(key)
                if ttl > 0:
                    time_remaining = ttl // 60
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Account temporarily locked. Try again in {time_remaining} minute(s)."
                    )
    except redis.RedisError as e:
        print(f"Redis error in check_login_attempts: {e}")


def record_failed_attempt(email: str):
    if not redis_client:
        return

    key = f"login_attempts:{email}"

    try:
        data = redis_client.get(key)

        if data:
            attempts_data = json.loads(data)
            attempts_data["count"] += 1
        else:
            attempts_data = {"count": 1, "locked": False}

        if attempts_data["count"] >= MAX_LOGIN_ATTEMPTS:
            attempts_data["locked"] = True
            redis_client.setex(
                key,
                timedelta(minutes=LOCKOUT_DURATION_MINUTES),
                json.dumps(attempts_data)
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Account locked for {LOCKOUT_DURATION_MINUTES} minutes."
            )
        else:
            redis_client.setex(
                key,
                timedelta(hours=24),
                json.dumps(attempts_data)
            )
    except redis.RedisError as e:
        print(f"Redis error in record_failed_attempt: {e}")


def clear_login_attempts(email: str):
    if not redis_client:
        return

    key = f"login_attempts:{email}"

    try:
        redis_client.delete(key)
    except redis.RedisError as e:
        print(f"Redis error in clear_login_attempts: {e}")

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    user = db.query(User).filter(User.email == create_user_request.email).first()
    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if len(CreateUserRequest.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    create_user_model = User(
        email=create_user_request.email,
        username=create_user_request.username,
        hashed_password=pwd_context.hash(create_user_request.password),
    )

    db.add(create_user_model)
    db.commit()

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    check_login_attempts(form_data.username)
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        record_failed_attempt(form_data.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    clear_login_attempts(form_data.username)

    token = create_access_token(user.email, user.id, user.is_admin, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}


def authenticate_user(email: str, password: str, db):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    if user.is_suspended:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is suspended")
    return user

def create_access_token(username: str, user_id: int, is_admin: bool, expires_delta: timedelta | None = None):
    encode = {"sub": username, "id": user_id, "is_admin": is_admin}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        is_admin: bool = payload.get("is_admin")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
        return {"username": username, "id": user_id, "is_admin": is_admin}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

@router.post("/admin-user", status_code=status.HTTP_201_CREATED)
async def create_admin_user(db: db_dependency, create_user_request: CreateUserRequest, user: Annotated[dict, Depends(get_current_user)]):
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create admin users")

    create_user_model = User(
        email=create_user_request.email,
        username=create_user_request.username,
        hashed_password=pwd_context.hash(create_user_request.password),
        is_admin=True,
    )

    db.add(create_user_model)
    db.commit()