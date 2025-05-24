# File: /srv/apps/esign/app/db/models.py

from sqlalchemy import (
    Column, String, DateTime, Enum, JSON, Text, Boolean, Integer
)
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import declarative_base
import enum
import uuid
import datetime

Base = declarative_base()

class SignatureStatus(enum.Enum):
    pending = "pending"
    signed = "signed"
    expired = "expired"
    canceled = "canceled"

class SignatureRequest(Base):
    __tablename__ = "signature_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_name = Column(String, nullable=False)
    client_email = Column(String, nullable=False)
    template_type = Column(String, nullable=False)  # e.g. 'case_eval' or 'case_eval_plus_records'
    pdf_path = Column(String, nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signed_ip = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    audit_log = Column(JSON, nullable=True)
    salesforce_case_id = Column(String, nullable=False)
    status = Column(Enum(SignatureStatus), default=SignatureStatus.pending)
    token_hash = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)