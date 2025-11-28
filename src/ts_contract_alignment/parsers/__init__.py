"""Document parsers for the TS Contract Alignment System."""

from .base import DocumentParser
from .word_parser import WordDocumentParser
from .pdf_parser import PDFDocumentParser
from .serialization import DocumentSerializer, serialize_document, deserialize_document
from .exceptions import (
    ParseError,
    DocumentCorruptedError,
    UnsupportedFormatError,
    PartialParseError,
    ErrorHandler,
)

__all__ = [
    "DocumentParser",
    "WordDocumentParser",
    "PDFDocumentParser",
    "DocumentSerializer",
    "serialize_document",
    "deserialize_document",
    "ParseError",
    "DocumentCorruptedError",
    "UnsupportedFormatError",
    "PartialParseError",
    "ErrorHandler",
]
