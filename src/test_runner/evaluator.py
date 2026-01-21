import re
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

class FuzzyEvaluator:
    """
    Evaluate answers with semantic matching, not strict string matching.
    Includes answer normalization and detailed failure logging.
    """
    
    # Boilerplate phrases to strip from LLM responses
    BOILERPLATE_PATTERNS = [
        r'^according to (?:the )?(?:documents?|reports?|data|information)[,\s]*',
        r'^based on (?:the )?(?:documents?|reports?|data|information|available)[,\s]*',
        r'^the (?:documents?|reports?|data) (?:shows?|indicates?|states?)[,\s]*',
        r"^here'?s? (?:the )?answer[:\s]*",
        r'^the answer is[:\s]*',
        r'^in the (?:documents?|reports?)[,\s]*',
        r'^from the (?:documents?|reports?)[,\s]*',
        r'^(?:yes|no)[,\.\s]+',  # Strip leading yes/no before main content
    ]
    
    # Company suffixes to normalize
    COMPANY_SUFFIXES = [
        r',?\s*inc\.?$',
        r',?\s*incorporated$',
        r',?\s*ltd\.?$',
        r',?\s*limited$',
        r',?\s*llc\.?$',
        r',?\s*corp\.?$',
        r',?\s*corporation$',
        r',?\s*co\.?$',
        r',?\s*company$',
        r',?\s*plc\.?$',
        r',?\s*& co\.?$',
    ]
    
    # Phrases indicating no data available
    NO_DATA_PHRASES = [
        "not available", "not provided", "does not provide",
        "does not specify", "no information", "not found in",
        "cannot find", "don't have information", "not in the documents",
        "not mentioned", "insufficient data", "no data",
        "unable to find", "could not find", "doesn't specify",
        "isn't specified", "not included", "not explicitly",
        "no relevant", "couldn't locate", "missing from",
        "not present", "not disclosed", "i don't have",
        "i cannot find", "there is no", "there's no"
    ]
    
    def __init__(self):
        self.last_evaluation_details: Optional[Dict[str, Any]] = None
    
    def normalize_answer(self, text: str) -> str:
        """
        Normalize an answer by stripping boilerplate and standardizing format.
        Returns the normalized text.
        """
        if not text:
            return ""
        
        normalized = text.strip()
        
        # Remove boilerplate phrases (case-insensitive)
        for pattern in self.BOILERPLATE_PATTERNS:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE).strip()
        
        # Normalize company names by removing suffixes
        for suffix in self.COMPANY_SUFFIXES:
            normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE).strip()
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove trailing punctuation except for % and numbers
        normalized = re.sub(r'[\.,:;!]+$', '', normalized)
        
        return normalized.strip()
    
    def normalize_number(self, text: str) -> Optional[float]:
        """
        Convert various number formats to a canonical float value.
        Handles: $40M, $40.0 million, 40,000,000, 40 million, etc.
        
        IMPORTANT: Only use this for short, focused expressions (typically expected values).
        For long verbose answers, use _extract_numbers() instead which finds all numbers.
        """
        if not text:
            return None
        
        text = text.strip()
        
        # Skip very long text (likely verbose answer) - use legacy extraction instead
        if len(text) > 50:
            return None
        
        # Pattern: optional $, number (with optional commas/decimals), optional multiplier
        # This matches complete currency/number expressions like "$40 million", "40M", "2,500"
        pattern = r'^\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(million|billion|trillion|thousand|[mbkt])?\s*$'
        match = re.match(pattern, text.lower())
        
        if not match:
            # Try simpler pattern: just a number with possible $ and commas
            pattern2 = r'^\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$'
            match = re.match(pattern2, text.lower())
            if not match:
                return None
            multiplier = 1
        else:
            multiplier_str = match.group(2) or ''
            if multiplier_str in ('trillion', 't'):
                multiplier = 1_000_000_000_000
            elif multiplier_str in ('billion', 'b'):
                multiplier = 1_000_000_000
            elif multiplier_str in ('million', 'm'):
                multiplier = 1_000_000
            elif multiplier_str in ('thousand', 'k'):
                multiplier = 1_000
            else:
                multiplier = 1
        
        try:
            num_str = match.group(1).replace(',', '')
            return float(num_str) * multiplier
        except ValueError:
            return None
    
    def normalize_percentage(self, text: str) -> Optional[float]:
        """
        Convert percentage to decimal for comparison.
        Handles: 60%, 0.60, 60 percent, etc.
        """
        if not text:
            return None
        
        cleaned = text.strip().lower()
        
        # Handle "X percent" or "X%"
        match = re.search(r'([\d.]+)\s*(?:%|percent)', cleaned)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        
        # Handle decimal form (0.60)
        match = re.search(r'^0\.\d+$', cleaned)
        if match:
            try:
                return float(cleaned) * 100
            except ValueError:
                return None
        
        return None
    
    def detect_no_data(self, actual: str) -> bool:
        """
        Detect if the response indicates no data was found.
        """
        if not actual:
            return True
        
        actual_lower = actual.lower()
        return any(phrase in actual_lower for phrase in self.NO_DATA_PHRASES)
    
    def evaluate(self, expected: str, actual: str) -> Tuple[bool, str]:
        """
        Returns (passed, match_type).
        Also populates self.last_evaluation_details with detailed info.
        """
        # Initialize evaluation details for logging
        self.last_evaluation_details = {
            'expected_raw': expected,
            'actual_raw': actual,
            'expected_normalized': None,
            'actual_normalized': None,
            'failure_reason': None,
            'match_type': None
        }
        
        if not actual:
            self.last_evaluation_details['failure_reason'] = 'no_answer_provided'
            return False, "no_answer"
        
        # Normalize both answers
        expected_norm = self.normalize_answer(expected)
        actual_norm = self.normalize_answer(actual)
        
        self.last_evaluation_details['expected_normalized'] = expected_norm
        self.last_evaluation_details['actual_normalized'] = actual_norm
        
        expected_lower = expected_norm.lower()
        actual_lower = actual_norm.lower()
        
        # Check if actual answer indicates no data was found
        actual_no_data = self.detect_no_data(actual)
        
        # Handle expected "[not in documents]" FIRST - before substring match
        # Otherwise verbose actual that includes "[not in documents]" substring could false-match
        if expected_lower == "[not in documents]":
            if actual_no_data:
                self.last_evaluation_details['match_type'] = 'uncertainty_match'
                return True, "uncertainty_match"
            self.last_evaluation_details['failure_reason'] = 'should_say_unknown'
            return False, "should_say_unknown"
        
        # Exact/substring match (after normalization)
        if expected_lower in actual_lower:
            self.last_evaluation_details['match_type'] = 'exact_match'
            return True, "exact_match"
        
        # NOTE: NO_DATA check moved to AFTER all matching attempts
        # This prevents false NO_DATA when response contains both "does not specify" boilerplate
        # AND actual data/numbers that could match
        
        # Try number matching with improved normalization
        expected_num = self.normalize_number(expected)
        actual_num = self.normalize_number(actual)
        
        if expected_num is not None and actual_num is not None:
            # Allow 1% tolerance for floating point
            if abs(expected_num - actual_num) / max(expected_num, 1) < 0.01:
                self.last_evaluation_details['match_type'] = 'number_match'
                return True, "number_match"
            # Fall through to try other methods
        
        # Legacy number extraction for complex cases
        expected_numbers = self._extract_numbers(expected)
        actual_numbers = self._extract_numbers(actual)
        
        if expected_numbers:
            if expected_numbers.issubset(actual_numbers):
                self.last_evaluation_details['match_type'] = 'number_match'
                return True, "number_match"
            
            expected_primary = self._get_primary_number(expected)
            actual_primary = self._get_primary_number(actual)
            if expected_primary and actual_primary:
                if self._numbers_match(expected_primary, actual_primary):
                    self.last_evaluation_details['match_type'] = 'number_match'
                    return True, "number_match"
        
        # Percentage matching with improved normalization
        expected_pct = self.normalize_percentage(expected)
        actual_pct = self.normalize_percentage(actual)
        if expected_pct is not None and actual_pct is not None:
            if abs(expected_pct - actual_pct) < 0.1:  # 0.1% tolerance
                self.last_evaluation_details['match_type'] = 'percentage_match'
                return True, "percentage_match"
        
        # Legacy percentage matching
        expected_pct_str = self._extract_percentage(expected)
        actual_pct_str = self._extract_percentage(actual)
        if expected_pct_str and actual_pct_str:
            if expected_pct_str.rstrip('+%') == actual_pct_str.rstrip('+%'):
                self.last_evaluation_details['match_type'] = 'percentage_match'
                return True, "percentage_match"
        
        # Entity/name matching (handles variants)
        expected_entities = self._extract_key_entities(expected)
        if expected_entities:
            # Normalize entity names for comparison
            normalized_expected = [self.normalize_answer(e).lower() for e in expected_entities]
            matches = sum(1 for e in normalized_expected if e in actual_lower)
            if matches >= len(expected_entities) * 0.7:
                self.last_evaluation_details['match_type'] = 'entity_match'
                return True, "entity_match"
        
        # Boolean matching
        if self._is_boolean_match(expected_lower, actual_lower):
            self.last_evaluation_details['match_type'] = 'boolean_match'
            return True, "boolean_match"
        
        # All matching attempts failed - now check if it's a NO_DATA response
        # This is checked LAST so that responses with both "does not specify" boilerplate
        # AND actual matching data still pass the matching checks above
        # 
        # Additional safeguard: if actual contains numbers, don't classify as NO_DATA
        # because the response DID provide data (even if it didn't match expected)
        actual_has_numbers = bool(actual_numbers) or self._extract_numbers(actual)
        if actual_no_data and not actual_has_numbers:
            self.last_evaluation_details['failure_reason'] = 'no_data'
            return False, "no_data"
        
        # Determine specific failure reason for non-NO_DATA failures
        if expected_numbers or expected_num is not None:
            self.last_evaluation_details['failure_reason'] = 'no_match_numeric'
        elif expected_entities:
            self.last_evaluation_details['failure_reason'] = 'name_variant'
        else:
            self.last_evaluation_details['failure_reason'] = 'no_match'
        
        return False, "no_match"
    
    def _extract_numbers(self, text: str) -> set:
        numbers = set()
        
        # Pattern 1: Currency with suffix like $40M, $2.5B
        for match in re.findall(r'\$[\d,]+(?:\.\d+)?(?:[MmBbKkTt])?', text):
            numbers.add(self._normalize_number_legacy(match))
        
        # Pattern 2: Number with word multiplier like "40 million", "$2.5 billion"
        for match in re.findall(r'\$?[\d,]+(?:\.\d+)?\s*(?:million|billion|trillion|thousand)', text, re.IGNORECASE):
            numbers.add(self._normalize_number_legacy(match))
        
        # Pattern 3: Plain numbers (only if not already captured)
        for match in re.findall(r'\b[\d,]+(?:\.\d+)?\b', text):
            normalized = self._normalize_number_legacy(match)
            if normalized:
                numbers.add(normalized)
        
        return numbers
    
    def _normalize_number_legacy(self, num_str: str) -> str:
        """Legacy normalization for _extract_numbers - handles various formats."""
        cleaned = num_str.replace('$', '').replace(',', '').strip().lower()
        
        # Handle word multipliers
        multiplier = 1
        if 'trillion' in cleaned:
            multiplier = 1_000_000_000_000
            cleaned = cleaned.replace('trillion', '').strip()
        elif 'billion' in cleaned:
            multiplier = 1_000_000_000
            cleaned = cleaned.replace('billion', '').strip()
        elif 'million' in cleaned:
            multiplier = 1_000_000
            cleaned = cleaned.replace('million', '').strip()
        elif 'thousand' in cleaned:
            multiplier = 1_000
            cleaned = cleaned.replace('thousand', '').strip()
        # Handle letter suffixes
        elif cleaned.endswith(('t',)):
            multiplier = 1_000_000_000_000
            cleaned = cleaned[:-1]
        elif cleaned.endswith(('b',)):
            multiplier = 1_000_000_000
            cleaned = cleaned[:-1]
        elif cleaned.endswith(('m',)):
            multiplier = 1_000_000
            cleaned = cleaned[:-1]
        elif cleaned.endswith(('k',)):
            multiplier = 1_000
            cleaned = cleaned[:-1]
        
        try:
            value = float(cleaned) * multiplier
            return str(int(value))
        except:
            return cleaned
    
    
    def _get_primary_number(self, text: str) -> Optional[str]:
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
    
    def _extract_percentage(self, text: str) -> Optional[str]:
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
    
    def evaluate_with_details(self, expected: str, actual: str) -> Dict[str, Any]:
        """
        Evaluate and return full details including normalized values and failure reason.
        Useful for logging and debugging.
        """
        passed, match_type = self.evaluate(expected, actual)
        
        details = self.last_evaluation_details.copy() if self.last_evaluation_details else {}
        details['passed'] = passed
        details['match_type'] = match_type
        
        # Log failures with details
        if not passed:
            logger.debug(
                f"Evaluation failed: {details.get('failure_reason', 'unknown')}\n"
                f"  Expected (norm): {details.get('expected_normalized', '')[:100]}\n"
                f"  Actual (norm): {details.get('actual_normalized', '')[:100]}"
            )
        
        return details
    
    def get_failure_category(self, match_type: str) -> str:
        """
        Map match_type to a UI-friendly failure category.
        """
        if match_type == "no_data":
            return "NO_DATA"
        elif match_type == "should_say_unknown":
            return "SHOULD_REFUSE"
        elif match_type == "no_answer":
            return "NO_ANSWER"
        else:
            return "MISMATCH"
