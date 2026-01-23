import re
import logging
import os
from typing import Tuple, Dict, Any, Optional

from openai import OpenAI

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
    
    # Location aliases for HQ/office location matching
    LOCATION_ALIASES = {
        "boston": ["boston, ma", "boston, massachusetts", "boston, massachusetts, usa", "boston ma", "boston massachusetts"],
        "san francisco": ["san francisco, ca", "san francisco, california", "sf", "san francisco ca", "san francisco california"],
        "new york": ["new york, ny", "new york city", "nyc", "new york, new york", "new york ny"],
        "los angeles": ["los angeles, ca", "la", "los angeles california", "los angeles ca"],
        "seattle": ["seattle, wa", "seattle, washington", "seattle wa"],
        "austin": ["austin, tx", "austin, texas", "austin tx"],
        "chicago": ["chicago, il", "chicago, illinois", "chicago il"],
        "denver": ["denver, co", "denver, colorado", "denver co"],
    }
    
    # Boolean/compliance answer normalization
    BOOLEAN_ALIASES = {
        "yes": ["yes", "true", "affirmative", "correct", "confirmed", "compliant", "achieved", "passed"],
        "no": ["no", "false", "negative", "not compliant", "not achieved", "failed", "n/a"],
    }
    
    def __init__(self):
        self.last_evaluation_details: Optional[Dict[str, Any]] = None
        
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        self.llm_client = None
        if api_key:
            try:
                self.llm_client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            except Exception as e:
                logger.warning(f"OpenAI client init failed, semantic equivalence disabled: {e}")
    
    def _check_semantic_equivalence(self, expected: str, actual: str, question: str) -> bool:
        """Use LLM to check if expected and actual are semantically equivalent answers."""
        if not self.llm_client:
            logger.debug("[SEMANTIC] Skipped - no LLM client")
            return False
        
        logger.info(f"[SEMANTIC] Checking: expected='{expected}' vs actual='{actual[:100]}...' question='{question[:50]}...'")
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"""Question: {question}
Expected answer: {expected}
Actual answer: {actual}

Are these semantically equivalent answers to the question?
Consider: abbreviations (CEO = Chief Executive Officer), different phrasings,
and cases where actual contains the expected information.

Reply YES or NO only."""
                }],
                temperature=0,
                max_tokens=3
            )
            result = response.choices[0].message.content.strip().upper() == "YES"
            logger.info(f"[SEMANTIC] Result: {result} (LLM response: '{response.choices[0].message.content.strip()}')")
            return result
        except Exception as e:
            logger.warning(f"[SEMANTIC] Check failed: {e}")
            return False
    
    def normalize_answer(self, text: str) -> str:
        """
        Normalize an answer by stripping boilerplate and standardizing format.
        Returns the normalized text.
        """
        if not text:
            return ""
        
        normalized = text.strip()
        
        # Remove markdown bold/italic formatting (**text** or *text* or __text__)
        normalized = re.sub(r'\*\*([^*]+)\*\*', r'\1', normalized)  # **bold**
        normalized = re.sub(r'\*([^*]+)\*', r'\1', normalized)      # *italic*
        normalized = re.sub(r'__([^_]+)__', r'\1', normalized)      # __bold__
        normalized = re.sub(r'_([^_]+)_', r'\1', normalized)        # _italic_
        
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
    
    def normalize_location(self, text: str) -> str:
        """Normalize location text to canonical form."""
        if not text:
            return ""
        text_lower = text.lower().strip()
        for canonical, aliases in self.LOCATION_ALIASES.items():
            if text_lower == canonical or text_lower in aliases:
                return canonical
        return text_lower
    
    def normalize_boolean(self, text: str) -> Optional[str]:
        """Normalize boolean/compliance answers to 'yes' or 'no'."""
        if not text:
            return None
        text_lower = text.lower().strip()
        for canonical, aliases in self.BOOLEAN_ALIASES.items():
            if text_lower in aliases or text_lower == canonical:
                return canonical
        return None
    
    def _locations_match(self, expected: str, actual: str) -> bool:
        """Check if two locations refer to the same place."""
        norm_expected = self.normalize_location(expected)
        norm_actual = self.normalize_location(actual)
        if norm_expected == norm_actual:
            return True
        if norm_expected in norm_actual or norm_actual in norm_expected:
            return True
        return False
    
    def _booleans_match(self, expected: str, actual: str) -> bool:
        """Check if two boolean/compliance answers match."""
        norm_expected = self.normalize_boolean(expected)
        norm_actual = self.normalize_boolean(actual)
        if norm_expected is None or norm_actual is None:
            return False
        return norm_expected == norm_actual
    
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
    
    def key_component_match(self, expected: str, actual: str) -> bool:
        """
        Check if all key components from expected appear in actual.
        Handles cases where exact substring doesn't match due to phrasing variations.
        
        Key components: numbers, times, percentages, and significant words (3+ chars).
        """
        # Strip parenthetical content from expected (often supplementary info)
        expected_core = re.sub(r'\([^)]*\)', '', expected).strip()
        expected_lower = expected_core.lower()
        actual_lower = actual.lower()
        
        # Extract times (e.g., "2:15 PM", "3:30 PM EST")
        time_pattern = r'\d{1,2}:\d{2}\s*(?:am|pm)?(?:\s*[a-z]{2,4})?'
        expected_times = set(re.findall(time_pattern, expected_lower))
        if expected_times:
            actual_times = set(re.findall(time_pattern, actual_lower))
            if not expected_times.issubset(actual_times):
                return False
        
        # Extract numbers (integers and decimals) from core expected only
        number_pattern = r'\d+(?:,\d{3})*(?:\.\d+)?'
        expected_nums = set(re.findall(number_pattern, expected_core.replace(',', '')))
        if expected_nums:
            actual_nums = set(re.findall(number_pattern, actual.replace(',', '')))
            # Check if at least 80% of expected numbers are in actual
            if not expected_nums.issubset(actual_nums):
                # Try without decimals for integer comparison
                expected_int = {n.split('.')[0] for n in expected_nums}
                actual_int = {n.split('.')[0] for n in actual_nums}
                if not expected_int.issubset(actual_int):
                    return False
        
        # Extract key words (significant terms, excluding common words)
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'with', 'and', 'or', 'to', 'from', 'for', 'of', 'in', 'on', 'at', 'by', 'has', 'have', 'had', 'which', 'that', 'this', 'be', 'been'}
        expected_words = set(re.findall(r'[a-z]{3,}', expected_lower)) - stopwords
        if expected_words:
            # At least 70% of key words should appear
            matches = sum(1 for w in expected_words if w in actual_lower)
            if matches < len(expected_words) * 0.7:
                return False
        
        return True
    
    def evaluate(self, expected: str, actual: str, query: str = "") -> Tuple[bool, str]:
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
        
        # Handle "Can be inferred" meta-answers
        # When expected says data is implicit/inferred, any substantive answer passes
        if "can be inferred" in expected_lower or "inferred but not explicitly" in expected_lower:
            # If actual provides data (not a no_data response), it's a pass
            if not actual_no_data and len(actual_norm) > 20:
                self.last_evaluation_details['match_type'] = 'inference_match'
                return True, "inference_match"
        
        # Exact/substring match (after normalization)
        if expected_lower in actual_lower:
            self.last_evaluation_details['match_type'] = 'exact_match'
            return True, "exact_match"
        
        # Key component matching (handles phrasing variations)
        # e.g., "2:15 PM to 3:30 PM" in actual "from 2:15 PM to 3:30 PM"
        # e.g., "Green (Healthy) with 110 customers" vs "Green (Healthy), which has 110 customers"
        if self.key_component_match(expected, actual):
            self.last_evaluation_details['match_type'] = 'component_match'
            return True, "component_match"
        
        # Location matching (Boston vs Boston, MA vs Boston, Massachusetts)
        if self._locations_match(expected_norm, actual_norm):
            self.last_evaluation_details['match_type'] = 'location_match'
            return True, "location_match"
        
        # Boolean/compliance matching (Yes vs Compliant vs Achieved)
        if self._booleans_match(expected_norm, actual_norm):
            self.last_evaluation_details['match_type'] = 'boolean_match'
            return True, "boolean_match"
        
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
        
        # Entity alias matching (handles abbreviations and alternate names)
        if self._entities_match_with_aliases(expected_norm, actual_norm):
            self.last_evaluation_details['match_type'] = 'alias_match'
            return True, "alias_match"
        
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
        
        # Try LLM semantic equivalence as last resort
        if self._check_semantic_equivalence(expected, actual, query):
            self.last_evaluation_details['match_type'] = 'semantic_match'
            return True, "semantic_match"

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
    
    def evaluate_with_details(self, expected: str, actual: str, query: str = "") -> Dict[str, Any]:
        """
        Evaluate and return full details including normalized values and failure reason.
        Useful for logging and debugging.
        """
        passed, match_type = self.evaluate(expected, actual, query)
        
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
    
    ENTITY_ALIASES = {
        'global defense systems': ['gds', 'defense systems', 'defense business unit'],
        'orion aerospace': ['aerospace', 'aerospace division', 'aero'],
        'orion energy solutions': ['energy solutions', 'energy', 'energy division'],
        'orion logistics': ['logistics', 'logistics division'],
        'orion smartcity': ['smartcity', 'smart city', 'smartcity division'],
        'sarah chen': ['chen', 'ceo chen', 's. chen'],
        'marcus webb': ['webb', 'cfo webb', 'm. webb'],
        'dr. evelyn reed': ['evelyn reed', 'reed', 'cto reed', 'dr reed', 'e. reed'],
        'alex thorne': ['thorne', 'coo thorne', 'a. thorne'],
        'fatima al-mansoori': ['al-mansoori', 'fatima', 'cso', 'chief sustainability'],
        'james park': ['park', 'general counsel park', 'j. park'],
        'dr. elena rostova': ['elena rostova', 'rostova', 'cdo rostova', 'dr rostova', 'e. rostova'],
        'admiral michael torres': ['michael torres', 'torres', 'admiral torres', 'vp defense'],
        'project helios': ['helios', 'helios project'],
        'falcon uav program': ['falcon uav', 'falcon program', 'uav program'],
        'urbanmesh iot platform': ['urbanmesh', 'urban mesh', 'iot platform'],
        'autonav logistics system': ['autonav', 'auto nav', 'autonav system'],
        'project borealis': ['borealis', 'borealis wind'],
    }
    
    def _normalize_with_aliases(self, text: str) -> str:
        """Normalize text and expand known entity aliases."""
        if not text:
            return ""
        
        text_lower = text.lower().strip()
        
        for canonical, aliases in self.ENTITY_ALIASES.items():
            if text_lower == canonical:
                return canonical
            for alias in aliases:
                if text_lower == alias:
                    return canonical
        
        return text_lower
    
    def _entities_match_with_aliases(self, expected: str, actual: str) -> bool:
        """Check if entities match after alias expansion."""
        exp_norm = self._normalize_with_aliases(expected)
        act_norm = self._normalize_with_aliases(actual)
        
        if exp_norm == act_norm:
            return True
        
        if exp_norm in act_norm or act_norm in exp_norm:
            return True
        
        return False
    
    def get_failure_category(self, match_type: str) -> str:
        """
        Map match_type to a detailed failure category for analysis.
        """
        if match_type == "no_data":
            return "NO_DATA"
        elif match_type == "should_say_unknown":
            return "SHOULD_REFUSE"
        elif match_type == "no_answer":
            return "NO_ANSWER"
        elif match_type == "timeout":
            return "TIMEOUT"
        elif match_type == "error":
            return "ERROR"
        elif match_type == "number_mismatch":
            return "FORMAT_MISMATCH"
        elif match_type == "partial_match":
            return "ALTERNATE_SOURCE"
        else:
            return "MISMATCH"
    
    def classify_failure(self, expected: str, actual: str, match_type: str) -> dict:
        """
        Provide detailed classification of why a match failed.
        
        Returns dict with:
            - category: High-level category (NO_DATA, FORMAT_MISMATCH, ALTERNATE_SOURCE, NOT_FOUND)
            - reason: Specific reason for failure
            - suggestion: Potential fix
        """
        result = {
            'category': self.get_failure_category(match_type),
            'reason': match_type,
            'suggestion': None
        }
        
        if not actual:
            result['category'] = 'NO_DATA'
            result['reason'] = 'System returned no answer'
            result['suggestion'] = 'Check if query retrieves relevant documents'
            return result
        
        if self.detect_no_data(actual):
            result['category'] = 'NOT_FOUND'
            result['reason'] = 'System explicitly said no data found'
            result['suggestion'] = 'Verify answer exists in corpus documents'
            return result
        
        exp_num = self.normalize_number(expected)
        if exp_num is not None:
            act_nums = self._extract_numbers(actual)
            if act_nums and exp_num not in [float(n) for n in act_nums]:
                result['category'] = 'FORMAT_MISMATCH'
                result['reason'] = f'Number format mismatch: expected {exp_num}, found {act_nums}'
                result['suggestion'] = 'Check for alternate number formats in source'
                return result
        
        if self._entities_match_with_aliases(expected, actual):
            result['category'] = 'ALTERNATE_SOURCE'
            result['reason'] = 'Matched via entity alias expansion'
            return result
        
        exp_words = set(expected.lower().split())
        act_words = set(actual.lower().split())
        overlap = len(exp_words & act_words) / max(len(exp_words), 1)
        
        if overlap > 0.5:
            result['category'] = 'ALTERNATE_SOURCE'
            result['reason'] = f'Partial overlap ({overlap:.0%}) - may be from different source'
            result['suggestion'] = 'Check source folder priority'
        else:
            result['category'] = 'MISMATCH'
            result['reason'] = 'No significant overlap between expected and actual'
            result['suggestion'] = 'Verify question references correct document'
        
        return result
