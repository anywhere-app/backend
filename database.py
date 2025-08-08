from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://postgres:pass@localhost/anywhere"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass