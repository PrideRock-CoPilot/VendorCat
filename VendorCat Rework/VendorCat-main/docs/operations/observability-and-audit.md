# Observability and Audit

This document defines logging, metrics, audit trail, and alerting standards for VendorCatalog.

## Logging Standards

### Log Levels

Use appropriate log level for each message:

| Level | When to Use | Example |
|-------|-------------|---------|
| DEBUG | Development troubleshooting, verbose details | "SQL query: SELECT * FROM vendor WHERE id=123" |
| INFO | Normal operations, business events | "Vendor created: vendor_id=123, name=Acme" |
| WARNING | Abnormal but recoverable situations | "Vendor not found: vendor_id=999, returning empty" |
| ERROR | Errors requiring attention but app continues | "Failed to send email notification: smtp timeout" |
| CRITICAL | System failure, app cannot continue | "Database connection failed: cannot start app" |

### Structured Logging

Use structured logging (JSON format) for easy parsing:

```python
import logging
import json

logger = logging.getLogger(__name__)

def log_vendor_create(vendor_id: int, vendor_name: str, actor: str, request_id: str):
    logger.info(json.dumps({
        "event": "vendor_created",
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "actor": actor,
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat()
    }))
```

**Benefits**:
- Machine-parsable for log aggregation
- Consistent format across all logs
- Easy to filter/search by field

### Correlation IDs

Attach correlation ID to every request for request tracing:

```python
import uuid

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
```

**Usage in logs**:
```python
logger.info(f"[{request.state.correlation_id}] Vendor search: query={search_term}")
```

**Benefit**: Trace all logs for single request across services.

### Log Context

Include relevant context in every log:

```python
def log_with_context(message: str, user: UserContext, vendor_id: int = None):
    context = {
        "user_id": user.user_id,
        "username": user.username,
        "org_id": user.organization_id,
        "vendor_id": vendor_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    logger.info(f"{message} | context={json.dumps(context)}")
```

### What to Log

**Always log**:
- User authentication (login, logout, failed attempts)
- Mutations (create, update, delete with entity ID)
- Permission checks (grant + deny with reason)
- External API calls (URL, status code, duration)
- Errors and exceptions (with stack trace)
- App startup and shutdown

**Never log**:
- Passwords or credentials
- Full credit card numbers
- Sensitive PII (SSN, tax ID)
- Full SQL queries with user data (log parameterized query instead)

### Log Retention

- **Application logs**: 30 days in hot storage, 90 days in cold storage
- **Audit logs**: 7 years (compliance requirement)
- **Security logs**: 1 year

## Metrics

### Business Metrics

Track business-level metrics:

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| vendors_created_daily | Vendors created per day | <5 (low usage) |
| vendors_updated_daily | Vendors updated per day | >1000 (high load) |
| vendor_searches_daily | Search queries per day | <10 (low usage) |
| user_logins_daily | Unique user logins per day | <5 (low adoption) |
| approval_cycle_time_hours | Hours from submit to approve | >24 (slow approvals) |

### Technical Metrics

Track system health:

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| request_duration_p95 | 95th percentile request time | >2000ms |
| request_error_rate | % of requests returning 5xx | >1% |
| database_query_duration_p95 | 95th percentile DB query time | >500ms |
| database_connection_pool_usage | % of DB connections used | >80% |
| memory_usage_mb | App memory usage | >2048 MB |
| cpu_usage_percent | App CPU usage | >80% |

### Metric Collection

Use Prometheus-compatible metrics:

```python
from prometheus_client import Counter, Histogram, Gauge

# Counters (always increasing)
vendor_create_counter = Counter('vendorcat_vendor_created_total', 'Total vendors created')
request_counter = Counter('vendorcat_requests_total', 'Total requests', ['method', 'endpoint', 'status'])

# Histograms (distribution)
request_duration = Histogram('vendorcat_request_duration_seconds', 'Request duration', ['endpoint'])
db_query_duration = Histogram('vendorcat_db_query_duration_seconds', 'DB query duration', ['query_type'])

# Gauges (current value)
active_users = Gauge('vendorcat_active_users', 'Current active users')
db_connection_pool_size = Gauge('vendorcat_db_connection_pool_size', 'DB connection pool size')

# Usage in code
@router.post("/vendor")
async def create_vendor(request: Request, vendor_data: dict):
    start_time = time.time()
    
    vendor = repo.create_vendor(vendor_data)
    vendor_create_counter.inc()  # Increment counter
    
    duration = time.time() - start_time
    request_duration.labels(endpoint='/vendor').observe(duration)  # Record duration
    
    return vendor
```

### Metric Export

Expose metrics at `/metrics` endpoint for Prometheus scraping:

```python
from prometheus_client import generate_latest

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

## Audit Trail

### audit_entity_change Table

Every mutation logged to audit table:

```sql
CREATE TABLE twvendor.audit_entity_change (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type STRING NOT NULL,  -- 'vendor', 'contact', 'address'
    entity_id BIGINT NOT NULL,
    change_type STRING NOT NULL,  -- 'create', 'update', 'delete', 'status_change'
    before_snapshot TEXT,  -- JSON snapshot before change
    after_snapshot TEXT,  -- JSON snapshot after change
    actor STRING NOT NULL,  -- username who made change
    request_id STRING,  -- correlation ID for request tracing
    change_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_reason TEXT  -- optional user-provided reason
)
USING DELTA
PARTITIONED BY (DATE(change_timestamp));
```

### Audit Logging Pattern

```python
def _write_audit_entity_change(
    entity_type: str,
    entity_id: int,
    change_type: str,
    before_snapshot: dict | None,
    after_snapshot: dict | None,
    actor: str,
    request_id: str,
    change_reason: str = None
):
    self._execute_write(
        """
        INSERT INTO twvendor.audit_entity_change (
            entity_type, entity_id, change_type,
            before_snapshot, after_snapshot,
            actor, request_id, change_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            entity_id,
            change_type,
            json.dumps(before_snapshot) if before_snapshot else None,
            json.dumps(after_snapshot) if after_snapshot else None,
            actor,
            request_id,
            change_reason
        )
    )
```

**Usage**:
```python
def update_vendor_status(self, vendor_id: int, new_status: str, user: UserContext):
    old_vendor = self.get_vendor_by_id(vendor_id)
    
    self._execute_write(
        "UPDATE twvendor.core_vendor SET vendor_status = ? WHERE vendor_id = ?",
        (new_status, vendor_id)
    )
    
    new_vendor = self.get_vendor_by_id(vendor_id)
    
    self._write_audit_entity_change(
        entity_type="vendor",
        entity_id=vendor_id,
        change_type="status_change",
        before_snapshot=old_vendor,
        after_snapshot=new_vendor,
        actor=user.username,
        request_id=request.state.correlation_id
    )
```

### Audit Query Examples

**Who changed vendor 123 in last 30 days?**
```sql
SELECT actor, change_type, change_timestamp
FROM twvendor.audit_entity_change
WHERE entity_type = 'vendor'
  AND entity_id = 123
  AND change_timestamp >= CURRENT_DATE - INTERVAL 30 DAYS
ORDER BY change_timestamp DESC;
```

**What fields changed in last update?**
```python
def audit_diff(audit_id: int):
    audit = repo.get_audit_by_id(audit_id)
    before = json.loads(audit['before_snapshot'])
    after = json.loads(audit['after_snapshot'])
    
    changes = {}
    for key in after.keys():
        if before.get(key) != after.get(key):
            changes[key] = {'before': before.get(key), 'after': after.get(key)}
    
    return changes
```

**All changes by user in last 7 days?**
```sql
SELECT entity_type, entity_id, change_type, change_timestamp
FROM twvendor.audit_entity_change
WHERE actor = 'john.doe'
  AND change_timestamp >= CURRENT_DATE - INTERVAL 7 DAYS
ORDER BY change_timestamp DESC;
```

### Audit Retention

- **Hot storage**: Last 90 days in Databricks
- **Cold storage**: 7 years in archive (S3/ADLS)
- **Compliance**: Required for SOX, GDPR, etc.

**Archive process** (quarterly):
```sql
-- Export old audit records
COPY (
    SELECT * FROM twvendor.audit_entity_change
    WHERE change_timestamp < CURRENT_DATE - INTERVAL 90 DAYS
) TO 's3://vendorcat-archive/audit/2025-Q4.parquet' FORMAT PARQUET;

-- Delete from hot storage
DELETE FROM twvendor.audit_entity_change
WHERE change_timestamp < CURRENT_DATE - INTERVAL 90 DAYS;
```

## Alerting

### Alert Rules

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High error rate | error_rate >5% for 5 min | Critical | Page on-call engineer |
| Slow requests | p95_duration >3s for 10 min | High | Create incident ticket |
| Database down | DB connection fails | Critical | Page on-call + email team |
| No user activity | logins_last_hour = 0 (during business hours) | Medium | Email tech lead |
| High permission denials | permission_denied_rate >10% for 15 min | Medium | Review RBAC config |
| Disk space low | disk_usage >90% | High | Alert ops team |
| Security vulnerability | Dependabot alert with severity=HIGH | High | Email security lead |

### Alert Channels

- **Critical**: PagerDuty + Slack #vendorcat-alerts
- **High**: Slack #vendorcat-alerts + email to tech lead
- **Medium**: Email to tech lead
- **Low**: Slack #vendorcat-logs (no notification)

### Alert Configuration (Prometheus AlertManager)

```yaml
groups:
  - name: vendorcat_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(vendorcat_requests_total{status="500"}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }}% over last 5 minutes"
      
      - alert: SlowRequests
        expr: histogram_quantile(0.95, vendorcat_request_duration_seconds) > 3
        for: 10m
        labels:
          severity: high
        annotations:
          summary: "Slow request duration"
          description: "P95 duration is {{ $value }}s"
```

## Dashboards

### Production Dashboard

**Tool**: Grafana

**Panels**:
1. Request rate (req/sec) - last 24h
2. Error rate (%) - last 24h
3. P50/P95/P99 latency - last 24h
4. Active users (gauge)
5. Vendors created today (counter)
6. Database query duration P95 - last 1h
7. Memory/CPU usage - last 1h

**Refresh**: 30 seconds

**Access**: Public read-only link for stakeholders

---

### Business Dashboard

**Tool**: Databricks SQL Dashboard

**Panels**:
1. Vendors created per day (last 30 days)
2. Vendors by status (active, inactive, pending)
3. Vendors by organization (pie chart)
4. Top 10 users by vendor edits (last 7 days)
5. Approval cycle time (avg, p95)
6. Search queries per day

**Refresh**: Daily at 8am

**Access**: Stakeholder access in Databricks

---

## Observability Checklist

For every feature, ensure:

- [ ] **INFO logs** for business events (create, update, delete)
- [ ] **ERROR logs** for failures (with context and stack trace)
- [ ] **Metrics** emitted (counter for events, histogram for duration)
- [ ] **Audit trail** written for mutations (before/after snapshot)
- [ ] **Correlation ID** propagated in logs
- [ ] **Alerts** configured for failure conditions
- [ ] **Dashboard** updated with new metrics

---

Last updated: 2026-02-15
