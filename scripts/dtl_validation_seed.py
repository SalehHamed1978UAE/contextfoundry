#!/usr/bin/env python3
"""
DTL Validation Pack - Phase 1: Seed 50 Golden Traces
Inserts 25 Ops + 25 Commercial decisions with evidence into TENANT_A
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.decision_trace_layer.agent_logger import AgentDecisionLogger

TENANT_A = "8eee325b-ba3b-447e-9ee7-6d66085ead5f"

OPS_DECISIONS = [
    {
        "summary": "Bypassed load balancer during auth service outage to restore user access",
        "choice": {"action": "bypass_lb", "service": "auth", "duration_minutes": 45},
        "rationale": "Auth service was unreachable via LB due to health check failures. Direct routing to healthy backend restored 98% of user sessions. LB was causing false negatives on health probes.",
        "evidence": {"evidence_type": "incident_log", "excerpt": "SEV1 incident INC-2024-0891: Auth service outage at 14:32 UTC. Health checks failing despite backend healthy. Direct routing bypassed LB at 14:47 UTC, restoring service."},
        "entities": [{"entity_id": "auth-service", "role": "subject"}, {"entity_id": "load-balancer-01", "role": "affected"}]
    },
    {
        "summary": "Rolled back deployment v2.4.1 due to 500 error spike exceeding 5% threshold",
        "choice": {"action": "rollback", "from_version": "2.4.1", "to_version": "2.4.0", "error_rate_peak": 0.12},
        "rationale": "Deployment triggered 12% 500 error rate within 5 minutes. Exceeded 5% rollback threshold. Root cause: database migration timing issue.",
        "evidence": {"evidence_type": "monitoring_alert", "excerpt": "Datadog alert: 500 error rate exceeded 5% threshold at 09:15 UTC. Peak 12.3% at 09:18 UTC. Auto-rollback initiated at 09:20 UTC."},
        "entities": [{"entity_id": "payment-service", "role": "subject"}, {"entity_id": "v2.4.1", "role": "affected"}]
    },
    {
        "summary": "Disabled feature flag 'new-checkout-flow' to stop cart abandonment spike",
        "choice": {"action": "disable_feature_flag", "flag": "new-checkout-flow", "impact": "reverted to legacy checkout"},
        "rationale": "New checkout flow caused 40% increase in cart abandonment. A/B test showed 15% conversion drop. Disabled flag pending UX investigation.",
        "evidence": {"evidence_type": "analytics_report", "excerpt": "Amplitude report: Cart abandonment rate 67% (up from 48%) for users in new-checkout-flow treatment group. Conversion rate 8.5% vs 10% control."},
        "entities": [{"entity_id": "checkout-service", "role": "subject"}, {"entity_id": "feature-flag-system", "role": "related"}]
    },
    {
        "summary": "Accepted risk: Skipped SOC2 audit control CC7.1 during production incident response",
        "choice": {"action": "skip_control", "control": "CC7.1", "justification": "incident_response", "risk_accepted_by": "ciso"},
        "rationale": "During SEV1 incident, normal change approval process (CC7.1) was bypassed to deploy hotfix. Risk accepted by CISO with post-incident review scheduled.",
        "evidence": {"evidence_type": "approval_log", "excerpt": "Emergency change EC-2024-0156: CISO approved bypass of CC7.1 at 03:45 UTC for critical production fix. Post-incident review scheduled for 48h."},
        "entities": [{"entity_id": "soc2-compliance", "role": "related"}, {"entity_id": "change-management", "role": "subject"}]
    },
    {
        "summary": "Increased API timeout from 5s to 15s to stabilize payment processing during peak",
        "choice": {"action": "increase_timeout", "service": "payment-api", "from_seconds": 5, "to_seconds": 15},
        "rationale": "Black Friday traffic caused downstream payment provider latency. Timeout increase reduced failed transactions by 60%. Temporary measure until provider scales.",
        "evidence": {"evidence_type": "performance_log", "excerpt": "Payment API P99 latency 8.2s during peak (normal: 1.2s). Timeout failures: 2,340 in 15 minutes. After timeout increase: 89 failures in next 15 minutes."},
        "entities": [{"entity_id": "payment-api", "role": "subject"}, {"entity_id": "stripe-integration", "role": "related"}]
    },
    {
        "summary": "Enabled rate limiting on public API due to suspected DDoS attack",
        "choice": {"action": "enable_rate_limit", "limit": "100 req/min/ip", "duration": "2 hours"},
        "rationale": "Traffic spike from 50K to 2M requests/minute. 80% from 50 IPs. Rate limiting reduced malicious traffic while maintaining legitimate access.",
        "evidence": {"evidence_type": "security_alert", "excerpt": "Cloudflare alert: Anomalous traffic pattern detected. 2.1M requests/minute from 50 source IPs. Bot score 92%. Rate limiting applied at 16:45 UTC."},
        "entities": [{"entity_id": "public-api", "role": "subject"}, {"entity_id": "cloudflare", "role": "related"}]
    },
    {
        "summary": "Increased database connection pool from 50 to 200 connections during traffic surge",
        "choice": {"action": "increase_pool_size", "service": "primary-db", "from": 50, "to": 200},
        "rationale": "Connection pool exhaustion causing 502 errors. Surge from viral marketing campaign. Pool increase resolved bottleneck within 2 minutes.",
        "evidence": {"evidence_type": "monitoring_alert", "excerpt": "PgBouncer: Connection pool exhausted. 50/50 connections in use. 847 requests queued. After increase: 0 queued, P99 latency dropped from 12s to 0.8s."},
        "entities": [{"entity_id": "postgresql-primary", "role": "subject"}, {"entity_id": "pgbouncer", "role": "related"}]
    },
    {
        "summary": "Disabled Redis cache to fix stale authentication tokens causing login failures",
        "choice": {"action": "disable_cache", "cache": "auth-token-cache", "duration": "30 minutes"},
        "rationale": "Cache invalidation bug caused stale tokens to persist. Disabling cache forced fresh token validation, resolving 100% of login failures.",
        "evidence": {"evidence_type": "incident_log", "excerpt": "INC-2024-1023: Users unable to login with valid credentials. Root cause: Redis cache serving expired JWT signatures. Cache disabled at 11:20 UTC."},
        "entities": [{"entity_id": "redis-auth-cache", "role": "subject"}, {"entity_id": "auth-service", "role": "related"}]
    },
    {
        "summary": "Escalated to VP Engineering: Database corruption detected in production",
        "choice": {"action": "escalate", "level": "vp_engineering", "severity": "SEV0", "reason": "data_integrity_risk"},
        "rationale": "Detected 0.01% of user records with corrupted preference data. Potential for broader impact. Escalated for executive decision on customer notification.",
        "evidence": {"evidence_type": "escalation_log", "excerpt": "Escalation ESC-2024-0089: Data integrity issue detected. 1,247 user records affected. VP Engineering notified at 08:00 UTC for executive decision."},
        "entities": [{"entity_id": "user-preferences-db", "role": "subject"}, {"entity_id": "vp-engineering", "role": "approver"}]
    },
    {
        "summary": "Applied temporary workaround for memory leak instead of permanent fix during incident",
        "choice": {"action": "apply_workaround", "workaround": "scheduled_restart", "interval": "4 hours", "permanent_fix_eta": "72 hours"},
        "rationale": "Memory leak in notification service. Permanent fix requires refactor. Workaround: restart pods every 4 hours. Acceptable trade-off for incident resolution.",
        "evidence": {"evidence_type": "incident_log", "excerpt": "INC-2024-1156: Memory leak in notification-service. Heap grows from 512MB to 4GB in 6 hours. Workaround approved: pod restart every 4 hours until patch deployed."},
        "entities": [{"entity_id": "notification-service", "role": "subject"}, {"entity_id": "kubernetes", "role": "related"}]
    },
    {
        "summary": "Switched to backup DNS provider after primary DNS outage",
        "choice": {"action": "failover_dns", "from": "route53", "to": "cloudflare_dns", "propagation_time": "15 minutes"},
        "rationale": "Route53 experiencing regional outage. Failover to Cloudflare DNS restored service for 95% of users within 15 minutes.",
        "evidence": {"evidence_type": "incident_log", "excerpt": "AWS Route53 outage in us-east-1 at 04:30 UTC. DNS resolution failing for 40% of requests. Failover to Cloudflare DNS completed at 04:45 UTC."},
        "entities": [{"entity_id": "route53", "role": "subject"}, {"entity_id": "cloudflare-dns", "role": "related"}]
    },
    {
        "summary": "Enabled circuit breaker on inventory service after cascading failure",
        "choice": {"action": "enable_circuit_breaker", "service": "inventory-api", "threshold": "50% failure rate", "timeout": "30 seconds"},
        "rationale": "Inventory service failures cascading to checkout. Circuit breaker prevents cascade, returns cached inventory data during outage.",
        "evidence": {"evidence_type": "monitoring_alert", "excerpt": "Hystrix: Inventory API failure rate 67%. Circuit opened at 12:15 UTC. Cached inventory served for 847 requests. No checkout impact."},
        "entities": [{"entity_id": "inventory-service", "role": "subject"}, {"entity_id": "checkout-service", "role": "related"}]
    },
    {
        "summary": "Terminated runaway query consuming 90% of database CPU",
        "choice": {"action": "kill_query", "query_id": "pg_stat_activity_pid_12847", "cpu_usage": 0.90, "duration": "45 minutes"},
        "rationale": "Unoptimized analytics query blocked all other transactions. Immediate termination restored service. Query author notified for optimization.",
        "evidence": {"evidence_type": "performance_log", "excerpt": "PostgreSQL: PID 12847 consuming 90% CPU for 45 minutes. Query: SELECT * FROM orders JOIN... (full table scan). Terminated at 15:30 UTC."},
        "entities": [{"entity_id": "postgresql-primary", "role": "subject"}, {"entity_id": "analytics-team", "role": "related"}]
    },
    {
        "summary": "Enabled maintenance mode during database migration",
        "choice": {"action": "enable_maintenance_mode", "duration_minutes": 30, "affected_services": ["checkout", "orders", "inventory"]},
        "rationale": "Schema migration requires exclusive lock. 30-minute maintenance window scheduled during lowest traffic period (2AM-3AM UTC).",
        "evidence": {"evidence_type": "change_log", "excerpt": "CHG-2024-0445: Maintenance window 02:00-02:30 UTC. Database migration for orders table partitioning. All write operations suspended."},
        "entities": [{"entity_id": "orders-database", "role": "subject"}, {"entity_id": "checkout-service", "role": "affected"}]
    },
    {
        "summary": "Scaled Kubernetes pods from 10 to 50 during flash sale event",
        "choice": {"action": "scale_pods", "service": "product-catalog", "from_replicas": 10, "to_replicas": 50},
        "rationale": "Flash sale expected 10x normal traffic. Pre-emptive scaling prevented any performance degradation. Returned to normal scale after 4 hours.",
        "evidence": {"evidence_type": "capacity_plan", "excerpt": "Flash sale capacity plan: Product catalog scaled to 50 pods at 08:55 UTC, 5 minutes before sale start. Peak traffic: 847K requests/minute handled without errors."},
        "entities": [{"entity_id": "product-catalog", "role": "subject"}, {"entity_id": "kubernetes", "role": "related"}]
    },
    {
        "summary": "Blocked suspicious IP range after detecting credential stuffing attack",
        "choice": {"action": "block_ip_range", "range": "185.234.0.0/16", "duration": "permanent", "reason": "credential_stuffing"},
        "rationale": "2.3M failed login attempts from IP range in 1 hour. Known botnet. Permanent block applied after security team review.",
        "evidence": {"evidence_type": "security_alert", "excerpt": "Security: Credential stuffing attack detected. 2.3M failed logins from 185.234.0.0/16. 0 successful. IP range blocked at 19:45 UTC."},
        "entities": [{"entity_id": "auth-service", "role": "subject"}, {"entity_id": "security-team", "role": "approver"}]
    },
    {
        "summary": "Enabled read replica for reporting queries to reduce primary load",
        "choice": {"action": "route_to_replica", "query_type": "reporting", "replica": "postgres-replica-02"},
        "rationale": "Reporting queries consuming 40% of primary CPU. Routing to replica freed primary for transactional workload. No data freshness issues (5s lag).",
        "evidence": {"evidence_type": "performance_log", "excerpt": "Primary CPU: 85% (40% from reporting). After replica routing: Primary CPU 45%. Replica lag: 5 seconds average."},
        "entities": [{"entity_id": "postgresql-primary", "role": "subject"}, {"entity_id": "postgresql-replica", "role": "related"}]
    },
    {
        "summary": "Implemented request queuing during API overload",
        "choice": {"action": "enable_queuing", "queue_size": 10000, "timeout": "60 seconds"},
        "rationale": "API receiving 3x capacity. Rather than dropping requests, queuing allows graceful degradation. Users see delayed but successful responses.",
        "evidence": {"evidence_type": "capacity_log", "excerpt": "API capacity: 5000 req/s. Incoming: 15000 req/s. Queue enabled: 10000 requests buffered. P99 latency increased from 200ms to 45s but 0 errors."},
        "entities": [{"entity_id": "api-gateway", "role": "subject"}, {"entity_id": "queue-service", "role": "related"}]
    },
    {
        "summary": "Rotated compromised API key after security incident",
        "choice": {"action": "rotate_key", "key_type": "stripe_api_key", "reason": "potential_compromise"},
        "rationale": "API key found in public GitHub repo. Immediate rotation. No unauthorized transactions detected. Developer education initiated.",
        "evidence": {"evidence_type": "security_incident", "excerpt": "SEC-2024-0034: Stripe API key exposed in public repo. Key rotated at 07:15 UTC. Audit: 0 unauthorized transactions. Key had read-only scope."},
        "entities": [{"entity_id": "stripe-integration", "role": "subject"}, {"entity_id": "security-team", "role": "approver"}]
    },
    {
        "summary": "Disabled auto-scaling during cost optimization review",
        "choice": {"action": "disable_autoscaling", "services": ["non-critical-batch"], "duration": "7 days"},
        "rationale": "Non-critical batch jobs auto-scaling to unnecessary capacity. Disabled during cost review. Manual scaling available if needed.",
        "evidence": {"evidence_type": "cost_report", "excerpt": "Cost analysis: batch-processor scaling to 100 pods for 5-minute load spikes. Monthly cost $12,000. With fixed 20 pods: $2,400. Queue latency increase: 15 minutes acceptable."},
        "entities": [{"entity_id": "batch-processor", "role": "subject"}, {"entity_id": "finops-team", "role": "approver"}]
    },
    {
        "summary": "Enabled debug logging temporarily to diagnose intermittent errors",
        "choice": {"action": "enable_debug_logging", "service": "payment-service", "duration": "2 hours"},
        "rationale": "Intermittent 502 errors with no clear pattern. Debug logging enabled to capture full request/response for analysis. Disk usage monitored.",
        "evidence": {"evidence_type": "debug_log", "excerpt": "Debug logging enabled for payment-service at 10:00 UTC. Captured 3 occurrences of 502 error. Root cause: upstream timeout not properly handled."},
        "entities": [{"entity_id": "payment-service", "role": "subject"}, {"entity_id": "logging-infrastructure", "role": "related"}]
    },
    {
        "summary": "Drained node for kernel security update during business hours",
        "choice": {"action": "drain_node", "node": "k8s-node-prod-12", "reason": "kernel_security_update"},
        "rationale": "Critical kernel CVE requires immediate patching. Node drained gracefully, pods rescheduled to other nodes. Zero downtime achieved.",
        "evidence": {"evidence_type": "security_advisory", "excerpt": "CVE-2024-1086: Linux kernel privilege escalation. CVSS 7.8. Node k8s-node-prod-12 drained at 14:00 UTC. 23 pods rescheduled. Update completed 14:15 UTC."},
        "entities": [{"entity_id": "kubernetes-node-12", "role": "subject"}, {"entity_id": "security-team", "role": "approver"}]
    },
    {
        "summary": "Switched to degraded mode: search results from cache only during Elasticsearch outage",
        "choice": {"action": "enable_degraded_mode", "service": "search", "fallback": "cached_results", "freshness": "24 hours"},
        "rationale": "Elasticsearch cluster unhealthy. Rather than failing searches, serve cached results with staleness warning. User experience preserved.",
        "evidence": {"evidence_type": "incident_log", "excerpt": "INC-2024-1289: Elasticsearch cluster 3/5 nodes unhealthy. Search degraded mode enabled at 16:30 UTC. Cached results served with 'Results may be outdated' warning."},
        "entities": [{"entity_id": "elasticsearch", "role": "subject"}, {"entity_id": "search-service", "role": "related"}]
    },
    {
        "summary": "Rejected deployment: Failed security scan with critical vulnerabilities",
        "choice": {"action": "reject_deployment", "version": "3.2.0", "reason": "critical_vulnerabilities", "vuln_count": 3},
        "rationale": "Security scan found 3 critical CVEs in dependencies. Deployment blocked until remediation. Dev team notified with fix guidance.",
        "evidence": {"evidence_type": "security_scan", "excerpt": "Snyk scan: 3 critical vulnerabilities in v3.2.0. CVE-2024-0001 (log4j), CVE-2024-0002 (jackson), CVE-2024-0003 (spring). Deployment blocked."},
        "entities": [{"entity_id": "payment-service-v3.2.0", "role": "subject"}, {"entity_id": "security-team", "role": "approver"}]
    },
    {
        "summary": "Enabled CDN bypass for dynamic API routes during cache poisoning incident",
        "choice": {"action": "bypass_cdn", "routes": ["/api/v1/user/*", "/api/v1/cart/*"], "duration": "until_investigation_complete"},
        "rationale": "Suspected cache poisoning on user-specific routes. CDN bypass ensures fresh responses while security team investigates.",
        "evidence": {"evidence_type": "security_incident", "excerpt": "SEC-2024-0045: Users reporting seeing other users' data. Cache poisoning suspected. CDN bypass for /api/v1/user/* enabled at 11:00 UTC."},
        "entities": [{"entity_id": "cloudflare-cdn", "role": "subject"}, {"entity_id": "security-team", "role": "approver"}]
    }
]

COMMERCIAL_DECISIONS = [
    {
        "summary": "Approved 25% discount for Enterprise customer citing high churn risk",
        "choice": {"action": "approve_discount", "discount_percent": 25, "customer": "Acme Corp", "arr": 450000, "term_months": 12},
        "rationale": "Customer ARR $450K, NPS -20, competitor offer in hand. 25% discount retains customer and maintains relationship. Margin remains above 60%.",
        "evidence": {"evidence_type": "sales_notes", "excerpt": "Acme Corp renewal at risk. Competitor offered 30% discount. Customer NPS -20 after support issues. VP Sales approved 25% retention discount."},
        "entities": [{"entity_id": "acme-corp", "role": "subject"}, {"entity_id": "vp-sales", "role": "approver"}]
    },
    {
        "summary": "Granted 90-day payment terms for strategic healthcare customer",
        "choice": {"action": "approve_payment_terms", "terms_days": 90, "customer": "MedTech Solutions", "deal_value": 2400000},
        "rationale": "Healthcare vertical anchor customer. Standard 30 days not feasible for hospital procurement cycles. 90 days aligns with their payment schedule.",
        "evidence": {"evidence_type": "approval_chain", "excerpt": "MedTech Solutions: $2.4M deal. Hospital procurement requires 90-day terms. CFO approved extended terms for strategic vertical entry."},
        "entities": [{"entity_id": "medtech-solutions", "role": "subject"}, {"entity_id": "cfo", "role": "approver"}]
    },
    {
        "summary": "Waived $15,000 SLA penalty due to service outage on our side",
        "choice": {"action": "waive_penalty", "amount": 15000, "customer": "GlobalTech Inc", "reason": "service_outage"},
        "rationale": "Customer entitled to penalty under SLA. Outage was our fault (3.5 hours downtime). Waiver maintains goodwill. Cost absorbed in customer success budget.",
        "evidence": {"evidence_type": "incident_report", "excerpt": "INC-2024-0789 caused 3.5 hour outage affecting GlobalTech Inc. SLA guarantees 99.9% uptime. Penalty waived as goodwill gesture. Customer satisfaction preserved."},
        "entities": [{"entity_id": "globaltech-inc", "role": "subject"}, {"entity_id": "customer-success", "role": "approver"}]
    },
    {
        "summary": "Rejected 40% discount request - exceeds policy maximum without CEO approval",
        "choice": {"action": "reject_discount", "requested_percent": 40, "policy_max": 30, "customer": "SmallStartup LLC"},
        "rationale": "40% discount exceeds 30% policy maximum. Customer not strategic enough to warrant CEO exception. Offered 25% as alternative.",
        "evidence": {"evidence_type": "policy_reference", "excerpt": "Discount policy: Max 30% without CEO approval. SmallStartup LLC ARR $50K. Not strategic account. 25% counter-offer presented."},
        "entities": [{"entity_id": "smallstartup-llc", "role": "subject"}, {"entity_id": "sales-ops", "role": "decision_maker"}]
    },
    {
        "summary": "Approved 20% discount with condition of 2-year commitment",
        "choice": {"action": "approve_conditional_discount", "discount_percent": 20, "condition": "2_year_commitment", "customer": "GrowthCo"},
        "rationale": "Customer requesting 25% discount. Counter-offered 20% with 2-year lock-in. Protects future revenue while providing competitive pricing.",
        "evidence": {"evidence_type": "negotiation_log", "excerpt": "GrowthCo negotiation: Initial ask 25% discount. Counter: 20% with 2-year commit. Customer accepted. Contract value: $180K over 2 years."},
        "entities": [{"entity_id": "growthco", "role": "subject"}, {"entity_id": "sales-director", "role": "approver"}]
    },
    {
        "summary": "Approved exception to standard SLA for Fortune 500 strategic customer",
        "choice": {"action": "approve_sla_exception", "sla_tier": "platinum", "standard_tier": "gold", "customer": "MegaCorp Industries"},
        "rationale": "Fortune 500 anchor customer. Platinum SLA at gold pricing secures 3-year $5M deal. Exception creates reference customer in manufacturing vertical.",
        "evidence": {"evidence_type": "executive_approval", "excerpt": "MegaCorp Industries: Fortune 500 manufacturer. Platinum SLA requested. CEO approved exception for strategic value. 3-year deal, $5M TCV."},
        "entities": [{"entity_id": "megacorp-industries", "role": "subject"}, {"entity_id": "ceo", "role": "approver"}]
    },
    {
        "summary": "Approved 15% discount citing competitor pressure from Salesforce",
        "choice": {"action": "approve_competitive_discount", "discount_percent": 15, "competitor": "Salesforce", "customer": "TechStart Inc"},
        "rationale": "Customer evaluating Salesforce alternative. 15% discount matches competitive landscape. Retains customer with minimal margin impact.",
        "evidence": {"evidence_type": "competitive_intel", "excerpt": "TechStart Inc: Active Salesforce evaluation. Salesforce pricing 20% lower. 15% discount approved to remain competitive. Win rate: 65% at this discount level."},
        "entities": [{"entity_id": "techstart-inc", "role": "subject"}, {"entity_id": "competitive-intel-team", "role": "related"}]
    },
    {
        "summary": "Approved discount exception with quarterly business review requirement",
        "choice": {"action": "approve_conditional_discount", "discount_percent": 22, "condition": "quarterly_review", "customer": "DataDriven Co"},
        "rationale": "22% discount approved with quarterly business reviews to ensure value realization. Reviews protect against churn at renewal.",
        "evidence": {"evidence_type": "success_plan", "excerpt": "DataDriven Co: 22% discount approved. Condition: Quarterly business reviews with success metrics. Review schedule: Q1, Q2, Q3, Q4. Renewal target: 100%."},
        "entities": [{"entity_id": "datadriven-co", "role": "subject"}, {"entity_id": "customer-success-manager", "role": "related"}]
    },
    {
        "summary": "Approved 30% discount for customer with high churn risk score",
        "choice": {"action": "approve_retention_discount", "discount_percent": 30, "churn_score": 0.85, "customer": "AtRisk Corp"},
        "rationale": "Churn prediction model shows 85% churn probability. 30% discount is max policy allows. Better to retain at reduced margin than lose entirely.",
        "evidence": {"evidence_type": "churn_analysis", "excerpt": "AtRisk Corp: Churn score 0.85 (high). Contributing factors: Support tickets up 300%, NPS -40, usage down 60%. 30% retention discount approved."},
        "entities": [{"entity_id": "atrisk-corp", "role": "subject"}, {"entity_id": "retention-team", "role": "approver"}]
    },
    {
        "summary": "Denied payment terms extension - customer credit risk too high",
        "choice": {"action": "reject_terms_extension", "requested_days": 120, "approved_days": 30, "customer": "CashFlow LLC", "credit_score": "D"},
        "rationale": "Customer requested 120-day terms but credit score is D (high risk). Standard 30-day terms maintained. Offered payment plan alternative.",
        "evidence": {"evidence_type": "credit_report", "excerpt": "CashFlow LLC credit check: D rating, 3 late payments in past year, DSO 95 days. 120-day terms rejected. 30-day terms with payment plan offered."},
        "entities": [{"entity_id": "cashflow-llc", "role": "subject"}, {"entity_id": "finance-team", "role": "decision_maker"}]
    },
    {
        "summary": "Approved free pilot extension for enterprise prospect",
        "choice": {"action": "approve_pilot_extension", "extension_days": 30, "customer": "Enterprise Prospect Corp", "deal_size": 800000},
        "rationale": "Enterprise evaluation taking longer than expected. 30-day extension maintains momentum. Deal size $800K justifies investment.",
        "evidence": {"evidence_type": "sales_notes", "excerpt": "Enterprise Prospect Corp: 30-day pilot extension requested. Procurement delayed due to budget cycle. Deal size $800K. Extension approved by Sales VP."},
        "entities": [{"entity_id": "enterprise-prospect-corp", "role": "subject"}, {"entity_id": "sales-vp", "role": "approver"}]
    },
    {
        "summary": "Approved multi-year discount for 3-year commitment",
        "choice": {"action": "approve_multiyear_discount", "discount_percent": 18, "term_years": 3, "customer": "LongTerm Partners"},
        "rationale": "3-year commitment provides revenue predictability. 18% discount (6% per year) standard for multi-year. TCV $540K.",
        "evidence": {"evidence_type": "contract_terms", "excerpt": "LongTerm Partners: 3-year agreement. 18% discount (6% annual equivalent). TCV $540K. Payment terms: Annual upfront. Contract signed Q4."},
        "entities": [{"entity_id": "longterm-partners", "role": "subject"}, {"entity_id": "sales-director", "role": "approver"}]
    },
    {
        "summary": "Denied discount request and deal was lost to competitor",
        "choice": {"action": "reject_discount", "requested_percent": 35, "offered_percent": 20, "customer": "PriceWars Inc", "outcome": "lost_deal"},
        "rationale": "Customer demanded 35% discount, exceeding policy. Counter-offered 20%. Customer chose competitor. Decision documented for future analysis.",
        "evidence": {"evidence_type": "loss_analysis", "excerpt": "PriceWars Inc: Lost to competitor after rejecting 35% discount request. Post-mortem: Customer primarily price-driven, low strategic value. Decision appropriate."},
        "entities": [{"entity_id": "pricewars-inc", "role": "subject"}, {"entity_id": "sales-ops", "role": "decision_maker"}]
    },
    {
        "summary": "Approved one-time credit for billing error causing customer inconvenience",
        "choice": {"action": "approve_credit", "amount": 5000, "customer": "Valued Customer Co", "reason": "billing_error"},
        "rationale": "Billing system error caused double charge. Credit applied immediately plus $500 goodwill gesture. Customer satisfied, relationship preserved.",
        "evidence": {"evidence_type": "support_ticket", "excerpt": "TICKET-89234: Valued Customer Co double-charged $5,000. System error confirmed. Credit + $500 goodwill applied within 4 hours. CSAT score: 5/5."},
        "entities": [{"entity_id": "valued-customer-co", "role": "subject"}, {"entity_id": "billing-team", "role": "related"}]
    },
    {
        "summary": "Approved custom contract terms for government entity",
        "choice": {"action": "approve_custom_terms", "customer": "State Agency", "modifications": ["liability_cap", "data_residency", "audit_rights"]},
        "rationale": "Government contracts require specific terms not in standard agreement. Legal approved modifications. Opens public sector vertical.",
        "evidence": {"evidence_type": "legal_review", "excerpt": "State Agency contract: Custom terms approved. Liability cap reduced to contract value. Data residency: US only. Audit rights: Annual. Legal signed off."},
        "entities": [{"entity_id": "state-agency", "role": "subject"}, {"entity_id": "legal-team", "role": "approver"}]
    },
    {
        "summary": "Approved volume discount for reseller partner",
        "choice": {"action": "approve_partner_discount", "discount_percent": 35, "partner_tier": "gold", "customer": "Channel Partner Inc"},
        "rationale": "Gold partner tier qualifies for 35% wholesale discount. Partner committed to $2M annual purchases. Standard partner program terms.",
        "evidence": {"evidence_type": "partner_agreement", "excerpt": "Channel Partner Inc: Gold tier partner. 35% discount on wholesale pricing. $2M annual commitment. Partner program T&Cs apply. Signed Q1."},
        "entities": [{"entity_id": "channel-partner-inc", "role": "subject"}, {"entity_id": "partner-team", "role": "approver"}]
    },
    {
        "summary": "Approved startup pricing for Y Combinator company",
        "choice": {"action": "approve_startup_pricing", "discount_percent": 50, "program": "YC_deal", "customer": "YC Startup 2024"},
        "rationale": "Y Combinator startup qualifies for 50% startup pricing. Program designed to acquire high-growth customers early. Standard YC deal terms.",
        "evidence": {"evidence_type": "program_eligibility", "excerpt": "YC Startup 2024: Y Combinator W24 batch. Eligible for 50% startup pricing under YC partnership. 2-year term. Annual review for graduation to standard pricing."},
        "entities": [{"entity_id": "yc-startup-2024", "role": "subject"}, {"entity_id": "startup-program", "role": "related"}]
    },
    {
        "summary": "Denied contract renewal without price increase due to rising costs",
        "choice": {"action": "reject_renewal_terms", "customer": "Legacy Customer Co", "requested": "no_increase", "minimum_increase": "5%"},
        "rationale": "Customer requesting flat renewal. Our costs increased 8% YoY. Minimum 5% increase required to maintain margins. Counter-offered 5%.",
        "evidence": {"evidence_type": "pricing_analysis", "excerpt": "Legacy Customer Co renewal: Flat pricing requested. Cost analysis shows 8% increase in delivery costs. 5% increase counter-offered. Customer accepted."},
        "entities": [{"entity_id": "legacy-customer-co", "role": "subject"}, {"entity_id": "finance-team", "role": "decision_maker"}]
    },
    {
        "summary": "Approved early termination with reduced penalty for acquired customer",
        "choice": {"action": "approve_early_termination", "penalty_percent": 25, "standard_penalty": 50, "customer": "Acquired Inc", "reason": "acquisition"},
        "rationale": "Customer acquired by company using competitor. Reduced termination penalty to 25% (standard 50%). Goodwill gesture for potential future relationship.",
        "evidence": {"evidence_type": "termination_request", "excerpt": "Acquired Inc: Acquired by TechGiant (uses competitor). Early termination requested. 25% penalty (reduced from 50%). $45K collected. Door left open for future."},
        "entities": [{"entity_id": "acquired-inc", "role": "subject"}, {"entity_id": "customer-success", "role": "approver"}]
    },
    {
        "summary": "Approved bundled discount for cross-sell opportunity",
        "choice": {"action": "approve_bundle_discount", "discount_percent": 12, "products": ["core", "analytics", "api"], "customer": "Expansion Co"},
        "rationale": "Customer expanding from Core to full suite. 12% bundle discount incentivizes adoption. LTV increases 3x with full platform usage.",
        "evidence": {"evidence_type": "expansion_opportunity", "excerpt": "Expansion Co: Current Core customer. Adding Analytics + API. 12% bundle discount approved. New ARR: $180K (up from $60K). LTV multiplier: 3x."},
        "entities": [{"entity_id": "expansion-co", "role": "subject"}, {"entity_id": "account-executive", "role": "approver"}]
    },
    {
        "summary": "Approved education discount for university",
        "choice": {"action": "approve_education_discount", "discount_percent": 40, "customer": "State University", "program": "edu_program"},
        "rationale": "Universities qualify for 40% education discount under EDU program. Builds brand awareness, creates future enterprise buyers.",
        "evidence": {"evidence_type": "program_eligibility", "excerpt": "State University: .edu domain verified. Eligible for 40% EDU discount. 500 student seats. Alumni often become enterprise buyers. Program approved."},
        "entities": [{"entity_id": "state-university", "role": "subject"}, {"entity_id": "edu-program", "role": "related"}]
    },
    {
        "summary": "Approved payment deferral for customer facing temporary cash flow issues",
        "choice": {"action": "approve_payment_deferral", "deferral_days": 60, "customer": "Seasonal Business Co", "reason": "cash_flow"},
        "rationale": "Seasonal business with Q1 cash crunch. 60-day deferral maintains relationship. Customer has 5-year history with us, always pays eventually.",
        "evidence": {"evidence_type": "payment_history", "excerpt": "Seasonal Business Co: 5-year customer. Payment history: 100% paid, avg DSO 45 days. Q1 cash crunch due to seasonal nature. 60-day deferral approved."},
        "entities": [{"entity_id": "seasonal-business-co", "role": "subject"}, {"entity_id": "finance-team", "role": "approver"}]
    },
    {
        "summary": "Approved non-standard cancellation clause for regulated industry",
        "choice": {"action": "approve_custom_clause", "clause": "regulatory_cancellation", "customer": "Regulated Finance Corp"},
        "rationale": "Financial services customer requires regulatory exit clause. If regulator mandates vendor change, can cancel with 90 days notice. Standard for industry.",
        "evidence": {"evidence_type": "legal_review", "excerpt": "Regulated Finance Corp: Regulatory cancellation clause requested. Common in financial services. 90-day notice period. Legal approved. No unusual risk."},
        "entities": [{"entity_id": "regulated-finance-corp", "role": "subject"}, {"entity_id": "legal-team", "role": "approver"}]
    },
    {
        "summary": "Denied refund request for service used extensively",
        "choice": {"action": "reject_refund", "amount": 12000, "customer": "Buyer's Remorse LLC", "reason": "extensive_usage"},
        "rationale": "Customer requested full refund after 11 months. Usage data shows extensive daily use. No grounds for refund under T&Cs.",
        "evidence": {"evidence_type": "usage_data", "excerpt": "Buyer's Remorse LLC: Refund requested month 11 of 12. Usage: 847 active users, 12,000 API calls/day, 45TB data processed. Refund denied per T&Cs."},
        "entities": [{"entity_id": "buyers-remorse-llc", "role": "subject"}, {"entity_id": "finance-team", "role": "decision_maker"}]
    },
    {
        "summary": "Approved contract restructuring for customer downsizing",
        "choice": {"action": "approve_restructure", "new_seats": 50, "old_seats": 200, "customer": "Downsizing Corp", "credit_applied": 15000},
        "rationale": "Customer laying off 75% of workforce. Restructured contract to 50 seats with $15K credit for future use. Maintains relationship through difficult time.",
        "evidence": {"evidence_type": "restructure_request", "excerpt": "Downsizing Corp: Layoffs reducing team 200 to 50. Contract restructured. $15K credit for unused seats applied to future invoices. Customer appreciated flexibility."},
        "entities": [{"entity_id": "downsizing-corp", "role": "subject"}, {"entity_id": "customer-success", "role": "approver"}]
    }
]


def main():
    print("=" * 60)
    print("DTL VALIDATION PACK - PHASE 1: SEED GOLDEN TRACES")
    print("=" * 60)
    print(f"Tenant A: {TENANT_A}")
    print()
    
    logger = AgentDecisionLogger(
        tenant_id=TENANT_A,
        decision_maker_id="b3e4c187-87e4-4511-890f-4dc41d6e9778",
        source_system="dtl_validation_seed",
        auto_enact=True
    )
    
    decisions_created = 0
    evidence_created = 0
    decision_ids = []
    
    print("\n--- Seeding 25 Ops Decisions ---")
    for i, dec in enumerate(OPS_DECISIONS[:25]):
        try:
            evidence_data = dec["evidence"]
            decision_id = logger.log_decision_event(
                decision_type="ops_incident_response",
                summary=dec["summary"],
                choice=dec["choice"],
                rationale=dec["rationale"],
                evidence_excerpt=evidence_data["excerpt"],
                evidence_type="agent_log"
            )
            if decision_id:
                decisions_created += 1
                evidence_created += 1
                decision_ids.append(decision_id)
                if i < 5:
                    print(f"  [{i+1}] Created: {decision_id[:8]}... - {dec['summary'][:50]}...")
        except Exception as e:
            print(f"  [!] Error creating decision {i+1}: {e}")
    
    print(f"\nOps decisions created: {decisions_created}/25")
    
    print("\n--- Seeding 25 Commercial Decisions ---")
    commercial_start = decisions_created
    for i, dec in enumerate(COMMERCIAL_DECISIONS[:25]):
        try:
            evidence_data = dec["evidence"]
            decision_id = logger.log_decision_event(
                decision_type="commercial_approval",
                summary=dec["summary"],
                choice=dec["choice"],
                rationale=dec["rationale"],
                evidence_excerpt=evidence_data["excerpt"],
                evidence_type="agent_log"
            )
            if decision_id:
                decisions_created += 1
                evidence_created += 1
                decision_ids.append(decision_id)
                if i < 5:
                    print(f"  [{i+1}] Created: {decision_id[:8]}... - {dec['summary'][:50]}...")
        except Exception as e:
            print(f"  [!] Error creating decision {i+1}: {e}")
    
    commercial_created = decisions_created - commercial_start
    print(f"\nCommercial decisions created: {commercial_created}/25")
    
    print("\n" + "=" * 60)
    print("PHASE 1 RESULTS")
    print("=" * 60)
    print(f"Total decisions created: {decisions_created}")
    print(f"Total evidence rows created: {evidence_created}")
    print(f"% decisions with evidence: {100 * evidence_created / max(decisions_created, 1):.1f}%")
    print()
    print("Sample decision IDs (first 10):")
    for i, did in enumerate(decision_ids[:10]):
        print(f"  {i+1}. {did}")
    
    return decisions_created, evidence_created, decision_ids


if __name__ == "__main__":
    main()
