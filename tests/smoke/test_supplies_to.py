"""
Smoke tests for SUPPLIES_TO relationship extraction.

Tests the supplier pattern matching in post_processor.py.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from context_foundry.extraction.post_processor import (
    extract_supplier_relationships,
    SUPPLIER_PATTERNS,
    SUPPLIER_BLOCKLIST
)


class TestSupplierPatterns:
    """Test the supplier relationship pattern matching."""
    
    def test_nel_hydrogen_supplies_electrolyzers(self):
        """Nel Hydrogen supplies electrolyzers should be detected."""
        text = "Nel Hydrogen supplies electrolyzers for the green hydrogen project."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        supplier_names = [r['supplier'].lower() for r in results]
        assert any('nel' in name for name in supplier_names)
    
    def test_shell_provides_hydrogen_offtake(self):
        """Shell provides hydrogen offtake should be detected."""
        text = "Shell provides hydrogen offtake for the facility."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        supplier_names = [r['supplier'].lower() for r in results]
        assert any('shell' in name for name in supplier_names)
    
    def test_honeywell_delivers_flight_computers(self):
        """Honeywell delivers flight computers should be detected."""
        text = "Honeywell delivers flight computers to the aerospace division."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        supplier_names = [r['supplier'].lower() for r in results]
        assert any('honeywell' in name for name in supplier_names)
    
    def test_passive_voice_raytheon_sar_radar(self):
        """Passive voice: SAR radar supplied by Raytheon should be detected."""
        text = "SAR radar systems supplied by Raytheon Technologies."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        supplier_names = [r['supplier'].lower() for r in results]
        assert any('raytheon' in name for name in supplier_names)
    
    def test_no_false_positives_non_supplier_text(self):
        """Non-supplier text should not produce false positives."""
        text = "The weather is nice today. John went to the store."
        results = extract_supplier_relationships(text)
        
        assert len(results) == 0
    
    def test_passive_voice_detection(self):
        """Various passive voice patterns should be detected."""
        text = "Advanced sensors provided by Lockheed Martin."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        supplier_names = [r['supplier'].lower() for r in results]
        assert any('lockheed' in name for name in supplier_names)
    
    def test_supplier_blocklist_filters_common_words(self):
        """Common words like 'the', 'a' should be filtered out."""
        assert 'the' in SUPPLIER_BLOCKLIST
        assert 'a' in SUPPLIER_BLOCKLIST
        assert 'an' in SUPPLIER_BLOCKLIST
        assert 'their' in SUPPLIER_BLOCKLIST
    
    def test_vendor_pattern(self):
        """Vendor/supplier role pattern should be detected."""
        text = "Acme Corp as the primary supplier of components."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        supplier_names = [r['supplier'].lower() for r in results]
        assert any('acme' in name for name in supplier_names)
    
    def test_contracted_pattern(self):
        """Contracted to supply pattern should be detected."""
        text = "Boeing contracted to supply aircraft parts."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        supplier_names = [r['supplier'].lower() for r in results]
        assert any('boeing' in name for name in supplier_names)
    
    def test_result_structure(self):
        """Results should have correct structure."""
        text = "Nel Hydrogen supplies electrolyzers."
        results = extract_supplier_relationships(text)
        
        assert len(results) >= 1
        result = results[0]
        
        assert 'supplier' in result
        assert 'product' in result
        assert 'relationship_type' in result
        assert 'confidence' in result
        assert result['relationship_type'] == 'SUPPLIES_TO'
        assert 0 <= result['confidence'] <= 1


class TestSupplierPatternsExist:
    """Verify supplier patterns are properly defined."""
    
    def test_patterns_exist(self):
        """SUPPLIER_PATTERNS should exist and have entries."""
        assert SUPPLIER_PATTERNS is not None
        assert len(SUPPLIER_PATTERNS) >= 5
    
    def test_pattern_structure(self):
        """Each pattern should have (regex, type, confidence) structure."""
        for pattern, rel_type, confidence in SUPPLIER_PATTERNS:
            assert isinstance(pattern, str)
            assert rel_type == 'SUPPLIES_TO'
            assert 0 < confidence <= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
