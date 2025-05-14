# File: /srv/apps/esign/app/db/session.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/esign")

engine = create_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_engine():
    return engine

def get_session():
    return SessionLocal()