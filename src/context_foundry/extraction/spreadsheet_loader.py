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
    Supports row-level entity extraction for employee directories, sales pipelines, etc.
    """

    # Spreadsheet type detection patterns
    SPREADSHEET_TYPE_PATTERNS = {
        'EMPLOYEE_DIRECTORY': {
            'required': ['name'],
            'indicators': [
                'employee', 'staff', 'team member', 'personnel',
                'department', 'title', 'role', 'position',
                'hire date', 'start date', 'manager', 'reports to',
                'email', 'phone', 'extension', 'location', 'office'
            ],
            'entity_type': 'PERSON',
            'min_matches': 2
        },
        'SALES_PIPELINE': {
            'required': ['company', 'account', 'deal', 'opportunity'],
            'indicators': [
                'deal', 'opportunity', 'account', 'company', 'client',
                'value', 'amount', 'revenue', 'arr', 'tcv',
                'stage', 'status', 'probability', 'close date',
                'owner', 'rep', 'sales rep', 'account executive'
            ],
            'entity_type': 'DEAL',
            'min_matches': 3
        },
        'CUSTOMER_LIST': {
            'required': ['customer', 'client', 'account'],
            'indicators': [
                'customer', 'client', 'account name',
                'contract', 'arr', 'mrr', 'revenue', 'value',
                'start date', 'renewal', 'expiration',
                'tier', 'plan', 'subscription', 'status'
            ],
            'entity_type': 'CUSTOMER',
            'min_matches': 2
        },
        'EXPENSE_REPORT': {
            'required': ['amount', 'expense', 'cost'],
            'indicators': [
                'expense', 'cost', 'amount', 'total',
                'category', 'type', 'description',
                'date', 'submitted', 'approved',
                'employee', 'submitted by', 'vendor', 'merchant'
            ],
            'entity_type': 'EXPENSE',
            'min_matches': 3
        },
        'VENDOR_LIST': {
            'required': ['vendor', 'supplier', 'provider'],
            'indicators': [
                'vendor', 'supplier', 'provider', 'partner',
                'contract', 'annual cost', 'spend',
                'category', 'service', 'product',
                'contact', 'renewal', 'start date'
            ],
            'entity_type': 'VENDOR',
            'min_matches': 2
        },
        'PROJECT_LIST': {
            'required': ['project', 'initiative'],
            'indicators': [
                'project', 'initiative', 'program',
                'status', 'phase', 'milestone',
                'owner', 'lead', 'manager',
                'start date', 'end date', 'deadline', 'due date',
                'budget', 'cost', 'resources'
            ],
            'entity_type': 'PROJECT',
            'min_matches': 2
        }
    }

    # Standard property mappings for each entity type
    PROPERTY_MAPPINGS = {
        'PERSON': {
            'name': 'name',
            'employee name': 'name',
            'full name': 'name',
            'first name': 'first_name',
            'first_name': 'first_name',
            'firstname': 'first_name',
            'last name': 'last_name',
            'last_name': 'last_name',
            'lastname': 'last_name',
            'department': 'department',
            'dept': 'department',
            'title': 'title',
            'job title': 'title',
            'role': 'title',
            'position': 'title',
            'manager': 'manager',
            'reports to': 'manager',
            'supervisor': 'manager',
            'hire date': 'hire_date',
            'start date': 'start_date',
            'email': 'email',
            'phone': 'phone',
            'extension': 'phone_ext',
            'location': 'location',
            'office': 'office',
            'salary': 'salary',
            'employee id': 'employee_id',
            'id': 'employee_id',
        },
        'DEAL': {
            'company': 'company',
            'account': 'company',
            'account name': 'company',
            'client': 'company',
            'deal name': 'deal_name',
            'opportunity': 'deal_name',
            'value': 'value',
            'deal value': 'value',
            'amount': 'value',
            'arr': 'arr',
            'tcv': 'tcv',
            'stage': 'stage',
            'status': 'status',
            'probability': 'probability',
            'close date': 'close_date',
            'expected close': 'close_date',
            'owner': 'owner',
            'sales rep': 'owner',
            'account executive': 'owner',
            'rep': 'owner',
            'notes': 'notes',
            'next steps': 'next_steps',
        },
        'CUSTOMER': {
            'customer': 'name',
            'customer name': 'name',
            'client': 'name',
            'account': 'name',
            'company': 'name',
            'arr': 'arr',
            'mrr': 'mrr',
            'contract value': 'contract_value',
            'revenue': 'revenue',
            'start date': 'start_date',
            'contract start': 'start_date',
            'renewal date': 'renewal_date',
            'expiration': 'renewal_date',
            'tier': 'tier',
            'plan': 'plan',
            'subscription': 'subscription_type',
            'status': 'status',
            'industry': 'industry',
            'contact': 'primary_contact',
        },
        'EXPENSE': {
            'description': 'description',
            'expense': 'description',
            'item': 'description',
            'amount': 'amount',
            'total': 'amount',
            'cost': 'amount',
            'category': 'category',
            'type': 'category',
            'date': 'date',
            'expense date': 'date',
            'submitted': 'submitted_date',
            'employee': 'employee',
            'submitted by': 'employee',
            'vendor': 'vendor',
            'merchant': 'vendor',
            'approved': 'approved',
            'status': 'status',
            'receipt': 'has_receipt',
        },
        'VENDOR': {
            'vendor': 'name',
            'vendor name': 'name',
            'supplier': 'name',
            'provider': 'name',
            'company': 'name',
            'category': 'category',
            'service': 'service_type',
            'product': 'product',
            'annual cost': 'annual_cost',
            'spend': 'annual_spend',
            'contract value': 'contract_value',
            'contact': 'contact',
            'renewal date': 'renewal_date',
            'start date': 'start_date',
            'status': 'status',
        },
        'PROJECT': {
            'project': 'name',
            'project name': 'name',
            'initiative': 'name',
            'description': 'description',
            'status': 'status',
            'phase': 'phase',
            'owner': 'owner',
            'lead': 'owner',
            'project manager': 'owner',
            'start date': 'start_date',
            'end date': 'end_date',
            'deadline': 'deadline',
            'due date': 'deadline',
            'budget': 'budget',
            'department': 'department',
            'team': 'team',
        }
    }

    # Relationship patterns based on entity type
    # Format: (source_prop, rel_type, target_type, target_prop, optional_subtype)
    # Use ORGANIZATIONAL_UNIT as generic type with subtype property to avoid hardcoding
    # entity types for every organizational structure variation (department, team, office, etc.)
    RELATIONSHIP_PATTERNS = {
        'PERSON': [
            ('department', 'WORKS_IN', 'ORGANIZATIONAL_UNIT', 'name', 'department'),
            ('manager', 'REPORTS_TO', 'PERSON', 'name', None),
            ('location', 'LOCATED_IN', 'ORGANIZATIONAL_UNIT', 'name', 'location'),
            ('office', 'WORKS_AT', 'ORGANIZATIONAL_UNIT', 'name', 'office'),
            ('team', 'MEMBER_OF', 'ORGANIZATIONAL_UNIT', 'name', 'team'),
            ('division', 'WORKS_IN', 'ORGANIZATIONAL_UNIT', 'name', 'division'),
            ('region', 'LOCATED_IN', 'ORGANIZATIONAL_UNIT', 'name', 'region'),
            ('cost_center', 'BELONGS_TO', 'ORGANIZATIONAL_UNIT', 'name', 'cost_center'),
        ],
        'DEAL': [
            ('owner', 'OWNED_BY', 'PERSON', 'name', None),
            ('company', 'WITH_COMPANY', 'CUSTOMER', 'name', None),
        ],
        'EXPENSE': [
            ('employee', 'SUBMITTED_BY', 'PERSON', 'name', None),
            ('vendor', 'PAID_TO', 'VENDOR', 'name', None),
            ('category', 'CATEGORIZED_AS', 'ORGANIZATIONAL_UNIT', 'name', 'expense_category'),
        ],
        'PROJECT': [
            ('owner', 'OWNED_BY', 'PERSON', 'name', None),
            ('department', 'BELONGS_TO', 'ORGANIZATIONAL_UNIT', 'name', 'department'),
            ('team', 'BELONGS_TO', 'ORGANIZATIONAL_UNIT', 'name', 'team'),
        ],
    }

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

    def load(self, file_path: str, original_filename: str = None) -> SpreadsheetDocument:
        """Load a spreadsheet file and extract all tables.
        
        Args:
            file_path: Path to the file on disk
            original_filename: Original filename with extension (used when file_path has no extension)
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        # If no extension on file_path, use original_filename to determine type
        if not extension and original_filename:
            extension = Path(original_filename).suffix.lower()

        logger.info(f"[SPREADSHEET] Loading: {original_filename or path.name} (extension: {extension})")

        # Use original filename for context (year extraction, etc.)
        context_name = original_filename or path.name
        
        if extension in ['.xlsx', '.xls']:
            return self._load_excel(file_path, context_name)
        elif extension == '.csv':
            return self._load_csv(file_path, context_name)
        else:
            raise ValueError(f"Unsupported file type: {extension}")

    def _load_excel(self, file_path: str, context_name: str = None) -> SpreadsheetDocument:
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
                # Use context_name (original filename) for year context, fallback to sheet_name
                extraction_context = context_name or sheet_name
                financial_metrics = self._extract_financial_metrics(df, extraction_context)
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

    def _load_csv(self, file_path: str, context_name: str = None) -> SpreadsheetDocument:
        """Load a CSV file."""
        df = pd.read_csv(file_path)
        df = self._clean_dataframe(df)

        filename = Path(file_path).stem
        extraction_context = context_name or filename
        markdown = self._dataframe_to_markdown(df, filename)
        financial_metrics = self._extract_financial_metrics(df, extraction_context)
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
        
        # Extract year context from sheet name for month-based data
        year_context = self._extract_year_from_context(sheet_name)

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
                    
                    # If no time labels found, try to use first column as months with year context
                    if not time_labels and len(df.columns) > 0:
                        first_col_vals = df.iloc[:, 0].astype(str).tolist()
                        month_labels = []
                        for val in first_col_vals:
                            month_period = self._normalize_month_to_period(val, year_context)
                            if month_period != val:  # It was recognized as a month
                                month_labels.append(month_period)
                        if len(month_labels) == len(first_col_vals):
                            time_labels = month_labels
                    
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
    
    def _extract_year_from_context(self, context_str: str) -> Optional[str]:
        """Extract year from a context string (filename, sheet name)."""
        year_match = re.search(r'(20\d{2})', str(context_str))
        if year_match:
            return year_match.group(1)
        return None

    def _normalize_period(self, period_str: str) -> str:
        """Normalize a period string to a consistent format."""
        period_str = str(period_str).strip()
        
        # Handle FY patterns: "FY 2023", "FY2023", "FY23"
        fy_match = re.search(r'FY\s*(\d{4}|\d{2})', period_str, re.IGNORECASE)
        if fy_match:
            year = fy_match.group(1)
            if len(year) == 2:
                year = '20' + year
            return f"FY{year}"
        
        # Handle quarter patterns: "Q4_2025", "Q4 2025", "Q4-2025", "Q42025"
        q_match = re.search(r'Q([1-4])[\s_\-]*(20\d{2})', period_str, re.IGNORECASE)
        if q_match:
            quarter = q_match.group(1)
            year = q_match.group(2)
            return f"Q{quarter}_{year}"
        
        # Handle standalone year: "2023", "2024"
        year_match = re.search(r'^(20\d{2})$', period_str)
        if year_match:
            return f"FY{year_match.group(1)}"
        
        # Handle year in longer string
        year_match = re.search(r'\b(20\d{2})\b', period_str)
        if year_match:
            return f"FY{year_match.group(1)}"
        
        return period_str
    
    def _normalize_month_to_period(self, month_str: str, year_context: str = None) -> str:
        """Convert month name to a standardized period format."""
        month_map = {
            'january': 'Jan', 'february': 'Feb', 'march': 'Mar', 'april': 'Apr',
            'may': 'May', 'june': 'Jun', 'july': 'Jul', 'august': 'Aug',
            'september': 'Sep', 'october': 'Oct', 'november': 'Nov', 'december': 'Dec',
            'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
            'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug', 'sep': 'Sep',
            'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
        }
        month_lower = str(month_str).lower().strip()
        if month_lower in month_map:
            month = month_map[month_lower]
            if year_context:
                return f"{month}_{year_context}"
            return month
        return str(month_str)

    def _get_time_labels(self, df: pd.DataFrame, year_context: str = None) -> List[str]:
        """Extract time period labels from the dataframe."""
        # Pattern to match time periods: FY2023, Q4_2025, 2023
        # Note: months are handled separately in _extract_financial_metrics
        time_pattern = re.compile(
            r'(FY\s*\d{2,4})|'  # FY2023, FY 23
            r'(Q[1-4][\s_\-]?\d{4})|'  # Q4_2025, Q4 2025
            r'(\b20\d{2}\b)',  # 2023
            re.IGNORECASE
        )
        
        # Check first column for time labels
        if len(df.columns) > 0:
            first_col = df.iloc[:, 0].astype(str)
            time_labels = []
            for val in first_col:
                if time_pattern.search(str(val)):
                    time_labels.append(self._normalize_period(val))
            if len(time_labels) == len(first_col):
                return time_labels
        
        # Check column headers (skip first which might be a label column)
        time_cols = []
        for col in df.columns[1:]:
            col_str = str(col)
            if time_pattern.search(col_str):
                time_cols.append(self._normalize_period(col_str))
        if time_cols:
            return time_cols
        
        # Also check all columns (for row-based data)
        all_time_cols = []
        for col in df.columns:
            col_str = str(col)
            if time_pattern.search(col_str):
                all_time_cols.append(self._normalize_period(col_str))
        if all_time_cols:
            return all_time_cols
        
        return []

    # ========== ROW-LEVEL ENTITY EXTRACTION METHODS ==========

    def detect_spreadsheet_type(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Detect what type of data this spreadsheet contains based on column headers.
        
        Returns:
            Dict with 'type', 'entity_type', 'matched_columns', 'confidence' or None if unknown
        """
        columns_lower = [str(c).lower().strip() for c in df.columns]

        best_match = None
        best_score = 0

        for sheet_type, config in self.SPREADSHEET_TYPE_PATTERNS.items():
            # Check for required columns
            has_required = any(
                any(req in col for col in columns_lower)
                for req in config['required']
            )

            if not has_required:
                continue

            # Count indicator matches
            matches = 0
            matched_columns = {}

            for col in columns_lower:
                for indicator in config['indicators']:
                    if indicator in col:
                        matches += 1
                        matched_columns[col] = indicator
                        break

            if matches >= config['min_matches'] and matches > best_score:
                best_score = matches
                best_match = {
                    'type': sheet_type,
                    'entity_type': config['entity_type'],
                    'matched_columns': matched_columns,
                    'confidence': min(1.0, matches / len(config['indicators']))
                }

        return best_match

    def map_columns_to_properties(
        self, 
        df: pd.DataFrame, 
        entity_type: str
    ) -> Dict[str, str]:
        """
        Map spreadsheet columns to entity properties.
        
        Returns:
            Dict mapping column_name -> property_name
        """
        mapping = {}
        property_patterns = self.PROPERTY_MAPPINGS.get(entity_type, {})

        for col in df.columns:
            col_lower = str(col).lower().strip()

            # Try exact match first
            if col_lower in property_patterns:
                mapping[col] = property_patterns[col_lower]
                continue

            # Try partial match
            for pattern, prop_name in property_patterns.items():
                if pattern in col_lower or col_lower in pattern:
                    mapping[col] = prop_name
                    break

            # If no match, use cleaned column name as property
            if col not in mapping:
                # Convert "Employee Name" -> "employee_name"
                clean_name = re.sub(r'[^\w\s]', '', col_lower)
                clean_name = re.sub(r'\s+', '_', clean_name)
                mapping[col] = clean_name

        return mapping

    def extract_row_entities(
        self,
        df: pd.DataFrame,
        sheet_type: Dict[str, Any],
        source_document: str
    ) -> List[Dict[str, Any]]:
        """
        Extract individual entities from each row of the spreadsheet.
        
        Returns:
            List of entity dicts ready for Knowledge Graph insertion
        """
        entities = []
        entity_type = sheet_type['entity_type']
        column_mapping = self.map_columns_to_properties(df, entity_type)

        # Find the name/identifier columns
        name_props = ['name', 'employee_name', 'company', 'customer', 'deal_name', 'project']
        name_column = None
        first_name_column = None
        last_name_column = None
        
        for col, prop in column_mapping.items():
            if prop in name_props:
                name_column = col
            elif prop == 'first_name':
                first_name_column = col
            elif prop == 'last_name':
                last_name_column = col

        for idx, row in df.iterrows():
            # Skip empty rows
            if row.isna().all():
                continue

            # Build entity attributes from row
            attributes = {}
            for col, prop in column_mapping.items():
                value = row[col]
                if pd.notna(value):
                    # Clean and convert value
                    if isinstance(value, (int, float)):
                        # Convert numpy types to Python native
                        if hasattr(value, 'item'):
                            attributes[prop] = value.item()
                        else:
                            attributes[prop] = value
                    else:
                        str_val = str(value).strip()
                        if str_val and str_val.lower() != 'nan':
                            attributes[prop] = str_val

            # Get entity name - try multiple strategies
            entity_name = None
            
            # Strategy 1: Combine first_name + last_name if both exist
            if first_name_column and last_name_column:
                first_name = row[first_name_column] if pd.notna(row[first_name_column]) else None
                last_name = row[last_name_column] if pd.notna(row[last_name_column]) else None
                if first_name and last_name:
                    entity_name = f"{str(first_name).strip()} {str(last_name).strip()}"
                elif first_name:
                    entity_name = str(first_name).strip()
                elif last_name:
                    entity_name = str(last_name).strip()
            
            # Strategy 2: Use first_name + name column (last name) 
            if not entity_name and first_name_column and name_column:
                first_name = row[first_name_column] if pd.notna(row[first_name_column]) else None
                name_val = row[name_column] if pd.notna(row[name_column]) else None
                if first_name and name_val:
                    entity_name = f"{str(first_name).strip()} {str(name_val).strip()}"
            
            # Strategy 3: Use name column if it looks like a full name
            if not entity_name and name_column and pd.notna(row[name_column]):
                name_val = str(row[name_column]).strip()
                # Check if attributes have a 'name' property with last name
                if 'name' in attributes and attributes['name'] != name_val:
                    # name column has first name, 'name' attribute has last name
                    entity_name = f"{name_val} {attributes['name']}"
                else:
                    entity_name = name_val
            
            # Strategy 4: Fallback to generic name
            if not entity_name:
                entity_name = f"{entity_type}_{idx}"

            # Skip if name is invalid
            if not entity_name or entity_name.lower() == 'nan':
                continue

            # Create canonical name (lowercase, underscores)
            canonical_name = re.sub(r'[^\w\s]', '', entity_name.lower())
            canonical_name = re.sub(r'\s+', '_', canonical_name)

            entity = {
                'entity_type': entity_type,
                'canonical_name': canonical_name,
                'display_name': entity_name,
                'attributes': {
                    **attributes,
                    '_source_document': source_document,
                    '_source_row': idx + 1,  # 1-indexed for user display
                },
                'confidence': 0.95,  # High confidence for structured data
            }

            entities.append(entity)

        return entities

    def extract_relationships(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract relationships between entities based on their properties.
        
        Returns:
            List of relationship dicts ready for Knowledge Graph insertion
        """
        relationships = []

        # Build lookup of entities by type and name
        entity_lookup = {}
        for entity in entities:
            etype = entity['entity_type']
            name = entity['display_name'].lower()
            if etype not in entity_lookup:
                entity_lookup[etype] = {}
            entity_lookup[etype][name] = entity['canonical_name']

        for entity in entities:
            entity_type = entity['entity_type']
            patterns = self.RELATIONSHIP_PATTERNS.get(entity_type, [])

            for pattern in patterns:
                # Pattern format: (source_prop, rel_type, target_type, target_prop, optional_subtype)
                source_prop = pattern[0]
                rel_type = pattern[1]
                target_type = pattern[2]
                target_prop = pattern[3]
                target_subtype = pattern[4] if len(pattern) > 4 else None
                
                # Get the property value that references another entity
                prop_value = entity.get('attributes', {}).get(source_prop)

                if not prop_value:
                    continue

                prop_value_lower = str(prop_value).lower().strip()
                if not prop_value_lower or prop_value_lower == 'nan':
                    continue

                # Try to find the target entity
                target_canonical = None

                # Check if target exists in our extracted entities
                if target_type in entity_lookup:
                    target_canonical = entity_lookup[target_type].get(prop_value_lower)

                # If not found but it's a valid reference, create implicit entity
                if not target_canonical and prop_value_lower:
                    target_canonical = re.sub(r'[^\w\s]', '', prop_value_lower)
                    target_canonical = re.sub(r'\s+', '_', target_canonical)

                if target_canonical:
                    # Build relationship attributes
                    rel_attributes = {
                        'source_property': source_prop,
                        'inferred': target_type not in entity_lookup,
                    }
                    
                    # Add subtype for ORGANIZATIONAL_UNIT targets (Option B implementation)
                    if target_subtype:
                        rel_attributes['target_subtype'] = target_subtype
                    
                    relationship = {
                        'relation_type': rel_type,
                        'source_name': entity['canonical_name'],
                        'source_type': entity_type,
                        'target_name': target_canonical,
                        'target_type': target_type,
                        'target_display_name': str(prop_value).strip(),
                        'attributes': rel_attributes,
                        'confidence': 0.9 if target_type in entity_lookup else 0.7,
                    }
                    
                    # If target is ORGANIZATIONAL_UNIT, add subtype as target property
                    if target_type == 'ORGANIZATIONAL_UNIT' and target_subtype:
                        relationship['target_properties'] = {
                            'subtype': target_subtype,
                        }
                    
                    relationships.append(relationship)

        return relationships

    def extract_all_row_entities(
        self,
        tables: List[ExtractedTable],
        source_filename: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract row-level entities and relationships from all tables in a spreadsheet.
        
        Returns:
            Tuple of (entities, relationships)
        """
        all_entities = []
        all_relationships = []

        for table in tables:
            # Detect spreadsheet type
            sheet_type = self.detect_spreadsheet_type(table.dataframe)

            if sheet_type:
                logger.info(f"  [RowExtract] Detected {sheet_type['type']} ({sheet_type['entity_type']}) in '{table.name}'")

                # Extract entities from rows
                entities = self.extract_row_entities(
                    table.dataframe,
                    sheet_type,
                    source_filename
                )
                all_entities.extend(entities)

                # Extract relationships
                relationships = self.extract_relationships(entities)
                all_relationships.extend(relationships)

                # Store in table metadata
                table.metadata['sheet_type'] = sheet_type['type']
                table.metadata['entity_type'] = sheet_type['entity_type']
                table.metadata['entity_count'] = len(entities)
                table.metadata['relationship_count'] = len(relationships)

                logger.info(f"    Extracted {len(entities)} entities, {len(relationships)} relationships")

        return all_entities, all_relationships
