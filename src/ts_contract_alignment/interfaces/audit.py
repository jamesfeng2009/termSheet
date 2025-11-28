"""Audit logger interface for the TS Contract Alignment System."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class AuditEventType(Enum):
    """Types of audit events tracked by the system."""
    DOCUMENT_PARSED = "document_parsed"
    TERMS_EXTRACTED = "terms_extracted"
    TEMPLATE_ANALYZED = "template_analyzed"
    ALIGNMENT_COMPLETED = "alignment_completed"
    MATCH_CREATED = "match_created"
    CONTRACT_GENERATED = "contract_generated"
    MODIFICATION_APPLIED = "modification_applied"
    REVIEW_ACTION = "review_action"
    EXPORT_COMPLETED = "export_completed"


@dataclass
class AuditEvent:
    """
    Audit event record.
    
    Represents a single auditable event in the system,
    including timestamp, related entities, and event details.
    """
    id: str
    event_type: AuditEventType
    timestamp: datetime
    document_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    details: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AuditLog:
    """
    Collection of audit events.
    
    Represents a log of audit events for a processing session
    or document pair.
    """
    events: List[AuditEvent] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def __post_init__(self):
        if self.events is None:
            self.events = []


class IAuditLogger(ABC):
    """
    Abstract interface for audit logging.
    
    Implementations of this interface handle recording and
    querying of audit events for traceability and compliance.
    """

    @abstractmethod
    def log_event(self, event: AuditEvent) -> None:
        """
        Record an audit event.
        
        Args:
            event: The audit event to record.
        """
        pass

    @abstractmethod
    def get_events(
        self,
        document_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AuditEvent]:
        """
        Query audit events with optional filters.
        
        Args:
            document_id: Filter by document ID.
            event_type: Filter by event type.
            start_time: Filter events after this time.
            end_time: Filter events before this time.
            
        Returns:
            List of matching audit events.
        """
        pass

    @abstractmethod
    def export_log(
        self,
        document_id: str,
        format: str = "json",
    ) -> str:
        """
        Export audit log for a document.
        
        Args:
            document_id: The document ID to export logs for.
            format: Export format ("json" or "csv").
            
        Returns:
            Exported log content as a string.
            
        Raises:
            ValueError: If format is not supported.
        """
        pass
