"""Custom exceptions for document parsing."""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ParseError(Exception):
    """
    Base exception for document parsing errors.
    
    Provides detailed error information including file path, location,
    and additional context for debugging and user feedback.
    
    Attributes:
        message: Human-readable error description.
        file_path: Path to the file that caused the error.
        location: Specific location within the file (page, paragraph, byte offset).
        details: Additional error details.
    """
    message: str
    file_path: Optional[str] = None
    location: Optional[str] = None
    details: Optional[dict] = field(default_factory=dict)

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        # Initialize Exception with the message
        super().__init__(str(self))

    def __str__(self) -> str:
        parts = [self.message]
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        if self.location:
            parts.append(f"Location: {self.location}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "file_path": self.file_path,
            "location": self.location,
            "details": self.details,
        }

    @property
    def has_location(self) -> bool:
        """Check if error has location information."""
        return self.location is not None and len(self.location) > 0


@dataclass
class DocumentCorruptedError(ParseError):
    """
    Exception raised when a document is corrupted or unreadable.
    
    This error indicates that the file exists but cannot be parsed
    due to corruption, invalid format, or encryption.
    """
    
    def get_recovery_suggestions(self) -> list[str]:
        """Return suggestions for recovering from this error."""
        suggestions = [
            "Try opening the file in its native application to verify it's not corrupted",
            "Check if the file is password-protected or encrypted",
            "Try re-downloading or re-exporting the file",
        ]
        if self.file_path and self.file_path.endswith('.pdf'):
            suggestions.append("For PDFs, try using a PDF repair tool")
        elif self.file_path and self.file_path.endswith('.docx'):
            suggestions.append("For Word documents, try opening in recovery mode")
        return suggestions


@dataclass
class UnsupportedFormatError(ParseError):
    """
    Exception raised when a document format is not supported.
    
    This error indicates that the file format is not recognized
    or not supported by the parser.
    """
    
    def get_supported_formats(self) -> list[str]:
        """Return list of supported formats."""
        return self.details.get("supported_formats", [".docx", ".pdf"])


@dataclass
class PartialParseError(ParseError):
    """
    Exception raised when parsing partially succeeds.
    
    This error indicates that some content was extracted but
    the parsing was incomplete due to errors in specific sections.
    """
    partial_result: Optional[Any] = None
    failed_sections: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.failed_sections is None:
            self.failed_sections = []
        super().__post_init__()

    def get_success_rate(self) -> float:
        """Calculate the success rate of parsing."""
        if not self.details:
            return 0.0
        total = self.details.get("total_sections", 0)
        failed = len(self.failed_sections)
        if total == 0:
            return 0.0
        return (total - failed) / total


class ErrorHandler:
    """
    Utility class for handling and aggregating parsing errors.
    
    Supports graceful degradation by collecting errors during parsing
    and allowing partial results to be returned.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.errors: list[ParseError] = []
        self.warnings: list[str] = []

    def add_error(self, error: ParseError) -> None:
        """Add an error to the collection."""
        self.errors.append(error)

    def add_warning(self, message: str, location: Optional[str] = None) -> None:
        """Add a warning message."""
        warning = f"{message}"
        if location:
            warning += f" (at {location})"
        self.warnings.append(warning)

    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def has_critical_errors(self) -> bool:
        """Check if any critical (non-recoverable) errors were recorded."""
        return any(isinstance(e, DocumentCorruptedError) for e in self.errors)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all errors and warnings."""
        return {
            "file_path": self.file_path,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "has_critical_errors": self.has_critical_errors(),
        }

    def raise_if_critical(self) -> None:
        """Raise the first critical error if any exist."""
        for error in self.errors:
            if isinstance(error, DocumentCorruptedError):
                raise error

    def create_partial_error(self, partial_result: Any = None) -> PartialParseError:
        """Create a PartialParseError from collected errors."""
        failed_sections = []
        for error in self.errors:
            if error.location:
                failed_sections.append(error.location)
        
        return PartialParseError(
            message=f"Parsing completed with {len(self.errors)} errors",
            file_path=self.file_path,
            location=None,
            details={
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
            },
            partial_result=partial_result,
            failed_sections=failed_sections,
        )
