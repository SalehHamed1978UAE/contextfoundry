"""
Spreadsheet Loader - Handles Excel, CSV, and tabular data extraction.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    """Represents an extracted table from a spreadsheet."""
    name: str
    dataframe: pd.DataFrame
    markdown: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    financial_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpreadsheetDocument:
    """Represents a parsed spreadsheet document."""
    filename: str
    tables: List[ExtractedTable]
    raw_text: str
    metadata: Dict[str, Any]


class SpreadsheetLoader:
    """
    Loads and parses spreadsheet files (Excel, CSV) into structured data.
    """

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

    TIME_PATTERNS = {
        'fiscal_year': r'FY\s*(\d{4}|\d{2})',
        'quarter': r'Q([1-4])\s*(\d{4}|\d{2})?',
        'year': r'20\d{2}',
        'month': r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*\d{4}',
    }

    def __init__(self):
        self._column_type_cache: Dict[str, str] = {}

    def load(self, file_path: str) -> SpreadsheetDocument:
        """Load a spreadsheet file and extract all tables."""
        path = Path(file_path)
        extension = path.suffix.lower()

        logger.info(f"[SPREADSHEET] Loading: {path.name}")

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

        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names

        for sheet_name in sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)

                if df.empty:
                    continue

                df = self._clean_dataframe(df)
                markdown = self._dataframe_to_markdown(df, sheet_name)
                financial_metrics = self._extract_financial_metrics(df, sheet_name)
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

                logger.info(f"  Sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} cols")
                if financial_metrics:
                    logger.info(f"    Financial metrics: {list(financial_metrics.keys())}")

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
        df = df.dropna(how='all').dropna(axis=1, how='all')

        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()

        df = df.replace(['nan', 'NaN', 'N/A', 'n/a', '-', ''], np.nan)
        df = df.infer_objects()

        return df

    def _dataframe_to_markdown(self, df: pd.DataFrame, title: str) -> str:
        """Convert dataframe to markdown table format."""
        from tabulate import tabulate

        max_rows = 100
        if len(df) > max_rows:
            df_display = df.head(max_rows)
            truncated = f"\n\n*Table truncated. Showing {max_rows} of {len(df)} rows.*"
        else:
            df_display = df
            truncated = ""

        md_table = tabulate(df_display, headers='keys', tablefmt='pipe', showindex=False)

        return f"## {title}\n\n{md_table}{truncated}"

    def _detect_time_periods(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """Detect time periods mentioned in the dataframe."""
        time_context = {
            'fiscal_years': [],
            'quarters': [],
            'years': [],
        }

        for col in df.columns:
            col_str = str(col)

            fy_match = re.search(r'FY\s*(\d{4}|\d{2})', col_str, re.IGNORECASE)
            if fy_match:
                year = fy_match.group(1)
                if len(year) == 2:
                    year = '20' + year
                time_context['fiscal_years'].append(f"FY{year}")

            q_match = re.search(r'Q([1-4])\s*(\d{4})?', col_str, re.IGNORECASE)
            if q_match:
                quarter = q_match.group(1)
                year = q_match.group(2) or ''
                time_context['quarters'].append(f"Q{quarter} {year}".strip())

            year_match = re.search(r'\b(20\d{2})\b', col_str)
            if year_match:
                time_context['years'].append(year_match.group(1))

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
        """Extract financial metrics from the dataframe."""
        metrics = {}

        first_col = df.columns[0] if len(df.columns) > 0 else None
        first_col_is_labels = False
        
        if first_col:
            first_col_values = df[first_col].astype(str).tolist()
            for val in first_col_values:
                if self._classify_column(val):
                    first_col_is_labels = True
                    break

        if first_col_is_labels:
            time_cols = [str(c) for c in df.columns[1:]]
            
            for idx, row in df.iterrows():
                metric_label = str(row[first_col])
                metric_type = self._classify_column(metric_label)
                
                if metric_type:
                    if metric_type not in metrics:
                        metrics[metric_type] = {}
                    
                    for col in df.columns[1:]:
                        period = self._normalize_period(str(col))
                        value = row[col]
                        
                        if pd.notna(value):
                            try:
                                metrics[metric_type][period] = float(value)
                            except (ValueError, TypeError):
                                pass
        else:
            for col in df.columns:
                col_type = self._classify_column(str(col))
                if col_type:
                    if col_type not in metrics:
                        metrics[col_type] = {}
                    
                    time_labels = self._get_time_labels(df)
                    col_data = df[col]
                    
                    if time_labels and len(time_labels) == len(col_data):
                        for period, value in zip(time_labels, col_data):
                            if pd.notna(value):
                                try:
                                    metrics[col_type][str(period)] = float(value)
                                except (ValueError, TypeError):
                                    pass
                    else:
                        values = col_data.dropna().tolist()
                        if values:
                            for i, v in enumerate(values):
                                try:
                                    metrics[col_type][f"row_{i}"] = float(v)
                                except (ValueError, TypeError):
                                    pass

        return metrics

    def _normalize_period(self, period_str: str) -> str:
        """Normalize a period string to a consistent format."""
        fy_match = re.search(r'FY\s*(\d{4}|\d{2})', period_str, re.IGNORECASE)
        if fy_match:
            year = fy_match.group(1)
            if len(year) == 2:
                year = '20' + year
            return f"FY{year}"
        
        year_match = re.search(r'\b(20\d{2})\b', period_str)
        if year_match:
            return f"FY{year_match.group(1)}"
        
        return period_str

    def _get_time_labels(self, df: pd.DataFrame) -> List[str]:
        """Extract time period labels from the dataframe."""
        if len(df.columns) > 0:
            first_col = df.iloc[:, 0].astype(str)
            time_labels = []

            for val in first_col:
                if re.search(r'(FY\s*)?\d{4}|Q[1-4]', str(val), re.IGNORECASE):
                    time_labels.append(val)

            if len(time_labels) == len(first_col):
                return time_labels

        time_cols = []
        for col in df.columns[1:]:
            col_str = str(col)
            if re.search(r'(FY\s*)?\d{4}|Q[1-4]', col_str, re.IGNORECASE):
                time_cols.append(col_str)

        if time_cols:
            return time_cols

        return []
