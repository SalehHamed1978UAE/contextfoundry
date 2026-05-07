"""
Financial Query Handler - Specialized handling for financial questions.
Retrieves pre-calculated metrics instead of asking LLM to calculate.
"""

import re
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID

logger = logging.getLogger(__name__)


class FinancialQueryHandler:
    """
    Handles financial queries by preferring pre-calculated metrics
    over LLM calculations.
    """

    # P2.2: Expanded metric types — recognized when extracting query parameters
    # and when matching against pre-calculated metrics in the database.
    METRIC_TYPES = {
        # Original 6 (P&L core)
        "revenue", "net_income", "ebitda", "gross_profit", "expenses", "margin",
        # Capital & Investment
        "capex", "capital_expenditure", "capital_spending",
        # Targets & Projections
        "target", "forecast", "projection", "goal", "objective", "plan",
        # Balance Sheet
        "debt", "cash", "assets", "liabilities", "equity", "book_value",
        # Operational
        "burn_rate", "runway", "headcount", "production", "capacity",
        # SaaS / Subscription
        "arr", "mrr", "acr", "churn", "ltv", "cac", "nrr",
        # Valuation
        "valuation", "market_cap", "enterprise_value", "share_price",
    }

    # P2.2: Query-substring → metric_type lookup (broader than the if/elif ladder).
    # Order matters: more specific matches are listed first.
    # Short tokens (arr, mrr, ltv, etc.) are matched with word boundaries
    # against a space-padded lowercased query in _match_metric_keyword().
    METRIC_KEYWORD_MAP = [
        # SaaS / Subscription (check before generic 'recurring')
        ("annual recurring revenue", "arr"),
        ("monthly recurring revenue", "mrr"),
        ("net revenue retention", "nrr"),
        ("customer acquisition cost", "cac"),
        ("lifetime value", "ltv"),
        ("ltv", "ltv"),
        ("arr", "arr"),
        ("mrr", "mrr"),
        ("nrr", "nrr"),
        ("cac", "cac"),
        ("churn", "churn"),
        # Capital
        ("capex", "capex"),
        ("capital expenditure", "capex"),
        ("capital spending", "capex"),
        # Operational
        ("burn rate", "burn_rate"),
        ("runway", "runway"),
        ("headcount", "headcount"),
        ("production capacity", "capacity"),
        ("production", "production"),
        ("capacity", "capacity"),
        # Balance sheet
        ("book value", "book_value"),
        ("total debt", "debt"),
        ("debt", "debt"),
        ("cash on hand", "cash"),
        ("cash position", "cash"),
        ("total assets", "assets"),
        ("total liabilities", "liabilities"),
        ("equity", "equity"),
        # Valuation
        ("market cap", "market_cap"),
        ("market capitalization", "market_cap"),
        ("enterprise value", "enterprise_value"),
        ("share price", "share_price"),
        ("valuation", "valuation"),
        # Targets / Projections
        ("forecast", "forecast"),
        ("projection", "projection"),
        ("target", "target"),
    ]

    FINANCIAL_QUERY_PATTERNS = [
        r'what\s+(?:was|is|were)\s+(?:the\s+)?(?:total\s+)?revenue',
        r'what\s+(?:was|is|were)\s+(?:the\s+)?(?:net\s+)?income',
        r'what\s+(?:was|is|were)\s+(?:the\s+)?(?:gross\s+)?(?:profit|margin)',
        r'what\s+(?:was|is|were)\s+(?:the\s+)?ebitda',
        r'growth\s+rate',
        r'year[- ]over[- ]year',
        r'yoy',
        r'cagr',
        r'margin',
        r'how\s+much\s+(?:did|does|was)',
        r'what\s+percentage',
        r'revenue\s+growth',
        r'income\s+growth',
        r'expense\s+growth',
    ]

    def __init__(self, session, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.FINANCIAL_QUERY_PATTERNS]

    @staticmethod
    def _match_metric_keyword(keyword: str, query_lower: str) -> bool:
        """Match a metric keyword against a lowercased query.

        Short alphanumeric-only keywords (e.g. 'arr', 'mrr', 'ltv', 'capex')
        are matched with word boundaries to avoid false positives like
        'narrative' matching 'arr'. Multi-word keywords use plain substring.
        """
        if " " in keyword:
            return keyword in query_lower
        # Word-boundary match for single tokens
        return re.search(r'\b' + re.escape(keyword) + r'\b', query_lower) is not None

    def is_financial_query(self, query: str) -> bool:
        """Check if query is asking for financial data.

        P2.2: Also matches when any expanded metric keyword is present
        (ARR, MRR, capex, debt, cash, headcount, market cap, etc.) so
        the expanded handler actually gets reached.
        """
        if any(p.search(query) for p in self._patterns):
            return True
        ql = query.lower()
        return any(self._match_metric_keyword(kw, ql) for kw, _ in self.METRIC_KEYWORD_MAP)

    def extract_query_parameters(self, query: str) -> Dict[str, Any]:
        """
        Extract parameters from a financial query.

        Returns:
            Dict with metric_type, time_period, comparison_type, etc.
        """
        params = {}

        query_lower = query.lower()

        # P2.2: Check expanded keyword map first for specialized metrics
        # (capex, ARR, MRR, churn, debt, cash, valuation, headcount, etc.).
        # Only fall through to the original P&L ladder if no specialized match.
        for keyword, metric in self.METRIC_KEYWORD_MAP:
            if self._match_metric_keyword(keyword, query_lower):
                params['metric_type'] = metric
                break

        if 'metric_type' in params:
            pass  # Specialized metric already matched
        # P2.2: Margin detection BEFORE operating→ebitda branch so
        # "operating margin" / "gross margin" / "net margin" route correctly.
        elif 'margin' in query_lower:
            params['is_ratio'] = True
            if 'gross' in query_lower:
                params['metric_type'] = 'gross_margin'
            elif 'net' in query_lower:
                params['metric_type'] = 'net_margin'
            elif 'operating' in query_lower:
                params['metric_type'] = 'operating_margin'
            else:
                params['metric_type'] = 'margin'
        elif any(x in query_lower for x in ['revenue', 'sales']):
            params['metric_type'] = 'revenue'
        elif 'net income' in query_lower or 'net loss' in query_lower:
            params['metric_type'] = 'net_income'
        elif 'ebitda' in query_lower or 'operating' in query_lower:
            params['metric_type'] = 'ebitda'
        elif 'gross' in query_lower:
            params['metric_type'] = 'gross_profit'
        elif 'expense' in query_lower:
            params['metric_type'] = 'expenses'

        time_periods = []
        fy_matches = re.findall(r'FY\s*(\d{4}|\d{2})', query, re.IGNORECASE)
        for match in fy_matches:
            year = match if len(match) == 4 else '20' + match
            time_periods.append(f"FY{year}")
        
        year_matches = re.findall(r'\b(20\d{2})\b', query)
        for year in year_matches:
            period = f"FY{year}"
            if period not in time_periods:
                time_periods.append(period)

        if time_periods:
            params['time_periods'] = time_periods
            if len(time_periods) == 1:
                params['time_period'] = time_periods[0]

        if any(x in query_lower for x in ['growth', 'change', 'increase', 'decrease', 'grew']):
            params['is_growth'] = True

        if 'cagr' in query_lower or 'compound' in query_lower:
            params['is_cagr'] = True

        if len(time_periods) == 2:
            params['is_comparison'] = True
            params['from_period'] = min(time_periods)
            params['to_period'] = max(time_periods)

        return params

    def find_matching_metrics(
        self,
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find pre-calculated metrics matching the query parameters.
        """
        from sqlalchemy import text

        conditions = ["tenant_id = :tenant_id"]
        bind_params = {'tenant_id': str(self.tenant_id)}

        metric_type = params.get('metric_type')
        is_growth = params.get('is_growth', False)
        is_cagr = params.get('is_cagr', False)
        from_period = params.get('from_period')
        to_period = params.get('to_period')

        if is_growth or is_cagr:
            conditions.append("entity_type = 'CALCULATED_METRIC'")
            
            if metric_type:
                if is_cagr:
                    conditions.append("name LIKE :name_pattern")
                    bind_params['name_pattern'] = f"{metric_type}_cagr%"
                else:
                    conditions.append("name LIKE :name_pattern")
                    bind_params['name_pattern'] = f"{metric_type}_yoy_growth%"
            
            if from_period and to_period:
                time_period_str = f"{from_period} to {to_period}"
                conditions.append("properties->>'time_period' = :time_period")
                bind_params['time_period'] = time_period_str
        else:
            if metric_type:
                conditions.append("properties->>'metric_type' = :metric_type")
                bind_params['metric_type'] = metric_type

            time_period = params.get('time_period')
            if time_period:
                conditions.append("properties->>'time_period' = :time_period")
                bind_params['time_period'] = time_period

            conditions.append("entity_type IN ('FINANCIAL_METRIC', 'CALCULATED_METRIC')")

        query = f"""
            SELECT name, entity_type, properties, confidence
            FROM public.entities
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE WHEN entity_type = 'CALCULATED_METRIC' AND properties->>'time_period' IS NOT NULL THEN 0
                     WHEN entity_type = 'FINANCIAL_METRIC' THEN 1
                     ELSE 2 END,
                confidence DESC
            LIMIT 10
        """

        try:
            result = self.session.execute(text(query), bind_params)
            rows = result.fetchall()
            return [
                {
                    'name': row.name,
                    'entity_type': row.entity_type,
                    'attributes': row.properties if isinstance(row.properties, dict) else {},
                    'confidence': row.confidence
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"[FINANCIAL] Query failed: {e}")
            return []

    def format_financial_answer(
        self,
        metrics: List[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> Optional[str]:
        """
        Format financial metrics into a natural language answer.
        """
        if not metrics:
            return None

        metric = metrics[0]
        attrs = metric.get('attributes', {})

        value = attrs.get('value')
        if value is None:
            return None

        unit = attrs.get('unit', '')
        period = attrs.get('time_period', '')
        formula = attrs.get('formula')
        source_doc = attrs.get('source_document', '')

        if unit == '%':
            formatted_value = f"{value}%"
        elif unit == '$M':
            formatted_value = f"${value:,.1f} million"
        elif unit == '$K':
            formatted_value = f"${value:,.1f} thousand"
        elif unit == '$':
            formatted_value = f"${value:,.2f}"
        elif unit == 'x':
            formatted_value = f"{value}x"
        else:
            formatted_value = str(value)

        metric_name = params.get('metric_type', 'metric')
        if metric_name:
            metric_name = metric_name.replace('_', ' ')

        is_growth = params.get('is_growth', False) or 'growth' in metric.get('name', '')

        if is_growth:
            if period:
                answer = f"The {metric_name} growth from {period} was {formatted_value}."
            else:
                answer = f"The {metric_name} growth rate was {formatted_value}."
        elif period:
            answer = f"The {metric_name} for {period} was {formatted_value}."
        else:
            answer = f"The {metric_name} was {formatted_value}."

        if formula and metric.get('entity_type') == 'CALCULATED_METRIC':
            answer += f" (Calculated: {formula})"

        if source_doc:
            answer += f" [Source: {source_doc}]"

        return answer

    def handle_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Main entry point: Check if query is financial, find matching metrics, 
        and return pre-calculated answer if available.
        
        Returns:
            Dict with 'answer', 'confidence', 'source' if match found, else None
        """
        if not self.is_financial_query(query):
            return None

        params = self.extract_query_parameters(query)
        logger.info(f"[FINANCIAL] Detected financial query, params: {params}")

        if not params.get('metric_type') and not params.get('is_growth'):
            return None

        metrics = self.find_matching_metrics(params)
        
        if not metrics:
            logger.info("[FINANCIAL] No matching pre-calculated metrics found")
            return None

        logger.info(f"[FINANCIAL] Found {len(metrics)} matching metrics: {[m['name'] for m in metrics]}")

        answer = self.format_financial_answer(metrics, params)
        
        if not answer:
            return None

        return {
            'answer': answer,
            'confidence': metrics[0].get('confidence', 0.95),
            'source': 'pre_calculated',
            'metric_name': metrics[0].get('name'),
            'entity_type': metrics[0].get('entity_type'),
        }
