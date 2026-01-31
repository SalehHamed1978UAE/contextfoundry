# Spreadsheet & Financial Data Integration Spec
**Date:** 2026-01-17
**Status:** Ready for Implementation

---

## Executive Summary

Add native support for spreadsheets (Excel, CSV) and structured financial data to Context Foundry. This enables:
- Direct upload of financial reports, budgets, income statements
- Automatic extraction of financial metrics as entities
- Pre-calculated ratios, growth rates, margins stored in Knowledge Graph
- Accurate answers to financial questions without LLM calculation errors

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DOCUMENT UPLOAD                                       │
│                                                                              │
│   Excel/CSV/PDF ──► File Type Detection ──► Route to Appropriate Loader    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
            ┌───────────┐  ┌───────────┐  ┌───────────┐
            │ Text Docs │  │Spreadsheet│  │ PDF Tables│
            │ (existing)│  │  Loader   │  │  Loader   │
            └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                  │              │              │
                  │              ▼              │
                  │    ┌─────────────────┐     │
                  │    │ Table Extractor │     │
                  │    │                 │     │
                  │    │ - Cell parsing  │     │
                  │    │ - Header detect │     │
                  │    │ - Type inference│     │
                  │    └────────┬────────┘     │
                  │             │              │
                  │             ▼              │
                  │    ┌─────────────────┐     │
                  │    │   Financial     │     │
                  │    │   Calculator    │     │
                  │    │                 │     │
                  │    │ - Growth rates  │     │
                  │    │ - Margins       │     │
                  │    │ - Ratios        │     │
                  │    │ - CAGR          │     │
                  │    └────────┬────────┘     │
                  │             │              │
                  └──────────┬──┴──────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │  Entity Extractor   │
                  │                     │
                  │ - Financial metrics │
                  │ - Time periods      │
                  │ - Companies/orgs    │
                  │ - Relationships     │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   Knowledge Graph   │
                  │                     │
                  │ Entities:           │
                  │ - FINANCIAL_METRIC  │
                  │ - TIME_PERIOD       │
                  │ - CALCULATION       │
                  │                     │
                  │ Relationships:      │
                  │ - METRIC_FOR_PERIOD │
                  │ - CALCULATED_FROM   │
                  │ - YEAR_OVER_YEAR    │
                  └─────────────────────┘
```

---

## Dependencies

```bash
# Core dependencies
pip install unstructured[all-docs]  # Document parsing (tables, Excel, PDF)
pip install pandas                   # Data manipulation
pip install openpyxl                 # Excel file support
pip install xlrd                     # Legacy Excel support (.xls)
pip install camelot-py[cv]          # PDF table extraction (optional)
pip install tabulate                 # Table formatting
```

**requirements.txt additions:**
```
unstructured[all-docs]>=0.10.0
pandas>=2.0.0
openpyxl>=3.1.0
xlrd>=2.0.0
tabulate>=0.9.0
```

---

## Component 1: Spreadsheet Loader

**File:** `src/context_foundry/extraction/spreadsheet_loader.py`

```python
"""
Spreadsheet Loader - Handles Excel, CSV, and tabular data extraction.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from uuid import UUID
import pandas as pd
import numpy as np

from unstructured.partition.auto import partition
from unstructured.partition.xlsx import partition_xlsx
from unstructured.partition.csv import partition_csv
from unstructured.documents.elements import Table, Title, NarrativeText

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    """Represents an extracted table from a spreadsheet."""
    name: str                           # Sheet name or table title
    dataframe: pd.DataFrame             # Parsed data
    markdown: str                       # Markdown representation
    metadata: Dict[str, Any] = field(default_factory=dict)
    financial_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpreadsheetDocument:
    """Represents a parsed spreadsheet document."""
    filename: str
    tables: List[ExtractedTable]
    raw_text: str                       # All text content
    metadata: Dict[str, Any]


class SpreadsheetLoader:
    """
    Loads and parses spreadsheet files (Excel, CSV) into structured data.
    """

    # Financial column name patterns (case-insensitive)
    FINANCIAL_PATTERNS = {
        'revenue': ['revenue', 'sales', 'total revenue', 'net revenue', 'gross revenue'],
        'net_income': ['net income', 'net profit', 'net loss', 'net earnings', 'bottom line'],
        'ebitda': ['ebitda', 'operating income', 'operating profit', 'operating loss'],
        'gross_profit': ['gross profit', 'gross margin', 'gross income'],
        'expenses': ['expenses', 'opex', 'operating expenses', 'total expenses', 'costs'],
        'assets': ['assets', 'total assets', 'current assets'],
        'liabilities': ['liabilities', 'total liabilities', 'current liabilities'],
        'equity': ['equity', "shareholders' equity", 'stockholders equity', 'net worth'],
        'cash': ['cash', 'cash and equivalents', 'cash position', 'ending cash'],
        'employees': ['employees', 'headcount', 'fte', 'staff count'],
        'customers': ['customers', 'customer count', 'active customers', 'total customers'],
    }

    # Time period patterns
    TIME_PATTERNS = {
        'fiscal_year': r'FY\s*(\d{4}|\d{2})',
        'quarter': r'Q([1-4])\s*(\d{4}|\d{2})?',
        'year': r'20\d{2}',
        'month': r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*\d{4}',
    }

    def __init__(self):
        self._column_type_cache: Dict[str, str] = {}

    def load(self, file_path: str) -> SpreadsheetDocument:
        """
        Load a spreadsheet file and extract all tables.

        Args:
            file_path: Path to Excel or CSV file

        Returns:
            SpreadsheetDocument with extracted tables and metadata
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        logger.info(f"Loading spreadsheet: {path.name}")

        if extension in ['.xlsx', '.xls']:
            return self._load_excel(file_path)
        elif extension == '.csv':
            return self._load_csv(file_path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")

    def _load_excel(self, file_path: str) -> SpreadsheetDocument:
        """Load an Excel file with multiple sheets."""
        tables = []
        all_text = []

        # Get sheet names
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names

        for sheet_name in sheet_names:
            try:
                # Read sheet with pandas for structured data
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)

                # Skip empty sheets
                if df.empty:
                    continue

                # Clean the dataframe
                df = self._clean_dataframe(df)

                # Convert to markdown
                markdown = self._dataframe_to_markdown(df, sheet_name)

                # Detect and extract financial metrics
                financial_metrics = self._extract_financial_metrics(df, sheet_name)

                # Detect time periods in data
                time_context = self._detect_time_periods(df)

                table = ExtractedTable(
                    name=sheet_name,
                    dataframe=df,
                    markdown=markdown,
                    metadata={
                        'sheet_name': sheet_name,
                        'row_count': len(df),
                        'column_count': len(df.columns),
                        'columns': list(df.columns),
                        'time_context': time_context,
                        'has_financial_data': bool(financial_metrics),
                    },
                    financial_metrics=financial_metrics
                )
                tables.append(table)
                all_text.append(markdown)

                logger.info(f"  Sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns")
                if financial_metrics:
                    logger.info(f"    Financial metrics detected: {list(financial_metrics.keys())}")

            except Exception as e:
                logger.warning(f"Failed to parse sheet '{sheet_name}': {e}")

        return SpreadsheetDocument(
            filename=Path(file_path).name,
            tables=tables,
            raw_text="\n\n".join(all_text),
            metadata={
                'file_type': 'excel',
                'sheet_count': len(tables),
                'total_rows': sum(t.metadata.get('row_count', 0) for t in tables),
            }
        )

    def _load_csv(self, file_path: str) -> SpreadsheetDocument:
        """Load a CSV file."""
        df = pd.read_csv(file_path)
        df = self._clean_dataframe(df)

        filename = Path(file_path).stem
        markdown = self._dataframe_to_markdown(df, filename)
        financial_metrics = self._extract_financial_metrics(df, filename)
        time_context = self._detect_time_periods(df)

        table = ExtractedTable(
            name=filename,
            dataframe=df,
            markdown=markdown,
            metadata={
                'row_count': len(df),
                'column_count': len(df.columns),
                'columns': list(df.columns),
                'time_context': time_context,
                'has_financial_data': bool(financial_metrics),
            },
            financial_metrics=financial_metrics
        )

        return SpreadsheetDocument(
            filename=Path(file_path).name,
            tables=[table],
            raw_text=markdown,
            metadata={
                'file_type': 'csv',
                'sheet_count': 1,
                'total_rows': len(df),
            }
        )

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize a dataframe."""
        # Remove completely empty rows and columns
        df = df.dropna(how='all').dropna(axis=1, how='all')

        # Strip whitespace from string columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()

        # Replace common null representations
        df = df.replace(['nan', 'NaN', 'N/A', 'n/a', '-', ''], np.nan)

        # Try to infer better dtypes
        df = df.infer_objects()

        return df

    def _dataframe_to_markdown(self, df: pd.DataFrame, title: str) -> str:
        """Convert dataframe to markdown table format."""
        from tabulate import tabulate

        # Limit very large tables
        max_rows = 100
        if len(df) > max_rows:
            df_display = df.head(max_rows)
            truncated = f"\n\n*Table truncated. Showing {max_rows} of {len(df)} rows.*"
        else:
            df_display = df
            truncated = ""

        # Convert to markdown
        md_table = tabulate(df_display, headers='keys', tablefmt='pipe', showindex=False)

        return f"## {title}\n\n{md_table}{truncated}"

    def _detect_time_periods(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """Detect time periods mentioned in the dataframe."""
        import re

        time_context = {
            'fiscal_years': [],
            'quarters': [],
            'years': [],
        }

        # Check column names
        for col in df.columns:
            col_str = str(col)

            # Fiscal year pattern
            fy_match = re.search(r'FY\s*(\d{4}|\d{2})', col_str, re.IGNORECASE)
            if fy_match:
                year = fy_match.group(1)
                if len(year) == 2:
                    year = '20' + year
                time_context['fiscal_years'].append(f"FY{year}")

            # Quarter pattern
            q_match = re.search(r'Q([1-4])\s*(\d{4})?', col_str, re.IGNORECASE)
            if q_match:
                quarter = q_match.group(1)
                year = q_match.group(2) or ''
                time_context['quarters'].append(f"Q{quarter} {year}".strip())

            # Plain year
            year_match = re.search(r'\b(20\d{2})\b', col_str)
            if year_match:
                time_context['years'].append(year_match.group(1))

        # Deduplicate
        for key in time_context:
            time_context[key] = list(set(time_context[key]))

        return time_context

    def _classify_column(self, column_name: str) -> Optional[str]:
        """Classify a column as a financial metric type."""
        col_lower = column_name.lower().strip()

        for metric_type, patterns in self.FINANCIAL_PATTERNS.items():
            for pattern in patterns:
                if pattern in col_lower:
                    return metric_type

        return None

    def _extract_financial_metrics(
        self,
        df: pd.DataFrame,
        sheet_name: str
    ) -> Dict[str, Any]:
        """
        Extract financial metrics from the dataframe.

        Returns structured financial data with:
        - Raw values by time period
        - Calculated growth rates
        - Calculated margins/ratios
        """
        metrics = {}

        # Identify financial columns
        financial_columns = {}
        for col in df.columns:
            col_type = self._classify_column(str(col))
            if col_type:
                financial_columns[col] = col_type

        if not financial_columns:
            return metrics

        # Extract metrics by type
        for col, metric_type in financial_columns.items():
            if metric_type not in metrics:
                metrics[metric_type] = {}

            # Get the column data
            col_data = df[col]

            # Try to get time periods from index or first column
            time_labels = self._get_time_labels(df)

            if time_labels:
                # Map values to time periods
                for i, (period, value) in enumerate(zip(time_labels, col_data)):
                    if pd.notna(value):
                        try:
                            metrics[metric_type][str(period)] = float(value)
                        except (ValueError, TypeError):
                            pass
            else:
                # Just store as list
                values = col_data.dropna().tolist()
                if values:
                    metrics[metric_type]['values'] = values

        return metrics

    def _get_time_labels(self, df: pd.DataFrame) -> List[str]:
        """Extract time period labels from the dataframe."""
        import re

        # Check if first column looks like time periods
        if len(df.columns) > 0:
            first_col = df.iloc[:, 0].astype(str)
            time_labels = []

            for val in first_col:
                # Check for year patterns
                if re.search(r'(FY\s*)?\d{4}|Q[1-4]', str(val), re.IGNORECASE):
                    time_labels.append(val)

            if len(time_labels) == len(first_col):
                return time_labels

        # Check column names for time periods
        time_cols = []
        for col in df.columns[1:]:  # Skip first column (usually metric names)
            col_str = str(col)
            if re.search(r'(FY\s*)?\d{4}|Q[1-4]', col_str, re.IGNORECASE):
                time_cols.append(col_str)

        if time_cols:
            return time_cols

        return []
```

---

## Component 2: Financial Calculator

**File:** `src/context_foundry/extraction/financial_calculator.py`

```python
"""
Financial Calculator - Pre-calculates financial metrics for accurate retrieval.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CalculatedMetric:
    """A calculated financial metric."""
    name: str
    value: float
    unit: str                    # '%', '$', 'x', 'days', etc.
    formula: str                 # How it was calculated
    source_metrics: List[str]   # What values were used
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

        # Growth rates
        calculated.extend(self._calculate_growth_rates(financial_data))

        # Margins
        calculated.extend(self._calculate_margins(financial_data))

        # CAGR
        calculated.extend(self._calculate_cagr(financial_data))

        # Ratios
        calculated.extend(self._calculate_ratios(financial_data))

        # Differences
        calculated.extend(self._calculate_differences(financial_data))

        logger.info(f"Calculated {len(calculated)} financial metrics")
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

            # Sort periods
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

        # Gross margin
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

        # Net margin
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

        # Operating margin (EBITDA margin)
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

            # Calculate number of years
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

        # Current ratio (assets / liabilities)
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

        # Debt-to-equity
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

        # 1. Raw financial values as entities
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
                    'confidence': 1.0,  # Direct extraction, high confidence
                }
                entities.append(entity)

        # 2. Calculated metrics as entities
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

        # Group entities by time period
        by_period = {}
        for entity in entities:
            period = entity.get('attributes', {}).get('time_period')
            if period:
                if period not in by_period:
                    by_period[period] = []
                by_period[period].append(entity)

        # Create SAME_PERIOD relationships
        for period, period_entities in by_period.items():
            for i, e1 in enumerate(period_entities):
                for e2 in period_entities[i + 1:]:
                    relationships.append({
                        'relation_type': 'SAME_PERIOD',
                        'source_name': e1['canonical_name'],
                        'target_name': e2['canonical_name'],
                        'attributes': {'period': period},
                    })

        # Create CALCULATED_FROM relationships
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
```

---

## Component 3: Integration with Document Pipeline

**File:** `src/context_foundry/extraction/document_processor.py` (modifications)

```python
"""
Modifications to integrate spreadsheet support into the document pipeline.
"""

from pathlib import Path
from typing import List, Optional
from uuid import UUID

from .spreadsheet_loader import SpreadsheetLoader, SpreadsheetDocument
from .financial_calculator import FinancialCalculator, FinancialMetricExtractor


class DocumentProcessor:
    """Enhanced document processor with spreadsheet support."""

    SPREADSHEET_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
    PDF_EXTENSIONS = {'.pdf'}
    TEXT_EXTENSIONS = {'.txt', '.md', '.doc', '.docx'}

    def __init__(self, session, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self.spreadsheet_loader = SpreadsheetLoader()
        self.financial_extractor = FinancialMetricExtractor()

    def process_document(self, file_path: str) -> ProcessedDocument:
        """
        Process a document based on its type.
        """
        extension = Path(file_path).suffix.lower()

        if extension in self.SPREADSHEET_EXTENSIONS:
            return self._process_spreadsheet(file_path)
        elif extension in self.PDF_EXTENSIONS:
            return self._process_pdf(file_path)
        else:
            return self._process_text(file_path)

    def _process_spreadsheet(self, file_path: str) -> ProcessedDocument:
        """
        Process a spreadsheet file.

        1. Load and parse with SpreadsheetLoader
        2. Extract financial metrics
        3. Pre-calculate derived metrics
        4. Create entities and relationships
        5. Create text chunks for semantic search
        """
        # Load spreadsheet
        spreadsheet = self.spreadsheet_loader.load(file_path)

        all_entities = []
        all_relationships = []
        all_chunks = []

        for table in spreadsheet.tables:
            # Extract financial metrics as entities
            if table.financial_metrics:
                entities = self.financial_extractor.extract_entities(
                    table.financial_metrics,
                    source_document=spreadsheet.filename
                )
                all_entities.extend(entities)

                relationships = self.financial_extractor.extract_relationships(entities)
                all_relationships.extend(relationships)

            # Create text chunk from markdown for semantic search
            chunk = DocumentChunk(
                content=table.markdown,
                metadata={
                    'source': spreadsheet.filename,
                    'sheet': table.name,
                    'type': 'table',
                    'has_financial_data': table.metadata.get('has_financial_data', False),
                    'time_context': table.metadata.get('time_context', {}),
                }
            )
            all_chunks.append(chunk)

        return ProcessedDocument(
            filename=spreadsheet.filename,
            chunks=all_chunks,
            entities=all_entities,
            relationships=all_relationships,
            metadata=spreadsheet.metadata
        )
```

---

## Component 4: New Entity Types

**File:** Database migration for new entity types

```sql
-- Migration: Add financial entity types

-- Add new entity types to ontology
INSERT INTO ontology.entity_types (name, display_name, description, base_type)
VALUES
    ('FINANCIAL_METRIC', 'Financial Metric', 'A financial value from a document (revenue, profit, etc.)', 'METRIC'),
    ('CALCULATED_METRIC', 'Calculated Metric', 'A derived financial metric (growth rate, margin, etc.)', 'METRIC'),
    ('TIME_PERIOD', 'Time Period', 'A fiscal year, quarter, or date range', 'TEMPORAL')
ON CONFLICT (name) DO NOTHING;

-- Add new relationship types
INSERT INTO ontology.relationship_types (name, display_name, description)
VALUES
    ('SAME_PERIOD', 'Same Period', 'Both metrics are for the same time period'),
    ('CALCULATED_FROM', 'Calculated From', 'This metric was calculated from source metrics'),
    ('METRIC_FOR_PERIOD', 'Metric For Period', 'Links a metric to its time period'),
    ('YEAR_OVER_YEAR', 'Year Over Year', 'Compares same metric across consecutive years')
ON CONFLICT (name) DO NOTHING;
```

---

## Component 5: Query Enhancement for Financial Data

**File:** `src/context_foundry/agents/financial_query_handler.py`

```python
"""
Financial Query Handler - Specialized handling for financial questions.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class FinancialQueryHandler:
    """
    Handles financial queries by preferring pre-calculated metrics
    over LLM calculations.
    """

    # Patterns that indicate a financial query
    FINANCIAL_QUERY_PATTERNS = [
        r'what\s+(?:was|is|were)\s+(?:the\s+)?(?:total\s+)?revenue',
        r'what\s+(?:was|is|were)\s+(?:the\s+)?(?:net\s+)?income',
        r'what\s+(?:was|is|were)\s+(?:the\s+)?(?:gross\s+)?(?:profit|margin)',
        r'what\s+(?:was|is|were)\s+(?:the\s+)?ebitda',
        r'growth\s+rate',
        r'year[- ]over[- ]year',
        r'cagr',
        r'margin',
        r'how\s+much\s+(?:did|does|was)',
        r'what\s+percentage',
    ]

    def __init__(self, session, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.FINANCIAL_QUERY_PATTERNS]

    def is_financial_query(self, query: str) -> bool:
        """Check if query is asking for financial data."""
        return any(p.search(query) for p in self._patterns)

    def extract_query_parameters(self, query: str) -> Dict[str, Any]:
        """
        Extract parameters from a financial query.

        Returns:
            Dict with metric_type, time_period, comparison_type, etc.
        """
        params = {}

        query_lower = query.lower()

        # Detect metric type
        if any(x in query_lower for x in ['revenue', 'sales']):
            params['metric_type'] = 'revenue'
        elif 'net income' in query_lower or 'net loss' in query_lower:
            params['metric_type'] = 'net_income'
        elif 'ebitda' in query_lower or 'operating' in query_lower:
            params['metric_type'] = 'ebitda'
        elif 'gross' in query_lower:
            params['metric_type'] = 'gross_profit'
        elif 'margin' in query_lower:
            params['is_ratio'] = True
            if 'gross' in query_lower:
                params['metric_type'] = 'gross_margin'
            elif 'net' in query_lower:
                params['metric_type'] = 'net_margin'
            elif 'operating' in query_lower:
                params['metric_type'] = 'operating_margin'

        # Detect time period
        fy_match = re.search(r'FY\s*(\d{4}|\d{2})', query, re.IGNORECASE)
        if fy_match:
            year = fy_match.group(1)
            if len(year) == 2:
                year = '20' + year
            params['time_period'] = f"FY{year}"

        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match and 'time_period' not in params:
            params['time_period'] = f"FY{year_match.group(1)}"

        # Detect if asking for growth/change
        if any(x in query_lower for x in ['growth', 'change', 'increase', 'decrease']):
            params['is_growth'] = True

        # Detect if asking for CAGR
        if 'cagr' in query_lower or 'compound' in query_lower:
            params['is_cagr'] = True

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

        # Filter by metric type
        if 'metric_type' in params:
            conditions.append("attributes->>'metric_type' = :metric_type")
            bind_params['metric_type'] = params['metric_type']

        # Filter by time period
        if 'time_period' in params:
            conditions.append("attributes->>'time_period' LIKE :time_period")
            bind_params['time_period'] = f"%{params['time_period']}%"

        # Filter by entity type
        if params.get('is_growth') or params.get('is_cagr'):
            conditions.append("entity_type = 'CALCULATED_METRIC'")
        else:
            conditions.append("entity_type IN ('FINANCIAL_METRIC', 'CALCULATED_METRIC')")

        query = f"""
            SELECT name, entity_type, attributes
            FROM public.entities
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE WHEN entity_type = 'FINANCIAL_METRIC' THEN 0 ELSE 1 END,
                confidence DESC
            LIMIT 10
        """

        result = self.session.execute(text(query), bind_params)
        return [dict(row) for row in result.fetchall()]

    def format_financial_answer(
        self,
        metrics: List[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> str:
        """
        Format financial metrics into a natural language answer.
        """
        if not metrics:
            return None

        metric = metrics[0]  # Best match
        attrs = metric.get('attributes', {})

        value = attrs.get('value')
        unit = attrs.get('unit', '')
        period = attrs.get('time_period', '')
        formula = attrs.get('formula')

        # Format the value
        if unit == '%':
            formatted_value = f"{value}%"
        elif unit in ['$M', '$K', '$']:
            formatted_value = f"${value:,.1f} million" if unit == '$M' else f"${value:,.0f}"
        else:
            formatted_value = str(value)

        # Build the answer
        metric_name = params.get('metric_type', 'metric').replace('_', ' ')

        if period:
            answer = f"The {metric_name} for {period} was {formatted_value}."
        else:
            answer = f"The {metric_name} was {formatted_value}."

        # Add calculation context if it's a derived metric
        if formula and metric.get('entity_type') == 'CALCULATED_METRIC':
            answer += f" (Calculated using: {formula})"

        return answer
```

---

## Usage Example

```python
# In web_app.py or document upload handler

from context_foundry.extraction.document_processor import DocumentProcessor

@app.route('/api/v1/documents/upload', methods=['POST'])
def upload_document():
    file = request.files['file']
    tenant_id = g.tenant_id

    # Save file
    file_path = save_uploaded_file(file)

    # Process document (handles spreadsheets automatically)
    processor = DocumentProcessor(session, tenant_id)
    result = processor.process_document(file_path)

    # result.entities includes:
    # - FINANCIAL_METRIC entities (raw values)
    # - CALCULATED_METRIC entities (growth rates, margins, etc.)

    # result.chunks includes:
    # - Markdown tables for semantic search

    # Store in Knowledge Graph
    store_entities(result.entities)
    store_relationships(result.relationships)
    store_chunks(result.chunks)

    return jsonify({
        'success': True,
        'entities_extracted': len(result.entities),
        'metrics_calculated': len([e for e in result.entities if e['entity_type'] == 'CALCULATED_METRIC']),
    })
```

---

## Testing

```python
# test_spreadsheet_integration.py

def test_excel_loading():
    loader = SpreadsheetLoader()
    doc = loader.load("test_data/financial_statements.xlsx")

    assert len(doc.tables) > 0
    assert doc.tables[0].financial_metrics

def test_financial_calculations():
    calculator = FinancialCalculator()

    data = {
        'revenue': {'FY2023': 42.3, 'FY2024': 64.8, 'FY2025': 87.5},
        'net_income': {'FY2023': -13.2, 'FY2024': -12.4, 'FY2025': -9.5},
    }

    metrics = calculator.calculate_all_metrics(data)

    # Check growth rates calculated
    growth_metrics = [m for m in metrics if 'growth' in m.name]
    assert len(growth_metrics) >= 2

    # Check CAGR calculated
    cagr_metrics = [m for m in metrics if 'cagr' in m.name]
    assert len(cagr_metrics) >= 1

def test_financial_query():
    handler = FinancialQueryHandler(session, tenant_id)

    assert handler.is_financial_query("What was the revenue in FY 2024?")
    assert handler.is_financial_query("What is the YoY growth rate?")

    params = handler.extract_query_parameters("What was the net income in FY 2024?")
    assert params['metric_type'] == 'net_income'
    assert params['time_period'] == 'FY2024'
```

---

## Summary

| Component | Purpose |
|-----------|---------|
| `SpreadsheetLoader` | Parse Excel/CSV files, extract tables |
| `FinancialCalculator` | Pre-calculate growth rates, margins, CAGR |
| `FinancialMetricExtractor` | Convert metrics to KG entities |
| `FinancialQueryHandler` | Route financial queries to pre-calculated data |

**Key Benefits:**
1. **Accuracy:** Pre-calculated metrics eliminate LLM calculation errors
2. **Speed:** Direct retrieval faster than LLM reasoning
3. **Auditability:** Formula stored with each calculated metric
4. **Temporal awareness:** Metrics tagged with time periods
