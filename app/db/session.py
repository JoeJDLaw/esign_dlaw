"""
Database session management for the eSign application.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from log_utils.logging_config import configure_logging

# Configure logging
logger = configure_logging(
    name="esign.db",
    logfile="esign.log",
    level=None  # Will use environment-based level
)

# Load environment variables
load_dotenv("/srv/shared/.env")

DATABASE_URL = os.getenv("ESIGN_DATABASE_URL", "postgresql://localhost/esign")
logger.debug("Using DATABASE_URL: %s", DATABASE_URL)

try:
    engine = create_engine(DATABASE_URL)
    # Test the connection
    with engine.connect() as conn:
        logger.debug("Successfully connected to database")
except Exception as e:
    logger.error("Failed to connect to database: %s", str(e), exc_info=True)
    raise

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_engine():
    """Get the SQLAlchemy engine instance."""
    return engine

def get_session():
    """Get a new database session."""
    try:
        session = SessionLocal()
        # Test the session using text()
        session.execute(text("SELECT 1"))
        return session
    except Exception as e:
        logger.error("Failed to create database session: %s", str(e), exc_info=True)
        raise
