"""Configuration Manager implementation for the TS Contract Alignment System.

This module provides functionality to load, validate, and manage configuration
for terminology mappings, matching rules, and rewriting templates.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .models import (
    ConfigurationError,
    ConfigurationType,
    MatchingRule,
    RewritingTemplate,
    SystemConfiguration,
    TerminologyMapping,
    ValidationResult,
)


class ConfigurationManager:
    """
    Manager for system configuration.
    
    Handles loading, validation, and access to terminology mappings,
    matching rules, and rewriting templates.
    """

    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Optional directory path for configuration files.
        """
        self._config_dir = Path(config_dir) if config_dir else None
        self._configuration = SystemConfiguration()
        self._is_loaded = False

    @property
    def configuration(self) -> SystemConfiguration:
        """Get the current system configuration."""
        return self._configuration

    @property
    def is_loaded(self) -> bool:
        """Check if configuration has been loaded."""
        return self._is_loaded

    # =========================================================================
    # Terminology Mapping Methods (Requirement 9.1)
    # =========================================================================

    def load_terminology_mappings(
        self, 
        source: Union[str, Path, Dict[str, Any], List[Dict[str, Any]]]
    ) -> ValidationResult:
        """
        Load and validate terminology mapping dictionaries.
        
        Supports loading from:
        - JSON file path
        - Dictionary with mappings
        - List of mapping dictionaries
        
        Args:
            source: File path, dictionary, or list of dictionaries.
            
        Returns:
            ValidationResult indicating success or failure with details.
            
        Raises:
            ConfigurationError: If validation fails and configuration cannot be applied.
        """
        # Parse source to get raw data
        raw_data = self._parse_source(source)
        
        # Handle both single dict and list formats
        if isinstance(raw_data, dict):
            if "mappings" in raw_data:
                mappings_data = raw_data["mappings"]
            else:
                mappings_data = [raw_data]
        else:
            mappings_data = raw_data
        
        # Validate and convert to TerminologyMapping objects
        result = ValidationResult(is_valid=True)
        mappings: List[TerminologyMapping] = []
        
        for i, mapping_dict in enumerate(mappings_data):
            mapping_result, mapping = self._validate_terminology_mapping(
                mapping_dict, index=i
            )
            result = result.merge(mapping_result)
            if mapping:
                mappings.append(mapping)
        
        # Check for duplicate IDs
        ids = [m.id for m in mappings]
        duplicates = [id for id in ids if ids.count(id) > 1]
        if duplicates:
            result.add_error(
                f"Duplicate terminology mapping IDs found: {set(duplicates)}"
            )
        
        if not result.is_valid:
            raise ConfigurationError(
                "Terminology mapping validation failed",
                validation_result=result
            )
        
        # Apply valid mappings
        self._configuration.terminology_mappings = mappings
        self._is_loaded = True
        
        return result

    def _validate_terminology_mapping(
        self, 
        data: Dict[str, Any], 
        index: int = 0
    ) -> tuple[ValidationResult, Optional[TerminologyMapping]]:
        """Validate a single terminology mapping dictionary."""
        result = ValidationResult(is_valid=True)
        prefix = f"Terminology mapping [{index}]"
        
        # Required fields
        required_fields = ["id", "standard_term", "variations", "language", "category"]
        for field in required_fields:
            if field not in data:
                result.add_error(f"{prefix}: Missing required field '{field}'")
        
        if not result.is_valid:
            return result, None
        
        # Validate field types
        if not isinstance(data["id"], str) or not data["id"].strip():
            result.add_error(f"{prefix}: 'id' must be a non-empty string")
        
        if not isinstance(data["standard_term"], str) or not data["standard_term"].strip():
            result.add_error(f"{prefix}: 'standard_term' must be a non-empty string")
        
        if not isinstance(data["variations"], list):
            result.add_error(f"{prefix}: 'variations' must be a list")
        elif not all(isinstance(v, str) for v in data["variations"]):
            result.add_error(f"{prefix}: All variations must be strings")
        
        valid_languages = ["zh", "en", "mixed"]
        if data["language"] not in valid_languages:
            result.add_error(
                f"{prefix}: 'language' must be one of {valid_languages}"
            )
        
        if not isinstance(data["category"], str) or not data["category"].strip():
            result.add_error(f"{prefix}: 'category' must be a non-empty string")
        
        if not result.is_valid:
            return result, None
        
        # Create mapping object
        mapping = TerminologyMapping(
            id=data["id"].strip(),
            standard_term=data["standard_term"].strip(),
            variations=[v.strip() for v in data["variations"] if v.strip()],
            language=data["language"],
            category=data["category"].strip(),
            description=data.get("description"),
            metadata=data.get("metadata", {})
        )
        
        return result, mapping

    def get_terminology_mapping(self, term_id: str) -> Optional[TerminologyMapping]:
        """Get a terminology mapping by ID."""
        for mapping in self._configuration.terminology_mappings:
            if mapping.id == term_id:
                return mapping
        return None

    def find_terminology_matches(self, text: str) -> List[TerminologyMapping]:
        """Find all terminology mappings that match the given text."""
        return [m for m in self._configuration.terminology_mappings if m.matches(text)]


    # =========================================================================
    # Matching Rules Methods (Requirement 9.2)
    # =========================================================================

    def load_matching_rules(
        self, 
        source: Union[str, Path, Dict[str, Any], List[Dict[str, Any]]]
    ) -> ValidationResult:
        """
        Load and validate custom matching rules.
        
        Rules are automatically sorted by priority after loading.
        
        Args:
            source: File path, dictionary, or list of dictionaries.
            
        Returns:
            ValidationResult indicating success or failure with details.
            
        Raises:
            ConfigurationError: If validation fails and configuration cannot be applied.
        """
        raw_data = self._parse_source(source)
        
        # Handle both single dict and list formats
        if isinstance(raw_data, dict):
            if "rules" in raw_data:
                rules_data = raw_data["rules"]
            else:
                rules_data = [raw_data]
        else:
            rules_data = raw_data
        
        result = ValidationResult(is_valid=True)
        rules: List[MatchingRule] = []
        
        for i, rule_dict in enumerate(rules_data):
            rule_result, rule = self._validate_matching_rule(rule_dict, index=i)
            result = result.merge(rule_result)
            if rule:
                rules.append(rule)
        
        # Check for duplicate IDs
        ids = [r.id for r in rules]
        duplicates = [id for id in ids if ids.count(id) > 1]
        if duplicates:
            result.add_error(f"Duplicate matching rule IDs found: {set(duplicates)}")
        
        # Check for priority conflicts (warning only)
        priorities = [r.priority for r in rules]
        if len(priorities) != len(set(priorities)):
            result.add_warning(
                "Multiple rules share the same priority. "
                "Consider using unique priorities for deterministic ordering."
            )
        
        if not result.is_valid:
            raise ConfigurationError(
                "Matching rules validation failed",
                validation_result=result
            )
        
        # Sort by priority and apply
        rules.sort(key=lambda r: r.priority)
        self._configuration.matching_rules = rules
        self._is_loaded = True
        
        return result

    def _validate_matching_rule(
        self, 
        data: Dict[str, Any], 
        index: int = 0
    ) -> tuple[ValidationResult, Optional[MatchingRule]]:
        """Validate a single matching rule dictionary."""
        result = ValidationResult(is_valid=True)
        prefix = f"Matching rule [{index}]"
        
        # Required fields
        required_fields = [
            "id", "name", "priority", "source_pattern", 
            "target_pattern", "source_categories", "target_categories"
        ]
        for field in required_fields:
            if field not in data:
                result.add_error(f"{prefix}: Missing required field '{field}'")
        
        if not result.is_valid:
            return result, None
        
        # Validate field types
        if not isinstance(data["id"], str) or not data["id"].strip():
            result.add_error(f"{prefix}: 'id' must be a non-empty string")
        
        if not isinstance(data["name"], str) or not data["name"].strip():
            result.add_error(f"{prefix}: 'name' must be a non-empty string")
        
        if not isinstance(data["priority"], int):
            result.add_error(f"{prefix}: 'priority' must be an integer")
        elif data["priority"] < 0:
            result.add_error(f"{prefix}: 'priority' must be non-negative")
        
        # Validate patterns are valid regex
        for pattern_field in ["source_pattern", "target_pattern"]:
            pattern = data.get(pattern_field, "")
            if not isinstance(pattern, str):
                result.add_error(f"{prefix}: '{pattern_field}' must be a string")
            elif pattern:
                try:
                    re.compile(pattern)
                except re.error as e:
                    result.add_error(
                        f"{prefix}: '{pattern_field}' is not a valid regex: {e}"
                    )
        
        # Validate category lists
        for cat_field in ["source_categories", "target_categories"]:
            cats = data.get(cat_field, [])
            if not isinstance(cats, list):
                result.add_error(f"{prefix}: '{cat_field}' must be a list")
            elif not all(isinstance(c, str) for c in cats):
                result.add_error(f"{prefix}: All items in '{cat_field}' must be strings")
        
        # Validate confidence_boost if present
        if "confidence_boost" in data:
            boost = data["confidence_boost"]
            if not isinstance(boost, (int, float)):
                result.add_error(f"{prefix}: 'confidence_boost' must be a number")
            elif not -1.0 <= boost <= 1.0:
                result.add_error(
                    f"{prefix}: 'confidence_boost' must be between -1.0 and 1.0"
                )
        
        if not result.is_valid:
            return result, None
        
        # Create rule object
        rule = MatchingRule(
            id=data["id"].strip(),
            name=data["name"].strip(),
            priority=data["priority"],
            source_pattern=data["source_pattern"],
            target_pattern=data["target_pattern"],
            source_categories=[c.strip() for c in data["source_categories"]],
            target_categories=[c.strip() for c in data["target_categories"]],
            confidence_boost=data.get("confidence_boost", 0.0),
            enabled=data.get("enabled", True),
            description=data.get("description"),
            metadata=data.get("metadata", {})
        )
        
        return result, rule

    def get_matching_rule(self, rule_id: str) -> Optional[MatchingRule]:
        """Get a matching rule by ID."""
        for rule in self._configuration.matching_rules:
            if rule.id == rule_id:
                return rule
        return None

    def get_rules_by_priority(self) -> List[MatchingRule]:
        """Get all enabled matching rules sorted by priority."""
        return self._configuration.get_rules_by_priority()


    # =========================================================================
    # Rewriting Templates Methods (Requirement 9.3)
    # =========================================================================

    def load_rewriting_templates(
        self, 
        source: Union[str, Path, Dict[str, Any], List[Dict[str, Any]]]
    ) -> ValidationResult:
        """
        Load and validate clause rewriting templates.
        
        Templates support language standardization and clause reformatting.
        
        Args:
            source: File path, dictionary, or list of dictionaries.
            
        Returns:
            ValidationResult indicating success or failure with details.
            
        Raises:
            ConfigurationError: If validation fails and configuration cannot be applied.
        """
        raw_data = self._parse_source(source)
        
        # Handle both single dict and list formats
        if isinstance(raw_data, dict):
            if "templates" in raw_data:
                templates_data = raw_data["templates"]
            else:
                templates_data = [raw_data]
        else:
            templates_data = raw_data
        
        result = ValidationResult(is_valid=True)
        templates: List[RewritingTemplate] = []
        
        for i, template_dict in enumerate(templates_data):
            template_result, template = self._validate_rewriting_template(
                template_dict, index=i
            )
            result = result.merge(template_result)
            if template:
                templates.append(template)
        
        # Check for duplicate IDs
        ids = [t.id for t in templates]
        duplicates = [id for id in ids if ids.count(id) > 1]
        if duplicates:
            result.add_error(f"Duplicate rewriting template IDs found: {set(duplicates)}")
        
        if not result.is_valid:
            raise ConfigurationError(
                "Rewriting templates validation failed",
                validation_result=result
            )
        
        self._configuration.rewriting_templates = templates
        self._is_loaded = True
        
        return result

    def _validate_rewriting_template(
        self, 
        data: Dict[str, Any], 
        index: int = 0
    ) -> tuple[ValidationResult, Optional[RewritingTemplate]]:
        """Validate a single rewriting template dictionary."""
        result = ValidationResult(is_valid=True)
        prefix = f"Rewriting template [{index}]"
        
        # Required fields
        required_fields = [
            "id", "name", "source_pattern", "replacement_template", 
            "language", "category"
        ]
        for field in required_fields:
            if field not in data:
                result.add_error(f"{prefix}: Missing required field '{field}'")
        
        if not result.is_valid:
            return result, None
        
        # Validate field types
        if not isinstance(data["id"], str) or not data["id"].strip():
            result.add_error(f"{prefix}: 'id' must be a non-empty string")
        
        if not isinstance(data["name"], str) or not data["name"].strip():
            result.add_error(f"{prefix}: 'name' must be a non-empty string")
        
        # Validate source_pattern is valid regex
        pattern = data.get("source_pattern", "")
        if not isinstance(pattern, str):
            result.add_error(f"{prefix}: 'source_pattern' must be a string")
        elif pattern:
            try:
                re.compile(pattern)
            except re.error as e:
                result.add_error(
                    f"{prefix}: 'source_pattern' is not a valid regex: {e}"
                )
        
        if not isinstance(data["replacement_template"], str):
            result.add_error(f"{prefix}: 'replacement_template' must be a string")
        
        valid_languages = ["zh", "en", "mixed"]
        if data["language"] not in valid_languages:
            result.add_error(
                f"{prefix}: 'language' must be one of {valid_languages}"
            )
        
        if not isinstance(data["category"], str) or not data["category"].strip():
            result.add_error(f"{prefix}: 'category' must be a non-empty string")
        
        if not result.is_valid:
            return result, None
        
        # Create template object
        template = RewritingTemplate(
            id=data["id"].strip(),
            name=data["name"].strip(),
            source_pattern=data["source_pattern"],
            replacement_template=data["replacement_template"],
            language=data["language"],
            category=data["category"].strip(),
            preserve_values=data.get("preserve_values", True),
            enabled=data.get("enabled", True),
            description=data.get("description"),
            metadata=data.get("metadata", {})
        )
        
        return result, template

    def get_rewriting_template(self, template_id: str) -> Optional[RewritingTemplate]:
        """Get a rewriting template by ID."""
        for template in self._configuration.rewriting_templates:
            if template.id == template_id:
                return template
        return None

    def get_templates_by_category(self, category: str) -> List[RewritingTemplate]:
        """Get all enabled rewriting templates for a category."""
        return self._configuration.get_templates_by_category(category)

    def apply_rewriting_template(
        self, 
        template_id: str, 
        text: str, 
        values: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Apply a rewriting template to text.
        
        Args:
            template_id: ID of the template to apply.
            text: Source text to rewrite.
            values: Optional dictionary of placeholder values.
            
        Returns:
            Rewritten text, or None if template not found or pattern doesn't match.
        """
        template = self.get_rewriting_template(template_id)
        if not template or not template.enabled:
            return None
        
        # Check if pattern matches
        match = re.search(template.source_pattern, text)
        if not match:
            return None
        
        # Build replacement with values
        replacement = template.replacement_template
        if values:
            for key, value in values.items():
                replacement = replacement.replace(f"{{{key}}}", value)
        
        # Apply replacement
        return re.sub(template.source_pattern, replacement, text)


    # =========================================================================
    # Configuration Validation Methods (Requirement 9.4)
    # =========================================================================

    def validate_configuration(
        self, 
        config: Optional[SystemConfiguration] = None
    ) -> ValidationResult:
        """
        Validate the complete system configuration.
        
        Checks for:
        - Internal consistency of each configuration type
        - Cross-references between configuration types
        - Potential conflicts
        
        Args:
            config: Configuration to validate. Uses current config if None.
            
        Returns:
            ValidationResult with all errors and warnings.
        """
        config = config or self._configuration
        result = ValidationResult(is_valid=True)
        
        # Validate terminology mappings
        term_result = self._validate_terminology_consistency(config)
        result = result.merge(term_result)
        
        # Validate matching rules
        rules_result = self._validate_rules_consistency(config)
        result = result.merge(rules_result)
        
        # Validate rewriting templates
        templates_result = self._validate_templates_consistency(config)
        result = result.merge(templates_result)
        
        # Cross-validate configurations
        cross_result = self._validate_cross_references(config)
        result = result.merge(cross_result)
        
        return result

    def _validate_terminology_consistency(
        self, 
        config: SystemConfiguration
    ) -> ValidationResult:
        """Validate terminology mappings for internal consistency."""
        result = ValidationResult(is_valid=True)
        
        # Check for overlapping variations across different mappings
        all_terms: Dict[str, str] = {}  # term -> mapping_id
        
        for mapping in config.terminology_mappings:
            for term in mapping.get_all_terms():
                term_lower = term.lower()
                if term_lower in all_terms:
                    result.add_warning(
                        f"Term '{term}' appears in multiple mappings: "
                        f"'{mapping.id}' and '{all_terms[term_lower]}'"
                    )
                else:
                    all_terms[term_lower] = mapping.id
        
        return result

    def _validate_rules_consistency(
        self, 
        config: SystemConfiguration
    ) -> ValidationResult:
        """Validate matching rules for internal consistency."""
        result = ValidationResult(is_valid=True)
        
        # Check for conflicting rules (same patterns, different targets)
        pattern_map: Dict[str, List[str]] = {}  # source_pattern -> [rule_ids]
        
        for rule in config.matching_rules:
            if rule.source_pattern in pattern_map:
                pattern_map[rule.source_pattern].append(rule.id)
            else:
                pattern_map[rule.source_pattern] = [rule.id]
        
        for pattern, rule_ids in pattern_map.items():
            if len(rule_ids) > 1:
                result.add_warning(
                    f"Multiple rules share source pattern '{pattern}': {rule_ids}. "
                    f"Priority ordering will determine which rule applies first."
                )
        
        return result

    def _validate_templates_consistency(
        self, 
        config: SystemConfiguration
    ) -> ValidationResult:
        """Validate rewriting templates for internal consistency."""
        result = ValidationResult(is_valid=True)
        
        # Check for conflicting templates (same pattern, same category)
        pattern_category_map: Dict[tuple, List[str]] = {}
        
        for template in config.rewriting_templates:
            key = (template.source_pattern, template.category)
            if key in pattern_category_map:
                pattern_category_map[key].append(template.id)
            else:
                pattern_category_map[key] = [template.id]
        
        for (pattern, category), template_ids in pattern_category_map.items():
            if len(template_ids) > 1:
                result.add_warning(
                    f"Multiple templates share pattern '{pattern}' for category "
                    f"'{category}': {template_ids}. Only the first will be applied."
                )
        
        return result

    def _validate_cross_references(
        self, 
        config: SystemConfiguration
    ) -> ValidationResult:
        """Validate cross-references between configuration types."""
        result = ValidationResult(is_valid=True)
        
        # Collect all categories used in terminology
        term_categories = {m.category for m in config.terminology_mappings}
        
        # Collect all categories used in rules
        rule_source_categories = set()
        rule_target_categories = set()
        for rule in config.matching_rules:
            rule_source_categories.update(rule.source_categories)
            rule_target_categories.update(rule.target_categories)
        
        # Collect all categories used in templates
        template_categories = {t.category for t in config.rewriting_templates}
        
        # Check if rule categories have corresponding terminology
        all_rule_categories = rule_source_categories | rule_target_categories
        missing_term_categories = all_rule_categories - term_categories
        if missing_term_categories:
            result.add_warning(
                f"Matching rules reference categories without terminology mappings: "
                f"{missing_term_categories}"
            )
        
        return result

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _parse_source(
        self, 
        source: Union[str, Path, Dict[str, Any], List[Dict[str, Any]]]
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Parse configuration source to raw data."""
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise ConfigurationError(f"Configuration file not found: {path}")
            
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return source

    def load_from_directory(self, config_dir: Union[str, Path]) -> ValidationResult:
        """
        Load all configuration files from a directory.
        
        Expects files named:
        - terminology.json
        - rules.json
        - templates.json
        
        Args:
            config_dir: Directory containing configuration files.
            
        Returns:
            Combined ValidationResult for all loaded configurations.
        """
        config_dir = Path(config_dir)
        result = ValidationResult(is_valid=True)
        
        # Load terminology mappings
        term_file = config_dir / "terminology.json"
        if term_file.exists():
            try:
                term_result = self.load_terminology_mappings(term_file)
                result = result.merge(term_result)
            except ConfigurationError as e:
                result.add_error(f"Terminology loading failed: {e.message}")
                if e.validation_result:
                    result = result.merge(e.validation_result)
        
        # Load matching rules
        rules_file = config_dir / "rules.json"
        if rules_file.exists():
            try:
                rules_result = self.load_matching_rules(rules_file)
                result = result.merge(rules_result)
            except ConfigurationError as e:
                result.add_error(f"Rules loading failed: {e.message}")
                if e.validation_result:
                    result = result.merge(e.validation_result)
        
        # Load rewriting templates
        templates_file = config_dir / "templates.json"
        if templates_file.exists():
            try:
                templates_result = self.load_rewriting_templates(templates_file)
                result = result.merge(templates_result)
            except ConfigurationError as e:
                result.add_error(f"Templates loading failed: {e.message}")
                if e.validation_result:
                    result = result.merge(e.validation_result)
        
        self._config_dir = config_dir
        return result

    def save_to_directory(
        self, 
        config_dir: Optional[Union[str, Path]] = None
    ) -> None:
        """
        Save current configuration to a directory.
        
        Args:
            config_dir: Directory to save to. Uses current config_dir if None.
        """
        config_dir = Path(config_dir) if config_dir else self._config_dir
        if not config_dir:
            raise ConfigurationError("No configuration directory specified")
        
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Save terminology mappings
        if self._configuration.terminology_mappings:
            term_data = {
                "mappings": [
                    {
                        "id": m.id,
                        "standard_term": m.standard_term,
                        "variations": m.variations,
                        "language": m.language,
                        "category": m.category,
                        "description": m.description,
                        "metadata": m.metadata,
                    }
                    for m in self._configuration.terminology_mappings
                ]
            }
            with open(config_dir / "terminology.json", "w", encoding="utf-8") as f:
                json.dump(term_data, f, indent=2, ensure_ascii=False)
        
        # Save matching rules
        if self._configuration.matching_rules:
            rules_data = {
                "rules": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "priority": r.priority,
                        "source_pattern": r.source_pattern,
                        "target_pattern": r.target_pattern,
                        "source_categories": r.source_categories,
                        "target_categories": r.target_categories,
                        "confidence_boost": r.confidence_boost,
                        "enabled": r.enabled,
                        "description": r.description,
                        "metadata": r.metadata,
                    }
                    for r in self._configuration.matching_rules
                ]
            }
            with open(config_dir / "rules.json", "w", encoding="utf-8") as f:
                json.dump(rules_data, f, indent=2, ensure_ascii=False)
        
        # Save rewriting templates
        if self._configuration.rewriting_templates:
            templates_data = {
                "templates": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "source_pattern": t.source_pattern,
                        "replacement_template": t.replacement_template,
                        "language": t.language,
                        "category": t.category,
                        "preserve_values": t.preserve_values,
                        "enabled": t.enabled,
                        "description": t.description,
                        "metadata": t.metadata,
                    }
                    for t in self._configuration.rewriting_templates
                ]
            }
            with open(config_dir / "templates.json", "w", encoding="utf-8") as f:
                json.dump(templates_data, f, indent=2, ensure_ascii=False)

    def reset(self) -> None:
        """Reset configuration to empty state."""
        self._configuration = SystemConfiguration()
        self._is_loaded = False

    def to_dict(self) -> Dict[str, Any]:
        """Export current configuration as a dictionary."""
        return {
            "version": self._configuration.version,
            "terminology_mappings": [
                {
                    "id": m.id,
                    "standard_term": m.standard_term,
                    "variations": m.variations,
                    "language": m.language,
                    "category": m.category,
                    "description": m.description,
                    "metadata": m.metadata,
                }
                for m in self._configuration.terminology_mappings
            ],
            "matching_rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "priority": r.priority,
                    "source_pattern": r.source_pattern,
                    "target_pattern": r.target_pattern,
                    "source_categories": r.source_categories,
                    "target_categories": r.target_categories,
                    "confidence_boost": r.confidence_boost,
                    "enabled": r.enabled,
                    "description": r.description,
                    "metadata": r.metadata,
                }
                for r in self._configuration.matching_rules
            ],
            "rewriting_templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "source_pattern": t.source_pattern,
                    "replacement_template": t.replacement_template,
                    "language": t.language,
                    "category": t.category,
                    "preserve_values": t.preserve_values,
                    "enabled": t.enabled,
                    "description": t.description,
                    "metadata": t.metadata,
                }
                for t in self._configuration.rewriting_templates
            ],
            "metadata": self._configuration.metadata,
        }
