"""
Targeted extraction for specific failure patterns.

Creates specialized prompts for each failure category.
"""

import json
import logging
import os
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


TARGETED_PROMPTS = {
    "PERSON_RESPONSIBILITIES": """
Your ONLY task is to extract RESPONSIBILITIES for people mentioned in this document.

For each person, extract:
- name: Full name
- title: Job title (CEO, CFO, CTO, COO, etc.)
- responsibilities: Their key duties, what they are accountable for

Look for phrases like:
- "responsible for..."
- "oversees..."
- "accountable for..."
- "leads..."
- "manages..."
- "in charge of..."
- "handles..."

Return JSON:
{
    "people": [
        {
            "name": "Person Name",
            "title": "Their Title",
            "responsibilities": ["responsibility 1", "responsibility 2"],
            "evidence": "quote from document"
        }
    ]
}

Only include responsibilities explicitly stated in the document.
""",

    "PROJECT_OWNERSHIP": """
Your ONLY task is to extract OWNERSHIP relationships between PROJECTS and BUSINESS UNITS.

For each project/program mentioned, identify which business unit OWNS it.

Look for phrases like:
- "[Project] is led by [BU]"
- "[Project] is part of [BU]"
- "[BU] owns/manages/runs [Project]"
- "[Project] under [BU] division"
- "[BU]'s [Project]"

Business units are divisions like:
- Orion Aerospace
- Orion Energy Solutions
- Orion Logistics
- Orion SmartCity

Return JSON:
{
    "ownership": [
        {
            "project": "Project Name",
            "business_unit": "Business Unit Name",
            "relationship_type": "OWNS",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated ownership relationships.
""",

    "BU_FOCUS_AREAS": """
Your ONLY task is to extract FOCUS AREAS for each business unit.

For each business unit mentioned, identify what they specialize in.

Look for phrases like:
- "[BU] focuses on..."
- "[BU] specializes in..."
- "[BU] products include..."
- "[BU] handles..."
- "[BU] develops..."
- "[BU] is responsible for..."

Return JSON:
{
    "focus_areas": [
        {
            "business_unit": "BU Name",
            "focus_areas": ["area 1", "area 2", "area 3"],
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated focus areas.
""",

    "CUSTOMER_RELATIONSHIPS": """
Your ONLY task is to extract CUSTOMER relationships.

Identify organizations that are CUSTOMERS of the company.

A customer is an organization that:
- Purchases products or services
- Has a contract or agreement
- Is described as client, buyer, or customer

Return JSON:
{
    "customers": [
        {
            "customer_name": "Organization Name",
            "customer_type": "ORGANIZATION",
            "supplier": "Manus Orion Group or specific business unit",
            "product_or_service": "what they buy (if mentioned)",
            "contract_value": "value if mentioned",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated customer relationships.
""",

    "PROJECT_BUDGETS": """
Your ONLY task is to extract BUDGET information for projects.

For each project, extract budget/funding amounts.

Look for:
- Total budget
- Annual budget
- Funding allocation
- Investment amount
- Cost projections

Return JSON:
{
    "budgets": [
        {
            "project": "Project Name",
            "budget": "$XXM",
            "budget_type": "total|annual|phase",
            "fiscal_year": "FYXX if mentioned",
            "source_document_type": "strategic_plan|status_update|financial_statement",
            "evidence": "quote from document"
        }
    ]
}

Preserve exact figures as stated. Note the document type for authority ranking.
""",

    "SUPPLIER_RELATIONSHIPS": """
Your ONLY task is to extract SUPPLIER relationships.

Identify organizations that are SUPPLIERS to the company.

A supplier is an organization that:
- Provides components, materials, or services
- Is described as vendor, supplier, or partner
- Has a supply contract

Return JSON:
{
    "suppliers": [
        {
            "supplier_name": "Organization Name",
            "supplier_type": "ORGANIZATION",
            "customer": "Manus Orion Group or specific project/business unit",
            "what_they_supply": "components, materials, services",
            "risk_level": "low|medium|high|critical if mentioned",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated supplier relationships.
""",

    "PARTNER_RELATIONSHIPS": """
Your ONLY task is to extract PARTNER relationships.

Identify organizations that are PARTNERS with the company.

A partner is an organization that:
- Has a partnership agreement
- Collaborates on projects or initiatives
- Is described as partner, ally, or collaborator

Return JSON:
{
    "partners": [
        {
            "partner_name": "Organization Name",
            "partner_type": "ORGANIZATION",
            "partnership_type": "strategic|technology|joint_venture|distribution",
            "scope": "what the partnership covers",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated partner relationships.
""",

    "PROJECT_INFO": """
Your ONLY task is to extract detailed PROJECT information.

For each project mentioned, extract:
- Project name
- Status (active, planned, completed)
- Timeline/milestones
- Key people involved
- Business unit owner
- Budget if mentioned
- Key objectives

Return JSON:
{
    "projects": [
        {
            "name": "Project Name",
            "status": "active|planned|completed",
            "start_date": "date if mentioned",
            "end_date": "date if mentioned",
            "business_unit": "owning BU",
            "project_lead": "person name if mentioned",
            "objectives": ["objective 1", "objective 2"],
            "budget": "amount if mentioned",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated project information.
""",

    "PERSON_INFO": """
Your ONLY task is to extract detailed PERSON information.

For each person mentioned, extract:
- Full name
- Title/role
- Department/team
- Reports to (manager)
- Direct reports (if mentioned)
- Key responsibilities
- Background/experience

Return JSON:
{
    "people": [
        {
            "name": "Full Name",
            "title": "Job Title",
            "department": "Department/Team/Business Unit",
            "reports_to": "Manager name if mentioned",
            "direct_reports": ["name1", "name2"] if mentioned,
            "responsibilities": ["resp1", "resp2"],
            "background": "experience/background if mentioned",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated information.
"""
}


class TargetedExtractor:
    """
    Runs targeted extraction for specific failure patterns.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        from openai import OpenAI
        api_key = self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=api_key)
        
        self.model = self.config.get("model", "gpt-4o")
        self.temperature = self.config.get("temperature", 0)
        self.max_tokens = self.config.get("max_tokens", 4000)

    def extract_for_category(self, category: str, documents: List[Dict]) -> List[Dict]:
        """
        Run targeted extraction for a specific failure category.

        Args:
            category: One of the TARGETED_PROMPTS keys
            documents: List of {"path": str, "text": str}

        Returns:
            List of extracted facts
        """
        if category not in TARGETED_PROMPTS:
            logger.warning(f"No targeted prompt for category: {category}")
            return []

        prompt_template = TARGETED_PROMPTS[category]
        results = []

        for doc in documents:
            doc_path = doc.get("path", "unknown")
            doc_text = doc.get("text", "")
            
            if not doc_text:
                continue

            logger.info(f"Targeted extraction ({category}) from {doc_path}")

            prompt = f"{prompt_template}\n\nDocument:\n{doc_text[:15000]}"

            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)
                result["_source_document"] = doc_path
                result["_category"] = category
                results.append(result)

                logger.info(f"Extracted {len(result)} items from {doc_path}")

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from {doc_path}: {e}")
            except Exception as e:
                logger.error(f"Extraction failed for {doc_path}: {e}")

        return results

    def extract_all_categories(self, documents: List[Dict], categories: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """
        Run targeted extraction for multiple categories.

        Args:
            documents: List of {"path": str, "text": str}
            categories: List of category names, or None for all

        Returns:
            Dict mapping category to list of extracted facts
        """
        if categories is None:
            categories = list(TARGETED_PROMPTS.keys())

        results = {}
        for category in categories:
            logger.info(f"Running extraction for category: {category}")
            results[category] = self.extract_for_category(category, documents)

        return results

    def save_extractions(self, results: Dict[str, List[Dict]], output_dir: str):
        """Save extraction results to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for category, extractions in results.items():
            file_path = output_path / f"{category.lower()}_extractions.json"
            with open(file_path, 'w') as f:
                json.dump({
                    "category": category,
                    "count": len(extractions),
                    "extractions": extractions
                }, f, indent=2)
            logger.info(f"Saved {len(extractions)} extractions to {file_path}")

    @staticmethod
    def load_corpus_documents(corpus_dir: str) -> List[Dict]:
        """Load all documents from a corpus directory."""
        documents = []
        corpus_path = Path(corpus_dir)

        if not corpus_path.exists():
            logger.warning(f"Corpus directory not found: {corpus_dir}")
            return documents

        for file_path in corpus_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".md", ".txt"]:
                try:
                    documents.append({
                        "path": str(file_path),
                        "text": file_path.read_text()
                    })
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {e}")

        logger.info(f"Loaded {len(documents)} documents from {corpus_dir}")
        return documents
