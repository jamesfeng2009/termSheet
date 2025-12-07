"""Action handler for review decisions."""

from typing import List, Optional, Dict
from datetime import datetime

from ..interfaces.review import ReviewAction, ReviewItem
from ..interfaces.generator import Modification
from ..interfaces.audit import AuditEventType
from ..audit.audit_logger import AuditLogger


class ActionHandler:
    """
    Handles accept/reject actions for review items.
    
    Manages user decisions on modifications and tracks
    the state of the review process.
    """

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        """
        Initialize the action handler.
        
        Args:
            audit_logger: Optional audit logger for tracking actions.
        """
        self.audit_logger = audit_logger
        self.action_history: List[Dict] = []

    def accept_item(
        self,
        item: ReviewItem,
        user_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> ReviewItem:
        """
        Accept a review item.
        
        Args:
            item: The review item to accept.
            user_id: Optional user identifier.
            comment: Optional comment.
            
        Returns:
            Updated ReviewItem with ACCEPT action.
        """
        item.action = ReviewAction.ACCEPT
        item.user_comment = comment

        # Log the action
        self._log_action(
            item_id=item.modification_id,
            action=ReviewAction.ACCEPT,
            user_id=user_id,
            comment=comment,
        )

        return item

    def reject_item(
        self,
        item: ReviewItem,
        user_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> ReviewItem:
        """
        Reject a review item.
        
        Args:
            item: The review item to reject.
            user_id: Optional user identifier.
            comment: Optional comment.
            
        Returns:
            Updated ReviewItem with REJECT action.
        """
        item.action = ReviewAction.REJECT
        item.user_comment = comment

        # Log the action
        self._log_action(
            item_id=item.modification_id,
            action=ReviewAction.REJECT,
            user_id=user_id,
            comment=comment,
        )

        return item

    def modify_item(
        self,
        item: ReviewItem,
        new_text: str,
        user_id: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> ReviewItem:
        """
        Modify a review item with custom text.
        
        Args:
            item: The review item to modify.
            new_text: The new text to use.
            user_id: Optional user identifier.
            comment: Optional comment.
            
        Returns:
            Updated ReviewItem with MODIFY action.
        """
        item.action = ReviewAction.MODIFY
        item.new_text = new_text
        item.user_comment = comment

        # Log the action
        self._log_action(
            item_id=item.modification_id,
            action=ReviewAction.MODIFY,
            user_id=user_id,
            comment=comment,
            new_text=new_text,
        )

        return item

    def batch_accept(
        self,
        items: List[ReviewItem],
        user_id: Optional[str] = None,
    ) -> List[ReviewItem]:
        """
        Accept multiple review items at once.
        
        Args:
            items: List of review items to accept.
            user_id: Optional user identifier.
            
        Returns:
            List of updated ReviewItems.
        """
        updated_items = []
        for item in items:
            updated_item = self.accept_item(item, user_id=user_id)
            updated_items.append(updated_item)

        # Log batch action
        self._log_batch_action(
            item_ids=[item.modification_id for item in items],
            action=ReviewAction.ACCEPT,
            user_id=user_id,
        )

        return updated_items

    def batch_reject(
        self,
        items: List[ReviewItem],
        user_id: Optional[str] = None,
    ) -> List[ReviewItem]:
        """
        Reject multiple review items at once.
        
        Args:
            items: List of review items to reject.
            user_id: Optional user identifier.
            
        Returns:
            List of updated ReviewItems.
        """
        updated_items = []
        for item in items:
            updated_item = self.reject_item(item, user_id=user_id)
            updated_items.append(updated_item)

        # Log batch action
        self._log_batch_action(
            item_ids=[item.modification_id for item in items],
            action=ReviewAction.REJECT,
            user_id=user_id,
        )

        return updated_items

    def accept_all_high_confidence(
        self,
        items: List[ReviewItem],
        threshold: float = 0.8,
        user_id: Optional[str] = None,
    ) -> List[ReviewItem]:
        """
        Accept all items above a confidence threshold.
        
        Args:
            items: List of review items.
            threshold: Confidence threshold (0.0 to 1.0).
            user_id: Optional user identifier.
            
        Returns:
            List of updated ReviewItems.
        """
        high_confidence_items = [
            item for item in items
            if item.confidence >= threshold and item.action == ReviewAction.PENDING
        ]

        return self.batch_accept(high_confidence_items, user_id=user_id)

    def get_pending_items(self, items: List[ReviewItem]) -> List[ReviewItem]:
        """
        Get all pending review items.
        
        Args:
            items: List of review items.
            
        Returns:
            List of pending items.
        """
        return [item for item in items if item.action == ReviewAction.PENDING]

    def get_accepted_items(self, items: List[ReviewItem]) -> List[ReviewItem]:
        """
        Get all accepted review items.
        
        Args:
            items: List of review items.
            
        Returns:
            List of accepted items.
        """
        return [item for item in items if item.action == ReviewAction.ACCEPT]

    def get_rejected_items(self, items: List[ReviewItem]) -> List[ReviewItem]:
        """
        Get all rejected review items.
        
        Args:
            items: List of review items.
            
        Returns:
            List of rejected items.
        """
        return [item for item in items if item.action == ReviewAction.REJECT]

    def get_review_statistics(self, items: List[ReviewItem]) -> Dict:
        """
        Get statistics about review progress.
        
        Args:
            items: List of review items.
            
        Returns:
            Dictionary with review statistics.
        """
        total = len(items)
        pending = len(self.get_pending_items(items))
        accepted = len(self.get_accepted_items(items))
        rejected = len(self.get_rejected_items(items))
        modified = len([item for item in items if item.action == ReviewAction.MODIFY])

        return {
            'total': total,
            'pending': pending,
            'accepted': accepted,
            'rejected': rejected,
            'modified': modified,
            'completed': accepted + rejected + modified,
            'completion_rate': (accepted + rejected + modified) / total if total > 0 else 0,
        }

    def _log_action(
        self,
        item_id: str,
        action: ReviewAction,
        user_id: Optional[str] = None,
        comment: Optional[str] = None,
        new_text: Optional[str] = None,
    ) -> None:
        """Log a review action."""
        action_record = {
            'item_id': item_id,
            'action': action.value,
            'user_id': user_id,
            'comment': comment,
            'new_text': new_text,
            'timestamp': datetime.utcnow().isoformat(),
        }
        self.action_history.append(action_record)

        # Log to audit logger if available
        if self.audit_logger:
            self.audit_logger.log_event(
                event_type=AuditEventType.REVIEW_ACTION,
                document_id=None,
                session_id=None,
                user_id=user_id,
                details={
                    'item_id': item_id,
                    'action': action.value,
                    'comment': comment,
                    'new_text': new_text,
                },
                metadata={},
            )

    def _log_batch_action(
        self,
        item_ids: List[str],
        action: ReviewAction,
        user_id: Optional[str] = None,
    ) -> None:
        """Log a batch review action."""
        action_record = {
            'item_ids': item_ids,
            'action': action.value,
            'user_id': user_id,
            'count': len(item_ids),
            'timestamp': datetime.utcnow().isoformat(),
        }
        self.action_history.append(action_record)

        # Log to audit logger if available
        if self.audit_logger:
            self.audit_logger.log_event(
                event_type=AuditEventType.REVIEW_ACTION,
                document_id=None,
                session_id=None,
                user_id=user_id,
                details={
                    'batch': True,
                    'item_ids': item_ids,
                    'action': action.value,
                    'count': len(item_ids),
                },
                metadata={},
            )

    def get_action_history(self) -> List[Dict]:
        """
        Get the history of all actions.
        
        Returns:
            List of action records.
        """
        return self.action_history.copy()
