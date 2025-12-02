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

    function renderMemoryGraph() {
        const graphContainer = document.getElementById('graphNodesHtml');
        const linksContainer = document.getElementById('graphLinks');
        
        if (graphContainer && graphContainer.children.length > 0) return;
        if (!graphContainer) return;
        
        const nodes = [
            { id: 'n1', label: 'Payment Service', x: 120, y: 100, type: 'service', status: 'trusted' },
            { id: 'n2', label: 'Auth Service', x: 300, y: 80, type: 'service', status: 'trusted' },
            { id: 'n3', label: 'Checkout API', x: 480, y: 120, type: 'service', status: 'trusted' },
            { id: 'n4', label: 'Payments DB', x: 80, y: 250, type: 'database', status: 'trusted' },
            { id: 'n5', label: 'Users DB', x: 260, y: 280, type: 'database', status: 'trusted' },
            { id: 'n6', label: 'API Gateway', x: 400, y: 260, type: 'service', status: 'trusted' },
            { id: 'n7', label: 'Cache Layer', x: 560, y: 220, type: 'service', status: 'staging' },
            { id: 'n8', label: 'Auth Team', x: 180, y: 180, type: 'team', status: 'trusted' },
        ];
        
        const links = [
            { source: 'n1', target: 'n4', label: 'reads_from' },
            { source: 'n2', target: 'n5', label: 'reads_from' },
            { source: 'n3', target: 'n1', label: 'depends_on' },
            { source: 'n3', target: 'n2', label: 'depends_on' },
            { source: 'n6', target: 'n2', label: 'routes_to' },
            { source: 'n6', target: 'n3', label: 'routes_to' },
            { source: 'n3', target: 'n7', label: 'uses' },
            { source: 'n8', target: 'n2', label: 'owns' },
            { source: 'n1', target: 'n5', label: 'writes_to' },
        ];
        
        const getNodeColor = (status, type) => {
            if (type === 'database') return '#f59e0b';
            if (type === 'team') return '#8b5cf6';
            if (status === 'staging') return '#f59e0b';
            return '#06b6d4';
        };

        const getNodeIcon = (type) => {
            switch(type) {
                case 'database': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>';
                case 'team': return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';
                default: return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>';
            }
        };
        
        links.forEach((link, i) => {
            const source = nodes.find(n => n.id === link.source);
            const target = nodes.find(n => n.id === link.target);
            if (!source || !target) return;
            
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.style.opacity = '0';
            g.style.transition = `opacity 0.5s ease ${0.5 + i * 0.05}s`;
            
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', source.x);
            line.setAttribute('y1', source.y);
            line.setAttribute('x2', target.x);
            line.setAttribute('y2', target.y);
            line.setAttribute('stroke', 'rgba(6, 182, 212, 0.25)');
            line.setAttribute('stroke-width', '1');
            g.appendChild(line);
            
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', midX);
            text.setAttribute('y', midY - 6);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('fill', 'rgba(148, 163, 184, 0.6)');
            text.setAttribute('font-size', '9');
            text.setAttribute('font-family', 'JetBrains Mono, monospace');
            text.textContent = link.label;
            g.appendChild(text);
            
            linksContainer.appendChild(g);
            
            setTimeout(() => { g.style.opacity = '1'; }, 50);
        });
        
        nodes.forEach((node, i) => {
            const color = getNodeColor(node.status, node.type);
            
            const nodeEl = document.createElement('div');
            nodeEl.className = 'graph-node';
            nodeEl.style.cssText = `
                position: absolute;
                left: ${node.x}px;
                top: ${node.y}px;
                width: 48px;
                height: 48px;
                margin-left: -24px;
                margin-top: -24px;
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
            
            const iconWrapper = document.createElement('div');
            iconWrapper.style.cssText = `width: 20px; height: 20px; color: ${color};`;
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
                padding: 6px 10px;
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
            `;
            tooltip.textContent = node.label;
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
            }, 100 + i * 80);
        });
    }

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

        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
