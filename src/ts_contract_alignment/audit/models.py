"""SQLAlchemy models for the audit system."""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class DocumentModel(Base):
    """Document table model."""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    doc_type = Column(String(10), nullable=False)
    upload_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    parsed_content = Column(JSONB)
    metadata_ = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("doc_type IN ('docx', 'pdf')", name="check_doc_type"),
        Index("idx_documents_doc_type", "doc_type"),
        Index("idx_documents_upload_timestamp", "upload_timestamp"),
    )


class TSExtractionModel(Base):
    """TS extraction results table model."""
    __tablename__ = "ts_extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    extraction_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    terms = Column(JSONB, nullable=False)
    unrecognized_sections = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_ts_extractions_document_id", "document_id"),
    )


class TemplateAnalysisModel(Base):
    """Template analysis results table model."""
    __tablename__ = "template_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    analysis_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    clauses = Column(JSONB, nullable=False)
    structure_map = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_template_analyses_document_id", "document_id"),
    )


class AlignmentModel(Base):
    """Alignment results table model."""
    __tablename__ = "alignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    template_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    alignment_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    matches = Column(JSONB, nullable=False)
    unmatched_terms = Column(JSONB)
    unmatched_clauses = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_alignments_ts_document_id", "ts_document_id"),
        Index("idx_alignments_template_document_id", "template_document_id"),
    )


class GeneratedContractModel(Base):
    """Generated contracts table model."""
    __tablename__ = "generated_contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alignment_id = Column(UUID(as_uuid=True), ForeignKey("alignments.id", ondelete="CASCADE"), nullable=False)
    generation_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    modifications = Column(JSONB, nullable=False)
    revision_tracked_path = Column(String(500))
    clean_version_path = Column(String(500))
    status = Column(String(20), default="draft")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'reviewing', 'finalized')", name="check_contract_status"),
        Index("idx_generated_contracts_alignment_id", "alignment_id"),
        Index("idx_generated_contracts_status", "status"),
    )


class ReviewSessionModel(Base):
    """Review sessions table model."""
    __tablename__ = "review_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("generated_contracts.id", ondelete="CASCADE"), nullable=False)
    session_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    items = Column(JSONB, nullable=False)
    status = Column(String(20), default="in_progress")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'completed', 'cancelled')", name="check_session_status"),
        Index("idx_review_sessions_contract_id", "contract_id"),
        Index("idx_review_sessions_status", "status"),
    )


class AuditEventModel(Base):
    """Audit events table model."""
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(String(100), nullable=True)
    details = Column(JSONB)
    metadata_ = Column("metadata", JSONB)

    __table_args__ = (
        Index("idx_audit_events_event_type", "event_type"),
        Index("idx_audit_events_timestamp", "timestamp"),
        Index("idx_audit_events_document_id", "document_id"),
        Index("idx_audit_events_user_id", "user_id"),
    )


class ConfigurationModel(Base):
    """Configuration table model."""
    __tablename__ = "configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_type = Column(String(50), nullable=False)
    config_data = Column(JSONB, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(String(5), default="true")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("config_type IN ('terminology', 'rules', 'templates')", name="check_config_type"),
        Index("idx_configurations_config_type", "config_type"),
        Index("idx_configurations_is_active", "is_active"),
    )


class VersionHistoryModel(Base):
    """Version history table model for rollback support."""
    __tablename__ = "version_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_version_history_entity", "entity_type", "entity_id"),
        Index("idx_version_history_version", "entity_type", "entity_id", "version"),
    )
