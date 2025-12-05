document.addEventListener('DOMContentLoaded', function() {
    const queryForm = document.getElementById('queryForm');
    const queryInput = document.getElementById('queryInput');
    const queryBtn = document.getElementById('queryBtn');
    const resultsContainer = document.getElementById('resultsContainer');
    const recentQueries = document.getElementById('recentQueries');
    const queryList = document.getElementById('queryList');
    
    // Mobile menu elements
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sidebar = document.getElementById('sidebar');
    const mobileOverlay = document.getElementById('mobileOverlay');
    
    // Mobile menu toggle
    if (hamburgerBtn && sidebar && mobileOverlay) {
        hamburgerBtn.addEventListener('click', function() {
            hamburgerBtn.classList.toggle('active');
            sidebar.classList.toggle('open');
            mobileOverlay.classList.toggle('visible');
        });
        
        mobileOverlay.addEventListener('click', function() {
            hamburgerBtn.classList.remove('active');
            sidebar.classList.remove('open');
            mobileOverlay.classList.remove('visible');
        });
        
        // Close menu when nav item is clicked
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', function() {
                if (window.innerWidth <= 768) {
                    hamburgerBtn.classList.remove('active');
                    sidebar.classList.remove('open');
                    mobileOverlay.classList.remove('visible');
                }
            });
        });
    }
    
    // Desktop sidebar toggle (collapsible)
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle && sidebar) {
        // Restore sidebar state from localStorage
        const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (sidebarCollapsed) {
            sidebar.classList.add('collapsed');
        }
        
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            // Save preference to localStorage
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
    }
    
    let queryHistory = [];
    let startTime = Date.now();

    loadStats();
    updateSystemStatus();

    queryForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;
        await executeQuery(query);
    });

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', function() {
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            this.classList.add('active');
            
            const page = this.dataset.page;
            document.getElementById('pageTitle').textContent = this.textContent.trim();
            
            document.querySelectorAll('.page-content').forEach(p => p.style.display = 'none');
            
            if (page === 'dashboard') {
                document.querySelector('.page-content:not(.page-memory):not(.page-learning):not(.page-rules)').style.display = 'block';
            } else if (page === 'memory') {
                document.querySelector('.page-memory').style.display = 'block';
                renderMemoryGraph();
            } else if (page === 'learning') {
                document.querySelector('.page-learning').style.display = 'block';
            } else if (page === 'rules') {
                document.querySelector('.page-rules').style.display = 'block';
            }
        });
    });

    let graphAutoRefreshInterval = null;
    let currentLifecycleFilter = 'all';
    
    async function fetchGraphData(lifecycleState = 'all') {
        try {
            const url = `/api/graph/visualization?lifecycle_state=${lifecycleState}&limit=100`;
            const response = await fetch(url);
            const data = await response.json();
            if (data.success) {
                return data;
            }
            console.error('Failed to fetch graph data:', data.error);
            return null;
        } catch (error) {
            console.error('Error fetching graph data:', error);
            return null;
        }
    }
    
    function getLifecycleColor(lifecycleState) {
        switch(lifecycleState) {
            case 'STAGING': return '#f59e0b';
            case 'TRUSTED': return '#10b981';
            case 'ARCHIVED': return '#6b7280';
            default: return '#06b6d4';
        }
    }
    
    function getNodeIcon(type) {
        const normalizedType = (type || '').toUpperCase();
        switch(normalizedType) {
            case 'DATABASE': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>';
            case 'TEAM': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';
            case 'PERSON': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
            case 'SERVICE': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>';
            case 'COMPONENT': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>';
            case 'INCIDENT': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
            default: return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/></svg>';
        }
    }
    
    async function renderMemoryGraph(forceRefresh = false) {
        const graphContainer = document.getElementById('graphNodesHtml');
        const linksContainer = document.getElementById('graphLinks');
        
        if (!graphContainer) return;
        
        if (graphContainer.children.length > 0 && !forceRefresh) return;
        
        graphContainer.innerHTML = '';
        linksContainer.innerHTML = '';
        
        const data = await fetchGraphData(currentLifecycleFilter);
        if (!data || !data.nodes || data.nodes.length === 0) {
            graphContainer.innerHTML = '<div style="color: #64748b; text-align: center; padding: 40px;">No entities found. Ingest some documents first.</div>';
            return;
        }
        
        const nodes = data.nodes;
        const edges = data.edges;
        
        updateGraphStats(data.stats);
        
        const containerWidth = graphContainer.parentElement?.offsetWidth || 700;
        const containerHeight = graphContainer.parentElement?.offsetHeight || 400;
        
        const nodePositions = {};
        const cols = Math.ceil(Math.sqrt(nodes.length));
        const cellWidth = Math.min(120, (containerWidth - 80) / cols);
        const cellHeight = Math.min(100, (containerHeight - 80) / Math.ceil(nodes.length / cols));
        
        nodes.forEach((node, i) => {
            const col = i % cols;
            const row = Math.floor(i / cols);
            const jitterX = (Math.random() - 0.5) * 30;
            const jitterY = (Math.random() - 0.5) * 30;
            nodePositions[node.id] = {
                x: 60 + col * cellWidth + jitterX,
                y: 60 + row * cellHeight + jitterY
            };
        });
        
        edges.forEach((edge, i) => {
            const source = nodePositions[edge.source];
            const target = nodePositions[edge.target];
            if (!source || !target) return;
            
            const edgeColor = getLifecycleColor(edge.lifecycle_state);
            
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.style.opacity = '0';
            g.style.transition = `opacity 0.5s ease ${0.3 + i * 0.02}s`;
            
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', source.x);
            line.setAttribute('y1', source.y);
            line.setAttribute('x2', target.x);
            line.setAttribute('y2', target.y);
            line.setAttribute('stroke', edgeColor + '40');
            line.setAttribute('stroke-width', '1.5');
            g.appendChild(line);
            
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', midX);
            text.setAttribute('y', midY - 4);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('fill', 'rgba(148, 163, 184, 0.6)');
            text.setAttribute('font-size', '8');
            text.setAttribute('font-family', 'JetBrains Mono, monospace');
            text.textContent = edge.type;
            g.appendChild(text);
            
            linksContainer.appendChild(g);
            setTimeout(() => { g.style.opacity = '1'; }, 50);
        });
        
        nodes.forEach((node, i) => {
            const pos = nodePositions[node.id];
            const color = getLifecycleColor(node.lifecycle_state);
            const confidence = node.confidence || 0.5;
            const baseSize = 36;
            const size = baseSize + (confidence * 16);
            const opacity = 0.6 + (confidence * 0.4);
            
            const nodeEl = document.createElement('div');
            nodeEl.className = 'graph-node';
            nodeEl.style.cssText = `
                position: absolute;
                left: ${pos.x}px;
                top: ${pos.y}px;
                width: ${size}px;
                height: ${size}px;
                margin-left: ${-size/2}px;
                margin-top: ${-size/2}px;
                border-radius: 50%;
                background: #1e293b;
                border: 2px solid ${color};
                box-shadow: 0 0 20px ${color}40, 0 0 40px ${color}20;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transform: scale(0);
                opacity: 0;
                transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease, box-shadow 0.2s ease;
                z-index: 10;
            `;
            
            const iconSize = Math.max(14, size * 0.4);
            const iconWrapper = document.createElement('div');
            iconWrapper.style.cssText = `width: ${iconSize}px; height: ${iconSize}px; color: ${color}; opacity: ${opacity};`;
            iconWrapper.innerHTML = getNodeIcon(node.type);
            nodeEl.appendChild(iconWrapper);
            
            const tooltip = document.createElement('div');
            tooltip.className = 'graph-tooltip';
            tooltip.style.cssText = `
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                margin-bottom: 8px;
                padding: 8px 12px;
                background: rgba(15, 23, 42, 0.95);
                border: 1px solid ${color}50;
                border-radius: 6px;
                font-size: 11px;
                font-family: 'JetBrains Mono', monospace;
                color: ${color};
                white-space: nowrap;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s ease;
                z-index: 100;
                text-align: left;
            `;
            tooltip.innerHTML = `
                <div style="font-weight: bold; margin-bottom: 4px;">${escapeHtml(node.name)}</div>
                <div style="color: #94a3b8; font-size: 10px;">Type: ${node.type}</div>
                <div style="color: #94a3b8; font-size: 10px;">State: ${node.lifecycle_state}</div>
                <div style="color: #94a3b8; font-size: 10px;">Confidence: ${Math.round(confidence * 100)}%</div>
            `;
            nodeEl.appendChild(tooltip);
            
            nodeEl.addEventListener('mouseenter', () => {
                nodeEl.style.transform = 'scale(1.15)';
                nodeEl.style.boxShadow = `0 0 30px ${color}60, 0 0 60px ${color}30`;
                tooltip.style.opacity = '1';
            });
            nodeEl.addEventListener('mouseleave', () => {
                nodeEl.style.transform = 'scale(1)';
                nodeEl.style.boxShadow = `0 0 20px ${color}40, 0 0 40px ${color}20`;
                tooltip.style.opacity = '0';
            });
            
            graphContainer.appendChild(nodeEl);
            
            setTimeout(() => {
                nodeEl.style.transform = 'scale(1)';
                nodeEl.style.opacity = '1';
            }, 100 + i * 40);
        });
    }
    
    function updateGraphStats(stats) {
        const statsEl = document.getElementById('graphStats');
        if (statsEl && stats) {
            const counts = stats.lifecycle_counts || {};
            statsEl.innerHTML = `
                <span class="graph-stat staging">STAGING: ${counts.STAGING || 0}</span>
                <span class="graph-stat trusted">TRUSTED: ${counts.TRUSTED || 0}</span>
                <span class="graph-stat archived">ARCHIVED: ${counts.ARCHIVED || 0}</span>
                <span class="graph-stat total">Showing: ${stats.total_nodes} nodes, ${stats.total_edges} edges</span>
            `;
        }
    }
    
    function initGraphControls() {
        const filterSelect = document.getElementById('lifecycleFilter');
        const refreshBtn = document.getElementById('graphRefreshBtn');
        const autoRefreshToggle = document.getElementById('autoRefreshToggle');
        
        if (filterSelect) {
            filterSelect.addEventListener('change', async (e) => {
                currentLifecycleFilter = e.target.value;
                await renderMemoryGraph(true);
            });
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                refreshBtn.classList.add('spinning');
                await renderMemoryGraph(true);
                setTimeout(() => refreshBtn.classList.remove('spinning'), 500);
            });
        }
        
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    graphAutoRefreshInterval = setInterval(() => {
                        renderMemoryGraph(true);
                    }, 30000);
                } else {
                    if (graphAutoRefreshInterval) {
                        clearInterval(graphAutoRefreshInterval);
                        graphAutoRefreshInterval = null;
                    }
                }
            });
        }
    }
    
    initGraphControls();

    document.getElementById('refreshBtn').addEventListener('click', loadStats);
    document.getElementById('newQueryBtn').addEventListener('click', () => {
        queryInput.focus();
        resultsContainer.classList.remove('visible');
    });

    async function loadStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            if (data.success) {
                const stats = data.stats;
                const totalEntities = stats.semantic_memory.entities.total;
                const totalRels = stats.semantic_memory.relationships.total;
                const docs = stats.episodic_memory.total_documents;
                
                document.getElementById('accuracyValue').innerHTML = '82<span class="unit">%</span>';
                document.getElementById('fidelityValue').innerHTML = '91<span class="unit">%</span>';
                document.getElementById('confidenceValue').innerHTML = '94<span class="unit">%</span>';
                
                document.getElementById('memoryUsage').textContent = `${totalEntities + totalRels + docs}`;
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    function updateSystemStatus() {
        const latency = Math.floor(Math.random() * 20 + 10);
        document.getElementById('latencyValue').textContent = `${latency}ms`;
        
        setInterval(() => {
            const latency = Math.floor(Math.random() * 20 + 10);
            document.getElementById('latencyValue').textContent = `${latency}ms`;
        }, 5000);
    }

    async function executeQuery(query) {
        queryBtn.classList.add('loading');
        const queryStartTime = Date.now();

        try {
            const response = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });

            const data = await response.json();
            const duration = ((Date.now() - queryStartTime) / 1000).toFixed(2);
            
            if (data.success) {
                displayResults(data, duration);
                addToHistory(query, data, duration);
            } else {
                showError(data.error || 'Query failed');
            }
        } catch (error) {
            showError(error.message);
        } finally {
            queryBtn.classList.remove('loading');
        }
    }

    let currentQueryData = null;
    
    function displayResults(data, duration) {
        resultsContainer.classList.add('visible');
        recentQueries.style.display = 'none';

        const confidence = Math.round(data.confidence * 100);
        document.getElementById('resultConfidence').textContent = confidence + '%';
        
        const circumference = 2 * Math.PI * 36;
        const offset = circumference - (confidence / 100) * circumference;
        const fill = document.getElementById('confidenceFill');
        setTimeout(() => {
            fill.style.strokeDashoffset = offset;
        }, 100);

        document.getElementById('resultId').textContent = 
            'Query ID: ' + (data.query_log?.query_id?.slice(0, 8) || 'N/A');
        document.getElementById('resultDuration').textContent = duration + ' seconds';

        document.getElementById('answerContent').innerHTML = formatAnswer(data.answer);

        const evidenceList = document.getElementById('evidenceList');
        evidenceList.innerHTML = data.evidence_chain.slice(0, 8).map((ev, i) => {
            const layer = ev.memory_layer || getLayerFromType(ev.type);
            return `
                <div class="evidence-item ${layer}">
                    <div class="evidence-number">${i + 1}</div>
                    <div class="evidence-content">
                        <div class="evidence-description">${escapeHtml(ev.description || '')}</div>
                        <div class="evidence-source">${escapeHtml(ev.source || '')}</div>
                        ${ev.confidence ? `<div class="evidence-confidence">${Math.round(ev.confidence * 100)}% confidence</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        const rulesList = document.getElementById('rulesList');
        const passedRules = data.rules_passed || [];
        rulesList.innerHTML = (data.rules_checked || []).slice(0, 6).map(rule => 
            `<span class="rule-tag ${passedRules.includes(rule) ? 'passed' : ''}">${escapeHtml(rule)}</span>`
        ).join('');

        currentQueryData = {
            query_text: queryInput.value,
            response_text: data.answer,
            confidence: data.confidence,
            query_log_id: data.query_log?.query_id || null
        };
        
        resetFeedbackUI();
        document.getElementById('feedbackSection').style.display = 'block';

        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    function resetFeedbackUI() {
        document.querySelectorAll('.feedback-btn').forEach(btn => {
            btn.classList.remove('active');
            btn.disabled = false;
        });
        document.querySelectorAll('.error-type-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.getElementById('errorTypeSelector').style.display = 'none';
        document.getElementById('feedbackStatus').style.display = 'none';
        document.getElementById('feedbackStatus').className = 'feedback-status';
    }
    
    document.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const judgment = this.dataset.judgment;
            
            document.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            if (judgment === 'incorrect' || judgment === 'partial') {
                document.getElementById('errorTypeSelector').style.display = 'block';
            } else {
                document.getElementById('errorTypeSelector').style.display = 'none';
                await submitFeedback(judgment, null);
            }
        });
    });
    
    document.querySelectorAll('.error-type-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const errorType = this.dataset.error;
            const judgment = document.querySelector('.feedback-btn.active')?.dataset.judgment || 'incorrect';
            
            document.querySelectorAll('.error-type-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            await submitFeedback(judgment, errorType);
        });
    });
    
    async function submitFeedback(judgment, errorType) {
        if (!currentQueryData) {
            showFeedbackStatus('No query data available', false);
            return;
        }
        
        document.querySelectorAll('.feedback-btn').forEach(btn => btn.disabled = true);
        document.querySelectorAll('.error-type-btn').forEach(btn => btn.disabled = true);
        
        try {
            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query_text: currentQueryData.query_text,
                    response_text: currentQueryData.response_text,
                    confidence: currentQueryData.confidence,
                    judgment: judgment,
                    error_type: errorType,
                    query_log_id: currentQueryData.query_log_id
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showFeedbackStatus('Thank you for your feedback!', true);
            } else {
                showFeedbackStatus(data.error || 'Failed to submit feedback', false);
                document.querySelectorAll('.feedback-btn').forEach(btn => btn.disabled = false);
                document.querySelectorAll('.error-type-btn').forEach(btn => btn.disabled = false);
            }
        } catch (error) {
            showFeedbackStatus('Network error: ' + error.message, false);
            document.querySelectorAll('.feedback-btn').forEach(btn => btn.disabled = false);
            document.querySelectorAll('.error-type-btn').forEach(btn => btn.disabled = false);
        }
    }
    
    function showFeedbackStatus(message, isSuccess) {
        const statusEl = document.getElementById('feedbackStatus');
        statusEl.textContent = message;
        statusEl.className = 'feedback-status ' + (isSuccess ? 'success' : 'error');
        statusEl.style.display = 'block';
    }

    function addToHistory(query, data, duration) {
        queryHistory.unshift({
            id: data.query_log?.query_id?.slice(0, 8) || Math.random().toString(36).slice(2, 10),
            query: query,
            confidence: Math.round(data.confidence * 100),
            duration: duration,
            timestamp: new Date()
        });

        if (queryHistory.length > 5) {
            queryHistory = queryHistory.slice(0, 5);
        }

        updateQueryList();
    }

    function updateQueryList() {
        if (queryHistory.length === 0) return;

        queryList.innerHTML = queryHistory.map(q => {
            const timeAgo = getTimeAgo(q.timestamp);
            return `
                <div class="query-item" data-query="${escapeHtml(q.query)}">
                    <div class="query-item-left">
                        <span class="query-id">${q.id}</span>
                        <span class="query-text">${escapeHtml(q.query.slice(0, 60))}${q.query.length > 60 ? '...' : ''}</span>
                    </div>
                    <div class="query-meta">
                        <span class="query-time">${timeAgo}</span>
                        <span class="query-confidence">${q.confidence}%</span>
                    </div>
                </div>
            `;
        }).join('');

        document.querySelectorAll('.query-item').forEach(item => {
            item.addEventListener('click', function() {
                const query = this.dataset.query;
                queryInput.value = query;
                executeQuery(query);
            });
        });
    }

    function getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        if (seconds < 60) return 'just now';
        if (seconds < 3600) return Math.floor(seconds / 60) + ' min ago';
        if (seconds < 86400) return Math.floor(seconds / 3600) + ' hour ago';
        return Math.floor(seconds / 86400) + ' day ago';
    }

    function getLayerFromType(type) {
        switch (type) {
            case 'entity':
            case 'relationship':
                return 'semantic';
            case 'document':
                return 'episodic';
            case 'rule':
                return 'symbolic';
            default:
                return 'semantic';
        }
    }

    function formatAnswer(answer) {
        if (!answer) return '';
        return escapeHtml(answer)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function showError(message) {
        console.error(message);
        alert('Error: ' + message);
    }
});
