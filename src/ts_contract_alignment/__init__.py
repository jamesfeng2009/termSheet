"""
TS Contract Alignment System

A system for intelligent alignment between Term Sheets (TS) and contract templates.
"""

__version__ = "0.1.0"

# Export main components
from .extractors import TSExtractor, TermPatternMatcher
from .models.extraction import ExtractedTerm, TSExtractionResult
from .models.document import ParsedDocument, DocumentSection, TextSegment
from .models.enums import (
    DocumentType,
    HeadingLevel,
    TermCategory,
    ClauseCategory,
    ActionType,
    MatchMethod,
)
from .models.alignment import AlignmentMatch, AlignmentResult
from .alignment import AlignmentEngine, RuleBasedMatcher, SemanticMatcher

__all__ = [
    "TSExtractor",
    "TermPatternMatcher",
    "ExtractedTerm",
    "TSExtractionResult",
    "ParsedDocument",
    "DocumentSection",
    "TextSegment",
    "DocumentType",
    "HeadingLevel",
    "TermCategory",
    "ClauseCategory",
    "ActionType",
    "MatchMethod",
    "AlignmentMatch",
    "AlignmentResult",
    "AlignmentEngine",
    "RuleBasedMatcher",
    "SemanticMatcher",
]
