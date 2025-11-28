"""Serialization and deserialization utilities for parsed documents."""

import json
from typing import Any

from ..models.document import DocumentSection, ParsedDocument, TextSegment
from ..models.enums import DocumentType, HeadingLevel


class DocumentSerializer:
    """
    Handles serialization and deserialization of ParsedDocument structures.
    
    Ensures round-trip consistency: serialize(deserialize(json)) == json
    and deserialize(serialize(doc)) == doc
    """

    @staticmethod
    def serialize(doc: ParsedDocument) -> str:
        """
        Serialize a ParsedDocument to JSON string.
        
        Args:
            doc: The ParsedDocument to serialize.
            
        Returns:
            JSON string representation of the document.
        """
        return json.dumps(
            DocumentSerializer._doc_to_dict(doc),
            ensure_ascii=False,
            indent=2
        )

    @staticmethod
    def deserialize(json_str: str) -> ParsedDocument:
        """
        Deserialize a JSON string to a ParsedDocument.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            ParsedDocument reconstructed from the JSON.
            
        Raises:
            ValueError: If the JSON is invalid or malformed.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        return DocumentSerializer._dict_to_doc(data)

    @staticmethod
    def _doc_to_dict(doc: ParsedDocument) -> dict[str, Any]:
        """Convert ParsedDocument to dictionary."""
        return {
            "id": doc.id,
            "filename": doc.filename,
            "doc_type": doc.doc_type.value,
            "sections": [DocumentSerializer._section_to_dict(s) for s in doc.sections],
            "metadata": doc.metadata,
            "raw_text": doc.raw_text,
        }

    @staticmethod
    def _dict_to_doc(data: dict[str, Any]) -> ParsedDocument:
        """Convert dictionary to ParsedDocument."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for ParsedDocument")
        
        required_fields = ["id", "filename", "doc_type"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        return ParsedDocument(
            id=data["id"],
            filename=data["filename"],
            doc_type=DocumentType(data["doc_type"]),
            sections=[DocumentSerializer._dict_to_section(s) for s in data.get("sections", [])],
            metadata=data.get("metadata", {}),
            raw_text=data.get("raw_text", ""),
        )

    @staticmethod
    def _section_to_dict(section: DocumentSection) -> dict[str, Any]:
        """Convert DocumentSection to dictionary."""
        return {
            "id": section.id,
            "title": section.title,
            "number": section.number,
            "level": section.level.value,
            "segments": [DocumentSerializer._segment_to_dict(s) for s in section.segments],
            "children": [DocumentSerializer._section_to_dict(c) for c in section.children],
            "parent_id": section.parent_id,
        }

    @staticmethod
    def _dict_to_section(data: dict[str, Any]) -> DocumentSection:
        """Convert dictionary to DocumentSection."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for DocumentSection")
        
        if "id" not in data:
            raise ValueError("Missing required field 'id' in DocumentSection")
        
        return DocumentSection(
            id=data["id"],
            title=data.get("title"),
            number=data.get("number"),
            level=HeadingLevel(data.get("level", HeadingLevel.PARAGRAPH.value)),
            segments=[DocumentSerializer._dict_to_segment(s) for s in data.get("segments", [])],
            children=[DocumentSerializer._dict_to_section(c) for c in data.get("children", [])],
            parent_id=data.get("parent_id"),
        )

    @staticmethod
    def _segment_to_dict(segment: TextSegment) -> dict[str, Any]:
        """Convert TextSegment to dictionary."""
        return {
            "id": segment.id,
            "content": segment.content,
            "start_pos": segment.start_pos,
            "end_pos": segment.end_pos,
            "language": segment.language,
            "formatting": segment.formatting,
        }

    @staticmethod
    def _dict_to_segment(data: dict[str, Any]) -> TextSegment:
        """Convert dictionary to TextSegment."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for TextSegment")
        
        required_fields = ["id", "content", "start_pos", "end_pos", "language"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in TextSegment")
        
        return TextSegment(
            id=data["id"],
            content=data["content"],
            start_pos=data["start_pos"],
            end_pos=data["end_pos"],
            language=data["language"],
            formatting=data.get("formatting", {}),
        )


def serialize_document(doc: ParsedDocument) -> str:
    """Convenience function to serialize a ParsedDocument."""
    return DocumentSerializer.serialize(doc)


def deserialize_document(json_str: str) -> ParsedDocument:
    """Convenience function to deserialize a ParsedDocument."""
    return DocumentSerializer.deserialize(json_str)
