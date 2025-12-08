"""Unit tests for review interface components."""

import pytest
from datetime import datetime

from src.ts_contract_alignment.interfaces.review import (
    ReviewAction,
    ReviewItem,
    ReviewSession,
)
from src.ts_contract_alignment.interfaces.generator import (
    GeneratedContract,
    Modification,
)
from src.ts_contract_alignment.models.enums import ActionType
from src.ts_contract_alignment.review.action_handler import ActionHandler
from src.ts_contract_alignment.review.highlight_manager import HighlightManager
from src.ts_contract_alignment.review.diff_highlighter import DiffHighlighter


class TestReviewItem:
    """Test ReviewItem data model."""

    def test_create_review_item(self):
        """Test creating a review item."""
        item = ReviewItem(
            modification_id="mod_001",
            ts_term_id="term_001",
            clause_id="clause_001",
            original_text="Original text",
            new_text="New text",
            confidence=0.85,
        )

        assert item.modification_id == "mod_001"
        assert item.ts_term_id == "term_001"
        assert item.clause_id == "clause_001"
        assert item.action == ReviewAction.PENDING
        assert item.user_comment is None


class TestReviewSession:
    """Test ReviewSession data model."""

    def test_create_review_session(self):
        """Test creating a review session."""
        items = [
            ReviewItem(
                modification_id=f"mod_{i}",
                ts_term_id=f"term_{i}",
                clause_id=f"clause_{i}",
                original_text=f"Original {i}",
                new_text=f"New {i}",
                confidence=0.8,
            )
            for i in range(5)
        ]

        session = ReviewSession(
            id="session_001",
            contract_id="contract_001",
            items=items,
            session_timestamp=datetime.utcnow().isoformat(),
        )

        assert session.id == "session_001"
        assert session.total_count == 5
        assert session.completed_count == 0

    def test_session_counts_completed_items(self):
        """Test that session correctly counts completed items."""
        items = [
            ReviewItem(
                modification_id="mod_1",
                ts_term_id="term_1",
                clause_id="clause_1",
                original_text="Original",
                new_text="New",
                confidence=0.8,
                action=ReviewAction.ACCEPT,
            ),
            ReviewItem(
                modification_id="mod_2",
                ts_term_id="term_2",
                clause_id="clause_2",
                original_text="Original",
                new_text="New",
                confidence=0.8,
                action=ReviewAction.REJECT,
            ),
            ReviewItem(
                modification_id="mod_3",
                ts_term_id="term_3",
                clause_id="clause_3",
                original_text="Original",
                new_text="New",
                confidence=0.8,
                action=ReviewAction.PENDING,
            ),
        ]

        session = ReviewSession(
            id="session_001",
            contract_id="contract_001",
            items=items,
        )

        assert session.total_count == 3
        assert session.completed_count == 2


class TestActionHandler:
    """Test ActionHandler functionality."""

    def test_accept_item(self):
        """Test accepting a review item."""
        handler = ActionHandler()
        item = ReviewItem(
            modification_id="mod_001",
            ts_term_id="term_001",
            clause_id="clause_001",
            original_text="Original",
            new_text="New",
            confidence=0.85,
        )

        updated_item = handler.accept_item(item, user_id="user_123")

        assert updated_item.action == ReviewAction.ACCEPT
        assert len(handler.action_history) == 1

    def test_reject_item(self):
        """Test rejecting a review item."""
        handler = ActionHandler()
        item = ReviewItem(
            modification_id="mod_001",
            ts_term_id="term_001",
            clause_id="clause_001",
            original_text="Original",
            new_text="New",
            confidence=0.85,
        )

        updated_item = handler.reject_item(item, user_id="user_123", comment="Not accurate")

        assert updated_item.action == ReviewAction.REJECT
        assert updated_item.user_comment == "Not accurate"

    def test_batch_accept(self):
        """Test batch accepting items."""
        handler = ActionHandler()
        items = [
            ReviewItem(
                modification_id=f"mod_{i}",
                ts_term_id=f"term_{i}",
                clause_id=f"clause_{i}",
                original_text="Original",
                new_text="New",
                confidence=0.85,
            )
            for i in range(3)
        ]

        updated_items = handler.batch_accept(items, user_id="user_123")

        assert len(updated_items) == 3
        assert all(item.action == ReviewAction.ACCEPT for item in updated_items)

    def test_get_review_statistics(self):
        """Test getting review statistics."""
        handler = ActionHandler()
        items = [
            ReviewItem(
                modification_id="mod_1",
                ts_term_id="term_1",
                clause_id="clause_1",
                original_text="Original",
                new_text="New",
                confidence=0.85,
                action=ReviewAction.ACCEPT,
            ),
            ReviewItem(
                modification_id="mod_2",
                ts_term_id="term_2",
                clause_id="clause_2",
                original_text="Original",
                new_text="New",
                confidence=0.85,
                action=ReviewAction.REJECT,
            ),
            ReviewItem(
                modification_id="mod_3",
                ts_term_id="term_3",
                clause_id="clause_3",
                original_text="Original",
                new_text="New",
                confidence=0.85,
                action=ReviewAction.PENDING,
            ),
        ]

        stats = handler.get_review_statistics(items)

        assert stats['total'] == 3
        assert stats['accepted'] == 1
        assert stats['rejected'] == 1
        assert stats['pending'] == 1
        assert stats['completed'] == 2
        assert stats['completion_rate'] == pytest.approx(2/3)


class TestHighlightManager:
    """Test HighlightManager functionality."""

    def test_build_mapping(self):
        """Test building term-clause mapping."""
        manager = HighlightManager()
        modifications = [
            Modification(
                id="mod_1",
                match_id="clause_1",
                original_text="Original",
                new_text="New",
                location_start=0,
                location_end=10,
                action=ActionType.INSERT,
                source_ts_paragraph_id="term_1",
                confidence=0.85,
            ),
            Modification(
                id="mod_2",
                match_id="clause_2",
                original_text="Original",
                new_text="New",
                location_start=10,
                location_end=20,
                action=ActionType.OVERRIDE,
                source_ts_paragraph_id="term_2",
                confidence=0.85,
            ),
        ]

        manager.build_mapping(modifications)

        assert manager.get_linked_clause("term_1") == "clause_1"
        assert manager.get_linked_clause("term_2") == "clause_2"
        assert manager.get_linked_term("clause_1") == "term_1"
        assert manager.get_linked_term("clause_2") == "term_2"

    def test_position_tracking(self):
        """Test position tracking."""
        manager = HighlightManager()
        
        manager.set_term_position("term_1", 0, 100)
        manager.set_clause_position("clause_1", 200, 300)

        assert manager.get_term_position("term_1") == (0, 100)
        assert manager.get_clause_position("clause_1") == (200, 300)


class TestDiffHighlighter:
    """Test DiffHighlighter functionality."""

    def test_highlight_insert_modification(self):
        """Test highlighting an insert modification."""
        highlighter = DiffHighlighter()
        modification = Modification(
            id="mod_1",
            match_id="clause_1",
            original_text="",
            new_text="New text",
            location_start=0,
            location_end=0,
            action=ActionType.INSERT,
            source_ts_paragraph_id="term_1",
            confidence=0.85,
        )

        result = highlighter.highlight_modification(modification)

        assert result['type'] == 'insert'
        assert result['new_text'] == "New text"
        assert len(result['segments']) == 1

    def test_highlight_override_modification(self):
        """Test highlighting an override modification."""
        highlighter = DiffHighlighter()
        modification = Modification(
            id="mod_1",
            match_id="clause_1",
            original_text="Old text",
            new_text="New text",
            location_start=0,
            location_end=8,
            action=ActionType.OVERRIDE,
            source_ts_paragraph_id="term_1",
            confidence=0.85,
        )

        result = highlighter.highlight_modification(modification)

        assert result['type'] == 'override'
        assert result['original_text'] == "Old text"
        assert result['new_text'] == "New text"
        assert len(result['segments']) > 0

    def test_classify_modification_severity(self):
        """Test classifying modification severity."""
        highlighter = DiffHighlighter()
        
        high_conf_mod = Modification(
            id="mod_1",
            match_id="clause_1",
            original_text="",
            new_text="New",
            location_start=0,
            location_end=0,
            action=ActionType.INSERT,
            source_ts_paragraph_id="term_1",
            confidence=0.95,
        )
        
        low_conf_mod = Modification(
            id="mod_2",
            match_id="clause_2",
            original_text="",
            new_text="New",
            location_start=0,
            location_end=0,
            action=ActionType.INSERT,
            source_ts_paragraph_id="term_2",
            confidence=0.45,
        )

        assert highlighter.classify_modification_severity(high_conf_mod) == 'low'
        assert highlighter.classify_modification_severity(low_conf_mod) == 'high'
