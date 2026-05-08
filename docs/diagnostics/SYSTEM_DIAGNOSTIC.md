CONTEXT FOUNDRY — SYSTEMATIC END-TO-END DIAGNOSTIC
Vault: 176a4fb2-0bb4-4da3-9068-0e26268fca71 | Target: Identify why score = 73/100
STAGE 0: VAULT STATE BASELINE
Run these SQL queries. Record results. Every downstream check depends on these numbers.
sql
Copy
-- 0.1 Vault metadata
SELECT v.vault_id, v.name, v.tenant_id, v.domain_id, v.created_at
FROM platform.vaults v WHERE v.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71';

-- 0.2 Document inventory
SELECT status, COUNT(*) FROM platform.documents 
WHERE vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71' GROUP BY status;

-- 0.3 Extraction job status
SELECT status, COUNT(*) FROM public.extraction_jobs ej
JOIN platform.documents d ON d.id = ej.document_id
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71' GROUP BY status;

-- 0.4 Entity counts by lifecycle
SELECT lifecycle_state, COUNT(*) FROM public.entities
WHERE vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71' GROUP BY lifecycle_state;

-- 0.5 Relationship counts
SELECT COUNT(*) as total_rels FROM public.relationships r
JOIN public.entities e ON e.id = r.source_entity_id
WHERE e.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71';

-- 0.6 Pending candidates (the sink)
SELECT candidate_type, COUNT(*) FROM public.ontology_candidates
WHERE vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71' AND status = 'PENDING'
GROUP BY candidate_type ORDER BY COUNT(*) DESC;

-- 0.7 Failed extraction jobs (with errors)
SELECT d.filename, ej.error_message, ej.updated_at 
FROM public.extraction_jobs ej
JOIN platform.documents d ON d.id = ej.document_id
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
AND status = 'FAILED' ORDER BY ej.updated_at DESC;

-- 0.8 Ontology active types
SELECT COUNT(DISTINCT relation_type) FROM ontology.relations WHERE status = 'ACTIVE';
PASS CRITERIA:
All 100 documents have status = 'complete' or 'extracted'
All extraction jobs have status = 'COMPLETE' (zero FAILED)
Candidate sink has < 50 pending types OR those types are genuinely novel
At least 1,000 relationships in the graph
FAILURE MODE: If FAILED extraction jobs exist → that's the #1 root cause. Fix those first.
STAGE 1: DOCUMENT INGESTION (Upload → Parse → Chunk)
1.1 Content Preservation Check
sql
Copy
-- For each critical document, verify content survived ingestion
SELECT d.filename, LENGTH(d.content) as content_length, d.status, d.parsing_error
FROM platform.documents d
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
AND d.filename IN (
  '02_organizational_announcement.md',
  '06_solid_state_battery_design.md',
  '04_greenhydrogen_initiative.md',
  '10_first_solar_supplier.md',
  '01_boeing_customer_profile.md'
);
PASS: content_length > 0 for all, parsing_error IS NULL
FAIL: content_length = 0 OR parsing_error NOT NULL
1.2 Chunk Integrity Check
sql
Copy
-- Count chunks per critical document
SELECT d.filename, COUNT(c.id) as chunk_count, 
       AVG(LENGTH(c.text)) as avg_chunk_length,
       SUM(CASE WHEN c.embedding IS NULL THEN 1 ELSE 0 END) as null_embeddings
FROM platform.documents d
LEFT JOIN platform.document_chunks c ON c.document_id = d.id
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
GROUP BY d.filename
ORDER BY chunk_count DESC;
PASS: chunk_count >= 1 per doc, avg_chunk_length >= 200 chars, null_embeddings = 0
FAIL: chunk_count = 0 (doc not chunked), null_embeddings > 0 (embeddings failed)
1.3 Markdown Table Preservation Check
sql
Copy
-- Check if markdown table rows appear in chunks for critical doc
SELECT c.chunk_index, c.text
FROM platform.document_chunks c
JOIN platform.documents d ON d.id = c.document_id
WHERE d.filename = '02_organizational_announcement.md'
AND (c.text LIKE '%|%' OR c.text LIKE '%Role%Name%')
ORDER BY c.chunk_index;
PASS: Chunks contain table rows with | delimiters
FAIL: Tables split across chunks, losing structural information
1.4 Truncation Check
sql
Copy
-- Check if any document was truncated at 15K char limit
SELECT d.filename, LENGTH(d.content) as original_length,
       (SELECT MAX(LENGTH(c.text)) * COUNT(*) FROM platform.document_chunks c WHERE c.document_id = d.id) as chunk_coverage
FROM platform.documents d
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
AND LENGTH(d.content) > 15000;
PASS: No docs > 15K OR chunk_coverage approx matches original_length
FAIL: Docs > 15K with poor chunk coverage = content lost to truncation
STAGE 2: EXTRACTION PIPELINE (Entity + Relationship Extraction)
2.1 Extraction Output Check
sql
Copy
-- Entities extracted per critical document
SELECT d.filename, 
       COUNT(DISTINCT e.id) as entity_count,
       COUNT(DISTINCT CASE WHEN e.lifecycle_state = 'STAGING' THEN e.id END) as staging_count,
       COUNT(DISTINCT CASE WHEN e.lifecycle_state = 'TRUSTED' THEN e.id END) as trusted_count
FROM platform.documents d
LEFT JOIN public.entities e ON e.source_document_id = d.id
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
GROUP BY d.filename
ORDER BY entity_count DESC;
PASS: entity_count > 0 for all critical docs, some TRUSTED entities exist
FAIL: entity_count = 0 = extraction produced nothing (the 02_org_announcement bug)
2.2 Relationship Extraction Check
sql
Copy
-- Relationships per critical document
SELECT d.filename, COUNT(DISTINCT r.id) as rel_count,
       STRING_AGG(DISTINCT r.relationship_type, ', ' ORDER BY r.relationship_type) as rel_types
FROM platform.documents d
LEFT JOIN public.entities e ON e.source_document_id = d.id
LEFT JOIN public.relationships r ON r.source_entity_id = e.id OR r.target_entity_id = e.id
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
GROUP BY d.filename
ORDER BY rel_count DESC;
PASS: rel_count > 0, includes HOLDS_POSITION for org charts
FAIL: rel_count = 0 OR missing HOLDS_POSITION
2.3 Per-Chunk Relation Gate Check
sql
Copy
-- The critical bug: relations only extracted when entities found in same chunk
-- Check if any chunk has relations but no entities (shouldn't happen with current logic)
SELECT c.chunk_index, 
       COUNT(DISTINCT e.id) as entities_in_chunk,
       COUNT(DISTINCT r.id) as relations_in_chunk
FROM platform.document_chunks c
LEFT JOIN public.entity_mentions em ON em.chunk_id = c.id
LEFT JOIN public.entities e ON e.id = em.entity_id
LEFT JOIN public.relationships r ON r.evidence_chunk_id = c.id
JOIN platform.documents d ON d.id = c.document_id
WHERE d.filename = '02_organizational_announcement.md'
GROUP BY c.chunk_index
ORDER BY c.chunk_index;
PASS: Every chunk with relations also has entities
FAIL: Chunks with 0 entities but >0 relations (shouldn't exist with current logic, but proves the gate)
2.4 Extraction Prompt Check
Python
Copy
# In Replit, print the ACTUAL prompt sent to the LLM for a critical doc
from src.context_foundry.extraction.multi_extractor import GPT4oMiniExtractor
extractor = GPT4oMiniExtractor()
# Read the document
with open("path/to/02_organizational_announcement.md") as f:
    doc_text = f.read()
# Build the prompt (don't call API, just get the prompt string)
prompt = extractor._build_prompt(doc_text)
print(prompt[:3000])  # Print first 3000 chars
PASS: Prompt contains explicit table extraction instructions
FAIL: Prompt has no table handling (the LLM treats tables as visual noise)
2.5 Guardrail Impact Check
sql
Copy
-- Count relationships that were filtered by guardrails
-- This requires reading extraction output JSON files
SELECT d.filename, 
       (SELECT COUNT(*) FROM public.relationships r 
        JOIN public.entities e ON e.id = r.source_entity_id 
        WHERE e.source_document_id = d.id) as final_rels,
       (SELECT COUNT(*) FROM public.ontology_candidates oc 
        WHERE oc.document_id = d.id AND oc.status = 'PENDING') as quarantined
FROM platform.documents d
WHERE d.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71';
PASS: quarantined / (final_rels + quarantined) < 0.20 (less than 20% quarantined)
FAIL: > 30% quarantined = the candidate sink is the bottleneck
STAGE 3: STAGING & PROMOTION (Ontology Validation → Graph)
3.1 Promotion Pipeline Check
sql
Copy
-- How many entities are stuck at each lifecycle stage?
SELECT 
  lifecycle_state,
  COUNT(*) as count,
  AVG(confidence_score) as avg_confidence,
  MIN(confidence_score) as min_confidence,
  MAX(confidence_score) as max_confidence
FROM public.entities
WHERE vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
GROUP BY lifecycle_state;
PASS: TRUSTED count > 0, avg_confidence TRUSTED >= 0.75
FAIL: Everything in STAGING (promotion blocked) OR everything ARCHIVED
3.2 Corroboration Gate Check
sql
Copy
-- The corroboration gate: Person entities need 2 corroborations
SELECT e.name, e.entity_type, e.lifecycle_state, 
       (e.properties->>'_corroboration_count')::int as corroborations
FROM public.entities e
WHERE e.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
AND e.entity_type = 'PERSON'
ORDER BY corroborations DESC NULLS LAST
LIMIT 20;
PASS: Most PERSON entities have corroborations >= 2 (if TRUSTED)
FAIL: TRUSTED Person entities with corroborations < 2 (gate bypassed) OR STAGING with corroborations = 1 (gate blocking)
3.3 Verification Check
sql
Copy
-- Evidence verification status
SELECT 
  e.lifecycle_state,
  COUNT(DISTINCT e.id) as entity_count,
  COUNT(DISTINCT er.id) as verified_evidence_count
FROM public.entities e
LEFT JOIN public.evidence_records er ON er.entity_id = e.id
WHERE e.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
GROUP BY e.lifecycle_state;
PASS: TRUSTED entities have verified evidence records
FAIL: TRUSTED entities with 0 evidence = verification pipeline didn't run
3.4 Archival Check
sql
Copy
-- Check if ARCHIVED entities have active relationships (facts lost)
SELECT e.name, e.entity_type, e.lifecycle_state, COUNT(r.id) as active_relationships
FROM public.entities e
LEFT JOIN public.relationships r ON r.source_entity_id = e.id OR r.target_entity_id = e.id
WHERE e.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
AND e.lifecycle_state = 'ARCHIVED'
AND r.id IS NOT NULL
GROUP BY e.name, e.entity_type, e.lifecycle_state
ORDER BY active_relationships DESC
LIMIT 10;
PASS: ARCHIVED entities have 0 active relationships (correct)
FAIL: ARCHIVED entities with >0 relationships = facts were archived with entities
STAGE 4: ENTITY RESOLUTION (Deduplication, Disambiguation)
4.1 Fragmentation Check
sql
Copy
-- Check for entity fragmentation (same name, multiple entries)
SELECT LOWER(e.name) as normalized_name, e.entity_type, 
       COUNT(*) as fragment_count,
       STRING_AGG(e.name, ' | ') as names,
       STRING_AGG(DISTINCT e.lifecycle_state, ', ') as states
FROM public.entities e
WHERE e.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
GROUP BY LOWER(e.name), e.entity_type
HAVING COUNT(*) > 1
ORDER BY fragment_count DESC
LIMIT 20;
PASS: fragment_count = 1 for most entities (no fragmentation)
FAIL: fragment_count > 2 for common names = entity resolution failing
4.2 Disambiguation Reasoner Status
Python
Copy
# In Replit:
from src.context_foundry.agents.disambiguation_reasoner import DisambiguationReasoner
# Check if this class is ever instantiated in the codebase
import subprocess
result = subprocess.run(['grep', '-r', 'DisambiguationReasoner', 'src/'], capture_output=True, text=True)
print(result.stdout)
PASS: DisambiguationReasoner is imported AND instantiated in query pipeline
FAIL: Never instantiated (dead code — confirmed from code analysis)
STAGE 5: QUERY PIPELINE (Question → Answer)
5.1 Role Resolver Check
Python
Copy
# In Replit:
from src.context_foundry.agents.role_resolver import RoleResolver
# Check what relationship types the role resolver queries
import inspect
source = inspect.getsource(RoleResolver)
# Find all relationship_type checks
import re
rel_types = re.findall(r"relationship_type\s*==?\s*['\"](\w+)['\"]", source)
print("Role resolver queries these types:", set(rel_types))
PASS: Includes HOLDS_POSITION, REPORTS_TO, and the types your test questions need
FAIL: Only queries types not present in your graph
5.2 Tree Retriever Check
Python
Copy
# In Replit:
from src.context_foundry.retrieval.tree_retriever import TreeRetriever
# Check if semantic search is implemented
import inspect
source = inspect.getsource(TreeRetriever)
if 'TODO' in source or 'NotImplemented' in source or 'return None' in source:
    print("TREE RETRIEVER HAS UNIMPLEMENTED STUBS")
    # Find the specific unimplemented methods
    for line in source.split('\n'):
        if 'TODO' in line or 'return None' in line or 'pass' in line:
            print(f"  {line.strip()}")
PASS: All methods implemented, no TODO stubs
FAIL: Unimplemented methods (confirmed from code analysis — semantic search returns None)
5.3 QueryExecutor Wiring Check
Python
Copy
# In Replit:
# Check if QueryExecutor is actually used
import subprocess
result = subprocess.run(['grep', '-r', 'QueryExecutor', 'src/'], capture_output=True, text=True)
print(result.stdout)
# Also check the RetrievalAgent
result2 = subprocess.run(['grep', '-r', 'build_context_bundle', 'src/'], capture_output=True, text=True)
print(result2.stdout)
PASS: QueryExecutor.execute() is called by RetrievalAgent
FAIL: Legacy path still active, QueryExecutor is bypassed
STAGE 6: THE 28 FAILING QUESTIONS
6.1 Per-Question Fact Check
For each of the 28 failing questions (from analysis_outputs/failure_analysis.json):
sql
Copy
-- Template: Check if the expected fact exists in the graph
-- Example for Q3: "Robert Kim" -> "President of NDS"
SELECT e1.name as person, r.relationship_type, e2.name as role
FROM public.entities e1
JOIN public.relationships r ON r.source_entity_id = e1.id
JOIN public.entities e2 ON e2.id = r.target_entity_id
WHERE e1.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
AND e1.name ILIKE '%Robert Kim%'
AND (r.relationship_type LIKE '%POSITION%' OR r.relationship_type LIKE '%ROLE%' OR r.relationship_type LIKE '%PRESIDENT%');
PASS: Expected fact exists in graph
FAIL: Expected fact missing (either not extracted, not promoted, or quarantined as candidate)
6.2 Evidence Chain Check
For each failing question where the fact IS in the graph:
sql
Copy
-- Check the evidence chain
SELECT e.name, er.source_text, er.verification_status, r.relationship_type
FROM public.entities e
JOIN public.evidence_records er ON er.entity_id = e.id
LEFT JOIN public.relationships r ON r.source_entity_id = e.id
WHERE e.name ILIKE '%Robert Kim%'
AND e.vault_id = '176a4fb2-0bb4-4da3-9068-0e26268fca71';
PASS: Evidence exists and is VERIFIED
FAIL: Evidence missing or UNVERIFIED = query can't ground answer
STAGE 7: SYNTHESIS — ROOT CAUSE DETERMINATION
After running all stages above, classify each failing question into one of these root cause categories:
Table
Category	Diagnostic Pattern	Fix Category
A. Not in corpus	Expected string doesn't appear in any document text	Test data issue
B. Ingestion loss	Document parsed but content_length = 0 or truncated	Fix parser/chunker
C. Extraction failure	Document has content but 0 entities/relations for that doc	Fix extraction prompt
D. Chunk boundary loss	Entities exist in different chunks, relation never extracted	Fix per-chunk relation gate
E. Guardrail filter	Relation extracted but filtered by multi_extractor guardrails	Relax guardrails
F. Candidate sink	Relation type in ontology_candidates (PENDING), not graph	Fix staging loader
G. Promotion blocked	Entity/relation in STAGING, never promoted to TRUSTED	Fix governance gates
H. Query pipeline	Fact exists in TRUSTED but retrieval doesn't find it	Fix query/retrieval
I. Disambiguation	Multiple matching entities, wrong one selected	Wire DisambiguationReasoner
J. Evidence gap	Fact in graph but no verified evidence	Run verification pipeline
The category with the most questions is your root cause. Fix that first.
EXPECTED RESULTS FROM THIS DIAGNOSTIC
Based on code analysis, I predict:
Table
Stage	Expected Finding	Confidence
0.7	Several FAILED extraction jobs exist (the 02_org_announcement bug)	High
1.3	Markdown tables split across chunks	High
2.2	Some docs have 0 or very few relationships	High
2.4	Extraction prompt has no table handling instructions	High
3.1	Most entities in STAGING, few in TRUSTED	Medium-High
3.2	Many Person entities with corroboration < 2	Medium
4.1	Boeing fragmented across multiple entries	High
4.2	DisambiguationReasoner never instantiated	High
5.1	Role resolver only checks ~4-7 relationship types	High
5.2	Tree retriever has unimplemented TODO stubs	High
6.1	Most failing questions = Category C or F (extraction or candidate sink)	High
Run these checks. Report the numbers. We'll know exactly what's wrong instead of guessing