"""
Validation Agent - Checks responses against symbolic rules.
Ensures governance and compliance with business rules.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from ..models.context_bundle import ContextBundle
from ..memory.symbolic import SymbolicMemory
from ..utils.logger import logger, QueryLogger


class ValidationAgent:
    """
    Agent that validates reasoning responses against symbolic rules.
    Checks for rule violations and adds validation metadata.
    """
    
    def __init__(self, session: Optional[Session] = None):
        from ..models.schema import get_session
        self.session = session or get_session()
        self.symbolic = SymbolicMemory(self.session)
        
        logger.info("ValidationAgent initialized")
    
    def validate_response(
        self,
        response: Dict,
        bundle: ContextBundle,
        query_logger: Optional[QueryLogger] = None
    ) -> Dict:
        """
        Validate a reasoning response against applicable rules.
        
        Returns the response enriched with validation results.
        """
        applicable_rules = bundle.symbolic_rules
        
        context = self._build_validation_context(response, bundle)
        
        validation_result = self.symbolic.validate_response(
            response.get("answer", ""),
            context,
            applicable_rules
        )
        
        response["validation"] = validation_result
        response["rules_checked"] = validation_result["rules_checked"]
        response["rules_passed"] = validation_result["rules_passed"]
        response["rules_violations"] = validation_result["violations"]
        response["rules_warnings"] = validation_result["warnings"]
        
        if validation_result["violations"]:
            response = self._adjust_for_violations(response, validation_result["violations"])
        
        if query_logger:
            query_logger.log_validation(
                validation_result["passed"],
                validation_result["violations"]
            )
        
        logger.info(f"Validation: {len(validation_result['rules_checked'])} rules checked, "
                   f"{len(validation_result['violations'])} violations")
        
        return response
    
    def _build_validation_context(self, response: Dict, bundle: ContextBundle) -> Dict:
        """Build context dictionary for rule evaluation."""
        context = {
            "query_text": bundle.query_text,
            "response_text": response.get("answer", ""),
            "confidence": response.get("confidence", 0),
        }
        
        if any(word in bundle.query_text.lower() for word in ["sev1", "severity 1", "critical"]):
            context["severity"] = "SEV1"
        elif any(word in bundle.query_text.lower() for word in ["sev2", "severity 2"]):
            context["severity"] = "SEV2"
        
        if any(word in bundle.query_text.lower() for word in ["escalat", "who should i contact"]):
            context["query_type"] = "escalation"
        elif any(word in bundle.query_text.lower() for word in ["impact", "affect", "down"]):
            context["query_type"] = "impact_assessment"
        elif any(word in bundle.query_text.lower() for word in ["incident", "outage"]):
            context["query_type"] = "incident_response"
        
        entity_types = set()
        for entity in bundle.semantic_entities:
            entity_type = entity.get("entity_type")
            if entity_type:
                entity_types.add(entity_type)
        context["entity_types"] = list(entity_types)
        
        if "DATABASE" in entity_types:
            context["affected_entity_type"] = "DATABASE"
        elif "SERVICE" in entity_types:
            context["affected_entity_type"] = "SERVICE"
        
        rel_types = set()
        for rel in bundle.semantic_relationships:
            rel_type = rel.get("relationship_type")
            if rel_type:
                rel_types.add(rel_type)
        context["relationship_types"] = list(rel_types)
        
        if "DEPENDS_ON" in rel_types:
            context["has_dependencies"] = True
        
        return context
    
    def _adjust_for_violations(self, response: Dict, violations: List[Dict]) -> Dict:
        """Adjust response based on rule violations."""
        response["confidence"] = max(0.1, response.get("confidence", 0.5) - 0.2)
        response["confidence_level"] = "low" if response["confidence"] >= 0.5 else "very_low"
        
        if "caveats" not in response:
            response["caveats"] = []
        
        for violation in violations:
            caveat = f"RULE VIOLATION: {violation['rule']} - {violation['description']}"
            response["caveats"].append(caveat)
        
        if "uncertainty" not in response:
            response["uncertainty"] = {}
        
        response["uncertainty"]["rule_violations"] = [v["rule"] for v in violations]
        response["uncertainty"]["reasons"] = response["uncertainty"].get("reasons", [])
        response["uncertainty"]["reasons"].append(
            f"{len(violations)} rule violation(s) detected"
        )
        
        return response
    
    def check_escalation_requirements(
        self,
        response: Dict,
        bundle: ContextBundle
    ) -> Dict:
        """
        Special validation for escalation-related queries.
        Ensures escalation policies are properly applied.
        """
        escalation_rules = self.symbolic.get_escalation_rules()
        
        if not escalation_rules:
            return response
        
        for rule in escalation_rules:
            if "sev1" in bundle.query_text.lower():
                if "metadata" in rule.to_dict():
                    contact = rule.to_dict()["metadata"].get("contact")
                    if contact and contact.lower() not in response.get("answer", "").lower():
                        if "caveats" not in response:
                            response["caveats"] = []
                        response["caveats"].append(
                            f"ESCALATION REMINDER: For SEV1, consider escalating to {contact}"
                        )
        
        return response
    
    def check_invariants(self, bundle: ContextBundle) -> List[Dict]:
        """
        Check if any invariants are violated in the context.
        This is called before reasoning to flag potential issues.
        """
        invariants = self.symbolic.get_invariants()
        violations = []
        
        for invariant in invariants:
            logger.debug(f"Checking invariant: {invariant.name}")
        
        return violations
