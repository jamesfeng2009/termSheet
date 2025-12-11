"""Conflict handling for contract generation."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..interfaces.generator import Modification
from ..models.enums import ActionType


logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts that can occur during generation."""
    FORMATTING_MISMATCH = "formatting_mismatch"
    STYLE_CONFLICT = "style_conflict"
    ENCODING_ERROR = "encoding_error"
    LOCATION_NOT_FOUND = "location_not_found"
    OVERLAPPING_MODIFICATION = "overlapping_modification"
    VALUE_TYPE_MISMATCH = "value_type_mismatch"
    STRUCTURE_VIOLATION = "structure_violation"


class ConflictResolution(Enum):
    """Resolution strategies for conflicts."""
    PRESERVE_ORIGINAL = "preserve_original"
    APPLY_NEW = "apply_new"
    MERGE = "merge"
    SKIP = "skip"
    MANUAL_REVIEW = "manual_review"


@dataclass
class ConflictRecord:
    """Record of a conflict during contract generation."""
    id: str
    modification_id: str
    conflict_type: ConflictType
    description: str
    original_value: Any
    attempted_value: Any
    resolution: ConflictResolution
    resolution_details: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "modification_id": self.modification_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "original_value": str(self.original_value),
            "attempted_value": str(self.attempted_value),
            "resolution": self.resolution.value,
            "resolution_details": self.resolution_details,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ConflictHandlerConfig:
    """Configuration for conflict handling."""
    default_resolution: ConflictResolution = ConflictResolution.PRESERVE_ORIGINAL
    log_all_conflicts: bool = True
    raise_on_critical: bool = False
    max_conflicts_before_abort: int = 100
    preserve_formatting_on_conflict: bool = True
    # Optional per-type override for resolution strategies. Keys are
    # ConflictType.value strings (e.g. "formatting_mismatch"), values are
    # ConflictResolution.value strings (e.g. "preserve_original",
    # "apply_new", "skip", "manual_review").
    per_type_resolution: Dict[str, str] = field(default_factory=dict)


class ConflictHandler:
    """
    Handles conflicts during contract generation.
    
    Detects, records, and resolves conflicts that occur when
    applying modifications to contract templates.
    """

    def __init__(self, config: Optional[ConflictHandlerConfig] = None):
        """
        Initialize the conflict handler.
        
        Args:
            config: Configuration for conflict handling.
        """
        self.config = config or ConflictHandlerConfig()
        self.conflicts: List[ConflictRecord] = []
        self._conflict_count = 0

    def detect_formatting_conflict(
        self,
        original_format: Dict[str, Any],
        target_format: Dict[str, Any],
        modification: Modification,
    ) -> Optional[ConflictRecord]:
        """
        Detect formatting conflicts between original and target.
        
        Args:
            original_format: Original formatting attributes.
            target_format: Target formatting attributes.
            modification: The modification being applied.
            
        Returns:
            ConflictRecord if conflict detected, None otherwise.
        """
        conflicts_found = []
        
        # Check each formatting attribute
        for key in original_format:
            if key in target_format:
                if original_format[key] != target_format[key]:
                    conflicts_found.append(
                        f"{key}: {original_format[key]} -> {target_format[key]}"
                    )
        
        if not conflicts_found:
            return None
        
        return self._create_conflict(
            modification=modification,
            conflict_type=ConflictType.FORMATTING_MISMATCH,
            description=f"Formatting mismatch: {', '.join(conflicts_found)}",
            original_value=original_format,
            attempted_value=target_format,
        )

    def detect_overlapping_modification(
        self,
        modification: Modification,
        existing_modifications: List[Modification],
    ) -> Optional[ConflictRecord]:
        """
        Detect if a modification overlaps with existing ones.
        
        Args:
            modification: The new modification.
            existing_modifications: List of already applied modifications.
            
        Returns:
            ConflictRecord if overlap detected, None otherwise.
        """
        for existing in existing_modifications:
            # Check for location overlap
            if self._locations_overlap(
                modification.location_start,
                modification.location_end,
                existing.location_start,
                existing.location_end,
            ):
                return self._create_conflict(
                    modification=modification,
                    conflict_type=ConflictType.OVERLAPPING_MODIFICATION,
                    description=f"Modification overlaps with existing modification {existing.id}",
                    original_value=existing.new_text,
                    attempted_value=modification.new_text,
                )
        
        return None

    def detect_location_not_found(
        self,
        modification: Modification,
        document_text: str,
    ) -> Optional[ConflictRecord]:
        """
        Detect if the target location cannot be found.
        
        Args:
            modification: The modification to apply.
            document_text: The full document text.
            
        Returns:
            ConflictRecord if location not found, None otherwise.
        """
        if modification.original_text and modification.original_text not in document_text:
            return self._create_conflict(
                modification=modification,
                conflict_type=ConflictType.LOCATION_NOT_FOUND,
                description=f"Target text not found in document: '{modification.original_text[:50]}...'",
                original_value=modification.original_text,
                attempted_value=modification.new_text,
            )
        
        return None

    def detect_structure_violation(
        self,
        modification: Modification,
        section_structure: Dict[str, Any],
    ) -> Optional[ConflictRecord]:
        """
        Detect if modification violates document structure.
        
        Args:
            modification: The modification to apply.
            section_structure: The document's section structure.
            
        Returns:
            ConflictRecord if structure violation detected, None otherwise.
        """
        # Check if modification would break section numbering
        # This is a simplified check - real implementation would be more thorough
        if modification.action == ActionType.INSERT:
            # Insertions generally don't violate structure
            return None
        
        # For overrides, check if we're modifying structural elements
        structural_patterns = ["第", "条", "章", "节", "Article", "Section", "Chapter"]
        
        for pattern in structural_patterns:
            if pattern in modification.original_text and pattern not in modification.new_text:
                return self._create_conflict(
                    modification=modification,
                    conflict_type=ConflictType.STRUCTURE_VIOLATION,
                    description=f"Modification may break document structure (removing '{pattern}')",
                    original_value=modification.original_text,
                    attempted_value=modification.new_text,
                )
        
        return None

    def _locations_overlap(
        self,
        start1: int,
        end1: int,
        start2: int,
        end2: int,
    ) -> bool:
        """Check if two location ranges overlap."""
        return not (end1 <= start2 or end2 <= start1)

    def _create_conflict(
        self,
        modification: Modification,
        conflict_type: ConflictType,
        description: str,
        original_value: Any,
        attempted_value: Any,
    ) -> ConflictRecord:
        """Create and record a conflict."""
        import uuid
        
        resolution = self._determine_resolution(conflict_type)
        resolution_details = self._get_resolution_details(conflict_type, resolution)
        
        conflict = ConflictRecord(
            id=str(uuid.uuid4()),
            modification_id=modification.id,
            conflict_type=conflict_type,
            description=description,
            original_value=original_value,
            attempted_value=attempted_value,
            resolution=resolution,
            resolution_details=resolution_details,
            metadata={
                "source_ts_paragraph_id": modification.source_ts_paragraph_id,
                "action_type": modification.action.value,
                "confidence": modification.confidence,
            },
        )
        
        self._record_conflict(conflict)
        return conflict

    def _determine_resolution(self, conflict_type: ConflictType) -> ConflictResolution:
        """Determine the resolution strategy for a conflict type."""
        # First look for an explicit override in the configuration, keyed by
        # ConflictType.value.
        if self.config.per_type_resolution:
            key = conflict_type.value
            override = self.config.per_type_resolution.get(key)
            if override is not None:
                try:
                    return ConflictResolution(override)
                except ValueError:
                    logger.warning(
                        "Invalid conflict resolution '%s' configured for type '%s'",
                        override,
                        key,
                    )

        # Fall back to the built-in default mapping when no override exists.
        resolution_map = {
            ConflictType.FORMATTING_MISMATCH: ConflictResolution.PRESERVE_ORIGINAL,
            ConflictType.STYLE_CONFLICT: ConflictResolution.PRESERVE_ORIGINAL,
            ConflictType.ENCODING_ERROR: ConflictResolution.SKIP,
            ConflictType.LOCATION_NOT_FOUND: ConflictResolution.MANUAL_REVIEW,
            ConflictType.OVERLAPPING_MODIFICATION: ConflictResolution.SKIP,
            ConflictType.VALUE_TYPE_MISMATCH: ConflictResolution.PRESERVE_ORIGINAL,
            ConflictType.STRUCTURE_VIOLATION: ConflictResolution.PRESERVE_ORIGINAL,
        }

        return resolution_map.get(conflict_type, self.config.default_resolution)

    def _get_resolution_details(
        self,
        conflict_type: ConflictType,
        resolution: ConflictResolution,
    ) -> str:
        """Get human-readable resolution details."""
        details_map = {
            (ConflictType.FORMATTING_MISMATCH, ConflictResolution.PRESERVE_ORIGINAL):
                "Original formatting preserved to maintain document consistency.",
            (ConflictType.STYLE_CONFLICT, ConflictResolution.PRESERVE_ORIGINAL):
                "Original style preserved to maintain document appearance.",
            (ConflictType.ENCODING_ERROR, ConflictResolution.SKIP):
                "Modification skipped due to encoding issues.",
            (ConflictType.LOCATION_NOT_FOUND, ConflictResolution.MANUAL_REVIEW):
                "Target location not found. Manual review required.",
            (ConflictType.OVERLAPPING_MODIFICATION, ConflictResolution.SKIP):
                "Modification skipped to avoid overlapping changes.",
            (ConflictType.VALUE_TYPE_MISMATCH, ConflictResolution.PRESERVE_ORIGINAL):
                "Original value preserved due to type mismatch.",
            (ConflictType.STRUCTURE_VIOLATION, ConflictResolution.PRESERVE_ORIGINAL):
                "Original structure preserved to maintain document integrity.",
        }
        
        return details_map.get(
            (conflict_type, resolution),
            f"Resolved using {resolution.value} strategy.",
        )

    def _record_conflict(self, conflict: ConflictRecord) -> None:
        """Record a conflict and handle logging."""
        self.conflicts.append(conflict)
        self._conflict_count += 1
        
        if self.config.log_all_conflicts:
            logger.warning(
                f"Conflict detected: {conflict.conflict_type.value} - "
                f"{conflict.description} (Resolution: {conflict.resolution.value})"
            )
        
        if self._conflict_count >= self.config.max_conflicts_before_abort:
            if self.config.raise_on_critical:
                raise RuntimeError(
                    f"Maximum conflict count ({self.config.max_conflicts_before_abort}) exceeded"
                )
            logger.error(
                f"Maximum conflict count exceeded. "
                f"Total conflicts: {self._conflict_count}"
            )

    def resolve_conflict(
        self,
        conflict: ConflictRecord,
        resolution: Optional[ConflictResolution] = None,
    ) -> Any:
        """
        Resolve a conflict and return the appropriate value.
        
        Args:
            conflict: The conflict to resolve.
            resolution: Optional override for resolution strategy.
            
        Returns:
            The resolved value to use.
        """
        resolution = resolution or conflict.resolution
        
        if resolution == ConflictResolution.PRESERVE_ORIGINAL:
            return conflict.original_value
        elif resolution == ConflictResolution.APPLY_NEW:
            return conflict.attempted_value
        elif resolution == ConflictResolution.MERGE:
            return self._merge_values(conflict.original_value, conflict.attempted_value)
        elif resolution == ConflictResolution.SKIP:
            return None
        else:
            # MANUAL_REVIEW - return original and flag for review
            return conflict.original_value

    def _merge_values(self, original: Any, new: Any) -> Any:
        """Attempt to merge two values."""
        if isinstance(original, dict) and isinstance(new, dict):
            merged = original.copy()
            merged.update(new)
            return merged
        elif isinstance(original, str) and isinstance(new, str):
            return f"{original} {new}"
        else:
            return new

    def get_conflicts(self) -> List[ConflictRecord]:
        """Get all recorded conflicts."""
        return self.conflicts.copy()

    def get_conflicts_by_type(
        self,
        conflict_type: ConflictType,
    ) -> List[ConflictRecord]:
        """Get conflicts filtered by type."""
        return [c for c in self.conflicts if c.conflict_type == conflict_type]

    def get_conflicts_requiring_review(self) -> List[ConflictRecord]:
        """Get conflicts that require manual review."""
        return [
            c for c in self.conflicts
            if c.resolution == ConflictResolution.MANUAL_REVIEW
        ]

    def export_conflict_report(self) -> Dict[str, Any]:
        """Export a summary report of all conflicts."""
        return {
            "total_conflicts": len(self.conflicts),
            "by_type": {
                ct.value: len(self.get_conflicts_by_type(ct))
                for ct in ConflictType
            },
            "requiring_review": len(self.get_conflicts_requiring_review()),
            "conflicts": [c.to_dict() for c in self.conflicts],
        }

    def clear_conflicts(self) -> None:
        """Clear all recorded conflicts."""
        self.conflicts = []
        self._conflict_count = 0
