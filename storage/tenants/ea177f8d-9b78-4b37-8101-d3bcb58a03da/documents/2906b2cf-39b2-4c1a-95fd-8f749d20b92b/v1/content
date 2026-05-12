# NexusConnect IoT Platform API Specification

**Document Type:** API Specification
**Authority Level:** 1 (Authoritative)
**Document Number:** TEC-DIG-001
**Version:** 4.2
**Effective Date:** January 1, 2026
**Owner:** Dr. Alan Chen, VP Engineering
**Classification:** Internal

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 3.0 | Jun 2025 | A. Chen | Major revision |
| 4.0 | Oct 2025 | A. Chen | Edge AI APIs |
| 4.1 | Dec 2025 | A. Chen | Security updates |
| 4.2 | Jan 2026 | A. Chen | Performance improvements |

---

## 1. Overview

### 1.1 Platform Description

NexusConnect is an enterprise IoT platform that enables device management, data ingestion, analytics, and edge computing across industrial environments.

### 1.2 API Characteristics

| Attribute | Value |
|-----------|-------|
| Architecture | REST + WebSocket |
| Data Format | JSON |
| Authentication | OAuth 2.0 + API Keys |
| Rate Limiting | Per-tier |
| Versioning | URL path (v4) |
| Base URL | `https://api.nexusconnect.io/v4` |

### 1.3 Supported Operations

| Resource | Create | Read | Update | Delete | Stream |
|----------|--------|------|--------|--------|--------|
| Devices | ✓ | ✓ | ✓ | ✓ | ✓ |
| Telemetry | ✓ | ✓ | - | - | ✓ |
| Commands | ✓ | ✓ | - | - | - |
| Alerts | ✓ | ✓ | ✓ | ✓ | ✓ |
| Models | ✓ | ✓ | ✓ | ✓ | - |
| Dashboards | ✓ | ✓ | ✓ | ✓ | - |

---

## 2. Authentication

### 2.1 OAuth 2.0 Flow

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={client_id}
&client_secret={client_secret}
&scope=devices:read devices:write telemetry:read
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "devices:read devices:write telemetry:read"
}
```

### 2.2 API Key Authentication

```
GET /v4/devices
Authorization: ApiKey {api_key}
X-Org-ID: {organization_id}
```

### 2.3 Scopes

| Scope | Description |
|-------|-------------|
| `devices:read` | Read device information |
| `devices:write` | Create, update, delete devices |
| `telemetry:read` | Read telemetry data |
| `telemetry:write` | Write telemetry data |
| `commands:execute` | Send commands to devices |
| `alerts:read` | Read alerts |
| `alerts:write` | Create and manage alerts |
| `models:read` | Read ML models |
| `models:deploy` | Deploy ML models |
| `admin` | Full administrative access |

---

## 3. Device Management API

### 3.1 List Devices

```http
GET /v4/devices
Authorization: Bearer {token}
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `limit` | integer | Items per page (max: 100) |
| `status` | string | Filter by status |
| `type` | string | Filter by device type |
| `tags` | string | Comma-separated tags |
| `search` | string | Search in name/ID |

**Response:**
```json
{
  "data": [
    {
      "id": "dev_abc123",
      "name": "Temperature Sensor 1",
      "type": "sensor",
      "status": "online",
      "lastSeen": "2026-01-08T14:32:00Z",
      "metadata": {
        "manufacturer": "Nexus",
        "model": "TMP-100",
        "firmware": "2.4.1"
      },
      "tags": ["factory-a", "production-line-1"],
      "created": "2025-06-15T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1250,
    "pages": 63
  }
}
```

### 3.2 Get Device

```http
GET /v4/devices/{device_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "dev_abc123",
  "name": "Temperature Sensor 1",
  "type": "sensor",
  "status": "online",
  "connection": {
    "protocol": "MQTT",
    "lastConnected": "2026-01-08T14:32:00Z",
    "ipAddress": "192.168.1.100",
    "rssi": -45
  },
  "capabilities": [
    "telemetry",
    "commands",
    "ota-update"
  ],
  "metadata": {
    "manufacturer": "Nexus",
    "model": "TMP-100",
    "firmware": "2.4.1",
    "location": "Building A, Floor 2"
  },
  "tags": ["factory-a", "production-line-1"],
  "created": "2025-06-15T10:00:00Z",
  "updated": "2026-01-08T14:32:00Z"
}
```

### 3.3 Create Device

```http
POST /v4/devices
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Vibration Sensor 1",
  "type": "sensor",
  "metadata": {
    "manufacturer": "Nexus",
    "model": "VIB-200",
    "location": "Motor Bay 3"
  },
  "tags": ["factory-a", "maintenance"],
  "credentials": {
    "type": "certificate",
    "certificate": "-----BEGIN CERTIFICATE-----\n..."
  }
}
```

**Response:** `201 Created`

### 3.4 Update Device

```http
PATCH /v4/devices/{device_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Vibration Sensor 1 - Updated",
  "metadata": {
    "location": "Motor Bay 4"
  }
}
```

### 3.5 Delete Device

```http
DELETE /v4/devices/{device_id}
Authorization: Bearer {token}
```

**Response:** `204 No Content`

---

## 4. Telemetry API

### 4.1 Send Telemetry

```http
POST /v4/devices/{device_id}/telemetry
Authorization: Bearer {token}
Content-Type: application/json

{
  "timestamp": "2026-01-08T14:32:00Z",
  "values": {
    "temperature": 72.5,
    "humidity": 45.2,
    "pressure": 1013.25
  }
}
```

**Response:** `202 Accepted`

### 4.2 Query Telemetry

```http
GET /v4/devices/{device_id}/telemetry
Authorization: Bearer {token}
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start` | ISO8601 | Start time (required) |
| `end` | ISO8601 | End time (default: now) |
| `keys` | string | Comma-separated telemetry keys |
| `aggregation` | string | none, avg, min, max, sum |
| `interval` | string | Aggregation interval (1m, 5m, 1h, 1d) |

**Example:**
```http
GET /v4/devices/dev_abc123/telemetry?start=2026-01-08T00:00:00Z&end=2026-01-08T23:59:59Z&keys=temperature,humidity&aggregation=avg&interval=1h
```

**Response:**
```json
{
  "deviceId": "dev_abc123",
  "start": "2026-01-08T00:00:00Z",
  "end": "2026-01-08T23:59:59Z",
  "aggregation": "avg",
  "interval": "1h",
  "data": [
    {
      "timestamp": "2026-01-08T00:00:00Z",
      "values": {
        "temperature": 71.2,
        "humidity": 44.8
      }
    },
    {
      "timestamp": "2026-01-08T01:00:00Z",
      "values": {
        "temperature": 70.8,
        "humidity": 45.1
      }
    }
  ]
}
```

### 4.3 Stream Telemetry (WebSocket)

```javascript
const ws = new WebSocket('wss://stream.nexusconnect.io/v4/telemetry');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    devices: ['dev_abc123', 'dev_def456'],
    token: 'Bearer eyJhbGciOi...'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // { deviceId: 'dev_abc123', timestamp: '...', values: {...} }
};
```

---

## 5. Commands API

### 5.1 Send Command

```http
POST /v4/devices/{device_id}/commands
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "reboot",
  "parameters": {
    "delay": 30
  },
  "timeout": 60
}
```

**Response:**
```json
{
  "commandId": "cmd_xyz789",
  "status": "pending",
  "created": "2026-01-08T14:35:00Z",
  "timeout": "2026-01-08T14:36:00Z"
}
```

### 5.2 Get Command Status

```http
GET /v4/devices/{device_id}/commands/{command_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "commandId": "cmd_xyz789",
  "name": "reboot",
  "status": "completed",
  "result": {
    "success": true,
    "message": "Device rebooted successfully"
  },
  "created": "2026-01-08T14:35:00Z",
  "completed": "2026-01-08T14:35:45Z"
}
```

### 5.3 Command Status Values

| Status | Description |
|--------|-------------|
| `pending` | Command queued |
| `sent` | Delivered to device |
| `acknowledged` | Device received command |
| `completed` | Execution successful |
| `failed` | Execution failed |
| `timeout` | No response within timeout |

---

## 6. Alerts API

### 6.1 Create Alert Rule

```http
POST /v4/alerts/rules
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "High Temperature Alert",
  "description": "Alert when temperature exceeds threshold",
  "enabled": true,
  "conditions": {
    "type": "threshold",
    "device": "dev_abc123",
    "key": "temperature",
    "operator": "gt",
    "value": 85,
    "duration": "5m"
  },
  "actions": [
    {
      "type": "email",
      "recipients": ["ops@nexus-industries.com"]
    },
    {
      "type": "webhook",
      "url": "https://ops.nexus-industries.com/alerts",
      "headers": {
        "X-API-Key": "secret"
      }
    }
  ],
  "severity": "critical"
}
```

### 6.2 Alert Operators

| Operator | Description |
|----------|-------------|
| `eq` | Equal to |
| `ne` | Not equal to |
| `gt` | Greater than |
| `gte` | Greater than or equal |
| `lt` | Less than |
| `lte` | Less than or equal |
| `between` | Between two values |
| `outside` | Outside two values |

### 6.3 List Active Alerts

```http
GET /v4/alerts
Authorization: Bearer {token}
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | active, acknowledged, resolved |
| `severity` | string | info, warning, critical |
| `device` | string | Filter by device ID |

**Response:**
```json
{
  "data": [
    {
      "id": "alert_123",
      "ruleId": "rule_456",
      "ruleName": "High Temperature Alert",
      "deviceId": "dev_abc123",
      "severity": "critical",
      "status": "active",
      "message": "Temperature 87.5°F exceeds threshold 85°F",
      "triggered": "2026-01-08T14:40:00Z",
      "acknowledged": null,
      "resolved": null
    }
  ]
}
```

### 6.4 Acknowledge Alert

```http
POST /v4/alerts/{alert_id}/acknowledge
Authorization: Bearer {token}
Content-Type: application/json

{
  "note": "Investigating the issue"
}
```

---

## 7. Edge AI API

### 7.1 List Models

```http
GET /v4/models
Authorization: Bearer {token}
```

**Response:**
```json
{
  "data": [
    {
      "id": "model_abc123",
      "name": "Anomaly Detection v2",
      "type": "anomaly_detection",
      "version": "2.3.0",
      "framework": "tensorflow_lite",
      "inputShape": [1, 128],
      "outputShape": [1, 1],
      "size": 2457600,
      "created": "2025-12-01T00:00:00Z",
      "deployments": 45
    }
  ]
}
```

### 7.2 Deploy Model to Device

```http
POST /v4/models/{model_id}/deploy
Authorization: Bearer {token}
Content-Type: application/json

{
  "devices": ["dev_abc123", "dev_def456"],
  "configuration": {
    "inferenceInterval": 1000,
    "threshold": 0.85,
    "bufferSize": 128
  }
}
```

**Response:**
```json
{
  "deploymentId": "dep_xyz789",
  "status": "in_progress",
  "devices": [
    {
      "deviceId": "dev_abc123",
      "status": "downloading"
    },
    {
      "deviceId": "dev_def456",
      "status": "queued"
    }
  ]
}
```

### 7.3 Get Inference Results

```http
GET /v4/devices/{device_id}/inferences
Authorization: Bearer {token}
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | string | Filter by model ID |
| `start` | ISO8601 | Start time |
| `end` | ISO8601 | End time |
| `anomaliesOnly` | boolean | Return only anomalies |

**Response:**
```json
{
  "data": [
    {
      "timestamp": "2026-01-08T14:45:00Z",
      "modelId": "model_abc123",
      "input": [0.23, 0.45, 0.67, ...],
      "output": 0.92,
      "isAnomaly": true,
      "latency": 12
    }
  ]
}
```

---

## 8. Rate Limits

### 8.1 Limits by Tier

| Tier | Requests/sec | Requests/day | WebSocket Connections |
|------|--------------|--------------|----------------------|
| Starter | 10 | 10,000 | 5 |
| Professional | 100 | 100,000 | 50 |
| Enterprise | 1,000 | 1,000,000 | 500 |
| Unlimited | Custom | Custom | Custom |

### 8.2 Rate Limit Headers

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Requests allowed per second |
| `X-RateLimit-Remaining` | Requests remaining |
| `X-RateLimit-Reset` | Time until reset (Unix epoch) |

### 8.3 Rate Limit Exceeded

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after 1 second.",
    "retryAfter": 1
  }
}
```

---

## 9. Error Handling

### 9.1 Error Response Format

```json
{
  "error": {
    "code": "DEVICE_NOT_FOUND",
    "message": "Device with ID 'dev_invalid' not found",
    "details": {
      "deviceId": "dev_invalid"
    },
    "requestId": "req_abc123"
  }
}
```

### 9.2 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Temporary unavailability |

---

## 10. SDKs and Libraries

### 10.1 Official SDKs

| Language | Package | Install |
|----------|---------|---------|
| Python | `nexusconnect` | `pip install nexusconnect` |
| JavaScript | `@nexus/connect` | `npm install @nexus/connect` |
| Java | `com.nexus.connect` | Maven |
| Go | `github.com/nexus/connect-go` | `go get` |
| C# | `Nexus.Connect` | NuGet |

### 10.2 Python Example

```python
from nexusconnect import NexusClient

client = NexusClient(
    api_key="your_api_key",
    org_id="your_org_id"
)

# List devices
devices = client.devices.list(status="online")

# Get telemetry
telemetry = client.telemetry.query(
    device_id="dev_abc123",
    start="2026-01-08T00:00:00Z",
    keys=["temperature", "humidity"]
)

# Send command
result = client.commands.send(
    device_id="dev_abc123",
    name="reboot",
    timeout=60
)
```

---

## 11. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 4.2 | Jan 2026 | Performance improvements, batch operations |
| 4.1 | Dec 2025 | Enhanced security, API key rotation |
| 4.0 | Oct 2025 | Edge AI APIs, model deployment |
| 3.5 | Aug 2025 | WebSocket streaming, alerts v2 |
| 3.0 | Jun 2025 | Major revision, new authentication |

---

**Prepared By:** Dr. Alan Chen, VP Engineering
**Approved By:** Robert Kim, Division President
**Classification:** Internal
