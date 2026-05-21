# Runbook: Notification Service Operations

## Overview

The notification-service handles all outbound communications including email, SMS, and push notifications. It is owned by the messaging-team and processes approximately 500,000 notifications per day.

## Service Architecture

The notification-service consumes events from notification-queue (RabbitMQ) and dispatches them through the appropriate channel. It depends on:

- notification-queue (RabbitMQ) - inbound message queue
- notification-db (PostgreSQL) - delivery tracking and templates
- email-gateway - external SMTP relay (SendGrid)
- sms-gateway - external SMS provider (Twilio)
- user-service - recipient contact information lookup

## Team Ownership

The messaging-team owns the notification-service. The primary on-call is Mike Thompson (Staff Engineer). Escalation contact is Lisa Wang (Engineering Director, messaging-team).

## Common Failure Scenarios

### Scenario 1: Queue Backlog

**Symptoms:**
- Notification delivery latency exceeds 5 minutes
- notification-queue depth growing steadily
- Consumer lag increasing on notification-service

**Diagnostic Steps:**

1. Check RabbitMQ queue depth:
```bash
rabbitmqctl list_queues name messages_ready messages_unacknowledged | grep notification
```

2. Check notification-service consumer count:
```bash
kubectl get pods -l app=notification-service
```

3. Check for slow database queries on notification-db:
```sql
SELECT pid, query, state, NOW() - query_start AS duration
FROM pg_stat_activity
WHERE datname = 'notifications' AND state != 'idle'
ORDER BY duration DESC;
```

**Recovery Actions:**

1. Scale notification-service horizontally: `kubectl scale deployment/notification-service --replicas=5`
2. If notification-db is the bottleneck, contact database-team
3. If email-gateway is rate limiting, check SendGrid dashboard and contact messaging-team

### Scenario 2: Email Gateway Failure

**Symptoms:**
- Email delivery rate drops to zero
- notification-service logs show SMTP connection errors
- email-gateway health check failing

**Diagnostic Steps:**

1. Check email-gateway connectivity:
```bash
curl https://api.sendgrid.com/v3/mail/send -X OPTIONS
```

2. Check notification-service retry queue depth
3. Verify API key hasn't expired

**Recovery Actions:**

1. notification-service automatically retries failed emails with exponential backoff
2. If SendGrid is fully down, enable backup SMTP relay
3. Contact messaging-team to activate failover provider
4. Notify affected teams (payments-team, commerce-team) about delayed email notifications

### Scenario 3: SMS Gateway Throttling

**Symptoms:**
- SMS delivery success rate drops below 95%
- Twilio API returning 429 (rate limit) errors
- High-priority notifications (2FA codes) delayed

**Diagnostic Steps:**

1. Check Twilio rate limit status in notification-service metrics
2. Verify current SMS send rate vs. account limits
3. Check for any marketing campaign that may be consuming SMS quota

**Recovery Actions:**

1. Prioritize 2FA and security notifications over marketing
2. Contact messaging-team to request Twilio rate limit increase
3. Queue non-critical SMS for off-peak delivery
4. If critical: escalate to Lisa Wang for emergency rate limit override

## Dependencies Map

### Upstream (sends events to us):
- payment-api → payment confirmation emails
- order-service → order status updates
- user-service → password reset, welcome emails, 2FA codes
- billing-service → invoice and receipt emails

### Infrastructure:
- notification-queue (RabbitMQ) → event ingestion
- notification-db (PostgreSQL) → delivery tracking
- email-gateway (SendGrid) → email delivery
- sms-gateway (Twilio) → SMS delivery

### Cross-team:
- payments-team depends on us for payment confirmations
- commerce-team depends on us for order updates
- platform-team manages the api-gateway that routes to us

## Monitoring and Alerts

- Grafana: "Notification Pipeline" dashboard
- Metrics: notifications_sent_total, notification_latency_seconds, delivery_failure_rate
- PagerDuty: Routes to messaging-team on-call
- SLA: 99.9% delivery rate, < 30 second latency for critical notifications

## Contact Information

- **Primary Owner**: messaging-team (#messaging-ops Slack)
- **On-Call**: Mike Thompson (PagerDuty)
- **Escalation**: Lisa Wang (Engineering Director)
- **External Vendors**: SendGrid support, Twilio support

## Document Metadata

- **Last Updated**: 2024-11-20
- **Version**: 3.0
- **Author**: Mike Thompson (messaging-team)
- **Review Cycle**: Monthly
