"""
Document Type Classifier for Context Foundry.

Classifies documents into specific types (resume, contract, incident_report, etc.)
to enable document-type-specific ontology selection.
"""
import os
from typing import Optional
from openai import OpenAI

from ..utils.logger import logger


DOCUMENT_TYPES = [
    "resume",
    "legal_contract", 
    "architecture_doc",
    "financial_report",
    "research_paper",
    "meeting_notes",
    "org_chart",
    "policy_document",
    "technical_spec",
    "incident_report",
    "runbook",
    "invoice",
    "email",
    "it_infrastructure",
    "project_plan",
    "sop",  # standard operating procedure
    "audit_report",
    "healthcare_record",
    "training_material",
]


def classify_document(text: str, max_chars: int = 5000) -> str:
    """
    Classify document type for ontology selection.
    
    Args:
        text: Document text content
        max_chars: Maximum characters to analyze (for efficiency)
        
    Returns:
        Document type label (lowercase, underscored)
    """
    sample = text[:max_chars] if len(text) > max_chars else text
    
    client = OpenAI(
        api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    )
    
    prompt = f"""Analyze this document and classify its type.

Return a single lowercase label from this list if it matches:
{', '.join(DOCUMENT_TYPES)}

If it doesn't match any of these types, create a descriptive lowercase label 
using underscores (e.g., supplier_agreement, employee_handbook).

Return ONLY the label, nothing else.

DOCUMENT:
{sample}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0
        )
        
        doc_type = response.choices[0].message.content.strip().lower().replace(" ", "_")
        logger.info(f"[DocumentClassifier] Classified as: {doc_type}")
        return doc_type
        
    except Exception as e:
        logger.error(f"[DocumentClassifier] Classification failed: {e}")
        return "unknown"


def get_document_type_from_filename(filename: str) -> Optional[str]:
    """
    Infer document type from filename patterns.
    
    Args:
        filename: Original filename
        
    Returns:
        Inferred document type or None
    """
    filename_lower = filename.lower()
    
    patterns = {
        "resume": ["resume", "cv", "curriculum"],
        "incident_report": ["incident", "postmortem", "outage"],
        "runbook": ["runbook", "playbook", "procedure"],
        "architecture_doc": ["architecture", "design", "system_design"],
        "meeting_notes": ["meeting", "minutes", "notes"],
        "invoice": ["invoice", "bill", "receipt"],
        "legal_contract": ["contract", "agreement", "nda", "terms"],
        "policy_document": ["policy", "guidelines", "rules"],
        "technical_spec": ["spec", "specification", "requirements"],
        "sop": ["sop", "standard_operating"],
    }
    
    for doc_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in filename_lower:
                logger.info(f"[DocumentClassifier] Inferred '{doc_type}' from filename: {filename}")
                return doc_type
    
    return None


def classify_with_fallback(text: str, filename: Optional[str] = None) -> str:
    """
    Classify document using filename hints first, then LLM classification.
    
    Args:
        text: Document text content
        filename: Original filename (optional)
        
    Returns:
        Document type label
    """
    if filename:
        inferred = get_document_type_from_filename(filename)
        if inferred:
            return inferred
    
    return classify_document(text)
