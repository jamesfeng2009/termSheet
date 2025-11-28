"""Data models and enums for the TS Contract Alignment System."""

from .enums import (
    ActionType,
    ClauseCategory,
    DocumentType,
    HeadingLevel,
    MatchMethod,
    TermCategory,
)
from .document import TextSegment, DocumentSection, ParsedDocument
from .extraction import ExtractedTerm, TSExtractionResult
from .template import FillableSegment, FillableType, AnalyzedClause, TemplateAnalysisResult
from .alignment import AlignmentMatch, AlignmentResult

__all__ = [
    # Enums
    "ActionType",
    "ClauseCategory",
    "DocumentType",
    "HeadingLevel",
    "MatchMethod",
    "TermCategory",
    "FillableType",
    # Document models
    "TextSegment",
    "DocumentSection",
    "ParsedDocument",
    # Extraction models
    "ExtractedTerm",
    "TSExtractionResult",
    # Template models
    "FillableSegment",
    "AnalyzedClause",
    "TemplateAnalysisResult",
    # Alignment models
    "AlignmentMatch",
    "AlignmentResult",
]
