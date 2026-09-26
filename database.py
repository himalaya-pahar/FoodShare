from typing import Annotated

from fastapi import Depends
from sqlmodel import SQLModel, Session, create_engine

from config import DATABASE_URL


IS_SQLITE = DATABASE_URL.startswith("sqlite")


if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"prepare_threshold": None},
    )


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]