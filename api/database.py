import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Local PostgreSQL database URI configured in docker-compose.yml
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgrespassword@localhost:5432/ecoflow"
)

# Connect to database
engine = create_engine(
    DATABASE_URL,
    # pool_pre_ping checks connection health before executing queries
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Dependency generator that yields database sessions and closes them after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
