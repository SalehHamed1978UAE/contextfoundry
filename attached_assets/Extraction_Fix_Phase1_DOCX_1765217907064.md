# Phase 1: Fix DOCX Text Extraction

**Problem:** Current DOCX extraction only reads paragraphs. Document titles, tables, and headers are completely missed.

**Evidence:** "Federated Data Catalog" (the document title) was not extracted because it's in a header or title field.

---

## Current Code (brain/app.py, ~line 338)

```python
text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
```

This ONLY extracts paragraph text.

---

## Replace With

```python
from docx import Document

def extract_docx_text_complete(file_path: str) -> str:
    """
    Extract ALL text from a DOCX file including:
    - Document properties (title, subject)
    - All paragraphs
    - All tables
    - Headers and footers
    """
    doc = Document(file_path)
    text_parts = []
    
    # 1. Document properties (often contains the title)
    try:
        if doc.core_properties.title:
            text_parts.append(f"DOCUMENT TITLE: {doc.core_properties.title}")
        if doc.core_properties.subject:
            text_parts.append(f"SUBJECT: {doc.core_properties.subject}")
    except Exception:
        pass
    
    # 2. All paragraphs (main body)
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            # Check if it's a heading (likely important entity)
            if para.style and para.style.name and 'Heading' in para.style.name:
                text_parts.append(f"SECTION: {text}")
            else:
                text_parts.append(text)
    
    # 3. All tables
    for table in doc.tables:
        table_text = []
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                table_text.append(" | ".join(row_cells))
        if table_text:
            text_parts.append("TABLE CONTENT:")
            text_parts.extend(table_text)
    
    # 4. Headers and footers from all sections
    for section in doc.sections:
        # Header
        if section.header:
            for para in section.header.paragraphs:
                text = para.text.strip()
                if text:
                    text_parts.insert(0, f"HEADER: {text}")  # Headers go first
        # Footer
        if section.footer:
            for para in section.footer.paragraphs:
                text = para.text.strip()
                if text:
                    text_parts.append(f"FOOTER: {text}")
    
    return "\n".join(text_parts)
```

---

## Integration

Find where DOCX files are processed and replace the simple paragraph extraction with `extract_docx_text_complete()`.

---

## Test

After implementing, check the Federated Data Catalog document:
1. How many characters extracted? (should increase)
2. Does "Federated Data Catalog" appear in extracted text?
3. Are table contents captured?

---

**DO NOT proceed to Phase 2 until this works.**
