"""Alignment data models for the TS Contract Alignment System."""

from dataclasses import dataclass, field
from typing import List, Optional

from .enums import ActionType, MatchMethod


@dataclass
class AlignmentMatch:
    """
    Alignment match between a TS term and a contract clause.
    
    Represents a single match result from the alignment engine,
    including the matching method, confidence score, and action type.
    """
    id: str
    ts_term_id: str
    clause_id: str
    fillable_segment_id: Optional[str]
    match_method: MatchMethod
    confidence: float
    action: ActionType
    needs_review: bool


@dataclass
class AlignmentResult:
    """
    Result of TS-to-template alignment.
    
    Contains all matches between TS terms and contract clauses,
    along with lists of unmatched items for review.
    """
    ts_document_id: str
    template_document_id: str
    matches: List[AlignmentMatch] = field(default_factory=list)
    unmatched_terms: List[str] = field(default_factory=list)
    unmatched_clauses: List[str] = field(default_factory=list)
    alignment_timestamp: str = ""

    def __post_init__(self):
        if self.matches is None:
            self.matches = []
        if self.unmatched_terms is None:
            self.unmatched_terms = []
        if self.unmatched_clauses is None:
            self.unmatched_clauses = []
