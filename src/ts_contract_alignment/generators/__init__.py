"""Contract generation components for the TS Contract Alignment System."""

from .contract_generator import ContractGenerator, AnnotationConfig
from .contract_generator import ConflictRecord as GeneratorConflictRecord
from .annotation_manager import AnnotationManager, AnnotationStyle, Annotation
from .document_exporter import DocumentExporter
from .conflict_handler import (
    ConflictHandler,
    ConflictHandlerConfig,
    ConflictRecord,
    ConflictType,
    ConflictResolution,
)

__all__ = [
    "ContractGenerator",
    "AnnotationConfig",
    "GeneratorConflictRecord",
    "AnnotationManager",
    "AnnotationStyle",
    "Annotation",
    "DocumentExporter",
    "ConflictHandler",
    "ConflictHandlerConfig",
    "ConflictRecord",
    "ConflictType",
    "ConflictResolution",
]
