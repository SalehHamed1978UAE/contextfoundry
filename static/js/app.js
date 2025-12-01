document.addEventListener('DOMContentLoaded', function() {
    const queryForm = document.getElementById('queryForm');
    const queryInput = document.getElementById('queryInput');
    const submitBtn = document.getElementById('submitBtn');
    const resultsSection = document.getElementById('resultsSection');
    const examplesList = document.getElementById('examplesList');

    loadStats();
    loadExamples();

    queryForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;
        await executeQuery(query);
    });

    async function loadStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            if (data.success) {
                const stats = data.stats;
                document.getElementById('semanticCount').textContent = 
                    stats.semantic_memory.entities.total + stats.semantic_memory.relationships.total;
                document.getElementById('episodicCount').textContent = 
                    stats.episodic_memory.total_documents;
                document.getElementById('symbolicCount').textContent = 
                    stats.symbolic_memory.total_rules;
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    async function loadExamples() {
        try {
            const response = await fetch('/api/examples');
            const data = await response.json();
            if (data.success) {
                examplesList.innerHTML = data.examples.slice(0, 4).map(ex => 
                    `<button class="example-btn" data-query="${ex.query}">${ex.category}</button>`
                ).join('');

                examplesList.querySelectorAll('.example-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        queryInput.value = this.dataset.query;
                        executeQuery(this.dataset.query);
                    });
                });
            }
        } catch (error) {
            console.error('Failed to load examples:', error);
        }
    }

    async function executeQuery(query) {
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;

        try {
            const response = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });

            const data = await response.json();
            
            if (data.success) {
                displayResults(data);
            } else {
                alert('Error: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            alert('Failed to execute query: ' + error.message);
        } finally {
            submitBtn.classList.remove('loading');
            submitBtn.disabled = false;
        }
    }

    function displayResults(data) {
        resultsSection.classList.add('visible');

        const confidence = Math.round(data.confidence * 100);
        document.getElementById('confidenceValue').textContent = confidence + '%';
        
        const circumference = 2 * Math.PI * 45;
        const offset = circumference - (confidence / 100) * circumference;
        const fill = document.getElementById('confidenceFill');
        
        if (!document.getElementById('confidenceGradient')) {
            const svg = fill.closest('svg');
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            defs.innerHTML = `
                <linearGradient id="confidenceGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#6366f1"/>
                    <stop offset="50%" style="stop-color:#8b5cf6"/>
                    <stop offset="100%" style="stop-color:#ec4899"/>
                </linearGradient>
            `;
            svg.insertBefore(defs, svg.firstChild);
        }
        
        fill.style.stroke = 'url(#confidenceGradient)';
        setTimeout(() => {
            fill.style.strokeDashoffset = offset;
        }, 100);

        document.getElementById('queryId').textContent = 
            'Query ID: ' + (data.query_log?.query_id?.slice(0, 8) || 'N/A');
        document.getElementById('queryDuration').textContent = 
            'Completed in ' + (data.query_log?.duration_seconds?.toFixed(2) || '0') + 's';

        document.getElementById('answerContent').innerHTML = formatAnswer(data.answer);

        const evidenceList = document.getElementById('evidenceList');
        evidenceList.innerHTML = data.evidence_chain.slice(0, 10).map((ev, i) => {
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
        rulesList.innerHTML = (data.rules_checked || []).map(rule => 
            `<span class="rule-tag ${passedRules.includes(rule) ? 'passed' : ''}">${escapeHtml(rule)}</span>`
        ).join('');

        const uncertaintySection = document.getElementById('uncertaintySection');
        const uncertainty = data.uncertainty || {};
        if (uncertainty.uncertain_facts?.length > 0 || uncertainty.reasons?.length > 0) {
            uncertaintySection.style.display = 'block';
            const notes = [
                ...(uncertainty.uncertain_facts || []),
                ...(uncertainty.reasons || [])
            ];
            document.getElementById('uncertaintyContent').textContent = notes.join(' ');
        } else {
            uncertaintySection.style.display = 'none';
        }

        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
});
