#!/usr/bin/env python3
"""
Generate synthetic documents at scale for stress testing Context Foundry.

Usage:
    python generate_scale_data.py --count 250    # 10x scale (~2,500 chunks)
    python generate_scale_data.py --count 1250   # 50x scale (~12,500 chunks)
"""

import argparse
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import json

PEOPLE = [
    "Mia White", "Alex Rivera", "Jordan Lee", "Taylor Kim", "Morgan Chen",
    "Casey Martinez", "Drew Patel", "Quinn Thompson", "Riley Garcia", "Blake Adams",
    "Avery Brown", "Cameron Davis", "Dakota Miller", "Emerson Wilson", "Finley Moore",
    "Harper Taylor", "Jamie Anderson", "Kendall Thomas", "Logan Jackson", "Parker Harris",
    "Reese Martin", "Sage Robinson", "Sydney Clark", "Tatum Lewis", "Blake Walker",
]

SERVICES = [
    "Auth Service", "Payment Service", "API Gateway", "Notification Service",
    "User Service", "Order Service", "Inventory Service", "Search Service",
    "Cache Layer", "Fraud Detection", "Analytics Service", "Checkout Service",
    "Shipping Service", "Recommendation Engine", "Email Service", "SMS Gateway",
]

TEAMS = [
    "Platform Team", "Backend Team", "Frontend Team", "Infrastructure Team",
    "Security Team", "Data Team", "DevOps Team", "QA Team", "SRE Team",
    "Mobile Team", "API Team", "Growth Team",
]

DATABASES = [
    "Users DB", "Payments DB", "Orders DB", "Analytics DB", "Cache Redis",
    "Search Elasticsearch", "Sessions Store", "Audit Log DB",
]

TOPICS = [
    "cloud migration", "cost reduction", "performance optimization", "security audit",
    "scalability planning", "technical debt", "microservices refactoring", "API versioning",
    "database sharding", "caching strategy", "monitoring improvements", "incident response",
    "capacity planning", "disaster recovery", "compliance requirements", "vendor evaluation",
    "hiring priorities", "team restructuring", "budget allocation", "Q4 planning",
    "observability stack", "CI/CD pipeline", "testing strategy", "documentation",
]

CONCERNS = [
    "latency issues", "memory leaks", "error rates increasing", "deployment failures",
    "scaling bottlenecks", "security vulnerabilities", "data inconsistency", "timeout errors",
    "resource exhaustion", "configuration drift", "missing documentation", "technical debt",
]

DECISIONS = [
    "approved", "deferred", "needs more analysis", "rejected", "pilot approved",
    "proceeding with caution", "escalated to leadership", "requires budget approval",
]

DOC_TEMPLATES = {
    "meeting_notes": {
        "prefix": "# {topic} Meeting Notes\n\n**Date:** {date}\n**Attendees:** {attendees}\n\n## Summary\n\n",
        "sections": [
            "## Discussion Points\n\n{content}\n\n",
            "## Action Items\n\n{action_items}\n\n",
            "## Decisions\n\n{decisions}\n\n",
        ],
    },
    "email": {
        "prefix": "**From:** {sender}\n**To:** {recipients}\n**Subject:** {subject}\n**Date:** {date}\n\n",
        "sections": [
            "{greeting}\n\n{content}\n\n{closing}\n\n",
        ],
    },
    "strategy_doc": {
        "prefix": "# {title}\n\n**Author:** {author}\n**Last Updated:** {date}\n**Status:** {status}\n\n## Executive Summary\n\n{summary}\n\n",
        "sections": [
            "## Background\n\n{background}\n\n",
            "## Proposed Approach\n\n{approach}\n\n",
            "## Timeline\n\n{timeline}\n\n",
            "## Risks and Mitigations\n\n{risks}\n\n",
        ],
    },
    "incident_report": {
        "prefix": "# Incident Report: {incident_title}\n\n**Severity:** {severity}\n**Date:** {date}\n**Duration:** {duration}\n**Services Affected:** {services}\n\n",
        "sections": [
            "## Timeline\n\n{timeline}\n\n",
            "## Root Cause\n\n{root_cause}\n\n",
            "## Resolution\n\n{resolution}\n\n",
            "## Action Items\n\n{action_items}\n\n",
        ],
    },
    "slack_export": {
        "prefix": "# #{channel} - {date_range}\n\n",
        "sections": [
            "{messages}\n\n",
        ],
    },
    "design_doc": {
        "prefix": "# Design Doc: {title}\n\n**Author:** {author}\n**Reviewers:** {reviewers}\n**Status:** {status}\n**Created:** {date}\n\n## Overview\n\n{overview}\n\n",
        "sections": [
            "## Requirements\n\n{requirements}\n\n",
            "## Technical Design\n\n{design}\n\n",
            "## Alternatives Considered\n\n{alternatives}\n\n",
            "## Implementation Plan\n\n{plan}\n\n",
        ],
    },
    "retrospective": {
        "prefix": "# {sprint} Retrospective\n\n**Date:** {date}\n**Facilitator:** {facilitator}\n**Team:** {team}\n\n",
        "sections": [
            "## What Went Well\n\n{good}\n\n",
            "## What Could Be Improved\n\n{improve}\n\n",
            "## Action Items\n\n{actions}\n\n",
        ],
    },
}


def random_date(days_back: int = 180) -> str:
    """Generate a random date within the last N days."""
    date = datetime.now() - timedelta(days=random.randint(0, days_back))
    return date.strftime("%Y-%m-%d")


def random_attendees(count: int = None) -> str:
    """Generate a random list of attendees."""
    if count is None:
        count = random.randint(3, 8)
    return ", ".join(random.sample(PEOPLE, min(count, len(PEOPLE))))


def random_services(count: int = None) -> str:
    """Generate a random list of services."""
    if count is None:
        count = random.randint(1, 4)
    return ", ".join(random.sample(SERVICES, min(count, len(SERVICES))))


def generate_discussion_content(topic: str, people: List[str]) -> str:
    """Generate realistic discussion content."""
    templates = [
        "{person} raised concerns about {concern} in the context of {topic}.",
        "{person} proposed that we should prioritize {topic} before Q4.",
        "There was significant debate about {topic}. {person} advocated for a phased approach.",
        "{person} noted that {service} is currently experiencing {concern}.",
        "The team discussed the impact of {topic} on {service}.",
        "{person} suggested involving {team} in the {topic} initiative.",
        "According to {person}, we need to address {concern} before proceeding with {topic}.",
        "{person} presented data showing improvements in {service} after implementing {topic}.",
        "The discussion around {topic} highlighted tensions between speed and stability.",
        "{person} recommended a proof-of-concept for {topic} using {service}.",
    ]
    
    lines = []
    for _ in range(random.randint(4, 8)):
        template = random.choice(templates)
        line = template.format(
            person=random.choice(people),
            concern=random.choice(CONCERNS),
            topic=topic,
            service=random.choice(SERVICES),
            team=random.choice(TEAMS),
        )
        lines.append(f"- {line}")
    
    return "\n".join(lines)


def generate_action_items(people: List[str]) -> str:
    """Generate action items."""
    templates = [
        "[ ] {person}: Follow up on {topic} by {date}",
        "[ ] {person}: Schedule meeting with {team} to discuss next steps",
        "[ ] {person}: Create proposal for {topic} improvements",
        "[ ] {person}: Review {service} metrics and report back",
        "[ ] {person}: Coordinate with {team} on {topic} requirements",
    ]
    
    items = []
    for _ in range(random.randint(2, 5)):
        template = random.choice(templates)
        item = template.format(
            person=random.choice(people),
            topic=random.choice(TOPICS),
            date=random_date(30),
            team=random.choice(TEAMS),
            service=random.choice(SERVICES),
        )
        items.append(item)
    
    return "\n".join(items)


def generate_decisions() -> str:
    """Generate meeting decisions."""
    templates = [
        "**{topic}**: {decision}. {person} to lead implementation.",
        "**{service} {topic}**: {decision} pending {team} review.",
        "**Budget for {topic}**: {decision}. Will revisit in Q{quarter}.",
    ]
    
    decisions = []
    for _ in range(random.randint(1, 3)):
        template = random.choice(templates)
        decision = template.format(
            topic=random.choice(TOPICS),
            decision=random.choice(DECISIONS),
            person=random.choice(PEOPLE),
            service=random.choice(SERVICES),
            team=random.choice(TEAMS),
            quarter=random.randint(1, 4),
        )
        decisions.append(decision)
    
    return "\n".join(decisions)


def generate_email_content(topic: str, sender: str) -> Dict[str, str]:
    """Generate email content."""
    greetings = ["Hi team,", "Hello everyone,", "Hi all,", f"Hi {random.choice(PEOPLE)},"]
    closings = ["Best,", "Thanks,", "Regards,", "Cheers,"]
    
    content_templates = [
        f"I wanted to follow up on our discussion about {topic}. After reviewing the data, I believe we should proceed with the proposed changes to {{service}}.\n\nKey points:\n- Current {random.choice(CONCERNS)} are impacting user experience\n- {{team}} has capacity to address this in the next sprint\n- Expected improvement: 20-30% reduction in latency\n\nPlease let me know if you have any concerns.",
        f"Quick update on {topic}:\n\nWe've completed the initial analysis and identified several areas for improvement in {{service}}. {{person}} will be presenting the findings in tomorrow's standup.\n\nMain recommendations:\n1. Increase caching layer capacity\n2. Optimize database queries\n3. Add circuit breakers for external dependencies",
        f"Following up on the {topic} initiative. {{team}} has made significant progress:\n\n- Completed POC for new {{service}} architecture\n- Reduced {random.choice(CONCERNS)} by 40%\n- Documentation updated in Confluence\n\nNext steps: Production rollout planned for next week.",
    ]
    
    return {
        "greeting": random.choice(greetings),
        "content": random.choice(content_templates).format(
            service=random.choice(SERVICES),
            team=random.choice(TEAMS),
            person=random.choice(PEOPLE),
        ),
        "closing": f"{random.choice(closings)}\n{sender}",
    }


def generate_slack_messages(channel: str, date: str) -> str:
    """Generate Slack-style messages."""
    message_templates = [
        "**{person}** [{time}]: Anyone looked at the {service} alerts? Seeing increased {concern}.",
        "**{person}** [{time}]: ^^ I'm on it. Checking {database} connection pool.",
        "**{person}** [{time}]: FYI - deploying hotfix for {service}. ETA 10 mins.",
        "**{person}** [{time}]: :white_check_mark: {service} metrics back to normal.",
        "**{person}** [{time}]: Question about {topic} - should we sync with {team}?",
        "**{person}** [{time}]: @here Quick reminder: {topic} review tomorrow at 2pm.",
        "**{person}** [{time}]: Just merged the {topic} changes. Please review when you get a chance.",
        "**{person}** [{time}]: Interesting article on {topic}: [link]",
        "**{person}** [{time}]: :thread: Starting thread on {concern} in {service}",
        "**{person}** [{time}]: Update from {team} standup - {topic} is now our P0.",
    ]
    
    messages = []
    for i in range(random.randint(10, 20)):
        time = f"{random.randint(8, 18):02d}:{random.randint(0, 59):02d}"
        template = random.choice(message_templates)
        msg = template.format(
            person=random.choice(PEOPLE),
            time=time,
            service=random.choice(SERVICES),
            concern=random.choice(CONCERNS),
            database=random.choice(DATABASES),
            topic=random.choice(TOPICS),
            team=random.choice(TEAMS),
        )
        messages.append(msg)
    
    return "\n\n".join(messages)


def generate_incident_timeline() -> str:
    """Generate incident timeline."""
    events = [
        "{time}: Alert triggered for {service} - {concern}",
        "{time}: On-call engineer ({person}) paged",
        "{time}: Initial investigation started",
        "{time}: Root cause identified: {root_cause}",
        "{time}: Mitigation applied",
        "{time}: Services recovering",
        "{time}: Incident resolved, monitoring",
    ]
    
    root_causes = [
        "database connection pool exhaustion",
        "memory leak in cache layer",
        "network partition in {service}",
        "failed deployment rollback",
        "certificate expiration",
        "resource limit reached",
    ]
    
    timeline = []
    hour = random.randint(0, 20)
    for event in events:
        hour += random.randint(0, 2)
        minute = random.randint(0, 59)
        time = f"{hour:02d}:{minute:02d}"
        line = event.format(
            time=time,
            service=random.choice(SERVICES),
            concern=random.choice(CONCERNS),
            person=random.choice(PEOPLE),
            root_cause=random.choice(root_causes).format(service=random.choice(SERVICES)),
        )
        timeline.append(f"- {line}")
    
    return "\n".join(timeline)


def generate_document(doc_type: str, index: int) -> Dict[str, str]:
    """Generate a single document of the specified type."""
    topic = random.choice(TOPICS)
    date = random_date()
    people = random.sample(PEOPLE, min(5, len(PEOPLE)))
    
    if doc_type == "meeting_notes":
        title = f"{topic.title()} Discussion - {date}"
        content = DOC_TEMPLATES["meeting_notes"]["prefix"].format(
            topic=topic.title(),
            date=date,
            attendees=", ".join(people),
        )
        for section in DOC_TEMPLATES["meeting_notes"]["sections"]:
            content += section.format(
                content=generate_discussion_content(topic, people),
                action_items=generate_action_items(people),
                decisions=generate_decisions(),
            )
        
    elif doc_type == "email":
        sender = random.choice(PEOPLE)
        recipients = random.sample([p for p in PEOPLE if p != sender], random.randint(1, 4))
        email_content = generate_email_content(topic, sender)
        
        title = f"Re: {topic.title()} Update"
        content = DOC_TEMPLATES["email"]["prefix"].format(
            sender=sender,
            recipients=", ".join(recipients),
            subject=f"Re: {topic.title()} Update",
            date=date,
        )
        for section in DOC_TEMPLATES["email"]["sections"]:
            content += section.format(**email_content)
    
    elif doc_type == "strategy_doc":
        author = random.choice(PEOPLE)
        statuses = ["Draft", "In Review", "Approved", "Deprecated"]
        
        title = f"{topic.title()} Strategy"
        content = DOC_TEMPLATES["strategy_doc"]["prefix"].format(
            title=f"{topic.title()} Strategy",
            author=author,
            date=date,
            status=random.choice(statuses),
            summary=f"This document outlines the strategic approach to {topic} for the upcoming quarter. Key stakeholders include {random.choice(TEAMS)} and {random.choice(TEAMS)}.",
        )
        for section in DOC_TEMPLATES["strategy_doc"]["sections"]:
            content += section.format(
                background=f"The need for {topic} has become increasingly apparent as {random.choice(SERVICES)} faces {random.choice(CONCERNS)}. {random.choice(PEOPLE)} initially raised this concern in Q{random.randint(1,3)}.",
                approach=generate_discussion_content(topic, people),
                timeline=f"- Phase 1 (Week 1-2): Planning and requirements\n- Phase 2 (Week 3-6): Implementation\n- Phase 3 (Week 7-8): Testing and rollout",
                risks=f"- {random.choice(CONCERNS)} may impact timeline\n- Resource constraints in {random.choice(TEAMS)}\n- Dependencies on {random.choice(SERVICES)}",
            )
    
    elif doc_type == "incident_report":
        severity = random.choice(["SEV1", "SEV2", "SEV3"])
        duration = f"{random.randint(15, 180)} minutes"
        services = random_services(random.randint(1, 4))
        
        title = f"Incident: {random.choice(SERVICES)} {random.choice(CONCERNS).title()}"
        content = DOC_TEMPLATES["incident_report"]["prefix"].format(
            incident_title=f"{random.choice(SERVICES)} {severity}",
            severity=severity,
            date=date,
            duration=duration,
            services=services,
        )
        for section in DOC_TEMPLATES["incident_report"]["sections"]:
            content += section.format(
                timeline=generate_incident_timeline(),
                root_cause=f"{random.choice(CONCERNS).capitalize()} in {random.choice(SERVICES)} caused cascading failures affecting {services}.",
                resolution=f"The issue was resolved by {random.choice(['rolling back the deployment', 'increasing resource limits', 'restarting affected services', 'applying a hotfix'])}. {random.choice(PEOPLE)} led the incident response.",
                action_items=generate_action_items(people),
            )
    
    elif doc_type == "slack_export":
        channels = ["engineering-general", "platform-team", "incidents", "frontend-dev", "backend-dev", "devops", "random"]
        channel = random.choice(channels)
        
        title = f"Slack Export: #{channel} - {date}"
        content = DOC_TEMPLATES["slack_export"]["prefix"].format(
            channel=channel,
            date_range=f"{date} to {random_date(7)}",
        )
        for section in DOC_TEMPLATES["slack_export"]["sections"]:
            content += section.format(
                messages=generate_slack_messages(channel, date),
            )
    
    elif doc_type == "design_doc":
        author = random.choice(PEOPLE)
        reviewers = ", ".join(random.sample([p for p in PEOPLE if p != author], 3))
        statuses = ["Draft", "In Review", "Approved", "Implemented"]
        
        title = f"Design: {topic.title()} Implementation"
        content = DOC_TEMPLATES["design_doc"]["prefix"].format(
            title=f"{topic.title()} Implementation",
            author=author,
            reviewers=reviewers,
            status=random.choice(statuses),
            date=date,
            overview=f"This design document proposes changes to {random.choice(SERVICES)} to support {topic}. The goal is to address current {random.choice(CONCERNS)} and improve system reliability.",
        )
        for section in DOC_TEMPLATES["design_doc"]["sections"]:
            content += section.format(
                requirements=f"1. Support {topic} with minimal downtime\n2. Maintain backward compatibility\n3. Improve observability\n4. Meet {random.choice(TEAMS)} SLA requirements",
                design=generate_discussion_content(topic, people),
                alternatives=f"1. Use existing {random.choice(SERVICES)} infrastructure (rejected: doesn't scale)\n2. Third-party solution (rejected: cost prohibitive)\n3. Proposed approach (selected)",
                plan=f"- Week 1: Development environment setup\n- Week 2-3: Core implementation\n- Week 4: Integration testing with {random.choice(SERVICES)}\n- Week 5: Staged rollout",
            )
    
    elif doc_type == "retrospective":
        team = random.choice(TEAMS)
        facilitator = random.choice(PEOPLE)
        sprint = f"Sprint {random.randint(20, 50)}"
        
        title = f"{team} {sprint} Retrospective"
        content = DOC_TEMPLATES["retrospective"]["prefix"].format(
            sprint=sprint,
            date=date,
            facilitator=facilitator,
            team=team,
        )
        for section in DOC_TEMPLATES["retrospective"]["sections"]:
            content += section.format(
                good=f"- Successful deployment of {topic} changes\n- {random.choice(PEOPLE)} onboarding went smoothly\n- Reduced {random.choice(CONCERNS)} by 30%\n- Good collaboration with {random.choice(TEAMS)}",
                improve=f"- Need better documentation for {random.choice(SERVICES)}\n- {random.choice(CONCERNS)} slowed us down\n- Too many context switches\n- Dependencies on {random.choice(TEAMS)} not clearly communicated",
                actions=generate_action_items(people),
            )
    
    else:
        title = f"Document {index}"
        content = f"Generic document content about {topic}."
    
    return {
        "title": title,
        "content": content,
        "doc_type": doc_type,
        "date": date,
    }


def generate_scale_data(count: int, output_dir: Path):
    """Generate scaled synthetic documents."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc_types = list(DOC_TEMPLATES.keys())
    type_weights = [0.25, 0.20, 0.15, 0.15, 0.10, 0.10, 0.05]
    
    type_dirs = {}
    for doc_type in doc_types:
        type_dir = output_dir / doc_type
        type_dir.mkdir(exist_ok=True)
        type_dirs[doc_type] = type_dir
    
    print(f"Generating {count} documents in {output_dir}...")
    
    manifest = []
    
    for i in range(count):
        doc_type = random.choices(doc_types, weights=type_weights[:len(doc_types)])[0]
        doc = generate_document(doc_type, i)
        
        filename = f"{doc_type}_{i:04d}.md"
        filepath = type_dirs[doc_type] / filename
        
        with open(filepath, "w") as f:
            f.write(doc["content"])
        
        manifest.append({
            "index": i,
            "filename": str(filepath.relative_to(output_dir)),
            "title": doc["title"],
            "doc_type": doc_type,
            "date": doc["date"],
            "word_count": len(doc["content"].split()),
        })
        
        if (i + 1) % 50 == 0:
            print(f"  Generated {i + 1}/{count} documents...")
    
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    total_words = sum(m["word_count"] for m in manifest)
    print(f"\nGeneration complete!")
    print(f"  Documents: {count}")
    print(f"  Total words: {total_words:,}")
    print(f"  Avg words/doc: {total_words // count}")
    print(f"  Output: {output_dir}")
    print(f"  Manifest: {manifest_path}")
    
    type_counts = {}
    for m in manifest:
        type_counts[m["doc_type"]] = type_counts.get(m["doc_type"], 0) + 1
    
    print("\nDocument type distribution:")
    for doc_type, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {doc_type}: {cnt}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic documents for scale testing")
    parser.add_argument("--count", type=int, default=250, help="Number of documents to generate")
    parser.add_argument("--output", type=str, default="test_data/scale_docs", help="Output directory")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    generate_scale_data(args.count, output_dir)


if __name__ == "__main__":
    main()
