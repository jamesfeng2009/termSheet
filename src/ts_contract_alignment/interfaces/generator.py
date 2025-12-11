"""Contract generator interface for the TS Contract Alignment System."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from ..models.alignment import AlignmentResult
from ..models.document import ParsedDocument
from ..models.enums import ActionType
from ..models.extraction import TSExtractionResult


@dataclass
class Modification:
    """
    Document modification record.
    
    Represents a single modification made to the contract document,
    including the original and new text, location, and source information.
    
    The optional ``status`` field is used by the review workflow to track
    whether a modification is pending, accepted, rejected, or auto-applied.
    It is intentionally modeled as a simple string to avoid additional
    dependencies and to remain backwards compatible with existing JSON
    persistence of modifications.
    """
    id: str
    match_id: str
    original_text: str
    new_text: str
    location_start: int
    location_end: int
    action: ActionType
    source_ts_paragraph_id: str
    confidence: float
    annotations: dict = field(default_factory=dict)
    status: str = "pending"

    def __post_init__(self):
        if self.annotations is None:
            self.annotations = {}
        if not self.status:
            self.status = "pending"


@dataclass
class GeneratedContract:
    """
    Generated contract document.
    
    Represents the output of the contract generation process,
    including all modifications and file paths for exported versions.
    """
    id: str
    template_document_id: str
    ts_document_id: str
    modifications: List[Modification] = field(default_factory=list)
    revision_tracked_path: str = ""
    clean_version_path: str = ""
    generation_timestamp: str = ""

    def __post_init__(self):
        if self.modifications is None:
            self.modifications = []


class IContractGenerator(ABC):
    """
    Abstract interface for contract generation.
    
    Implementations of this interface handle applying alignment
    results to generate completed contracts with annotations.
    """

    @abstractmethod
    def generate(
        self,
        template_doc: ParsedDocument,
        alignment_result: AlignmentResult,
        ts_result: TSExtractionResult,
    ) -> GeneratedContract:
        """
        Generate a completed contract by applying alignment mappings.
        
        Args:
            template_doc: The parsed contract template document.
            alignment_result: The alignment result with term-to-clause mappings.
            ts_result: The extracted TS terms.
            
        Returns:
            GeneratedContract with all modifications applied.
        """
        pass

    @abstractmethod
    def export_docx(
        self,
        contract: GeneratedContract,
        with_revisions: bool = True,
    ) -> str:
        """
        Export the generated contract to a .docx file.
        
        Args:
            contract: The generated contract to export.
            with_revisions: Whether to include revision tracking marks.
            
        Returns:
            File path to the exported .docx document.
        """
        pass
