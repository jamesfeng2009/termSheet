"""End-to-end processing pipeline for TS Contract Alignment System.

This module provides the main orchestration logic that wires together all
components to process Term Sheets and contract templates from upload to
final document generation.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .alignment.alignment_engine import AlignmentEngine
from .analyzers.template_analyzer import TemplateAnalyzer
from .audit.audit_logger import AuditLogger
from .audit.database import DatabaseManager
from .config.config_manager import ConfigurationManager
from .extractors.ts_extractor import TSExtractor
from .extractors.hybrid_extractor import HybridTSExtractor
from .generators.contract_generator import ContractGenerator
from .generators.conflict_handler import ConflictHandlerConfig
from .interfaces.alignment import IAlignmentEngine
from .interfaces.analyzer import ITemplateAnalyzer
from .interfaces.audit import AuditEventType, IAuditLogger
from .interfaces.extractor import ITSExtractor
from .interfaces.generator import GeneratedContract, IContractGenerator
from .interfaces.parser import IDocumentParser
from .models.alignment import AlignmentResult
from .models.document import ParsedDocument
from .models.extraction import TSExtractionResult
from .models.template import TemplateAnalysisResult
from .parsers.base import DocumentParser
from .parsers.exceptions import DocumentCorruptedError, ParseError
from .performance import DatabaseOptimizer, PerformanceMonitor, SimpleCache
from .review.review_manager import ReviewManager


logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the processing pipeline."""
    
    # Database configuration
    database_url: Optional[str] = None
    
    # Output directories
    output_dir: str = "data/generated"
    temp_dir: str = "data/temp"
    
    # Alignment configuration
    confidence_threshold: float = 0.7
    semantic_threshold: float = 0.6
    
    # Performance configuration
    enable_caching: bool = True
    max_processing_time: int = 60  # seconds
    
    # Feature flags
    enable_semantic_matching: bool = True
    enable_audit_logging: bool = True
    enable_version_history: bool = True
    
    # Configuration files
    config_dir: Optional[str] = None
    
    # Embedding model configuration
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    use_embedding_model: bool = False  # Set to True to enable semantic matching
    # Extraction configuration
    use_hybrid_extractor: bool = False  # Set to True to enable HybridTSExtractor

    # Alignment / review strategy configuration
    # Maps TermCategory.value -> "insert" | "override" | "auto" (default "auto").
    # When set to "insert" or "override" it will override the automatic
    # placeholder-based classification in AlignmentEngine._classify_action.
    action_policies: Dict[str, str] = field(default_factory=dict)

    # Per-category confidence thresholds for human review. Keys are
    # TermCategory.value strings and values are floats in [0.0, 1.0]. When a
    # threshold is specified for a category it takes precedence over the
    # global confidence_threshold when computing the needs_review flag.
    per_category_confidence_thresholds: Dict[str, float] = field(default_factory=dict)

    # Optional conflict resolution policies for contract generation. Keys are
    # ConflictType.value strings and values are ConflictResolution.value
    # strings, passed through to ConflictHandlerConfig.per_type_resolution.
    conflict_policies: Dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of a complete pipeline execution."""
    
    success: bool
    contract: Optional[GeneratedContract] = None
    ts_document: Optional[ParsedDocument] = None
    template_document: Optional[ParsedDocument] = None
    ts_extraction: Optional[TSExtractionResult] = None
    template_analysis: Optional[TemplateAnalysisResult] = None
    alignment: Optional[AlignmentResult] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineStats:
    """Statistics about pipeline execution."""
    
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_processing_time: float = 0.0
    total_processing_time: float = 0.0


class ProcessingPipeline:
    """
    Main processing pipeline for TS-Contract alignment.
    
    Orchestrates the complete workflow from document upload to
    contract generation, with error handling and audit logging.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        parser: Optional[IDocumentParser] = None,
        ts_extractor: Optional[ITSExtractor] = None,
        template_analyzer: Optional[ITemplateAnalyzer] = None,
        alignment_engine: Optional[IAlignmentEngine] = None,
        contract_generator: Optional[IContractGenerator] = None,
        audit_logger: Optional[IAuditLogger] = None,
        config_manager: Optional[ConfigurationManager] = None,
    ):
        """
        Initialize the processing pipeline.
        
        Args:
            config: Pipeline configuration.
            parser: Optional document parser (created if not provided).
            ts_extractor: Optional TS extractor (created if not provided).
            template_analyzer: Optional template analyzer (created if not provided).
            alignment_engine: Optional alignment engine (created if not provided).
            contract_generator: Optional contract generator (created if not provided).
            audit_logger: Optional audit logger (created if not provided).
            config_manager: Optional configuration manager (created if not provided).
        """
        self.config = config or PipelineConfig()
        self.stats = PipelineStats()
        
        # Initialize performance monitoring
        self.performance_monitor = PerformanceMonitor(
            max_processing_time=self.config.max_processing_time
        )
        
        # Initialize cache if enabled
        self._cache = SimpleCache() if self.config.enable_caching else None
        
        # Initialize database manager if needed
        self._db_manager = None
        if self.config.enable_audit_logging or self.config.enable_semantic_matching:
            self._db_manager = DatabaseManager(
                database_url=self.config.database_url,
                pool_size=10,  # Increased pool size for better concurrency
                max_overflow=20,  # Allow more overflow connections
            )
            
            # Optimize database for performance
            db_optimizer = DatabaseOptimizer(self._db_manager)
            try:
                db_optimizer.ensure_indexes()
                db_optimizer.optimize_vector_search()
                logger.info("Database optimizations applied")
            except Exception as e:
                logger.warning(f"Failed to apply database optimizations: {e}")
        
        # Initialize embedding model if needed
        self._embedding_model = None
        if self.config.use_embedding_model and self.config.enable_semantic_matching:
            self._embedding_model = self._load_embedding_model()
        
        # Initialize components
        self._parser = parser or DocumentParser()

        # TS extractor: support both legacy TSExtractor and new HybridTSExtractor.
        if ts_extractor is not None:
            self._ts_extractor = ts_extractor
        elif self.config.use_hybrid_extractor:
            self._ts_extractor = HybridTSExtractor()
        else:
            self._ts_extractor = TSExtractor()
        self._template_analyzer = template_analyzer or TemplateAnalyzer(
            embedding_model=self._embedding_model
        )
        self._alignment_engine = alignment_engine or AlignmentEngine(
            embedding_model=self._embedding_model,
            db_connection=self._db_manager.engine if self._db_manager else None,
            confidence_threshold=self.config.confidence_threshold,
        )
        # If a configuration manager is available and loaded, hydrate
        # PipelineConfig policy fields from SystemConfiguration before
        # constructing downstream components that rely on them.
        if self._config_manager is not None and self._config_manager.is_loaded:
            sys_cfg = self._config_manager.configuration
            if not self.config.action_policies and sys_cfg.action_policies:
                self.config.action_policies = dict(sys_cfg.action_policies)
            if (
                not self.config.per_category_confidence_thresholds
                and sys_cfg.review_thresholds_by_category
            ):
                self.config.per_category_confidence_thresholds = dict(
                    sys_cfg.review_thresholds_by_category
                )
            if not self.config.conflict_policies and sys_cfg.conflict_resolution_policies:
                self.config.conflict_policies = dict(
                    sys_cfg.conflict_resolution_policies
                )

        conflict_cfg = None
        if self.config.conflict_policies:
            conflict_cfg = ConflictHandlerConfig(
                per_type_resolution=self.config.conflict_policies
            )

        self._contract_generator = contract_generator or ContractGenerator(
            output_dir=self.config.output_dir,
            conflict_config=conflict_cfg,
        )
        self._audit_logger = audit_logger
        if self._audit_logger is None and self.config.enable_audit_logging:
            self._audit_logger = AuditLogger(db_manager=self._db_manager)
        
        self._config_manager = config_manager or ConfigurationManager(
            config_dir=self.config.config_dir
        )
        
        # Load configuration if directory specified
        if self.config.config_dir:
            try:
                self._config_manager.load_from_directory(self.config.config_dir)
                logger.info(f"Loaded configuration from {self.config.config_dir}")
            except Exception as e:
                logger.warning(f"Failed to load configuration: {e}")
        
        # Create output directories
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.temp_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("Processing pipeline initialized")

    def _load_embedding_model(self):
        """Load the sentence-transformers embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.config.embedding_model_name}")
            model = SentenceTransformer(self.config.embedding_model_name)
            logger.info("Embedding model loaded successfully")
            return model
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. Semantic matching disabled."
            )
            return None
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return None

    def process(
        self,
        ts_file_path: str,
        template_file_path: str,
        user_id: Optional[str] = None,
    ) -> PipelineResult:
        """
        Execute the complete processing pipeline.
        
        Args:
            ts_file_path: Path to the Term Sheet document.
            template_file_path: Path to the contract template document.
            user_id: Optional user ID for audit logging.
            
        Returns:
            PipelineResult containing the generated contract and metadata.
        """
        start_time = time.time()
        result = PipelineResult(success=False)
        
        # Start overall performance tracking
        overall_metric = self.performance_monitor.start_operation(
            "pipeline_execution",
            ts_file=ts_file_path,
            template_file=template_file_path
        )
        
        try:
            logger.info(f"Starting pipeline execution for TS: {ts_file_path}, Template: {template_file_path}")
            
            # Step 1: Parse documents
            parse_metric = self.performance_monitor.start_operation("parse_documents")
            ts_doc, template_doc = self._parse_documents(
                ts_file_path, template_file_path, user_id
            )
            self.performance_monitor.end_operation(parse_metric)
            result.ts_document = ts_doc
            result.template_document = template_doc
            
            # Step 2: Extract TS terms
            extract_metric = self.performance_monitor.start_operation("extract_ts_terms")
            ts_extraction = self._extract_ts_terms(ts_doc, user_id)
            self.performance_monitor.end_operation(extract_metric)
            result.ts_extraction = ts_extraction
            
            # Step 3: Analyze template
            analyze_metric = self.performance_monitor.start_operation("analyze_template")
            template_analysis = self._analyze_template(template_doc, user_id)
            self.performance_monitor.end_operation(analyze_metric)
            result.template_analysis = template_analysis
            
            # Step 4: Align TS terms with template clauses
            align_metric = self.performance_monitor.start_operation("align_terms_clauses")
            alignment = self._align_terms_and_clauses(
                ts_extraction, template_analysis, user_id
            )
            self.performance_monitor.end_operation(align_metric)
            result.alignment = alignment
            
            # Step 5: Generate contract
            generate_metric = self.performance_monitor.start_operation("generate_contract")
            contract = self._generate_contract(
                template_doc, alignment, ts_extraction, template_file_path, user_id
            )
            self.performance_monitor.end_operation(generate_metric)
            result.contract = contract
            
            # Step 6: Save version history if enabled
            if self.config.enable_version_history and self._audit_logger:
                version_metric = self.performance_monitor.start_operation("save_version_history")
                self._save_version_history(contract, ts_extraction, template_analysis, alignment)
                self.performance_monitor.end_operation(version_metric)
            
            # Mark as successful
            result.success = True
            result.processing_time = time.time() - start_time
            
            # Add performance metrics to result
            result.metadata["performance_stats"] = self.performance_monitor.get_all_stats()
            
            # End overall tracking
            self.performance_monitor.end_operation(overall_metric, success=True)
            
            logger.info(
                f"Pipeline execution completed successfully in {result.processing_time:.2f}s"
            )
            
            # Warn if processing time exceeded threshold
            if result.processing_time > self.config.max_processing_time:
                warning = (
                    f"Processing time ({result.processing_time:.2f}s) exceeded "
                    f"target ({self.config.max_processing_time}s)"
                )
                result.warnings.append(warning)
                logger.warning(warning)
            
        except DocumentCorruptedError as e:
            error_msg = f"Document corrupted: {e.message}"
            result.errors.append(error_msg)
            logger.error(error_msg)
            self.performance_monitor.end_operation(overall_metric, success=False, error=error_msg)
            
        except ParseError as e:
            error_msg = f"Parsing error: {e.message}"
            result.errors.append(error_msg)
            logger.error(error_msg)
            self.performance_monitor.end_operation(overall_metric, success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"Pipeline execution failed: {str(e)}"
            result.errors.append(error_msg)
            logger.exception(error_msg)
            self.performance_monitor.end_operation(overall_metric, success=False, error=error_msg)
            
        finally:
            result.processing_time = time.time() - start_time
            self._update_stats(result)
        
        return result

    def _parse_documents(
        self,
        ts_file_path: str,
        template_file_path: str,
        user_id: Optional[str],
    ) -> Tuple[ParsedDocument, ParsedDocument]:
        """Parse both TS and template documents."""
        logger.info("Step 1: Parsing documents")
        
        # Parse TS document
        try:
            ts_doc = self._parser.parse(ts_file_path)
            logger.info(f"TS document parsed: {len(ts_doc.sections)} sections")
            
            if self._audit_logger:
                self._audit_logger.log_document_parsed(
                    document_id=ts_doc.id,
                    filename=ts_doc.filename,
                    doc_type=ts_doc.doc_type.value,
                    section_count=len(ts_doc.sections),
                    user_id=user_id,
                )
        except Exception as e:
            logger.error(f"Failed to parse TS document: {e}")
            raise
        
        # Parse template document
        try:
            template_doc = self._parser.parse(template_file_path)
            logger.info(f"Template document parsed: {len(template_doc.sections)} sections")
            
            if self._audit_logger:
                self._audit_logger.log_document_parsed(
                    document_id=template_doc.id,
                    filename=template_doc.filename,
                    doc_type=template_doc.doc_type.value,
                    section_count=len(template_doc.sections),
                    user_id=user_id,
                )
        except Exception as e:
            logger.error(f"Failed to parse template document: {e}")
            raise
        
        return ts_doc, template_doc

    def _extract_ts_terms(
        self,
        ts_doc: ParsedDocument,
        user_id: Optional[str],
    ) -> TSExtractionResult:
        """Extract terms from TS document."""
        logger.info("Step 2: Extracting TS terms")
        
        try:
            extraction = self._ts_extractor.extract(ts_doc)
            logger.info(f"Extracted {len(extraction.terms)} terms from TS")
            
            if self._audit_logger:
                categories = list(set(term.category.value for term in extraction.terms))
                self._audit_logger.log_terms_extracted(
                    document_id=ts_doc.id,
                    term_count=len(extraction.terms),
                    categories=categories,
                    user_id=user_id,
                )
            
            return extraction
            
        except Exception as e:
            logger.error(f"Failed to extract TS terms: {e}")
            raise

    def _analyze_template(
        self,
        template_doc: ParsedDocument,
        user_id: Optional[str],
    ) -> TemplateAnalysisResult:
        """Analyze contract template."""
        logger.info("Step 3: Analyzing template")
        
        try:
            analysis = self._template_analyzer.analyze(template_doc)
            logger.info(f"Analyzed {len(analysis.clauses)} clauses in template")
            
            # Count fillable segments
            fillable_count = sum(
                len(clause.fillable_segments) for clause in analysis.clauses
            )
            
            if self._audit_logger:
                self._audit_logger.log_template_analyzed(
                    document_id=template_doc.id,
                    clause_count=len(analysis.clauses),
                    fillable_count=fillable_count,
                    user_id=user_id,
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze template: {e}")
            raise

    def _align_terms_and_clauses(
        self,
        ts_extraction: TSExtractionResult,
        template_analysis: TemplateAnalysisResult,
        user_id: Optional[str],
    ) -> AlignmentResult:
        """Align TS terms with template clauses."""
        logger.info("Step 4: Aligning terms and clauses")
        
        try:
            # Get configuration for alignment if available
            config = None
            if self._config_manager.is_loaded or self.config:
                config = {
                    "confidence_threshold": self.config.confidence_threshold,
                    "semantic_threshold": self.config.semantic_threshold,
                }

                # Thread per-category strategies from PipelineConfig into the
                # alignment engine. Keys are TermCategory.value strings.
                if self.config.action_policies:
                    config["action_policies_by_category"] = self.config.action_policies

                if self.config.per_category_confidence_thresholds:
                    config["review_thresholds_by_category"] = (
                        self.config.per_category_confidence_thresholds
                    )
            
            alignment = self._alignment_engine.align(
                ts_extraction, template_analysis, config
            )
            
            logger.info(
                f"Alignment completed: {len(alignment.matches)} matches, "
                f"{len(alignment.unmatched_terms)} unmatched terms"
            )
            
            if self._audit_logger:
                self._audit_logger.log_alignment_completed(
                    ts_document_id=ts_extraction.document_id,
                    template_document_id=template_analysis.document_id,
                    match_count=len(alignment.matches),
                    unmatched_term_count=len(alignment.unmatched_terms),
                    user_id=user_id,
                )
                
                # Log individual matches
                for match in alignment.matches:
                    self._audit_logger.log_match_created(
                        document_id=ts_extraction.document_id,
                        ts_term_id=match.ts_term_id,
                        clause_id=match.clause_id,
                        match_method=match.match_method.value,
                        confidence=match.confidence,
                        action=match.action.value,
                        user_id=user_id,
                    )
            
            return alignment
            
        except Exception as e:
            logger.error(f"Failed to align terms and clauses: {e}")
            raise

    def _generate_contract(
        self,
        template_doc: ParsedDocument,
        alignment: AlignmentResult,
        ts_extraction: TSExtractionResult,
        template_file_path: str,
        user_id: Optional[str],
    ) -> GeneratedContract:
        """Generate the final contract."""
        logger.info("Step 5: Generating contract")
        
        try:
            contract = self._contract_generator.generate(
                template_doc, alignment, ts_extraction
            )
            
            logger.info(
                f"Contract generated with {len(contract.modifications)} modifications"
            )
            
            # Export both versions
            try:
                revision_path, clean_path = self._contract_generator.export_both_versions(
                    contract, template_file_path
                )
                logger.info(f"Contract exported to: {revision_path}, {clean_path}")
            except Exception as e:
                logger.warning(f"Failed to export contract files: {e}")
            
            if self._audit_logger:
                self._audit_logger.log_contract_generated(
                    contract_id=contract.id,
                    ts_document_id=ts_extraction.document_id,
                    template_document_id=template_doc.id,
                    modification_count=len(contract.modifications),
                    user_id=user_id,
                )
                
                # Log individual modifications
                for mod in contract.modifications:
                    self._audit_logger.log_modification_applied(
                        document_id=template_doc.id,
                        modification_id=mod.id,
                        action_type=mod.action.value,
                        source_ts_paragraph_id=mod.source_ts_paragraph_id,
                        confidence=mod.confidence,
                        user_id=user_id,
                    )
            
            return contract
            
        except Exception as e:
            logger.error(f"Failed to generate contract: {e}")
            raise

    def _save_version_history(
        self,
        contract: GeneratedContract,
        ts_extraction: TSExtractionResult,
        template_analysis: TemplateAnalysisResult,
        alignment: AlignmentResult,
    ) -> None:
        """Save version history for rollback capability."""
        if not self._audit_logger:
            return
        
        try:
            # Save contract version
            contract_snapshot = {
                "id": contract.id,
                "template_document_id": contract.template_document_id,
                "ts_document_id": contract.ts_document_id,
                "modifications": [
                    {
                        "id": m.id,
                        "match_id": m.match_id,
                        "original_text": m.original_text,
                        "new_text": m.new_text,
                        "location_start": m.location_start,
                        "location_end": m.location_end,
                        "action": m.action.value,
                        "source_ts_paragraph_id": m.source_ts_paragraph_id,
                        "confidence": m.confidence,
                        "annotations": m.annotations,
                    }
                    for m in contract.modifications
                ],
                "generation_timestamp": contract.generation_timestamp,
            }
            self._audit_logger.save_version(
                "contract", contract.id, contract_snapshot
            )
            
            # Save alignment version
            alignment_snapshot = {
                "ts_document_id": alignment.ts_document_id,
                "template_document_id": alignment.template_document_id,
                "matches": [
                    {
                        "id": m.id,
                        "ts_term_id": m.ts_term_id,
                        "clause_id": m.clause_id,
                        "fillable_segment_id": m.fillable_segment_id,
                        "match_method": m.match_method.value,
                        "confidence": m.confidence,
                        "action": m.action.value,
                        "needs_review": m.needs_review,
                    }
                    for m in alignment.matches
                ],
                "unmatched_terms": alignment.unmatched_terms,
                "unmatched_clauses": alignment.unmatched_clauses,
                "alignment_timestamp": alignment.alignment_timestamp,
            }
            self._audit_logger.save_version(
                "alignment", f"{alignment.ts_document_id}_{alignment.template_document_id}",
                alignment_snapshot
            )
            
            logger.info("Version history saved")
            
        except Exception as e:
            logger.warning(f"Failed to save version history: {e}")

    def _update_stats(self, result: PipelineResult) -> None:
        """Update pipeline statistics."""
        self.stats.total_executions += 1
        
        if result.success:
            self.stats.successful_executions += 1
        else:
            self.stats.failed_executions += 1
        
        self.stats.total_processing_time += result.processing_time
        self.stats.average_processing_time = (
            self.stats.total_processing_time / self.stats.total_executions
        )

    def get_stats(self) -> PipelineStats:
        """Get pipeline execution statistics."""
        return self.stats
    
    def get_performance_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed performance statistics for all operations.
        
        Returns:
            Dictionary with performance metrics for each operation.
        """
        return self.performance_monitor.get_all_stats()
    
    def optimize_database(self) -> None:
        """
        Run database optimization tasks.
        
        This includes:
        - Ensuring all indexes exist
        - Running ANALYZE to update statistics
        - Optimizing vector search parameters
        """
        if not self._db_manager:
            logger.warning("Database manager not initialized, skipping optimization")
            return
        
        optimizer = DatabaseOptimizer(self._db_manager)
        
        try:
            logger.info("Running database optimization...")
            optimizer.ensure_indexes()
            optimizer.optimize_vector_search()
            optimizer.analyze_tables()
            logger.info("Database optimization completed")
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")

    def create_review_session(self, contract: GeneratedContract):
        """
        Create a review session for a generated contract.
        
        Args:
            contract: The generated contract to review.
            
        Returns:
            ReviewSession object.
        """
        review_manager = ReviewManager(db_manager=self._db_manager)
        return review_manager.create_session(contract)

    def close(self) -> None:
        """Close the pipeline and release resources."""
        if self._audit_logger:
            self._audit_logger.close()
        if self._db_manager:
            self._db_manager.close()
        logger.info("Processing pipeline closed")
