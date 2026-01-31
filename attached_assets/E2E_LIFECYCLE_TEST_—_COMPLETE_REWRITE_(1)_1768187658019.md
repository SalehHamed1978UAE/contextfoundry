E2E LIFECYCLE TEST — COMPLETE REWRITE

\================================================================================  
CRITICAL RULES — READ BEFORE DOING ANYTHING  
\================================================================================

1\. DO NOT MODIFY APPLICATION CODE  
   \- If something doesn't work, STOP  
   \- Do not "fix" the extraction pipeline  
   \- Do not "fix" the query system  
   \- Do not "fix" the database schema  
   \- Do not add workarounds

2\. DO NOT MODIFY DATA TO MAKE TESTS WORK  
   \- Do not manually insert entities  
   \- Do not manually create relationships  
   \- Do not patch the database

3\. IF ANYTHING FAILS — STOP AND REPORT  
   \- Do not continue to the next step  
   \- Do not try a different approach  
   \- Do not retry with different parameters  
   \- Log the exact error and EXIT

4\. REPORT FAILURES CLEARLY  
   \- What step failed  
   \- What the error was  
   \- What the expected behavior was  
   \- Then STOP and wait for human decision

5\. THE TEST IS A DIAGNOSTIC TOOL  
   \- It tells us if the system works  
   \- It does not fix the system  
   \- If the system is broken, humans decide how to fix it

\================================================================================  
FAILURE BEHAVIOR  
\================================================================================

If vault creation fails:  
  → Log: "FAILED: Could not create vault. Error: {error}"  
  → Exit immediately with code 1

If document upload fails:  
  → Log: "FAILED: Could not upload documents. Error: {error}"  
  → Exit immediately with code 1

If extraction times out:  
  → Log: "FAILED: Extraction timeout. chunks={n}, entities={n}, relationships={n}"  
  → Exit immediately with code 1

If query execution fails:  
  → Log: "FAILED: Query execution error. Error: {error}"  
  → Exit immediately with code 1

If ANY import fails:  
  → Log: "FAILED: Import error. Cannot import {module}. Error: {error}"  
  → Exit immediately with code 1

If database connection fails:  
  → Log: "FAILED: Database connection error. Error: {error}"  
  → Exit immediately with code 1

\================================================================================  
WHAT "STOP AND REPORT" MEANS  
\================================================================================

DO NOT:  
  ❌ "Let me try a different approach..."  
  ❌ "Let me fix this by..."  
  ❌ "I'll add a workaround for..."  
  ❌ "Let me modify the code to..."  
  ❌ "Let me adjust the query to..."

DO:  
  ✅ Log the exact error  
  ✅ Log which step failed  
  ✅ Exit with code 1  
  ✅ Wait for human to decide next steps

\================================================================================  
EXAMPLE FAILURE OUTPUT  
\================================================================================

\[03:15:22\] Starting E2E test for 5 vaults  
\[03:15:22\] Output file: /mnt/user-data/outputs/e2e\_results\_20260112\_031522.txt

\[03:15:22\] \============================================================  
\[03:15:22\] VAULT: TechVentures  
\[03:15:22\] \============================================================  
\[03:15:22\] Step 0: Delete existing vault 'TechVentures'  
\[03:15:22\]          No existing vault found  
\[03:15:22\] Step 1: Create vault 'TechVentures'  
\[03:15:22\]          Created vault: abc123-def456  
\[03:15:22\] Step 2: Upload documents from 'test documents/TechVentures'  
\[03:15:23\]          Uploaded: 01\_leadership\_memo.txt  
\[03:15:23\]          Uploaded: 02\_portfolio\_summary.txt  
\[03:15:23\]          Uploaded: 03\_org\_chart.txt  
\[03:15:23\]          Uploaded: 04\_compensation\_memo.txt  
\[03:15:23\]          Total: 4 documents  
\[03:15:23\] Step 3: Trigger extraction for 4 documents

\================================================================================  
FAILED: Import error  
\================================================================================  
Cannot import: from services.ingestion import process\_document  
Error: ModuleNotFoundError: No module named 'services.ingestion'

Action required: Human must verify correct import path.  
Do NOT attempt to fix this automatically.  
\================================================================================

Exit code: 1

\================================================================================  
AFTER A FAILURE  
\================================================================================

When the test fails:

1\. Share the COMPLETE output with the user  
2\. Do NOT attempt to fix the issue  
3\. Wait for the user to tell you what to do

The user will either:  
\- Tell you the correct import path  
\- Tell you to fix something specific  
\- Investigate the issue themselves

You do NOT make this decision. You report and wait.

Delete the current e2e\_lifecycle\_test.py and start fresh.

\================================================================================  
PURPOSE  
\================================================================================

Test Context Foundry exactly as a real user would:  
1\. Delete existing vaults  
2\. Create fresh vaults  
3\. Upload documents  
4\. Run extraction  
5\. Run ALL queries  
6\. Save full answers to a file for human review

This is regression testing. Run it before any deploy to verify the system works.

\================================================================================  
HARD RULES  
\================================================================================

1\. NO HARDCODING  
   \- Don't hardcode document filenames — read from directory  
   \- Don't hardcode expected answers — just record what comes back  
   \- Don't hardcode entity names — query what was extracted  
   \- Don't hardcode tenant IDs — look up by name

2\. USE REAL VAULT NAMES  
   \- "TechVentures" not "E2E\_Test\_TechVentures"  
   \- These are the user's actual vaults

3\. NO CLEANUP AT END  
   \- Leave vaults intact after test  
   \- User wants to review and use them

4\. SAVE FULL ANSWERS  
   \- Every word of every answer  
   \- No truncation  
   \- No auto-pass/fail

5\. IF ANYTHING FAILS — STOP AND REPORT  
   \- Don't try to fix it  
   \- Don't skip it  
   \- Log the error and exit

\================================================================================  
CONFIGURATION  
\================================================================================

Pull from a single config file. No hardcoding in the test script.

File: scripts/e2e\_config.py  
\`\`\`python  
VAULTS \= \[  
    {  
        "name": "TechVentures",  
        "doc\_dir": "test documents/TechVentures",  
        "queries": \[  
            "Who is the CEO?",  
            "What is the CEO's salary?",  
            "Who is the CTO?",  
            "Who is the CTO of TechVentures?",  
            "What is Sarah Chen's compensation?",  
            "Who reports to the CEO?",  
            "What portfolio companies does TechVentures have?",  
            "Tell me about CloudMatrix",  
            "Tell me about HealthSync",  
            "Tell me about SecureNode",  
        \],  
    },  
    {  
        "name": "Morrison & Sterling",  
        "doc\_dir": "test documents/Law Firm",  
        "queries": \[  
            "Who is the Managing Partner?",  
            "What is the Managing Partner's compensation?",  
            "Who is the CFO?",  
            "Who is the COO?",  
            "Who reports to Amanda Foster?",  
            "What practice groups does the firm have?",  
            "Tell me about the litigation practice",  
            "Who are the Tier 1 clients?",  
            "What is Richard Sterling's compensation?",  
        \],  
    },  
    {  
        "name": "Riverside Medical Center",  
        "doc\_dir": "test documents/Hospital",  
        "queries": \[  
            "Who is the CEO?",  
            "What is the CEO's salary?",  
            "Who is the CMO?",  
            "Who is the CIO?",  
            "What is the CIO's compensation?",  
            "Who reports to the CEO?",  
            "What departments does the hospital have?",  
            "Tell me about the cardiac initiative",  
            "Who leads the oncology department?",  
            "Who leads the cardiology department?",  
        \],  
    },  
    {  
        "name": "Titan Manufacturing",  
        "doc\_dir": "test documents/Titan Manufacturing",  
        "queries": \[  
            "Who is the CEO?",  
            "What is the CEO's compensation?",  
            "Who is the COO?",  
            "Who is the CTO?",  
            "Who reports to the CEO?",  
            "Who manages the Detroit plant?",  
            "What is the Detroit plant manager's compensation?",  
            "What plants does the company have?",  
            "Tell me about the automation initiative",  
            "Who leads quality assurance?",  
        \],  
    },  
    {  
        "name": "Launchpad Ventures",  
        "doc\_dir": "test documents/Launchpad Ventures",  
        "queries": \[  
            "Who is the Managing Partner?",  
            "What is the Managing Partner's compensation?",  
            "Who are the General Partners?",  
            "Who reports to Alexandra Kim?",  
            "What portfolio companies are in Cohort 12?",  
            "Tell me about CloudAI",  
            "Tell me about NeuralBox",  
            "What is David Park's compensation?",  
            "Who leads the Healthcare investments?",  
            "What is the accelerator program structure?",  
        \],  
    },  
\]  
\`\`\`

\================================================================================  
TEST FLOW  
\================================================================================

For EACH vault in VAULTS:

STEP 0: DELETE EXISTING VAULT  
\-----------------------------  
\- Look up vault by name in platform.tenants  
\- If exists:  
  \- Delete all relationships for this tenant\_id  
  \- Delete all entities for this tenant\_id  
  \- Delete all document\_chunks for this tenant\_id  
  \- Delete all documents for this tenant\_id  
  \- Delete any other FK-constrained data  
  \- Delete the vault itself  
\- Log what was deleted

STEP 1: CREATE VAULT  
\--------------------  
\- Create vault with the exact name from config  
\- Store tenant\_id  
\- Log: "Created vault: {name} ({tenant\_id})"

STEP 2: UPLOAD DOCUMENTS  
\------------------------  
\- List all files in doc\_dir (don't hardcode filenames)  
\- For each file:  
  \- Read content  
  \- Insert into documents table  
  \- Store document\_id  
\- Log: "Uploaded {n} documents: {filenames}"

STEP 3: TRIGGER EXTRACTION  
\--------------------------  
\- Call extraction for each document  
\- Log: "Triggered extraction for {n} documents"

STEP 4: WAIT FOR EXTRACTION  
\---------------------------  
\- Poll every 10 seconds  
\- Check: document\_chunks \> 0, entities \> 0, relationships \> 0  
\- Max wait: 10 minutes per vault  
\- Log progress every 30 seconds  
\- When complete, log:  
  \- Number of chunks  
  \- Number of entities  
  \- Number of relationships

STEP 5: RUN QUERIES  
\-------------------  
\- For each query in config:  
  \- Execute query via ToolAgent  
  \- Record FULL answer (no truncation)  
  \- Record confidence  
  \- Write to output file immediately  
\- Log: "Executed {n} queries"

STEP 6: DONE (NO CLEANUP)  
\-------------------------  
\- Do NOT delete the vault  
\- User wants to keep it for manual testing  
\- Log: "Vault ready for use: {name}"

\================================================================================  
OUTPUT FILE  
\================================================================================

Location: /mnt/user-data/outputs/e2e\_results\_YYYYMMDD\_HHMMSS.txt

Format:

# **\================================================================================ E2E LIFECYCLE TEST RESULTS**

# **Run Date: 2026-01-12 03:00:00**

# **\================================================================================ VAULT: TechVentures**

Documents Uploaded: 4

* 01\_leadership\_memo.txt  
* 02\_portfolio\_summary.txt  
* 03\_org\_chart.txt  
* 04\_compensation\_memo.txt

Extraction Results:

* Chunks: 12  
* Entities: 166  
* Relationships: 120

---

## **QUERY 1/10: Who is the CEO?**

ANSWER: The CEO of TechVentures is Sarah Chen. She has extensive experience in venture capital, having previously served as Partner at Sequoia Capital. Sarah joined TechVentures in 2019 and has led the firm through significant growth, overseeing investments in over 50 portfolio companies across technology sectors.

Note: Your documents also mention other CEOs:

* Ahmed Malik (CEO of SecureNode)  
* Dr. Patricia Vance (CEO of HealthSync)  
* Robert Kim (CEO of CloudMatrix)

## **CONFIDENCE: 90%**

---

## **QUERY 2/10: What is the CEO's salary?**

ANSWER: Sarah Chen's base salary is $850,000. Her total compensation package includes:

* Base Salary: $850,000  
* Target Bonus: $1,200,000 (141% of base)  
* Equity: 2.5% carried interest in Fund IV  
* Total Target Compensation: $2,050,000

## **CONFIDENCE: 85%**

... (continue for all 10 queries)

# **\================================================================================ VAULT: Morrison & Sterling**

Documents Uploaded: 3

* 01\_firm\_overview.txt  
* 02\_partner\_compensation.txt  
* 03\_client\_roster.txt

Extraction Results:

* Chunks: 8  
* Entities: 97  
* Relationships: 100

---

## **QUERY 1/9: Who is the Managing Partner?**

ANSWER: \[FULL ANSWER HERE\]

## **CONFIDENCE: XX%**

... (continue for all 9 queries)

# **\================================================================================ VAULT: Riverside Medical Center**

... (continue for all 10 queries)

# **\================================================================================ VAULT: Titan Manufacturing**

... (continue for all 10 queries)

# **\================================================================================ VAULT: Launchpad Ventures**

... (continue for all 10 queries)

# **\================================================================================ SUMMARY**

Run Date: 2026-01-12 03:00:00 Total Runtime: 25 minutes 43 seconds

| Vault | Docs | Chunks | Entities | Rels | Queries |
| ----- | ----- | ----- | ----- | ----- | ----- |
| TechVentures | 4 | 12 | 166 | 120 | 10 |
| Morrison & Sterling | 3 | 8 | 97 | 100 | 9 |
| Riverside Medical Center | 3 | 10 | 93 | 120 | 10 |
| Titan Manufacturing | 3 | 9 | 85 | 92 | 10 |
| Launchpad Ventures | 3 | 11 | 103 | 131 | 10 |
| \------------------------- | \------ | \-------- | \---------- | \------ | \-------- |
| TOTAL | 16 | 50 | 544 | 563 | 49 |

# **All 49 queries executed. Review answers above for correctness.**

\================================================================================  
IMPLEMENTATION  
\================================================================================

File: scripts/e2e\_lifecycle\_test.py  
\`\`\`python  
\#\!/usr/bin/env python3  
"""  
E2E Lifecycle Test for Context Foundry

Tests the complete system exactly as a real user would:  
1\. Delete existing vaults  
2\. Create fresh vaults  
3\. Upload documents  
4\. Run extraction  
5\. Run all queries  
6\. Save full answers to file for human review

Usage:  
    python scripts/e2e\_lifecycle\_test.py

Output:  
    /mnt/user-data/outputs/e2e\_results\_YYYYMMDD\_HHMMSS.txt  
"""

import os  
import sys  
import time  
from datetime import datetime  
from typing import List, Dict, Any, Optional  
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(\_\_file\_\_))))

from db import get\_session  
from e2e\_config import VAULTS

\# Configuration  
MAX\_EXTRACTION\_WAIT \= 600  \# 10 minutes per vault  
POLL\_INTERVAL \= 10  \# seconds

\# Output file  
OUTPUT\_DIR \= "/mnt/user-data/outputs"  
OUTPUT\_FILE \= os.path.join(OUTPUT\_DIR, f"e2e\_results\_{datetime.now().strftime('%Y%m%d\_%H%M%S')}.txt")

class E2ETest:  
    def \_\_init\_\_(self):  
        self.start\_time \= datetime.now()  
        self.results \= \[\]  
          
        \# Ensure output directory exists  
        os.makedirs(OUTPUT\_DIR, exist\_ok=True)  
          
        \# Initialize output file  
        self.write\_output(f"""================================================================================  
E2E LIFECYCLE TEST RESULTS  
\================================================================================  
Run Date: {self.start\_time.strftime('%Y-%m-%d %H:%M:%S')}  
\================================================================================  
""")  
      
    def log(self, message: str):  
        """Log to console with timestamp."""  
        elapsed \= (datetime.now() \- self.start\_time).total\_seconds()  
        timestamp \= datetime.now().strftime("%H:%M:%S")  
        print(f"\[{timestamp}\] \[{int(elapsed)}s\] {message}")  
      
    def write\_output(self, text: str):  
        """Write to output file."""  
        with open(OUTPUT\_FILE, "a", encoding="utf-8") as f:  
            f.write(text)  
      
    def run(self) \-\> int:  
        """Run E2E test for all vaults. Returns exit code."""  
          
        self.log(f"Starting E2E test for {len(VAULTS)} vaults")  
        self.log(f"Output file: {OUTPUT\_FILE}")  
          
        for vault\_config in VAULTS:  
            self.log(f"\\n{'='\*60}")  
            self.log(f"VAULT: {vault\_config\['name'\]}")  
            self.log(f"{'='\*60}")  
              
            result \= self.test\_vault(vault\_config)  
            self.results.append(result)  
              
            if not result\["success"\]:  
                self.log(f"VAULT FAILED: {result\['error'\]}")  
            else:  
                self.log(f"VAULT COMPLETE: {result\['query\_count'\]} queries executed")  
          
        \# Write summary  
        self.write\_summary()  
          
        self.log(f"\\n{'='\*60}")  
        self.log(f"E2E TEST COMPLETE")  
        self.log(f"Output file: {OUTPUT\_FILE}")  
        self.log(f"{'='\*60}")  
          
        \# Return 0 if all vaults succeeded, 1 if any failed  
        failed \= \[r for r in self.results if not r\["success"\]\]  
        return 1 if failed else 0  
      
    def test\_vault(self, config: Dict\[str, Any\]) \-\> Dict\[str, Any\]:  
        """Test a single vault. Returns result dict."""  
          
        vault\_name \= config\["name"\]  
        doc\_dir \= config\["doc\_dir"\]  
        queries \= config\["queries"\]  
          
        result \= {  
            "vault": vault\_name,  
            "success": False,  
            "error": None,  
            "doc\_count": 0,  
            "chunk\_count": 0,  
            "entity\_count": 0,  
            "relationship\_count": 0,  
            "query\_count": 0,  
        }  
          
        try:  
            \# Step 0: Delete existing vault  
            tenant\_id \= self.step0\_delete\_existing(vault\_name)  
              
            \# Step 1: Create vault  
            tenant\_id \= self.step1\_create\_vault(vault\_name)  
              
            \# Step 2: Upload documents  
            doc\_ids, doc\_names \= self.step2\_upload\_documents(tenant\_id, doc\_dir)  
            result\["doc\_count"\] \= len(doc\_ids)  
              
            \# Step 3: Trigger extraction  
            self.step3\_trigger\_extraction(doc\_ids, tenant\_id)  
              
            \# Step 4: Wait for extraction  
            counts \= self.step4\_wait\_for\_extraction(tenant\_id)  
            result\["chunk\_count"\] \= counts\["chunks"\]  
            result\["entity\_count"\] \= counts\["entities"\]  
            result\["relationship\_count"\] \= counts\["relationships"\]  
              
            \# Write vault header to output  
            self.write\_vault\_header(vault\_name, doc\_names, counts)  
              
            \# Step 5: Run queries  
            self.step5\_run\_queries(tenant\_id, vault\_name, queries)  
            result\["query\_count"\] \= len(queries)  
              
            \# Step 6: Done (no cleanup)  
            self.log(f"Vault ready for use: {vault\_name}")  
              
            result\["success"\] \= True  
            return result  
              
        except Exception as e:  
            result\["error"\] \= str(e)  
            self.log(f"ERROR: {e}")  
            return result  
      
    def step0\_delete\_existing(self, vault\_name: str) \-\> Optional\[str\]:  
        """Delete existing vault if it exists."""  
        self.log(f"Step 0: Delete existing vault '{vault\_name}'")  
          
        session \= get\_session(use\_rls\_role=False)  
          
        \# Find existing vault  
        result \= session.execute(  
            text("SELECT id FROM platform.tenants WHERE name \= :name"),  
            {"name": vault\_name}  
        ).fetchone()  
          
        if not result:  
            self.log("         No existing vault found")  
            return None  
          
        tenant\_id \= str(result\[0\])  
        self.log(f"         Found existing vault: {tenant\_id}")  
          
        \# Delete in correct order (FK constraints)  
        tables\_to\_clear \= \[  
            "entity\_aliases",  
            "duplicate\_candidates",   
            "relationships",  
            "entities",  
            "document\_chunks",  
            "documents",  
        \]  
          
        for table in tables\_to\_clear:  
            try:  
                r \= session.execute(  
                    text(f"DELETE FROM {table} WHERE tenant\_id \= :tid"),  
                    {"tid": tenant\_id}  
                )  
                if r.rowcount \> 0:  
                    self.log(f"         Deleted {r.rowcount} rows from {table}")  
            except Exception as e:  
                self.log(f"         Warning: Could not delete from {table}: {e}")  
          
        \# Delete vault  
        session.execute(  
            text("DELETE FROM platform.tenants WHERE id \= :tid"),  
            {"tid": tenant\_id}  
        )  
          
        session.commit()  
        self.log("         Deleted existing vault")  
        return tenant\_id  
      
    def step1\_create\_vault(self, vault\_name: str) \-\> str:  
        """Create vault and return tenant\_id."""  
        self.log(f"Step 1: Create vault '{vault\_name}'")  
          
        session \= get\_session(use\_rls\_role=False)  
          
        \# Create vault \- adjust columns based on actual schema  
        result \= session.execute(  
            text("""  
                INSERT INTO platform.tenants (name, slug, created\_at)  
                VALUES (:name, :slug, NOW())  
                RETURNING id  
            """),  
            {"name": vault\_name, "slug": vault\_name.lower().replace(" ", "-").replace("&", "and")}  
        )  
          
        tenant\_id \= str(result.fetchone()\[0\])  
        session.commit()  
          
        self.log(f"         Created vault: {tenant\_id}")  
        return tenant\_id  
      
    def step2\_upload\_documents(self, tenant\_id: str, doc\_dir: str) \-\> tuple:  
        """Upload all documents from directory. Returns (doc\_ids, doc\_names)."""  
        self.log(f"Step 2: Upload documents from '{doc\_dir}'")  
          
        if not os.path.exists(doc\_dir):  
            raise Exception(f"Document directory not found: {doc\_dir}")  
          
        \# List all files (don't hardcode)  
        files \= sorted(\[f for f in os.listdir(doc\_dir) if os.path.isfile(os.path.join(doc\_dir, f))\])  
          
        if not files:  
            raise Exception(f"No documents found in: {doc\_dir}")  
          
        session \= get\_session(use\_rls\_role=False)  
        doc\_ids \= \[\]  
        doc\_names \= \[\]  
          
        for filename in files:  
            filepath \= os.path.join(doc\_dir, filename)  
              
            with open(filepath, "r", encoding="utf-8") as f:  
                content \= f.read()  
              
            \# Insert document \- adjust columns based on actual schema  
            result \= session.execute(  
                text("""  
                    INSERT INTO documents (tenant\_id, filename, content, created\_at)  
                    VALUES (:tid, :fname, :content, NOW())  
                    RETURNING id  
                """),  
                {"tid": tenant\_id, "fname": filename, "content": content}  
            )  
              
            doc\_id \= str(result.fetchone()\[0\])  
            doc\_ids.append(doc\_id)  
            doc\_names.append(filename)  
              
            self.log(f"         Uploaded: {filename}")  
          
        session.commit()  
        self.log(f"         Total: {len(doc\_ids)} documents")  
        return doc\_ids, doc\_names  
      
    def step3\_trigger\_extraction(self, doc\_ids: List\[str\], tenant\_id: str):  
        """Trigger extraction for all documents."""  
        self.log(f"Step 3: Trigger extraction for {len(doc\_ids)} documents")  
          
        \# Import extraction function \- adjust based on actual codebase  
        from services.ingestion import process\_document  
          
        for doc\_id in doc\_ids:  
            process\_document(doc\_id, tenant\_id)  
          
        self.log("         Extraction triggered")  
      
    def step4\_wait\_for\_extraction(self, tenant\_id: str) \-\> Dict\[str, int\]:  
        """Wait for extraction to complete. Returns counts."""  
        self.log(f"Step 4: Wait for extraction (max {MAX\_EXTRACTION\_WAIT}s)")  
          
        session \= get\_session(use\_rls\_role=False)  
        elapsed \= 0  
          
        while elapsed \< MAX\_EXTRACTION\_WAIT:  
            result \= session.execute(  
                text("""  
                    SELECT   
                        (SELECT COUNT(\*) FROM document\_chunks WHERE tenant\_id \= :tid),  
                        (SELECT COUNT(\*) FROM entities WHERE tenant\_id \= :tid),  
                        (SELECT COUNT(\*) FROM relationships WHERE tenant\_id \= :tid)  
                """),  
                {"tid": tenant\_id}  
            ).fetchone()  
              
            chunks, entities, rels \= result  
              
            if elapsed % 30 \== 0:  
                self.log(f"         \[{elapsed}s\] chunks={chunks}, entities={entities}, relationships={rels}")  
              
            if chunks \> 0 and entities \> 0 and rels \> 0:  
                self.log(f"         Extraction complete in {elapsed}s")  
                return {"chunks": chunks, "entities": entities, "relationships": rels}  
              
            time.sleep(POLL\_INTERVAL)  
            elapsed \+= POLL\_INTERVAL  
          
        raise Exception(f"Extraction timeout after {MAX\_EXTRACTION\_WAIT}s")  
      
    def write\_vault\_header(self, vault\_name: str, doc\_names: List\[str\], counts: Dict\[str, int\]):  
        """Write vault header to output file."""  
        self.write\_output(f"""  
\================================================================================  
VAULT: {vault\_name}  
\================================================================================  
Documents Uploaded: {len(doc\_names)}  
""")  
        for doc in doc\_names:  
            self.write\_output(f"  \- {doc}\\n")  
          
        self.write\_output(f"""  
Extraction Results:  
  \- Chunks: {counts\['chunks'\]}  
  \- Entities: {counts\['entities'\]}  
  \- Relationships: {counts\['relationships'\]}

""")  
      
    def step5\_run\_queries(self, tenant\_id: str, vault\_name: str, queries: List\[str\]):  
        """Run all queries and write full answers to output file."""  
        self.log(f"Step 5: Run {len(queries)} queries")  
          
        from tool\_agent import ToolAgent  
          
        session \= get\_session(use\_rls\_role=True)  
        session.execute(text(f"SET app.current\_tenant\_id \= '{tenant\_id}'"))  
          
        agent \= ToolAgent(session, tenant\_id)  
          
        for i, query in enumerate(queries, 1):  
            self.log(f"         Query {i}/{len(queries)}: {query\[:50\]}...")  
              
            try:  
                result \= agent.query(query, vault\_context=vault\_name)  
                answer \= result.get("answer", "NO ANSWER RETURNED")  
                confidence \= result.get("confidence", 0\)  
            except Exception as e:  
                answer \= f"ERROR: {e}"  
                confidence \= 0  
              
            \# Write FULL answer to output file  
            self.write\_output(f"""--------------------------------------------------------------------------------  
QUERY {i}/{len(queries)}: {query}  
\--------------------------------------------------------------------------------  
ANSWER:  
{answer}

CONFIDENCE: {confidence:.0%}  
\--------------------------------------------------------------------------------

""")  
          
        self.log(f"         All {len(queries)} queries executed")  
      
    def write\_summary(self):  
        """Write summary to output file."""  
        total\_runtime \= (datetime.now() \- self.start\_time).total\_seconds()  
        minutes \= int(total\_runtime // 60\)  
        seconds \= int(total\_runtime % 60\)  
          
        self.write\_output(f"""  
\================================================================================  
SUMMARY  
\================================================================================  
Run Date: {self.start\_time.strftime('%Y-%m-%d %H:%M:%S')}  
Total Runtime: {minutes} minutes {seconds} seconds

{"Vault":\<25} | Docs | Chunks | Entities | Rels | Queries | Status  
{"-"\*25}-|------|--------|----------|------|---------|--------  
""")  
          
        total\_docs \= 0  
        total\_chunks \= 0  
        total\_entities \= 0  
        total\_rels \= 0  
        total\_queries \= 0  
          
        for r in self.results:  
            status \= "OK" if r\["success"\] else f"FAILED: {r\['error'\]}"  
            self.write\_output(f"{r\['vault'\]:\<25} | {r\['doc\_count'\]:\>4} | {r\['chunk\_count'\]:\>6} | {r\['entity\_count'\]:\>8} | {r\['relationship\_count'\]:\>4} | {r\['query\_count'\]:\>7} | {status}\\n")  
              
            total\_docs \+= r\["doc\_count"\]  
            total\_chunks \+= r\["chunk\_count"\]  
            total\_entities \+= r\["entity\_count"\]  
            total\_rels \+= r\["relationship\_count"\]  
            total\_queries \+= r\["query\_count"\]  
          
        self.write\_output(f"""{"-"\*25}-|------|--------|----------|------|---------|--------  
{"TOTAL":\<25} | {total\_docs:\>4} | {total\_chunks:\>6} | {total\_entities:\>8} | {total\_rels:\>4} | {total\_queries:\>7} |

All {total\_queries} queries executed. Review answers above for correctness.  
\================================================================================  
""")

def main():  
    test \= E2ETest()  
    exit\_code \= test.run()  
    sys.exit(exit\_code)

if \_\_name\_\_ \== "\_\_main\_\_":  
    main()  
\`\`\`

\================================================================================  
BEFORE RUNNING  
\================================================================================

1\. Verify test documents exist:  
   ls \-la "test documents/TechVentures/"  
   ls \-la "test documents/Law Firm/"  
   ls \-la "test documents/Hospital/"  
   ls \-la "test documents/Titan Manufacturing/"  
   ls \-la "test documents/Launchpad Ventures/"

2\. Verify import paths are correct:  
   \- from services.ingestion import process\_document  
   \- from tool\_agent import ToolAgent  
     
   Adjust if needed based on actual codebase.

3\. Verify database schema:  
   \- platform.tenants columns (name, slug, etc.)  
   \- documents columns (tenant\_id, filename, content, etc.)  
     
   Adjust INSERT statements if needed.

\================================================================================  
RUN THE TEST  
\================================================================================

python scripts/e2e\_lifecycle\_test.py

\================================================================================  
OUTPUT  
\================================================================================

Results saved to: /mnt/user-data/outputs/e2e\_results\_YYYYMMDD\_HHMMSS.txt

Share this file for review of all 49 answers.

\================================================================================  
REMEMBER  
\================================================================================

\- This deletes and recreates the user's actual vaults  
\- This leaves vaults intact after test (no cleanup)  
\- This saves FULL answers for human review

\- No auto-pass/fail — humans verify correctness

