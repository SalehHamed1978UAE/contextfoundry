# Corpus Maker: Fix Drop Zone + Multi-Folder Selection

## Problem 1: Drop Zone Doesn't Work

The big dashed box should be clickable to open the folder picker. Currently only the small button works.

**Fix:** Make the drop zone clickable:

```javascript
// Add click handler to drop zone
document.getElementById('dropZone').addEventListener('click', function() {
    document.getElementById('folderInput').click();
});
```

Also make sure the drop zone has `cursor: pointer` in CSS:
```css
.drop-zone {
    cursor: pointer;
}
```

---

## Problem 2: Can't Multi-Select Folders

**THIS IS A BROWSER LIMITATION.** The HTML `<input type="file" webkitdirectory>` only allows selecting ONE folder at a time. This cannot be changed - it's how browsers work.

### Solution: Drag and Drop

**Drag and drop DOES support multiple folders.** User can:
1. Open Finder/Explorer
2. Navigate to their corpus folder
3. Select multiple subfolders (Shift+click or Cmd/Ctrl+click)
4. Drag them ALL onto the drop zone at once

**Update the UI to make this clear:**

```html
<div class="drop-zone" id="dropZone">
    <div class="drop-zone-content">
        <svg>...</svg>
        <p><strong>Drag folders here</strong></p>
        <p class="hint">Select multiple folders in Finder/Explorer, then drag them all at once</p>
        <p class="divider">— or —</p>
        <p class="hint">Click to select one folder (browser limitation)</p>
    </div>
</div>
```

### Drag and Drop Handler (Make sure this exists):

```javascript
const dropZone = document.getElementById('dropZone');

// Drag over
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('drag-over');
});

// Drag leave
dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');
});

// Drop - handle multiple folders!
dropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');

    const items = Array.from(e.dataTransfer.items);
    const allFolders = [];

    for (const item of items) {
        if (item.kind === 'file') {
            const entry = item.webkitGetAsEntry();

            if (entry && entry.isDirectory) {
                // It's a folder - get all files inside
                const files = await traverseDirectory(entry);
                allFolders.push({
                    name: entry.name,
                    files: files
                });
            }
        }
    }

    if (allFolders.length > 0) {
        // Add ALL dropped folders to the selection
        allFolders.forEach(folder => {
            addFolderToSelection(folder.name, folder.files);
        });
        updateUI();
    }
});

// Recursively get all files in a directory
async function traverseDirectory(dirEntry, path = '') {
    const files = [];
    const reader = dirEntry.createReader();

    const readEntries = () => new Promise((resolve) => {
        reader.readEntries(resolve);
    });

    let entries;
    do {
        entries = await readEntries();
        for (const entry of entries) {
            const entryPath = path ? `${path}/${entry.name}` : entry.name;

            if (entry.isFile) {
                const file = await new Promise(resolve => entry.file(resolve));
                // Store the relative path
                file.relativePath = `${dirEntry.name}/${entryPath}`;
                files.push(file);
            } else if (entry.isDirectory) {
                const subFiles = await traverseDirectory(entry, entryPath);
                files.push(...subFiles);
            }
        }
    } while (entries.length > 0);

    return files;
}

// Add a folder to the selection (accumulative!)
function addFolderToSelection(folderName, files) {
    // Check if folder already exists
    if (folderStructure[folderName]) {
        // Folder already added, skip or merge
        console.log(`Folder "${folderName}" already in selection`);
        return;
    }

    folderStructure[folderName] = {
        files: files,
        included: true,
        category: detectCategory(folderName)
    };
}
```

---

## Updated User Flow

```
┌─────────────────────────────────────────────────────────────┐
│  📁 DOCUMENTS                                               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │         Drag folders here                          │   │
│  │                                                     │   │
│  │   Select multiple folders in Finder/Explorer,      │   │
│  │   then drag them all at once                       │   │
│  │                                                     │   │
│  │              — or —                                │   │
│  │                                                     │   │
│  │   Click to select one folder (browser limitation)  │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Selected:                                                  │
│  ☑ 📁 strategy/        12 files    [Strategy ▼]    ✕      │
│  ☑ 📁 projects/         8 files    [Projects ▼]    ✕      │
│  ☑ 📁 financials/       5 files    [Financials ▼]  ✕      │
│                                                             │
│  25 files in 3 folders                                      │
└─────────────────────────────────────────────────────────────┘
```

**Key points:**
1. Drop zone is clickable (opens single folder picker)
2. Drop zone accepts drag-and-drop (multiple folders at once!)
3. Dropped folders ACCUMULATE (don't replace previous selection)
4. Each folder can be removed individually with ✕ button
5. Clear messaging about the browser limitation

---

## Summary for Replit

1. **Fix the drop zone click handler** - should trigger `folderInput.click()`
2. **Implement proper drag-and-drop** - must handle MULTIPLE folders dropped at once
3. **Accumulate folders** - don't replace, ADD to selection
4. **Update UI text** - emphasize "drag folders here" as primary, click as secondary
5. **Browser limitation** - explain that clicking only allows one folder due to browser restrictions
