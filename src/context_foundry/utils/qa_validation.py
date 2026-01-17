"""
Shared QA Validation Module for Context Foundry.

Provides consistent validation across all response paths (ReasoningAgent, ToolAgent direct answers).
Detects metric mismatches, temporal mismatches, and pre-calculated values.

QA Accuracy Fixes Implementation:
- Issue 1: Document metadata garbage detection (Document Owner, etc.)
- Issue 2: Financial metric type distinction (net income vs EBITDA)
- Issue 3: Pre-calculated value detection for growth rates
- Issue 4: Temporal/year mismatch detection  
- Issue 6: Metric type validation (customer retention vs NRR)
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Issue 1 Fix: Document Metadata Garbage Detection
METADATA_GARBAGE_PATTERNS = [
    r'\bdocument\s+owner\b',
    r'\bconfidential\s*[-:]\s*(?:internal|board|executive)',
    r'\bclassification\s*:\s*(?:internal|confidential)',
    r'\bversion\s*:\s*\d+\.\d+',
    r'\beffective\s+date\s*:',
    r'\blast\s+(?:updated|modified)\s*:',
]


def detect_metadata_garbage(answer: str) -> Optional[str]:
    """Issue 1: Detect document metadata garbage in LLM answers."""
    answer_lower = answer.lower()
    
    for pattern in METADATA_GARBAGE_PATTERNS:
        if re.search(pattern, answer_lower, re.IGNORECASE):
            logger.warning(f"[QA Validation] Detected metadata garbage pattern: {pattern}")
            return "Note: The answer may contain document metadata rather than actual content. Please verify the information."
    
    return None


def clean_metadata_garbage(answer: str) -> str:
    """Issue 1: Clean document metadata garbage from LLM answers.
    
    Removes or replaces phrases like "Document Owner" that were incorrectly
    extracted from document metadata headers.
    """
    if not answer:
        return answer
    
    # Patterns that indicate the LLM confused metadata with content
    # Order matters - most specific patterns first
    cleanup_patterns = [
        # "I found multiple people with the Document Owner role: ..." -> remove entire sentence
        (r'I found multiple people with the Document Owner role[^.]*\.?', ''),
        # "The CTO is Document Owner." -> remove the sentence
        (r'[^.!?]*\bis\s+Document\s+Owner\b[^.!?]*[.!?]?', ''),
        # "The CTO of NexaTech is Document Owner" (no period) -> remove
        (r'The\s+\w+\s+(?:of\s+\w+\s+)?is\s+Document\s+Owner\b', ''),
        # "CEO (Document Owner)" -> "CEO"
        (r'\s*\(\s*Document\s+Owner\s*\)\s*', ' '),
        # "- CEO (Document Owner)" list items -> "- CEO"
        (r'-\s*\w+\s*\(\s*Document\s+Owner\s*\)', ''),
        # Standalone "Document Owner" as a name -> remove
        (r'\bDocument\s+Owner\b', ''),
        # Clean up empty parentheses ()
        (r'\(\s*\)', ''),
        # Clean up bullet points with empty content "- -"
        (r'-\s+-', '-'),
        # Clean up remaining double/triple spaces
        (r'\s{2,}', ' '),
        # Clean up leading/trailing spaces in list items
        (r'-\s+\n', '-\n'),
    ]
    
    cleaned = answer
    for pattern, replacement in cleanup_patterns:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    
    # Remove empty list items and clean up
    cleaned = re.sub(r'\n\s*-\s*\n', '\n', cleaned)
    cleaned = re.sub(r':\s*\n\s*\n', ':\n', cleaned)
    
    return cleaned.strip()


# Issue 2 Fix: Financial Metric Type Distinction
FINANCIAL_METRIC_TYPES = {
    'net_income': ['net income', 'net profit', 'net loss', 'bottom line', 'net earnings', 'profit after tax'],
    'ebitda': ['ebitda', 'operating income', 'operating loss', 'operating profit', 'earnings before interest'],
    'gross_profit': ['gross profit', 'gross margin', 'gross income'],
    'revenue': ['revenue', 'sales', 'total revenue', 'net revenue', 'top line'],
}

# Issue 6 Fix: Metric Type Distinction (Customer Retention vs NRR, etc.)
METRIC_DISTINCTIONS = {
    'customer_retention': {
        'aliases': ['customer retention', 'retention rate', 'customer churn', 'churn rate', 'customer loyalty'],
        'not_same_as': ['nrr', 'net revenue retention', 'revenue retention', 'dollar retention', 'arr']
    },
    'nrr': {
        'aliases': ['net revenue retention', 'nrr', 'revenue retention', 'dollar retention', 'drr'],
        'not_same_as': ['customer retention', 'churn rate', 'customer churn', 'gross retention']
    },
    'net_income': {
        'aliases': ['net income', 'net profit', 'net loss', 'profit after tax', 'bottom line'],
        'not_same_as': ['ebitda', 'operating income', 'operating profit', 'gross profit']
    },
    'ebitda': {
        'aliases': ['ebitda', 'operating income', 'operating profit'],
        'not_same_as': ['net income', 'net profit', 'net loss', 'gross profit']
    }
}


@dataclass
class QAValidationResult:
    """Result of QA validation checks."""
    validation_notes: List[str] = field(default_factory=list)
    precalculated_value: Optional[str] = None
    has_warnings: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_notes": self.validation_notes,
            "precalculated_value": self.precalculated_value,
            "has_warnings": self.has_warnings
        }


def classify_financial_metric_in_query(query: str) -> Optional[str]:
    """Issue 2: Classify what financial metric type the query is asking for."""
    query_lower = query.lower()
    
    for metric_type, keywords in FINANCIAL_METRIC_TYPES.items():
        for keyword in keywords:
            if keyword in query_lower:
                return metric_type
    return None


def check_financial_metric_mismatch(query: str, answer: str) -> Optional[str]:
    """Issue 2: Check if answer provides wrong financial metric type."""
    requested_metric = classify_financial_metric_in_query(query)
    if not requested_metric:
        return None
    
    answer_lower = answer.lower()
    
    # Check if we're returning EBITDA when asked for net income
    if requested_metric == 'net_income' and 'ebitda' in answer_lower:
        return "Note: The available data shows EBITDA figures, not net income. EBITDA and net income are different financial metrics - net income is after all expenses and taxes."
    
    # Check if we're returning net income when asked for EBITDA
    if requested_metric == 'ebitda' and ('net income' in answer_lower or 'net profit' in answer_lower):
        return "Note: The available data shows net income figures, not EBITDA. These are different metrics."
    
    return None


def extract_query_year(query: str) -> Optional[str]:
    """Issue 4: Extract the target year from a query."""
    patterns = [
        r'FY\s*(20\d{2})',
        r'(?:in|for|during|end of|at the end of)\s*(?:FY\s*)?(20\d{2})',
        r'(?:fiscal year|fiscal)\s*(20\d{2})',
        r'\b(20\d{2})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def check_temporal_mismatch(query: str, answer: str) -> Optional[str]:
    """Issue 4: Check if answer provides data for wrong year."""
    query_year = extract_query_year(query)
    if not query_year:
        return None
    
    # Look for year mentions in the answer
    answer_years = re.findall(r'(?:FY\s*)?(20\d{2})', answer, re.IGNORECASE)
    
    # If answer mentions a different year prominently, flag it
    for answer_year in answer_years:
        if answer_year != query_year:
            # Check if this is a data mismatch (FY explicitly mentioned with wrong year)
            if f"FY {answer_year}" in answer or f"FY{answer_year}" in answer:
                return f"Note: Query asks for {query_year} data but the response references {answer_year}. Please verify this is the correct time period."
    
    return None


def validate_metric_match(query: str, answer: str) -> Optional[str]:
    """Issue 6: Ensure answer contains the right type of metric."""
    query_lower = query.lower()
    answer_lower = answer.lower()
    
    for metric_type, config in METRIC_DISTINCTIONS.items():
        # Check if query asks for this metric type
        query_asks_for = any(alias in query_lower for alias in config['aliases'])
        
        if query_asks_for:
            # Check if answer provides a different metric type
            answer_has_wrong = any(wrong in answer_lower for wrong in config['not_same_as'])
            query_has_wrong = any(wrong in query_lower for wrong in config['not_same_as'])
            
            # Only flag if query clearly asks for one metric and answer provides another
            if answer_has_wrong and not query_has_wrong:
                logger.warning(f"Metric mismatch: Query asks for {metric_type} but answer may contain different metric")
                return f"Note: The query asks for {metric_type.replace('_', ' ')} but the available data may show a different metric type. Please verify the metric type matches your question."
    
    return None


def find_precalculated_values(documents: List[Dict[str, Any]], query: str) -> Optional[str]:
    """Issue 3: Look for pre-calculated percentages/values in documents.
    
    For growth rate queries, prefer explicitly stated values over calculations.
    """
    query_lower = query.lower()
    calculation_keywords = ['growth rate', 'percentage', 'increase', 'decrease', 'change', 'growth']
    
    is_calculation_query = any(kw in query_lower for kw in calculation_keywords)
    if not is_calculation_query:
        return None
    
    # Extract target year from query
    query_year = extract_query_year(query)
    
    for doc in documents:
        text = doc.get('content', '') or doc.get('text', '') or ''
        
        # Look for patterns like "35% growth" or "growth of 35%" or "increased 35%"
        percentage_patterns = [
            r'(\d+(?:\.\d+)?)\s*%\s*(?:growth|increase|decrease|change)',
            r'(?:growth|increase|decrease|change)\s*(?:of|by)\s*(\d+(?:\.\d+)?)\s*%',
            r'(?:grew|increased|decreased)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%',
            r'year[- ]over[- ]year\s*(?:growth\s*)?(?:of\s*)?(\d+(?:\.\d+)?)\s*%',
            r'yoy\s*(?:growth\s*)?(?:of\s*)?(\d+(?:\.\d+)?)\s*%',
        ]
        
        for pattern in percentage_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Check if the context mentions the relevant year
                if query_year and query_year in text:
                    logger.info(f"Found pre-calculated value in document: {matches[0]}%")
                    return matches[0]
    
    return None


def validate_qa_response(
    query: str,
    answer: str,
    documents: Optional[List[Dict[str, Any]]] = None
) -> QAValidationResult:
    """
    Run all QA validation checks on a query/answer pair.
    
    This is the main entry point for QA validation.
    Call this from both ReasoningAgent and ToolAgent direct answer paths.
    
    Args:
        query: The user's query text
        answer: The generated answer text
        documents: Optional list of retrieved documents/chunks for pre-calculated value detection
        
    Returns:
        QAValidationResult with validation notes and any detected issues
    """
    result = QAValidationResult()
    
    # Issue 1: Check for document metadata garbage in answer
    metadata_warning = detect_metadata_garbage(answer)
    if metadata_warning:
        result.validation_notes.append(metadata_warning)
        logger.info(f"[QA Validation] Metadata garbage detected in answer")
    
    # Issue 2: Check for financial metric type mismatch (net income vs EBITDA)
    financial_warning = check_financial_metric_mismatch(query, answer)
    if financial_warning:
        result.validation_notes.append(financial_warning)
        logger.info(f"[QA Validation] Financial metric mismatch detected")
    
    # Issue 4: Check for temporal/year mismatch
    temporal_warning = check_temporal_mismatch(query, answer)
    if temporal_warning:
        result.validation_notes.append(temporal_warning)
        logger.info(f"[QA Validation] Temporal mismatch detected")
    
    # Issue 6: Check for metric type confusion (customer retention vs NRR, etc.)
    metric_warning = validate_metric_match(query, answer)
    if metric_warning:
        result.validation_notes.append(metric_warning)
        logger.info(f"[QA Validation] Metric type mismatch detected")
    
    # Issue 3: Check for pre-calculated values in documents
    if documents:
        precalc_value = find_precalculated_values(documents, query)
        if precalc_value:
            result.precalculated_value = precalc_value
            logger.info(f"[QA Validation] Found pre-calculated value: {precalc_value}")
    
    result.has_warnings = bool(result.validation_notes)
    
    return result
