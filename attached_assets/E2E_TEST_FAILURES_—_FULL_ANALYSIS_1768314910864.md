E2E TEST FAILURES — FULL ANALYSIS

\================================================================================  
CRITICAL: TECHVENTURES REPORTS\_TO BROKEN  
\================================================================================

Expected: 48 relationships  
Actual: 42 relationships (lost 6\)

"Who reports to CEO" returns 1 person instead of 3\.  
\`\`\`sql  
\-- Check what REPORTS\_TO exists  
SELECT e1.name as employee, e2.name as manager  
FROM relationships r  
JOIN entities e1 ON r.source\_id \= e1.id  
JOIN entities e2 ON r.target\_id \= e2.id  
WHERE r.relationship\_type \= 'REPORTS\_TO'  
  AND e1.tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'TechVentures');

\-- Check if Dr. Hassan and James O'Brien exist  
SELECT name FROM entities  
WHERE tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'TechVentures')  
  AND (name ILIKE '%hassan%' OR name ILIKE '%o''brien%');  
\`\`\`

\================================================================================  
MEDIUM: LAUNCHPAD ENTITY CONFUSION  
\================================================================================

"Tell me about CloudAI" returns HEALTHBRIDGE data.  
\`\`\`sql  
\-- Check entity names in Launchpad  
SELECT name, entity\_type FROM entities  
WHERE tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'Launchpad Ventures')  
  AND (name ILIKE '%cloudai%' OR name ILIKE '%healthbridge%');  
\`\`\`

Is there a CloudAI entity? Or is semantic search confusing them?

\================================================================================  
MEDIUM: SEMANTIC RETRIEVAL GAPS  
\================================================================================

"Who leads Healthcare investments" returns nothing.  
But Dr. Rachel Green has "Focus: Healthcare & Biotech".

Check if "leads" \+ "Healthcare" can match "Focus: Healthcare".

\================================================================================  
MEDIUM: ACCELERATOR STRUCTURE MISSING  
\================================================================================

Query returns generic response (25% confidence).  
Check if accelerator structure exists in chunks:  
\`\`\`sql  
SELECT chunk\_text   
FROM document\_chunks  
WHERE tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'Launchpad Ventures')  
  AND chunk\_text ILIKE '%accelerator%';  
\`\`\`

\================================================================================  
ACTION REQUIRED  
\================================================================================

1\. Fix TechVentures REPORTS\_TO (CRITICAL \- blocking)  
2\. Investigate CloudAI/HEALTHBRIDGE confusion  
3\. Check semantic matching for "leads Healthcare"  
4\. Verify accelerator content in chunks

Report findings before proceeding.  
\================================================================================  
