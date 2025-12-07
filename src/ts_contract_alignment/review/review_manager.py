"""Review session management implementation."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..audit.database import DatabaseManager
from ..audit.models import ReviewSessionModel, GeneratedContractModel
from ..interfaces.review import (
    IReviewInterface,
    ReviewSession,
    ReviewItem,
    ReviewAction,
)
from ..interfaces.generator import GeneratedContract


class ReviewManager(IReviewInterface):
    """
    Implementation of review session management.
    
    Handles creating review sessions, tracking user decisions,
    and managing the review workflow.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize the review manager.
        
        Args:
            db_manager: Optional database manager. If not provided,
                       a new one will be created.
        """
        self._db_manager = db_manager or DatabaseManager()

    def _get_session(self):
        """Get database session context manager."""
        return self._db_manager.get_session()

    def create_session(self, contract: GeneratedContract) -> ReviewSession:
        """
        Create a review session for a generated contract.
        
        Args:
            contract: The generated contract to review.
            
        Returns:
            ReviewSession with all modifications as review items.
        """
        # Create review items from modifications
        items = []
        for mod in contract.modifications:
            item = ReviewItem(
                modification_id=mod.id,
                ts_term_id=mod.source_ts_paragraph_id,
                clause_id=mod.match_id,
                original_text=mod.original_text,
                new_text=mod.new_text,
                confidence=mod.confidence,
                action=ReviewAction.PENDING,
                user_comment=None,
            )
            items.append(item)

        # Create session
        session_id = str(uuid.uuid4())
        session = ReviewSession(
            id=session_id,
            contract_id=contract.id,
            items=items,
            completed_count=0,
            total_count=len(items),
            session_timestamp=datetime.utcnow().isoformat(),
        )

        # Save to database
        with self._get_session() as db:
            # Serialize items to JSON
            items_json = [
                {
                    "modification_id": item.modification_id,
                    "ts_term_id": item.ts_term_id,
                    "clause_id": item.clause_id,
                    "original_text": item.original_text,
                    "new_text": item.new_text,
                    "confidence": item.confidence,
                    "action": item.action.value,
                    "user_comment": item.user_comment,
                }
                for item in items
            ]

            session_model = ReviewSessionModel(
                id=uuid.UUID(session_id),
                contract_id=uuid.UUID(contract.id),
                session_timestamp=datetime.utcnow(),
                items=items_json,
                status="in_progress",
            )
            db.add(session_model)

        return session

    def update_item(
        self,
        session_id: str,
        item_id: str,
        action: ReviewAction,
        comment: Optional[str] = None,
    ) -> ReviewItem:
        """
        Update a review item with user action.
        
        Args:
            session_id: The review session ID.
            item_id: The modification ID to update.
            action: The user's review action.
            comment: Optional user comment.
            
        Returns:
            Updated ReviewItem.
        """
        with self._get_session() as db:
            # Load session from database
            session_model = db.query(ReviewSessionModel).filter(
                ReviewSessionModel.id == uuid.UUID(session_id)
            ).first()

            if not session_model:
                raise ValueError(f"Review session {session_id} not found")

            # Update the specific item
            items = session_model.items
            updated_item = None
            for item_data in items:
                if item_data["modification_id"] == item_id:
                    item_data["action"] = action.value
                    item_data["user_comment"] = comment
                    updated_item = ReviewItem(
                        modification_id=item_data["modification_id"],
                        ts_term_id=item_data["ts_term_id"],
                        clause_id=item_data["clause_id"],
                        original_text=item_data["original_text"],
                        new_text=item_data["new_text"],
                        confidence=item_data["confidence"],
                        action=ReviewAction(item_data["action"]),
                        user_comment=item_data.get("user_comment"),
                    )
                    break

            if not updated_item:
                raise ValueError(f"Review item {item_id} not found in session {session_id}")

            # Save updated items
            session_model.items = items
            session_model.updated_at = datetime.utcnow()

            return updated_item

    def finalize_session(self, session_id: str) -> str:
        """
        Finalize the review session and export the final document.
        
        This method marks the session as completed and returns the path
        to the finalized document. The actual document export is handled
        by the document exporter.
        
        Args:
            session_id: The review session ID.
            
        Returns:
            File path to the finalized .docx document.
        """
        with self._get_session() as db:
            # Load session from database
            session_model = db.query(ReviewSessionModel).filter(
                ReviewSessionModel.id == uuid.UUID(session_id)
            ).first()

            if not session_model:
                raise ValueError(f"Review session {session_id} not found")

            # Mark session as completed
            session_model.status = "completed"
            session_model.updated_at = datetime.utcnow()

            # Get the contract to find the clean version path
            contract_model = db.query(GeneratedContractModel).filter(
                GeneratedContractModel.id == session_model.contract_id
            ).first()

            if not contract_model:
                raise ValueError(f"Contract {session_model.contract_id} not found")

            # Return the clean version path
            # The actual export with accepted/rejected changes would be handled
            # by the document exporter in a real implementation
            return contract_model.clean_version_path or ""

    def get_session(self, session_id: str) -> ReviewSession:
        """
        Retrieve a review session by ID.
        
        Args:
            session_id: The review session ID.
            
        Returns:
            ReviewSession object.
        """
        with self._get_session() as db:
            session_model = db.query(ReviewSessionModel).filter(
                ReviewSessionModel.id == uuid.UUID(session_id)
            ).first()

            if not session_model:
                raise ValueError(f"Review session {session_id} not found")

            # Deserialize items
            items = [
                ReviewItem(
                    modification_id=item_data["modification_id"],
                    ts_term_id=item_data["ts_term_id"],
                    clause_id=item_data["clause_id"],
                    original_text=item_data["original_text"],
                    new_text=item_data["new_text"],
                    confidence=item_data["confidence"],
                    action=ReviewAction(item_data["action"]),
                    user_comment=item_data.get("user_comment"),
                )
                for item_data in session_model.items
            ]

            return ReviewSession(
                id=str(session_model.id),
                contract_id=str(session_model.contract_id),
                items=items,
                completed_count=sum(1 for item in items if item.action != ReviewAction.PENDING),
                total_count=len(items),
                session_timestamp=session_model.session_timestamp.isoformat(),
            )
