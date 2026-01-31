# Corpus Maker: Bug Fixes Required

## Issue 1: No Upload Confirmation

**Problem:** After upload completes, there's no feedback - screen just sits there.

**Fix:** Add success/error feedback after upload completes.

```javascript
async function uploadCorpus() {
    const uploadBtn = document.querySelector('.upload-btn');
    const originalText = uploadBtn.innerHTML;

    try {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<span class="spinner"></span> Uploading...';

        const response = await fetch('/api/corpus-maker/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            // SHOW SUCCESS MESSAGE
            showNotification('success', `Successfully uploaded ${result.files_uploaded} files to "${corpusName}"`);

            // Clear the form
            clearSelection();
            document.getElementById('corpusName').value = '';

            // Refresh the registered corpora list
            loadRegisteredCorpora();
        } else {
            showNotification('error', `Upload failed: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        showNotification('error', `Upload failed: ${error.message}`);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalText;
    }
}

// Add this notification function
function showNotification(type, message) {
    // Remove existing notifications
    document.querySelectorAll('.notification').forEach(n => n.remove());

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-icon">${type === 'success' ? '✓' : '✕'}</span>
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;

    // Insert at top of main content area
    const container = document.querySelector('.corpus-maker-content') || document.body;
    container.insertBefore(notification, container.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => notification.remove(), 5000);
}
```

**CSS for notifications:**
```css
.notification {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
    animation: slideIn 0.3s ease;
}

@keyframes slideIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}

.notification-success {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #4ade80;
}

.notification-error {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #f87171;
}

.notification-icon {
    font-size: 1.25rem;
    font-weight: bold;
}

.notification-message {
    flex: 1;
}

.notification-close {
    background: none;
    border: none;
    color: inherit;
    font-size: 1.25rem;
    cursor: pointer;
    opacity: 0.7;
}

.notification-close:hover {
    opacity: 1;
}
```

---

## Issue 2: "Validate First" Button Does Nothing

**Problem:** Button exists but has no functionality.

**Fix:** Either implement validation OR remove the button.

### Option A: Implement Validation

```javascript
async function validateCorpus() {
    const corpusName = document.getElementById('corpusName').value.trim();

    if (!corpusName) {
        showNotification('error', 'Please enter a corpus name first');
        return;
    }

    if (selectedFiles.length === 0 && Object.keys(folderStructure).length === 0) {
        showNotification('error', 'Please select files to validate');
        return;
    }

    const validateBtn = document.querySelector('.validate-btn');
    validateBtn.disabled = true;
    validateBtn.innerHTML = 'Validating...';

    try {
        // Collect files to validate
        const filesToValidate = [];

        Object.entries(folderStructure).forEach(([folder, data]) => {
            if (data.included) {
                data.files.forEach(file => {
                    filesToValidate.push({
                        name: file.name,
                        size: file.size,
                        type: file.type || 'unknown',
                        folder: folder,
                        category: data.category
                    });
                });
            }
        });

        // Check for issues
        const issues = [];
        const validExtensions = ['.pdf', '.docx', '.xlsx', '.xls', '.csv', '.txt', '.md'];

        filesToValidate.forEach(file => {
            const ext = '.' + file.name.split('.').pop().toLowerCase();

            if (!validExtensions.includes(ext)) {
                issues.push(`Invalid file type: ${file.name}`);
            }

            if (file.size === 0) {
                issues.push(`Empty file: ${file.name}`);
            }

            if (file.size > 50 * 1024 * 1024) { // 50MB
                issues.push(`File too large (>50MB): ${file.name}`);
            }
        });

        // Show results
        const validatedSection = document.getElementById('validatedFiles');
        validatedSection.style.display = 'block';

        if (issues.length === 0) {
            validatedSection.innerHTML = `
                <div class="validation-success">
                    <h4>✓ Validation Passed</h4>
                    <p>${filesToValidate.length} files ready for upload</p>
                </div>
            `;
            showNotification('success', 'Validation passed! Ready to upload.');
        } else {
            validatedSection.innerHTML = `
                <div class="validation-errors">
                    <h4>⚠ Validation Issues (${issues.length})</h4>
                    <ul>
                        ${issues.map(i => `<li>${i}</li>`).join('')}
                    </ul>
                </div>
            `;
            showNotification('error', `Found ${issues.length} validation issues`);
        }

    } catch (error) {
        showNotification('error', `Validation failed: ${error.message}`);
    } finally {
        validateBtn.disabled = false;
        validateBtn.innerHTML = 'Validate First';
    }
}
```

### Option B: Remove the Button

If validation isn't needed, just remove the button from the HTML:
```html
<!-- DELETE THIS -->
<button class="validate-btn" onclick="validateCorpus()">Validate First</button>
```

---

## Issue 3: "Registered Corpora" Shows Nothing

**Problem:** Section exists but doesn't load or display any data.

**Fix:** Implement the API call and rendering.

```javascript
// Call this on page load and after successful upload
async function loadRegisteredCorpora() {
    const container = document.getElementById('registeredCorpora');

    try {
        const response = await fetch('/api/corpus-maker/corpora');
        const data = await response.json();

        if (!data.corpora || data.corpora.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No corpora registered yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <table class="corpora-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Files</th>
                        <th>Vault ID</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.corpora.map(corpus => `
                        <tr>
                            <td>${corpus.name}</td>
                            <td>${corpus.file_count || '-'}</td>
                            <td><code>${corpus.vault_id ? corpus.vault_id.slice(0, 8) + '...' : '-'}</code></td>
                            <td>${corpus.created_at ? new Date(corpus.created_at).toLocaleDateString() : '-'}</td>
                            <td>
                                <button class="btn-sm" onclick="viewCorpus('${corpus.id}')">View</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        container.innerHTML = `
            <div class="error-state">
                <p>Failed to load corpora: ${error.message}</p>
            </div>
        `;
    }
}

// Load on page ready
document.addEventListener('DOMContentLoaded', loadRegisteredCorpora);
```

**Backend API needed:**
```python
@app.route('/api/corpus-maker/corpora', methods=['GET'])
def list_corpora():
    """List all registered corpora from test_config.json"""
    try:
        with open('src/test_config.json', 'r') as f:
            config = json.load(f)

        corpora = []
        for name, info in config.get('corpora', {}).items():
            corpora.append({
                'id': name.lower().replace(' ', '-'),
                'name': name,
                'file_count': info.get('file_count'),
                'vault_id': info.get('current_vault_id'),
                'created_at': info.get('created_at'),
                'questions_file': info.get('questions_file')
            })

        return jsonify({'corpora': corpora})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Issue 4: "Validated Files" Section Empty

**Problem:** Section shows nothing.

**Fix:** This section should populate after validation runs (see Issue 2 fix above).

If validation isn't being used, hide or remove this section:

```javascript
// Hide if not using validation
document.getElementById('validatedFilesSection').style.display = 'none';
```

Or remove from HTML entirely.

---

## Summary Checklist for Replit

| Issue | Fix |
|-------|-----|
| No upload confirmation | Add `showNotification()` function + call after upload |
| "Validate First" does nothing | Implement `validateCorpus()` OR remove button |
| "Registered Corpora" empty | Add `loadRegisteredCorpora()` + backend `/api/corpus-maker/corpora` |
| "Validated Files" empty | Populate after validation OR remove section |

**Priority:**
1. Upload confirmation (most important - users need feedback)
2. Registered Corpora list (useful to see what's uploaded)
3. Validation (nice to have)
