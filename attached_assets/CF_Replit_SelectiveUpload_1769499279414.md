# Corpus Maker: Selective Folder Upload

**Goal**: User selects parent folder, then chooses which subfolders to include (excluding questions, manifests, etc.)

---

## User Flow

```
CorpusFolder/
├── ☑ strategy/         ← Include
├── ☑ projects/         ← Include
├── ☑ financials/       ← Include
├── ☐ questions.json    ← Exclude (unchecked)
├── ☐ manifest.json     ← Exclude (unchecked)
└── ☐ readme.md         ← Exclude (unchecked)
```

1. User clicks "Select Corpus Folder"
2. Selects the parent folder (e.g., `CorpusFolder`)
3. UI shows checkboxes for each subfolder AND loose files
4. **Folders are checked by default, loose files are unchecked by default**
5. User adjusts if needed
6. Upload only the checked items

---

## Part 1: HTML Structure

```html
<div class="upload-section">
    <h3>Documents</h3>

    <!-- Upload Button -->
    <button type="button" class="btn btn-primary" onclick="selectCorpusFolder()">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        Select Corpus Folder
    </button>

    <input type="file" id="folderInput" webkitdirectory directory multiple hidden>

    <!-- Drop Zone (shown when nothing selected) -->
    <div class="drop-zone" id="dropZone">
        <p><strong>Select your corpus folder</strong></p>
        <p class="hint">You'll be able to choose which subfolders to include</p>
    </div>

    <!-- Selection Panel (shown after folder selected) -->
    <div id="selectionPanel" class="selection-panel" style="display: none;">
        <div class="panel-header">
            <h4 id="rootFolderName">📁 CorpusFolder</h4>
            <div class="panel-actions">
                <button type="button" class="btn-link" onclick="selectAllFolders()">Select All Folders</button>
                <button type="button" class="btn-link" onclick="deselectAll()">Deselect All</button>
                <button type="button" class="btn-link danger" onclick="clearSelection()">Clear</button>
            </div>
        </div>

        <div class="panel-hint">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            Folders are selected by default. Uncheck items you don't want to upload.
        </div>

        <div id="itemList" class="item-list">
            <!-- Items will be rendered here -->
        </div>

        <div id="selectionSummary" class="selection-summary">
            <!-- Summary will be rendered here -->
        </div>
    </div>
</div>
```

---

## Part 2: CSS Styles

```css
/* Selection Panel */
.selection-panel {
    margin-top: 1rem;
    border: 1px solid #334155;
    border-radius: 12px;
    background: #1e293b;
    overflow: hidden;
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    background: #0f172a;
    border-bottom: 1px solid #334155;
}

.panel-header h4 {
    margin: 0;
    font-size: 0.938rem;
    color: #e2e8f0;
}

.panel-actions {
    display: flex;
    gap: 1rem;
}

.btn-link {
    background: none;
    border: none;
    color: #06b6d4;
    font-size: 0.75rem;
    cursor: pointer;
    padding: 0;
}

.btn-link:hover {
    text-decoration: underline;
}

.btn-link.danger {
    color: #f87171;
}

.panel-hint {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: rgba(6, 182, 212, 0.1);
    color: #06b6d4;
    font-size: 0.75rem;
    border-bottom: 1px solid #334155;
}

/* Item List */
.item-list {
    max-height: 350px;
    overflow-y: auto;
}

.item-row {
    display: flex;
    align-items: center;
    padding: 0.625rem 1rem;
    border-bottom: 1px solid #0f172a;
    transition: background 0.15s;
}

.item-row:hover {
    background: rgba(255, 255, 255, 0.02);
}

.item-row:last-child {
    border-bottom: none;
}

.item-row.excluded {
    opacity: 0.5;
}

.item-checkbox {
    width: 18px;
    height: 18px;
    margin-right: 0.75rem;
    accent-color: #06b6d4;
    cursor: pointer;
}

.item-icon {
    margin-right: 0.5rem;
    font-size: 1rem;
}

.item-icon.folder {
    color: #fbbf24;
}

.item-icon.file {
    color: #64748b;
}

.item-name {
    flex: 1;
    font-size: 0.875rem;
    color: #e2e8f0;
}

.item-row.excluded .item-name {
    color: #64748b;
    text-decoration: line-through;
}

.item-count {
    font-size: 0.75rem;
    color: #64748b;
    margin-right: 1rem;
}

.item-category {
    width: 130px;
}

.category-select {
    width: 100%;
    padding: 0.25rem 0.5rem;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    color: #e2e8f0;
    font-size: 0.75rem;
}

.item-row.excluded .category-select {
    display: none;
}

/* Selection Summary */
.selection-summary {
    padding: 1rem;
    background: #0f172a;
    border-top: 1px solid #334155;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.summary-text {
    font-size: 0.875rem;
    color: #e2e8f0;
}

.summary-text strong {
    color: #06b6d4;
}

.summary-excluded {
    font-size: 0.75rem;
    color: #64748b;
}
```

---

## Part 3: JavaScript

```javascript
// ============================================================
// STATE
// ============================================================

let allFiles = [];           // All files from selected folder
let folderStructure = {};    // subfolder -> { files: [], included: bool, category: string }
let looseFiles = [];         // Files in root (not in subfolders)
let rootFolderName = '';

// Files to auto-exclude (loose files matching these patterns)
const AUTO_EXCLUDE_PATTERNS = [
    /^questions.*\.json$/i,
    /^manifest\.json$/i,
    /^readme\.md$/i,
    /^\..*$/,              // Hidden files
    /.*\.log$/i,
    /^test.*\.json$/i,
];

const CATEGORY_KEYWORDS = {
    'strategy': ['strategy', 'strategic', 'planning', 'roadmap', 'vision'],
    'projects': ['project', 'projects', 'initiative', 'program'],
    'financials': ['financial', 'finance', 'budget', 'revenue', 'earnings'],
    'compliance': ['compliance', 'regulatory', 'audit', 'risk'],
    'hr': ['hr', 'human', 'personnel', 'employee'],
    'technical': ['technical', 'engineering', 'architecture', 'system'],
    'legal': ['legal', 'contract', 'agreement', 'nda'],
};

// ============================================================
// FOLDER SELECTION
// ============================================================

function selectCorpusFolder() {
    document.getElementById('folderInput').click();
}

document.getElementById('folderInput').addEventListener('change', function(e) {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    processSelectedFolder(files);
    e.target.value = '';
});

// ============================================================
// PROCESS FOLDER
// ============================================================

function processSelectedFolder(files) {
    allFiles = files;
    folderStructure = {};
    looseFiles = [];

    // Get root folder name
    const firstPath = files[0].webkitRelativePath || '';
    rootFolderName = firstPath.split('/')[0] || 'Selected Folder';

    // Categorize files
    files.forEach(file => {
        const path = file.webkitRelativePath || file.name;
        const parts = path.split('/');

        if (parts.length === 2) {
            // Loose file in root: CorpusFolder/file.txt
            looseFiles.push({
                file: file,
                name: parts[1],
                included: !shouldAutoExclude(parts[1])
            });
        } else if (parts.length > 2) {
            // File in subfolder: CorpusFolder/subfolder/file.txt
            const subfolder = parts[1];

            if (!folderStructure[subfolder]) {
                folderStructure[subfolder] = {
                    files: [],
                    included: true,  // Folders included by default
                    category: detectCategory(subfolder)
                };
            }
            folderStructure[subfolder].files.push(file);
        }
    });

    updateUI();
}

function shouldAutoExclude(filename) {
    return AUTO_EXCLUDE_PATTERNS.some(pattern => pattern.test(filename));
}

function detectCategory(folderName) {
    const nameLower = folderName.toLowerCase();
    for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
        if (keywords.some(kw => nameLower.includes(kw))) {
            return category;
        }
    }
    return 'uncategorized';
}

// ============================================================
// UPDATE UI
// ============================================================

function updateUI() {
    const dropZone = document.getElementById('dropZone');
    const panel = document.getElementById('selectionPanel');
    const itemList = document.getElementById('itemList');

    dropZone.style.display = 'none';
    panel.style.display = 'block';

    document.getElementById('rootFolderName').textContent = `📁 ${rootFolderName}`;

    // Build item list HTML
    let html = '';

    // Folders first (sorted alphabetically)
    const sortedFolders = Object.entries(folderStructure).sort((a, b) => a[0].localeCompare(b[0]));

    sortedFolders.forEach(([name, data]) => {
        html += `
            <div class="item-row ${data.included ? '' : 'excluded'}" data-type="folder" data-name="${name}">
                <input type="checkbox" class="item-checkbox"
                       ${data.included ? 'checked' : ''}
                       onchange="toggleFolder('${name}', this.checked)">
                <span class="item-icon folder">📁</span>
                <span class="item-name">${name}</span>
                <span class="item-count">${data.files.length} files</span>
                <div class="item-category">
                    <select class="category-select" onchange="setCategory('${name}', this.value)">
                        <option value="uncategorized" ${data.category === 'uncategorized' ? 'selected' : ''}>Uncategorized</option>
                        <option value="strategy" ${data.category === 'strategy' ? 'selected' : ''}>Strategy</option>
                        <option value="projects" ${data.category === 'projects' ? 'selected' : ''}>Projects</option>
                        <option value="financials" ${data.category === 'financials' ? 'selected' : ''}>Financials</option>
                        <option value="compliance" ${data.category === 'compliance' ? 'selected' : ''}>Compliance</option>
                        <option value="hr" ${data.category === 'hr' ? 'selected' : ''}>HR</option>
                        <option value="technical" ${data.category === 'technical' ? 'selected' : ''}>Technical</option>
                        <option value="legal" ${data.category === 'legal' ? 'selected' : ''}>Legal</option>
                    </select>
                </div>
            </div>
        `;
    });

    // Then loose files
    if (looseFiles.length > 0) {
        html += `<div class="item-separator">Root Files</div>`;

        looseFiles.forEach((item, index) => {
            html += `
                <div class="item-row ${item.included ? '' : 'excluded'}" data-type="file" data-index="${index}">
                    <input type="checkbox" class="item-checkbox"
                           ${item.included ? 'checked' : ''}
                           onchange="toggleLooseFile(${index}, this.checked)">
                    <span class="item-icon file">📄</span>
                    <span class="item-name">${item.name}</span>
                    <span class="item-count"></span>
                    <div class="item-category"></div>
                </div>
            `;
        });
    }

    itemList.innerHTML = html;
    updateSummary();
}

function updateSummary() {
    const summary = document.getElementById('selectionSummary');

    // Count included
    let includedFolders = 0;
    let includedFiles = 0;
    let excludedFiles = 0;

    Object.values(folderStructure).forEach(data => {
        if (data.included) {
            includedFolders++;
            includedFiles += data.files.length;
        } else {
            excludedFiles += data.files.length;
        }
    });

    looseFiles.forEach(item => {
        if (item.included) {
            includedFiles++;
        } else {
            excludedFiles++;
        }
    });

    summary.innerHTML = `
        <div class="summary-text">
            <strong>${includedFiles}</strong> files in <strong>${includedFolders}</strong> folders selected
        </div>
        <div class="summary-excluded">
            ${excludedFiles > 0 ? `${excludedFiles} files excluded` : ''}
        </div>
    `;
}

// ============================================================
// TOGGLE HANDLERS
// ============================================================

function toggleFolder(name, included) {
    folderStructure[name].included = included;

    // Update row styling
    const row = document.querySelector(`.item-row[data-name="${name}"]`);
    if (row) {
        row.classList.toggle('excluded', !included);
    }

    updateSummary();
}

function toggleLooseFile(index, included) {
    looseFiles[index].included = included;

    // Update row styling
    const row = document.querySelector(`.item-row[data-index="${index}"]`);
    if (row) {
        row.classList.toggle('excluded', !included);
    }

    updateSummary();
}

function setCategory(folderName, category) {
    folderStructure[folderName].category = category;
}

function selectAllFolders() {
    Object.keys(folderStructure).forEach(name => {
        folderStructure[name].included = true;
    });
    updateUI();
}

function deselectAll() {
    Object.keys(folderStructure).forEach(name => {
        folderStructure[name].included = false;
    });
    looseFiles.forEach(item => {
        item.included = false;
    });
    updateUI();
}

function clearSelection() {
    allFiles = [];
    folderStructure = {};
    looseFiles = [];
    rootFolderName = '';

    document.getElementById('dropZone').style.display = 'block';
    document.getElementById('selectionPanel').style.display = 'none';
}

// ============================================================
// UPLOAD
// ============================================================

async function uploadCorpus() {
    const corpusName = document.getElementById('corpusName').value.trim();

    if (!corpusName) {
        alert('Please enter a corpus name');
        return;
    }

    // Collect only included files
    const filesToUpload = [];
    const pathMap = {};

    // Add files from included folders
    Object.entries(folderStructure).forEach(([folderName, data]) => {
        if (data.included) {
            data.files.forEach(file => {
                const path = file.webkitRelativePath || file.name;
                filesToUpload.push({ file, path });
                pathMap[path] = data.category;
            });
        }
    });

    // Add included loose files
    looseFiles.forEach(item => {
        if (item.included) {
            const path = item.file.webkitRelativePath || item.name;
            filesToUpload.push({ file: item.file, path });
            pathMap[path] = 'uncategorized';
        }
    });

    if (filesToUpload.length === 0) {
        alert('No files selected for upload');
        return;
    }

    // Build FormData
    const formData = new FormData();
    formData.append('corpus_name', corpusName);
    formData.append('anchor_org', document.getElementById('anchorOrg')?.value || '');
    formData.append('path_map', JSON.stringify(pathMap));

    filesToUpload.forEach(({ file, path }) => {
        formData.append('files', file, path);
    });

    // Upload
    const uploadBtn = document.querySelector('.upload-btn');
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';

    try {
        const response = await fetch('/api/corpus-maker/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            alert(`Uploaded ${result.files_uploaded} files to "${corpusName}"`);
            clearSelection();
        } else {
            alert(`Upload failed: ${result.error}`);
        }
    } catch (err) {
        alert(`Upload failed: ${err.message}`);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload Corpus';
    }
}
```

---

## Summary

**User Flow:**
1. Click "Select Corpus Folder"
2. Select the parent folder (e.g., `NexusCorpus`)
3. UI shows:
   - ☑ strategy/ (12 files) [Strategy ▼]
   - ☑ projects/ (8 files) [Projects ▼]
   - ☐ questions.json *(auto-excluded)*
   - ☐ manifest.json *(auto-excluded)*
4. User can check/uncheck any item
5. Click "Upload Corpus" → only checked items uploaded

**Auto-Exclude Patterns:**
- `questions*.json`
- `manifest.json`
- `readme.md`
- Hidden files (`.gitignore`, etc.)
- `*.log` files
- `test*.json`

**Key Features:**
- Folders checked by default
- Loose files unchecked by default (except valid documents)
- "Select All Folders" / "Deselect All" quick actions
- Category dropdowns only shown for included folders
- Summary shows files selected vs excluded
