"""Audit logger implementation for the TS Contract Alignment System."""

import csv
import io
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..interfaces.audit import AuditEvent, AuditEventType, AuditLog, IAuditLogger
from .database import DatabaseManager
from .models import AuditEventModel, VersionHistoryModel


class AuditLogger(IAuditLogger):
    """
    Audit logger implementation with PostgreSQL backend.
    
    Records all system events for traceability and compliance,
    supports querying and exporting audit logs.
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        database_url: Optional[str] = None,
    ):
        """
        Initialize the audit logger.
        
        Args:
            db_manager: Optional DatabaseManager instance. If not provided,
                       a new one will be created.
            database_url: Database URL for creating a new DatabaseManager.
        """
        if db_manager is not None:
            self._db_manager = db_manager
            self._owns_db_manager = False
        else:
            self._db_manager = DatabaseManager(database_url=database_url)
            self._owns_db_manager = True
    
    def _to_model(self, event: AuditEvent) -> AuditEventModel:
        """Convert AuditEvent dataclass to SQLAlchemy model."""
        return AuditEventModel(
            id=uuid.UUID(event.id) if isinstance(event.id, str) else event.id,
            event_type=event.event_type.value if isinstance(event.event_type, AuditEventType) else event.event_type,
            timestamp=event.timestamp,
            document_id=uuid.UUID(event.document_id) if event.document_id else None,
            session_id=uuid.UUID(event.session_id) if event.session_id else None,
            user_id=event.user_id,
            details=event.details or {},
            metadata_=event.metadata or {},
        )

    def _from_model(self, model: AuditEventModel) -> AuditEvent:
        """Convert SQLAlchemy model to AuditEvent dataclass."""
        return AuditEvent(
            id=str(model.id),
            event_type=AuditEventType(model.event_type),
            timestamp=model.timestamp,
            document_id=str(model.document_id) if model.document_id else None,
            session_id=str(model.session_id) if model.session_id else None,
            user_id=model.user_id,
            details=model.details or {},
            metadata=model.metadata_ or {},
        )
    
    def log_event(self, event: AuditEvent) -> None:
        """
        Record an audit event to the database.
        
        Args:
            event: The audit event to record.
        """
        model = self._to_model(event)
        with self._db_manager.get_session() as session:
            session.add(model)
    
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
        with self._db_manager.get_session() as session:
            query = select(AuditEventModel)
            
            conditions = []
            if document_id:
                conditions.append(AuditEventModel.document_id == uuid.UUID(document_id))
            if event_type:
                event_type_value = event_type.value if isinstance(event_type, AuditEventType) else event_type
                conditions.append(AuditEventModel.event_type == event_type_value)
            if start_time:
                conditions.append(AuditEventModel.timestamp >= start_time)
            if end_time:
                conditions.append(AuditEventModel.timestamp <= end_time)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            query = query.order_by(AuditEventModel.timestamp.desc())
            
            result = session.execute(query)
            models = result.scalars().all()
            
            return [self._from_model(m) for m in models]
    
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
        if format not in ("json", "csv"):
            raise ValueError(f"Unsupported export format: {format}. Use 'json' or 'csv'.")
        
        events = self.get_events(document_id=document_id)
        
        if format == "json":
            return self._export_json(events)
        else:
            return self._export_csv(events)
    
    def _export_json(self, events: List[AuditEvent]) -> str:
        """Export events to JSON format with mapping tables and confidence scores."""
        # Extract mapping table entries from match events
        mapping_table = []
        for e in events:
            if e.event_type == AuditEventType.MATCH_CREATED or (
                isinstance(e.event_type, str) and e.event_type == "match_created"
            ):
                mapping_table.append({
                    "ts_term_id": e.details.get("ts_term_id"),
                    "clause_id": e.details.get("clause_id"),
                    "match_method": e.details.get("match_method"),
                    "confidence": e.details.get("confidence"),
                    "action": e.details.get("action"),
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                })
        
        # Extract confidence scores summary
        confidence_scores = [
            entry["confidence"] for entry in mapping_table 
            if entry.get("confidence") is not None
        ]
        
        data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "event_count": len(events),
            "mapping_table": mapping_table,
            "confidence_summary": {
                "total_matches": len(mapping_table),
                "average_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                "min_confidence": min(confidence_scores) if confidence_scores else 0,
                "max_confidence": max(confidence_scores) if confidence_scores else 0,
            },
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type.value if isinstance(e.event_type, AuditEventType) else e.event_type,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "document_id": e.document_id,
                    "session_id": e.session_id,
                    "user_id": e.user_id,
                    "details": e.details,
                    "metadata": e.metadata,
                }
                for e in events
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def _export_csv(self, events: List[AuditEvent]) -> str:
        """Export events to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "id", "event_type", "timestamp", "document_id",
            "session_id", "user_id", "details", "metadata"
        ])
        
        # Write data rows
        for e in events:
            writer.writerow([
                e.id,
                e.event_type.value if isinstance(e.event_type, AuditEventType) else e.event_type,
                e.timestamp.isoformat() if e.timestamp else "",
                e.document_id or "",
                e.session_id or "",
                e.user_id or "",
                json.dumps(e.details, ensure_ascii=False),
                json.dumps(e.metadata, ensure_ascii=False),
            ])
        
        return output.getvalue()

    # ========== Version History Methods ==========
    
    def save_version(
        self,
        entity_type: str,
        entity_id: str,
        snapshot: Dict[str, Any],
    ) -> int:
        """
        Save a version snapshot for an entity.
        
        Args:
            entity_type: Type of entity (e.g., 'document', 'alignment', 'contract').
            entity_id: ID of the entity.
            snapshot: JSON-serializable snapshot of the entity state.
            
        Returns:
            The version number assigned to this snapshot.
        """
        with self._db_manager.get_session() as session:
            # Get the latest version number
            query = select(VersionHistoryModel.version).where(
                and_(
                    VersionHistoryModel.entity_type == entity_type,
                    VersionHistoryModel.entity_id == uuid.UUID(entity_id),
                )
            ).order_by(VersionHistoryModel.version.desc()).limit(1)
            
            result = session.execute(query)
            latest = result.scalar()
            new_version = (latest or 0) + 1
            
            # Create new version record
            version_record = VersionHistoryModel(
                entity_type=entity_type,
                entity_id=uuid.UUID(entity_id),
                version=new_version,
                snapshot=snapshot,
            )
            session.add(version_record)
            
            return new_version
    
    def get_version(
        self,
        entity_type: str,
        entity_id: str,
        version: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a version snapshot for an entity.
        
        Args:
            entity_type: Type of entity.
            entity_id: ID of the entity.
            version: Specific version to retrieve. If None, returns latest.
            
        Returns:
            The snapshot data, or None if not found.
        """
        with self._db_manager.get_session() as session:
            query = select(VersionHistoryModel).where(
                and_(
                    VersionHistoryModel.entity_type == entity_type,
                    VersionHistoryModel.entity_id == uuid.UUID(entity_id),
                )
            )
            
            if version is not None:
                query = query.where(VersionHistoryModel.version == version)
            else:
                query = query.order_by(VersionHistoryModel.version.desc())
            
            query = query.limit(1)
            
            result = session.execute(query)
            record = result.scalar()
            
            return record.snapshot if record else None
    
    def get_version_history(
        self,
        entity_type: str,
        entity_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all version snapshots for an entity.
        
        Args:
            entity_type: Type of entity.
            entity_id: ID of the entity.
            
        Returns:
            List of version records with version number and snapshot.
        """
        with self._db_manager.get_session() as session:
            query = select(VersionHistoryModel).where(
                and_(
                    VersionHistoryModel.entity_type == entity_type,
                    VersionHistoryModel.entity_id == uuid.UUID(entity_id),
                )
            ).order_by(VersionHistoryModel.version.asc())
            
            result = session.execute(query)
            records = result.scalars().all()
            
            return [
                {
                    "version": r.version,
                    "snapshot": r.snapshot,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]
    
    def rollback_to_version(
        self,
        entity_type: str,
        entity_id: str,
        version: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Rollback an entity to a specific version.
        
        This retrieves the snapshot at the specified version and saves it
        as a new version, effectively rolling back to that state.
        
        Args:
            entity_type: Type of entity.
            entity_id: ID of the entity.
            version: Version to rollback to.
            
        Returns:
            The restored snapshot, or None if version not found.
        """
        snapshot = self.get_version(entity_type, entity_id, version)
        if snapshot is None:
            return None
        
        # Save the rollback as a new version
        self.save_version(entity_type, entity_id, snapshot)
        
        # Log the rollback event
        # For contract rollbacks, use entity_id as document_id for easier querying
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.MODIFICATION_APPLIED,
            timestamp=datetime.utcnow(),
            document_id=entity_id,  # Use entity_id for all entity types
            details={
                "action": "rollback",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "rolled_back_to_version": version,
            },
        ))
        
        return snapshot

    # ========== Convenience Logging Methods ==========
    
    def log_document_parsed(
        self,
        document_id: str,
        filename: str,
        doc_type: str,
        section_count: int,
        user_id: Optional[str] = None,
    ) -> None:
        """Log a document parsing event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.DOCUMENT_PARSED,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            user_id=user_id,
            details={
                "filename": filename,
                "doc_type": doc_type,
                "section_count": section_count,
            },
        ))
    
    def log_terms_extracted(
        self,
        document_id: str,
        term_count: int,
        categories: List[str],
        user_id: Optional[str] = None,
    ) -> None:
        """Log a TS terms extraction event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.TERMS_EXTRACTED,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            user_id=user_id,
            details={
                "term_count": term_count,
                "categories": categories,
            },
        ))
    
    def log_template_analyzed(
        self,
        document_id: str,
        clause_count: int,
        fillable_count: int,
        user_id: Optional[str] = None,
    ) -> None:
        """Log a template analysis event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.TEMPLATE_ANALYZED,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            user_id=user_id,
            details={
                "clause_count": clause_count,
                "fillable_count": fillable_count,
            },
        ))
    
    def log_alignment_completed(
        self,
        ts_document_id: str,
        template_document_id: str,
        match_count: int,
        unmatched_term_count: int,
        user_id: Optional[str] = None,
    ) -> None:
        """Log an alignment completion event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.ALIGNMENT_COMPLETED,
            timestamp=datetime.utcnow(),
            document_id=ts_document_id,
            user_id=user_id,
            details={
                "ts_document_id": ts_document_id,
                "template_document_id": template_document_id,
                "match_count": match_count,
                "unmatched_term_count": unmatched_term_count,
            },
        ))
    
    def log_match_created(
        self,
        document_id: str,
        ts_term_id: str,
        clause_id: str,
        match_method: str,
        confidence: float,
        action: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Log a match creation event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.MATCH_CREATED,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            user_id=user_id,
            details={
                "ts_term_id": ts_term_id,
                "clause_id": clause_id,
                "match_method": match_method,
                "confidence": confidence,
                "action": action,
            },
        ))
    
    def log_contract_generated(
        self,
        contract_id: str,
        ts_document_id: str,
        template_document_id: str,
        modification_count: int,
        user_id: Optional[str] = None,
    ) -> None:
        """Log a contract generation event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.CONTRACT_GENERATED,
            timestamp=datetime.utcnow(),
            document_id=ts_document_id,
            user_id=user_id,
            details={
                "contract_id": contract_id,
                "ts_document_id": ts_document_id,
                "template_document_id": template_document_id,
                "modification_count": modification_count,
            },
        ))
    
    def log_modification_applied(
        self,
        document_id: str,
        modification_id: str,
        action_type: str,
        source_ts_paragraph_id: str,
        confidence: float,
        user_id: Optional[str] = None,
    ) -> None:
        """Log a modification application event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.MODIFICATION_APPLIED,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            user_id=user_id,
            details={
                "modification_id": modification_id,
                "action_type": action_type,
                "source_ts_paragraph_id": source_ts_paragraph_id,
                "confidence": confidence,
            },
        ))
    
    def log_review_action(
        self,
        document_id: str,
        session_id: str,
        modification_id: str,
        action: str,
        user_id: str,
        comment: Optional[str] = None,
    ) -> None:
        """Log a user review action event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.REVIEW_ACTION,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            session_id=session_id,
            user_id=user_id,
            details={
                "modification_id": modification_id,
                "action": action,
                "comment": comment,
            },
        ))
    
    def log_export_completed(
        self,
        document_id: str,
        export_path: str,
        export_format: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Log an export completion event."""
        self.log_event(AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.EXPORT_COMPLETED,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            user_id=user_id,
            details={
                "export_path": export_path,
                "export_format": export_format,
            },
        ))
    
    def close(self) -> None:
        """Close the audit logger and release resources."""
        if self._owns_db_manager:
            self._db_manager.close()
