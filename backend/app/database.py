import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# 默认使用 PostgreSQL；本地无 PG 时可设 DATABASE_URL=sqlite:///./carbon.db 快速开发
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://carbon:carbon@localhost:5432/carbon",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
