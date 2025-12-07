"""Abstract interfaces for the TS Contract Alignment System."""

from .parser import IDocumentParser
from .extractor import ITSExtractor
from .analyzer import ITemplateAnalyzer
from .alignment import IAlignmentEngine
from .generator import IContractGenerator
from .audit import IAuditLogger
from .review import IReviewInterface

__all__ = [
    "IDocumentParser",
    "ITSExtractor",
    "ITemplateAnalyzer",
    "IAlignmentEngine",
    "IContractGenerator",
    "IAuditLogger",
    "IReviewInterface",
]
