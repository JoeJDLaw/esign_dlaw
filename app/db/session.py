# File: /srv/apps/esign/app/db/session.py

import os
import sys
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

# Load environment variables
load_dotenv()

# Set up logging to stderr
logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/esign")
logging.debug(f"Using DATABASE_URL: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    # Test the connection
    with engine.connect() as conn:
        logging.debug("Successfully connected to database")
except Exception as e:
    logging.error(f"Failed to connect to database: {str(e)}", exc_info=True)
    raise

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_engine():
    return engine

def get_session():
    try:
        session = SessionLocal()
        # Test the session using text()
        session.execute(text("SELECT 1"))
        return session
    except Exception as e:
        logging.error(f"Failed to create database session: {str(e)}", exc_info=True)
        raise