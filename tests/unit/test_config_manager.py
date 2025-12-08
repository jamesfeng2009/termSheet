"""Unit tests for the Configuration Manager."""

import json
import tempfile
from pathlib import Path

import pytest

from ts_contract_alignment.config import (
    ConfigurationManager,
    ConfigurationError,
    MatchingRule,
    RewritingTemplate,
    TerminologyMapping,
    ValidationResult,
)


class TestTerminologyMappings:
    """Tests for terminology mapping configuration (Requirement 9.1)."""

    def test_load_terminology_from_dict(self):
        """Test loading terminology mappings from a dictionary."""
        manager = ConfigurationManager()
        
        mappings = {
            "mappings": [
                {
                    "id": "term_001",
                    "standard_term": "Investment Amount",
                    "variations": ["投资金额", "investment sum", "capital amount"],
                    "language": "mixed",
                    "category": "investment_amount",
                    "description": "Total investment amount"
                }
            ]
        }
        
        result = manager.load_terminology_mappings(mappings)
        
        assert result.is_valid
        assert len(manager.configuration.terminology_mappings) == 1
        assert manager.configuration.terminology_mappings[0].standard_term == "Investment Amount"

    def test_load_terminology_from_list(self):
        """Test loading terminology mappings from a list."""
        manager = ConfigurationManager()
        
        mappings = [
            {
                "id": "term_001",
                "standard_term": "Valuation",
                "variations": ["估值", "company value"],
                "language": "mixed",
                "category": "valuation"
            },
            {
                "id": "term_002",
                "standard_term": "Board Seats",
                "variations": ["董事席位", "director seats"],
                "language": "mixed",
                "category": "board_seats"
            }
        ]
        
        result = manager.load_terminology_mappings(mappings)
        
        assert result.is_valid
        assert len(manager.configuration.terminology_mappings) == 2

    def test_terminology_validation_missing_fields(self):
        """Test validation fails for missing required fields."""
        manager = ConfigurationManager()
        
        mappings = [
            {
                "id": "term_001",
                "standard_term": "Test"
                # Missing: variations, language, category
            }
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_terminology_mappings(mappings)
        
        assert "Missing required field" in str(exc_info.value.validation_result.errors)

    def test_terminology_validation_duplicate_ids(self):
        """Test validation fails for duplicate IDs."""
        manager = ConfigurationManager()
        
        mappings = [
            {
                "id": "term_001",
                "standard_term": "Term A",
                "variations": ["a"],
                "language": "en",
                "category": "other"
            },
            {
                "id": "term_001",  # Duplicate ID
                "standard_term": "Term B",
                "variations": ["b"],
                "language": "en",
                "category": "other"
            }
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_terminology_mappings(mappings)
        
        assert "Duplicate terminology mapping IDs" in str(exc_info.value.validation_result.errors)

    def test_terminology_matches(self):
        """Test terminology matching functionality."""
        manager = ConfigurationManager()
        
        mappings = [
            {
                "id": "term_001",
                "standard_term": "Investment Amount",
                "variations": ["投资金额", "capital"],
                "language": "mixed",
                "category": "investment_amount"
            }
        ]
        
        manager.load_terminology_mappings(mappings)
        
        # Test matching
        matches = manager.find_terminology_matches("The investment amount is $10M")
        assert len(matches) == 1
        
        matches = manager.find_terminology_matches("投资金额为1000万美元")
        assert len(matches) == 1
        
        matches = manager.find_terminology_matches("No match here")
        assert len(matches) == 0

    def test_load_terminology_from_file(self):
        """Test loading terminology from a JSON file."""
        manager = ConfigurationManager()
        
        mappings = {
            "mappings": [
                {
                    "id": "term_001",
                    "standard_term": "Test Term",
                    "variations": ["variation1"],
                    "language": "en",
                    "category": "other"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(mappings, f)
            temp_path = f.name
        
        try:
            result = manager.load_terminology_mappings(temp_path)
            assert result.is_valid
            assert len(manager.configuration.terminology_mappings) == 1
        finally:
            Path(temp_path).unlink()



class TestMatchingRules:
    """Tests for matching rules configuration (Requirement 9.2)."""

    def test_load_matching_rules_from_dict(self):
        """Test loading matching rules from a dictionary."""
        manager = ConfigurationManager()
        
        rules = {
            "rules": [
                {
                    "id": "rule_001",
                    "name": "Investment Amount Match",
                    "priority": 1,
                    "source_pattern": r"investment\s+amount",
                    "target_pattern": r"投资金额",
                    "source_categories": ["investment_amount"],
                    "target_categories": ["investment_terms"],
                    "confidence_boost": 0.1
                }
            ]
        }
        
        result = manager.load_matching_rules(rules)
        
        assert result.is_valid
        assert len(manager.configuration.matching_rules) == 1
        assert manager.configuration.matching_rules[0].priority == 1

    def test_rules_sorted_by_priority(self):
        """Test that rules are sorted by priority after loading."""
        manager = ConfigurationManager()
        
        rules = [
            {
                "id": "rule_003",
                "name": "Low Priority",
                "priority": 10,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["other"],
                "target_categories": ["miscellaneous"]
            },
            {
                "id": "rule_001",
                "name": "High Priority",
                "priority": 1,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["investment_amount"],
                "target_categories": ["investment_terms"]
            },
            {
                "id": "rule_002",
                "name": "Medium Priority",
                "priority": 5,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["valuation"],
                "target_categories": ["investment_terms"]
            }
        ]
        
        manager.load_matching_rules(rules)
        
        sorted_rules = manager.get_rules_by_priority()
        assert sorted_rules[0].id == "rule_001"
        assert sorted_rules[1].id == "rule_002"
        assert sorted_rules[2].id == "rule_003"

    def test_rules_validation_invalid_regex(self):
        """Test validation fails for invalid regex patterns."""
        manager = ConfigurationManager()
        
        rules = [
            {
                "id": "rule_001",
                "name": "Bad Regex",
                "priority": 1,
                "source_pattern": "[invalid(regex",  # Invalid regex
                "target_pattern": ".*",
                "source_categories": ["other"],
                "target_categories": ["miscellaneous"]
            }
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_matching_rules(rules)
        
        assert "not a valid regex" in str(exc_info.value.validation_result.errors)

    def test_rules_validation_invalid_confidence_boost(self):
        """Test validation fails for out-of-range confidence boost."""
        manager = ConfigurationManager()
        
        rules = [
            {
                "id": "rule_001",
                "name": "Bad Boost",
                "priority": 1,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["other"],
                "target_categories": ["miscellaneous"],
                "confidence_boost": 2.0  # Out of range
            }
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_matching_rules(rules)
        
        assert "confidence_boost" in str(exc_info.value.validation_result.errors)

    def test_rules_priority_conflict_warning(self):
        """Test warning is generated for priority conflicts."""
        manager = ConfigurationManager()
        
        rules = [
            {
                "id": "rule_001",
                "name": "Rule A",
                "priority": 1,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["other"],
                "target_categories": ["miscellaneous"]
            },
            {
                "id": "rule_002",
                "name": "Rule B",
                "priority": 1,  # Same priority
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["other"],
                "target_categories": ["miscellaneous"]
            }
        ]
        
        result = manager.load_matching_rules(rules)
        
        assert result.is_valid
        assert any("same priority" in w for w in result.warnings)


class TestRewritingTemplates:
    """Tests for rewriting templates configuration (Requirement 9.3)."""

    def test_load_rewriting_templates_from_dict(self):
        """Test loading rewriting templates from a dictionary."""
        manager = ConfigurationManager()
        
        templates = {
            "templates": [
                {
                    "id": "template_001",
                    "name": "Investment Amount Standardization",
                    "source_pattern": r"(\d+)\s*万\s*美元",
                    "replacement_template": "USD {amount} million",
                    "language": "en",
                    "category": "investment_terms"
                }
            ]
        }
        
        result = manager.load_rewriting_templates(templates)
        
        assert result.is_valid
        assert len(manager.configuration.rewriting_templates) == 1

    def test_apply_rewriting_template(self):
        """Test applying a rewriting template to text."""
        manager = ConfigurationManager()
        
        templates = [
            {
                "id": "template_001",
                "name": "Amount Format",
                "source_pattern": r"(\d+)\s*million",
                "replacement_template": "{amount}M",
                "language": "en",
                "category": "investment_terms"
            }
        ]
        
        manager.load_rewriting_templates(templates)
        
        result = manager.apply_rewriting_template(
            "template_001",
            "The investment is 10 million dollars",
            {"amount": "10"}
        )
        
        assert result is not None
        assert "10M" in result

    def test_templates_validation_invalid_regex(self):
        """Test validation fails for invalid source pattern."""
        manager = ConfigurationManager()
        
        templates = [
            {
                "id": "template_001",
                "name": "Bad Pattern",
                "source_pattern": "[invalid(regex",
                "replacement_template": "replacement",
                "language": "en",
                "category": "other"
            }
        ]
        
        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_rewriting_templates(templates)
        
        assert "not a valid regex" in str(exc_info.value.validation_result.errors)

    def test_templates_by_category(self):
        """Test getting templates by category."""
        manager = ConfigurationManager()
        
        templates = [
            {
                "id": "template_001",
                "name": "Template A",
                "source_pattern": ".*",
                "replacement_template": "A",
                "language": "en",
                "category": "investment_terms"
            },
            {
                "id": "template_002",
                "name": "Template B",
                "source_pattern": ".*",
                "replacement_template": "B",
                "language": "en",
                "category": "governance"
            },
            {
                "id": "template_003",
                "name": "Template C",
                "source_pattern": ".*",
                "replacement_template": "C",
                "language": "en",
                "category": "investment_terms"
            }
        ]
        
        manager.load_rewriting_templates(templates)
        
        investment_templates = manager.get_templates_by_category("investment_terms")
        assert len(investment_templates) == 2
        
        governance_templates = manager.get_templates_by_category("governance")
        assert len(governance_templates) == 1


class TestConfigurationValidation:
    """Tests for configuration validation (Requirement 9.4)."""

    def test_validate_complete_configuration(self):
        """Test validating a complete configuration."""
        manager = ConfigurationManager()
        
        # Load all configuration types
        manager.load_terminology_mappings([
            {
                "id": "term_001",
                "standard_term": "Investment",
                "variations": ["投资"],
                "language": "mixed",
                "category": "investment_amount"
            }
        ])
        
        manager.load_matching_rules([
            {
                "id": "rule_001",
                "name": "Investment Rule",
                "priority": 1,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["investment_amount"],
                "target_categories": ["investment_terms"]
            }
        ])
        
        manager.load_rewriting_templates([
            {
                "id": "template_001",
                "name": "Investment Template",
                "source_pattern": ".*",
                "replacement_template": "replacement",
                "language": "en",
                "category": "investment_terms"
            }
        ])
        
        result = manager.validate_configuration()
        
        assert result.is_valid

    def test_validate_cross_reference_warning(self):
        """Test warning for missing cross-references."""
        manager = ConfigurationManager()
        
        # Load rules with categories not in terminology
        manager.load_matching_rules([
            {
                "id": "rule_001",
                "name": "Rule",
                "priority": 1,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["unknown_category"],
                "target_categories": ["investment_terms"]
            }
        ])
        
        result = manager.validate_configuration()
        
        # Should have warning about missing terminology
        assert any("without terminology mappings" in w for w in result.warnings)

    def test_validate_overlapping_terms_warning(self):
        """Test warning for overlapping terminology variations."""
        manager = ConfigurationManager()
        
        manager.load_terminology_mappings([
            {
                "id": "term_001",
                "standard_term": "Investment",
                "variations": ["capital", "funding"],
                "language": "en",
                "category": "investment_amount"
            },
            {
                "id": "term_002",
                "standard_term": "Capital",
                "variations": ["capital", "funds"],  # "capital" overlaps
                "language": "en",
                "category": "valuation"
            }
        ])
        
        result = manager.validate_configuration()
        
        assert any("appears in multiple mappings" in w for w in result.warnings)


class TestConfigurationPersistence:
    """Tests for configuration save/load from directory."""

    def test_save_and_load_from_directory(self):
        """Test saving and loading configuration from a directory."""
        manager = ConfigurationManager()
        
        # Set up configuration
        manager.load_terminology_mappings([
            {
                "id": "term_001",
                "standard_term": "Test",
                "variations": ["test_var"],
                "language": "en",
                "category": "other"
            }
        ])
        
        manager.load_matching_rules([
            {
                "id": "rule_001",
                "name": "Test Rule",
                "priority": 1,
                "source_pattern": ".*",
                "target_pattern": ".*",
                "source_categories": ["other"],
                "target_categories": ["miscellaneous"]
            }
        ])
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save
            manager.save_to_directory(temp_dir)
            
            # Verify files exist
            assert (Path(temp_dir) / "terminology.json").exists()
            assert (Path(temp_dir) / "rules.json").exists()
            
            # Load into new manager
            new_manager = ConfigurationManager()
            result = new_manager.load_from_directory(temp_dir)
            
            assert result.is_valid
            assert len(new_manager.configuration.terminology_mappings) == 1
            assert len(new_manager.configuration.matching_rules) == 1

    def test_to_dict_export(self):
        """Test exporting configuration to dictionary."""
        manager = ConfigurationManager()
        
        manager.load_terminology_mappings([
            {
                "id": "term_001",
                "standard_term": "Test",
                "variations": ["var"],
                "language": "en",
                "category": "other"
            }
        ])
        
        config_dict = manager.to_dict()
        
        assert "terminology_mappings" in config_dict
        assert "matching_rules" in config_dict
        assert "rewriting_templates" in config_dict
        assert len(config_dict["terminology_mappings"]) == 1

    def test_reset_configuration(self):
        """Test resetting configuration."""
        manager = ConfigurationManager()
        
        manager.load_terminology_mappings([
            {
                "id": "term_001",
                "standard_term": "Test",
                "variations": ["var"],
                "language": "en",
                "category": "other"
            }
        ])
        
        assert manager.is_loaded
        assert len(manager.configuration.terminology_mappings) == 1
        
        manager.reset()
        
        assert not manager.is_loaded
        assert len(manager.configuration.terminology_mappings) == 0
