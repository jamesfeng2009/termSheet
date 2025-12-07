"""Data models for configuration management."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConfigurationType(Enum):
    """Types of configuration supported by the system."""
    TERMINOLOGY = "terminology"
    RULES = "rules"
    TEMPLATES = "templates"


@dataclass
class TerminologyMapping:
    """
    Terminology mapping for legal term variations.
    
    Maps standard terms to their variations across different legal conventions.
    """
    id: str
    standard_term: str
    variations: List[str]
    language: str  # "zh", "en", "mixed"
    category: str  # Maps to TermCategory or ClauseCategory
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, text: str) -> bool:
        """Check if text matches this terminology mapping."""
        text_lower = text.lower()
        if self.standard_term.lower() in text_lower:
            return True
        return any(var.lower() in text_lower for var in self.variations)

    def get_all_terms(self) -> List[str]:
        """Get all terms including standard and variations."""
        return [self.standard_term] + self.variations


@dataclass
class MatchingRule:
    """
    Custom matching rule for alignment.
    
    Defines rules for matching TS terms to contract clauses.
    """
    id: str
    name: str
    priority: int  # Lower number = higher priority
    source_pattern: str  # Regex or keyword pattern for TS terms
    target_pattern: str  # Regex or keyword pattern for contract clauses
    source_categories: List[str]  # TermCategory values
    target_categories: List[str]  # ClauseCategory values
    confidence_boost: float = 0.0  # Boost to add to confidence score
    enabled: bool = True
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RewritingTemplate:
    """
    Template for clause rewriting and language standardization.
    
    Defines how to rewrite or standardize clause language.
    """
    id: str
    name: str
    source_pattern: str  # Pattern to match in source text
    replacement_template: str  # Template for replacement (supports {placeholders})
    language: str  # Target language: "zh", "en"
    category: str  # ClauseCategory value
    preserve_values: bool = True  # Whether to preserve extracted values
    enabled: bool = True
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
    
    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result into this one."""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings
        )


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str, validation_result: Optional[ValidationResult] = None):
        super().__init__(message)
        self.message = message
        self.validation_result = validation_result


@dataclass
class SystemConfiguration:
    """
    Complete system configuration.
    
    Aggregates all configuration types into a single structure.
    """
    terminology_mappings: List[TerminologyMapping] = field(default_factory=list)
    matching_rules: List[MatchingRule] = field(default_factory=list)
    rewriting_templates: List[RewritingTemplate] = field(default_factory=list)
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_terminology_by_category(self, category: str) -> List[TerminologyMapping]:
        """Get terminology mappings for a specific category."""
        return [t for t in self.terminology_mappings if t.category == category]
    
    def get_rules_by_priority(self) -> List[MatchingRule]:
        """Get matching rules sorted by priority (ascending)."""
        return sorted(
            [r for r in self.matching_rules if r.enabled],
            key=lambda r: r.priority
        )
    
    def get_templates_by_category(self, category: str) -> List[RewritingTemplate]:
        """Get rewriting templates for a specific category."""
        return [
            t for t in self.rewriting_templates 
            if t.category == category and t.enabled
        ]
