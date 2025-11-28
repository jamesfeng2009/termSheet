"""Unit tests for the Audit Logger."""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.ts_contract_alignment.interfaces.audit import AuditEvent, AuditEventType
from src.ts_contract_alignment.audit.audit_logger import AuditLogger


class MockSession:
    """Mock SQLAlchemy session for testing."""
    
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self._execute_results = []
    
    def add(self, obj):
        self.added.append(obj)
    
    def commit(self):
        self.committed = True
    
    def rollback(self):
        self.rolled_back = True
    
    def close(self):
        self.closed = True
    
    def execute(self, query):
        result = MagicMock()
        if self._execute_results:
            result.scalars.return_value.all.return_value = self._execute_results
            result.scalar.return_value = self._execute_results[0] if self._execute_results else None
        else:
            result.scalars.return_value.all.return_value = []
            result.scalar.return_value = None
        return result
    
    def set_execute_results(self, results):
        self._execute_results = results


class MockDatabaseManager:
    """Mock DatabaseManager for testing."""
    
    def __init__(self):
        self._session = MockSession()
    
    def get_session(self):
        return MockContextManager(self._session)
    
    def close(self):
        pass


class MockContextManager:
    """Mock context manager for session."""
    
    def __init__(self, session):
        self._session = session
    
    def __enter__(self):
        return self._session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._session.commit()
        else:
            self._session.rollback()
        self._session.close()
        return False


class TestAuditLogger:
    """Tests for AuditLogger class."""
    
    def test_log_event_adds_to_session(self):
        """Test that log_event adds an event to the database session."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        event = AuditEvent(
            id=str(uuid.uuid4()),
            event_type=AuditEventType.DOCUMENT_PARSED,
            timestamp=datetime.utcnow(),
            document_id=str(uuid.uuid4()),
            details={"filename": "test.docx"},
        )
        
        logger.log_event(event)
        
        assert len(db_manager._session.added) == 1
        assert db_manager._session.committed
    
    def test_log_document_parsed(self):
        """Test logging a document parsed event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        logger.log_document_parsed(
            document_id=doc_id,
            filename="test.docx",
            doc_type="docx",
            section_count=5,
            user_id="user123",
        )
        
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.DOCUMENT_PARSED.value
        assert added_model.details["filename"] == "test.docx"
        assert added_model.details["section_count"] == 5
    
    def test_log_terms_extracted(self):
        """Test logging a terms extracted event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        logger.log_terms_extracted(
            document_id=doc_id,
            term_count=10,
            categories=["investment_amount", "valuation"],
        )
        
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.TERMS_EXTRACTED.value
        assert added_model.details["term_count"] == 10
    
    def test_log_alignment_completed(self):
        """Test logging an alignment completed event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        ts_doc_id = str(uuid.uuid4())
        template_doc_id = str(uuid.uuid4())
        logger.log_alignment_completed(
            ts_document_id=ts_doc_id,
            template_document_id=template_doc_id,
            match_count=8,
            unmatched_term_count=2,
        )
        
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.ALIGNMENT_COMPLETED.value
        assert added_model.details["match_count"] == 8
    
    def test_log_match_created(self):
        """Test logging a match created event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        logger.log_match_created(
            document_id=doc_id,
            ts_term_id="term_001",
            clause_id="clause_005",
            match_method="rule_keyword",
            confidence=0.92,
            action="override",
        )
        
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.MATCH_CREATED.value
        assert added_model.details["confidence"] == 0.92
    
    def test_log_contract_generated(self):
        """Test logging a contract generated event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        contract_id = str(uuid.uuid4())
        ts_doc_id = str(uuid.uuid4())
        template_doc_id = str(uuid.uuid4())
        logger.log_contract_generated(
            contract_id=contract_id,
            ts_document_id=ts_doc_id,
            template_document_id=template_doc_id,
            modification_count=15,
        )
        
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.CONTRACT_GENERATED.value
        assert added_model.details["modification_count"] == 15
    
    def test_log_modification_applied(self):
        """Test logging a modification applied event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        logger.log_modification_applied(
            document_id=doc_id,
            modification_id="mod_001",
            action_type="insert",
            source_ts_paragraph_id="para_001",
            confidence=0.85,
        )
        
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.MODIFICATION_APPLIED.value
        assert added_model.details["action_type"] == "insert"
    
    def test_log_review_action(self):
        """Test logging a review action event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        logger.log_review_action(
            document_id=doc_id,
            session_id=session_id,
            modification_id="mod_001",
            action="accept",
            user_id="user123",
            comment="Looks good",
        )
        
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.REVIEW_ACTION.value
        assert added_model.user_id == "user123"
        assert added_model.details["action"] == "accept"


class TestAuditLoggerExport:
    """Tests for audit log export functionality."""
    
    def test_export_json_format(self):
        """Test exporting audit log in JSON format."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        # Create mock events
        doc_id = str(uuid.uuid4())
        mock_events = [
            AuditEvent(
                id=str(uuid.uuid4()),
                event_type=AuditEventType.DOCUMENT_PARSED,
                timestamp=datetime.utcnow(),
                document_id=doc_id,
                details={"filename": "test.docx"},
            ),
        ]
        
        # Mock the get_events method
        with patch.object(logger, 'get_events', return_value=mock_events):
            result = logger.export_log(doc_id, format="json")
        
        data = json.loads(result)
        assert "export_timestamp" in data
        assert data["event_count"] == 1
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "document_parsed"
        assert "mapping_table" in data
        assert "confidence_summary" in data
    
    def test_export_json_with_mapping_table(self):
        """Test that JSON export includes mapping table from match events."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        mock_events = [
            AuditEvent(
                id=str(uuid.uuid4()),
                event_type=AuditEventType.MATCH_CREATED,
                timestamp=datetime.utcnow(),
                document_id=doc_id,
                details={
                    "ts_term_id": "term_001",
                    "clause_id": "clause_005",
                    "match_method": "rule_keyword",
                    "confidence": 0.92,
                    "action": "override",
                },
            ),
            AuditEvent(
                id=str(uuid.uuid4()),
                event_type=AuditEventType.MATCH_CREATED,
                timestamp=datetime.utcnow(),
                document_id=doc_id,
                details={
                    "ts_term_id": "term_002",
                    "clause_id": "clause_010",
                    "match_method": "semantic",
                    "confidence": 0.85,
                    "action": "insert",
                },
            ),
        ]
        
        with patch.object(logger, 'get_events', return_value=mock_events):
            result = logger.export_log(doc_id, format="json")
        
        data = json.loads(result)
        assert len(data["mapping_table"]) == 2
        assert data["mapping_table"][0]["ts_term_id"] == "term_001"
        assert data["mapping_table"][0]["confidence"] == 0.92
        assert data["confidence_summary"]["total_matches"] == 2
        assert data["confidence_summary"]["average_confidence"] == 0.885
        assert data["confidence_summary"]["min_confidence"] == 0.85
        assert data["confidence_summary"]["max_confidence"] == 0.92
    
    def test_export_csv_format(self):
        """Test exporting audit log in CSV format."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        mock_events = [
            AuditEvent(
                id=str(uuid.uuid4()),
                event_type=AuditEventType.DOCUMENT_PARSED,
                timestamp=datetime.utcnow(),
                document_id=doc_id,
                details={"filename": "test.docx"},
            ),
        ]
        
        with patch.object(logger, 'get_events', return_value=mock_events):
            result = logger.export_log(doc_id, format="csv")
        
        lines = result.strip().split('\n')
        assert len(lines) == 2  # Header + 1 data row
        assert "id,event_type,timestamp" in lines[0]
        assert "document_parsed" in lines[1]
    
    def test_export_invalid_format_raises_error(self):
        """Test that invalid export format raises ValueError."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        doc_id = str(uuid.uuid4())
        with pytest.raises(ValueError) as exc_info:
            logger.export_log(doc_id, format="xml")
        
        assert "Unsupported export format" in str(exc_info.value)


class TestVersionHistory:
    """Tests for version history functionality."""
    
    def test_save_version_creates_record(self):
        """Test that save_version creates a version record."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        entity_id = str(uuid.uuid4())
        snapshot = {"data": "test", "value": 123}
        
        version = logger.save_version(
            entity_type="document",
            entity_id=entity_id,
            snapshot=snapshot,
        )
        
        assert version == 1
        assert len(db_manager._session.added) == 1
    
    def test_get_version_history_returns_list(self):
        """Test that get_version_history returns version list."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        entity_id = str(uuid.uuid4())
        
        # Mock returns empty list
        result = logger.get_version_history(
            entity_type="document",
            entity_id=entity_id,
        )
        
        assert isinstance(result, list)
    
    def test_rollback_to_version_logs_event(self):
        """Test that rollback logs an audit event."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        entity_id = str(uuid.uuid4())
        snapshot = {"data": "test"}
        
        # Mock get_version to return a snapshot
        with patch.object(logger, 'get_version', return_value=snapshot):
            with patch.object(logger, 'save_version', return_value=2):
                result = logger.rollback_to_version(
                    entity_type="document",
                    entity_id=entity_id,
                    version=1,
                )
        
        assert result == snapshot
        # Check that an audit event was logged
        assert len(db_manager._session.added) == 1
        added_model = db_manager._session.added[0]
        assert added_model.event_type == AuditEventType.MODIFICATION_APPLIED.value
        assert added_model.details["action"] == "rollback"
    
    def test_rollback_to_nonexistent_version_returns_none(self):
        """Test that rollback to nonexistent version returns None."""
        db_manager = MockDatabaseManager()
        logger = AuditLogger(db_manager=db_manager)
        
        entity_id = str(uuid.uuid4())
        
        # Mock get_version to return None
        with patch.object(logger, 'get_version', return_value=None):
            result = logger.rollback_to_version(
                entity_type="document",
                entity_id=entity_id,
                version=999,
            )
        
        assert result is None
