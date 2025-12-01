document.addEventListener('DOMContentLoaded', function() {
    const queryForm = document.getElementById('queryForm');
    const queryInput = document.getElementById('queryInput');
    const queryBtn = document.getElementById('queryBtn');
    const resultsContainer = document.getElementById('resultsContainer');
    const recentQueries = document.getElementById('recentQueries');
    const queryList = document.getElementById('queryList');
    
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
        const nodesContainer = document.getElementById('graphNodes');
        const linksContainer = document.getElementById('graphLinks');
        
        if (nodesContainer.children.length > 0) return;
        
        const nodes = [
            { id: 1, label: 'Payment Service', x: 150, y: 80, type: 'service' },
            { id: 2, label: 'Auth Service', x: 250, y: 120, type: 'service' },
            { id: 3, label: 'Checkout', x: 200, y: 180, type: 'service' },
            { id: 4, label: 'DB', x: 100, y: 160, type: 'database' },
            { id: 5, label: 'API Gateway', x: 300, y: 80, type: 'service' },
            { id: 6, label: 'Cache', x: 350, y: 160, type: 'service' },
        ];
        
        const links = [
            { source: 1, target: 4 },
            { source: 2, target: 4 },
            { source: 3, target: 1 },
            { source: 3, target: 2 },
            { source: 5, target: 2 },
            { source: 5, target: 6 },
        ];
        
        links.forEach(link => {
            const source = nodes.find(n => n.id === link.source);
            const target = nodes.find(n => n.id === link.target);
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', source.x);
            line.setAttribute('y1', source.y);
            line.setAttribute('x2', target.x);
            line.setAttribute('y2', target.y);
            line.setAttribute('stroke', 'rgba(6, 182, 212, 0.3)');
            line.setAttribute('stroke-width', '1');
            line.setAttribute('stroke-dasharray', '4,4');
            linksContainer.appendChild(line);
        });
        
        nodes.forEach(node => {
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('transform', `translate(${node.x}, ${node.y})`);
            
            const glow = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            glow.setAttribute('r', '20');
            glow.setAttribute('fill', 'url(#nodeGlow)');
            g.appendChild(glow);
            
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('r', '10');
            circle.setAttribute('fill', '#0f172a');
            circle.setAttribute('stroke', node.type === 'database' ? '#f59e0b' : '#06b6d4');
            circle.setAttribute('stroke-width', '2');
            g.appendChild(circle);
            
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            icon.setAttribute('text-anchor', 'middle');
            icon.setAttribute('dominant-baseline', 'central');
            icon.setAttribute('fill', node.type === 'database' ? '#f59e0b' : '#06b6d4');
            icon.setAttribute('font-size', '8');
            icon.textContent = node.type === 'database' ? 'DB' : 'S';
            g.appendChild(icon);
            
            nodesContainer.appendChild(g);
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
