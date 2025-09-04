import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# Allow overriding via env; default to writable subdir ./data
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATA_DIR = os.getenv("DATA_DIR", "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    DATABASE_URL = f"sqlite:///./{DATA_DIR}/app.db"

# check_same_thread=False is required only for SQLite used with threads (uvicorn)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

