# Program Planning Starter Kit - Hybrid Implementation Specification

**Version:** 3.0 (Hybrid)
**Date:** January 28, 2026
**Purpose:** Fix EPM quality issues with disciplined, checkpoint-gated implementation

---

## THE THREE LAWS (Non-Negotiable)

> **Read this section before EVERY coding session. Replit forgets context.**

### Law 1: Per-Task Proof Required
Before marking ANY task complete, provide:
- Console logs showing code executed
- DB screenshots showing data created/modified
- Test output showing pass/fail
- For exports: attach actual Excel/PDF files

### Law 2: No Guessing
- If a file path is mentioned, READ IT first
- If a line number is given, VERIFY it still matches
- If unsure about existing behavior, TEST before changing

### Law 3: One Task at a Time
- Complete Task X.1 fully before starting Task X.2
- Do not skip ahead
- Do not "batch" multiple tasks

---

## CONTEXT RECOVERY CHECKLIST

**When starting a new session, verify:**
- [ ] Which phase am I in?
- [ ] Which task am I on?
- [ ] What evidence have I already delivered?
- [ ] Are all regression tests passing?
- [ ] Run: `npx tsc --noEmit` to verify no compile errors

---

## PROBLEM STATEMENT

### Current Bugs (We're Fixing Broken, Not Building New)

| Bug | Example | Root Cause | Line |
|-----|---------|------------|------|
| Template contamination | Sneaker store gets "Food Safety Compliance" | Generic prompts | `wbs-builder.ts` |
| Illogical dependencies | WS002 depends on WS001 but both start Month 1 | No validation | `epm-synthesizer.ts:446` |
| Generic risk mitigations | All say "Monitor and implement controls" | Hardcoded template | `epm-synthesizer.ts:1514` |
| Wrong FTE units | Shows "100" instead of "1.0" | No normalization | `epm-synthesizer.ts` resourcePlan |
| Unmeasurable KPIs | Target is "Improvement" | Fallback string | `epm-synthesizer.ts:1570` |
| Benefits = SWOT copy | Just copies opportunities verbatim | No transformation | `epm-synthesizer.ts:1464-1474` |

### Quality Targets

After implementation, EPM output must:
- [ ] Have workstreams relevant to specific industry (no sneaker+food)
- [ ] Have valid dependency chains (predecessor ends before successor starts)
- [ ] Have FTE values between 0.0 and 1.0
- [ ] Have specific, actionable risk mitigations (not templates)
- [ ] Have measurable KPI targets (not "Improvement")
- [ ] Have benefits derived from strategy (not copied from SWOT)

---

## ARCHITECTURE OVERVIEW

### Current Flow
```
Strategic Understanding → WBS Builder → EPM Synthesizer → Export Service
        ↓                      ↓               ↓              ↓
   Business Context     Workstreams    14 Components    Excel/CSV/MD
```

### Enhanced Flow (What We're Building)
```
Strategic Understanding
    → Initiative Normalizer (new) ──────────────────┐
    → WBS Builder (enhanced prompts) ───────────────┤
    → Dependency Validator (new) ───────────────────┤
    → Industry Validator (new) ─────────────────────┤
    → FTE Normalizer (new) ─────────────────────────┤
    → EPM Synthesizer (enhanced prompts) ───────────┤
    → Quality Gates (new) ──────────────────────────┤
    → Export Service (Excel + PDF) ─────────────────┘
```

### File Structure
```
/server/intelligence/
├── validators/
│   ├── dependency-validator.ts
│   ├── industry-validator.ts
│   ├── completeness-validator.ts
│   └── quality-gate.ts
├── normalizers/
│   ├── initiative-normalizer.ts
│   └── fte-normalizer.ts
├── prompts/
│   ├── workstream-prompt.ts
│   ├── risk-mitigation-prompt.ts
│   └── kpi-prompt.ts
├── resource-generator.ts
├── budget-generator.ts
└── assumption-extractor.ts

/server/services/
├── excel-export-service.ts
└── pdf-export-service.ts
```

---

## PHASE 0: QUICK BUG FIXES (Do First)

> **Objective:** Fix the 6 known bugs with minimal code changes. Quick wins before architecture.

---

### Task 0.1: Fix Generic Risk Mitigation

**File:** `server/intelligence/epm-synthesizer.ts`
**Line:** 1514 (verify before editing)

**Current Code:**
```typescript
mitigation: `Monitor and implement controls to reduce ${impact.toLowerCase()} impact`,
```

**Replace With:**
```typescript
mitigation: this.generateSpecificMitigation(insight, insights),
```

**Add Method (in same file):**
```typescript
private generateSpecificMitigation(insight: StrategyInsight, allInsights: StrategyInsights): string {
  const content = insight.content.toLowerCase();
  const impact = insight.impact || 'medium';

  // Industry-specific mitigations
  if (content.includes('staff') || content.includes('employee') || content.includes('turnover')) {
    return `Cross-train 2+ backup staff on critical roles; document all procedures with video tutorials; establish relationships with 2 staffing agencies for emergency coverage`;
  }
  if (content.includes('supply') || content.includes('supplier') || content.includes('vendor')) {
    return `Qualify 2 backup suppliers per critical category; maintain 2-week safety stock; negotiate flexible delivery terms with primary supplier`;
  }
  if (content.includes('cost') || content.includes('budget') || content.includes('expense')) {
    return `Implement weekly cost tracking dashboard; establish 10% contingency reserve; require approval for any expense >$5000; monthly variance review with stakeholders`;
  }
  if (content.includes('delay') || content.includes('timeline') || content.includes('schedule')) {
    return `Break into 2-week milestones with go/no-go gates; identify parallel paths for critical activities; pre-negotiate resource availability with vendors`;
  }
  if (content.includes('competition') || content.includes('competitor') || content.includes('market')) {
    return `Monthly competitive analysis; differentiation strategy review quarterly; customer feedback loop to identify unmet needs; agile pricing response process`;
  }
  if (content.includes('regulatory') || content.includes('compliance') || content.includes('permit')) {
    return `Engage regulatory consultant in Month 1; submit applications 4 weeks early; maintain compliance checklist with weekly reviews; establish escalation path to legal`;
  }
  if (content.includes('technology') || content.includes('system') || content.includes('software')) {
    return `Proof of concept before full deployment; vendor SLA with 4-hour response time; maintain rollback capability; user acceptance testing before go-live`;
  }

  // Default based on impact
  if (impact === 'Critical' || impact === 'High') {
    return `Assign dedicated owner for daily monitoring; establish early warning triggers; maintain contingency budget of 15%; weekly status review with steering committee`;
  }
  return `Monitor via monthly review cycle; establish escalation criteria; document response procedures; assign backup owner`;
}
```

**Acceptance Criteria:**
- [ ] No risk has "Monitor and implement controls" text
- [ ] Mitigations are specific to risk content

**Evidence Required:**
1. Screenshot of modified code in context
2. Run journey, export risks, show mitigations are specific

---

### Task 0.2: Fix Unmeasurable KPI Targets

**File:** `server/intelligence/epm-synthesizer.ts`
**Line:** 1570 (verify before editing)

**Current Code:**
```typescript
target: benefit.estimatedValue ? `+${benefit.estimatedValue.toLocaleString()}` : 'Improvement',
```

**Replace With:**
```typescript
target: this.generateMeasurableTarget(benefit, insights),
```

**Add Method:**
```typescript
private generateMeasurableTarget(benefit: any, insights: StrategyInsights): string {
  const content = benefit.content?.toLowerCase() || benefit.description?.toLowerCase() || '';

  if (benefit.estimatedValue) {
    return `+${benefit.estimatedValue.toLocaleString()} (${benefit.estimatedValue > 10000 ? 'annual' : 'monthly'})`;
  }

  // Generate specific targets based on benefit type
  if (content.includes('revenue') || content.includes('sales')) {
    return '+15% revenue growth within 12 months';
  }
  if (content.includes('cost') || content.includes('efficiency')) {
    return '10% cost reduction by end of program';
  }
  if (content.includes('customer') || content.includes('satisfaction')) {
    return 'CSAT score ≥4.5/5.0 within 6 months';
  }
  if (content.includes('time') || content.includes('speed') || content.includes('faster')) {
    return '25% reduction in cycle time';
  }
  if (content.includes('quality') || content.includes('error') || content.includes('defect')) {
    return 'Error rate <2% within 3 months';
  }
  if (content.includes('market') || content.includes('share')) {
    return 'Capture 5% market share within 12 months';
  }
  if (content.includes('employee') || content.includes('retention') || content.includes('turnover')) {
    return 'Employee retention >90% annually';
  }

  // Default: At least give a measurable format
  return 'Achieve baseline +20% within program timeline';
}
```

**Acceptance Criteria:**
- [ ] No KPI has target "Improvement"
- [ ] All targets have numbers or percentages

**Evidence Required:**
1. Screenshot of modified code
2. Export KPIs, verify all targets are measurable

---

### Task 0.3: Fix FTE Values (100 → 1.0)

**File:** `server/intelligence/epm-synthesizer.ts`
**Location:** Find `resourcePlan` or `internalTeam` generation

**Add Normalizer Call:**
```typescript
// After generating resource allocations, normalize FTE
function normalizeFTE(value: number): number {
  if (value > 10) return value / 100;  // 100 → 1.0, 80 → 0.8
  if (value > 1.0) return 1.0;          // Cap at 1.0
  return value;
}

// Apply to all FTE values before saving
for (const role of resourcePlan.internalTeam) {
  role.fteAllocation = normalizeFTE(role.fteAllocation);
}
```

**Acceptance Criteria:**
- [ ] All FTE values in output are 0.0-1.0
- [ ] Values like 100, 80, 50 become 1.0, 0.8, 0.5

**Evidence Required:**
1. Export resources, screenshot showing FTE values ≤ 1.0

---

### Task 0.4: Add Dependency Validation

**File:** `server/intelligence/epm-synthesizer.ts`
**Location:** After `generateWorkstreams()` call (around line 446)

**Add Validation:**
```typescript
// After workstreams generated, validate dependencies
const workstreamMap = new Map(workstreams.map(ws => [ws.id, ws]));

for (const ws of workstreams) {
  if (!ws.dependencies || ws.dependencies.length === 0) continue;

  const invalidDeps: string[] = [];
  for (const depId of ws.dependencies) {
    const predecessor = workstreamMap.get(depId);
    if (!predecessor) {
      console.warn(`[EPM] ${ws.id} depends on non-existent ${depId}`);
      invalidDeps.push(depId);
      continue;
    }

    // Check finish-to-start: predecessor must end before successor starts
    if (predecessor.endMonth >= ws.startMonth) {
      console.warn(
        `[EPM] Invalid dependency: ${ws.id} starts M${ws.startMonth} but ${depId} ends M${predecessor.endMonth}`
      );
      // Auto-fix: Remove invalid dependency
      invalidDeps.push(depId);
    }
  }

  // Remove invalid dependencies
  if (invalidDeps.length > 0) {
    ws.dependencies = ws.dependencies.filter(d => !invalidDeps.includes(d));
    console.log(`[EPM] Removed ${invalidDeps.length} invalid dependencies from ${ws.id}`);
  }
}
```

**Acceptance Criteria:**
- [ ] No workstream depends on one that ends after it starts
- [ ] Invalid dependencies logged and removed

**Evidence Required:**
1. Console log showing dependency validation ran
2. Export workstreams, verify dependencies are valid

---

### Task 0.5: Add Industry Keyword Check

**File:** `server/intelligence/epm-synthesizer.ts`
**Location:** After workstream generation

**Add Check:**
```typescript
// Industry contamination keywords
const FORBIDDEN_KEYWORDS: Record<string, string[]> = {
  'food_service': ['fishing gear', 'marine equipment', 'sneaker', 'footwear', 'apparel sizing'],
  'retail_fashion': ['food safety', 'health inspection', 'kitchen', 'menu', 'chef', 'FDA', 'fishing'],
  'retail_sporting': ['food safety', 'kitchen', 'menu', 'runway', 'fashion collection'],
};

const detectedIndustry = this.detectIndustry(businessContext);
const forbidden = FORBIDDEN_KEYWORDS[detectedIndustry] || [];

for (const ws of workstreams) {
  const text = `${ws.name} ${ws.description}`.toLowerCase();

  for (const keyword of forbidden) {
    if (text.includes(keyword.toLowerCase())) {
      console.error(`[EPM] ⚠️ Template contamination: "${ws.name}" contains "${keyword}" (forbidden for ${detectedIndustry})`);
      // Flag but don't remove - let quality gate catch it
    }
  }
}
```

**Acceptance Criteria:**
- [ ] Sneaker store journey logs warning if food keywords found
- [ ] Café journey passes without warnings

**Evidence Required:**
1. Run sneaker store journey, show console logs
2. Run café journey, show no contamination warnings

---

### Phase 0 Completion Checklist

- [ ] Task 0.1: Risk mitigations are specific
- [ ] Task 0.2: KPI targets are measurable
- [ ] Task 0.3: FTE values are 0.0-1.0
- [ ] Task 0.4: Dependencies validated
- [ ] Task 0.5: Industry contamination check added
- [ ] Run regression suite: `npm test`

**STOP. Provide all evidence before proceeding to Phase 1.**

---

## PHASE 1: VALIDATION LAYER

> **Objective:** Build reusable validators that catch quality issues

---

### Task 1.1: Create Dependency Validator Module

**File:** `server/intelligence/validators/dependency-validator.ts`

```typescript
/**
 * Dependency Validator
 * Detects and fixes illogical dependency chains
 */

export interface DependencyValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  invalidDependencies: Array<{ workstreamId: string; dependsOn: string; reason: string }>;
}

export interface WorkstreamForValidation {
  id: string;
  name: string;
  startMonth: number;
  endMonth: number;
  dependencies: string[];
}

/**
 * Validate dependency chains
 */
export function validateDependencyChains(
  workstreams: WorkstreamForValidation[]
): DependencyValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const invalidDependencies: DependencyValidationResult['invalidDependencies'] = [];

  const wsMap = new Map(workstreams.map(ws => [ws.id, ws]));

  // Check 1: Detect circular dependencies using DFS
  const visited = new Set<string>();
  const recursionStack = new Set<string>();

  function detectCycle(wsId: string, path: string[]): string[] | null {
    visited.add(wsId);
    recursionStack.add(wsId);

    const ws = wsMap.get(wsId);
    if (!ws) return null;

    for (const depId of ws.dependencies || []) {
      if (!visited.has(depId)) {
        const cycle = detectCycle(depId, [...path, wsId]);
        if (cycle) return cycle;
      } else if (recursionStack.has(depId)) {
        return [...path, wsId, depId];
      }
    }

    recursionStack.delete(wsId);
    return null;
  }

  for (const ws of workstreams) {
    if (!visited.has(ws.id)) {
      const cycle = detectCycle(ws.id, []);
      if (cycle) {
        errors.push(`Circular dependency detected: ${cycle.join(' → ')}`);
      }
    }
  }

  // Check 2: Validate finish-to-start timing
  for (const ws of workstreams) {
    for (const depId of ws.dependencies || []) {
      const predecessor = wsMap.get(depId);

      if (!predecessor) {
        errors.push(`${ws.id} depends on ${depId} which does not exist`);
        invalidDependencies.push({
          workstreamId: ws.id,
          dependsOn: depId,
          reason: 'Predecessor does not exist',
        });
        continue;
      }

      if (predecessor.endMonth > ws.startMonth) {
        errors.push(
          `${ws.id} (starts M${ws.startMonth}) cannot depend on ${depId} (ends M${predecessor.endMonth})`
        );
        invalidDependencies.push({
          workstreamId: ws.id,
          dependsOn: depId,
          reason: `Predecessor ends M${predecessor.endMonth}, successor starts M${ws.startMonth}`,
        });
      } else if (predecessor.endMonth === ws.startMonth) {
        warnings.push(
          `${ws.id} starts same month ${depId} ends - tight coupling, consider lag time`
        );
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    invalidDependencies,
  };
}

/**
 * Auto-fix invalid dependencies by removing them
 */
export function removeInvalidDependencies(
  workstreams: WorkstreamForValidation[],
  invalidDeps: DependencyValidationResult['invalidDependencies']
): WorkstreamForValidation[] {
  const invalidMap = new Map<string, Set<string>>();

  for (const inv of invalidDeps) {
    if (!invalidMap.has(inv.workstreamId)) {
      invalidMap.set(inv.workstreamId, new Set());
    }
    invalidMap.get(inv.workstreamId)!.add(inv.dependsOn);
  }

  return workstreams.map(ws => ({
    ...ws,
    dependencies: ws.dependencies.filter(depId => {
      const toRemove = invalidMap.get(ws.id);
      return !toRemove || !toRemove.has(depId);
    }),
  }));
}
```

**Acceptance Criteria:**
- [ ] Detects circular dependencies
- [ ] Detects finish-to-start violations
- [ ] Returns list of invalid dependencies
- [ ] Auto-fix removes invalid dependencies

**Evidence Required:**
1. Create test file with sample data
2. Show validation catches circular dependency
3. Show validation catches timing violation

---

### Task 1.2: Create Industry Validator Module

**File:** `server/intelligence/validators/industry-validator.ts`

```typescript
/**
 * Industry Validator
 * Detects template contamination (sneaker store ≠ food workstreams)
 */

export interface IndustryValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  contaminationScore: number;  // 0-100, higher = more contaminated
  contaminatedWorkstreams: Array<{
    workstreamId: string;
    workstreamName: string;
    forbiddenKeyword: string;
    wrongIndustry: string;
  }>;
}

const INDUSTRY_KEYWORDS: Record<string, string[]> = {
  food_service: [
    'food safety', 'health inspection', 'kitchen', 'menu', 'chef', 'FDA',
    'recipe', 'cooking', 'food prep', 'dining', 'restaurant', 'café', 'barista'
  ],
  retail_fashion: [
    'collection', 'runway', 'fabric', 'sizing', 'seasonal fashion', 'apparel',
    'clothing', 'accessories', 'boutique', 'fashion trend'
  ],
  retail_sporting: [
    'fishing gear', 'marine equipment', 'sporting goods', 'outdoor equipment',
    'tackle', 'rods', 'reels', 'bait', 'athletic equipment'
  ],
  technology: [
    'sprint', 'deployment', 'architecture', 'API', 'database', 'software',
    'development', 'coding', 'infrastructure'
  ],
  healthcare: [
    'HIPAA', 'patient', 'clinical', 'medical', 'diagnosis', 'treatment',
    'healthcare provider', 'medical records'
  ],
};

/**
 * Validate workstreams are relevant to declared industry
 */
export function validateIndustryRelevance(
  workstreams: Array<{ id: string; name: string; description: string }>,
  declaredIndustry: string
): IndustryValidationResult {
  const warnings: string[] = [];
  const errors: string[] = [];
  const contaminatedWorkstreams: IndustryValidationResult['contaminatedWorkstreams'] = [];

  const expectedKeywords = INDUSTRY_KEYWORDS[declaredIndustry] || [];

  for (const ws of workstreams) {
    const text = `${ws.name} ${ws.description}`.toLowerCase();

    // Check for keywords from OTHER industries
    for (const [otherIndustry, keywords] of Object.entries(INDUSTRY_KEYWORDS)) {
      if (otherIndustry === declaredIndustry) continue;

      for (const keyword of keywords) {
        const keywordLower = keyword.toLowerCase();

        // Skip if this keyword is also valid for our industry
        if (expectedKeywords.some(k => k.toLowerCase() === keywordLower)) continue;

        if (text.includes(keywordLower)) {
          warnings.push(
            `${ws.id} "${ws.name}" contains "${keyword}" (typical for ${otherIndustry}, not ${declaredIndustry})`
          );
          contaminatedWorkstreams.push({
            workstreamId: ws.id,
            workstreamName: ws.name,
            forbiddenKeyword: keyword,
            wrongIndustry: otherIndustry,
          });
        }
      }
    }
  }

  const contaminationScore = workstreams.length > 0
    ? Math.min(100, (contaminatedWorkstreams.length / workstreams.length) * 100)
    : 0;

  if (contaminationScore >= 50) {
    errors.push(`High template contamination: ${contaminationScore.toFixed(0)}% of workstreams have wrong-industry keywords`);
  }

  return {
    valid: contaminationScore < 30,  // Allow minor overlap
    errors,
    warnings,
    contaminationScore,
    contaminatedWorkstreams,
  };
}

/**
 * Detect industry from business context
 */
export function detectIndustry(businessContext: string): string {
  const context = businessContext.toLowerCase();

  if (context.includes('café') || context.includes('cafe') || context.includes('coffee') ||
      context.includes('restaurant') || context.includes('food') || context.includes('kitchen')) {
    return 'food_service';
  }
  if (context.includes('sneaker') || context.includes('shoe') || context.includes('footwear') ||
      context.includes('fashion') || context.includes('apparel') || context.includes('clothing')) {
    return 'retail_fashion';
  }
  if (context.includes('fishing') || context.includes('marine') || context.includes('sporting') ||
      context.includes('outdoor') || context.includes('tackle')) {
    return 'retail_sporting';
  }
  if (context.includes('software') || context.includes('app') || context.includes('platform') ||
      context.includes('saas') || context.includes('technology')) {
    return 'technology';
  }
  if (context.includes('healthcare') || context.includes('medical') || context.includes('clinic') ||
      context.includes('hospital') || context.includes('patient')) {
    return 'healthcare';
  }

  return 'general';
}
```

**Acceptance Criteria:**
- [ ] Detects food keywords in non-food business
- [ ] Calculates contamination score
- [ ] Returns list of contaminated workstreams
- [ ] Fails validation if score > 30%

**Evidence Required:**
1. Test with sneaker store + "Food Safety" workstream → detected
2. Test with café + "Menu Development" → passes

---

### Task 1.3: Create Completeness Validator

**File:** `server/intelligence/validators/completeness-validator.ts`

```typescript
/**
 * Completeness Validator
 * Ensures all required fields are populated
 */

export interface CompletenessResult {
  valid: boolean;
  score: number;  // 0-100
  criticalFailures: string[];
  warnings: string[];
}

export function validateCompleteness(program: {
  workstreams: Array<{
    id: string;
    name: string;
    deliverables?: string[];
    resources?: Array<{ role: string; fteAllocation: number }>;
  }>;
  riskRegister?: {
    risks: Array<{
      id: string;
      description: string;
      mitigation: string;
    }>;
  };
  kpis?: {
    kpis: Array<{
      name: string;
      target: string;
    }>;
  };
}): CompletenessResult {
  const criticalFailures: string[] = [];
  const warnings: string[] = [];
  let totalChecks = 0;
  let passedChecks = 0;

  // Check 1: Workstreams have deliverables
  for (const ws of program.workstreams) {
    totalChecks++;
    if (!ws.deliverables || ws.deliverables.length === 0) {
      criticalFailures.push(`${ws.id} "${ws.name}": No deliverables defined`);
    } else {
      passedChecks++;
    }
  }

  // Check 2: Workstreams have resources
  for (const ws of program.workstreams) {
    totalChecks++;
    if (!ws.resources || ws.resources.length === 0) {
      warnings.push(`${ws.id} "${ws.name}": No resources assigned`);
    } else {
      passedChecks++;
    }
  }

  // Check 3: Minimum 5 risks
  totalChecks++;
  const riskCount = program.riskRegister?.risks?.length || 0;
  if (riskCount < 5) {
    warnings.push(`Only ${riskCount} risks (minimum 5 recommended)`);
  } else {
    passedChecks++;
  }

  // Check 4: No generic risk mitigations
  for (const risk of program.riskRegister?.risks || []) {
    totalChecks++;
    if (risk.mitigation?.toLowerCase().includes('monitor and implement controls')) {
      criticalFailures.push(`${risk.id}: Generic mitigation detected - must be specific`);
    } else {
      passedChecks++;
    }
  }

  // Check 5: No unmeasurable KPI targets
  for (const kpi of program.kpis?.kpis || []) {
    totalChecks++;
    if (kpi.target === 'Improvement' || !kpi.target || kpi.target.length < 5) {
      criticalFailures.push(`KPI "${kpi.name}": Target "${kpi.target}" is not measurable`);
    } else {
      passedChecks++;
    }
  }

  const score = totalChecks > 0 ? Math.round((passedChecks / totalChecks) * 100) : 0;

  return {
    valid: criticalFailures.length === 0,
    score,
    criticalFailures,
    warnings,
  };
}
```

**Acceptance Criteria:**
- [ ] Detects missing deliverables
- [ ] Detects generic risk mitigations
- [ ] Detects unmeasurable KPI targets
- [ ] Calculates completeness score

**Evidence Required:**
1. Test with program missing deliverables → detected
2. Test with generic mitigation → detected
3. Test with "Improvement" target → detected

---

### Task 1.4: Create FTE Normalizer

**File:** `server/intelligence/normalizers/fte-normalizer.ts`

```typescript
/**
 * FTE Normalizer
 * Fixes "100" → "1.0" FTE bug
 */

export interface FTENormalizationResult {
  normalized: Array<{ role: string; fteAllocation: number }>;
  fixes: string[];
}

/**
 * Normalize a single FTE value
 */
export function normalizeFTE(value: number): number {
  // If value > 10, assume it's percentage and convert
  if (value > 10) {
    return value / 100;
  }
  // If value > 1.0 but <= 10, might be headcount - cap at 1.0
  if (value > 1.0) {
    return 1.0;
  }
  // Ensure non-negative
  if (value < 0) {
    return 0;
  }
  return value;
}

/**
 * Normalize all resources and return list of fixes made
 */
export function normalizeResources(
  resources: Array<{ role: string; fteAllocation: number }>
): FTENormalizationResult {
  const fixes: string[] = [];

  const normalized = resources.map(r => {
    const original = r.fteAllocation;
    const fixed = normalizeFTE(original);

    if (original !== fixed) {
      fixes.push(`${r.role}: ${original} → ${fixed}`);
    }

    return { ...r, fteAllocation: fixed };
  });

  return { normalized, fixes };
}
```

**Acceptance Criteria:**
- [ ] 100 → 1.0
- [ ] 80 → 0.8
- [ ] 1.5 → 1.0 (capped)
- [ ] 0.75 → 0.75 (unchanged)

**Evidence Required:**
1. Unit test showing all conversions work

---

### Task 1.5: Integrate Validators into EPM Synthesizer

**File:** `server/intelligence/epm-synthesizer.ts`

**Add imports at top:**
```typescript
import { validateDependencyChains, removeInvalidDependencies } from './validators/dependency-validator';
import { validateIndustryRelevance, detectIndustry } from './validators/industry-validator';
import { validateCompleteness } from './validators/completeness-validator';
import { normalizeResources } from './normalizers/fte-normalizer';
```

**Add after workstream generation (around line 446):**
```typescript
// === VALIDATION PASS ===
console.log('[EPM] Running validation pass...');

// Step 1: Detect industry
const detectedIndustry = detectIndustry(strategicUnderstanding.businessContext);
console.log(`[EPM] Detected industry: ${detectedIndustry}`);

// Step 2: Validate dependencies
const depResult = validateDependencyChains(workstreams);
if (!depResult.valid) {
  console.warn('[EPM] ⚠️ Dependency issues detected:', depResult.errors);
  workstreams = removeInvalidDependencies(workstreams, depResult.invalidDependencies);
  console.log('[EPM] Auto-fixed dependencies');
}

// Step 3: Validate industry relevance
const industryResult = validateIndustryRelevance(workstreams, detectedIndustry);
if (!industryResult.valid) {
  console.error('[EPM] ⚠️ Template contamination detected:', industryResult.warnings);
  // Log but don't block - let quality gate decide
}

// Step 4: Normalize FTEs
for (const ws of workstreams) {
  if (ws.resources && ws.resources.length > 0) {
    const { normalized, fixes } = normalizeResources(ws.resources);
    if (fixes.length > 0) {
      console.log(`[EPM] FTE fixes for ${ws.id}:`, fixes);
    }
    ws.resources = normalized;
  }
}

console.log('[EPM] Validation pass complete');
```

**Acceptance Criteria:**
- [ ] All validators called in sequence
- [ ] Auto-fix applied where possible
- [ ] Warnings/errors logged
- [ ] Program still generates (doesn't hard-fail)

**Evidence Required:**
1. Run journey, show console logs with validation output
2. Export EPM, verify FTEs normalized
3. Export EPM, verify no invalid dependencies

---

### Phase 1 Completion Checklist

- [ ] Task 1.1: Dependency validator created and tested
- [ ] Task 1.2: Industry validator created and tested
- [ ] Task 1.3: Completeness validator created and tested
- [ ] Task 1.4: FTE normalizer created and tested
- [ ] Task 1.5: All validators integrated into EPM flow
- [ ] Regression tests pass

**Evidence Required for Phase 1 Sign-off:**
1. All validator files exist
2. Console logs showing validators run
3. Sample EPM export showing clean output

**STOP. Provide all evidence before proceeding to Phase 2.**

---

## PHASE 2: PROMPT ENHANCEMENT

> **Objective:** Fix the root cause - bad AI prompts producing generic content

---

### Task 2.1: Enhanced Workstream Prompt

**File:** `server/intelligence/prompts/workstream-prompt.ts`

```typescript
/**
 * Enhanced Workstream Prompt
 * Prevents template contamination by enforcing industry specificity
 */

export function buildWorkstreamPrompt(context: {
  businessName: string;
  industry: string;
  location: string;
  strategicObjective: string;
  swotHighlights: string;
}): string {
  return `
## Context
Business: ${context.businessName}
Industry: ${context.industry}
Location: ${context.location}
Strategic Objective: ${context.strategicObjective}
SWOT Summary: ${context.swotHighlights}

## Requirements
Generate workstreams that are SPECIFIC to this ${context.industry} business:

1. Every workstream name must relate directly to ${context.industry} operations
2. Do NOT include generic templates from other industries
3. Do NOT include food safety for non-food businesses
4. Do NOT include healthcare compliance for non-healthcare businesses
5. Each workstream must directly support: "${context.strategicObjective}"

## Workstream Structure Required
For each workstream, provide:
- id: WS001, WS002, etc.
- name: Specific to this business type
- description: How this supports the strategic objective
- deliverables: Array of concrete outputs (minimum 2)
- dependencies: Which workstreams must complete first (predecessor ends BEFORE this starts)
- startMonth/endMonth: Realistic timing
- resources: Roles with FTE as decimal 0.0-1.0 (NOT percentages like 100 or 80)
- owner: Role responsible

## Anti-Patterns to AVOID
- "Operational Efficiency Enhancement" (too generic)
- "Process Improvement Initiative" (meaningless)
- "Stakeholder Engagement Program" (vague)
- FTE values like 100, 80, 50 (these are percentages, use 1.0, 0.8, 0.5)
- Dependencies that start before their predecessor ends

## Good Examples for ${context.industry}
${getIndustryExamples(context.industry)}

Generate 5-8 workstreams following these requirements exactly.
`;
}

function getIndustryExamples(industry: string): string {
  const examples: Record<string, string> = {
    food_service: `
- "Menu Development & Recipe Standardization" - specific to food
- "Kitchen Equipment Procurement & Installation" - specific to food
- "Health Permit & Food Safety Certification" - specific to food
- "Barista Training Program" - specific to café`,
    retail_fashion: `
- "Store Layout & Visual Merchandising Design" - specific to fashion retail
- "Inventory Management & POS Integration" - specific to retail
- "Brand Identity & Marketing Launch" - specific to fashion
- "Staff Training on Product Knowledge" - specific to retail`,
    retail_sporting: `
- "Equipment Display & Store Layout" - specific to sporting goods
- "Supplier Partnerships for Gear" - specific to sporting
- "Expert Staff Hiring & Training" - specific to specialized retail
- "Inventory System for Seasonal Products" - specific to sporting`,
    technology: `
- "Technical Architecture Design" - specific to tech
- "Development Environment Setup" - specific to tech
- "API Development & Integration" - specific to tech
- "Security & Compliance Framework" - specific to tech`,
  };
  return examples[industry] || '- Use industry-specific terminology\n- Focus on domain expertise required';
}
```

**Acceptance Criteria:**
- [ ] Prompt explicitly forbids wrong-industry content
- [ ] Industry-specific examples provided
- [ ] FTE format specified as decimal

**Evidence Required:**
1. Show prompt output for café
2. Show prompt output for sneaker store
3. Run both journeys, verify workstreams are industry-appropriate

---

### Task 2.2: Risk Mitigation Prompt

**File:** `server/intelligence/prompts/risk-mitigation-prompt.ts`

```typescript
/**
 * Risk Mitigation Prompt
 * Generates SPECIFIC mitigations, not generic templates
 */

export function buildRiskMitigationPrompt(risk: {
  description: string;
  category: string;
  probability: string;
  impact: string;
  businessContext: string;
  industry: string;
}): string {
  return `
## Risk to Mitigate
Description: ${risk.description}
Category: ${risk.category}
Probability: ${risk.probability}
Impact: ${risk.impact}

## Business Context
Industry: ${risk.industry}
Context: ${risk.businessContext}

## Requirements
Generate a SPECIFIC mitigation plan. Do NOT use generic phrases like:
- "Monitor and implement controls"
- "Develop contingency plans"
- "Establish governance"
- "Regular monitoring"

Instead provide CONCRETE ACTIONS:
1. strategy: One of 'avoid', 'transfer', 'mitigate', 'accept'
2. actions: 2-4 specific, actionable steps with timelines
3. owner: Role responsible (e.g., "Operations Manager")
4. cost: Estimated mitigation cost in dollars
5. triggerCondition: When to activate contingency (specific threshold)

## Example Good Mitigation
Risk: "Key barista leaves during launch"
- strategy: mitigate
- actions: [
    "Cross-train 2 backup staff on signature drinks by Week 3",
    "Document all recipes with video tutorials by Week 2",
    "Establish relationship with barista staffing agency by Week 1"
  ]
- owner: "Café Manager"
- cost: 2500
- triggerCondition: "Staff turnover exceeds 20% or key role vacant >5 days"

Generate mitigation following this format exactly.
`;
}
```

**Acceptance Criteria:**
- [ ] Prompt explicitly forbids generic phrases
- [ ] Example shows concrete actions
- [ ] Actions have timelines

**Evidence Required:**
1. Generate risks for café, verify mitigations are specific

---

### Task 2.3: KPI Prompt

**File:** `server/intelligence/prompts/kpi-prompt.ts`

```typescript
/**
 * KPI Prompt
 * Generates MEASURABLE targets, never "Improvement"
 */

export function buildKPIPrompt(benefit: {
  description: string;
  category: string;
  businessContext: string;
  industry: string;
}): string {
  return `
## Benefit to Measure
Description: ${benefit.description}
Category: ${benefit.category}

## Business Context
Industry: ${benefit.industry}
Context: ${benefit.businessContext}

## Requirements
Create a MEASURABLE KPI. Do NOT use:
- "Improvement" as a target
- Vague terms like "increase", "enhance", "optimize" without numbers
- Unmeasurable outcomes

Provide:
1. name: Clear KPI name
2. metric: What exactly is measured
3. baseline: Current state (number or "Establish in Month 1")
4. target: Specific numeric goal
5. unit: e.g., "%", "points", "days", "$", "count"
6. measurementFrequency: weekly/monthly/quarterly
7. dataSource: Where measurement comes from

## Example Good KPI
Benefit: "Improved customer satisfaction"
- name: "Customer Satisfaction Score (CSAT)"
- metric: "Post-visit survey average rating"
- baseline: "Establish in Month 1"
- target: 4.5
- unit: "points (1-5 scale)"
- measurementFrequency: "monthly"
- dataSource: "POS receipt survey system"

Generate KPI following this format exactly.
`;
}
```

**Acceptance Criteria:**
- [ ] Prompt explicitly forbids "Improvement"
- [ ] Example shows numeric target

**Evidence Required:**
1. Generate KPIs, verify all have numeric targets

---

### Phase 2 Completion Checklist

- [ ] Task 2.1: Workstream prompt enhanced
- [ ] Task 2.2: Risk mitigation prompt enhanced
- [ ] Task 2.3: KPI prompt enhanced
- [ ] Journey smoke tests show:
  - [ ] No template contamination
  - [ ] No generic mitigations
  - [ ] No "Improvement" targets

**STOP. Provide all evidence before proceeding to Phase 3.**

---

## PHASE 3: INITIATIVE NORMALIZER

> **Objective:** Convert strategic decisions into structured seeds for WBS

---

### Task 3.1: Create Initiative Normalizer Module

**File:** `server/intelligence/normalizers/initiative-normalizer.ts`

```typescript
/**
 * Initiative Normalizer
 * Converts strategic decisions into structured initiatives
 */

export interface RawDecision {
  id?: string;
  content: string;
  category?: string;
  priority?: string;
}

export interface NormalizedInitiative {
  verb: string;
  object: string;
  outcome: string;
  successMetric: string | null;
  phaseHint: 'Phase 1' | 'Phase 2' | 'Phase 3' | 'Phase 4';
  sourceDecisionId?: string;
}

const ACTION_VERBS = [
  'Launch', 'Establish', 'Develop', 'Implement', 'Create',
  'Build', 'Deploy', 'Execute', 'Design', 'Configure',
  'Integrate', 'Train', 'Recruit', 'Procure', 'Secure',
  'Obtain', 'Negotiate', 'Finalize', 'Complete', 'Deliver'
];

const PHASE_KEYWORDS: Record<string, string[]> = {
  'Phase 1': ['foundation', 'initial', 'setup', 'planning', 'design', 'secure', 'obtain', 'license', 'permit', 'location'],
  'Phase 2': ['develop', 'build', 'create', 'implement', 'configure', 'recruit', 'hire'],
  'Phase 3': ['integrate', 'test', 'train', 'deploy', 'launch'],
  'Phase 4': ['operate', 'monitor', 'optimize', 'maintain', 'scale', 'expand'],
};

/**
 * Extract verb from decision text
 */
function extractVerb(text: string): string {
  const words = text.split(/\s+/);

  // Check first word
  for (const verb of ACTION_VERBS) {
    if (words[0]?.toLowerCase() === verb.toLowerCase()) {
      return verb;
    }
  }

  // Look in first 5 words
  for (let i = 0; i < Math.min(5, words.length); i++) {
    for (const verb of ACTION_VERBS) {
      if (words[i]?.toLowerCase() === verb.toLowerCase()) {
        return verb;
      }
    }
  }

  // Infer from content
  const lowerText = text.toLowerCase();
  if (lowerText.includes('open') || lowerText.includes('launch')) return 'Launch';
  if (lowerText.includes('hire') || lowerText.includes('recruit')) return 'Recruit';
  if (lowerText.includes('buy') || lowerText.includes('purchase')) return 'Procure';
  if (lowerText.includes('build') || lowerText.includes('construct')) return 'Build';
  if (lowerText.includes('install') || lowerText.includes('setup')) return 'Implement';
  if (lowerText.includes('train')) return 'Train';
  if (lowerText.includes('design')) return 'Design';

  return 'Implement';  // Default
}

/**
 * Extract object from decision text
 */
function extractObject(text: string, verb: string): string {
  let cleaned = text;
  if (text.toLowerCase().startsWith(verb.toLowerCase())) {
    cleaned = text.substring(verb.length).trim();
  }

  cleaned = cleaned
    .replace(/^(a|an|the|new)\s+/i, '')
    .replace(/\s+(for|to|in|at|by|with)\s+.*$/i, '');

  if (cleaned.length > 150) {
    cleaned = cleaned.substring(0, 150).trim();
    const lastSpace = cleaned.lastIndexOf(' ');
    if (lastSpace > 100) {
      cleaned = cleaned.substring(0, lastSpace);
    }
  }

  return cleaned || 'initiative';
}

/**
 * Determine phase hint from content
 */
function determinePhaseHint(text: string): 'Phase 1' | 'Phase 2' | 'Phase 3' | 'Phase 4' {
  const lowerText = text.toLowerCase();

  for (const [phase, keywords] of Object.entries(PHASE_KEYWORDS)) {
    for (const keyword of keywords) {
      if (lowerText.includes(keyword)) {
        return phase as 'Phase 1' | 'Phase 2' | 'Phase 3' | 'Phase 4';
      }
    }
  }

  return 'Phase 2';  // Default
}

/**
 * Normalize a single decision
 */
export function normalizeDecision(decision: RawDecision): NormalizedInitiative {
  const verb = extractVerb(decision.content);
  const object = extractObject(decision.content, verb);
  const phaseHint = determinePhaseHint(decision.content);

  // Generate outcome
  const outcome = `${verb} ${object} successfully completed`;

  // Generate success metric
  let successMetric: string | null = null;
  const lowerContent = decision.content.toLowerCase();
  if (lowerContent.includes('location') || lowerContent.includes('store')) {
    successMetric = 'Location operational and passing all inspections';
  } else if (lowerContent.includes('system') || lowerContent.includes('software')) {
    successMetric = 'System live with <1% error rate';
  } else if (lowerContent.includes('staff') || lowerContent.includes('team')) {
    successMetric = 'All positions filled with training completed';
  } else if (lowerContent.includes('license') || lowerContent.includes('permit')) {
    successMetric = 'All permits obtained and compliance verified';
  }

  return {
    verb,
    object,
    outcome,
    successMetric,
    phaseHint,
    sourceDecisionId: decision.id,
  };
}

/**
 * Normalize all decisions
 */
export function normalizeAllDecisions(decisions: RawDecision[]): NormalizedInitiative[] {
  return decisions.map(d => normalizeDecision(d));
}
```

**Acceptance Criteria:**
- [ ] Extracts verb, object, outcome from free-form text
- [ ] Assigns phase hints based on keywords
- [ ] Generates success metrics

**Evidence Required:**
1. Test with "Launch a specialty café in Dubai Marina"
2. Test with "Hire and train barista staff"
3. Show normalized output for each

---

### Task 3.2: Integration Hook

**File:** `server/intelligence/epm-synthesizer.ts`

**Add import:**
```typescript
import { normalizeAllDecisions } from './normalizers/initiative-normalizer';
```

**Add after decisions are processed:**
```typescript
// Normalize strategic decisions into initiatives
const initiatives = normalizeAllDecisions(strategicDecisions.map(d => ({
  id: d.id,
  content: d.content || d.description || d.title,
  category: d.category,
  priority: d.priority,
})));

console.log(`[EPM] Normalized ${initiatives.length} initiatives`);
initiatives.forEach(init => {
  console.log(`  - ${init.verb} ${init.object} (${init.phaseHint})`);
});

// Pass initiatives to WBS builder for seeding
// (Will be used in Phase 4)
```

**Acceptance Criteria:**
- [ ] Initiatives logged during synthesis
- [ ] Each initiative shows verb + object + phase

**Evidence Required:**
1. Run journey, show console output with initiatives

---

### Phase 3 Completion Checklist

- [ ] Task 3.1: Initiative normalizer created
- [ ] Task 3.2: Integration hook added
- [ ] Initiatives logged during journey

**STOP. Provide all evidence before proceeding to Phase 4.**

---

## PHASE 4: RESOURCE & BUDGET GENERATION

> **Objective:** Generate proper resource allocation with RACI and budget estimates

---

### Task 4.1: Resource Generator

**File:** `server/intelligence/resource-generator.ts`

```typescript
/**
 * Resource Generator
 * Generates FTE allocations and RACI matrix
 */

export interface ResourceAllocation {
  workstreamId: string;
  role: string;
  fte: number;  // 0.0 to 1.0
  startMonth: number;
  endMonth: number;
}

export interface RACIEntry {
  workstreamId: string;
  role: string;
  responsibility: 'R' | 'A' | 'C' | 'I';
}

const ROLE_TEMPLATES: Record<string, Array<{ name: string; category: string; defaultFTE: number }>> = {
  food_service: [
    { name: 'Operations Manager', category: 'management', defaultFTE: 1.0 },
    { name: 'Head Chef', category: 'operational', defaultFTE: 1.0 },
    { name: 'Marketing Coordinator', category: 'support', defaultFTE: 0.5 },
    { name: 'HR/Training Lead', category: 'support', defaultFTE: 0.5 },
  ],
  retail_fashion: [
    { name: 'Store Manager', category: 'management', defaultFTE: 1.0 },
    { name: 'Visual Merchandiser', category: 'operational', defaultFTE: 0.75 },
    { name: 'Inventory Manager', category: 'operational', defaultFTE: 0.75 },
    { name: 'Marketing Coordinator', category: 'support', defaultFTE: 0.5 },
  ],
  default: [
    { name: 'Program Manager', category: 'management', defaultFTE: 1.0 },
    { name: 'Project Lead', category: 'management', defaultFTE: 0.75 },
    { name: 'Business Analyst', category: 'support', defaultFTE: 0.5 },
  ],
};

/**
 * Generate resource allocations
 */
export function generateResourceAllocations(
  workstreams: Array<{ id: string; name: string; startMonth: number; endMonth: number; description: string }>,
  industry: string
): ResourceAllocation[] {
  const roles = ROLE_TEMPLATES[industry] || ROLE_TEMPLATES.default;
  const allocations: ResourceAllocation[] = [];

  for (const ws of workstreams) {
    const wsLower = `${ws.name} ${ws.description}`.toLowerCase();

    for (const role of roles) {
      let fte = 0;

      if (role.category === 'management') {
        fte = role.defaultFTE * 0.5;  // Managers split across workstreams
      } else if (role.category === 'operational') {
        if (wsLower.includes('operation') || wsLower.includes('setup') || wsLower.includes('build')) {
          fte = role.defaultFTE;
        }
      } else if (role.category === 'support') {
        fte = role.defaultFTE * 0.25;  // Support partial involvement
      }

      if (fte > 0) {
        allocations.push({
          workstreamId: ws.id,
          role: role.name,
          fte: Math.min(fte, 1.0),  // Cap at 1.0
          startMonth: ws.startMonth,
          endMonth: ws.endMonth,
        });
      }
    }
  }

  return allocations;
}

/**
 * Generate RACI matrix
 */
export function generateRACIMatrix(
  workstreams: Array<{ id: string; name: string; description: string }>,
  industry: string
): RACIEntry[] {
  const roles = ROLE_TEMPLATES[industry] || ROLE_TEMPLATES.default;
  const raci: RACIEntry[] = [];

  for (const ws of workstreams) {
    for (const role of roles) {
      let responsibility: 'R' | 'A' | 'C' | 'I';

      if (role.category === 'management') {
        responsibility = 'A';  // Accountable
      } else if (role.category === 'operational') {
        responsibility = 'R';  // Responsible
      } else {
        responsibility = 'C';  // Consulted
      }

      raci.push({
        workstreamId: ws.id,
        role: role.name,
        responsibility,
      });
    }
  }

  return raci;
}
```

**Acceptance Criteria:**
- [ ] FTE values always 0.0-1.0
- [ ] RACI uses only R, A, C, I
- [ ] Industry-specific roles

**Evidence Required:**
1. Generate allocations for café, verify FTEs ≤ 1.0
2. Generate RACI, verify values are R/A/C/I

---

### Task 4.2: Budget Generator

**File:** `server/intelligence/budget-generator.ts`

```typescript
/**
 * Budget Generator
 * Generates CapEx/OpEx estimates per workstream
 */

export interface BudgetLine {
  workstreamId: string;
  category: 'CapEx' | 'OpEx';
  amount: number;
  notes: string;
}

const BUDGET_PROFILES: Record<string, { capexBase: number; opexBase: number }> = {
  food_service: { capexBase: 50000, opexBase: 10000 },
  retail_fashion: { capexBase: 40000, opexBase: 8000 },
  retail_sporting: { capexBase: 45000, opexBase: 9000 },
  default: { capexBase: 30000, opexBase: 6000 },
};

/**
 * Generate budget estimates
 */
export function generateBudgetEstimates(
  workstreams: Array<{ id: string; name: string; description: string; startMonth: number; endMonth: number }>,
  industry: string,
  resourceAllocations: Array<{ workstreamId: string; fte: number }>
): BudgetLine[] {
  const profile = BUDGET_PROFILES[industry] || BUDGET_PROFILES.default;
  const budgetLines: BudgetLine[] = [];

  for (const ws of workstreams) {
    const wsLower = `${ws.name} ${ws.description}`.toLowerCase();
    const duration = ws.endMonth - ws.startMonth + 1;

    // Calculate labor cost
    const wsAllocations = resourceAllocations.filter(a => a.workstreamId === ws.id);
    const totalFTE = wsAllocations.reduce((sum, a) => sum + a.fte, 0);
    const laborCost = totalFTE * duration * 160 * 50;  // FTE × months × hours/month × avg rate

    // CapEx: One-time costs
    let capex = 0;
    if (wsLower.includes('buildout') || wsLower.includes('construction') || wsLower.includes('setup')) {
      capex = profile.capexBase * 3;
    } else if (wsLower.includes('equipment') || wsLower.includes('system') || wsLower.includes('pos')) {
      capex = profile.capexBase * 1.5;
    } else if (wsLower.includes('technology') || wsLower.includes('software')) {
      capex = profile.capexBase;
    }

    if (capex > 0) {
      budgetLines.push({
        workstreamId: ws.id,
        category: 'CapEx',
        amount: Math.round(capex),
        notes: `Capital expenditure for ${ws.name}`,
      });
    }

    // OpEx: Labor + operational costs
    const opex = laborCost + (profile.opexBase * duration);
    budgetLines.push({
      workstreamId: ws.id,
      category: 'OpEx',
      amount: Math.round(opex),
      notes: `Operational costs including labor for ${ws.name}`,
    });
  }

  return budgetLines;
}

/**
 * Calculate budget summary
 */
export function calculateBudgetSummary(budgetLines: BudgetLine[]): {
  totalCapex: number;
  totalOpex: number;
  total: number;
} {
  const totalCapex = budgetLines.filter(b => b.category === 'CapEx').reduce((sum, b) => sum + b.amount, 0);
  const totalOpex = budgetLines.filter(b => b.category === 'OpEx').reduce((sum, b) => sum + b.amount, 0);

  return {
    totalCapex,
    totalOpex,
    total: totalCapex + totalOpex,
  };
}
```

**Acceptance Criteria:**
- [ ] Every workstream has budget line
- [ ] CapEx and OpEx separated
- [ ] Summary calculated correctly

**Evidence Required:**
1. Generate budget, show CapEx/OpEx breakdown

---

### Task 4.3: Integration into EPM

**File:** `server/intelligence/epm-synthesizer.ts`

**Add after workstream generation:**
```typescript
import { generateResourceAllocations, generateRACIMatrix } from './resource-generator';
import { generateBudgetEstimates, calculateBudgetSummary } from './budget-generator';

// Generate resources and budget
const resourceAllocations = generateResourceAllocations(workstreams, detectedIndustry);
const raciMatrix = generateRACIMatrix(workstreams, detectedIndustry);
const budgetLines = generateBudgetEstimates(workstreams, detectedIndustry, resourceAllocations);
const budgetSummary = calculateBudgetSummary(budgetLines);

console.log(`[EPM] Generated ${resourceAllocations.length} resource allocations`);
console.log(`[EPM] Generated ${raciMatrix.length} RACI entries`);
console.log(`[EPM] Budget: CapEx $${budgetSummary.totalCapex.toLocaleString()}, OpEx $${budgetSummary.totalOpex.toLocaleString()}`);
```

**Acceptance Criteria:**
- [ ] Resource/budget generation integrated
- [ ] Logs show generated data

**Evidence Required:**
1. Console logs from journey run

---

### Phase 4 Completion Checklist

- [ ] Task 4.1: Resource generator created
- [ ] Task 4.2: Budget generator created
- [ ] Task 4.3: Integration complete
- [ ] All FTEs 0.0-1.0
- [ ] Budget has CapEx/OpEx

**STOP. Provide all evidence before proceeding to Phase 5.**

---

## PHASE 5: ASSUMPTIONS & RISKS ENHANCEMENT

> **Objective:** Extract assumptions/constraints and enhance risk generation

---

### Task 5.1: Assumption Extractor

**File:** `server/intelligence/assumption-extractor.ts`

```typescript
/**
 * Assumption & Constraint Extractor
 */

export interface AssumptionConstraint {
  type: 'assumption' | 'constraint';
  description: string;
  category: 'timeline' | 'budget' | 'resource' | 'market' | 'regulatory';
}

const INDUSTRY_ASSUMPTIONS: Record<string, AssumptionConstraint[]> = {
  food_service: [
    { type: 'assumption', description: 'Health permits obtainable within standard processing time', category: 'regulatory' },
    { type: 'assumption', description: 'Qualified kitchen and service staff available in local market', category: 'resource' },
    { type: 'constraint', description: 'Must comply with local food safety regulations', category: 'regulatory' },
    { type: 'constraint', description: 'Operating hours subject to local zoning', category: 'regulatory' },
  ],
  retail_fashion: [
    { type: 'assumption', description: 'Target demographic has sufficient spending power', category: 'market' },
    { type: 'assumption', description: 'Supplier relationships can be established with key brands', category: 'resource' },
    { type: 'constraint', description: 'Inventory must align with seasonal buying cycles', category: 'timeline' },
  ],
  default: [
    { type: 'assumption', description: 'Funding available as per budget plan', category: 'budget' },
    { type: 'assumption', description: 'Key stakeholders remain available throughout program', category: 'resource' },
    { type: 'constraint', description: 'Program must complete within defined timeline', category: 'timeline' },
    { type: 'constraint', description: 'Budget cannot exceed approved amount without governance approval', category: 'budget' },
  ],
};

/**
 * Generate assumptions and constraints
 */
export function generateAssumptionsAndConstraints(industry: string): AssumptionConstraint[] {
  const industrySpecific = INDUSTRY_ASSUMPTIONS[industry] || [];
  const common = INDUSTRY_ASSUMPTIONS.default;

  // Combine and deduplicate
  const all = [...industrySpecific, ...common];

  // Ensure minimums
  const assumptions = all.filter(a => a.type === 'assumption');
  const constraints = all.filter(a => a.type === 'constraint');

  if (assumptions.length < 3) {
    all.push({ type: 'assumption', description: 'Market conditions remain stable during program', category: 'market' });
  }
  if (constraints.length < 3) {
    all.push({ type: 'constraint', description: 'All activities must comply with local laws', category: 'regulatory' });
  }

  return all;
}
```

**Acceptance Criteria:**
- [ ] At least 3 assumptions
- [ ] At least 3 constraints
- [ ] Industry-specific items included

**Evidence Required:**
1. Generate for café, show assumptions/constraints

---

### Task 5.2: Integration

**File:** `server/intelligence/epm-synthesizer.ts`

**Add:**
```typescript
import { generateAssumptionsAndConstraints } from './assumption-extractor';

const assumptionsConstraints = generateAssumptionsAndConstraints(detectedIndustry);
const assumptions = assumptionsConstraints.filter(a => a.type === 'assumption');
const constraints = assumptionsConstraints.filter(a => a.type === 'constraint');

console.log(`[EPM] Generated ${assumptions.length} assumptions, ${constraints.length} constraints`);
```

**Evidence Required:**
1. Console log showing counts

---

### Phase 5 Completion Checklist

- [ ] Task 5.1: Assumption extractor created
- [ ] Task 5.2: Integration complete
- [ ] At least 3 assumptions
- [ ] At least 3 constraints

**STOP. Provide all evidence before proceeding to Phase 6.**

---

## PHASE 6: QUALITY GATES

> **Objective:** Block bad output before export

---

### Task 6.1: Quality Gate Module

**File:** `server/intelligence/validators/quality-gate.ts`

```typescript
/**
 * Quality Gate
 * Validates EPM program before export
 */

export interface QualityGateResult {
  passed: boolean;
  score: number;  // 0-100
  criticalFailures: string[];
  warnings: string[];
}

export function runQualityGates(program: {
  workstreams: Array<{
    id: string;
    name: string;
    startMonth: number;
    endMonth: number;
    dependencies: string[];
    deliverables?: string[];
    resources?: Array<{ fteAllocation: number }>;
  }>;
  riskRegister?: {
    risks: Array<{ id: string; mitigation: string }>;
  };
  kpis?: {
    kpis: Array<{ name: string; target: string }>;
  };
}): QualityGateResult {
  const criticalFailures: string[] = [];
  const warnings: string[] = [];
  let score = 100;

  // Gate 1: Minimum workstreams
  if (program.workstreams.length < 3) {
    criticalFailures.push(`Only ${program.workstreams.length} workstreams - minimum 3 required`);
    score -= 25;
  }

  // Gate 2: All workstreams have deliverables
  for (const ws of program.workstreams) {
    if (!ws.deliverables || ws.deliverables.length === 0) {
      criticalFailures.push(`${ws.id} "${ws.name}": No deliverables`);
      score -= 5;
    }
  }

  // Gate 3: Valid dependencies
  const wsMap = new Map(program.workstreams.map(w => [w.id, w]));
  for (const ws of program.workstreams) {
    for (const depId of ws.dependencies || []) {
      const predecessor = wsMap.get(depId);
      if (predecessor && predecessor.endMonth >= ws.startMonth) {
        criticalFailures.push(`${ws.id} depends on ${depId} but timings overlap`);
        score -= 10;
      }
    }
  }

  // Gate 4: FTE values valid
  for (const ws of program.workstreams) {
    for (const r of ws.resources || []) {
      if (r.fteAllocation > 1.0) {
        criticalFailures.push(`${ws.id}: FTE ${r.fteAllocation} > 1.0`);
        score -= 5;
      }
    }
  }

  // Gate 5: No generic mitigations
  for (const risk of program.riskRegister?.risks || []) {
    if (risk.mitigation?.toLowerCase().includes('monitor and implement controls')) {
      criticalFailures.push(`${risk.id}: Generic mitigation`);
      score -= 5;
    }
  }

  // Gate 6: No "Improvement" KPIs
  for (const kpi of program.kpis?.kpis || []) {
    if (kpi.target === 'Improvement') {
      criticalFailures.push(`KPI "${kpi.name}": Unmeasurable target`);
      score -= 5;
    }
  }

  // Gate 7: Minimum risks
  const riskCount = program.riskRegister?.risks?.length || 0;
  if (riskCount < 5) {
    warnings.push(`Only ${riskCount} risks (recommend 5+)`);
    score -= 5;
  }

  return {
    passed: criticalFailures.length === 0,
    score: Math.max(0, score),
    criticalFailures,
    warnings,
  };
}

/**
 * Log quality gate results
 */
export function logQualityGateResults(result: QualityGateResult): void {
  console.log('\n' + '='.repeat(60));
  console.log('QUALITY GATE RESULTS');
  console.log('='.repeat(60));
  console.log(`Overall: ${result.passed ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`Score: ${result.score}/100`);

  if (result.criticalFailures.length > 0) {
    console.log('\n❌ CRITICAL FAILURES:');
    result.criticalFailures.forEach(f => console.log(`  - ${f}`));
  }

  if (result.warnings.length > 0) {
    console.log('\n⚠️ WARNINGS:');
    result.warnings.forEach(w => console.log(`  - ${w}`));
  }

  console.log('='.repeat(60) + '\n');
}
```

**Acceptance Criteria:**
- [ ] All gates implemented
- [ ] Critical failures block (passed = false)
- [ ] Score calculated

**Evidence Required:**
1. Test with valid program → passes
2. Test with missing deliverables → fails

---

### Task 6.2: Integration Before Export

**File:** Where export is triggered (likely `server/services/export-service.ts` or API route)

**Add:**
```typescript
import { runQualityGates, logQualityGateResults } from '../intelligence/validators/quality-gate';

// Before export
const qualityResult = runQualityGates(program);
logQualityGateResults(qualityResult);

if (!qualityResult.passed) {
  console.error('[Export] ❌ Quality gates failed - export blocked');
  throw new Error(`Quality gates failed: ${qualityResult.criticalFailures.join('; ')}`);
}

console.log(`[Export] ✅ Quality gates passed with score ${qualityResult.score}/100`);
```

**Evidence Required:**
1. Console output showing quality gate check before export

---

### Phase 6 Completion Checklist

- [ ] Task 6.1: Quality gate module created
- [ ] Task 6.2: Integration before export
- [ ] Quality gates logged in console

**STOP. Provide all evidence before proceeding to Phase 7.**

---

## PHASE 7: EXCEL EXPORT

> **Objective:** Create import-ready Excel workbook with 8 sheets

---

### Task 7.1: Install ExcelJS

```bash
npm install exceljs
npm install @types/exceljs --save-dev
```

**Evidence Required:**
1. package.json showing exceljs

---

### Task 7.2: Excel Export Service

**File:** `server/services/excel-export-service.ts`

```typescript
/**
 * Excel Export Service
 * Generates Program Planning Starter Kit workbook
 */

import ExcelJS from 'exceljs';

interface ExportData {
  programTitle: string;
  programObjective: string;
  totalBudget: number;
  totalMonths: number;
  startDate: Date;
  workstreams: Array<{
    id: string;
    name: string;
    description: string;
    startMonth: number;
    endMonth: number;
    dependencies: string[];
    deliverables: string[];
    owner: string;
  }>;
  resources: Array<{
    workstreamId: string;
    role: string;
    fte: number;
    startMonth: number;
    endMonth: number;
  }>;
  budget: Array<{
    workstreamId: string;
    category: 'CapEx' | 'OpEx';
    amount: number;
    notes: string;
  }>;
  raci: Array<{
    workstreamId: string;
    role: string;
    responsibility: 'R' | 'A' | 'C' | 'I';
  }>;
  risks: Array<{
    id: string;
    description: string;
    category: string;
    probability: number;
    impact: string;
    mitigation: string;
    owner: string;
  }>;
  assumptions: Array<{
    type: 'assumption' | 'constraint';
    description: string;
    category: string;
  }>;
  kpis: Array<{
    name: string;
    target: string;
    frequency: string;
  }>;
}

export async function generateStarterKitExcel(data: ExportData): Promise<Buffer> {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Premisia Program Planning';
  workbook.created = new Date();

  // Sheet 1: Executive Summary
  addExecutiveSummarySheet(workbook, data);

  // Sheet 2: WBS
  addWBSSheet(workbook, data);

  // Sheet 3: Schedule
  addScheduleSheet(workbook, data);

  // Sheet 4: Resources
  addResourcesSheet(workbook, data);

  // Sheet 5: Budget
  addBudgetSheet(workbook, data);

  // Sheet 6: RACI
  addRACISheet(workbook, data);

  // Sheet 7: Risks
  addRisksSheet(workbook, data);

  // Sheet 8: Assumptions
  addAssumptionsSheet(workbook, data);

  const buffer = await workbook.xlsx.writeBuffer();
  return Buffer.from(buffer);
}

function addExecutiveSummarySheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('Executive Summary');

  // Title
  sheet.mergeCells('A1:D1');
  const titleCell = sheet.getCell('A1');
  titleCell.value = data.programTitle;
  titleCell.font = { bold: true, size: 18 };
  titleCell.alignment = { horizontal: 'center' };

  // Details
  sheet.getCell('A3').value = 'Program Objective:';
  sheet.getCell('A3').font = { bold: true };
  sheet.mergeCells('B3:D3');
  sheet.getCell('B3').value = data.programObjective;

  sheet.getCell('A5').value = 'Total Budget:';
  sheet.getCell('A5').font = { bold: true };
  sheet.getCell('B5').value = data.totalBudget;
  sheet.getCell('B5').numFmt = '$#,##0';

  sheet.getCell('A6').value = 'Duration:';
  sheet.getCell('A6').font = { bold: true };
  sheet.getCell('B6').value = `${data.totalMonths} months`;

  sheet.getCell('A7').value = 'Workstreams:';
  sheet.getCell('A7').font = { bold: true };
  sheet.getCell('B7').value = data.workstreams.length;

  // Column widths
  sheet.getColumn('A').width = 25;
  sheet.getColumn('B').width = 40;
}

function addWBSSheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('WBS');

  // Headers
  const headers = ['WBS Code', 'Task Name', 'Description', 'Duration (months)', 'Start', 'End', 'Dependencies', 'Owner', 'Deliverables'];
  const headerRow = sheet.addRow(headers);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } };

  // Data
  data.workstreams.forEach((ws, idx) => {
    sheet.addRow([
      `1.${idx + 1}`,
      ws.name,
      ws.description,
      ws.endMonth - ws.startMonth + 1,
      ws.startMonth,
      ws.endMonth,
      ws.dependencies.join(', '),
      ws.owner || 'TBD',
      ws.deliverables.join('; '),
    ]);
  });

  // Widths
  sheet.getColumn('A').width = 12;
  sheet.getColumn('B').width = 35;
  sheet.getColumn('C').width = 40;
  sheet.getColumn('I').width = 50;

  sheet.views = [{ state: 'frozen', ySplit: 1 }];
}

function addScheduleSheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('Schedule');

  const maxMonth = Math.max(...data.workstreams.map(w => w.endMonth), 12);
  const headers = ['ID', 'Task', 'Start', 'End', 'Duration', 'Deps'];

  for (let m = 0; m <= maxMonth; m++) {
    headers.push(`M${m}`);
  }

  const headerRow = sheet.addRow(headers);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } };

  // Data with Gantt
  data.workstreams.forEach((ws, idx) => {
    const row: (string | number)[] = [
      idx + 1,
      ws.name,
      ws.startMonth,
      ws.endMonth,
      ws.endMonth - ws.startMonth + 1,
      ws.dependencies.join(', '),
    ];

    for (let m = 0; m <= maxMonth; m++) {
      row.push(m >= ws.startMonth && m <= ws.endMonth ? '█' : '');
    }

    const dataRow = sheet.addRow(row);

    // Color Gantt cells
    for (let m = 0; m <= maxMonth; m++) {
      if (m >= ws.startMonth && m <= ws.endMonth) {
        const cell = dataRow.getCell(7 + m);
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF70AD47' } };
      }
    }
  });

  sheet.getColumn('B').width = 35;
  sheet.views = [{ state: 'frozen', xSplit: 2, ySplit: 1 }];
}

function addResourcesSheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('Resources');

  const headers = ['Workstream', 'Role', 'FTE', 'Start', 'End', 'Duration'];
  const headerRow = sheet.addRow(headers);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } };

  for (const resource of data.resources) {
    const ws = data.workstreams.find(w => w.id === resource.workstreamId);
    sheet.addRow([
      ws?.name || resource.workstreamId,
      resource.role,
      resource.fte,
      resource.startMonth,
      resource.endMonth,
      resource.endMonth - resource.startMonth + 1,
    ]);
  }

  // Total FTE
  const totalFTE = data.resources.reduce((sum, r) => sum + r.fte, 0);
  const summaryRow = sheet.addRow(['TOTAL', '', totalFTE, '', '', '']);
  summaryRow.font = { bold: true };

  sheet.getColumn('A').width = 30;
  sheet.getColumn('B').width = 25;
  sheet.views = [{ state: 'frozen', ySplit: 1 }];
}

function addBudgetSheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('Budget');

  const headers = ['Workstream', 'Category', 'Amount', 'Notes'];
  const headerRow = sheet.addRow(headers);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } };

  for (const item of data.budget) {
    const ws = data.workstreams.find(w => w.id === item.workstreamId);
    const row = sheet.addRow([
      ws?.name || item.workstreamId,
      item.category,
      item.amount,
      item.notes,
    ]);
    row.getCell('C').numFmt = '$#,##0';
  }

  // Totals
  sheet.addRow([]);
  const totalCapex = data.budget.filter(b => b.category === 'CapEx').reduce((sum, b) => sum + b.amount, 0);
  const totalOpex = data.budget.filter(b => b.category === 'OpEx').reduce((sum, b) => sum + b.amount, 0);

  const capexRow = sheet.addRow(['Total CapEx', '', totalCapex, '']);
  capexRow.font = { bold: true };
  capexRow.getCell('C').numFmt = '$#,##0';

  const opexRow = sheet.addRow(['Total OpEx', '', totalOpex, '']);
  opexRow.font = { bold: true };
  opexRow.getCell('C').numFmt = '$#,##0';

  const totalRow = sheet.addRow(['GRAND TOTAL', '', totalCapex + totalOpex, '']);
  totalRow.font = { bold: true };
  totalRow.getCell('C').numFmt = '$#,##0';
  totalRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFFF00' } };

  sheet.getColumn('A').width = 30;
  sheet.getColumn('C').width = 15;
  sheet.getColumn('D').width = 40;
  sheet.views = [{ state: 'frozen', ySplit: 1 }];
}

function addRACISheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('RACI');

  const roles = [...new Set(data.raci.map(r => r.role))];
  const headers = ['Workstream', ...roles];
  const headerRow = sheet.addRow(headers);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } };

  for (const ws of data.workstreams) {
    const rowData: string[] = [ws.name];
    for (const role of roles) {
      const entry = data.raci.find(r => r.workstreamId === ws.id && r.role === role);
      rowData.push(entry?.responsibility || '');
    }
    const row = sheet.addRow(rowData);

    // Color code
    for (let i = 1; i < row.cellCount; i++) {
      const cell = row.getCell(i + 1);
      const value = cell.value as string;
      if (value === 'R') cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF92D050' } };
      else if (value === 'A') cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFC000' } };
      else if (value === 'C') cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF00B0F0' } };
      else if (value === 'I') cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFD9D9D9' } };
      cell.alignment = { horizontal: 'center' };
    }
  }

  // Legend
  sheet.addRow([]);
  sheet.addRow(['Legend:']);
  sheet.addRow(['R = Responsible (does the work)']);
  sheet.addRow(['A = Accountable (approves/owns)']);
  sheet.addRow(['C = Consulted (provides input)']);
  sheet.addRow(['I = Informed (kept updated)']);

  sheet.getColumn('A').width = 35;
  sheet.views = [{ state: 'frozen', xSplit: 1, ySplit: 1 }];
}

function addRisksSheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('Risks');

  const headers = ['ID', 'Description', 'Category', 'Probability', 'Impact', 'Mitigation', 'Owner'];
  const headerRow = sheet.addRow(headers);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } };

  for (const risk of data.risks) {
    const row = sheet.addRow([
      risk.id,
      risk.description,
      risk.category,
      `${risk.probability}%`,
      risk.impact,
      risk.mitigation,
      risk.owner,
    ]);

    // Color impact
    const impactCell = row.getCell('E');
    if (risk.impact === 'Critical') {
      impactCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFF0000' } };
      impactCell.font = { color: { argb: 'FFFFFFFF' } };
    } else if (risk.impact === 'High') {
      impactCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFC000' } };
    } else if (risk.impact === 'Medium') {
      impactCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFFF00' } };
    }
  }

  sheet.getColumn('A').width = 10;
  sheet.getColumn('B').width = 40;
  sheet.getColumn('F').width = 50;
  sheet.getColumn('G').width = 20;
  sheet.views = [{ state: 'frozen', ySplit: 1 }];
}

function addAssumptionsSheet(workbook: ExcelJS.Workbook, data: ExportData): void {
  const sheet = workbook.addWorksheet('Assumptions');

  const headers = ['Type', 'Description', 'Category'];
  const headerRow = sheet.addRow(headers);
  headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } };

  // Assumptions first
  for (const item of data.assumptions.filter(a => a.type === 'assumption')) {
    sheet.addRow(['Assumption', item.description, item.category]);
  }

  sheet.addRow([]);

  // Then constraints
  for (const item of data.assumptions.filter(a => a.type === 'constraint')) {
    const row = sheet.addRow(['Constraint', item.description, item.category]);
    row.getCell('A').fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFC000' } };
  }

  sheet.getColumn('A').width = 15;
  sheet.getColumn('B').width = 60;
  sheet.getColumn('C').width = 15;
  sheet.views = [{ state: 'frozen', ySplit: 1 }];
}
```

**Acceptance Criteria:**
- [ ] 8 sheets created
- [ ] Formatting professional
- [ ] Gantt chart renders

**Evidence Required:**
1. Generate Excel, open in Excel
2. Screenshot showing all 8 sheet tabs

---

### Phase 7 Completion Checklist

- [ ] Task 7.1: ExcelJS installed
- [ ] Task 7.2: Excel export service complete
- [ ] All 8 sheets working
- [ ] Download and verify file opens

**STOP. Provide all evidence before proceeding to Phase 8.**

---

## PHASE 8: API & UI INTEGRATION

> **Objective:** Wire up export endpoint and add download buttons

---

### Task 8.1: Export API Endpoint

**Add to export routes:**
```typescript
// GET /api/export/:sessionId/starter-kit
app.get('/api/export/:sessionId/starter-kit', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const { format } = req.query;  // 'excel' or 'pdf'

    // Get program
    const program = await getEPMProgramForSession(sessionId);
    if (!program) {
      return res.status(404).json({ error: 'Program not found' });
    }

    // Run quality gates
    const qualityResult = runQualityGates(program);
    if (!qualityResult.passed) {
      return res.status(400).json({
        error: 'Quality gates failed',
        details: qualityResult.criticalFailures,
      });
    }

    // Generate Excel
    const excelBuffer = await generateStarterKitExcel(prepareExportData(program));

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="StarterKit_${sessionId.slice(0, 8)}.xlsx"`);
    return res.send(excelBuffer);

  } catch (error) {
    console.error('[Export API] Error:', error);
    res.status(500).json({ error: 'Export failed' });
  }
});
```

**Evidence Required:**
1. Test endpoint with curl or browser
2. File downloads correctly

---

### Task 8.2: UI Download Buttons

**Add to EPM completion component:**
```tsx
{starterKitReady && (
  <div className="starter-kit-downloads">
    <h3>Program Planning Starter Kit</h3>
    <p>Download to import into MS Project, Jira, Monday.com, or Smartsheet:</p>

    <a
      href={`/api/export/${sessionId}/starter-kit?format=excel`}
      className="btn btn-primary"
      download
    >
      📊 Download Excel Workbook
    </a>
  </div>
)}
```

**Evidence Required:**
1. Screenshot of download buttons
2. Click downloads file

---

### Phase 8 Completion Checklist

- [ ] Task 8.1: API endpoint works
- [ ] Task 8.2: UI buttons work
- [ ] File downloads and opens correctly

**STOP. Provide all evidence before proceeding to Phase 9.**

---

## PHASE 9: FINAL VERIFICATION

---

### Task 9.1: Regression Suite

```bash
npm test
```

**All tests must pass.**

**Evidence Required:**
1. Full test output

---

### Task 9.2: Journey Smoke Tests

**Run 2 complete journeys:**

1. **Specialty Café**
   - Full journey to EPM
   - Download Excel
   - Verify: Food-relevant workstreams, valid deps, FTEs ≤ 1.0

2. **Sneaker Store** (or other non-food)
   - Full journey to EPM
   - Download Excel
   - Verify: NO food keywords, valid deps, FTEs ≤ 1.0

**Evidence Required:**
1. Two session IDs
2. Two Excel files attached
3. Quality gate output showing pass

---

### Task 9.3: Quality Report

**For each journey, run quality gates and report:**
- Score
- Pass/Fail
- Any warnings

**Target: Both journeys score ≥ 80/100**

---

## COMPLETION CRITERIA

The feature is COMPLETE when:

1. ✅ All 9 phases complete with evidence
2. ✅ Regression suite passes
3. ✅ 2 journeys smoke tested successfully
4. ✅ Excel files open with 8 sheets
5. ✅ Quality gates score ≥ 80
6. ✅ No template contamination
7. ✅ All FTEs 0.0-1.0
8. ✅ All mitigations specific
9. ✅ All KPIs measurable

---

## APPENDIX: Before/After Examples

### Workstream Name
**Before:** "Operational Efficiency Enhancement"
**After:** "Specialty Coffee Operations Setup"

### Dependency
**Before:** WS002 depends on WS001, both start Month 1
**After:** WS002 (Month 2-3) depends on WS001 (Month 1-2) finish-to-start

### FTE
**Before:** 100
**After:** 1.0

### Risk Mitigation
**Before:** "Monitor and implement controls to reduce high impact"
**After:** "Cross-train 2 backup staff on signature drinks by Week 3; document all recipes with video tutorials; establish relationship with barista staffing agency"

### KPI Target
**Before:** "Improvement"
**After:** "4.5 points (1-5 scale), measured monthly via POS survey"

---

*End of Hybrid Specification*

**Remember:** Per-task proof required. One task at a time. No skipping ahead.
