"""
Validation Agent

Validates responses against symbolic rules.
Ensures answers comply with policies and invariants.
"""

import json
from typing import Dict, Any, List, Tuple

from src.models.schemas import ReasoningResponse, ContextBundle


class ValidationAgent:
    """Validates responses against symbolic rules"""

    def __init__(self, db_manager):
        self.db = db_manager

    async def validate(
        self,
        response: ReasoningResponse,
        bundle: ContextBundle
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate response against applicable rules

        Args:
            response: ReasoningResponse to validate
            bundle: ContextBundle with applicable rules

        Returns:
            Tuple of (all_rules_passed, list_of_violations)
        """

        violations = []
        rules_checked = []

        # Get applicable rules from bundle
        rules = bundle.symbolic_rules_applied

        if not rules:
            # No rules to check
            return True, []

        # For MVP, implement basic rule validation
        # In production, would use a proper rule engine

        for rule in rules:
            rule_name = rule.get("rule_name")
            rule_type = rule.get("rule_type")
            expression = rule.get("expression")

            rules_checked.append(rule_name)

            # Check rule based on type
            passed, violation = await self._check_rule(
                rule_name,
                rule_type,
                expression,
                response,
                bundle
            )

            if not passed:
                violations.append(violation)

        # Update response with validation results
        response.rules_checked = rules_checked
        response.rules_passed = len(violations) == 0
        response.validation_failures = violations

        return len(violations) == 0, violations

    async def _check_rule(
        self,
        rule_name: str,
        rule_type: str,
        expression: str,
        response: ReasoningResponse,
        bundle: ContextBundle
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check a single rule

        Args:
            rule_name: Name of rule
            rule_type: Type of rule (invariant, safety, etc.)
            expression: Rule expression
            response: Response to validate
            bundle: Context bundle

        Returns:
            Tuple of (passed, violation_dict)
        """

        # Parse expression (stored as JSON string)
        try:
            expr_dict = json.loads(expression) if isinstance(expression, str) else expression
        except:
            expr_dict = {}

        condition = expr_dict.get("condition", "")

        # For MVP, implement simple rule checks
        # In production, would use a DSL or rule engine

        # Example rule checks:
        if "must have" in condition.lower() and "owner" in condition.lower():
            # Check if services mentioned have owners
            return await self._check_ownership_rule(rule_name, response, bundle)

        elif "circuit breaker" in condition.lower():
            # Check if high-criticality dependencies have circuit breakers
            return await self._check_circuit_breaker_rule(rule_name, response, bundle)

        elif "escalation" in condition.lower():
            # Check incident escalation policy
            return await self._check_escalation_rule(rule_name, response, bundle)

        # Default: rule passes (conservative)
        return True, {}

    async def _check_ownership_rule(
        self,
        rule_name: str,
        response: ReasoningResponse,
        bundle: ContextBundle
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check that services have owners"""

        # Check if any Service entities in context lack OWNS relationships
        service_entities = [
            e for e in bundle.semantic_entities
            if e.get("entity_type") == "Service"
        ]

        if not service_entities:
            return True, {}  # No services mentioned, rule not applicable

        # Check for OWNS relationships
        for service in service_entities:
            service_id = service.get("entity_id")

            # Check if this service has an OWNS relationship
            has_owner = any(
                rel.get("relationship_type") == "OWNS" and
                rel.get("target_entity_id") == service_id
                for rel in bundle.semantic_relationships
            )

            if not has_owner:
                return False, {
                    "rule": rule_name,
                    "violation": f"Service {service_id} lacks owner",
                    "severity": "warning",
                    "recommendation": "Verify service ownership in CMDB"
                }

        return True, {}

    async def _check_circuit_breaker_rule(
        self,
        rule_name: str,
        response: ReasoningResponse,
        bundle: ContextBundle
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check circuit breaker requirements"""

        # For MVP, just check if high-criticality dependencies are mentioned
        # and warn about circuit breaker requirements

        high_crit_deps = [
            rel for rel in bundle.semantic_relationships
            if rel.get("relationship_type") in ["DEPENDS_ON", "CALLS"]
            and rel.get("properties", {}).get("criticality") == "high"
        ]

        if high_crit_deps:
            # Add caveat to response
            caveat = "High-criticality dependencies require circuit breaker implementation"
            if caveat not in response.caveats:
                response.caveats.append(caveat)

        return True, {}  # Warning, not violation

    async def _check_escalation_rule(
        self,
        rule_name: str,
        response: ReasoningResponse,
        bundle: ContextBundle
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check incident escalation policy"""

        # Check if answer involves critical incidents
        if "critical" in response.answer.lower() or "incident" in response.answer.lower():
            # Add escalation policy reminder
            caveat = "Critical incidents require escalation if unresolved for >30 minutes"
            if caveat not in response.caveats:
                response.caveats.append(caveat)

        return True, {}

    async def record_validation(
        self,
        response: ReasoningResponse,
        passed: bool,
        violations: List[Dict[str, Any]]
    ):
        """Record validation results for learning"""

        async with self.db.get_postgres_connection() as conn:
            # Update rules application counts
            for rule_name in response.rules_checked:
                await conn.execute("""
                    UPDATE symbolic_rules
                    SET times_applied = times_applied + 1,
                        last_applied = NOW()
                    WHERE rule_name = $1
                """, rule_name)

            # Record violations
            for violation in violations:
                rule_name = violation.get("rule")
                await conn.execute("""
                    UPDATE symbolic_rules
                    SET times_violated = times_violated + 1
                    WHERE rule_name = $1
                """, rule_name)
