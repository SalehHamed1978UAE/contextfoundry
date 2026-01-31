# Corpus Maker: Add "Create Vault" Functionality

## Problem

Currently:
- Corpus Maker can upload/register a corpus
- But there's NO way to create a vault from that corpus
- Test Runner only works with EXISTING vaults
- "Fresh" mode DELETES an existing vault first
- Can't create a vault for a NEW corpus
- Can't create MULTIPLE vaults from the same corpus

## Solution

Add a "Create Vault" action that:
1. Creates a new vault in the platform
2. Uploads corpus documents to the vault
3. Triggers extraction
4. Updates test_config.json with the new vault ID

---

## Part 1: Update Corpus Maker UI

Add a "Create Vault" button to each registered corpus:

```html
<!-- In the Registered Corpora section -->
<div class="corpus-card" data-corpus-id="${corpus.id}">
    <div class="corpus-header">
        <h4>${corpus.name}</h4>
        <span class="corpus-files">${corpus.file_count || '?'} files</span>
    </div>

    <div class="corpus-details">
        <div class="detail-row">
            <span class="label">Questions:</span>
            <span class="value">${corpus.questions_file || 'None'}</span>
        </div>
        <div class="detail-row">
            <span class="label">Current Vault:</span>
            <span class="value">${corpus.current_vault_id ? corpus.current_vault_id.slice(0, 12) + '...' : 'None'}</span>
        </div>
    </div>

    <div class="corpus-actions">
        <!-- PRIMARY ACTION: Create New Vault -->
        <button class="btn btn-primary" onclick="createVaultFromCorpus('${corpus.id}')">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 5v14M5 12h14"/>
            </svg>
            Create Vault
        </button>

        <!-- Secondary: View existing vault if exists -->
        ${corpus.current_vault_id ? `
            <button class="btn btn-secondary" onclick="openVault('${corpus.current_vault_id}')">
                Open Vault
            </button>
        ` : ''}

        <!-- Delete corpus registration -->
        <button class="btn btn-outline danger" onclick="deleteCorpus('${corpus.id}')">
            Delete
        </button>
    </div>
</div>
```

---

## Part 2: JavaScript - Create Vault Function

```javascript
async function createVaultFromCorpus(corpusId) {
    // Get corpus details
    const corpus = await fetch(`/api/corpus-maker/corpora/${corpusId}`).then(r => r.json());

    if (!corpus) {
        showNotification('error', 'Corpus not found');
        return;
    }

    // Show modal for vault name
    const vaultName = prompt(
        `Create new vault from "${corpus.name}"?\n\nEnter vault name:`,
        `${corpus.name} - ${new Date().toLocaleDateString()}`
    );

    if (!vaultName) return; // User cancelled

    // Show progress
    showProgress('Creating vault...');

    try {
        const response = await fetch('/api/corpus-maker/create-vault', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                corpus_id: corpusId,
                vault_name: vaultName,
                auto_extract: true
            })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('success', `Vault "${vaultName}" created! ${result.documents_uploaded} documents uploaded.`);

            // Refresh the corpus list to show new vault ID
            loadRegisteredCorpora();

            // Optionally open the vault
            if (confirm('Vault created! Open it now?')) {
                window.location.href = `/app/${result.vault_id}`;
            }
        } else {
            showNotification('error', `Failed to create vault: ${result.error}`);
        }
    } catch (error) {
        showNotification('error', `Error: ${error.message}`);
    } finally {
        hideProgress();
    }
}

function showProgress(message) {
    // Create or show progress overlay
    let overlay = document.getElementById('progressOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'progressOverlay';
        overlay.className = 'progress-overlay';
        overlay.innerHTML = `
            <div class="progress-content">
                <div class="spinner"></div>
                <p id="progressMessage">${message}</p>
            </div>
        `;
        document.body.appendChild(overlay);
    } else {
        document.getElementById('progressMessage').textContent = message;
        overlay.style.display = 'flex';
    }
}

function hideProgress() {
    const overlay = document.getElementById('progressOverlay');
    if (overlay) overlay.style.display = 'none';
}

function openVault(vaultId) {
    window.location.href = `/app/${vaultId}`;
}
```

---

## Part 3: Backend API - Create Vault Endpoint

```python
@app.route('/api/corpus-maker/create-vault', methods=['POST'])
def create_vault_from_corpus():
    """
    Create a new vault and populate it with corpus documents.

    Request body:
    {
        "corpus_id": "codex-nexus-industries",
        "vault_name": "Nexus Industries Test 2",
        "auto_extract": true
    }
    """
    data = request.json
    corpus_id = data.get('corpus_id')
    vault_name = data.get('vault_name')
    auto_extract = data.get('auto_extract', True)

    if not corpus_id or not vault_name:
        return jsonify({'success': False, 'error': 'Missing corpus_id or vault_name'}), 400

    try:
        # 1. Load corpus config
        with open('src/test_config.json', 'r') as f:
            config = json.load(f)

        # Find corpus by ID (ID is lowercase name with dashes)
        corpus = None
        corpus_name = None
        for name, info in config.get('corpora', {}).items():
            if name.lower().replace(' ', '-') == corpus_id:
                corpus = info
                corpus_name = name
                break

        if not corpus:
            return jsonify({'success': False, 'error': f'Corpus not found: {corpus_id}'}), 404

        # 2. Create new vault
        from platform_foundation.src.tenant_service import TenantService
        tenant_service = TenantService()

        new_vault = tenant_service.create_tenant(
            name=vault_name,
            description=f"Created from corpus: {corpus_name}"
        )
        vault_id = str(new_vault['id'])

        # 3. Upload documents from corpus folder
        from platform_foundation.src.document_service import DocumentService
        doc_service = DocumentService()

        corpus_path = Path(corpus['root_path'])
        uploaded_count = 0

        # Get upload rules
        upload_rules = config.get('upload_rules', {})
        valid_extensions = upload_rules.get('valid_extensions', ['.pdf', '.docx', '.xlsx', '.txt', '.md'])
        include_folders = upload_rules.get('include_folders', ['documents'])

        for folder in include_folders:
            folder_path = corpus_path / folder
            if not folder_path.exists():
                continue

            for file_path in folder_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
                    with open(file_path, 'rb') as f:
                        content = f.read()

                    doc_service.upload_document(
                        tenant_id=vault_id,
                        filename=file_path.name,
                        mime_type=get_mime_type(file_path),
                        file_content=content,
                        auto_extract=auto_extract
                    )
                    uploaded_count += 1

        # 4. Update config with new vault ID (optional - could create separate entry)
        # For now, just update current_vault_id
        config['corpora'][corpus_name]['current_vault_id'] = vault_id
        config['corpora'][corpus_name]['last_vault_created'] = datetime.now().isoformat()

        with open('src/test_config.json', 'w') as f:
            json.dump(config, f, indent=2)

        return jsonify({
            'success': True,
            'vault_id': vault_id,
            'vault_name': vault_name,
            'documents_uploaded': uploaded_count,
            'auto_extract': auto_extract
        })

    except Exception as e:
        logger.error(f"Failed to create vault: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def get_mime_type(file_path):
    """Get MIME type from file extension."""
    ext = file_path.suffix.lower()
    mime_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.csv': 'text/csv',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
    }
    return mime_types.get(ext, 'application/octet-stream')
```

---

## Part 4: CSS for Corpus Cards

```css
.corpus-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.corpus-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}

.corpus-header h4 {
    margin: 0;
    color: #e2e8f0;
    font-size: 1rem;
}

.corpus-files {
    font-size: 0.75rem;
    color: #64748b;
    background: #0f172a;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
}

.corpus-details {
    margin-bottom: 1rem;
}

.detail-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.813rem;
    padding: 0.25rem 0;
    border-bottom: 1px solid #0f172a;
}

.detail-row .label {
    color: #64748b;
}

.detail-row .value {
    color: #94a3b8;
    font-family: monospace;
}

.corpus-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.corpus-actions .btn {
    flex: 1;
    min-width: 100px;
}

.corpus-actions .btn-primary {
    background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
    border: none;
    color: white;
}

.corpus-actions .btn-secondary {
    background: #334155;
    border: 1px solid #475569;
    color: #e2e8f0;
}

.corpus-actions .btn-outline.danger {
    background: transparent;
    border: 1px solid #475569;
    color: #64748b;
}

.corpus-actions .btn-outline.danger:hover {
    border-color: #ef4444;
    color: #ef4444;
}

/* Progress Overlay */
.progress-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(15, 23, 42, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.progress-content {
    text-align: center;
    color: #e2e8f0;
}

.spinner {
    width: 48px;
    height: 48px;
    border: 3px solid #334155;
    border-top-color: #06b6d4;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 1rem;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
```

---

## Part 5: Update Test Runner to Show Corpus-based Vault Creation

In Test Runner, add option to create vault from corpus:

```html
<!-- Add below the vault dropdown -->
<div class="vault-actions">
    <span>or</span>
    <button class="btn-link" onclick="showCreateVaultModal()">
        + Create new vault from corpus
    </button>
</div>
```

```javascript
function showCreateVaultModal() {
    // Fetch available corpora and show selection modal
    fetch('/api/corpus-maker/corpora')
        .then(r => r.json())
        .then(data => {
            const corpora = data.corpora || [];

            if (corpora.length === 0) {
                alert('No corpora registered. Go to Corpus Maker to add one first.');
                return;
            }

            // Show modal with corpus selection
            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <h3>Create Vault from Corpus</h3>
                    <div class="form-group">
                        <label>Select Corpus:</label>
                        <select id="corpusSelect">
                            ${corpora.map(c => `<option value="${c.id}">${c.name} (${c.file_count || '?'} files)</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Vault Name:</label>
                        <input type="text" id="newVaultName" placeholder="My Test Vault">
                    </div>
                    <div class="modal-actions">
                        <button class="btn btn-primary" onclick="createVaultAndClose()">Create Vault</button>
                        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        });
}

async function createVaultAndClose() {
    const corpusId = document.getElementById('corpusSelect').value;
    const vaultName = document.getElementById('newVaultName').value.trim();

    if (!vaultName) {
        alert('Please enter a vault name');
        return;
    }

    closeModal();

    // Use the same create-vault API
    const response = await fetch('/api/corpus-maker/create-vault', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            corpus_id: corpusId,
            vault_name: vaultName,
            auto_extract: true
        })
    });

    const result = await response.json();

    if (result.success) {
        alert(`Vault created! ${result.documents_uploaded} documents uploaded.`);
        // Refresh vault dropdown
        loadVaults();
        // Select the new vault
        document.getElementById('vaultSelect').value = result.vault_id;
    } else {
        alert(`Failed: ${result.error}`);
    }
}

function closeModal() {
    document.querySelector('.modal')?.remove();
}
```

---

## Summary

**What this adds:**

1. **Corpus Maker** → Each corpus card has a "Create Vault" button
2. **Test Runner** → "Create new vault from corpus" link below vault dropdown
3. **Backend** → `/api/corpus-maker/create-vault` endpoint that:
   - Creates a new vault
   - Uploads all corpus documents
   - Triggers extraction
   - Updates test_config.json

**User can now:**
- Create a vault from a new corpus ✓
- Create multiple vaults from the same corpus ✓
- No need to delete existing vault first ✓
