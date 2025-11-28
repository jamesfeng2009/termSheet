"""Base document parser implementation."""

from pathlib import Path

from ..interfaces.parser import IDocumentParser
from ..models.document import ParsedDocument
from ..models.enums import DocumentType
from .exceptions import UnsupportedFormatError
from .pdf_parser import PDFDocumentParser
from .serialization import DocumentSerializer
from .word_parser import WordDocumentParser


class DocumentParser(IDocumentParser):
    """
    Main document parser that delegates to format-specific parsers.
    
    Implements the IDocumentParser interface and provides a unified
    API for parsing Word and PDF documents.
    """

    def __init__(self):
        self._word_parser = WordDocumentParser()
        self._pdf_parser = PDFDocumentParser()
        self._serializer = DocumentSerializer()

    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse a document and return its structured representation.
        
        Automatically detects the document format and delegates to
        the appropriate parser.
        
        Args:
            file_path: Path to the document file to parse.
            
        Returns:
            ParsedDocument containing the structured content.
            
        Raises:
            FileNotFoundError: If the file does not exist.
            UnsupportedFormatError: If the file format is not supported.
            DocumentCorruptedError: If the document is corrupted.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix == ".docx":
            return self._word_parser.parse(file_path)
        elif suffix == ".pdf":
            return self._pdf_parser.parse(file_path)
        else:
            raise UnsupportedFormatError(
                message=f"Unsupported file format: {suffix}",
                file_path=file_path,
                location="file extension",
                details={"supported_formats": [".docx", ".pdf"]}
            )

    def serialize(self, doc: ParsedDocument) -> str:
        """
        Serialize a ParsedDocument to JSON string.
        
        Args:
            doc: The ParsedDocument to serialize.
            
        Returns:
            JSON string representation of the document.
        """
        return self._serializer.serialize(doc)

    def deserialize(self, json_str: str) -> ParsedDocument:
        """
        Deserialize a JSON string to a ParsedDocument.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            ParsedDocument reconstructed from the JSON.
            
        Raises:
            ValueError: If the JSON is invalid or malformed.
        """
        return self._serializer.deserialize(json_str)

    def get_supported_formats(self) -> list[str]:
        """Return list of supported file formats."""
        return [".docx", ".pdf"]

    def detect_document_type(self, file_path: str) -> DocumentType:
        """
        Detect the document type from file extension.
        
        Args:
            file_path: Path to the document file.
            
        Returns:
            DocumentType enum value.
            
        Raises:
            UnsupportedFormatError: If format is not supported.
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix == ".docx":
            return DocumentType.WORD
        elif suffix == ".pdf":
            return DocumentType.PDF
        else:
            raise UnsupportedFormatError(
                message=f"Unsupported file format: {suffix}",
                file_path=file_path,
                location="file extension"
            )
