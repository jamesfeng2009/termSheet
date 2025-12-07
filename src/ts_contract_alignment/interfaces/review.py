"""Review interface for the TS Contract Alignment System."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

from ..interfaces.generator import GeneratedContract


class ReviewAction(Enum):
    """Review action types."""
    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"
    PENDING = "pending"


@dataclass
class ReviewItem:
    """
    Review item for a single modification.
    
    Represents a modification that needs user review,
    including the original and new text, confidence, and user action.
    """
    modification_id: str
    ts_term_id: str
    clause_id: str
    original_text: str
    new_text: str
    confidence: float
    action: ReviewAction = ReviewAction.PENDING
    user_comment: Optional[str] = None


@dataclass
class ReviewSession:
    """
    Review session for a generated contract.
    
    Manages the review process for all modifications in a contract,
    tracking progress and user decisions.
    """
    id: str
    contract_id: str
    items: List[ReviewItem] = field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0
    session_timestamp: str = ""

    def __post_init__(self):
        if self.items is None:
            self.items = []
        self.total_count = len(self.items)
        self.completed_count = sum(1 for item in self.items if item.action != ReviewAction.PENDING)


class IReviewInterface(ABC):
    """
    Abstract interface for review functionality.
    
    Implementations handle creating review sessions, managing user
    decisions, and exporting finalized documents.
    """

    @abstractmethod
    def create_session(self, contract: GeneratedContract) -> ReviewSession:
        """
        Create a review session for a generated contract.
        
        Args:
            contract: The generated contract to review.
            
        Returns:
            ReviewSession with all modifications as review items.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def finalize_session(self, session_id: str) -> str:
        """
        Finalize the review session and export the final document.
        
        Args:
            session_id: The review session ID.
            
        Returns:
            File path to the finalized .docx document.
        """
        pass
