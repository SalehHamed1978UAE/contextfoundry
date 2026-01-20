# Context Foundry — Test Runner Dashboard Specification

**Version:** 1.0
**Date:** January 20, 2026
**Purpose:** Full visibility and control over test execution

---

## Problem Statement

Running tests in background workflows is unreliable:
- Can't see progress in real-time
- Workflows restart and interrupt tests
- No visibility into errors until after the fact
- Have to repeatedly ask "status?"
- Can't make informed decisions about continue vs fresh start
- No way to upload custom question sets
- No way to run specific question sets against specific vaults

---

## Solution

Build a **Test Runner Dashboard** accessible from the Vaults page that provides:
1. Full visibility into test progress
2. Ability to upload and manage question sets
3. Ability to run any question set against any vault
4. Real-time logs and status
5. Test history with resume capability

---

## Entry Point

**Location:** Vaults page (where all vaults are listed)

**New button:** `[🧪 Test Runner]` in the page header

**Behavior:** Clicking opens the Test Runner Dashboard as a full page

---

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ← Back to Vaults                                    TEST RUNNER            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─── QUESTION SETS ────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  Name              Questions  Uploaded       Actions                 │   │
│  │  ───────────────────────────────────────────────────────────────────│   │
│  │  NexaTech-105      105        2026-01-10     [View] [Delete]        │   │
│  │  MedSync-235       235        2026-01-15     [View] [Delete]        │   │
│  │  Manus-235         235        2026-01-17     [View] [Delete]        │   │
│  │  Custom-50         50         2026-01-19     [View] [Delete]        │   │
│  │                                                                      │   │
│  │  [📤 Upload Question Set]                                            │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─── START NEW TEST ───────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  Vault:         [Dropdown: Select vault...]                          │   │
│  │                 Shows: vault name, entity count, last updated        │   │
│  │                                                                      │   │
│  │  Question Set:  [Dropdown: Select question set...]                   │   │
│  │                 Shows: name, question count                          │   │
│  │                                                                      │   │
│  │  Mode:          ○ Auto (resume if checkpoint exists)                 │   │
│  │                 ○ Fresh (delete vault, re-upload, re-extract, run)   │   │
│  │                                                                      │   │
│  │  Corpus Folder: [Dropdown: Select corpus...] (only shown if Fresh)   │   │
│  │                 Shows available corpus folders for upload            │   │
│  │                                                                      │   │
│  │  [▶ START TEST]  (disabled if test already running)                  │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─── CURRENT TEST ─────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  Vault: Manus HealthTech Clean          Status: 🔄 RUNNING           │   │
│  │  Question Set: Manus-235                Started: 10:42:00            │   │
│  │                                                                      │   │
│  │  ┌─ Pipeline Progress ───────────────────────────────────────────┐   │   │
│  │  │                                                               │   │   │
│  │  │  [1] Delete vault      ✅ Complete                            │   │   │
│  │  │  [2] Create vault      ✅ Complete (id: 47d54408-69f8...)     │   │   │
│  │  │  [3] Upload docs       ✅ Complete (114 files, 45s)           │   │   │
│  │  │  [4] Extraction        ✅ Complete (1050 entities, 81 rels)   │   │   │
│  │  │  [5] Q&A               🔄 Running                             │   │   │
│  │  │                                                               │   │   │
│  │  └───────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─ Q&A Progress ────────────────────────────────────────────────┐   │   │
│  │  │                                                               │   │   │
│  │  │  Progress: 196 / 235 questions                                │   │   │
│  │  │  ████████████████████████████░░░░░░░░  83.4%                  │   │   │
│  │  │                                                               │   │   │
│  │  │  ✅ Passed: 180    ❌ Failed: 16    📊 Accuracy: 91.8%        │   │   │
│  │  │                                                               │   │   │
│  │  └───────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Current Question: Q196                                              │   │
│  │  ┌───────────────────────────────────────────────────────────────┐   │   │
│  │  │ "What is the total revenue for FY 2024?"                      │   │   │
│  │  └───────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  [⏹ STOP TEST]                                                       │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─── TEST HISTORY ─────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  Vault              Question Set   Date         Status    Result     │   │
│  │  ──────────────────────────────────────────────────────────────────  │   │
│  │  Manus Clean        Manus-235      2026-01-19   🔄 RUNNING  196/235  │   │
│  │    └─ [View Progress]                                                │   │
│  │                                                                      │   │
│  │  Manus Clean        Manus-235      2026-01-19   ⚠️ INTERRUPTED       │   │
│  │    └─ 195/235 (83.0%)              [Resume] [View Results]           │   │
│  │                                                                      │   │
│  │  NexaTech Prod      NexaTech-105   2026-01-17   ✅ COMPLETE          │   │
│  │    └─ 99/105 (94.3%)               [View Results]                    │   │
│  │                                                                      │   │
│  │  MedSync Test       MedSync-235    2026-01-15   ✅ COMPLETE          │   │
│  │    └─ 215/235 (91.5%)              [View Results]                    │   │
│  │                                                                      │   │
│  │  Old Test           Custom-50      2026-01-10   ❌ FAILED            │   │
│  │    └─ Error: Extraction timeout    [View Logs] [Retry]               │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─── LIVE LOG ─────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  10:42:15 [INFO]  [Q&A] Starting question Q196                       │   │
│  │  10:42:15 [INFO]  [Q&A] Q196: Querying API...                        │   │
│  │  10:42:16 [INFO]  [Q&A] Q196: Response received (0.8s)               │   │
│  │  10:42:16 [PASS]  [Q&A] Q196: ✅ PASS                                │   │
│  │           Expected: "AED 485,100,000"                                │   │
│  │           Actual:   "AED 485,100,000"                                │   │
│  │  10:42:16 [INFO]  [Q&A] Starting question Q197                       │   │
│  │  10:42:17 [INFO]  [Q&A] Q197: Response received (0.9s)               │   │
│  │  10:42:17 [FAIL]  [Q&A] Q197: ❌ FAIL                                │   │
│  │           Expected: "$485M"                                          │   │
│  │           Actual:   "AED 485,100,000"                                │   │
│  │           Reason:   Format mismatch                                  │   │
│  │  10:42:17 [INFO]  [Q&A] Starting question Q198                       │   │
│  │  10:42:18 [WARN]  [Q&A] Q198: Slow response (2.1s)                   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐     │   │
│  │  │ [✓] Auto-scroll          [Filter: All ▼]    [Clear] [Export]│     │   │
│  │  └─────────────────────────────────────────────────────────────┘     │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Functional Requirements

### 1. Question Set Management

#### 1.1 Question Sets Table

Displays all uploaded question sets with:
- **Name** — User-defined name
- **Questions** — Count of questions in set
- **Uploaded** — Date uploaded
- **Actions** — View, Delete

#### 1.2 Upload Question Set

**Button:** `[📤 Upload Question Set]`

**Accepted formats:**
- `.json` — Array of question objects
- `.jsonl` — One question object per line

**Required schema per question:**
```json
{
  "id": "Q1",
  "question": "What is the company's total revenue for FY 2024?",
  "expected_answer": "$485M",
  "category": "financial"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique identifier (e.g., "Q1", "Q2") |
| question | Yes | The question text |
| expected_answer | Yes | Expected answer for comparison |
| category | No | Optional grouping (financial, hr, operations, etc.) |

**Upload flow:**
1. User clicks `[📤 Upload Question Set]`
2. File picker opens (accepts .json, .jsonl)
3. System validates format and schema
4. If valid: Prompt user to name the question set (default: filename)
5. If invalid: Show error with details (which questions failed validation)
6. Question set saved and appears in table

#### 1.3 View Question Set

Opens modal showing all questions:
- Sortable/filterable table
- Columns: ID, Question, Expected Answer, Category
- Export button (download as JSON or JSONL)

#### 1.4 Delete Question Set

- Confirmation dialog: "Delete question set 'Manus-235'? This cannot be undone."
- Cannot delete if question set is currently in use by a running test

---

### 2. Start New Test

#### 2.1 Form Fields

| Field | Type | Description |
|-------|------|-------------|
| Vault | Dropdown | All vaults user has access to. Shows: name, entity count, last updated |
| Question Set | Dropdown | All uploaded question sets. Shows: name, question count |
| Mode | Radio | **Auto** (default) or **Fresh** |
| Corpus Folder | Dropdown | Only shown if Fresh mode. Which document corpus to upload |

#### 2.2 Mode Definitions

**Auto Mode (default):**
1. Check if checkpoint exists for this vault + question set combination
2. If checkpoint exists AND vault still has data:
   - Skip to Q&A stage
   - Resume from last answered question
3. If no checkpoint OR vault is empty:
   - Run full pipeline (but don't delete existing vault data)

**Fresh Mode:**
1. Delete all data in selected vault
2. Upload documents from selected corpus folder
3. Run extraction pipeline
4. Wait for extraction to complete
5. Run full Q&A

#### 2.3 Start Button States

| State | Button |
|-------|--------|
| Ready | `[▶ START TEST]` enabled |
| Test running | `[▶ START TEST]` disabled, shows "Test in progress..." |
| Missing selection | `[▶ START TEST]` disabled until vault + question set selected |

---

### 3. Current Test Panel

#### 3.1 Header Info

- **Vault** — Name of vault being tested
- **Question Set** — Name of question set being used
- **Status** — RUNNING, COMPLETE, INTERRUPTED, FAILED
- **Started** — Timestamp when test began

#### 3.2 Pipeline Progress

Shows 5 stages with status icons:

| Stage | Icon States | Details Shown |
|-------|-------------|---------------|
| [1] Delete vault | ⏳ Pending / 🔄 Running / ✅ Complete / ⏭️ Skipped | — |
| [2] Create vault | ⏳ Pending / 🔄 Running / ✅ Complete / ⏭️ Skipped | Vault ID when complete |
| [3] Upload docs | ⏳ Pending / 🔄 Running / ✅ Complete / ⏭️ Skipped | File count, duration |
| [4] Extraction | ⏳ Pending / 🔄 Running / ✅ Complete / ⏭️ Skipped | Entity count, relationship count |
| [5] Q&A | ⏳ Pending / 🔄 Running / ✅ Complete | Progress bar, counts |

**Skipped** — Shown when Auto mode resumes from checkpoint

#### 3.3 Q&A Progress

- **Progress bar** — Visual representation of X/Y questions
- **Passed count** — Green, with checkmark icon
- **Failed count** — Red, with X icon
- **Accuracy** — Calculated as passed / answered, shown as percentage

#### 3.4 Current Question Display

Shows the question currently being processed:
- Question ID (e.g., "Q196")
- Full question text in a box

#### 3.5 Stop Button

`[⏹ STOP TEST]`

- Gracefully stops test after current question completes
- Saves checkpoint so test can be resumed
- Changes status to INTERRUPTED

---

### 4. Test History

#### 4.1 History Table

| Column | Description |
|--------|-------------|
| Vault | Vault name |
| Question Set | Question set name |
| Date | When test was started |
| Status | RUNNING, COMPLETE, INTERRUPTED, FAILED |
| Result | X/Y (percentage) |
| Actions | Context-dependent buttons |

#### 4.2 Status Icons and Colors

| Status | Icon | Color |
|--------|------|-------|
| RUNNING | 🔄 | Blue |
| COMPLETE | ✅ | Green |
| INTERRUPTED | ⚠️ | Yellow/Orange |
| FAILED | ❌ | Red |

#### 4.3 Actions by Status

| Status | Available Actions |
|--------|-------------------|
| RUNNING | [View Progress] — scrolls to Current Test panel |
| COMPLETE | [View Results] — opens results modal |
| INTERRUPTED | [Resume] — restarts test from checkpoint, [View Results] — shows partial results |
| FAILED | [View Logs] — shows error details, [Retry] — starts fresh test with same config |

#### 4.4 View Results Modal

Shows detailed Q&A results:

```
┌─────────────────────────────────────────────────────────────────┐
│  TEST RESULTS: Manus HealthTech Clean × Manus-235               │
│  Date: 2026-01-19 10:42:00                                      │
│  Status: COMPLETE                                               │
│  Result: 215/235 (91.5%)                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Filter: [All ▼] [Passed ▼] [Failed ▼]    Search: [________]    │
│                                                                 │
│  ID    Question                    Expected      Actual    Pass │
│  ───────────────────────────────────────────────────────────────│
│  Q1    What is the CEO's name?     John Smith    John Smith  ✅ │
│  Q2    Total revenue FY 2024?      $485M         $485M       ✅ │
│  Q3    Headquarters location?      Boston, MA    Boston, MA  ✅ │
│  Q4    Net income FY 2023?         -$13.2M       -$12.4M     ❌ │
│        └─ Reason: Value mismatch                                │
│  ...                                                            │
│                                                                 │
│  [Export JSON] [Export CSV]                          [Close]    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 5. Live Log Panel

#### 5.1 Log Display

- Scrollable log area showing real-time output
- Each line has timestamp, level, component, message
- Color-coded by level

#### 5.2 Log Levels and Colors

| Level | Color | Example |
|-------|-------|---------|
| INFO | White/Gray | `[INFO] Starting question Q196` |
| PASS | Green | `[PASS] Q196: ✅ PASS` |
| FAIL | Red | `[FAIL] Q197: ❌ FAIL` |
| WARN | Yellow | `[WARN] Slow response (2.1s)` |
| ERROR | Red (bold) | `[ERROR] API connection failed` |

#### 5.3 Log Controls

| Control | Function |
|---------|----------|
| Auto-scroll checkbox | When checked, automatically scrolls to newest log entry |
| Filter dropdown | Show All, Info only, Errors only, Pass/Fail only |
| Clear button | Clears the log display (doesn't affect stored logs) |
| Export button | Downloads full log as .log file |

---

## API Specification

### Question Sets Endpoints

#### Upload Question Set
```
POST /api/test-runner/question-sets/upload
Content-Type: multipart/form-data

Body:
  - file: The .json or .jsonl file
  - name: (optional) Name for the question set

Response (201 Created):
{
  "id": "uuid",
  "name": "Manus-235",
  "question_count": 235,
  "uploaded_at": "2026-01-19T10:00:00Z"
}

Response (400 Bad Request):
{
  "error": "Invalid question format",
  "details": [
    {"line": 5, "error": "Missing required field 'expected_answer'"},
    {"line": 12, "error": "Invalid JSON syntax"}
  ]
}
```

#### List Question Sets
```
GET /api/test-runner/question-sets

Response (200 OK):
{
  "question_sets": [
    {
      "id": "uuid-1",
      "name": "NexaTech-105",
      "question_count": 105,
      "uploaded_at": "2026-01-10T08:00:00Z"
    },
    {
      "id": "uuid-2",
      "name": "MedSync-235",
      "question_count": 235,
      "uploaded_at": "2026-01-15T09:30:00Z"
    }
  ]
}
```

#### Get Question Set Details
```
GET /api/test-runner/question-sets/{id}

Response (200 OK):
{
  "id": "uuid",
  "name": "Manus-235",
  "question_count": 235,
  "uploaded_at": "2026-01-17T10:00:00Z",
  "questions": [
    {
      "id": "Q1",
      "question": "What is the CEO's name?",
      "expected_answer": "John Smith",
      "category": "leadership"
    },
    ...
  ]
}
```

#### Delete Question Set
```
DELETE /api/test-runner/question-sets/{id}

Response (200 OK):
{
  "deleted": true
}

Response (409 Conflict):
{
  "error": "Question set is in use by running test",
  "test_id": "uuid"
}
```

### Test Execution Endpoints

#### Start Test
```
POST /api/test-runner/start

Body:
{
  "vault_id": "uuid",
  "question_set_id": "uuid",
  "mode": "auto" | "fresh",
  "corpus_folder": "Manus Healthtec"  // required if mode is "fresh"
}

Response (201 Created):
{
  "test_id": "uuid",
  "status": "running",
  "started_at": "2026-01-19T10:42:00Z"
}

Response (409 Conflict):
{
  "error": "Test already running",
  "test_id": "existing-test-uuid"
}
```

#### Get Test Status
```
GET /api/test-runner/status

Response (200 OK) — Test running:
{
  "running": true,
  "test_id": "uuid",
  "vault_id": "uuid",
  "vault_name": "Manus HealthTech Clean",
  "question_set_id": "uuid",
  "question_set_name": "Manus-235",
  "started_at": "2026-01-19T10:42:00Z",
  "mode": "auto",
  "stage": "qa",
  "stages": {
    "delete": {"status": "skipped"},
    "create": {"status": "skipped"},
    "upload": {"status": "skipped"},
    "extract": {"status": "skipped"},
    "qa": {"status": "running"}
  },
  "qa_progress": {
    "total": 235,
    "answered": 196,
    "passed": 180,
    "failed": 16,
    "accuracy_percent": 91.8
  },
  "current_question": {
    "id": "Q197",
    "text": "What is the total revenue for FY 2024?"
  },
  "errors": []
}

Response (200 OK) — No test running:
{
  "running": false,
  "test_id": null
}
```

#### Stop Test
```
POST /api/test-runner/stop

Response (200 OK):
{
  "stopped": true,
  "test_id": "uuid",
  "final_status": "interrupted",
  "qa_progress": {
    "answered": 196,
    "passed": 180,
    "failed": 16
  }
}

Response (400 Bad Request):
{
  "error": "No test running"
}
```

### History & Results Endpoints

#### Get Test History
```
GET /api/test-runner/history
Query params:
  - limit (optional): Number of results (default 20)
  - offset (optional): Pagination offset

Response (200 OK):
{
  "tests": [
    {
      "test_id": "uuid-1",
      "vault_id": "uuid",
      "vault_name": "Manus HealthTech Clean",
      "question_set_id": "uuid",
      "question_set_name": "Manus-235",
      "started_at": "2026-01-19T10:42:00Z",
      "completed_at": "2026-01-19T11:15:00Z",
      "status": "complete",
      "questions_total": 235,
      "questions_passed": 215,
      "questions_failed": 20,
      "accuracy_percent": 91.5
    },
    ...
  ],
  "total": 15
}
```

#### Get Test Results
```
GET /api/test-runner/results/{test_id}

Response (200 OK):
{
  "test_id": "uuid",
  "vault_name": "Manus HealthTech Clean",
  "question_set_name": "Manus-235",
  "started_at": "2026-01-19T10:42:00Z",
  "completed_at": "2026-01-19T11:15:00Z",
  "status": "complete",
  "summary": {
    "total": 235,
    "passed": 215,
    "failed": 20,
    "accuracy_percent": 91.5
  },
  "results": [
    {
      "question_id": "Q1",
      "question": "What is the CEO's name?",
      "expected_answer": "John Smith",
      "actual_answer": "John Smith",
      "passed": true,
      "duration_ms": 850,
      "category": "leadership"
    },
    {
      "question_id": "Q4",
      "question": "Net income FY 2023?",
      "expected_answer": "-$13.2M",
      "actual_answer": "-$12.4M",
      "passed": false,
      "failure_reason": "Value mismatch",
      "duration_ms": 920,
      "category": "financial"
    },
    ...
  ]
}
```

### Logs Endpoint

#### Stream Logs (Server-Sent Events)
```
GET /api/test-runner/logs

Response: SSE stream

event: log
data: {"timestamp": "2026-01-19T10:42:15Z", "level": "INFO", "component": "Q&A", "message": "Starting question Q196"}

event: log
data: {"timestamp": "2026-01-19T10:42:16Z", "level": "PASS", "component": "Q&A", "message": "Q196: PASS", "details": {"expected": "AED 485M", "actual": "AED 485M"}}

event: log
data: {"timestamp": "2026-01-19T10:42:17Z", "level": "FAIL", "component": "Q&A", "message": "Q197: FAIL", "details": {"expected": "$485M", "actual": "AED 485,100,000", "reason": "Format mismatch"}}
```

---

## Database Schema

### question_sets
```sql
CREATE TABLE question_sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  question_count INTEGER NOT NULL,
  questions JSONB NOT NULL,
  uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  uploaded_by UUID REFERENCES users(id),
  
  CONSTRAINT unique_question_set_name UNIQUE (name)
);

CREATE INDEX idx_question_sets_name ON question_sets(name);
```

### test_runs
```sql
CREATE TABLE test_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vault_id UUID NOT NULL,
  vault_name VARCHAR(255) NOT NULL,
  question_set_id UUID REFERENCES question_sets(id),
  question_set_name VARCHAR(255) NOT NULL,
  mode VARCHAR(20) NOT NULL CHECK (mode IN ('auto', 'fresh')),
  corpus_folder VARCHAR(255),
  
  status VARCHAR(20) NOT NULL DEFAULT 'running' 
    CHECK (status IN ('running', 'complete', 'interrupted', 'failed')),
  stage VARCHAR(20) 
    CHECK (stage IN ('delete', 'create', 'upload', 'extract', 'qa', 'complete')),
  
  started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  completed_at TIMESTAMP WITH TIME ZONE,
  
  questions_total INTEGER,
  questions_answered INTEGER DEFAULT 0,
  questions_passed INTEGER DEFAULT 0,
  questions_failed INTEGER DEFAULT 0,
  
  checkpoint JSONB,
  error_message TEXT,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_test_runs_status ON test_runs(status);
CREATE INDEX idx_test_runs_vault ON test_runs(vault_id);
CREATE INDEX idx_test_runs_started ON test_runs(started_at DESC);
```

### test_results
```sql
CREATE TABLE test_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  test_run_id UUID REFERENCES test_runs(id) ON DELETE CASCADE,
  
  question_id VARCHAR(50) NOT NULL,
  question_text TEXT NOT NULL,
  expected_answer TEXT NOT NULL,
  actual_answer TEXT,
  category VARCHAR(100),
  
  passed BOOLEAN NOT NULL,
  failure_reason TEXT,
  duration_ms INTEGER,
  
  answered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  CONSTRAINT unique_test_question UNIQUE (test_run_id, question_id)
);

CREATE INDEX idx_test_results_run ON test_results(test_run_id);
CREATE INDEX idx_test_results_passed ON test_results(test_run_id, passed);
```

---

## File Storage

### Checkpoint File
Location: `data/test-runner/checkpoints/{test_id}.json`

```json
{
  "test_id": "uuid",
  "vault_id": "uuid",
  "vault_name": "Manus HealthTech Clean",
  "question_set_id": "uuid",
  "question_set_name": "Manus-235",
  "mode": "fresh",
  "started_at": "2026-01-19T10:42:00Z",
  "stage": "qa",
  "stages_completed": {
    "delete": {"completed_at": "2026-01-19T10:42:05Z"},
    "create": {"completed_at": "2026-01-19T10:42:10Z", "vault_id": "uuid"},
    "upload": {"completed_at": "2026-01-19T10:45:00Z", "file_count": 114},
    "extract": {"completed_at": "2026-01-19T10:55:00Z", "entities": 1050, "relationships": 81}
  },
  "qa_progress": {
    "total": 235,
    "answered": 196,
    "last_question_id": "Q196"
  }
}
```

### Log File
Location: `data/test-runner/logs/{test_id}.log`

Plain text, one log entry per line:
```
2026-01-19T10:42:15Z [INFO] [Q&A] Starting question Q196
2026-01-19T10:42:16Z [INFO] [Q&A] Q196: Response received (0.8s)
2026-01-19T10:42:16Z [PASS] [Q&A] Q196: PASS | Expected: "AED 485M" | Actual: "AED 485M"
```

---

## Runner Script Integration

The existing runner script needs to emit events that the API can consume.

### Option A: Write to status file (simpler)

Runner writes to `data/test-runner/status/{test_id}.json` after each operation:

```json
{
  "stage": "qa",
  "qa_progress": {
    "answered": 196,
    "passed": 180,
    "failed": 16
  },
  "current_question": {
    "id": "Q197",
    "text": "What is the total revenue for FY 2024?"
  },
  "last_updated": "2026-01-19T10:42:17Z"
}
```

API polls this file for status endpoint.

### Option B: Message queue (more robust)

Runner publishes events to Redis pub/sub or similar:

```
PUBLISH test-runner:uuid {"event": "question_complete", "question_id": "Q196", "passed": true}
```

API subscribes and forwards to SSE clients.

### Recommendation

Start with Option A (status file). It's simpler and the polling overhead is minimal. Can upgrade to Option B later if needed.

---

## Error Handling

### Test Execution Errors

| Error | Behavior |
|-------|----------|
| Vault not found | Fail test immediately, show error |
| Question set not found | Fail test immediately, show error |
| Corpus folder not found | Fail test immediately, show error |
| Upload fails | Retry 3 times, then fail test |
| Extraction timeout (>30 min) | Fail test, save checkpoint |
| API error during Q&A | Log error, skip question, continue |
| Server crash | Test status remains "running", user can check and resume |

### Recovery Behavior

When user clicks Resume on an INTERRUPTED test:
1. Load checkpoint file
2. Verify vault still exists and has data
3. If vault OK: Resume Q&A from last answered question
4. If vault deleted: Fail with error "Vault no longer exists. Run Fresh test."

---

## Build Priority

**Phase 1: Core functionality**
1. Question Sets table + Upload
2. Start Test form (vault + question set dropdowns)
3. Status endpoint + Current Test panel (basic)
4. Test History table (basic)

**Phase 2: Full visibility**
5. Live Log panel with SSE streaming
6. Detailed stage progress in Current Test
7. View Results modal with filtering

**Phase 3: Polish**
8. Resume functionality
9. Export options (JSON, CSV, logs)
10. Stop test gracefully

---

## Success Criteria

A test run is trustworthy when:
- [ ] I can see real-time progress without asking "status?"
- [ ] I can see exactly which stage is running
- [ ] I can see pass/fail results as they happen
- [ ] If something fails, I see the error immediately
- [ ] I can resume an interrupted test with one click
- [ ] I can compare results across multiple test runs
- [ ] The test runs start-to-finish without manual intervention

---

## Notes

- Only one test can run at a time (for v1)
- Test results are persisted even if browser is closed
- Logs are kept for 30 days, then auto-deleted
- Question sets are never auto-deleted (user must manually delete)
