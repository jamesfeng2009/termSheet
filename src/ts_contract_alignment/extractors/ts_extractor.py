"""TS Extractor implementation for the TS Contract Alignment System.

This module implements the ITSExtractor interface to extract business terms
from parsed Term Sheet documents.
"""

import json
import uuid
from datetime import datetime
from typing import Any, List, Optional

from ..interfaces.extractor import ITSExtractor
from ..models.document import DocumentSection, ParsedDocument, TextSegment
from ..models.enums import TermCategory
from ..models.extraction import ExtractedTerm, TSExtractionResult
from .term_patterns import TermPatternMatcher


class TSExtractor(ITSExtractor):
    """
    Term Sheet information extractor.
    
    Extracts business terms from parsed Term Sheet documents using
    pattern matching and keyword analysis.
    """

    def __init__(self):
        self._pattern_matcher = TermPatternMatcher()
        self._term_counter = 0

    def extract(self, parsed_doc: ParsedDocument) -> TSExtractionResult:
        """
        Extract business terms from a parsed Term Sheet document.
        
        Args:
            parsed_doc: The parsed Term Sheet document.
            
        Returns:
            TSExtractionResult containing all extracted terms.
        """
        self._term_counter = 0
        terms: List[ExtractedTerm] = []
        unrecognized_sections: List[str] = []
        
        # Process all sections recursively
        for section in parsed_doc.sections:
            section_terms, section_unrecognized = self._process_section(
                section, parsed_doc.id
            )
            terms.extend(section_terms)
            unrecognized_sections.extend(section_unrecognized)
        
        # Ensure unique IDs
        self._ensure_unique_ids(terms)
        
        return TSExtractionResult(
            document_id=parsed_doc.id,
            terms=terms,
            unrecognized_sections=unrecognized_sections,
            extraction_timestamp=datetime.utcnow().isoformat()
        )

    def _process_section(
        self, section: DocumentSection, doc_id: str
    ) -> tuple[List[ExtractedTerm], List[str]]:
        """Process a document section and extract terms."""
        terms: List[ExtractedTerm] = []
        unrecognized: List[str] = []
        
        # Combine section title and content for analysis
        section_text = self._get_section_text(section)
        
        # Try to match the section to a term category
        category, confidence = self._pattern_matcher.match_category(section_text)
        
        if category:
            term = self._create_term_from_section(
                section, category, confidence, doc_id
            )
            if term:
                terms.append(term)
        elif section.title and section_text.strip():
            # Section couldn't be categorized
            unrecognized.append(section.id)
        
        # Process child sections recursively
        for child in section.children:
            child_terms, child_unrecognized = self._process_section(child, doc_id)
            terms.extend(child_terms)
            unrecognized.extend(child_unrecognized)
        
        return terms, unrecognized

    def _get_section_text(self, section: DocumentSection) -> str:
        """Get combined text from a section."""
        parts = []
        if section.title:
            parts.append(section.title)
        for segment in section.segments:
            parts.append(segment.content)
        return " ".join(parts)

    def _create_term_from_section(
        self,
        section: DocumentSection,
        category: TermCategory,
        confidence: float,
        doc_id: str
    ) -> Optional[ExtractedTerm]:
        """Create an ExtractedTerm from a document section."""
        section_text = self._get_section_text(section)
        
        # Extract value if possible
        value = self._pattern_matcher.extract_value(section_text, category)
        if value is None:
            value = section_text  # Use full text as value if no specific value found
        
        # Generate unique paragraph ID
        paragraph_id = self._generate_paragraph_id(section)
        
        # Get source segment ID (first segment if available)
        source_segment_id = (
            section.segments[0].id if section.segments else section.id
        )
        
        return ExtractedTerm(
            id=self._generate_term_id(),
            category=category,
            title=section.title or f"{category.value} term",
            value=value,
            raw_text=section_text,
            source_section_id=section.id,
            source_paragraph_id=paragraph_id,
            confidence=confidence,
            metadata={
                "section_number": section.number,
                "section_level": section.level.value,
                "document_id": doc_id,
            }
        )

    def _generate_term_id(self) -> str:
        """Generate a unique term ID."""
        self._term_counter += 1
        return f"term_{self._term_counter:04d}"

    def _generate_paragraph_id(self, section: DocumentSection) -> str:
        """Generate a unique paragraph ID for a section."""
        if section.number:
            return f"para_{section.number.replace('.', '_')}"
        return f"para_{section.id}"

    def _ensure_unique_ids(self, terms: List[ExtractedTerm]) -> None:
        """Ensure all terms have unique IDs."""
        seen_ids: set[str] = set()
        for term in terms:
            if term.id in seen_ids:
                # Generate new unique ID
                term.id = f"term_{uuid.uuid4().hex[:8]}"
            seen_ids.add(term.id)

    def serialize(self, result: TSExtractionResult) -> str:
        """
        Serialize a TSExtractionResult to JSON string.
        
        Args:
            result: The extraction result to serialize.
            
        Returns:
            JSON string representation of the extraction result.
        """
        return json.dumps(
            self._result_to_dict(result),
            ensure_ascii=False,
            indent=2
        )

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
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        return self._dict_to_result(data)

    def _result_to_dict(self, result: TSExtractionResult) -> dict[str, Any]:
        """Convert TSExtractionResult to dictionary."""
        return {
            "document_id": result.document_id,
            "terms": [self._term_to_dict(t) for t in result.terms],
            "unrecognized_sections": result.unrecognized_sections,
            "extraction_timestamp": result.extraction_timestamp,
        }

    def _dict_to_result(self, data: dict[str, Any]) -> TSExtractionResult:
        """Convert dictionary to TSExtractionResult."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for TSExtractionResult")
        
        if "document_id" not in data:
            raise ValueError("Missing required field 'document_id'")
        
        return TSExtractionResult(
            document_id=data["document_id"],
            terms=[self._dict_to_term(t) for t in data.get("terms", [])],
            unrecognized_sections=data.get("unrecognized_sections", []),
            extraction_timestamp=data.get("extraction_timestamp", ""),
        )

    def _term_to_dict(self, term: ExtractedTerm) -> dict[str, Any]:
        """Convert ExtractedTerm to dictionary."""
        return {
            "id": term.id,
            "category": term.category.value,
            "title": term.title,
            "value": term.value,
            "raw_text": term.raw_text,
            "source_section_id": term.source_section_id,
            "source_paragraph_id": term.source_paragraph_id,
            "confidence": term.confidence,
            "metadata": term.metadata,
        }

    def _dict_to_term(self, data: dict[str, Any]) -> ExtractedTerm:
        """Convert dictionary to ExtractedTerm."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for ExtractedTerm")
        
        required_fields = [
            "id", "category", "title", "value", "raw_text",
            "source_section_id", "source_paragraph_id", "confidence"
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in ExtractedTerm")
        
        return ExtractedTerm(
            id=data["id"],
            category=TermCategory(data["category"]),
            title=data["title"],
            value=data["value"],
            raw_text=data["raw_text"],
            source_section_id=data["source_section_id"],
            source_paragraph_id=data["source_paragraph_id"],
            confidence=data["confidence"],
            metadata=data.get("metadata", {}),
        )
