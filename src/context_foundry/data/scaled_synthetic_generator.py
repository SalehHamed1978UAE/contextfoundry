"""
Scaled Synthetic IT Operations Data Generator for MVP2.
Creates 1,000+ entities with realistic IT infrastructure patterns.

Target:
- 50+ services (microservices architecture)
- 30+ databases (various types)
- 40+ components (caches, queues, load balancers)
- 15 teams
- 200+ people
- 300+ incidents
- 50+ runbooks
- 5,000+ relationships
"""
import uuid
from datetime import datetime, timedelta
import random
from typing import List, Dict, Tuple, Optional
import hashlib


FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Edward", "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Raymond", "Christine", "Gregory", "Debra",
    "Frank", "Rachel", "Alexander", "Carolyn", "Patrick", "Janet", "Jack", "Catherine",
    "Wei", "Mei", "Amit", "Priya", "Raj", "Deepa", "Chen", "Liu", "Yuki", "Kenji",
    "Hiroshi", "Aiko", "Carlos", "Maria", "Diego", "Sofia", "Ahmed", "Fatima",
    "Omar", "Layla", "Ivan", "Olga", "Alexei", "Natasha", "Pierre", "Marie"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Chen", "Wang", "Li", "Zhang", "Liu", "Yang", "Kim",
    "Park", "Choi", "Patel", "Shah", "Singh", "Kumar", "Gupta", "Sharma",
    "Nakamura", "Tanaka", "Yamamoto", "Watanabe", "Suzuki", "Takahashi", "Ito", "Sato",
    "Mueller", "Schmidt", "Schneider", "Fischer", "Weber", "Wagner", "Becker", "Hoffmann",
    "O'Brien", "O'Connor", "Murphy", "Kelly", "Sullivan", "Ryan", "Walsh", "Byrne"
]

ROLES = [
    ("Engineer", 0.40),
    ("Senior Engineer", 0.25),
    ("Staff Engineer", 0.10),
    ("Tech Lead", 0.08),
    ("Engineering Manager", 0.05),
    ("Principal Engineer", 0.04),
    ("Director", 0.03),
    ("SRE", 0.03),
    ("DBA", 0.02),
]

EXPERTISE_DOMAINS = [
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Kafka", "RabbitMQ",
    "Kubernetes", "Docker", "AWS", "GCP", "Azure", "Terraform", "Ansible",
    "Python", "Go", "Java", "TypeScript", "Rust", "C++", "Ruby", "Scala",
    "React", "Vue", "Angular", "Node.js", "Django", "FastAPI", "Spring Boot",
    "GraphQL", "REST", "gRPC", "WebSocket", "HTTP/2",
    "Prometheus", "Grafana", "Datadog", "PagerDuty", "Splunk", "ELK",
    "OAuth", "JWT", "SAML", "SSO", "MFA", "IAM",
    "CI/CD", "Jenkins", "GitHub Actions", "ArgoCD", "Spinnaker",
    "Microservices", "Event-Driven", "CQRS", "Domain-Driven Design",
    "Machine Learning", "TensorFlow", "PyTorch", "MLOps",
    "Networking", "DNS", "Load Balancing", "CDN", "WAF"
]

DOMAINS = [
    {
        "name": "Platform",
        "prefix": "platform",
        "teams": ["Platform Core", "Platform Infrastructure", "Platform Data", "Platform Security"],
        "services": [
            ("Config Service", "SERVICE", "Centralized configuration management"),
            ("Feature Flags Service", "SERVICE", "Feature flag management and rollouts"),
            ("Secrets Manager", "SERVICE", "Secure secrets storage and retrieval"),
            ("Service Registry", "SERVICE", "Service discovery and registration"),
            ("API Gateway", "SERVICE", "Main API gateway and routing"),
            ("Load Balancer Controller", "COMPONENT", "Kubernetes ingress controller"),
            ("Certificate Manager", "SERVICE", "TLS certificate management"),
            ("DNS Service", "SERVICE", "Internal DNS resolution"),
            ("Rate Limiter Service", "SERVICE", "API rate limiting and throttling"),
            ("Health Check Service", "SERVICE", "Service health monitoring"),
            ("Deployment Service", "SERVICE", "Deployment orchestration"),
            ("Rollback Service", "SERVICE", "Automated rollback management"),
        ],
        "databases": [
            ("Config Database", "PostgreSQL", "Configuration storage"),
            ("Registry Database", "PostgreSQL", "Service registry data"),
            ("Platform Cache", "Redis", "Platform-wide caching"),
            ("Platform Events", "Kafka", "Platform event bus"),
            ("Rate Limit Store", "Redis", "Rate limiting counters"),
            ("Deployment Database", "PostgreSQL", "Deployment history"),
        ]
    },
    {
        "name": "Identity",
        "prefix": "identity",
        "teams": ["Identity Core", "Identity Security"],
        "services": [
            ("Auth Service", "SERVICE", "Authentication and token management"),
            ("User Service", "SERVICE", "User profile management"),
            ("Permission Service", "SERVICE", "Authorization and RBAC"),
            ("SSO Service", "SERVICE", "Single sign-on integration"),
            ("MFA Service", "SERVICE", "Multi-factor authentication"),
            ("OAuth Provider", "SERVICE", "OAuth2 authorization server"),
            ("Session Service", "SERVICE", "Session management"),
            ("Audit Service", "SERVICE", "Security audit logging"),
        ],
        "databases": [
            ("User Database", "PostgreSQL", "User accounts and profiles"),
            ("Session Cache", "Redis", "Active session storage"),
            ("Permission Database", "PostgreSQL", "RBAC permissions"),
            ("Audit Log Database", "PostgreSQL", "Security audit logs"),
            ("Auth Events", "Kafka", "Authentication event stream"),
        ]
    },
    {
        "name": "Payments",
        "prefix": "payments",
        "teams": ["Payments Core", "Payments Integrations", "Fraud Prevention"],
        "services": [
            ("Payment Service", "SERVICE", "Core payment processing"),
            ("Payment Gateway", "SERVICE", "Payment provider integrations"),
            ("Stripe Adapter", "SERVICE", "Stripe payment integration"),
            ("PayPal Adapter", "SERVICE", "PayPal payment integration"),
            ("Fraud Detection Service", "SERVICE", "Real-time fraud analysis"),
            ("Risk Scoring Service", "SERVICE", "Transaction risk assessment"),
            ("Refund Service", "SERVICE", "Refund processing"),
            ("Payout Service", "SERVICE", "Merchant payouts"),
            ("Reconciliation Service", "SERVICE", "Payment reconciliation"),
            ("Invoice Service", "SERVICE", "Invoice generation"),
        ],
        "databases": [
            ("Payments Database", "PostgreSQL", "Transaction records"),
            ("Fraud Database", "PostgreSQL", "Fraud detection models and rules"),
            ("Payments Cache", "Redis", "Payment session caching"),
            ("Payment Events", "Kafka", "Payment event stream"),
            ("Reconciliation Database", "PostgreSQL", "Reconciliation records"),
        ]
    },
    {
        "name": "Commerce",
        "prefix": "commerce",
        "teams": ["Commerce Core", "Catalog", "Checkout"],
        "services": [
            ("Checkout Service", "SERVICE", "Checkout flow orchestration"),
            ("Cart Service", "SERVICE", "Shopping cart management"),
            ("Pricing Service", "SERVICE", "Dynamic pricing engine"),
            ("Promotion Service", "SERVICE", "Discounts and promotions"),
            ("Tax Service", "SERVICE", "Tax calculation"),
            ("Inventory Service", "SERVICE", "Inventory management"),
            ("Product Catalog", "SERVICE", "Product information"),
            ("Search Service", "SERVICE", "Product search"),
            ("Recommendation Service", "SERVICE", "Product recommendations"),
        ],
        "databases": [
            ("Product Database", "PostgreSQL", "Product catalog"),
            ("Inventory Database", "PostgreSQL", "Inventory levels"),
            ("Cart Database", "Redis", "Shopping cart data"),
            ("Search Index", "Elasticsearch", "Product search index"),
            ("Recommendation Database", "MongoDB", "Recommendation models"),
            ("Commerce Events", "Kafka", "Commerce event stream"),
        ]
    },
    {
        "name": "Orders",
        "prefix": "orders",
        "teams": ["Order Management", "Fulfillment"],
        "services": [
            ("Order Service", "SERVICE", "Order lifecycle management"),
            ("Fulfillment Service", "SERVICE", "Order fulfillment orchestration"),
            ("Shipping Service", "SERVICE", "Shipping provider integration"),
            ("Returns Service", "SERVICE", "Returns processing"),
            ("Order Tracking", "SERVICE", "Shipment tracking"),
            ("Warehouse Service", "SERVICE", "Warehouse operations"),
        ],
        "databases": [
            ("Order Database", "PostgreSQL", "Order records"),
            ("Fulfillment Database", "PostgreSQL", "Fulfillment status"),
            ("Shipping Database", "PostgreSQL", "Shipping records"),
            ("Order Events", "Kafka", "Order event stream"),
        ]
    },
    {
        "name": "Notifications",
        "prefix": "notifications",
        "teams": ["Communications"],
        "services": [
            ("Notification Service", "SERVICE", "Notification orchestration"),
            ("Email Service", "SERVICE", "Email delivery"),
            ("SMS Service", "SERVICE", "SMS delivery"),
            ("Push Service", "SERVICE", "Push notification delivery"),
            ("Template Service", "SERVICE", "Message template management"),
            ("Preference Service", "SERVICE", "User notification preferences"),
        ],
        "databases": [
            ("Notification Database", "PostgreSQL", "Notification logs"),
            ("Template Database", "PostgreSQL", "Message templates"),
            ("Notification Queue", "RabbitMQ", "Notification delivery queue"),
        ]
    },
    {
        "name": "Analytics",
        "prefix": "analytics",
        "teams": ["Data Engineering", "Data Science"],
        "services": [
            ("Analytics Service", "SERVICE", "Analytics data collection"),
            ("Metrics Service", "SERVICE", "Business metrics"),
            ("Reporting Service", "SERVICE", "Report generation"),
            ("ETL Pipeline", "SERVICE", "Data transformation"),
            ("ML Platform", "SERVICE", "Machine learning platform"),
            ("A/B Testing Service", "SERVICE", "Experimentation platform"),
        ],
        "databases": [
            ("Analytics Database", "PostgreSQL", "Analytics data"),
            ("Data Warehouse", "PostgreSQL", "Data warehouse"),
            ("Metrics Database", "TimescaleDB", "Time series metrics"),
            ("ML Feature Store", "Redis", "ML feature storage"),
            ("Analytics Events", "Kafka", "Analytics event stream"),
        ]
    },
    {
        "name": "Support",
        "prefix": "support",
        "teams": ["Customer Support Engineering"],
        "services": [
            ("Ticket Service", "SERVICE", "Support ticket management"),
            ("Chat Service", "SERVICE", "Live chat support"),
            ("Knowledge Base", "SERVICE", "Help articles and FAQs"),
            ("Escalation Service", "SERVICE", "Ticket escalation"),
        ],
        "databases": [
            ("Ticket Database", "PostgreSQL", "Support tickets"),
            ("Knowledge Database", "PostgreSQL", "Knowledge articles"),
            ("Chat Database", "MongoDB", "Chat history"),
        ]
    },
    {
        "name": "Observability",
        "prefix": "observability",
        "teams": ["SRE", "DevOps"],
        "services": [
            ("Logging Service", "SERVICE", "Centralized logging"),
            ("Tracing Service", "SERVICE", "Distributed tracing"),
            ("Alerting Service", "SERVICE", "Alert management"),
            ("Status Page", "SERVICE", "Public status page"),
            ("Incident Service", "SERVICE", "Incident management"),
            ("On-Call Service", "SERVICE", "On-call scheduling"),
            ("Runbook Service", "SERVICE", "Automated runbook execution"),
            ("Chaos Engineering Service", "SERVICE", "Chaos testing orchestration"),
        ],
        "databases": [
            ("Log Storage", "Elasticsearch", "Log aggregation"),
            ("Trace Database", "PostgreSQL", "Trace data"),
            ("Alert Database", "PostgreSQL", "Alert rules and history"),
            ("Incident Database", "PostgreSQL", "Incident records"),
            ("Runbook Database", "PostgreSQL", "Runbook definitions and history"),
        ]
    },
    {
        "name": "Mobile",
        "prefix": "mobile",
        "teams": ["Mobile iOS", "Mobile Android", "Mobile Platform"],
        "services": [
            ("Mobile API Gateway", "SERVICE", "Mobile-specific API gateway"),
            ("Push Notification Broker", "SERVICE", "Mobile push notification routing"),
            ("App Config Service", "SERVICE", "Mobile app configuration"),
            ("App Update Service", "SERVICE", "App version and update management"),
            ("Mobile Analytics", "SERVICE", "Mobile-specific analytics"),
            ("Deep Link Service", "SERVICE", "Deep link handling"),
            ("Mobile Auth Service", "SERVICE", "Mobile-specific authentication"),
            ("Offline Sync Service", "SERVICE", "Mobile offline data synchronization"),
        ],
        "databases": [
            ("Mobile Config Database", "PostgreSQL", "Mobile app configurations"),
            ("Mobile Session Cache", "Redis", "Mobile session storage"),
            ("Mobile Events", "Kafka", "Mobile event stream"),
            ("App Version Database", "PostgreSQL", "App version history"),
        ]
    },
    {
        "name": "Vendor",
        "prefix": "vendor",
        "teams": ["Vendor Integrations", "Partner Engineering"],
        "services": [
            ("Stripe Integration", "SERVICE", "Stripe payment integration"),
            ("PayPal Integration", "SERVICE", "PayPal payment integration"),
            ("Twilio Integration", "SERVICE", "Twilio SMS/Voice integration"),
            ("SendGrid Integration", "SERVICE", "SendGrid email integration"),
            ("AWS SES Adapter", "SERVICE", "AWS SES email adapter"),
            ("Salesforce Connector", "SERVICE", "Salesforce CRM integration"),
            ("Zendesk Connector", "SERVICE", "Zendesk support integration"),
            ("Slack Integration", "SERVICE", "Slack notifications and workflows"),
            ("GitHub Integration", "SERVICE", "GitHub webhook handler"),
            ("PagerDuty Integration", "SERVICE", "PagerDuty incident integration"),
        ],
        "databases": [
            ("Vendor Credentials Vault", "PostgreSQL", "Vendor API credentials"),
            ("Integration Logs", "PostgreSQL", "Vendor integration logs"),
            ("Webhook Queue", "RabbitMQ", "Inbound webhook queue"),
            ("Vendor Events", "Kafka", "Vendor event stream"),
        ]
    },
    {
        "name": "Internal",
        "prefix": "internal",
        "teams": ["Internal Tools", "Developer Experience"],
        "services": [
            ("Admin Dashboard", "SERVICE", "Internal admin interface"),
            ("Employee Portal", "SERVICE", "Employee self-service portal"),
            ("Onboarding Service", "SERVICE", "Employee onboarding workflows"),
            ("Access Request Service", "SERVICE", "Access request management"),
            ("Audit Dashboard", "SERVICE", "Security audit dashboard"),
            ("Cost Tracker", "SERVICE", "Cloud cost tracking"),
            ("Documentation Portal", "SERVICE", "Internal documentation"),
            ("Developer Portal", "SERVICE", "API documentation and sandbox"),
        ],
        "databases": [
            ("Admin Database", "PostgreSQL", "Admin configurations"),
            ("Employee Database", "PostgreSQL", "Employee records"),
            ("Access Request Database", "PostgreSQL", "Access request records"),
            ("Cost Database", "PostgreSQL", "Cost tracking data"),
        ]
    },
    {
        "name": "Content",
        "prefix": "content",
        "teams": ["Content Engineering", "Media"],
        "services": [
            ("CMS Service", "SERVICE", "Content management system"),
            ("Media Service", "SERVICE", "Image and video processing"),
            ("CDN Manager", "SERVICE", "CDN configuration and purging"),
            ("Image Optimizer", "SERVICE", "Image optimization and resizing"),
            ("Video Transcoder", "SERVICE", "Video transcoding"),
            ("Asset Manager", "SERVICE", "Digital asset management"),
            ("SEO Service", "SERVICE", "SEO metadata management"),
        ],
        "databases": [
            ("Content Database", "PostgreSQL", "Content records"),
            ("Media Database", "PostgreSQL", "Media metadata"),
            ("Asset Storage", "MongoDB", "Asset metadata"),
            ("CDN Cache", "Redis", "CDN cache control"),
            ("Media Events", "Kafka", "Media processing events"),
        ]
    },
    {
        "name": "Compliance",
        "prefix": "compliance",
        "teams": ["Security", "Compliance Engineering"],
        "services": [
            ("GDPR Service", "SERVICE", "GDPR compliance automation"),
            ("Data Retention Service", "SERVICE", "Data retention policy enforcement"),
            ("Consent Manager", "SERVICE", "User consent management"),
            ("Audit Logger", "SERVICE", "Compliance audit logging"),
            ("Data Export Service", "SERVICE", "GDPR data export"),
            ("Data Deletion Service", "SERVICE", "GDPR right to deletion"),
            ("Encryption Service", "SERVICE", "Data encryption at rest"),
            ("Key Management Service", "SERVICE", "Cryptographic key management"),
        ],
        "databases": [
            ("Consent Database", "PostgreSQL", "User consent records"),
            ("Audit Log Database", "PostgreSQL", "Compliance audit logs"),
            ("Retention Policy Database", "PostgreSQL", "Retention policies"),
            ("Key Store", "PostgreSQL", "Encryption key metadata"),
        ]
    },
    {
        "name": "Marketing",
        "prefix": "marketing",
        "teams": ["Marketing Engineering"],
        "services": [
            ("Campaign Service", "SERVICE", "Marketing campaign management"),
            ("Email Marketing Service", "SERVICE", "Marketing email campaigns"),
            ("Referral Service", "SERVICE", "Referral program management"),
            ("Coupon Service", "SERVICE", "Coupon and discount management"),
            ("Loyalty Service", "SERVICE", "Loyalty program management"),
            ("Attribution Service", "SERVICE", "Marketing attribution tracking"),
            ("Lead Scoring Service", "SERVICE", "Lead scoring and qualification"),
        ],
        "databases": [
            ("Campaign Database", "PostgreSQL", "Campaign data"),
            ("Coupon Database", "PostgreSQL", "Coupon and discount codes"),
            ("Loyalty Database", "PostgreSQL", "Loyalty program data"),
            ("Attribution Database", "PostgreSQL", "Attribution data"),
            ("Marketing Events", "Kafka", "Marketing event stream"),
        ]
    },
    {
        "name": "Localization",
        "prefix": "localization",
        "teams": ["Localization Engineering"],
        "services": [
            ("Translation Service", "SERVICE", "Text translation management"),
            ("Currency Service", "SERVICE", "Currency conversion"),
            ("Timezone Service", "SERVICE", "Timezone handling"),
            ("Regional Config Service", "SERVICE", "Regional configuration"),
            ("Language Detection Service", "SERVICE", "Automatic language detection"),
        ],
        "databases": [
            ("Translation Database", "PostgreSQL", "Translation strings"),
            ("Currency Database", "PostgreSQL", "Currency exchange rates"),
            ("Regional Config Database", "PostgreSQL", "Regional configurations"),
        ]
    },
]

INCIDENT_TEMPLATES = [
    {
        "type": "database_failure",
        "patterns": [
            "{db} primary failover - {duration} minute outage",
            "{db} connection pool exhaustion",
            "{db} disk space critical - writes blocked",
            "{db} replication lag exceeded threshold",
            "{db} deadlock detected causing transaction failures",
            "{db} corrupted index requiring rebuild",
        ],
        "severity_weights": {"SEV1": 0.4, "SEV2": 0.4, "SEV3": 0.2},
    },
    {
        "type": "service_degradation",
        "patterns": [
            "{service} latency spike - p99 exceeded {value}ms",
            "{service} error rate elevated to {value}%",
            "{service} memory leak causing OOM crashes",
            "{service} CPU saturation at {value}%",
            "{service} thread pool exhaustion",
            "{service} circuit breaker open to {dependency}",
        ],
        "severity_weights": {"SEV1": 0.2, "SEV2": 0.5, "SEV3": 0.3},
    },
    {
        "type": "infrastructure",
        "patterns": [
            "Network partition in {region}",
            "Load balancer health check failures",
            "DNS resolution failures for {service}",
            "Certificate expiry on {service}",
            "Kubernetes pod eviction storm",
            "AWS API rate limiting",
        ],
        "severity_weights": {"SEV1": 0.5, "SEV2": 0.3, "SEV3": 0.2},
    },
    {
        "type": "security",
        "patterns": [
            "Elevated failed authentication attempts",
            "Suspicious API access pattern detected",
            "Token validation bypass vulnerability",
            "DDoS attack mitigated",
            "Unauthorized data access attempt",
        ],
        "severity_weights": {"SEV1": 0.6, "SEV2": 0.3, "SEV3": 0.1},
    },
    {
        "type": "deployment",
        "patterns": [
            "{service} deployment rollback required",
            "{service} config change caused failures",
            "Feature flag misconfiguration",
            "Database migration failure",
            "Canary deployment failed health checks",
        ],
        "severity_weights": {"SEV1": 0.1, "SEV2": 0.5, "SEV3": 0.4},
    },
]

RUNBOOK_TEMPLATES = [
    {
        "type": "database",
        "title": "{db} Emergency Procedures",
        "sections": [
            "Failover Procedure",
            "Connection Pool Recovery",
            "Disk Space Cleanup",
            "Replication Recovery",
            "Backup and Restore",
        ],
    },
    {
        "type": "service",
        "title": "{service} Incident Response",
        "sections": [
            "Health Check Verification",
            "Log Analysis",
            "Scaling Procedures",
            "Restart Procedures",
            "Rollback Steps",
        ],
    },
    {
        "type": "escalation",
        "title": "{team} Escalation Procedures",
        "sections": [
            "On-Call Contacts",
            "Escalation Matrix",
            "Communication Templates",
            "War Room Setup",
        ],
    },
]


class ScaledSyntheticGenerator:
    """Generates scaled synthetic IT operations data for MVP2."""
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.entity_id_map = {}
        self.used_names = set()
        
    def _generate_id(self, name: str) -> str:
        """Generate deterministic UUID from name for consistency."""
        hash_input = f"context_foundry:{name}"
        hash_bytes = hashlib.md5(hash_input.encode()).hexdigest()
        return str(uuid.UUID(hash_bytes))
    
    def _unique_person_name(self) -> str:
        """Generate unique person name."""
        for _ in range(100):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            name = f"{first} {last}"
            if name not in self.used_names:
                self.used_names.add(name)
                return name
        return f"Person_{len(self.used_names)}"
    
    def _select_role(self) -> str:
        """Select role based on distribution."""
        r = random.random()
        cumulative = 0
        for role, prob in ROLES:
            cumulative += prob
            if r < cumulative:
                return role
        return "Engineer"
    
    def _select_expertise(self, count: int = 3) -> List[str]:
        """Select random expertise areas."""
        return random.sample(EXPERTISE_DOMAINS, min(count, len(EXPERTISE_DOMAINS)))
    
    def generate_teams(self) -> List[Dict]:
        """Generate all teams from domain definitions."""
        teams = []
        for domain in DOMAINS:
            for team_name in domain["teams"]:
                team_id = self._generate_id(team_name)
                self.entity_id_map[team_name] = team_id
                teams.append({
                    "id": team_id,
                    "name": team_name,
                    "entity_type": "TEAM",
                    "properties": {
                        "domain": domain["name"],
                        "slack_channel": f"#{team_name.lower().replace(' ', '-')}",
                        "on_call_rotation": random.choice(["daily", "weekly"]),
                    },
                    "description": f"{team_name} - responsible for {domain['name'].lower()} domain services",
                })
        return teams
    
    def generate_people(self, teams: List[Dict], people_per_team_range: Tuple[int, int] = (8, 15)) -> List[Dict]:
        """Generate people for each team."""
        people = []
        for team in teams:
            team_size = random.randint(*people_per_team_range)
            team_people = []
            
            manager_created = False
            lead_created = False
            
            for i in range(team_size):
                name = self._unique_person_name()
                person_id = self._generate_id(name)
                self.entity_id_map[name] = person_id
                
                if not manager_created and random.random() < 0.15:
                    role = "Engineering Manager"
                    manager_created = True
                elif not lead_created and random.random() < 0.2:
                    role = "Tech Lead"
                    lead_created = True
                else:
                    role = self._select_role()
                
                expertise = self._select_expertise(random.randint(2, 5))
                
                email = f"{name.lower().replace(' ', '.')}@company.com"
                phone = f"+1-555-{random.randint(1000, 9999)}"
                
                person = {
                    "id": person_id,
                    "name": name,
                    "entity_type": "PERSON",
                    "properties": {
                        "role": role,
                        "team": team["name"],
                        "email": email,
                        "phone": phone,
                        "expertise": expertise,
                        "pagerduty": role in ["SRE", "Tech Lead", "Engineering Manager"],
                    },
                    "description": f"{name} - {role} on {team['name']}, expertise in {', '.join(expertise[:2])}",
                }
                people.append(person)
                team_people.append(person)
            
            if not manager_created and team_people:
                team_people[0]["properties"]["role"] = "Engineering Manager"
                team_people[0]["description"] = team_people[0]["description"].replace(
                    team_people[0]["properties"]["role"], "Engineering Manager"
                )
        
        return people
    
    def generate_services_and_components(self) -> Tuple[List[Dict], List[Dict]]:
        """Generate services and components from domain definitions."""
        services = []
        databases = []
        
        for domain in DOMAINS:
            for svc_name, svc_type, description in domain["services"]:
                svc_id = self._generate_id(svc_name)
                self.entity_id_map[svc_name] = svc_id
                
                entity = {
                    "id": svc_id,
                    "name": svc_name,
                    "entity_type": svc_type,
                    "properties": {
                        "domain": domain["name"],
                        "language": random.choice(["Python", "Go", "Java", "TypeScript", "Rust"]),
                        "tier": random.choice(["critical", "standard", "experimental"]) if svc_type == "SERVICE" else "infrastructure",
                        "repository": f"github.com/company/{svc_name.lower().replace(' ', '-')}",
                    },
                    "description": description,
                }
                services.append(entity)
            
            for db_name, db_type, description in domain["databases"]:
                db_id = self._generate_id(db_name)
                self.entity_id_map[db_name] = db_id
                
                if db_type in ["Redis", "Kafka", "RabbitMQ", "Elasticsearch"]:
                    entity_type = "COMPONENT"
                else:
                    entity_type = "DATABASE"
                
                entity = {
                    "id": db_id,
                    "name": db_name,
                    "entity_type": entity_type,
                    "properties": {
                        "domain": domain["name"],
                        "type": db_type,
                        "version": self._get_db_version(db_type),
                        "cluster": random.choice([True, False]),
                        "sla": f"99.{random.randint(9, 99)}%",
                    },
                    "description": description,
                }
                databases.append(entity)
        
        return services, databases
    
    def _get_db_version(self, db_type: str) -> str:
        """Get realistic version for database type."""
        versions = {
            "PostgreSQL": ["14.2", "15.1", "16.0"],
            "MySQL": ["8.0.32", "8.0.33"],
            "MongoDB": ["6.0", "7.0"],
            "Redis": ["7.0", "7.2"],
            "Elasticsearch": ["8.8", "8.10"],
            "Kafka": ["3.4", "3.5"],
            "RabbitMQ": ["3.12", "3.13"],
            "TimescaleDB": ["2.11", "2.12"],
        }
        return random.choice(versions.get(db_type, ["1.0"]))
    
    def generate_relationships(
        self, 
        teams: List[Dict], 
        people: List[Dict], 
        services: List[Dict], 
        databases: List[Dict]
    ) -> List[Dict]:
        """Generate all relationships between entities."""
        relationships = []
        
        for person in people:
            team_name = person["properties"]["team"]
            relationships.append(self._create_relationship(
                person["name"], team_name, "MEMBER_OF",
                f"{person['name']} is a member of {team_name}."
            ))
            
            role = person["properties"]["role"]
            if role in ["Tech Lead", "Engineering Manager", "Director"]:
                relationships.append(self._create_relationship(
                    person["name"], team_name, "MANAGES",
                    f"{person['name']} manages {team_name}."
                ))
        
        team_domains = {t["name"]: t["properties"]["domain"] for t in teams}
        for entity in services + databases:
            domain = entity["properties"]["domain"]
            owning_teams = [t["name"] for t in teams if t["properties"]["domain"] == domain]
            if owning_teams:
                primary_team = owning_teams[0]
                relationships.append(self._create_relationship(
                    primary_team, entity["name"], "OWNS",
                    f"{primary_team} owns and maintains {entity['name']}."
                ))
                
                for support_team in owning_teams[1:]:
                    if random.random() < 0.5:
                        relationships.append(self._create_relationship(
                            support_team, entity["name"], "SUPPORTS",
                            f"{support_team} provides support for {entity['name']}."
                        ))
        
        relationships.extend(self._generate_service_dependencies(services, databases))
        
        relationships.extend(self._generate_escalation_paths(people, teams))
        
        return relationships
    
    def _create_relationship(
        self, 
        source: str, 
        target: str, 
        rel_type: str, 
        source_sentence: str,
        confidence: float = None
    ) -> Dict:
        """Create a relationship dictionary."""
        if confidence is None:
            confidence = round(random.uniform(0.85, 0.98), 2)
        
        return {
            "id": str(uuid.uuid4()),
            "source_name": source,
            "target_name": target,
            "relationship_type": rel_type,
            "confidence": confidence,
            "source_sentence": source_sentence,
        }
    
    def _generate_service_dependencies(
        self, 
        services: List[Dict], 
        databases: List[Dict]
    ) -> List[Dict]:
        """Generate realistic service dependency graph."""
        relationships = []
        
        service_map = {s["name"]: s for s in services}
        db_map = {d["name"]: d for d in databases}
        
        for service in services:
            svc_domain = service["properties"]["domain"]
            
            for db in databases:
                if db["properties"]["domain"] == svc_domain:
                    if random.random() < 0.6:
                        relationships.append(self._create_relationship(
                            service["name"], db["name"], "DEPENDS_ON",
                            f"{service['name']} uses {db['name']} for data storage.",
                            round(random.uniform(0.90, 0.98), 2)
                        ))
            
            if "Auth" not in service["name"] and random.random() < 0.7:
                auth_services = [s["name"] for s in services if "Auth" in s["name"] or "Permission" in s["name"]]
                if auth_services:
                    auth_svc = random.choice(auth_services)
                    relationships.append(self._create_relationship(
                        service["name"], auth_svc, "DEPENDS_ON",
                        f"{service['name']} validates requests through {auth_svc}.",
                        round(random.uniform(0.85, 0.95), 2)
                    ))
            
            if "API Gateway" not in service["name"] and random.random() < 0.3:
                gateway = next((s for s in services if "API Gateway" in s["name"]), None)
                if gateway:
                    relationships.append(self._create_relationship(
                        "API Gateway", service["name"], "DEPENDS_ON",
                        f"API Gateway routes traffic to {service['name']}.",
                        round(random.uniform(0.80, 0.95), 2)
                    ))
            
            config_service = next((s for s in services if "Config Service" in s["name"]), None)
            if config_service and service["name"] != "Config Service" and random.random() < 0.4:
                relationships.append(self._create_relationship(
                    service["name"], "Config Service", "DEPENDS_ON",
                    f"{service['name']} retrieves configuration from Config Service.",
                    round(random.uniform(0.75, 0.90), 2)
                ))
        
        domain_service_map = {}
        for service in services:
            domain = service["properties"]["domain"]
            if domain not in domain_service_map:
                domain_service_map[domain] = []
            domain_service_map[domain].append(service["name"])
        
        cross_domain_deps = [
            ("Commerce", "Payments"),
            ("Commerce", "Identity"),
            ("Orders", "Commerce"),
            ("Orders", "Payments"),
            ("Orders", "Notifications"),
            ("Notifications", "Identity"),
            ("Analytics", "Commerce"),
            ("Analytics", "Payments"),
            ("Support", "Identity"),
            ("Support", "Orders"),
        ]
        
        for source_domain, target_domain in cross_domain_deps:
            if source_domain in domain_service_map and target_domain in domain_service_map:
                source_svcs = domain_service_map[source_domain]
                target_svcs = domain_service_map[target_domain]
                
                for _ in range(min(3, len(source_svcs), len(target_svcs))):
                    src = random.choice(source_svcs)
                    tgt = random.choice(target_svcs)
                    if src != tgt:
                        relationships.append(self._create_relationship(
                            src, tgt, "DEPENDS_ON",
                            f"{src} integrates with {tgt} for {target_domain.lower()} functionality.",
                            round(random.uniform(0.75, 0.92), 2)
                        ))
        
        return relationships
    
    def _generate_escalation_paths(
        self, 
        people: List[Dict], 
        teams: List[Dict]
    ) -> List[Dict]:
        """Generate escalation paths between people."""
        relationships = []
        
        team_people = {}
        for person in people:
            team = person["properties"]["team"]
            if team not in team_people:
                team_people[team] = {"engineers": [], "leads": [], "managers": []}
            
            role = person["properties"]["role"]
            if role in ["Engineering Manager", "Director"]:
                team_people[team]["managers"].append(person)
            elif role in ["Tech Lead", "Staff Engineer", "Principal Engineer"]:
                team_people[team]["leads"].append(person)
            else:
                team_people[team]["engineers"].append(person)
        
        for team_name, members in team_people.items():
            for engineer in members["engineers"]:
                if members["leads"]:
                    lead = random.choice(members["leads"])
                    relationships.append(self._create_relationship(
                        engineer["name"], lead["name"], "ESCALATES_TO",
                        f"For urgent issues, {engineer['name']} escalates to {lead['name']}.",
                        0.90
                    ))
            
            for lead in members["leads"]:
                if members["managers"]:
                    manager = random.choice(members["managers"])
                    relationships.append(self._create_relationship(
                        lead["name"], manager["name"], "ESCALATES_TO",
                        f"For SEV1/SEV2 incidents, {lead['name']} escalates to {manager['name']}.",
                        0.95
                    ))
        
        sre_team = team_people.get("SRE", {})
        sre_leads = sre_team.get("leads", []) + sre_team.get("managers", [])
        if sre_leads:
            sre_lead = sre_leads[0]
            for team_name, members in team_people.items():
                if team_name != "SRE" and members["managers"]:
                    manager = members["managers"][0]
                    relationships.append(self._create_relationship(
                        manager["name"], sre_lead["name"], "ESCALATES_TO",
                        f"For infrastructure incidents, {manager['name']} coordinates with {sre_lead['name']}.",
                        0.85
                    ))
        
        return relationships
    
    def generate_incidents(
        self, 
        services: List[Dict], 
        databases: List[Dict],
        people: List[Dict],
        count: int = 300
    ) -> Tuple[List[Dict], List[Dict]]:
        """Generate incident records and their relationships."""
        incidents = []
        incident_relationships = []
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 11, 30)
        
        all_entities = services + databases
        
        for i in range(count):
            template = random.choice(INCIDENT_TEMPLATES)
            pattern = random.choice(template["patterns"])
            
            entity = random.choice(all_entities)
            
            severity_r = random.random()
            cumulative = 0
            severity = "SEV3"
            for sev, prob in template["severity_weights"].items():
                cumulative += prob
                if severity_r < cumulative:
                    severity = sev
                    break
            
            title = pattern.format(
                service=entity["name"],
                db=entity["name"],
                dependency=random.choice(all_entities)["name"],
                region=random.choice(["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]),
                value=random.randint(90, 500),
                duration=random.randint(5, 120),
            )
            
            incident_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
            duration = random.randint(5, 180)
            
            incident_id = f"INC-2024-{i+1:04d}"
            db_id = self._generate_id(incident_id)
            
            incident = {
                "id": db_id,
                "name": f"{incident_id}: {title}",
                "entity_type": "INCIDENT",
                "properties": {
                    "external_id": incident_id,
                    "severity": severity,
                    "status": random.choice(["resolved", "resolved", "resolved", "mitigated"]),
                    "duration_minutes": duration,
                    "date": incident_date.strftime("%Y-%m-%d"),
                    "type": template["type"],
                },
                "description": f"{severity} incident: {title}. Duration: {duration} minutes.",
            }
            incidents.append(incident)
            
            incident_relationships.append(self._create_relationship(
                incident["name"], entity["name"], "AFFECTS",
                f"{incident_id} affected {entity['name']}.",
                0.95
            ))
            
            domain = entity["properties"].get("domain", "Platform")
            domain_people = [p for p in people if any(t["properties"]["domain"] == domain for t in self.generate_teams() if t["name"] == p["properties"]["team"])]
            
            if not domain_people:
                domain_people = people
            
            leads_managers = [p for p in domain_people if p["properties"]["role"] in ["Tech Lead", "Engineering Manager", "SRE"]]
            if leads_managers:
                resolver = random.choice(leads_managers)
            else:
                resolver = random.choice(domain_people)
            
            incident_relationships.append(self._create_relationship(
                incident["name"], resolver["name"], "RESOLVED_BY",
                f"{incident_id} was resolved by {resolver['name']}.",
                0.90
            ))
            
            if random.random() < 0.3:
                caused_by = random.choice(all_entities)
                if caused_by["name"] != entity["name"]:
                    incident_relationships.append(self._create_relationship(
                        incident["name"], caused_by["name"], "CAUSED_BY",
                        f"{incident_id} was caused by issues in {caused_by['name']}.",
                        round(random.uniform(0.70, 0.90), 2)
                    ))
        
        return incidents, incident_relationships
    
    def generate_runbooks(
        self, 
        services: List[Dict], 
        databases: List[Dict],
        teams: List[Dict]
    ) -> List[Dict]:
        """Generate runbook documents."""
        runbooks = []
        
        for db in databases:
            if db["entity_type"] == "DATABASE":
                template = random.choice([t for t in RUNBOOK_TEMPLATES if t["type"] == "database"])
                title = template["title"].format(db=db["name"])
                
                content_parts = [f"# {title}\n\n"]
                for section in template["sections"]:
                    content_parts.append(f"## {section}\n\n")
                    content_parts.append(f"Standard operating procedure for {db['name']} {section.lower()}.\n\n")
                    content_parts.append(f"1. Verify {db['name']} status using monitoring dashboard\n")
                    content_parts.append(f"2. Check {db['name']} logs for errors\n")
                    content_parts.append(f"3. Execute recovery procedure as documented\n")
                    content_parts.append(f"4. Verify recovery and notify stakeholders\n\n")
                
                runbooks.append({
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "content": "".join(content_parts),
                    "document_type": "RUNBOOK",
                    "source_authority": 0.95,
                    "entities_mentioned": [db["name"]],
                })
        
        for service in services[:20]:
            template = random.choice([t for t in RUNBOOK_TEMPLATES if t["type"] == "service"])
            title = template["title"].format(service=service["name"])
            
            content_parts = [f"# {title}\n\n"]
            for section in template["sections"]:
                content_parts.append(f"## {section}\n\n")
                content_parts.append(f"Procedure for {service['name']} {section.lower()}.\n\n")
            
            runbooks.append({
                "id": str(uuid.uuid4()),
                "title": title,
                "content": "".join(content_parts),
                "document_type": "RUNBOOK",
                "source_authority": 0.90,
                "entities_mentioned": [service["name"]],
            })
        
        for team in teams[:10]:
            template = random.choice([t for t in RUNBOOK_TEMPLATES if t["type"] == "escalation"])
            title = template["title"].format(team=team["name"])
            
            content_parts = [f"# {title}\n\n"]
            for section in template["sections"]:
                content_parts.append(f"## {section}\n\n")
                content_parts.append(f"Escalation procedure for {team['name']}.\n\n")
            
            runbooks.append({
                "id": str(uuid.uuid4()),
                "title": title,
                "content": "".join(content_parts),
                "document_type": "RUNBOOK",
                "source_authority": 0.90,
                "entities_mentioned": [team["name"]],
            })
        
        return runbooks
    
    def generate_rules(self) -> List[Dict]:
        """Generate symbolic rules for the system."""
        rules = [
            {
                "id": str(uuid.uuid4()),
                "name": "sev1_requires_escalation",
                "rule_type": "ESCALATION_POLICY",
                "condition": "incident.severity == 'SEV1'",
                "action": "require_escalation_to_management",
                "priority": 1,
                "description": "All SEV1 incidents must be escalated to engineering management within 15 minutes."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "sev2_requires_oncall",
                "rule_type": "ESCALATION_POLICY",
                "condition": "incident.severity == 'SEV2'",
                "action": "page_oncall_engineer",
                "priority": 2,
                "description": "All SEV2 incidents require immediate on-call engineer engagement."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "critical_service_sla",
                "rule_type": "INVARIANT",
                "condition": "service.tier == 'critical'",
                "action": "enforce_99.9_sla",
                "priority": 1,
                "description": "Critical tier services must maintain 99.9% availability SLA."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "database_failover_required",
                "rule_type": "SAFETY_CHECK",
                "condition": "database.type in ['PostgreSQL', 'MySQL'] AND database.primary == True",
                "action": "require_replica",
                "priority": 1,
                "description": "Primary databases must have at least one replica for failover."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "pci_data_encryption",
                "rule_type": "INVARIANT",
                "condition": "service.domain == 'Payments'",
                "action": "require_encryption_at_rest",
                "priority": 1,
                "description": "All payment data must be encrypted at rest and in transit."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "auth_required_for_pii",
                "rule_type": "SAFETY_CHECK",
                "condition": "service.handles_pii == True",
                "action": "require_auth_service_dependency",
                "priority": 1,
                "description": "Services handling PII must authenticate through Auth Service."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "incident_postmortem_required",
                "rule_type": "VALIDATION",
                "condition": "incident.severity in ['SEV1', 'SEV2'] AND incident.status == 'resolved'",
                "action": "require_postmortem_within_72h",
                "priority": 2,
                "description": "SEV1 and SEV2 incidents require postmortem within 72 hours."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "deployment_approval_required",
                "rule_type": "SAFETY_CHECK",
                "condition": "deployment.environment == 'production' AND service.tier == 'critical'",
                "action": "require_tech_lead_approval",
                "priority": 1,
                "description": "Production deployments to critical services require tech lead approval."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "sre_oncall_for_infra",
                "rule_type": "ESCALATION_POLICY",
                "condition": "incident.type == 'infrastructure'",
                "action": "include_sre_oncall",
                "priority": 1,
                "description": "Infrastructure incidents must include SRE on-call."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "cross_domain_change_review",
                "rule_type": "VALIDATION",
                "condition": "change.affects_domains.count > 1",
                "action": "require_cross_team_review",
                "priority": 2,
                "description": "Changes affecting multiple domains require review from each domain team."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "security_incident_ciso",
                "rule_type": "ESCALATION_POLICY",
                "condition": "incident.type == 'security'",
                "action": "notify_security_team",
                "priority": 1,
                "description": "Security incidents must be immediately reported to the security team."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "customer_data_access_audit",
                "rule_type": "INVARIANT",
                "condition": "access.data_type == 'customer_pii'",
                "action": "log_to_audit_trail",
                "priority": 1,
                "description": "All access to customer PII must be logged to audit trail."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "dependency_update_testing",
                "rule_type": "VALIDATION",
                "condition": "change.type == 'dependency_update'",
                "action": "require_integration_tests",
                "priority": 2,
                "description": "Dependency updates require passing integration tests."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "canary_deployment_critical",
                "rule_type": "SAFETY_CHECK",
                "condition": "deployment.service.tier == 'critical'",
                "action": "require_canary_phase",
                "priority": 1,
                "description": "Critical service deployments must use canary deployment strategy."
            },
            {
                "id": str(uuid.uuid4()),
                "name": "backup_verification_weekly",
                "rule_type": "INVARIANT",
                "condition": "database.type in ['PostgreSQL', 'MySQL']",
                "action": "verify_backup_weekly",
                "priority": 2,
                "description": "Database backups must be verified weekly through restore testing."
            },
        ]
        
        return rules
    
    def generate(self) -> Dict:
        """Generate complete scaled synthetic dataset."""
        teams = self.generate_teams()
        
        people = self.generate_people(teams)
        
        services, databases = self.generate_services_and_components()
        
        relationships = self.generate_relationships(teams, people, services, databases)
        
        incidents, incident_relationships = self.generate_incidents(
            services, databases, people, count=400
        )
        relationships.extend(incident_relationships)
        
        runbooks = self.generate_runbooks(services, databases, teams)
        
        rules = self.generate_rules()
        
        all_entities = teams + people + services + databases + incidents
        
        return {
            "entities": all_entities,
            "relationships": relationships,
            "documents": runbooks,
            "rules": rules,
            "metadata": {
                "entity_count": len(all_entities),
                "relationship_count": len(relationships),
                "document_count": len(runbooks),
                "rule_count": len(rules),
                "teams": len(teams),
                "people": len(people),
                "services": len(services),
                "databases": len(databases),
                "incidents": len(incidents),
                "generated_at": datetime.now().isoformat(),
                "generator_version": "2.0.0",
            }
        }


def generate_scaled_synthetic_data(seed: int = 42) -> Dict:
    """Generate scaled synthetic IT operations data for MVP2."""
    generator = ScaledSyntheticGenerator(seed=seed)
    return generator.generate()


if __name__ == "__main__":
    data = generate_scaled_synthetic_data()
    
    print("\n" + "="*60)
    print("SCALED SYNTHETIC DATA GENERATION COMPLETE")
    print("="*60)
    
    meta = data["metadata"]
    print(f"\nTotal Entities: {meta['entity_count']}")
    print(f"  - Teams: {meta['teams']}")
    print(f"  - People: {meta['people']}")
    print(f"  - Services: {meta['services']}")
    print(f"  - Databases: {meta['databases']}")
    print(f"  - Incidents: {meta['incidents']}")
    print(f"\nRelationships: {meta['relationship_count']}")
    print(f"Documents: {meta['document_count']}")
    print(f"Rules: {meta['rule_count']}")
    print("="*60)
