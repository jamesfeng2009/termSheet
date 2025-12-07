"""View rendering for side-by-side document comparison."""

from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

from ..models.document import ParsedDocument, DocumentSection
from ..models.extraction import TSExtractionResult, ExtractedTerm
from ..interfaces.generator import GeneratedContract, Modification
from ..interfaces.review import ReviewSession


class ViewRenderer:
    """
    Renders side-by-side view of TS and contract documents.
    
    Uses Jinja2 templates to generate HTML views for document comparison
    and review.
    """

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the view renderer.
        
        Args:
            template_dir: Directory containing Jinja2 templates.
                         If not provided, uses default templates directory.
        """
        if template_dir is None:
            # Default to templates directory in project root
            template_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "templates"
            )
        
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def render_side_by_side(
        self,
        ts_doc: ParsedDocument,
        ts_result: TSExtractionResult,
        contract_doc: ParsedDocument,
        contract: GeneratedContract,
        session: ReviewSession,
    ) -> str:
        """
        Render side-by-side view of TS and contract.
        
        Args:
            ts_doc: Parsed TS document.
            ts_result: Extracted TS terms.
            contract_doc: Parsed contract template document.
            contract: Generated contract with modifications.
            session: Review session with user decisions.
            
        Returns:
            HTML string for the side-by-side view.
        """
        # Prepare TS document data
        ts_sections = self._prepare_sections(ts_doc.sections)
        ts_terms = self._prepare_terms(ts_result.terms)
        
        # Prepare contract document data
        contract_sections = self._prepare_sections(contract_doc.sections)
        modifications = self._prepare_modifications(contract.modifications)
        
        # Prepare review items
        review_items = self._prepare_review_items(session.items)
        
        # Create mapping between TS terms and contract clauses
        term_to_clause_map = self._create_term_clause_mapping(contract.modifications)
        
        # Load and render template
        template = self.env.get_template('side_by_side.html')
        return template.render(
            ts_sections=ts_sections,
            ts_terms=ts_terms,
            contract_sections=contract_sections,
            modifications=modifications,
            review_items=review_items,
            term_to_clause_map=term_to_clause_map,
            session_id=session.id,
            contract_id=contract.id,
            progress=f"{session.completed_count}/{session.total_count}",
        )

    def _prepare_sections(self, sections: List[DocumentSection]) -> List[Dict]:
        """Convert document sections to template-friendly format."""
        result = []
        for section in sections:
            section_data = {
                'id': section.id,
                'title': section.title or '',
                'number': section.number or '',
                'level': section.level.value,
                'segments': [
                    {
                        'id': seg.id,
                        'content': seg.content,
                        'language': seg.language,
                        'formatting': seg.formatting,
                    }
                    for seg in section.segments
                ],
                'children': self._prepare_sections(section.children),
            }
            result.append(section_data)
        return result

    def _prepare_terms(self, terms: List[ExtractedTerm]) -> List[Dict]:
        """Convert extracted terms to template-friendly format."""
        return [
            {
                'id': term.id,
                'category': term.category.value,
                'title': term.title,
                'value': str(term.value),
                'raw_text': term.raw_text,
                'source_section_id': term.source_section_id,
                'source_paragraph_id': term.source_paragraph_id,
                'confidence': term.confidence,
            }
            for term in terms
        ]

    def _prepare_modifications(self, modifications: List[Modification]) -> List[Dict]:
        """Convert modifications to template-friendly format."""
        return [
            {
                'id': mod.id,
                'match_id': mod.match_id,
                'original_text': mod.original_text,
                'new_text': mod.new_text,
                'location_start': mod.location_start,
                'location_end': mod.location_end,
                'action': mod.action.value,
                'source_ts_paragraph_id': mod.source_ts_paragraph_id,
                'confidence': mod.confidence,
                'annotations': mod.annotations,
            }
            for mod in modifications
        ]

    def _prepare_review_items(self, items: List) -> List[Dict]:
        """Convert review items to template-friendly format."""
        return [
            {
                'modification_id': item.modification_id,
                'ts_term_id': item.ts_term_id,
                'clause_id': item.clause_id,
                'original_text': item.original_text,
                'new_text': item.new_text,
                'confidence': item.confidence,
                'action': item.action.value,
                'user_comment': item.user_comment or '',
            }
            for item in items
        ]

    def _create_term_clause_mapping(self, modifications: List[Modification]) -> Dict[str, str]:
        """Create mapping from TS term IDs to clause IDs."""
        mapping = {}
        for mod in modifications:
            mapping[mod.source_ts_paragraph_id] = mod.match_id
        return mapping
