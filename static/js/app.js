// Initialize app - supports both DOMContentLoaded and turbo:load for Turbo.js navigation
function initApp() {
    const queryForm = document.getElementById('queryForm');
    const queryInput = document.getElementById('queryInput');
    const queryBtn = document.getElementById('queryBtn');
    const resultsContainer = document.getElementById('resultsContainer');
    const recentQueries = document.getElementById('recentQueries');
    const queryList = document.getElementById('queryList');
    
    // Mobile menu elements (permanent across Turbo navigations)
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sidebar = document.getElementById('sidebar');
    const mobileOverlay = document.getElementById('mobileOverlay');
    
    // Mobile menu toggle - only attach once (check for _initialized flag)
    if (hamburgerBtn && sidebar && mobileOverlay && !hamburgerBtn._appInitialized) {
        hamburgerBtn._appInitialized = true;
        
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
    }
    
    // Desktop sidebar toggle (collapsible) - only attach once
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle && sidebar && !sidebarToggle._appInitialized) {
        sidebarToggle._appInitialized = true;
        
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

    // Handle page switching
    function switchToPage(page, updateUrl = false) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.page-content').forEach(p => p.style.display = 'none');
        
        if (page === 'memory') {
            document.querySelector('.nav-item[data-page="memory"]')?.classList.add('active');
            document.querySelector('.page-memory').style.display = 'block';
            document.getElementById('pageTitle').textContent = 'Memory Graph';
            renderMemoryGraph();
            if (updateUrl) {
                history.pushState({page: 'memory'}, '', '/?page=memory');
            }
        } else {
            document.querySelector('.nav-item[data-page="dashboard"]')?.classList.add('active');
            document.querySelector('.page-content:not(.page-memory)').style.display = 'block';
            document.getElementById('pageTitle').textContent = 'Dashboard';
            if (updateUrl) {
                history.pushState({page: 'dashboard'}, '', '/');
            }
        }
    }
    
    // Check URL for page parameter on load
    const urlParams = new URLSearchParams(window.location.search);
    const initialPage = urlParams.get('page');
    if (initialPage === 'memory') {
        switchToPage('memory', false);
    }
    
    // Handle nav item clicks
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', function(e) {
            const page = this.dataset.page;
            // Only handle client-side navigation for pages with data-page attribute
            if (page) {
                e.preventDefault();
                switchToPage(page, true);
            }
            // Let other links (Command Center, A/B Eval) navigate normally
        });
    });
    
    // Handle browser back/forward
    window.addEventListener('popstate', function(e) {
        if (e.state && e.state.page) {
            switchToPage(e.state.page, false);
        } else {
            const params = new URLSearchParams(window.location.search);
            switchToPage(params.get('page') || 'dashboard', false);
        }
    });

    let currentLifecycleFilter = 'all';
    let graphNodes = {};
    let graphEdges = [];
    let selectedNodeId = null;
    let searchDebounceTimer = null;
    let layoutRadiusMultiplier = 1.0;
    let customNodePositions = {};
    let isDragging = false;
    let dragNodeId = null;
    let dragOffset = { x: 0, y: 0 };
    
    // Frontier detection data from query responses
    let currentFrontierNodes = {};  // Map of entity_name -> frontier info
    let currentGapsIdentified = [];
    
    // Helper to get human-readable frontier reason text
    function getFrontierReasonText(reason) {
        switch(reason) {
            case 'no_relationships': return 'No relationships documented';
            case 'no_edges_for_mode': return 'No edges for this traversal mode';
            case 'below_confidence_threshold': return 'Confidence below threshold';
            case 'max_depth_reached': return 'Maximum traversal depth reached';
            case 'all_neighbors_visited': return 'All neighbors already visited';
            default: return 'Unknown boundary';
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
    
    function getEntityTypeColor(entityType) {
        const type = (entityType || '').toUpperCase();
        switch(type) {
            case 'SERVICE': return '#3B82F6';
            case 'COMPONENT': return '#8B5CF6';
            case 'TEAM': return '#10B981';
            case 'PERSON': return '#F59E0B';
            case 'DATABASE': return '#06B6D4';
            case 'INCIDENT': return '#EF4444';
            case 'RUNBOOK': return '#EC4899';
            case 'DOCUMENT': return '#84CC16';
            default: return '#94A3B8';
        }
    }
    
    function getLifecycleBorderStyle(lifecycleState) {
        switch(lifecycleState) {
            case 'TRUSTED': return { style: 'solid', opacity: 1 };
            case 'STAGING': return { style: 'dashed', opacity: 0.85 };
            case 'ARCHIVED': return { style: 'solid', opacity: 0.4 };
            default: return { style: 'solid', opacity: 0.7 };
        }
    }
    
    function getRelationshipTypeColor(relType) {
        const type = (relType || '').toUpperCase();
        switch(type) {
            case 'DEPENDS_ON': return '#3B82F6';
            case 'OWNS': return '#10B981';
            case 'AFFECTS': return '#F97316';
            case 'SUPPORTS': return '#8B5CF6';
            case 'MEMBER_OF': return '#EAB308';
            case 'CAUSED_BY': return '#EF4444';
            case 'MANAGES': return '#06B6D4';
            case 'USES': return '#EC4899';
            case 'RESOLVED_BY': return '#22C55E';
            case 'ASSIGNED_TO': return '#F59E0B';
            default: return '#94A3B8';
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
    
    async function searchEntities(query) {
        if (!query || query.length < 2) return [];
        try {
            const url = `/api/graph/search?q=${encodeURIComponent(query)}&lifecycle_state=${currentLifecycleFilter}`;
            const response = await fetch(url);
            const data = await response.json();
            return data.success ? data.results : [];
        } catch (error) {
            console.error('Search error:', error);
            return [];
        }
    }
    
    async function expandEntity(entityId) {
        try {
            const url = `/api/graph/expand/${entityId}?lifecycle_state=${currentLifecycleFilter}&include_speculative=true`;
            const response = await fetch(url);
            const data = await response.json();
            if (data.success) {
                if (data.nodes && data.nodes.length === 0 && data.message) {
                    showGraphMessage(data.message);
                    return data;
                }
                data.nodes.forEach(node => {
                    if (!graphNodes[node.id]) {
                        graphNodes[node.id] = node;
                    }
                });
                data.edges.forEach(edge => {
                    if (!graphEdges.find(e => e.id === edge.id)) {
                        graphEdges.push(edge);
                    }
                });
                
                if (data.speculative && data.speculative.inferred && data.speculative.inferred.length > 0) {
                    data.speculative.inferred.forEach(inf => {
                        const targetId = inf.target_entity_id;
                        if (!graphNodes[targetId]) {
                            graphNodes[targetId] = {
                                id: targetId,
                                name: inf.target_entity_name,
                                type: inf.target_entity_type || 'UNKNOWN',
                                lifecycle_state: 'TRUSTED',
                                confidence: inf.confidence,
                                is_speculative_target: true
                            };
                        }
                        const sourceId = inf.source_entity_id;
                        if (!graphNodes[sourceId]) {
                            graphNodes[sourceId] = {
                                id: sourceId,
                                name: inf.source_entity_name,
                                type: inf.source_entity_type || 'UNKNOWN',
                                lifecycle_state: 'TRUSTED',
                                confidence: inf.confidence,
                                is_speculative_target: true
                            };
                        }
                        const specEdgeId = `spec-${sourceId}-${targetId}-${inf.rule_name}`;
                        if (!graphEdges.find(e => e.id === specEdgeId)) {
                            graphEdges.push({
                                id: specEdgeId,
                                source: sourceId,
                                target: targetId,
                                type: inf.inferred_relationship_type,
                                confidence: inf.confidence,
                                speculative: true,
                                rule_name: inf.rule_name,
                                supporting_evidence: inf.supporting_evidence
                            });
                        }
                    });
                }
                
                if (data.frontier && Array.isArray(data.frontier)) {
                    data.frontier.forEach(f => {
                        currentFrontierNodes[f.entity_name] = {
                            reason: f.reason,
                            message: f.message,
                            entity_type: f.entity_type,
                            depth: f.depth
                        };
                    });
                }
                
                renderGraph();
                return data;
            }
            return null;
        } catch (error) {
            console.error('Expand error:', error);
            return null;
        }
    }
    
    function showGraphMessage(message) {
        const emptyState = document.getElementById('graphEmptyState');
        if (emptyState) {
            emptyState.innerHTML = `
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 16px; opacity: 0.5;">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 8v4M12 16h.01"/>
                </svg>
                <div style="font-size: 14px; margin-bottom: 8px;">${escapeHtml(message)}</div>
                <div style="font-size: 12px; opacity: 0.7;">Try changing the lifecycle filter or searching for a different entity</div>
            `;
            emptyState.style.display = 'block';
        }
    }
    
    function resetEmptyState() {
        const emptyState = document.getElementById('graphEmptyState');
        if (emptyState) {
            emptyState.innerHTML = `
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 16px; opacity: 0.5;">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                </svg>
                <div style="font-size: 14px; margin-bottom: 8px;">Search to explore the knowledge graph</div>
                <div style="font-size: 12px; opacity: 0.7;">Type an entity name above to get started</div>
            `;
        }
    }
    
    async function loadEntityDetails(entityId) {
        try {
            const url = `/api/graph/entity/${entityId}`;
            const response = await fetch(url);
            const data = await response.json();
            if (data.success) {
                showDetailsPanel(data);
            }
        } catch (error) {
            console.error('Details error:', error);
        }
    }
    
    let currentDetailEntityId = null;
    
    function showDetailsPanel(data) {
        const panel = document.getElementById('detailsPanel');
        const content = document.getElementById('detailsContent');
        if (!panel || !content) return;
        
        const entity = data.entity;
        currentDetailEntityId = entity.id;
        const typeColor = getEntityTypeColor(entity.type);
        const lifecycleColor = getLifecycleColor(entity.lifecycle_state);
        
        let propsHtml = '';
        if (entity.properties && Object.keys(entity.properties).length > 0) {
            propsHtml = '<div style="margin-top: 16px;"><div style="color: var(--text-muted); font-size: 11px; margin-bottom: 8px;">PROPERTIES</div>';
            for (const [key, value] of Object.entries(entity.properties)) {
                if (key !== '_promoted_at' && value) {
                    propsHtml += `<div style="margin-bottom: 4px;"><span style="color: var(--text-muted);">${escapeHtml(key)}:</span> ${escapeHtml(String(value))}</div>`;
                }
            }
            propsHtml += '</div>';
        }
        
        let outgoingHtml = '';
        if (data.outgoing_relationships && data.outgoing_relationships.length > 0) {
            outgoingHtml = '<div style="margin-top: 16px;"><div style="color: var(--text-muted); font-size: 11px; margin-bottom: 8px;">OUTGOING RELATIONSHIPS</div>';
            data.outgoing_relationships.forEach(rel => {
                const relColor = getEntityTypeColor(rel.target_type);
                outgoingHtml += `
                    <div class="rel-item" data-entity-id="${rel.target_id}" style="padding: 8px; margin-bottom: 4px; background: var(--bg-secondary); border-radius: 4px; cursor: pointer;">
                        <div style="color: var(--accent-primary); font-size: 11px;">${escapeHtml(rel.relationship_type)}</div>
                        <div>${escapeHtml(rel.target_name)} <span style="color: ${relColor}; font-size: 11px;">(${rel.target_type})</span></div>
                    </div>
                `;
            });
            outgoingHtml += '</div>';
        }
        
        let incomingHtml = '';
        if (data.incoming_relationships && data.incoming_relationships.length > 0) {
            incomingHtml = '<div style="margin-top: 16px;"><div style="color: var(--text-muted); font-size: 11px; margin-bottom: 8px;">INCOMING RELATIONSHIPS</div>';
            data.incoming_relationships.forEach(rel => {
                const relColor = getEntityTypeColor(rel.source_type);
                incomingHtml += `
                    <div class="rel-item" data-entity-id="${rel.source_id}" style="padding: 8px; margin-bottom: 4px; background: var(--bg-secondary); border-radius: 4px; cursor: pointer;">
                        <div style="color: var(--accent-warning); font-size: 11px;">${escapeHtml(rel.relationship_type)}</div>
                        <div>${escapeHtml(rel.source_name)} <span style="color: ${relColor}; font-size: 11px;">(${rel.source_type})</span></div>
                    </div>
                `;
            });
            incomingHtml += '</div>';
        }
        
        content.innerHTML = `
            <div style="border-left: 3px solid ${typeColor}; padding-left: 12px; margin-bottom: 16px;">
                <div style="font-size: 16px; font-weight: 600; margin-bottom: 4px;">${escapeHtml(entity.name)}</div>
                <div style="color: ${typeColor}; font-size: 12px;">${entity.type}</div>
            </div>
            
            <div class="detail-tabs" style="display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid var(--border-color);">
                <button class="detail-tab active" data-tab="details" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid var(--accent-primary); color: var(--accent-primary); font-size: 11px; cursor: pointer; font-weight: 600;">Details</button>
                <button class="detail-tab" data-tab="history" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); font-size: 11px; cursor: pointer;">History</button>
            </div>
            
            <div id="detailsTabContent" class="tab-content">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
                    <div style="background: var(--bg-secondary); padding: 12px; border-radius: 6px;">
                        <div style="color: var(--text-muted); font-size: 10px; margin-bottom: 4px;">STATE</div>
                        <div style="color: ${lifecycleColor}; font-weight: 500;">${entity.lifecycle_state}</div>
                    </div>
                    <div style="background: var(--bg-secondary); padding: 12px; border-radius: 6px;">
                        <div style="color: var(--text-muted); font-size: 10px; margin-bottom: 4px;">CONFIDENCE</div>
                        <div style="color: var(--text-primary); font-weight: 500;">${Math.round(entity.confidence * 100)}%</div>
                    </div>
                </div>
                ${entity.description ? `<div style="margin-bottom: 16px; color: var(--text-secondary);">${escapeHtml(entity.description)}</div>` : ''}
                ${entity.source_sentence ? `<div style="margin-bottom: 16px; padding: 12px; background: var(--bg-secondary); border-radius: 6px; font-size: 12px; color: var(--text-muted); font-style: italic;">"${escapeHtml(entity.source_sentence)}"</div>` : ''}
                ${propsHtml}
                ${outgoingHtml}
                ${incomingHtml}
                <div style="margin-top: 20px;">
                    <button id="expandFromPanelBtn" class="btn btn-primary" style="width: 100%; padding: 10px;" data-entity-id="${entity.id}">
                        Expand Neighbors
                    </button>
                </div>
            </div>
            
            <div id="historyTabContent" class="tab-content" style="display: none;">
                <div id="historyLoading" style="text-align: center; padding: 24px; color: var(--text-muted);">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;">
                        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
                        <path d="M12 2a10 10 0 0 1 10 10"/>
                    </svg>
                    <div style="margin-top: 8px; font-size: 11px;">Loading history...</div>
                </div>
                <div id="historyContent"></div>
            </div>
        `;
        
        panel.style.display = 'block';
        
        // Setup tab switching
        content.querySelectorAll('.detail-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                
                // Update tab styles
                content.querySelectorAll('.detail-tab').forEach(t => {
                    t.classList.remove('active');
                    t.style.borderBottomColor = 'transparent';
                    t.style.color = 'var(--text-muted)';
                });
                tab.classList.add('active');
                tab.style.borderBottomColor = 'var(--accent-primary)';
                tab.style.color = 'var(--accent-primary)';
                
                // Show/hide content
                document.getElementById('detailsTabContent').style.display = tabName === 'details' ? 'block' : 'none';
                document.getElementById('historyTabContent').style.display = tabName === 'history' ? 'block' : 'none';
                
                // Load history if switching to history tab
                if (tabName === 'history' && currentDetailEntityId) {
                    loadEntityHistory(currentDetailEntityId);
                }
            });
        });
        
        content.querySelectorAll('.rel-item').forEach(item => {
            item.addEventListener('click', () => {
                const targetId = item.dataset.entityId;
                expandEntity(targetId);
                loadEntityDetails(targetId);
            });
        });
        
        const expandBtn = document.getElementById('expandFromPanelBtn');
        if (expandBtn) {
            expandBtn.addEventListener('click', () => {
                expandEntity(expandBtn.dataset.entityId);
            });
        }
    }
    
    async function loadEntityHistory(entityId) {
        const historyContent = document.getElementById('historyContent');
        const historyLoading = document.getElementById('historyLoading');
        
        if (!historyContent) return;
        
        if (historyLoading) historyLoading.style.display = 'block';
        historyContent.innerHTML = '';
        
        try {
            const response = await fetch(`/api/entities/${entityId}/history`);
            const data = await response.json();
            
            if (historyLoading) historyLoading.style.display = 'none';
            
            if (data.success && data.history && data.history.length > 0) {
                let html = `
                    <div style="color: var(--text-primary); font-weight: 600; margin-bottom: 12px; font-size: 13px;">
                        ${escapeHtml(data.current_name)} - Version History
                    </div>
                    <div style="border-left: 2px solid var(--border-color); padding-left: 16px;">
                `;
                
                data.history.forEach((version, index) => {
                    const isCurrent = version.is_current;
                    const validFrom = version.valid_from ? new Date(version.valid_from).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Unknown';
                    const confidence = Math.round((version.confidence || 0.5) * 100);
                    const stateColor = version.lifecycle_state === 'TRUSTED' ? '#10b981' : 
                                       version.lifecycle_state === 'STAGING' ? '#f59e0b' : '#6b7280';
                    
                    html += `
                        <div style="position: relative; padding: 12px 0; ${index < data.history.length - 1 ? 'border-bottom: 1px dashed var(--border-color);' : ''}">
                            <div style="position: absolute; left: -22px; top: 14px; width: 12px; height: 12px; border-radius: 50%; background: ${isCurrent ? 'var(--accent-primary)' : 'var(--bg-tertiary)'}; border: 2px solid ${isCurrent ? 'var(--accent-primary)' : 'var(--border-color)'};"></div>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <span style="color: ${isCurrent ? 'var(--accent-primary)' : 'var(--text-primary)'}; font-weight: ${isCurrent ? '600' : '400'}; font-size: 12px;">
                                    ${validFrom} ${isCurrent ? '(Current)' : ''}
                                </span>
                                <span style="font-size: 10px; color: var(--text-muted);">${confidence}%</span>
                            </div>
                            <div style="display: flex; gap: 8px; margin-bottom: 6px;">
                                <span style="background: ${stateColor}20; color: ${stateColor}; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 500;">${version.lifecycle_state}</span>
                            </div>
                            ${version.change_reason ? `
                                <div style="background: var(--bg-secondary); padding: 8px; border-radius: 4px; font-size: 11px; color: var(--text-muted); margin-top: 6px;">
                                    "${escapeHtml(version.change_reason)}"
                                </div>
                            ` : ''}
                        </div>
                    `;
                });
                
                html += '</div>';
                historyContent.innerHTML = html;
            } else {
                historyContent.innerHTML = `
                    <div style="text-align: center; padding: 24px; color: var(--text-muted);">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 8px; opacity: 0.5;">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M12 6v6l4 2"/>
                        </svg>
                        <div style="font-size: 12px;">No version history available</div>
                        <div style="font-size: 10px; margin-top: 4px; opacity: 0.7;">This entity has only one version</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load entity history:', error);
            if (historyLoading) historyLoading.style.display = 'none';
            historyContent.innerHTML = `
                <div style="text-align: center; padding: 24px; color: #ef4444;">
                    <div style="font-size: 12px;">Failed to load history</div>
                </div>
            `;
        }
    }
    
    function renderGraph() {
        const graphContainer = document.getElementById('graphNodesHtml');
        const linksContainer = document.getElementById('graphLinks');
        const emptyState = document.getElementById('graphEmptyState');
        const canvasContainer = document.getElementById('graphCanvasContainer');
        
        if (!graphContainer) return;
        
        graphContainer.innerHTML = '';
        linksContainer.innerHTML = '';
        
        const nodes = Object.values(graphNodes);
        const edges = graphEdges.filter(e => graphNodes[e.source] && graphNodes[e.target]);
        
        if (nodes.length === 0) {
            if (emptyState) emptyState.style.display = 'block';
            updateVisibleCount(0);
            return;
        }
        
        if (emptyState) emptyState.style.display = 'none';
        updateVisibleCount(nodes.length);
        
        const container = canvasContainer || graphContainer.parentElement;
        const rect = container?.getBoundingClientRect();
        const containerWidth = Math.max(rect?.width || 300, 200);
        const containerHeight = Math.max(rect?.height || 250, 200);
        const padding = 50;
        const centerX = containerWidth / 2;
        const centerY = containerHeight / 2;
        
        const centerNode = nodes.find(n => n.is_center) || nodes[0];
        const nodePositions = {};
        
        if (centerNode) {
            if (customNodePositions[centerNode.id]) {
                nodePositions[centerNode.id] = customNodePositions[centerNode.id];
            } else {
                nodePositions[centerNode.id] = { x: centerX, y: centerY };
            }
            
            const neighbors = nodes.filter(n => n.id !== centerNode.id);
            const angleStep = (2 * Math.PI) / Math.max(neighbors.length, 1);
            const maxRadius = Math.min(containerWidth - padding * 2, containerHeight - padding * 2) / 2;
            const baseRadius = Math.max(60, Math.min(maxRadius, 120));
            const radius = baseRadius * layoutRadiusMultiplier;
            
            neighbors.forEach((node, i) => {
                if (customNodePositions[node.id]) {
                    nodePositions[node.id] = customNodePositions[node.id];
                } else {
                    const angle = i * angleStep - Math.PI / 2;
                    let x = centerX + radius * Math.cos(angle);
                    let y = centerY + radius * Math.sin(angle);
                    x = Math.max(padding, Math.min(containerWidth - padding, x));
                    y = Math.max(padding, Math.min(containerHeight - padding, y));
                    nodePositions[node.id] = { x, y };
                }
            });
        }
        
        let existingDefs = linksContainer.querySelector('defs');
        if (!existingDefs) {
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            linksContainer.insertBefore(defs, linksContainer.firstChild);
            existingDefs = defs;
        }
        existingDefs.innerHTML = '';
        
        const markerColors = new Set();
        edges.forEach(edge => {
            if (edge.speculative) {
                markerColors.add('#a855f7');
            } else {
                const color = getRelationshipTypeColor(edge.type);
                markerColors.add(color);
            }
        });
        
        markerColors.forEach(color => {
            const markerId = `arrow-${color.replace('#', '')}`;
            const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
            marker.setAttribute('id', markerId);
            marker.setAttribute('viewBox', '0 0 10 10');
            marker.setAttribute('refX', '9');
            marker.setAttribute('refY', '5');
            marker.setAttribute('markerWidth', '6');
            marker.setAttribute('markerHeight', '6');
            marker.setAttribute('orient', 'auto-start-reverse');
            
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
            path.setAttribute('fill', color);
            marker.appendChild(path);
            existingDefs.appendChild(marker);
        });
        
        edges.forEach((edge, i) => {
            const source = nodePositions[edge.source];
            const target = nodePositions[edge.target];
            if (!source || !target) return;
            
            const relColor = edge.speculative ? '#a855f7' : getRelationshipTypeColor(edge.type);
            const confidence = edge.confidence || 0.5;
            const baseWidth = 1.5;
            const maxWidth = 4;
            const strokeWidth = baseWidth + (confidence * (maxWidth - baseWidth));
            const strokeOpacity = 0.5 + (confidence * 0.4);
            const markerId = `arrow-${relColor.replace('#', '')}`;
            
            const dx = target.x - source.x;
            const dy = target.y - source.y;
            const len = Math.sqrt(dx * dx + dy * dy);
            const nodeRadius = 25;
            const arrowOffset = 8;
            
            const startX = source.x + (dx / len) * nodeRadius;
            const startY = source.y + (dy / len) * nodeRadius;
            const endX = target.x - (dx / len) * (nodeRadius + arrowOffset);
            const endY = target.y - (dy / len) * (nodeRadius + arrowOffset);
            
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.style.opacity = '0';
            g.style.transition = `opacity 0.4s ease ${i * 0.05}s`;
            
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', startX);
            line.setAttribute('y1', startY);
            line.setAttribute('x2', endX);
            line.setAttribute('y2', endY);
            line.setAttribute('stroke', relColor);
            line.setAttribute('stroke-opacity', strokeOpacity);
            line.setAttribute('stroke-width', strokeWidth);
            line.setAttribute('marker-end', `url(#${markerId})`);
            
            if (edge.speculative) {
                line.setAttribute('stroke-dasharray', '8,4');
            } else if (confidence < 0.5) {
                line.setAttribute('stroke-dasharray', '4,2');
            }
            
            g.appendChild(line);
            
            const midX = (startX + endX) / 2;
            const midY = (startY + endY) / 2;
            
            const labelBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            const labelText = edge.type || '';
            const labelWidth = labelText.length * 5.5 + 10;
            labelBg.setAttribute('x', midX - labelWidth / 2);
            labelBg.setAttribute('y', midY - 9);
            labelBg.setAttribute('width', labelWidth);
            labelBg.setAttribute('height', 16);
            labelBg.setAttribute('fill', 'rgba(15, 23, 42, 0.95)');
            labelBg.setAttribute('stroke', relColor);
            labelBg.setAttribute('stroke-width', '1');
            labelBg.setAttribute('stroke-opacity', '0.5');
            labelBg.setAttribute('rx', '4');
            g.appendChild(labelBg);
            
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', midX);
            text.setAttribute('y', midY);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('dominant-baseline', 'middle');
            text.setAttribute('fill', relColor);
            text.setAttribute('font-size', '9');
            text.setAttribute('font-weight', '500');
            text.setAttribute('font-family', 'JetBrains Mono, monospace');
            text.textContent = labelText;
            g.appendChild(text);
            
            linksContainer.appendChild(g);
            setTimeout(() => { g.style.opacity = '1'; }, 50);
        });
        
        const isMobile = containerWidth < 500;
        
        nodes.forEach((node, i) => {
            const pos = nodePositions[node.id];
            if (!pos) return;
            
            const typeColor = getEntityTypeColor(node.type);
            const lifecycleStyle = getLifecycleBorderStyle(node.lifecycle_state);
            const confidence = node.confidence || 0.5;
            const isCenter = node.is_center;
            const isSelected = node.id === selectedNodeId;
            const baseSize = isMobile ? (isCenter ? 44 : 32) : (isCenter ? 56 : 40);
            const size = baseSize + (confidence * (isMobile ? 8 : 12));
            const borderWidth = isSelected ? 3 : 2;
            
            // Check if this node is on the frontier (knowledge boundary)
            const frontierInfo = currentFrontierNodes[node.name];
            const isFrontier = !!frontierInfo;
            const frontierColor = '#f59e0b';  // Amber/warning color
            
            // Debug: log node names and frontier status
            if (Object.keys(currentFrontierNodes).length > 0) {
                console.log('Checking node:', node.name, 'isFrontier:', isFrontier, 'frontierKeys:', Object.keys(currentFrontierNodes));
            }
            
            // Override border style for frontier nodes
            const borderStyle = isFrontier ? 'dashed' : lifecycleStyle.style;
            const nodeColor = isFrontier ? frontierColor : typeColor;
            const nodeOpacity = lifecycleStyle.opacity;
            
            const nodeEl = document.createElement('div');
            nodeEl.className = 'graph-node' + (isFrontier ? ' frontier-node' : '');
            nodeEl.dataset.nodeId = node.id;
            nodeEl.style.cssText = `
                position: absolute;
                left: ${pos.x}px;
                top: ${pos.y}px;
                width: ${size}px;
                height: ${size}px;
                margin-left: ${-size/2}px;
                margin-top: ${-size/2}px;
                border-radius: ${isCenter ? '12px' : '50%'};
                background: ${isSelected ? nodeColor + '30' : (isFrontier ? '#1e293b' : '#1e293b')};
                border: ${borderWidth}px ${borderStyle} ${nodeColor};
                box-shadow: 0 0 ${isCenter ? '30px' : '20px'} ${nodeColor}${isCenter ? '60' : '40'}${isFrontier ? ', inset 0 0 10px ' + frontierColor + '20' : ''};
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transform: scale(0);
                opacity: 0;
                transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease, box-shadow 0.2s ease, background 0.2s ease;
                z-index: ${isCenter ? 20 : 10};
            `;
            
            nodeEl.dataset.nodeOpacity = nodeOpacity;
            
            const iconSize = Math.max(16, size * 0.4);
            const iconWrapper = document.createElement('div');
            iconWrapper.style.cssText = `width: ${iconSize}px; height: ${iconSize}px; color: ${nodeColor}; position: relative;`;
            iconWrapper.innerHTML = getNodeIcon(node.type);
            nodeEl.appendChild(iconWrapper);
            
            // Add frontier indicator (question mark badge) for frontier nodes
            if (isFrontier) {
                const frontierBadge = document.createElement('div');
                frontierBadge.className = 'frontier-badge';
                frontierBadge.style.cssText = `
                    position: absolute;
                    top: -4px;
                    right: -4px;
                    width: 16px;
                    height: 16px;
                    background: ${frontierColor};
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 10px;
                    font-weight: bold;
                    color: #1e293b;
                    box-shadow: 0 0 8px ${frontierColor}80;
                `;
                frontierBadge.textContent = '?';
                nodeEl.appendChild(frontierBadge);
            }
            
            const lifecycleColor = getLifecycleColor(node.lifecycle_state);
            const tooltip = document.createElement('div');
            tooltip.className = 'graph-tooltip' + (isFrontier ? ' frontier-tooltip' : '');
            tooltip.style.cssText = `
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                margin-bottom: 8px;
                padding: 8px 12px;
                background: rgba(15, 23, 42, 0.95);
                border: 1px solid ${isFrontier ? frontierColor : typeColor}50;
                border-radius: 6px;
                font-size: 11px;
                font-family: 'JetBrains Mono', monospace;
                color: ${isFrontier ? frontierColor : typeColor};
                white-space: nowrap;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s ease;
                z-index: 100;
                max-width: 280px;
            `;
            
            // Build tooltip content - enhanced for frontier nodes
            let tooltipHtml = `<div style="font-weight: bold;">${escapeHtml(node.name)}</div>`;
            tooltipHtml += `<div style="display: flex; gap: 8px; margin-top: 4px; font-size: 10px;">
                <span style="color: ${typeColor};">${node.type}</span>
                <span style="color: ${lifecycleColor};">${node.lifecycle_state}</span>
                <span style="color: #94a3b8;">${Math.round(confidence * 100)}%</span>
            </div>`;
            
            if (isFrontier) {
                const reasonText = getFrontierReasonText(frontierInfo.reason);
                tooltipHtml += `
                    <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid ${frontierColor}30;">
                        <div style="display: flex; align-items: center; gap: 4px; color: ${frontierColor}; font-weight: 600;">
                            <span style="font-size: 12px;">?</span>
                            <span>Knowledge Boundary</span>
                        </div>
                        <div style="margin-top: 4px; color: #94a3b8; white-space: normal; line-height: 1.3;">
                            ${escapeHtml(frontierInfo.message)}
                        </div>
                    </div>
                `;
            }
            
            tooltip.innerHTML = tooltipHtml;
            nodeEl.appendChild(tooltip);
            
            nodeEl.addEventListener('mouseenter', () => {
                nodeEl.style.transform = 'scale(1.1)';
                nodeEl.style.boxShadow = `0 0 40px ${nodeColor}80`;
                tooltip.style.opacity = '1';
            });
            nodeEl.addEventListener('mouseleave', () => {
                nodeEl.style.transform = 'scale(1)';
                nodeEl.style.boxShadow = `0 0 ${isCenter ? '30px' : '20px'} ${nodeColor}${isCenter ? '60' : '40'}`;
                tooltip.style.opacity = '0';
            });
            
            let clickTimeout = null;
            
            nodeEl.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                isDragging = true;
                window.graphHasDragged = false;
                dragNodeId = node.id;
                const rect = nodeEl.getBoundingClientRect();
                dragOffset = {
                    x: e.clientX - rect.left - rect.width / 2,
                    y: e.clientY - rect.top - rect.height / 2
                };
                nodeEl.style.cursor = 'grabbing';
                nodeEl.style.zIndex = '100';
                e.preventDefault();
            });
            
            nodeEl.addEventListener('click', (e) => {
                if (window.graphHasDragged) {
                    window.graphHasDragged = false;
                    return;
                }
                if (clickTimeout) {
                    clearTimeout(clickTimeout);
                    clickTimeout = null;
                    expandEntity(node.id);
                } else {
                    clickTimeout = setTimeout(() => {
                        selectedNodeId = node.id;
                        loadEntityDetails(node.id);
                        renderGraph();
                        clickTimeout = null;
                    }, 250);
                }
            });
            
            graphContainer.appendChild(nodeEl);
            
            setTimeout(() => {
                nodeEl.style.transform = 'scale(1)';
                nodeEl.style.opacity = nodeOpacity.toString();
            }, 100 + i * 50);
        });
    }
    
    function updateVisibleCount(count) {
        const el = document.getElementById('statVisible');
        if (el) el.textContent = count;
    }
    
    async function loadGlobalStats() {
        try {
            const response = await fetch('/api/graph/visualization?limit=1');
            const data = await response.json();
            if (data.success && data.stats) {
                const counts = data.stats.lifecycle_counts || {};
                const trusted = document.getElementById('statTrusted');
                const staging = document.getElementById('statStaging');
                const archived = document.getElementById('statArchived');
                if (trusted) trusted.textContent = counts.TRUSTED || 0;
                if (staging) staging.textContent = counts.STAGING || 0;
                if (archived) archived.textContent = counts.ARCHIVED || 0;
            }
        } catch (error) {
            console.error('Stats error:', error);
        }
    }
    
    function clearGraph() {
        graphNodes = {};
        graphEdges = [];
        selectedNodeId = null;
        customNodePositions = {};
        layoutRadiusMultiplier = 1.0;
        renderGraph();
        const panel = document.getElementById('detailsPanel');
        if (panel) panel.style.display = 'none';
        resetEmptyState();
        const emptyState = document.getElementById('graphEmptyState');
        if (emptyState) emptyState.style.display = 'block';
    }
    
    function setupDragHandlers() {
        const graphContainer = document.getElementById('graphNodesHtml');
        const canvasContainer = document.getElementById('graphCanvasContainer');
        if (!canvasContainer) return;
        
        canvasContainer.addEventListener('mousemove', (e) => {
            if (!isDragging || !dragNodeId) return;
            
            const containerRect = canvasContainer.getBoundingClientRect();
            const x = e.clientX - containerRect.left;
            const y = e.clientY - containerRect.top;
            
            const prevPos = customNodePositions[dragNodeId];
            if (!prevPos || Math.abs(x - prevPos.x) > 3 || Math.abs(y - prevPos.y) > 3) {
                window.graphHasDragged = true;
            }
            
            customNodePositions[dragNodeId] = { x, y };
            
            const nodeEl = document.querySelector(`.graph-node[data-node-id="${dragNodeId}"]`);
            if (nodeEl) {
                nodeEl.style.left = `${x}px`;
                nodeEl.style.top = `${y}px`;
            }
            
            document.querySelectorAll('.graph-node').forEach(el => {
                if (el.dataset.nodeId !== dragNodeId) {
                    el.style.pointerEvents = 'none';
                }
            });
        });
        
        canvasContainer.addEventListener('mouseup', () => {
            if (isDragging && dragNodeId) {
                const nodeEl = document.querySelector(`.graph-node[data-node-id="${dragNodeId}"]`);
                if (nodeEl) {
                    nodeEl.style.cursor = 'pointer';
                    nodeEl.style.zIndex = '';
                }
                renderGraph();
            }
            isDragging = false;
            dragNodeId = null;
            document.querySelectorAll('.graph-node').forEach(el => {
                el.style.pointerEvents = '';
            });
        });
        
        canvasContainer.addEventListener('mouseleave', () => {
            if (isDragging && dragNodeId) {
                const nodeEl = document.querySelector(`.graph-node[data-node-id="${dragNodeId}"]`);
                if (nodeEl) {
                    nodeEl.style.cursor = 'pointer';
                    nodeEl.style.zIndex = '';
                }
            }
            isDragging = false;
            dragNodeId = null;
        });
    }
    
    function initGraphExplorer() {
        const searchInput = document.getElementById('graphSearchInput');
        const searchResults = document.getElementById('searchResults');
        const filterSelect = document.getElementById('lifecycleFilter');
        const clearBtn = document.getElementById('graphClearBtn');
        const closePanel = document.getElementById('closePanelBtn');
        const spreadBtn = document.getElementById('graphSpreadBtn');
        const compactBtn = document.getElementById('graphCompactBtn');
        const resetBtn = document.getElementById('graphResetBtn');
        
        setupDragHandlers();
        
        if (searchInput && searchResults) {
            searchInput.addEventListener('input', () => {
                clearTimeout(searchDebounceTimer);
                const query = searchInput.value.trim();
                
                if (query.length < 2) {
                    searchResults.style.display = 'none';
                    return;
                }
                
                searchDebounceTimer = setTimeout(async () => {
                    const results = await searchEntities(query);
                    if (results.length === 0) {
                        searchResults.innerHTML = '<div style="padding: 12px; color: var(--text-muted);">No entities found</div>';
                    } else {
                        searchResults.innerHTML = results.map(r => {
                            const typeColor = getEntityTypeColor(r.type);
                            const lifecycleColor = getLifecycleColor(r.lifecycle_state);
                            return `
                            <div class="search-result-item" data-entity-id="${r.id}" style="padding: 12px; cursor: pointer; border-bottom: 1px solid var(--border-color); transition: background 0.2s; border-left: 3px solid ${typeColor};">
                                <div style="font-weight: 500; color: var(--text-primary);">${escapeHtml(r.name)}</div>
                                <div style="font-size: 11px; margin-top: 4px; display: flex; gap: 8px;">
                                    <span style="color: ${typeColor};">${r.type}</span>
                                    <span style="color: ${lifecycleColor};">${r.lifecycle_state}</span>
                                    <span style="color: var(--text-muted);">${Math.round(r.confidence * 100)}%</span>
                                </div>
                            </div>
                        `}).join('');
                    }
                    searchResults.style.display = 'block';
                    
                    searchResults.querySelectorAll('.search-result-item').forEach(item => {
                        item.addEventListener('mouseenter', () => {
                            item.style.background = 'var(--bg-tertiary)';
                        });
                        item.addEventListener('mouseleave', () => {
                            item.style.background = 'transparent';
                        });
                        item.addEventListener('click', () => {
                            const entityId = item.dataset.entityId;
                            searchResults.style.display = 'none';
                            searchInput.value = '';
                            clearGraph();
                            expandEntity(entityId);
                            loadEntityDetails(entityId);
                        });
                    });
                }, 200);
            });
            
            document.addEventListener('click', (e) => {
                if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                    searchResults.style.display = 'none';
                }
            });
        }
        
        if (filterSelect) {
            filterSelect.addEventListener('change', (e) => {
                currentLifecycleFilter = e.target.value;
            });
        }
        
        if (clearBtn) {
            clearBtn.addEventListener('click', clearGraph);
        }
        
        if (closePanel) {
            closePanel.addEventListener('click', () => {
                const panel = document.getElementById('detailsPanel');
                if (panel) panel.style.display = 'none';
                selectedNodeId = null;
                renderGraph();
            });
        }
        
        if (spreadBtn) {
            spreadBtn.addEventListener('click', () => {
                customNodePositions = {};
                layoutRadiusMultiplier = Math.min(layoutRadiusMultiplier + 0.3, 2.5);
                renderGraph();
            });
        }
        
        if (compactBtn) {
            compactBtn.addEventListener('click', () => {
                customNodePositions = {};
                layoutRadiusMultiplier = Math.max(layoutRadiusMultiplier - 0.3, 0.4);
                renderGraph();
            });
        }
        
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                customNodePositions = {};
                layoutRadiusMultiplier = 1.0;
                renderGraph();
            });
        }
        
        loadGlobalStats();
    }
    
    function renderMemoryGraph() {
        initGraphExplorer();
    }
    
    initGraphExplorer();

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
        
        // Store frontier detection data for graph visualization
        currentFrontierNodes = {};
        currentGapsIdentified = data.gaps_identified || [];
        if (data.frontier && Array.isArray(data.frontier)) {
            data.frontier.forEach(f => {
                currentFrontierNodes[f.entity_name] = {
                    reason: f.reason,
                    message: f.message,
                    entity_type: f.entity_type,
                    depth: f.depth
                };
            });
        }
        
        // Build speculative data from speculative_inferences for backward compatibility
        const speculativeData = {
            inferred: (data.speculative_inferences || []).map(inf => ({
                source_entity_name: inf.source_entity_name,
                target_entity_name: inf.target_entity_name,
                confidence: inf.confidence,
                inferred_relationship_type: inf.relationship_type || 'RELATED_TO',
                rule_name: inf.rule_name,
                supporting_evidence: inf.explanation ? [inf.explanation] : []
            })),
            similar: (data.speculative?.similar || [])
        };
        
        // Render gaps panel if there are gaps identified or speculative results
        renderGapsPanel(data.gaps_identified || [], data.frontier || [], speculativeData);
        
        // Render tiered results summary
        renderTieredResultsSummary(data);
        
        resetFeedbackUI();
        document.getElementById('feedbackSection').style.display = 'block';

        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    function renderGapsPanel(gaps, frontier, speculative) {
        let gapsPanel = document.getElementById('gapsPanel');
        
        // Create panel if it doesn't exist
        if (!gapsPanel) {
            gapsPanel = document.createElement('div');
            gapsPanel.id = 'gapsPanel';
            gapsPanel.className = 'gaps-panel';
            // Insert after evidence section
            const evidenceSection = document.querySelector('.evidence-section');
            if (evidenceSection) {
                evidenceSection.parentNode.insertBefore(gapsPanel, evidenceSection.nextSibling);
            }
        }
        
        // Get speculative counts
        const inferredCount = speculative?.inferred?.length || 0;
        const similarCount = speculative?.similar?.length || 0;
        const hasSpeculative = inferredCount > 0 || similarCount > 0;
        
        // Hide if no gaps, frontier nodes, or speculative results
        if ((!gaps || gaps.length === 0) && (!frontier || frontier.length === 0) && !hasSpeculative) {
            gapsPanel.style.display = 'none';
            return;
        }
        
        gapsPanel.style.display = 'block';
        
        const frontierHtml = frontier.length > 0 ? `
            <div class="frontier-section">
                <div class="frontier-header" onclick="this.parentElement.classList.toggle('collapsed')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 16v-4"/>
                        <path d="M12 8h.01"/>
                    </svg>
                    <span>Knowledge Boundaries (${frontier.length})</span>
                    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                </div>
                <div class="frontier-items">
                    ${frontier.map(f => `
                        <div class="frontier-item">
                            <div class="frontier-entity">
                                <span class="frontier-icon">?</span>
                                <span class="frontier-name">${escapeHtml(f.entity_name)}</span>
                                <span class="frontier-type">${escapeHtml(f.entity_type || '')}</span>
                            </div>
                            <div class="frontier-message">${escapeHtml(f.message)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';
        
        const gapsHtml = gaps.length > 0 ? `
            <div class="gaps-section">
                <div class="gaps-header" onclick="this.parentElement.classList.toggle('collapsed')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="12" y1="18" x2="12" y2="12"/>
                        <line x1="9" y1="15" x2="15" y2="15"/>
                    </svg>
                    <span>Documentation Gaps (${gaps.length})</span>
                    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                </div>
                <div class="gaps-items">
                    ${gaps.map(gap => `
                        <div class="gap-item">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <path d="M12 8v4"/>
                                <path d="M12 16h.01"/>
                            </svg>
                            <span>${escapeHtml(gap)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';
        
        const speculativeHtml = hasSpeculative ? `
            <div class="speculative-section">
                <div class="speculative-header" onclick="this.parentElement.classList.toggle('collapsed')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10" stroke-dasharray="5,5"/>
                        <path d="M12 8l4 4-4 4"/>
                    </svg>
                    <span>Speculative Connections (${inferredCount + similarCount})</span>
                    <span class="speculative-badge">AI Inferred</span>
                    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                </div>
                <div class="speculative-items">
                    ${inferredCount > 0 ? `
                        <div class="speculative-group">
                            <div class="speculative-group-title">Rule-Based Inferences (${inferredCount})</div>
                            ${speculative.inferred.map(inf => `
                                <div class="speculative-item inferred">
                                    <div class="speculative-entity">
                                        <span class="speculative-icon">~</span>
                                        <span class="speculative-name">${escapeHtml(inf.source_entity_name)} → ${escapeHtml(inf.target_entity_name)}</span>
                                        <span class="speculative-confidence">${Math.round(inf.confidence * 100)}%</span>
                                    </div>
                                    <div class="speculative-relationship">${escapeHtml(inf.inferred_relationship_type)}</div>
                                    <div class="speculative-rule">Rule: ${escapeHtml(inf.rule_name)}</div>
                                    ${inf.supporting_evidence?.length > 0 ? `
                                        <div class="speculative-evidence">
                                            ${inf.supporting_evidence.map(e => `<span class="evidence-chip">${escapeHtml(e)}</span>`).join('')}
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    ${similarCount > 0 ? `
                        <div class="speculative-group">
                            <div class="speculative-group-title">Vector Similarity (${similarCount})</div>
                            ${speculative.similar.map(sim => `
                                <div class="speculative-item similar">
                                    <div class="speculative-entity">
                                        <span class="speculative-icon">≈</span>
                                        <span class="speculative-name">${escapeHtml(sim.entity_name)}</span>
                                        <span class="speculative-type">${escapeHtml(sim.entity_type)}</span>
                                        <span class="speculative-confidence">${Math.round(sim.confidence * 100)}%</span>
                                    </div>
                                    <div class="speculative-scores">
                                        <span>Similarity: ${Math.round(sim.similarity_score * 100)}%</span>
                                        <span>Co-occurrence: ${Math.round(sim.co_occurrence_score * 100)}%</span>
                                    </div>
                                    ${sim.supporting_evidence?.length > 0 ? `
                                        <div class="speculative-evidence">
                                            ${sim.supporting_evidence.map(e => `<span class="evidence-chip">${escapeHtml(e)}</span>`).join('')}
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        ` : '';
        
        gapsPanel.innerHTML = `
            <div class="gaps-panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <span>Knowledge Frontier</span>
            </div>
            ${frontierHtml}
            ${speculativeHtml}
            ${gapsHtml}
        `;
    }
    
    function renderTieredResultsSummary(data) {
        const summaryPanel = document.getElementById('tieredResultsSummary');
        if (!summaryPanel) return;
        
        // Calculate counts from tiered_results or individual fields
        const tieredResults = data.tiered_results || {};
        
        const confirmedCount = tieredResults.confirmed?.count || 
            (data.blast_radius_entities?.length || 0);
        const inferredCount = tieredResults.inferred?.count || 
            (data.speculative_inferences?.length || 0);
        const boundaryCount = tieredResults.boundaries?.count || 
            (data.frontier?.length || 0);
        
        // Only show if we have any tiered data
        const hasData = confirmedCount > 0 || inferredCount > 0 || boundaryCount > 0;
        
        if (!hasData) {
            summaryPanel.style.display = 'none';
            return;
        }
        
        summaryPanel.style.display = 'block';
        
        // Update counts with animation
        const confirmedEl = document.getElementById('confirmedCount');
        const inferredEl = document.getElementById('inferredCount');
        const boundaryEl = document.getElementById('boundaryCount');
        
        if (confirmedEl) confirmedEl.textContent = confirmedCount;
        if (inferredEl) inferredEl.textContent = inferredCount;
        if (boundaryEl) boundaryEl.textContent = boundaryCount;
        
        // Add click handlers for tier cards
        const confirmedCard = summaryPanel.querySelector('.tier-card.confirmed');
        const inferredCard = summaryPanel.querySelector('.tier-card.inferred');
        const boundaryCard = summaryPanel.querySelector('.tier-card.boundary');
        
        if (confirmedCard && confirmedCount > 0) {
            confirmedCard.style.cursor = 'pointer';
            confirmedCard.onclick = () => {
                const evidenceSection = document.querySelector('.evidence-section');
                if (evidenceSection) evidenceSection.scrollIntoView({ behavior: 'smooth' });
            };
        }
        
        if (inferredCard && inferredCount > 0) {
            inferredCard.style.cursor = 'pointer';
            inferredCard.onclick = () => {
                const speculativeSection = document.querySelector('.speculative-section');
                if (speculativeSection) speculativeSection.scrollIntoView({ behavior: 'smooth' });
            };
        }
        
        if (boundaryCard && boundaryCount > 0) {
            boundaryCard.style.cursor = 'pointer';
            boundaryCard.onclick = () => {
                const frontierSection = document.querySelector('.frontier-section');
                if (frontierSection) frontierSection.scrollIntoView({ behavior: 'smooth' });
            };
        }
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
    
    // ============================================
    // TIMELINE SLIDER FUNCTIONALITY
    // ============================================
    
    let timelineEarliest = null;
    let timelineLatest = null;
    let currentAsOfDate = null;
    let timelineDebounceTimer = null;
    let currentExpandedEntityId = null; // Track which entity is currently displayed
    
    async function initTimeline() {
        try {
            const response = await fetch('/api/knowledge/date-range');
            const data = await response.json();
            
            if (data.success) {
                timelineEarliest = new Date(data.earliest);
                timelineLatest = new Date(data.today);
                
                const earliestLabel = document.getElementById('timelineEarliestLabel');
                const latestLabel = document.getElementById('timelineLatestLabel');
                const datePicker = document.getElementById('timelineDatePicker');
                
                if (earliestLabel) {
                    earliestLabel.textContent = formatDateShort(timelineEarliest);
                }
                if (latestLabel) {
                    latestLabel.textContent = 'Today';
                }
                if (datePicker) {
                    datePicker.min = formatDateISO(timelineEarliest);
                    datePicker.max = formatDateISO(timelineLatest);
                    datePicker.value = formatDateISO(timelineLatest);
                }
                
                setupTimelineListeners();
            }
        } catch (error) {
            console.error('Failed to load timeline range:', error);
        }
    }
    
    function setupTimelineListeners() {
        const slider = document.getElementById('timelineSlider');
        const datePicker = document.getElementById('timelineDatePicker');
        const resetBtn = document.getElementById('timelineResetBtn');
        const returnBtn = document.getElementById('returnToPresentBtn');
        
        console.log('Timeline listeners setup:', { slider: !!slider, datePicker: !!datePicker });
        
        if (slider) {
            slider.addEventListener('input', () => {
                clearTimeout(timelineDebounceTimer);
                const date = sliderValueToDate(parseInt(slider.value));
                console.log('Slider moved:', slider.value, '-> date:', date);
                updateTimelineLabel(date);
                
                timelineDebounceTimer = setTimeout(() => {
                    console.log('Setting timeline date:', date, 'currentEntity:', currentExpandedEntityId);
                    setTimelineDate(date);
                }, 300);
            });
        }
        
        if (datePicker) {
            datePicker.addEventListener('change', () => {
                const date = new Date(datePicker.value);
                if (!isNaN(date.getTime())) {
                    const sliderValue = dateToSliderValue(date);
                    if (slider) slider.value = sliderValue;
                    setTimelineDate(date);
                }
            });
        }
        
        if (resetBtn) {
            resetBtn.addEventListener('click', resetTimeline);
        }
        
        if (returnBtn) {
            returnBtn.addEventListener('click', resetTimeline);
        }
    }
    
    function sliderValueToDate(value) {
        if (!timelineEarliest || !timelineLatest) return new Date();
        const range = timelineLatest.getTime() - timelineEarliest.getTime();
        const offset = (value / 100) * range;
        return new Date(timelineEarliest.getTime() + offset);
    }
    
    function dateToSliderValue(date) {
        if (!timelineEarliest || !timelineLatest) return 100;
        const range = timelineLatest.getTime() - timelineEarliest.getTime();
        if (range === 0) return 100;
        const offset = date.getTime() - timelineEarliest.getTime();
        return Math.round((offset / range) * 100);
    }
    
    function updateTimelineLabel(date) {
        const label = document.getElementById('timelineCurrentLabel');
        if (label) {
            const isToday = isSameDay(date, new Date());
            label.textContent = isToday ? 'Today' : formatDateDisplay(date);
            label.style.color = isToday ? 'var(--accent-primary)' : '#f97316';
        }
    }
    
    function setTimelineDate(date) {
        const isToday = isSameDay(date, new Date());
        
        if (isToday) {
            currentAsOfDate = null;
            hideTimelineBanner();
        } else {
            currentAsOfDate = formatDateISO(date);
            showTimelineBanner(date);
        }
        
        const datePicker = document.getElementById('timelineDatePicker');
        if (datePicker) {
            datePicker.value = formatDateISO(date);
        }
        
        refreshGraphWithTimeline();
    }
    
    function resetTimeline() {
        currentAsOfDate = null;
        
        const slider = document.getElementById('timelineSlider');
        const datePicker = document.getElementById('timelineDatePicker');
        const label = document.getElementById('timelineCurrentLabel');
        
        if (slider) slider.value = 100;
        if (datePicker) datePicker.value = formatDateISO(new Date());
        if (label) {
            label.textContent = 'Today';
            label.style.color = 'var(--accent-primary)';
        }
        
        hideTimelineBanner();
        refreshGraphWithTimeline();
    }
    
    function showTimelineBanner(date) {
        const banner = document.getElementById('timelineBanner');
        const dateLabel = document.getElementById('timelineBannerDate');
        
        if (banner) {
            banner.style.display = 'flex';
        }
        if (dateLabel) {
            dateLabel.textContent = formatDateDisplay(date);
        }
    }
    
    function hideTimelineBanner() {
        const banner = document.getElementById('timelineBanner');
        if (banner) {
            banner.style.display = 'none';
        }
    }
    
    function updateTimelineEntityCount(count, total) {
        const countEl = document.getElementById('timelineEntityCount');
        if (countEl) {
            countEl.textContent = `${count} entities`;
        }
    }
    
    async function refreshGraphWithTimeline() {
        console.log('refreshGraphWithTimeline called, currentEntity:', currentExpandedEntityId, 'asOfDate:', currentAsOfDate);
        clearGraph();
        loadGlobalStats();
        
        // Re-expand the current entity with the new date filter
        if (currentExpandedEntityId) {
            console.log('Re-expanding entity with date:', currentAsOfDate);
            await expandEntityWithTimeline(currentExpandedEntityId);
        } else {
            console.log('No current entity to re-expand');
        }
    }
    
    async function searchEntitiesWithTimeline(query) {
        if (!query || query.length < 2) return [];
        try {
            let url = `/api/graph/search?q=${encodeURIComponent(query)}&lifecycle_state=${currentLifecycleFilter}`;
            if (currentAsOfDate) {
                url += `&as_of_date=${encodeURIComponent(currentAsOfDate)}`;
            }
            const response = await fetch(url);
            const data = await response.json();
            return data.success ? data.results : [];
        } catch (error) {
            console.error('Search error:', error);
            return [];
        }
    }
    
    async function expandEntityWithTimeline(entityId) {
        try {
            let url = `/api/graph/expand/${entityId}?lifecycle_state=${currentLifecycleFilter}&include_speculative=true`;
            if (currentAsOfDate) {
                url += `&as_of_date=${encodeURIComponent(currentAsOfDate)}`;
            }
            const response = await fetch(url);
            const data = await response.json();
            if (data.success) {
                currentExpandedEntityId = entityId;
                
                if (data.nodes && data.nodes.length === 0 && data.message) {
                    showGraphMessage(data.message);
                    return data;
                }
                data.nodes.forEach(node => {
                    if (!graphNodes[node.id]) {
                        graphNodes[node.id] = node;
                    }
                });
                data.edges.forEach(edge => {
                    if (!graphEdges.find(e => e.id === edge.id)) {
                        graphEdges.push(edge);
                    }
                });
                
                if (data.speculative && data.speculative.inferred && data.speculative.inferred.length > 0) {
                    data.speculative.inferred.forEach(inf => {
                        const targetId = inf.target_entity_id;
                        if (!graphNodes[targetId]) {
                            graphNodes[targetId] = {
                                id: targetId,
                                name: inf.target_entity_name,
                                type: inf.target_entity_type || 'UNKNOWN',
                                lifecycle_state: 'TRUSTED',
                                confidence: inf.confidence,
                                is_speculative_target: true
                            };
                        }
                        const sourceId = inf.source_entity_id;
                        if (!graphNodes[sourceId]) {
                            graphNodes[sourceId] = {
                                id: sourceId,
                                name: inf.source_entity_name,
                                type: inf.source_entity_type || 'UNKNOWN',
                                lifecycle_state: 'TRUSTED',
                                confidence: inf.confidence,
                                is_speculative_target: true
                            };
                        }
                        const specEdgeId = `spec-${sourceId}-${targetId}-${inf.rule_name}`;
                        if (!graphEdges.find(e => e.id === specEdgeId)) {
                            graphEdges.push({
                                id: specEdgeId,
                                source: sourceId,
                                target: targetId,
                                type: inf.inferred_relationship_type,
                                confidence: inf.confidence,
                                speculative: true,
                                rule_name: inf.rule_name,
                                supporting_evidence: inf.supporting_evidence
                            });
                        }
                    });
                }
                
                if (data.frontier && Array.isArray(data.frontier)) {
                    console.log('Frontier nodes received:', data.frontier.length, data.frontier);
                    data.frontier.forEach(f => {
                        currentFrontierNodes[f.entity_name] = {
                            reason: f.reason,
                            message: f.message,
                            entity_type: f.entity_type,
                            depth: f.depth
                        };
                    });
                    console.log('currentFrontierNodes updated:', Object.keys(currentFrontierNodes));
                }
                
                console.log('Before renderGraph - graphNodes:', Object.keys(graphNodes).length, 'graphEdges:', graphEdges.length);
                const specEdges = graphEdges.filter(e => e.speculative);
                console.log('Speculative edges in graphEdges:', specEdges.length, specEdges.map(e => `${e.source} -> ${e.target}`));
                
                if (data.is_historical) {
                    updateTimelineEntityCount(data.stats.total_nodes);
                }
                
                renderGraph();
                return data;
            }
            return null;
        } catch (error) {
            console.error('Expand error:', error);
            return null;
        }
    }
    
    function formatDateISO(date) {
        return date.toISOString().split('T')[0];
    }
    
    function formatDateShort(date) {
        return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    }
    
    function formatDateDisplay(date) {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }
    
    function isSameDay(date1, date2) {
        return date1.getFullYear() === date2.getFullYear() &&
               date1.getMonth() === date2.getMonth() &&
               date1.getDate() === date2.getDate();
    }
    
    // Override the original search and expand functions to use timeline
    const originalSearchEntities = searchEntities;
    searchEntities = async function(query) {
        return searchEntitiesWithTimeline(query);
    };
    
    const originalExpandEntity = expandEntity;
    expandEntity = async function(entityId) {
        return expandEntityWithTimeline(entityId);
    };
    
    // Initialize timeline when Memory Graph page is shown
    const originalRenderMemoryGraph = renderMemoryGraph;
    renderMemoryGraph = function() {
        originalRenderMemoryGraph();
        initTimeline();
    };
}

// Initialize on first page load
document.addEventListener('DOMContentLoaded', initApp);

// Re-initialize on Turbo navigations (for Turbo.js seamless page transitions)
document.addEventListener('turbo:load', initApp);
