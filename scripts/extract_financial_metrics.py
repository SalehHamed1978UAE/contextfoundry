#!/usr/bin/env python3
"""
Extract financial metrics from markdown tables in document chunks
and create FINANCIAL_METRIC + CALCULATED_METRIC entities.
"""

import re
import json
import logging
from uuid import uuid4
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VAULT_ID = "73beac38-9fdb-4d24-a68e-134b7a03aecd"

METRIC_PATTERNS = {
    'revenue': r'\*\*?Revenue\*?\*?\s*\|?\s*\$?([\d,.]+)\s*[Mm]?',
    'net_income': r'\*\*?Net\s+Income\*?\*?\s*\|?\s*\$?([\d,.]+)\s*[Mm]?',
    'gross_profit': r'\*\*?Gross\s+Profit\*?\*?\s*\|?\s*\$?([\d,.]+)\s*[Mm]?',
    'ebitda': r'\*\*?EBITDA\*?\*?\s*\|?\s*\$?([\d,.]+)\s*[Mm]?',
    'gross_margin': r'\*?Gross\s+Margin\*?\s*\|?\s*\*?([\d.]+)%',
    'net_margin': r'\*?Net\s+Income\s+Margin\*?\s*\|?\s*\*?([\d.]+)%',
    'ebitda_margin': r'\*?EBITDA\s+Margin\*?\s*\|?\s*\*?([\d.]+)%',
}

FISCAL_YEARS = ['FY2023', 'FY2024', 'FY2025', 'FY 2023', 'FY 2024', 'FY 2025']


def parse_table_row(text, metric_name, fy_pattern):
    """Extract metric values for each fiscal year from a table row."""
    values = {}
    row_pattern = rf'{metric_name}[^|]*\|([^|]+)\|([^|]+)\|([^|]+)'
    match = re.search(row_pattern, text, re.IGNORECASE)
    if match:
        for i, year in enumerate(['FY2023', 'FY2024', 'FY2025']):
            val_str = match.group(i + 1).strip()
            val_str = val_str.replace('$', '').replace(',', '').replace('M', '').replace('*', '').strip()
            try:
                values[year] = float(val_str)
            except ValueError:
                pass
    return values


def extract_from_financial_table(text):
    """Extract structured financial data from markdown table."""
    metrics = {}
    
    table_pattern = r'\|\s*Metric\s*\|.*?\n\|[-\s|]+\n((?:\|[^\n]+\n)+)'
    table_match = re.search(table_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if table_match:
        table_content = table_match.group(0)
        
        metric_rows = [
            ('revenue', r'\*\*Revenue\*\*'),
            ('net_income', r'\*\*Net Income\*\*'),
            ('gross_profit', r'\*\*Gross Profit\*\*'),
            ('ebitda', r'\*\*EBITDA\*\*'),
            ('gross_margin', r'\*Gross Margin\*'),
            ('net_margin', r'\*Net Income Margin\*'),
            ('ebitda_margin', r'\*EBITDA Margin\*'),
            ('cogs', r'Cost of Goods'),
            ('rd_expense', r'Research & Development'),
            ('sm_expense', r'Sales & Marketing'),
            ('ga_expense', r'General & Administrative'),
        ]
        
        for metric_key, row_pattern in metric_rows:
            row_match = re.search(rf'{row_pattern}[^|]*\|([^|]+)\|([^|]+)\|([^|]+)\|', table_content, re.IGNORECASE)
            if row_match:
                metrics[metric_key] = {}
                for i, year in enumerate(['FY2023', 'FY2024', 'FY2025']):
                    val_str = row_match.group(i + 1).strip()
                    val_str = re.sub(r'[*$%,MKx]', '', val_str).strip()
                    try:
                        metrics[metric_key][year] = float(val_str)
                    except ValueError:
                        pass
    
    return metrics


def calculate_derived_metrics(base_metrics):
    """Calculate growth rates, differences, and other derived metrics."""
    derived = []
    
    years = ['FY2023', 'FY2024', 'FY2025']
    
    for metric_name, values in base_metrics.items():
        for i in range(1, len(years)):
            prev_year = years[i-1]
            curr_year = years[i]
            
            if prev_year in values and curr_year in values:
                prev_val = values[prev_year]
                curr_val = values[curr_year]
                
                if prev_val and prev_val != 0:
                    growth_pct = ((curr_val - prev_val) / prev_val) * 100
                    derived.append({
                        'name': f'{metric_name}_yoy_growth_{prev_year}_to_{curr_year}',
                        'metric_type': metric_name,
                        'value': round(growth_pct, 1),
                        'unit': '%',
                        'time_period': f'{prev_year} to {curr_year}',
                        'formula': f'({curr_val} - {prev_val}) / {prev_val} * 100',
                        'calculation_type': 'yoy_growth'
                    })
                
                difference = curr_val - prev_val
                unit = '$M' if metric_name in ['revenue', 'net_income', 'gross_profit', 'ebitda'] else '%'
                derived.append({
                    'name': f'{metric_name}_change_{prev_year}_to_{curr_year}',
                    'metric_type': metric_name,
                    'value': round(difference, 2),
                    'unit': unit,
                    'time_period': f'{prev_year} to {curr_year}',
                    'formula': f'{curr_val} - {prev_val}',
                    'calculation_type': 'change'
                })
        
        if 'FY2023' in values and 'FY2025' in values:
            start_val = values['FY2023']
            end_val = values['FY2025']
            if start_val and start_val != 0:
                total_growth = ((end_val - start_val) / start_val) * 100
                derived.append({
                    'name': f'{metric_name}_total_growth_FY2023_to_FY2025',
                    'metric_type': metric_name,
                    'value': round(total_growth, 1),
                    'unit': '%',
                    'time_period': 'FY2023 to FY2025',
                    'formula': f'({end_val} - {start_val}) / {start_val} * 100',
                    'calculation_type': 'total_growth'
                })
                
                total_change = end_val - start_val
                unit = '$M' if metric_name in ['revenue', 'net_income', 'gross_profit', 'ebitda'] else '%'
                derived.append({
                    'name': f'{metric_name}_total_change_FY2023_to_FY2025',
                    'metric_type': metric_name,
                    'value': round(total_change, 2),
                    'unit': unit,
                    'time_period': 'FY2023 to FY2025',
                    'formula': f'{end_val} - {start_val}',
                    'calculation_type': 'absolute_change'
                })
    
    return derived


def run_extraction():
    """Main extraction function."""
    import sys
    sys.path.insert(0, '.')
    
    from src.context_foundry.models.database import get_session
    from src.context_foundry.models.schema import Entity
    from sqlalchemy import text
    
    session = get_session()
    
    try:
        result = session.execute(text("""
            SELECT id, text FROM document_chunks 
            WHERE tenant_id = :tenant_id
            AND (text ILIKE '%| Metric |%' OR text ILIKE '%FY 2023%' OR text ILIKE '%Revenue%')
        """), {'tenant_id': VAULT_ID})
        chunks = result.fetchall()
        logger.info(f"Found {len(chunks)} chunks with potential financial data")
        
        all_metrics = {}
        for chunk_id, text_content in chunks:
            extracted = extract_from_financial_table(text_content)
            for metric_name, values in extracted.items():
                if metric_name not in all_metrics:
                    all_metrics[metric_name] = {}
                all_metrics[metric_name].update(values)
        
        logger.info(f"Extracted base metrics: {json.dumps(all_metrics, indent=2)}")
        
        base_entities = []
        for metric_name, values in all_metrics.items():
            for year, value in values.items():
                unit = '$M' if metric_name in ['revenue', 'net_income', 'gross_profit', 'ebitda', 'cogs', 'rd_expense', 'sm_expense', 'ga_expense'] else '%'
                base_entities.append({
                    'name': f'{metric_name}_{year}',
                    'entity_type': 'FINANCIAL_METRIC',
                    'properties': {
                        'metric_type': metric_name,
                        'value': value,
                        'unit': unit,
                        'time_period': year,
                        'source_document': 'financials_2025.md'
                    }
                })
        
        derived = calculate_derived_metrics(all_metrics)
        
        logger.info(f"Creating {len(base_entities)} FINANCIAL_METRIC entities")
        logger.info(f"Creating {len(derived)} CALCULATED_METRIC entities")
        
        session.execute(text("""
            DELETE FROM entities 
            WHERE tenant_id = :tenant_id 
            AND entity_type IN ('FINANCIAL_METRIC', 'CALCULATED_METRIC')
        """), {'tenant_id': VAULT_ID})
        
        for entity_data in base_entities:
            entity = Entity(
                id=uuid4(),
                tenant_id=VAULT_ID,
                name=entity_data['name'],
                entity_type=entity_data['entity_type'],
                properties=entity_data['properties'],
                confidence=0.95,
                lifecycle_stage='TRUSTED',
                created_at=datetime.utcnow()
            )
            session.add(entity)
        
        for calc_data in derived:
            entity = Entity(
                id=uuid4(),
                tenant_id=VAULT_ID,
                name=calc_data['name'],
                entity_type='CALCULATED_METRIC',
                properties={
                    'metric_type': calc_data['metric_type'],
                    'value': calc_data['value'],
                    'unit': calc_data['unit'],
                    'time_period': calc_data['time_period'],
                    'formula': calc_data['formula'],
                    'calculation_type': calc_data['calculation_type']
                },
                confidence=0.95,
                lifecycle_stage='TRUSTED',
                created_at=datetime.utcnow()
            )
            session.add(entity)
        
        session.commit()
        logger.info(f"Successfully created {len(base_entities)} FINANCIAL_METRIC and {len(derived)} CALCULATED_METRIC entities")
        
        return len(base_entities), len(derived)
        
    except Exception as e:
        session.rollback()
        logger.error(f"Extraction failed: {e}")
        raise
    finally:
        session.close()


if __name__ == '__main__':
    run_extraction()
