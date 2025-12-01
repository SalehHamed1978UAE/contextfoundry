"""
Symbolic Memory Layer - Rules and Invariants.
Stores business rules with priority ordering for validation and governance.
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from ..models.schema import Rule, RuleType, get_session
from ..utils.logger import logger


class SymbolicMemory:
    """
    Rule-based memory for validation and governance.
    Rules are matched against query context and applied in priority order.
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        logger.info("SymbolicMemory initialized")
    
    def add_rule(
        self,
        name: str,
        rule_type: RuleType,
        description: str,
        condition: str,
        action: str,
        priority: int = 100,
        entity_types: List[str] = None,
        relationship_types: List[str] = None,
        metadata: dict = None
    ) -> Rule:
        """Add a rule to symbolic memory."""
        rule = Rule(
            name=name,
            rule_type=rule_type,
            description=description,
            condition=condition,
            action=action,
            priority=priority,
            entity_types=entity_types or [],
            relationship_types=relationship_types or [],
            metadata=metadata or {}
        )
        self.session.add(rule)
        self.session.commit()
        
        logger.debug(f"Added rule: {name} [{rule_type.value}] (priority: {priority})")
        return rule
    
    def get_active_rules(self, rule_types: List[RuleType] = None) -> List[Rule]:
        """Get all active rules, optionally filtered by type."""
        query = self.session.query(Rule).filter(Rule.is_active == True)
        
        if rule_types:
            query = query.filter(Rule.rule_type.in_(rule_types))
        
        return query.order_by(Rule.priority.desc()).all()
    
    def find_applicable_rules(
        self,
        entity_types: List[str] = None,
        relationship_types: List[str] = None,
        query_keywords: List[str] = None
    ) -> List[Dict]:
        """
        Find rules that apply to the given context.
        Returns rules that match entity types, relationship types, or keywords.
        """
        all_rules = self.get_active_rules()
        applicable = []
        
        for rule in all_rules:
            score = 0
            match_reasons = []
            
            if entity_types and rule.entity_types:
                matching_types = set(entity_types) & set(rule.entity_types)
                if matching_types:
                    score += len(matching_types) * 2
                    match_reasons.append(f"entity_types: {matching_types}")
            
            if relationship_types and rule.relationship_types:
                matching_rels = set(relationship_types) & set(rule.relationship_types)
                if matching_rels:
                    score += len(matching_rels) * 2
                    match_reasons.append(f"relationship_types: {matching_rels}")
            
            if query_keywords:
                rule_text = f"{rule.name} {rule.description} {rule.condition}".lower()
                for keyword in query_keywords:
                    if keyword.lower() in rule_text:
                        score += 1
                        match_reasons.append(f"keyword: {keyword}")
            
            if score > 0 or (not entity_types and not relationship_types and not query_keywords):
                applicable.append({
                    **rule.to_dict(),
                    "match_score": score,
                    "match_reasons": match_reasons
                })
        
        applicable.sort(key=lambda x: (x["match_score"], x["priority"]), reverse=True)
        
        logger.debug(f"Found {len(applicable)} applicable rules")
        return applicable
    
    def get_escalation_rules(self) -> List[Rule]:
        """Get all escalation policy rules."""
        return self.get_active_rules(rule_types=[RuleType.ESCALATION_POLICY])
    
    def get_invariants(self) -> List[Rule]:
        """Get all invariant rules (must always be true)."""
        return self.get_active_rules(rule_types=[RuleType.INVARIANT])
    
    def get_safety_checks(self) -> List[Rule]:
        """Get all safety check rules."""
        return self.get_active_rules(rule_types=[RuleType.SAFETY_CHECK])
    
    def evaluate_rule(self, rule: Rule, context: Dict) -> Dict:
        """
        Evaluate if a rule condition is met given the context.
        Returns evaluation result with explanation.
        
        For MVP, this is a simple keyword-based evaluation.
        In production, this would use a proper rule engine.
        """
        condition_lower = rule.condition.lower()
        
        triggered = False
        explanation = []
        
        if "sev1" in condition_lower:
            if context.get("severity") == "SEV1":
                triggered = True
                explanation.append("SEV1 condition matched")
        
        if "depends_on" in condition_lower:
            if context.get("has_dependency_failure"):
                triggered = True
                explanation.append("Dependency failure detected")
        
        if "escalat" in condition_lower:
            if context.get("query_type") in ["escalation", "incident_response"]:
                triggered = True
                explanation.append("Escalation query type matched")
        
        if "database" in condition_lower:
            if context.get("affected_entity_type") == "DATABASE":
                triggered = True
                explanation.append("Database entity type matched")
        
        if not explanation:
            explanation.append("Rule evaluated (default match)")
            triggered = True
        
        return {
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "triggered": triggered,
            "explanation": explanation,
            "action": rule.action if triggered else None,
            "priority": rule.priority
        }
    
    def validate_response(
        self,
        response_text: str,
        context: Dict,
        applicable_rules: List[Dict]
    ) -> Dict:
        """
        Validate a response against applicable rules.
        Returns validation result with any violations.
        """
        violations = []
        warnings = []
        rules_checked = []
        rules_passed = []
        
        for rule_dict in applicable_rules:
            rule = self.session.query(Rule).get(rule_dict["id"])
            if not rule:
                continue
            
            rules_checked.append(rule.name)
            eval_result = self.evaluate_rule(rule, context)
            
            if eval_result["triggered"]:
                if rule.rule_type == RuleType.INVARIANT:
                    if not self._check_invariant_satisfied(rule, response_text, context):
                        violations.append({
                            "rule": rule.name,
                            "type": "INVARIANT_VIOLATION",
                            "description": rule.description,
                            "expected_action": rule.action
                        })
                    else:
                        rules_passed.append(rule.name)
                
                elif rule.rule_type == RuleType.SAFETY_CHECK:
                    if not self._check_safety_satisfied(rule, response_text, context):
                        warnings.append({
                            "rule": rule.name,
                            "type": "SAFETY_WARNING",
                            "description": rule.description,
                            "recommended_action": rule.action
                        })
                    else:
                        rules_passed.append(rule.name)
                
                else:
                    rules_passed.append(rule.name)
        
        passed = len(violations) == 0
        
        logger.info(f"Validation: {len(rules_checked)} rules checked, "
                   f"{len(rules_passed)} passed, {len(violations)} violations")
        
        return {
            "passed": passed,
            "rules_checked": rules_checked,
            "rules_passed": rules_passed,
            "violations": violations,
            "warnings": warnings
        }
    
    def _check_invariant_satisfied(self, rule: Rule, response: str, context: Dict) -> bool:
        """Check if an invariant is satisfied. Simplified for MVP."""
        return True
    
    def _check_safety_satisfied(self, rule: Rule, response: str, context: Dict) -> bool:
        """Check if a safety requirement is satisfied. Simplified for MVP."""
        return True
    
    def get_statistics(self) -> Dict:
        """Get statistics about symbolic memory."""
        total = self.session.query(Rule).count()
        active = self.session.query(Rule).filter(Rule.is_active == True).count()
        
        by_type = {}
        for rule_type in RuleType:
            count = self.session.query(Rule).filter(
                Rule.rule_type == rule_type
            ).count()
            if count > 0:
                by_type[rule_type.value] = count
        
        return {
            "total_rules": total,
            "active_rules": active,
            "by_type": by_type
        }
