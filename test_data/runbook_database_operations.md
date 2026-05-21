# Runbook: Database Operations and Emergency Procedures

## Overview

This runbook covers operational procedures for the core PostgreSQL databases managed by the database-team. The database-team is responsible for all production database instances including payments-db, users-db, orders-db, inventory-db, and notification-db.

## Database Inventory

| Database | Service | Engine | Host | Team |
|----------|---------|--------|------|------|
| payments-db | payment-api | PostgreSQL 14 | db-prod-payments.internal | database-team |
| users-db | user-service | PostgreSQL 15 | db-prod-users.internal | database-team |
| orders-db | order-service | PostgreSQL 15 | db-prod-orders.internal | database-team |
| inventory-db | inventory-service | PostgreSQL 15 | db-prod-inventory.internal | database-team |
| notification-db | notification-service | PostgreSQL 14 | db-prod-notifications.internal | database-team |
| analytics-db | analytics-pipeline | PostgreSQL 15 | db-prod-analytics.internal | database-team |

## Team Structure

The database-team consists of:
- **Bob Martinez** - Team Lead, Senior DBA
- **Rachel Green** - DBA, specializes in PostgreSQL performance tuning
- **Tom Harris** - DBA, specializes in backup and disaster recovery
- **Nina Patel** - Junior DBA, handles routine maintenance

Escalation path: Nina Patel → Rachel Green → Bob Martinez → Carol Johnson (VP Engineering)

## Emergency Procedures

### Procedure 1: Database Failover

**When to use:** Primary database is unresponsive or corrupted.

**Steps:**

1. Verify primary is truly down (not just slow):
```bash
pg_isready -h db-prod-payments.internal -p 5432
```

2. Check replication lag on replica:
```sql
SELECT pg_last_wal_replay_lsn() - pg_last_wal_receive_lsn() AS replication_lag;
```

3. Promote replica to primary:
```bash
pg_ctl promote -D /var/lib/postgresql/data
```

4. Update DNS to point to new primary
5. Notify all dependent services:
   - For payments-db: notify payments-team (Alice Chen)
   - For users-db: notify platform-team (David Kim)
   - For orders-db: notify commerce-team (Sarah Park)
   - For notification-db: notify messaging-team (Mike Thompson)

### Procedure 2: Connection Pool Emergency

**When to use:** Any database hits max connections limit.

**Symptoms:**
- Services reporting connection refused errors
- pg_stat_activity shows max connections reached
- PagerDuty alert: "Database connection pool at capacity"

**Steps:**

1. Identify connection consumers:
```sql
SELECT application_name, count(*)
FROM pg_stat_activity
GROUP BY application_name
ORDER BY count DESC;
```

2. Kill idle connections older than 10 minutes:
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND query_start < NOW() - INTERVAL '10 minutes';
```

3. If a single service is consuming excessive connections, contact the owning team:
   - payment-api → payments-team
   - user-service → platform-team
   - order-service → commerce-team
   - notification-service → messaging-team

4. Temporarily increase max_connections if needed (requires restart)

### Procedure 3: Storage Emergency

**When to use:** Database disk usage exceeds 85%.

**Steps:**

1. Check current disk usage per database:
```sql
SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname))
FROM pg_database
ORDER BY pg_database_size(pg_database.datname) DESC;
```

2. Identify largest tables:
```sql
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

3. Run VACUUM FULL on bloated tables (requires downtime coordination with service team)
4. Archive old data if applicable
5. If immediate space needed: expand volume via cloud provider console

## Backup and Recovery

### Backup Schedule
- **Full backup**: Daily at 02:00 UTC (all databases)
- **WAL archiving**: Continuous to S3
- **Retention**: 30 days for full backups, 7 days for WAL

### Recovery Procedure

1. Stop the target database service
2. Restore from latest full backup:
```bash
pg_restore -h localhost -U postgres -d target_db /backups/latest/target_db.dump
```
3. Apply WAL logs up to desired point-in-time
4. Verify data integrity
5. Restart dependent services

## Cross-Team Dependencies

The database-team supports the following teams:
- **payments-team**: payments-db for payment-api
- **platform-team**: users-db for user-service
- **commerce-team**: orders-db and inventory-db for order-service and inventory-service
- **messaging-team**: notification-db for notification-service
- **data-team**: analytics-db for analytics-pipeline

## Monitoring

- Grafana dashboards: "PostgreSQL Overview", "Database Connections", "Replication Lag"
- PagerDuty: Routes to database-team on-call
- Custom alerts for: connection pool > 80%, replication lag > 1s, disk > 85%

## Contact Information

- **Team Lead**: Bob Martinez (#database-ops Slack)
- **Escalation**: Carol Johnson (VP Engineering)
- **On-Call Rotation**: Bob → Rachel → Tom → Nina (weekly)

## Document Metadata

- **Last Updated**: 2024-12-01
- **Version**: 4.2
- **Author**: Bob Martinez (database-team)
- **Review Cycle**: Monthly
