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
from .generators import ContractGenerator
from .interfaces.generator import GeneratedContract, Modification
from .interfaces.audit import AuditEvent, AuditEventType, AuditLog, IAuditLogger
from .audit import AuditLogger, DatabaseManager
from .config import (
    ConfigurationManager,
    ConfigurationType,
    TerminologyMapping,
    MatchingRule,
    RewritingTemplate,
    SystemConfiguration,
    ConfigurationError,
    ValidationResult,
)

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
    "ContractGenerator",
    "GeneratedContract",
    "Modification",
    "AuditEvent",
    "AuditEventType",
    "AuditLog",
    "IAuditLogger",
    "AuditLogger",
    "DatabaseManager",
    "ConfigurationManager",
    "ConfigurationType",
    "TerminologyMapping",
    "MatchingRule",
    "RewritingTemplate",
    "SystemConfiguration",
    "ConfigurationError",
    "ValidationResult",
]
