"""
Org Chart Synthetic Data Generator.

Creates a realistic org chart dataset to test Context Foundry on a non-IT domain.
Demonstrates that the tri-memory architecture is domain-agnostic.

Structure:
- 5 Departments (Engineering, Product, Sales, Marketing, Operations)
- 8 Teams (distributed across departments)
- 30 People (with roles and reporting structure)
- Relationships: REPORTS_TO, MEMBER_OF, LEADS, COLLABORATES_WITH
- Rules: VP approval for large teams, steering committee for cross-dept projects
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass
import random


@dataclass
class OrgPerson:
    name: str
    role: str
    level: str  # IC, Manager, Director, VP, C-Level
    department: str
    expertise: List[str]


@dataclass
class OrgTeam:
    name: str
    department: str
    focus: str
    headcount: int


@dataclass
class OrgDepartment:
    name: str
    head: str
    mission: str


class OrgChartGenerator:
    """Generates synthetic org chart data for testing."""
    
    def __init__(self):
        self.departments: List[OrgDepartment] = []
        self.teams: List[OrgTeam] = []
        self.people: List[OrgPerson] = []
        self.relationships: List[Tuple[str, str, str, str]] = []  # (from, rel_type, to, source)
        
    def generate(self) -> Dict:
        """Generate the complete org chart dataset."""
        self._create_departments()
        self._create_teams()
        self._create_people()
        self._create_relationships()
        
        return {
            "departments": [d.__dict__ for d in self.departments],
            "teams": [t.__dict__ for t in self.teams],
            "people": [p.__dict__ for p in self.people],
            "relationships": [
                {"from": r[0], "type": r[1], "to": r[2], "source": r[3]}
                for r in self.relationships
            ],
            "rules": self._create_rules(),
            "documents": self._create_documents(),
        }
    
    def _create_departments(self):
        """Create 5 departments."""
        self.departments = [
            OrgDepartment(
                name="Engineering",
                head="Sarah Chen",
                mission="Build and maintain the company's technology products"
            ),
            OrgDepartment(
                name="Product",
                head="Michael Torres",
                mission="Define product strategy and roadmap"
            ),
            OrgDepartment(
                name="Sales",
                head="Jennifer Williams",
                mission="Drive revenue growth through customer acquisition"
            ),
            OrgDepartment(
                name="Marketing",
                head="David Kim",
                mission="Build brand awareness and generate leads"
            ),
            OrgDepartment(
                name="Operations",
                head="Lisa Patel",
                mission="Ensure operational excellence and efficiency"
            ),
        ]
    
    def _create_teams(self):
        """Create 8 teams across departments (prefixed with 'Org:' to avoid collision with IT ops data)."""
        self.teams = [
            OrgTeam(
                name="Org: Platform Team",
                department="Engineering",
                focus="Core infrastructure and developer tools",
                headcount=12
            ),
            OrgTeam(
                name="Org: Frontend Team",
                department="Engineering",
                focus="User interface and experience",
                headcount=8
            ),
            OrgTeam(
                name="Org: Data Team",
                department="Engineering",
                focus="Data pipelines and analytics infrastructure",
                headcount=6
            ),
            OrgTeam(
                name="Org: Product Strategy",
                department="Product",
                focus="Long-term product vision and roadmap",
                headcount=4
            ),
            OrgTeam(
                name="Org: Enterprise Sales",
                department="Sales",
                focus="Large account acquisition and management",
                headcount=9
            ),
            OrgTeam(
                name="Org: Growth Team",
                department="Marketing",
                focus="User acquisition and activation",
                headcount=7
            ),
            OrgTeam(
                name="Org: Brand Team",
                department="Marketing",
                focus="Brand identity and communications",
                headcount=5
            ),
            OrgTeam(
                name="Org: People Ops",
                department="Operations",
                focus="HR, recruiting, and employee experience",
                headcount=6
            ),
        ]
    
    def _create_people(self):
        """Create 30 people with roles and levels."""
        self.people = [
            OrgPerson("Sarah Chen", "VP of Engineering", "VP", "Engineering", ["architecture", "scaling", "leadership"]),
            OrgPerson("Michael Torres", "VP of Product", "VP", "Product", ["strategy", "roadmap", "user-research"]),
            OrgPerson("Jennifer Williams", "VP of Sales", "VP", "Sales", ["enterprise", "negotiation", "partnerships"]),
            OrgPerson("David Kim", "VP of Marketing", "VP", "Marketing", ["brand", "growth", "analytics"]),
            OrgPerson("Lisa Patel", "VP of Operations", "VP", "Operations", ["process", "efficiency", "compliance"]),
            
            OrgPerson("Alex Rivera", "Director of Platform", "Director", "Engineering", ["infrastructure", "kubernetes", "reliability"]),
            OrgPerson("Emily Zhang", "Director of Frontend", "Director", "Engineering", ["react", "ux", "performance"]),
            OrgPerson("James Wilson", "Director of Data", "Director", "Engineering", ["data-pipelines", "ml", "analytics"]),
            OrgPerson("Rachel Green", "Director of Product Strategy", "Director", "Product", ["vision", "market-analysis", "pricing"]),
            OrgPerson("Chris Anderson", "Director of Enterprise Sales", "Director", "Sales", ["accounts", "closing", "relationships"]),
            OrgPerson("Nina Sharma", "Director of Growth", "Director", "Marketing", ["acquisition", "conversion", "retention"]),
            OrgPerson("Tom Baker", "Director of Brand", "Director", "Marketing", ["messaging", "design", "pr"]),
            OrgPerson("Maria Garcia", "Director of People Ops", "Director", "Operations", ["recruiting", "culture", "benefits"]),
            
            OrgPerson("Kevin Lee", "Engineering Manager", "Manager", "Engineering", ["team-lead", "agile", "mentoring"]),
            OrgPerson("Amy Chen", "Senior Platform Engineer", "IC", "Engineering", ["go", "kubernetes", "distributed-systems"]),
            OrgPerson("Brian Taylor", "Platform Engineer", "IC", "Engineering", ["python", "terraform", "aws"]),
            OrgPerson("Diana Ross", "Platform Engineer", "IC", "Engineering", ["java", "microservices", "kafka"]),
            OrgPerson("Eric Johnson", "Senior Frontend Engineer", "IC", "Engineering", ["typescript", "react", "accessibility"]),
            OrgPerson("Fiona Martinez", "Frontend Engineer", "IC", "Engineering", ["javascript", "css", "testing"]),
            OrgPerson("George Brown", "Data Engineer", "IC", "Engineering", ["spark", "airflow", "sql"]),
            OrgPerson("Hannah White", "ML Engineer", "IC", "Engineering", ["python", "tensorflow", "mlops"]),
            
            OrgPerson("Ian Clark", "Senior Product Manager", "IC", "Product", ["specs", "prioritization", "stakeholders"]),
            OrgPerson("Julia Adams", "Product Manager", "IC", "Product", ["user-stories", "analytics", "experiments"]),
            
            OrgPerson("Kyle Thompson", "Senior Account Executive", "IC", "Sales", ["enterprise", "saas", "demos"]),
            OrgPerson("Laura Davis", "Account Executive", "IC", "Sales", ["prospecting", "pipeline", "crm"]),
            
            OrgPerson("Mark Robinson", "Growth Marketing Manager", "Manager", "Marketing", ["campaigns", "seo", "paid"]),
            OrgPerson("Nancy Wright", "Content Strategist", "IC", "Marketing", ["writing", "seo", "social"]),
            
            OrgPerson("Oscar Hernandez", "HR Business Partner", "IC", "Operations", ["employee-relations", "policies", "onboarding"]),
            OrgPerson("Patricia Moore", "Recruiter", "IC", "Operations", ["sourcing", "interviewing", "closing"]),
            OrgPerson("Robert Jackson", "Office Manager", "IC", "Operations", ["facilities", "events", "vendors"]),
        ]
    
    def _create_relationships(self):
        """Create all org chart relationships."""
        
        vp_map = {
            "Engineering": "Sarah Chen",
            "Product": "Michael Torres",
            "Sales": "Jennifer Williams",
            "Marketing": "David Kim",
            "Operations": "Lisa Patel",
        }
        
        director_team_map = {
            "Alex Rivera": "Org: Platform Team",
            "Emily Zhang": "Org: Frontend Team",
            "James Wilson": "Org: Data Team",
            "Rachel Green": "Org: Product Strategy",
            "Chris Anderson": "Org: Enterprise Sales",
            "Nina Sharma": "Org: Growth Team",
            "Tom Baker": "Org: Brand Team",
            "Maria Garcia": "Org: People Ops",
        }
        
        team_members = {
            "Org: Platform Team": ["Kevin Lee", "Amy Chen", "Brian Taylor", "Diana Ross"],
            "Org: Frontend Team": ["Eric Johnson", "Fiona Martinez"],
            "Org: Data Team": ["George Brown", "Hannah White"],
            "Org: Product Strategy": ["Ian Clark", "Julia Adams"],
            "Org: Enterprise Sales": ["Kyle Thompson", "Laura Davis"],
            "Org: Growth Team": ["Mark Robinson", "Nancy Wright"],
            "Org: Brand Team": [],
            "Org: People Ops": ["Oscar Hernandez", "Patricia Moore", "Robert Jackson"],
        }
        
        for person in self.people:
            if person.level == "Director":
                vp = vp_map.get(person.department)
                if vp:
                    self.relationships.append((
                        person.name,
                        "REPORTS_TO",
                        vp,
                        f"{person.name} reports to {vp} as {person.role}."
                    ))
        
        for director, team in director_team_map.items():
            self.relationships.append((
                director,
                "LEADS",
                team,
                f"{director} leads the {team}."
            ))
            self.relationships.append((
                director,
                "MEMBER_OF",
                team,
                f"{director} is a member of {team}."
            ))
        
        for team, members in team_members.items():
            director = [d for d, t in director_team_map.items() if t == team]
            if director:
                for member in members:
                    self.relationships.append((
                        member,
                        "REPORTS_TO",
                        director[0],
                        f"{member} reports to {director[0]}."
                    ))
                    self.relationships.append((
                        member,
                        "MEMBER_OF",
                        team,
                        f"{member} is a member of {team}."
                    ))
        
        self.relationships.append((
            "Org: Platform Team",
            "COLLABORATES_WITH",
            "Org: Data Team",
            "Org: Platform Team provides infrastructure support to Org: Data Team."
        ))
        self.relationships.append((
            "Org: Growth Team",
            "COLLABORATES_WITH",
            "Org: Product Strategy",
            "Org: Growth Team works closely with Org: Product Strategy on experiments."
        ))
        self.relationships.append((
            "Org: Enterprise Sales",
            "COLLABORATES_WITH",
            "Org: Product Strategy",
            "Org: Enterprise Sales provides customer feedback to Org: Product Strategy."
        ))
        
        for dept in self.departments:
            vp = vp_map.get(dept.name)
            if vp:
                self.relationships.append((
                    vp,
                    "LEADS",
                    dept.name,
                    f"{vp} leads the {dept.name} department."
                ))
    
    def _create_rules(self) -> List[Dict]:
        """Create business rules for org chart domain."""
        return [
            {
                "name": "VP Approval for Large Teams",
                "type": "INVARIANT",
                "priority": 100,
                "condition": "team.headcount > 10",
                "action": "require_approval(department.vp, 'headcount_increase')",
                "description": "VP approval is required for any headcount changes to teams with more than 10 members."
            },
            {
                "name": "Director Approval for Hiring",
                "type": "ESCALATION_POLICY",
                "priority": 90,
                "condition": "action.type == 'hiring' AND team.headcount <= 10",
                "action": "require_approval(team.director, 'hiring')",
                "description": "Directors can approve hiring for teams with 10 or fewer members."
            },
            {
                "name": "Cross-Department Steering Committee",
                "type": "VALIDATION",
                "priority": 85,
                "condition": "project.departments.count > 1",
                "action": "require_steering_committee(project.departments)",
                "description": "Projects spanning multiple departments require a steering committee with representatives from each department."
            },
            {
                "name": "Manager Span of Control",
                "type": "SAFETY_CHECK",
                "priority": 80,
                "condition": "manager.direct_reports > 8",
                "action": "flag_for_review('span_of_control_exceeded')",
                "description": "Managers should have no more than 8 direct reports. Exceeding this triggers a review."
            },
            {
                "name": "Budget Authority by Level",
                "type": "ESCALATION_POLICY",
                "priority": 95,
                "condition": "expense.amount > level_budget_limit",
                "action": "escalate_to_next_level(approver)",
                "description": "Expense approvals escalate based on amount: IC ($500), Manager ($5K), Director ($50K), VP ($500K)."
            },
        ]
    
    def _create_documents(self) -> List[Dict]:
        """Create HR/org documents for episodic memory."""
        return [
            {
                "title": "Hiring Process Guide",
                "type": "POLICY",
                "content": """# Hiring Process Guide

## Overview
This guide outlines the standard process for making new hires.

## Approval Requirements
- Teams with 10 or fewer members: Director approval required
- Teams with more than 10 members: VP approval required
- All hires require budget allocation from Finance

## Process Steps
1. Submit headcount request with justification
2. Obtain required approval (Director or VP)
3. Work with Recruiting to post the role
4. Conduct interviews per hiring standards
5. Make offer with HR review

## Org: Platform Team Special Notes
The Org: Platform Team currently has 12 members, exceeding the 10-person threshold.
Any new hires require VP of Engineering (Sarah Chen) approval.
"""
            },
            {
                "title": "Escalation Procedures",
                "type": "PROCEDURE",
                "content": """# Escalation Procedures

## Standard Escalation Path
1. Team Lead / Manager
2. Director
3. VP
4. Executive Team

## Hiring Escalation
- Standard teams (<=10): Director is final approver
- Large teams (>10): Must escalate to VP
- VP can delegate back to Director with documented approval

## Cross-Department Escalation
When an issue spans departments:
1. Directors from each department convene
2. If unresolved, escalate to respective VPs
3. Joint VP decision is binding
"""
            },
            {
                "title": "Team Structure Overview",
                "type": "REFERENCE",
                "content": """# Team Structure Overview

## Engineering Department (VP: Sarah Chen)
- Org: Platform Team (12 members) - Director: Alex Rivera
- Org: Frontend Team (8 members) - Director: Emily Zhang
- Org: Data Team (6 members) - Director: James Wilson

## Product Department (VP: Michael Torres)
- Org: Product Strategy (4 members) - Director: Rachel Green

## Sales Department (VP: Jennifer Williams)
- Org: Enterprise Sales (9 members) - Director: Chris Anderson

## Marketing Department (VP: David Kim)
- Org: Growth Team (7 members) - Director: Nina Sharma
- Org: Brand Team (5 members) - Director: Tom Baker

## Operations Department (VP: Lisa Patel)
- Org: People Ops (6 members) - Director: Maria Garcia
"""
            },
        ]


def generate_org_chart_data() -> Dict:
    """Generate org chart synthetic data."""
    generator = OrgChartGenerator()
    return generator.generate()


if __name__ == "__main__":
    import json
    data = generate_org_chart_data()
    print(json.dumps(data, indent=2))
