CRITICAL: REGRESSION DETECTED

"Who reports to the CEO" returning only 1 person instead of 3\.

\================================================================================  
IMMEDIATE DIAGNOSTICS  
\================================================================================

1\. Check if relationships still exist:  
\`\`\`sql  
\-- Find Sarah Chen's entity ID  
SELECT id, name, entity\_type FROM entities   
WHERE UPPER(name) LIKE '%SARAH CHEN%'  
  AND tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'TechVentures');

\-- Find all REPORTS\_TO relationships where Sarah Chen is target  
SELECT   
    e1.name as reports\_from,  
    r.relationship\_type,  
    e2.name as reports\_to  
FROM relationships r  
JOIN entities e1 ON r.source\_id \= e1.id  
JOIN entities e2 ON r.target\_id \= e2.id  
WHERE UPPER(e2.name) LIKE '%SARAH CHEN%'  
  AND r.relationship\_type \= 'REPORTS\_TO';  
\`\`\`

2\. Check total relationship count for TechVentures:  
\`\`\`sql  
SELECT COUNT(\*) FROM relationships r  
JOIN entities e ON r.source\_id \= e.id  
WHERE e.tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'TechVentures');  
\`\`\`

Compare to expected: 48 relationships

3\. Check if Learning Flow re-extracted anything:  
\`\`\`sql  
SELECT \* FROM extraction\_jobs   
WHERE tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'TechVentures')  
ORDER BY created\_at DESC  
LIMIT 10;  
\`\`\`

4\. Check query\_gaps for this query:  
\`\`\`sql  
SELECT \* FROM query\_gaps   
WHERE query\_text LIKE '%reports%CEO%'  
ORDER BY created\_at DESC;  
\`\`\`  
 \-- 1\. How many REPORTS\_TO relationships exist for TechVentures?  
  SELECT COUNT(\*)  
  FROM relationships r  
  JOIN entities ceo ON r.target\_id \= ceo.id  
  WHERE r.relationship\_type \= 'REPORTS\_TO'  
    AND ceo.name ILIKE '%Sarah Chen%';

  \-- 2\. List ALL REPORTS\_TO relationships in TechVentures  
  SELECT  
      e1.name as reports\_from,  
      r.relationship\_type,  
      e2.name as reports\_to  
  FROM relationships r  
  JOIN entities e1 ON r.source\_id \= e1.id  
  JOIN entities e2 ON r.target\_id \= e2.id  
  WHERE r.relationship\_type \= 'REPORTS\_TO'  
    AND r.tenant\_id \= (SELECT id FROM platform.tenants WHERE name \= 'TechVentures')  
  ORDER BY e2.name;

  \-- 3\. Who is linked to Sarah Chen by ANY relationship?  
  SELECT  
      e1.name as entity,  
      r.relationship\_type,  
      'Sarah Chen' as ceo  
  FROM relationships r  
  JOIN entities e1 ON r.source\_id \= e1.id  
  JOIN entities ceo ON r.target\_id \= ceo.id  
  WHERE ceo.name ILIKE '%Sarah Chen%';

  \-- 4\. Check if there are multiple Sarah Chen entities (duplicate issue?)  
  SELECT id, name, entity\_type, tenant\_id  
  FROM entities  
  WHERE name ILIKE '%Sarah%Chen%';

  \-- 5\. What was working before? Check the previous E2E results  
  \-- (Compare with /Users/saleh/Downloads/e2e\_results\_20260113\_111115.txt)  
\================================================================================  
REPORT BACK  
\================================================================================

1\. How many REPORTS\_TO relationships exist for Sarah Chen?  
2\. Total relationships for TechVentures (should be 48)?  
3\. Did any new extraction jobs run recently?  
4\. Any errors in logs?

This needs to be fixed before proceeding.  
\================================================================================  
