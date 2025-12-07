"""Configuration management for the TS Contract Alignment System."""

from .config_manager import ConfigurationManager
from .models import (
    ConfigurationType,
    TerminologyMapping,
    MatchingRule,
    RewritingTemplate,
    SystemConfiguration,
    ConfigurationError,
    ValidationResult,
)

__all__ = [
    "ConfigurationManager",
    "ConfigurationType",
    "TerminologyMapping",
    "MatchingRule",
    "RewritingTemplate",
    "SystemConfiguration",
    "ConfigurationError",
    "ValidationResult",
]
