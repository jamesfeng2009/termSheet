"""Unit tests for the Contract Generator."""

import uuid
from datetime import datetime

import pytest

from ts_contract_alignment.generators import (
    ContractGenerator,
    AnnotationConfig,
    AnnotationManager,
    AnnotationStyle,
    ConflictHandler,
    ConflictType,
    ConflictResolution,
    DocumentExporter,
)
from ts_contract_alignment.interfaces.generator import GeneratedContract, Modification
from ts_contract_alignment.models.alignment import AlignmentMatch, AlignmentResult
from ts_contract_alignment.models.document import (
    DocumentSection,
    ParsedDocument,
    TextSegment,
)
from ts_contract_alignment.models.enums import (
    ActionType,
    DocumentType,
    HeadingLevel,
    MatchMethod,
    TermCategory,
)
from ts_contract_alignment.models.extraction import ExtractedTerm, TSExtractionResult


class TestContractGenerator:
    """Tests for ContractGenerator class."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create a ContractGenerator instance."""
        return ContractGenerator(output_dir=str(tmp_path))

    @pytest.fixture
    def sample_template_doc(self):
        """Create a sample template document."""
        return ParsedDocument(
            id="template_001",
            filename="contract_template.docx",
            doc_type=DocumentType.WORD,
            sections=[
                DocumentSection(
                    id="sec_001",
                    title="Investment Terms",
                    number="1",
                    level=HeadingLevel.SECTION,
                    segments=[
                        TextSegment(
                            id="seg_001",
                            content="The investment amount shall be [AMOUNT].",
                            start_pos=0,
                            end_pos=42,
                            language="en",
                            formatting={"bold": False},
                        )
                    ],
                    children=[],
                )
            ],
            metadata={"page_count": 10},
            raw_text="Investment Terms\nThe investment amount shall be [AMOUNT].",
        )

    @pytest.fixture
    def sample_ts_result(self):
        """Create a sample TS extraction result."""
        return TSExtractionResult(
            document_id="ts_001",
            terms=[
                ExtractedTerm(
                    id="term_001",
                    category=TermCategory.INVESTMENT_AMOUNT,
                    title="Investment Amount",
                    value=10000000,
                    raw_text="Investment Amount: USD 10,000,000",
                    source_section_id="ts_sec_001",
                    source_paragraph_id="ts_para_001",
                    confidence=0.95,
                    metadata={},
                )
            ],
            unrecognized_sections=[],
            extraction_timestamp=datetime.utcnow().isoformat(),
        )

    @pytest.fixture
    def sample_alignment_result(self):
        """Create a sample alignment result."""
        return AlignmentResult(
            ts_document_id="ts_001",
            template_document_id="template_001",
            matches=[
                AlignmentMatch(
                    id="match_001",
                    ts_term_id="term_001",
                    clause_id="sec_001",
                    fillable_segment_id="seg_001",
                    match_method=MatchMethod.RULE_KEYWORD,
                    confidence=0.92,
                    action=ActionType.INSERT,
                    needs_review=False,
                )
            ],
            unmatched_terms=[],
            unmatched_clauses=[],
            alignment_timestamp=datetime.utcnow().isoformat(),
        )

    def test_generate_creates_contract(
        self, generator, sample_template_doc, sample_alignment_result, sample_ts_result
    ):
        """Test that generate creates a GeneratedContract."""
        contract = generator.generate(
            sample_template_doc, sample_alignment_result, sample_ts_result
        )

        assert isinstance(contract, GeneratedContract)
        assert contract.template_document_id == "template_001"
        assert contract.ts_document_id == "ts_001"
        assert len(contract.modifications) == 1

    def test_generate_creates_modification_with_correct_action(
        self, generator, sample_template_doc, sample_alignment_result, sample_ts_result
    ):
        """Test that modifications have correct action type."""
        contract = generator.generate(
            sample_template_doc, sample_alignment_result, sample_ts_result
        )

        mod = contract.modifications[0]
        assert mod.action == ActionType.INSERT
        assert mod.source_ts_paragraph_id == "ts_para_001"
        assert mod.confidence == 0.92

    def test_generate_creates_annotations(
        self, generator, sample_template_doc, sample_alignment_result, sample_ts_result
    ):
        """Test that modifications include annotations."""
        contract = generator.generate(
            sample_template_doc, sample_alignment_result, sample_ts_result
        )

        mod = contract.modifications[0]
        assert "timestamp" in mod.annotations
        assert "action_type" in mod.annotations
        assert mod.annotations["action_type"] == "insert"

    def test_generate_formats_currency_values(
        self, generator, sample_template_doc, sample_alignment_result, sample_ts_result
    ):
        """Test that currency values are formatted correctly."""
        contract = generator.generate(
            sample_template_doc, sample_alignment_result, sample_ts_result
        )

        mod = contract.modifications[0]
        assert "USD" in mod.new_text
        assert "10,000,000" in mod.new_text

    def test_generate_skips_skip_actions(
        self, generator, sample_template_doc, sample_ts_result
    ):
        """Test that SKIP actions are not included in modifications."""
        alignment_result = AlignmentResult(
            ts_document_id="ts_001",
            template_document_id="template_001",
            matches=[
                AlignmentMatch(
                    id="match_001",
                    ts_term_id="term_001",
                    clause_id="sec_001",
                    fillable_segment_id="seg_001",
                    match_method=MatchMethod.RULE_KEYWORD,
                    confidence=0.92,
                    action=ActionType.SKIP,
                    needs_review=False,
                )
            ],
            unmatched_terms=[],
            unmatched_clauses=[],
            alignment_timestamp=datetime.utcnow().isoformat(),
        )

        contract = generator.generate(
            sample_template_doc, alignment_result, sample_ts_result
        )

        assert len(contract.modifications) == 0

    def test_generate_sets_file_paths(
        self, generator, sample_template_doc, sample_alignment_result, sample_ts_result
    ):
        """Test that file paths are set correctly."""
        contract = generator.generate(
            sample_template_doc, sample_alignment_result, sample_ts_result
        )

        assert contract.revision_tracked_path.endswith("_tracked.docx")
        assert contract.clean_version_path.endswith("_clean.docx")


class TestAnnotationManager:
    """Tests for AnnotationManager class."""

    @pytest.fixture
    def manager(self):
        """Create an AnnotationManager instance."""
        return AnnotationManager()

    @pytest.fixture
    def sample_modification(self):
        """Create a sample modification."""
        return Modification(
            id="mod_001",
            match_id="match_001",
            original_text="[AMOUNT]",
            new_text="USD 10,000,000",
            location_start=0,
            location_end=8,
            action=ActionType.INSERT,
            source_ts_paragraph_id="ts_para_001",
            confidence=0.92,
            annotations={},
        )

    def test_create_annotation(self, manager, sample_modification):
        """Test creating an annotation."""
        annotation = manager.create_annotation(sample_modification)

        assert annotation.modification_id == "mod_001"
        assert annotation.source_ts_paragraph_id == "ts_para_001"
        assert annotation.action_type == ActionType.INSERT
        assert annotation.confidence == 0.92

    def test_annotation_to_text(self, manager, sample_modification):
        """Test converting annotation to text."""
        annotation = manager.create_annotation(sample_modification)
        text = annotation.to_text(manager.config)

        assert "TS:ts_para_001" in text
        assert "INSERT" in text
        assert "92%" in text

    def test_export_annotations_summary(self, manager, sample_modification):
        """Test exporting annotations summary."""
        manager.create_annotation(sample_modification)
        summary = manager.export_annotations_summary()

        assert len(summary) == 1
        assert summary[0]["modification_id"] == "mod_001"


class TestConflictHandler:
    """Tests for ConflictHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a ConflictHandler instance."""
        return ConflictHandler()

    @pytest.fixture
    def sample_modification(self):
        """Create a sample modification."""
        return Modification(
            id="mod_001",
            match_id="match_001",
            original_text="Original text",
            new_text="New text",
            location_start=0,
            location_end=13,
            action=ActionType.OVERRIDE,
            source_ts_paragraph_id="ts_para_001",
            confidence=0.85,
            annotations={},
        )

    def test_detect_formatting_conflict(self, handler, sample_modification):
        """Test detecting formatting conflicts."""
        original = {"bold": True, "font_size": 12}
        target = {"bold": False, "font_size": 14}

        conflict = handler.detect_formatting_conflict(
            original, target, sample_modification
        )

        assert conflict is not None
        assert conflict.conflict_type == ConflictType.FORMATTING_MISMATCH

    def test_no_conflict_when_formats_match(self, handler, sample_modification):
        """Test no conflict when formats match."""
        original = {"bold": True, "font_size": 12}
        target = {"bold": True, "font_size": 12}

        conflict = handler.detect_formatting_conflict(
            original, target, sample_modification
        )

        assert conflict is None

    def test_detect_location_not_found(self, handler, sample_modification):
        """Test detecting location not found conflict."""
        document_text = "This is completely different text."

        conflict = handler.detect_location_not_found(
            sample_modification, document_text
        )

        assert conflict is not None
        assert conflict.conflict_type == ConflictType.LOCATION_NOT_FOUND

    def test_resolve_conflict_preserve_original(self, handler, sample_modification):
        """Test resolving conflict by preserving original."""
        original = {"bold": True}
        target = {"bold": False}

        conflict = handler.detect_formatting_conflict(
            original, target, sample_modification
        )

        resolved = handler.resolve_conflict(conflict)
        assert resolved == original

    def test_get_conflicts_by_type(self, handler, sample_modification):
        """Test getting conflicts by type."""
        handler.detect_formatting_conflict(
            {"bold": True}, {"bold": False}, sample_modification
        )

        conflicts = handler.get_conflicts_by_type(ConflictType.FORMATTING_MISMATCH)
        assert len(conflicts) == 1

    def test_export_conflict_report(self, handler, sample_modification):
        """Test exporting conflict report."""
        handler.detect_formatting_conflict(
            {"bold": True}, {"bold": False}, sample_modification
        )

        report = handler.export_conflict_report()
        assert report["total_conflicts"] == 1
        assert "by_type" in report


class TestModification:
    """Tests for Modification dataclass."""

    def test_modification_creation(self):
        """Test creating a Modification."""
        mod = Modification(
            id="mod_001",
            match_id="match_001",
            original_text="Original",
            new_text="New",
            location_start=0,
            location_end=8,
            action=ActionType.INSERT,
            source_ts_paragraph_id="para_001",
            confidence=0.9,
        )

        assert mod.id == "mod_001"
        assert mod.action == ActionType.INSERT
        assert mod.annotations == {}

    def test_modification_with_annotations(self):
        """Test Modification with annotations."""
        mod = Modification(
            id="mod_001",
            match_id="match_001",
            original_text="Original",
            new_text="New",
            location_start=0,
            location_end=8,
            action=ActionType.OVERRIDE,
            source_ts_paragraph_id="para_001",
            confidence=0.85,
            annotations={"key": "value"},
        )

        assert mod.annotations["key"] == "value"
