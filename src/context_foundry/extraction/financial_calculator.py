"""
Financial Calculator - Pre-calculates financial metrics for accurate retrieval.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CalculatedMetric:
    """A calculated financial metric."""
    name: str
    value: float
    unit: str
    formula: str
    source_metrics: List[str]
    time_period: Optional[str]
    confidence: float = 1.0


class FinancialCalculator:
    """
    Calculates financial metrics from raw data.
    All calculations are done upfront so the LLM can retrieve
    accurate values instead of attempting to calculate.
    """

    def calculate_all_metrics(
        self,
        financial_data: Dict[str, Dict[str, float]]
    ) -> List[CalculatedMetric]:
        """
        Calculate all possible financial metrics from the data.

        Args:
            financial_data: Dict of metric_type -> {period: value}
                Example: {'revenue': {'FY2023': 42.3, 'FY2024': 64.8}}

        Returns:
            List of calculated metrics
        """
        calculated = []

        calculated.extend(self._calculate_growth_rates(financial_data))
        calculated.extend(self._calculate_margins(financial_data))
        calculated.extend(self._calculate_cagr(financial_data))
        calculated.extend(self._calculate_ratios(financial_data))
        calculated.extend(self._calculate_differences(financial_data))

        logger.info(f"[FINANCIAL] Calculated {len(calculated)} derived metrics")
        return calculated

    def _calculate_growth_rates(
        self,
        data: Dict[str, Dict[str, float]]
    ) -> List[CalculatedMetric]:
        """Calculate year-over-year growth rates."""
        metrics = []

        for metric_type, values in data.items():
            if len(values) < 2:
                continue

            sorted_periods = sorted(values.keys())

            for i in range(1, len(sorted_periods)):
                prev_period = sorted_periods[i - 1]
                curr_period = sorted_periods[i]

                prev_value = values[prev_period]
                curr_value = values[curr_period]

                if prev_value and prev_value != 0:
                    growth_rate = ((curr_value - prev_value) / abs(prev_value)) * 100

                    metrics.append(CalculatedMetric(
                        name=f"{metric_type}_yoy_growth",
                        value=round(growth_rate, 2),
                        unit='%',
                        formula=f"({curr_value} - {prev_value}) / {prev_value} * 100",
                        source_metrics=[
                            f"{metric_type}_{prev_period}",
                            f"{metric_type}_{curr_period}"
                        ],
                        time_period=f"{prev_period} to {curr_period}"
                    ))

        return metrics

    def _calculate_margins(
        self,
        data: Dict[str, Dict[str, float]]
    ) -> List[CalculatedMetric]:
        """Calculate profit margins."""
        metrics = []
        revenue = data.get('revenue', {})

        if not revenue:
            return metrics

        gross_profit = data.get('gross_profit', {})
        for period in set(revenue.keys()) & set(gross_profit.keys()):
            if revenue[period] and revenue[period] != 0:
                margin = (gross_profit[period] / revenue[period]) * 100
                metrics.append(CalculatedMetric(
                    name='gross_margin',
                    value=round(margin, 2),
                    unit='%',
                    formula=f"gross_profit / revenue * 100",
                    source_metrics=[f"gross_profit_{period}", f"revenue_{period}"],
                    time_period=period
                ))

        net_income = data.get('net_income', {})
        for period in set(revenue.keys()) & set(net_income.keys()):
            if revenue[period] and revenue[period] != 0:
                margin = (net_income[period] / revenue[period]) * 100
                metrics.append(CalculatedMetric(
                    name='net_margin',
                    value=round(margin, 2),
                    unit='%',
                    formula=f"net_income / revenue * 100",
                    source_metrics=[f"net_income_{period}", f"revenue_{period}"],
                    time_period=period
                ))

        ebitda = data.get('ebitda', {})
        for period in set(revenue.keys()) & set(ebitda.keys()):
            if revenue[period] and revenue[period] != 0:
                margin = (ebitda[period] / revenue[period]) * 100
                metrics.append(CalculatedMetric(
                    name='operating_margin',
                    value=round(margin, 2),
                    unit='%',
                    formula=f"ebitda / revenue * 100",
                    source_metrics=[f"ebitda_{period}", f"revenue_{period}"],
                    time_period=period
                ))

        return metrics

    def _calculate_cagr(
        self,
        data: Dict[str, Dict[str, float]]
    ) -> List[CalculatedMetric]:
        """Calculate Compound Annual Growth Rate."""
        metrics = []

        for metric_type, values in data.items():
            if len(values) < 2:
                continue

            sorted_periods = sorted(values.keys())
            start_period = sorted_periods[0]
            end_period = sorted_periods[-1]

            start_value = values[start_period]
            end_value = values[end_period]

            n_periods = len(sorted_periods) - 1

            if start_value and start_value > 0 and n_periods > 0:
                cagr = ((end_value / start_value) ** (1 / n_periods) - 1) * 100

                metrics.append(CalculatedMetric(
                    name=f"{metric_type}_cagr",
                    value=round(cagr, 2),
                    unit='%',
                    formula=f"((end_value / start_value) ^ (1 / {n_periods}) - 1) * 100",
                    source_metrics=[
                        f"{metric_type}_{start_period}",
                        f"{metric_type}_{end_period}"
                    ],
                    time_period=f"{start_period} to {end_period}"
                ))

        return metrics

    def _calculate_ratios(
        self,
        data: Dict[str, Dict[str, float]]
    ) -> List[CalculatedMetric]:
        """Calculate financial ratios."""
        metrics = []

        assets = data.get('assets', {})
        liabilities = data.get('liabilities', {})
        for period in set(assets.keys()) & set(liabilities.keys()):
            if liabilities[period] and liabilities[period] != 0:
                ratio = assets[period] / liabilities[period]
                metrics.append(CalculatedMetric(
                    name='current_ratio',
                    value=round(ratio, 2),
                    unit='x',
                    formula='assets / liabilities',
                    source_metrics=[f"assets_{period}", f"liabilities_{period}"],
                    time_period=period
                ))

        equity = data.get('equity', {})
        for period in set(liabilities.keys()) & set(equity.keys()):
            if equity[period] and equity[period] != 0:
                ratio = liabilities[period] / equity[period]
                metrics.append(CalculatedMetric(
                    name='debt_to_equity',
                    value=round(ratio, 2),
                    unit='x',
                    formula='liabilities / equity',
                    source_metrics=[f"liabilities_{period}", f"equity_{period}"],
                    time_period=period
                ))

        return metrics

    def _calculate_differences(
        self,
        data: Dict[str, Dict[str, float]]
    ) -> List[CalculatedMetric]:
        """Calculate period-over-period differences."""
        metrics = []

        for metric_type, values in data.items():
            if len(values) < 2:
                continue

            sorted_periods = sorted(values.keys())

            for i in range(1, len(sorted_periods)):
                prev_period = sorted_periods[i - 1]
                curr_period = sorted_periods[i]

                prev_value = values[prev_period]
                curr_value = values[curr_period]

                diff = curr_value - prev_value

                metrics.append(CalculatedMetric(
                    name=f"{metric_type}_change",
                    value=round(diff, 2),
                    unit='$M' if abs(diff) > 1 else '$',
                    formula=f"{curr_value} - {prev_value}",
                    source_metrics=[
                        f"{metric_type}_{prev_period}",
                        f"{metric_type}_{curr_period}"
                    ],
                    time_period=f"{prev_period} to {curr_period}"
                ))

        return metrics


class FinancialMetricExtractor:
    """
    Extracts financial metrics as entities for the Knowledge Graph.
    """

    def __init__(self, calculator: Optional[FinancialCalculator] = None):
        self.calculator = calculator or FinancialCalculator()

    def extract_entities(
        self,
        financial_data: Dict[str, Dict[str, float]],
        source_document: str
    ) -> List[Dict[str, Any]]:
        """
        Convert financial data into entity format for Knowledge Graph.

        Returns list of entities ready for insertion.
        """
        entities = []

        for metric_type, values in financial_data.items():
            for period, value in values.items():
                entity = {
                    'entity_type': 'FINANCIAL_METRIC',
                    'canonical_name': f"{metric_type}_{period}",
                    'display_name': f"{metric_type.replace('_', ' ').title()} ({period})",
                    'attributes': {
                        'value': value,
                        'metric_type': metric_type,
                        'time_period': period,
                        'unit': self._infer_unit(metric_type, value),
                        'source_document': source_document,
                    },
                    'confidence': 1.0,
                }
                entities.append(entity)

        calculated = self.calculator.calculate_all_metrics(financial_data)
        for calc in calculated:
            entity = {
                'entity_type': 'CALCULATED_METRIC',
                'canonical_name': f"{calc.name}_{calc.time_period}".replace(' ', '_'),
                'display_name': f"{calc.name.replace('_', ' ').title()} ({calc.time_period})",
                'attributes': {
                    'value': calc.value,
                    'unit': calc.unit,
                    'formula': calc.formula,
                    'source_metrics': calc.source_metrics,
                    'time_period': calc.time_period,
                    'source_document': source_document,
                },
                'confidence': calc.confidence,
            }
            entities.append(entity)

        return entities

    def extract_relationships(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create relationships between financial entities.
        """
        relationships = []

        by_period = {}
        for entity in entities:
            period = entity.get('attributes', {}).get('time_period')
            if period:
                if period not in by_period:
                    by_period[period] = []
                by_period[period].append(entity)

        for entity in entities:
            if entity['entity_type'] == 'CALCULATED_METRIC':
                source_metrics = entity.get('attributes', {}).get('source_metrics', [])
                for source in source_metrics:
                    relationships.append({
                        'relation_type': 'CALCULATED_FROM',
                        'source_name': entity['canonical_name'],
                        'target_name': source,
                        'attributes': {
                            'formula': entity.get('attributes', {}).get('formula')
                        },
                    })

        return relationships

    def _infer_unit(self, metric_type: str, value: float) -> str:
        """Infer the unit for a metric type."""
        if metric_type in ['revenue', 'net_income', 'ebitda', 'gross_profit',
                          'expenses', 'assets', 'liabilities', 'equity', 'cash']:
            if abs(value) >= 1_000_000:
                return '$M'
            elif abs(value) >= 1_000:
                return '$K'
            else:
                return '$'
        elif metric_type in ['employees', 'customers']:
            return 'count'
        else:
            return ''
