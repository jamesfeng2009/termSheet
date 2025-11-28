"""TS extractor interface for the TS Contract Alignment System."""

from abc import ABC, abstractmethod

from ..models.document import ParsedDocument
from ..models.extraction import TSExtractionResult


class ITSExtractor(ABC):
    """
    Abstract interface for Term Sheet information extraction.
    
    Implementations of this interface handle extraction of business
    terms from parsed Term Sheet documents.
    """

    @abstractmethod
    def extract(self, parsed_doc: ParsedDocument) -> TSExtractionResult:
        """
        Extract business terms from a parsed Term Sheet document.
        
        Args:
            parsed_doc: The parsed Term Sheet document.
            
        Returns:
            TSExtractionResult containing all extracted terms.
        """
        pass

    @abstractmethod
    def serialize(self, result: TSExtractionResult) -> str:
        """
        Serialize a TSExtractionResult to JSON string.
        
        Args:
            result: The extraction result to serialize.
            
        Returns:
            JSON string representation of the extraction result.
        """
        pass

    @abstractmethod
    def deserialize(self, json_str: str) -> TSExtractionResult:
        """
        Deserialize a JSON string to a TSExtractionResult.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            TSExtractionResult reconstructed from the JSON.
            
        Raises:
            ValueError: If the JSON is invalid or malformed.
        """
        pass
