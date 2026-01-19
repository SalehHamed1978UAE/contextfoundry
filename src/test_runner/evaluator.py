import re
from typing import Tuple

class FuzzyEvaluator:
    """
    Evaluate answers with semantic matching, not strict string matching.
    """
    
    def evaluate(self, expected: str, actual: str) -> Tuple[bool, str]:
        """Returns (passed, match_type)"""
        if not actual:
            return False, "no_answer"
        
        expected_lower = expected.lower().strip()
        actual_lower = actual.lower().strip()
        
        if expected_lower in actual_lower:
            return True, "exact_match"
        
        if expected_lower == "[not in documents]":
            uncertainty_phrases = [
                "not available", "not provided", "does not provide",
                "does not specify", "no information", "not found in",
                "cannot find", "don't have information", "not in the documents",
                "not mentioned", "insufficient data", "no data",
                "unable to find", "could not find", "doesn't specify",
                "isn't specified", "not included", "not explicitly"
            ]
            if any(phrase in actual_lower for phrase in uncertainty_phrases):
                return True, "uncertainty_match"
            return False, "should_say_unknown"
        
        expected_numbers = self._extract_numbers(expected)
        actual_numbers = self._extract_numbers(actual)
        
        if expected_numbers:
            if expected_numbers.issubset(actual_numbers):
                return True, "number_match"
            
            expected_primary = self._get_primary_number(expected)
            actual_primary = self._get_primary_number(actual)
            if expected_primary and actual_primary:
                if self._numbers_match(expected_primary, actual_primary):
                    return True, "number_match"
        
        expected_pct = self._extract_percentage(expected)
        actual_pct = self._extract_percentage(actual)
        if expected_pct and actual_pct:
            if expected_pct.rstrip('+%') == actual_pct.rstrip('+%'):
                return True, "percentage_match"
        
        expected_entities = self._extract_key_entities(expected)
        if expected_entities:
            matches = sum(1 for e in expected_entities if e.lower() in actual_lower)
            if matches >= len(expected_entities) * 0.7:
                return True, "entity_match"
        
        if self._is_boolean_match(expected_lower, actual_lower):
            return True, "boolean_match"
        
        return False, "no_match"
    
    def _extract_numbers(self, text: str) -> set:
        numbers = set()
        for match in re.findall(r'\$[\d,]+(?:\.\d+)?(?:[MmBbKk])?', text):
            numbers.add(self._normalize_number(match))
        for match in re.findall(r'\b[\d,]+(?:\.\d+)?\b', text):
            normalized = self._normalize_number(match)
            if normalized:
                numbers.add(normalized)
        return numbers
    
    def _normalize_number(self, num_str: str) -> str:
        normalized = num_str.replace('$', '').replace(',', '')
        if normalized.endswith(('M', 'm')):
            try:
                value = float(normalized[:-1]) * 1_000_000
                return str(int(value))
            except:
                pass
        elif normalized.endswith(('B', 'b')):
            try:
                value = float(normalized[:-1]) * 1_000_000_000
                return str(int(value))
            except:
                pass
        elif normalized.endswith(('K', 'k')):
            try:
                value = float(normalized[:-1]) * 1_000
                return str(int(value))
            except:
                pass
        return normalized
    
    def _get_primary_number(self, text: str) -> str:
        numbers = list(self._extract_numbers(text))
        if not numbers:
            return None
        try:
            return max(numbers, key=lambda x: float(x) if x else 0)
        except:
            return numbers[0]
    
    def _numbers_match(self, a: str, b: str) -> bool:
        try:
            return abs(float(a) - float(b)) < 0.01
        except:
            return a == b
    
    def _extract_percentage(self, text: str) -> str:
        match = re.search(r'(\d+(?:\.\d+)?%\+?)', text)
        return match.group(1) if match else None
    
    def _extract_key_entities(self, text: str) -> list:
        entities = []
        entities.extend(re.findall(r'"([^"]+)"', text))
        entities.extend(re.findall(r'\(([A-Z][^)]+)\)', text))
        entities.extend(re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text))
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'which'}
        for word in re.findall(r'\b[A-Z][a-z]+\b', text):
            if word.lower() not in common_words:
                entities.append(word)
        return entities
    
    def _is_boolean_match(self, expected: str, actual: str) -> bool:
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
