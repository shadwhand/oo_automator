from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

DATABASE_PATH = Path("data/oo_automator.db")


def get_engine(db_path: Path = DATABASE_PATH):
    """Get or create database engine."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    return engine


def init_db(engine=None):
    """Initialize database tables."""
    if engine is None:
        engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine


def get_session(engine=None):
    """Get a database session."""
    if engine is None:
        engine = get_engine()
    return Session(engine)
