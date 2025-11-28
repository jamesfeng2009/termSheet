"""Document parser interface for the TS Contract Alignment System."""

from abc import ABC, abstractmethod

from ..models.document import ParsedDocument


class IDocumentParser(ABC):
    """
    Abstract interface for document parsing.
    
    Implementations of this interface handle parsing of different
    document formats (Word, PDF) into a structured representation.
    """

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse a document and return its structured representation.
        
        Args:
            file_path: Path to the document file to parse.
            
        Returns:
            ParsedDocument containing the structured content.
            
        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is not supported.
            ParseError: If the document is corrupted or unreadable.
        """
        pass

    @abstractmethod
    def serialize(self, doc: ParsedDocument) -> str:
        """
        Serialize a ParsedDocument to JSON string.
        
        Args:
            doc: The ParsedDocument to serialize.
            
        Returns:
            JSON string representation of the document.
        """
        pass

    @abstractmethod
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
        pass
