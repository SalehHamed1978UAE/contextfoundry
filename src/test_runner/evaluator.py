"""
Fuzzy evaluator for answer matching.

Handles:
- Format differences ("30%" vs "30%+")
- Prose vs exact value ("Revenue increased by $40M" vs "$40 million")
- "I don't know" variations
- Number extraction and comparison
"""

import re
from typing import Tuple, Set, List, Optional


class FuzzyEvaluator:
    """
    Evaluate answers with semantic matching, not strict string matching.
    """
    
    def evaluate(self, expected: str, actual: str) -> Tuple[bool, str]:
        """
        Returns (passed, match_type)
        
        match_type is one of:
        - exact_match
        - uncertainty_match
        - number_match
        - entity_match
        - percentage_match
        - boolean_match
        - no_match
        """
        if not expected or not actual:
            return False, "empty_response"
        
        expected_lower = expected.lower().strip()
        actual_lower = actual.lower().strip()
        
        # Case 1: Exact match (expected appears in actual)
        if expected_lower in actual_lower:
            return True, "exact_match"
        
        # Case 2: "[NOT IN DOCUMENTS]" handling
        if expected_lower == "[not in documents]":
            uncertainty_phrases = [
                "not available",
                "not provided", 
                "does not provide",
                "does not specify",
                "no information",
                "not found in",
                "cannot find",
                "don't have information",
                "not in the documents",
                "not mentioned",
                "insufficient data",
                "no data",
                "unable to find",
                "could not find",
                "doesn't specify",
                "isn't specified",
                "not included",
                "not explicitly",
                "cannot determine",
                "not stated",
                "no specific",
                "insufficient",
            ]
            if any(phrase in actual_lower for phrase in uncertainty_phrases):
                return True, "uncertainty_match"
            return False, "should_say_unknown"
        
        # Case 3: Numeric extraction and comparison
        expected_numbers = self._extract_numbers(expected)
        actual_numbers = self._extract_numbers(actual)
        
        if expected_numbers:
            # Check if all expected numbers appear in actual
            if expected_numbers.issubset(actual_numbers):
                return True, "number_match"
            
            # Check if primary number matches (first/largest)
            expected_primary = self._get_primary_number(expected)
            actual_primary = self._get_primary_number(actual)
            if expected_primary and actual_primary:
                if self._numbers_match(expected_primary, actual_primary):
                    return True, "number_match"
        
        # Case 4: Percentage matching (30% vs 30%+)
        expected_pct = self._extract_percentage(expected)
        actual_pct = self._extract_percentage(actual)
        if expected_pct and actual_pct:
            # Strip + suffix for comparison
            if expected_pct.rstrip('+%') == actual_pct.rstrip('+%'):
                return True, "percentage_match"
        
        # Case 5: Key entity extraction
        expected_entities = self._extract_key_entities(expected)
        if expected_entities:
            matches = sum(1 for e in expected_entities if e.lower() in actual_lower)
            # If 70%+ of key entities present, consider it a match
            if matches >= len(expected_entities) * 0.7:
                return True, "entity_match"
        
        # Case 6: Boolean/Yes-No matching
        if self._is_boolean_match(expected_lower, actual_lower):
            return True, "boolean_match"
        
        return False, "no_match"
    
    def _extract_numbers(self, text: str) -> Set[str]:
        """Extract all numbers from text, normalized."""
        numbers = set()
        
        # Currency: $500,000 or $1.2M
        for match in re.findall(r'\$[\d,]+(?:\.\d+)?(?:[MmBbKk])?', text):
            normalized = self._normalize_number(match)
            if normalized:
                numbers.add(normalized)
        
        # Plain numbers with optional commas/decimals
        for match in re.findall(r'\b[\d,]+(?:\.\d+)?\b', text):
            normalized = self._normalize_number(match)
            if normalized:
                numbers.add(normalized)
        
        return numbers
    
    def _normalize_number(self, num_str: str) -> Optional[str]:
        """Normalize number string for comparison."""
        # Remove $ and commas
        normalized = num_str.replace('$', '').replace(',', '')
        
        if not normalized:
            return None
        
        # Handle M/B/K suffixes
        if normalized.endswith(('M', 'm')):
            try:
                value = float(normalized[:-1]) * 1_000_000
                return str(int(value))
            except ValueError:
                pass
        elif normalized.endswith(('B', 'b')):
            try:
                value = float(normalized[:-1]) * 1_000_000_000
                return str(int(value))
            except ValueError:
                pass
        elif normalized.endswith(('K', 'k')):
            try:
                value = float(normalized[:-1]) * 1_000
                return str(int(value))
            except ValueError:
                pass
        
        return normalized
    
    def _get_primary_number(self, text: str) -> Optional[str]:
        """Get the most significant number from text."""
        numbers = list(self._extract_numbers(text))
        if not numbers:
            return None
        # Return largest number (likely the main value)
        try:
            return max(numbers, key=lambda x: float(x) if x else 0)
        except ValueError:
            return numbers[0]
    
    def _numbers_match(self, a: str, b: str) -> bool:
        """Check if two number strings represent the same value."""
        try:
            return abs(float(a) - float(b)) < 0.01
        except ValueError:
            return a == b
    
    def _extract_percentage(self, text: str) -> Optional[str]:
        """Extract percentage value."""
        match = re.search(r'(\d+(?:\.\d+)?%\+?)', text)
        return match.group(1) if match else None
    
    def _extract_key_entities(self, text: str) -> List[str]:
        """Extract likely entity names."""
        entities = []
        
        # Quoted strings
        entities.extend(re.findall(r'"([^"]+)"', text))
        
        # Parenthetical names
        entities.extend(re.findall(r'\(([A-Z][^)]+)\)', text))
        
        # Capitalized multi-word names (e.g., "Boston Office")
        entities.extend(re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text))
        
        # Single capitalized words that aren't common
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'which'}
        for word in re.findall(r'\b[A-Z][a-z]+\b', text):
            if word.lower() not in common_words:
                entities.append(word)
        
        return entities
    
    def _is_boolean_match(self, expected: str, actual: str) -> bool:
        """Check if both express same yes/no meaning."""
        yes_words = {'yes', 'true', 'correct', 'affirmative', 'confirmed'}
        no_words = {'no', 'false', 'incorrect', 'negative', 'denied'}
        
        expected_yes = any(w in expected for w in yes_words)
        expected_no = any(w in expected for w in no_words)
        actual_yes = any(w in actual for w in yes_words)
        actual_no = any(w in actual for w in no_words)
        
        if expected_yes and actual_yes:
            return True
        if expected_no and actual_no:
            return True
        
        return False
