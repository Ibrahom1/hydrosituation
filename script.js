// Modern Professional Hydrological Dashboard
let dashboardData = {};
let isRefreshing = false;
let chartsInstances = {};
let currentView = { dams: 'chart', headworks: 'chart' };

// Chart.js global configuration
Chart.defaults.font.family = 'Poppins, Inter, Segoe UI, Roboto, sans-serif';
Chart.defaults.font.size = 14;
Chart.defaults.color = '#22223b';
Chart.defaults.plugins.legend.labels.color = '#22223b';
Chart.defaults.plugins.title.color = '#a21caf';
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(37,99,235,0.95)';
Chart.defaults.plugins.tooltip.titleColor = '#fff';
Chart.defaults.plugins.tooltip.bodyColor = '#fff';
Chart.defaults.plugins.tooltip.borderColor = '#a21caf';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.layout = Chart.defaults.layout || {};
Chart.defaults.layout.padding = { left: 8, right: 8, top: 8, bottom: 8 };
Chart.defaults.elements.line.borderWidth = 3;
Chart.defaults.elements.point.radius = 5;
Chart.defaults.elements.point.backgroundColor = '#ec4899';
Chart.defaults.elements.point.borderColor = '#fff';

// Professional color palette
const colors = {
    primary: '#2563eb',
    secondary: '#06b6d4',
    success: '#10b981',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#3b82f6',
    gray: {
        100: '#f3f4f6',
        200: '#e5e7eb',
        300: '#d1d5db',
        400: '#9ca3af',
        500: '#6b7280',
        600: '#4b5563'
    }
};

// Utility Functions
function formatValue(value) {
    if (typeof value === 'string') {
        value = value.replace(/,/g, '');
    }
    const num = parseFloat(value);
    return isNaN(num) ? 'N/A' : num.toLocaleString('en-US');
}

async function fetchHistoricalSeries(name, hours = 24) {
    try {
        const res = await fetch(`http://localhost:5000/api/history?name=${encodeURIComponent(name)}&hours=${hours}`);
        if (!res.ok) throw new Error('history status');
        const data = await res.json();
        if (!data.success) throw new Error('history payload');
        if (data.inflow.length === 0 && data.outflow.length === 0) return null; // first run fallback
        return {
            inflow: data.inflow.map(p => ({ x: new Date(p.x), y: p.y })),
            outflow: data.outflow.map(p => ({ x: new Date(p.x), y: p.y }))
        };
    } catch (e) {
        console.warn('History fetch failed for', name, e);
        return null;
    }
}

function generateSyntheticSeries(currentValue, hours = 24) {
    const data = [];
    const now = new Date();
    const value = parseFloat(String(currentValue).replace(/,/g, '')) || 50000;
    
    for (let i = hours; i >= 0; i--) {
        const time = new Date(now.getTime() - (i * 60 * 60 * 1000));
        const variation = (Math.random() - 0.5) * 0.15 * value;
        data.push({
            x: time,
            y: Math.max(0, value + variation)
        });
    }
    
    return data;
}

function getParameterUnit(key) {
    const units = {
        'discharge': 'cusecs',
        'pond_level': 'ft',
        'water_level': 'ft',
        'rainfall': 'mm',
        'temperature': '°C',
        'flow': 'cusecs',
        'level': 'ft',
        'inflow': 'cusecs',
        'outflow': 'cusecs'
    };
    
    for (const [param, unit] of Object.entries(units)) {
        if (key.toLowerCase().includes(param)) {
            return unit;
        }
    }
    return '';
}

function getStatusClass(key, value) {
    const numValue = parseFloat(String(value).replace(/,/g, ''));
    if (isNaN(numValue)) return 'normal';
    
    if (key.includes('level') || key.includes('discharge')) {
        if (numValue > 100000) return 'high';
        if (numValue < 10000) return 'low';
        return 'normal';
    }
    
    return 'normal';
}

// Generate historical data for charts
function generateHistoricalData(currentValue, hours = 24) {
    const data = [];
    const now = new Date();
    const value = parseFloat(String(currentValue).replace(/,/g, '')) || 50000;
    
    for (let i = hours; i >= 0; i--) {
        const time = new Date(now.getTime() - (i * 60 * 60 * 1000));
        const variation = (Math.random() - 0.5) * 0.15 * value;
        data.push({
            x: time,
            y: Math.max(0, value + variation)
        });
    }
    
    return data;
}
// Create professional chart
function createChart(containerId, name, parameter, value, unit) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    
    const canvas = document.createElement('canvas');
    canvas.className = 'chart-canvas';
    container.appendChild(canvas);
    
    const historicalData = generateHistoricalData(value);
    const color = parameter.includes('inflow') ? colors.primary : 
                 parameter.includes('outflow') ? colors.secondary :
                 parameter.includes('level') ? colors.info : colors.success;
    
    const chart = new Chart(canvas, {
        type: 'line',
        data: {
            datasets: [{
                label: `${name} ${parameter}`,
                data: historicalData,
                borderColor: color,
                backgroundColor: color + '20',
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.9)',
                    titleColor: '#f9fafb',
                    bodyColor: '#f9fafb',
                    borderColor: color,
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.y.toLocaleString()} ${unit}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        displayFormats: {
                            hour: 'HH:mm'
                        }
                    },
                    grid: {
                        color: colors.gray[200],
                        drawTicks: false
                    },
                    border: {
                        display: false
                    },
                    ticks: {
                        maxTicksLimit: 6,
                        color: colors.gray[500]
                    }
                },
                y: {
                    grid: {
                        color: colors.gray[200],
                        drawTicks: false
                    },
                    border: {
                        display: false
                    },
                    ticks: {
                        color: colors.gray[500],
                        callback: function(value) {
                            return value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
    
    return chart;
}

// Toggle view between chart and table
function toggleView(section, view) {
    currentView[section] = view;
    
    // Update toggle buttons
    const toggles = document.querySelectorAll(`[data-section="${section}"]`);
    toggles.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    
    // Re-render the section
    if (section === 'dams') {
        displayDams();
    } else {
        displayHeadworks();
    }
}

// Create charts grid HTML with single chart per item showing inflow/outflow
function createChartsGrid(data, sectionType) {
    if (!data || data.length === 0) {
        return `
            <div class="loading-placeholder">
                <i class="fas fa-chart-line"></i>
                <p>No ${sectionType} data available for charting</p>
            </div>
        `;
    }
    const chartsHtml = data.map((item, itemIndex) => {
        const chartId = `chart_${sectionType}_${itemIndex}`;
        const inflowValue = item.inflow_discharge || 0;
        const outflowValue = item.outflow_discharge || 0;
        const recordingTime = item.recording_time || 'N/A';
        const status = item.status || 'NORMAL';
        
        // Handle inflow trend
        const inflowTrend = (item.inflow_trend || '').toLowerCase();
        const inflowTrendClass = inflowTrend.includes('rise') || inflowTrend.includes('rising') ? 'trend-rising' : 
                               inflowTrend.includes('fall') || inflowTrend.includes('falling') ? 'trend-falling' : 'trend-steady';
        const inflowTrendLabel = item.inflow_trend || 'N/A';
        
        // Handle outflow trend  
        const outflowTrend = (item.outflow_trend || '').toLowerCase();
        const outflowTrendClass = outflowTrend.includes('rise') || outflowTrend.includes('rising') ? 'trend-rising' : 
                                outflowTrend.includes('fall') || outflowTrend.includes('falling') ? 'trend-falling' : 'trend-steady';
        const outflowTrendLabel = item.outflow_trend || 'N/A';
        
        const formattedInflow = formatValue(inflowValue);
        const formattedOutflow = formatValue(outflowValue);
        return `
        <div class="chart-item">
            <div class="chart-header">
                <h6 class="chart-title">${item.name}</h6>
                <span class="chart-status ${status.toLowerCase()}">${status}</span>
            </div>
            <div class="chart-canvas" id="${chartId}"></div>
            <div class="chart-info">
                <div class="flow-values">
                    <div class="flow-item inflow">
                        <div class="flow-label"><i class="fas fa-arrow-down"></i>Inflow</div>
                        <div class="flow-value">${formattedInflow} cusecs</div>
                        <div class="flow-trend ${inflowTrendClass}"><i class="fas fa-chart-line"></i>${inflowTrendLabel}</div>
                    </div>
                    <div class="flow-item outflow">
                        <div class="flow-label"><i class="fas fa-arrow-up"></i>Outflow</div>
                        <div class="flow-value">${formattedOutflow} cusecs</div>
                        <div class="flow-trend ${outflowTrendClass}"><i class="fas fa-chart-line"></i>${outflowTrendLabel}</div>
                    </div>
                </div>
                <div class="recording-info">
                    <div class="recording-time"><i class="fas fa-clock"></i><span>Recorded: ${recordingTime}</span></div>
                </div>
            </div>
        </div>`;
    }).join('');
    return `<div class="charts-container">${chartsHtml}</div>`;
}

// Create data table HTML
function createDataTable(data, sectionType) {
    if (!data || data.length === 0) {
        return `
            <div class="loading-placeholder">
                <i class="fas fa-table"></i>
                <p>No ${sectionType} data available</p>
            </div>
        `;
    }
    
    const allParams = new Set();
    data.forEach(item => {
        Object.keys(item).forEach(key => {
            if (!['name', 'location', 'id', 'lat', 'long', 'inflow_time', 'outflow_time', 'inflow_trend', 'outflow_trend'].includes(key)) {
                const value = item[key];
                if (value && value !== '' && !isNaN(parseFloat(String(value).replace(/,/g, '')))) {
                    allParams.add(key);
                }
            }
        });
    });
    
    const headers = ['Name', ...Array.from(allParams).map(param => 
        param.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    )];
    
    const rows = data.map(item => {
        const cells = [
            item.name || 'N/A',
            ...Array.from(allParams).map(param => {
                const value = formatValue(item[param]);
                const unit = getParameterUnit(param);
                const status = getStatusClass(param, value);
                return `<span class="data-value trend-${status === 'normal' ? 'steady' : status === 'high' ? 'rising' : 'falling'}">${value} ${unit}</span>`;
            })
        ];
        
        return `<tr>${cells.map(cell => `<td>${cell}</td>`).join('')}</tr>`;
    }).join('');
    
    return `
        <div class="data-table">
            <table>
                <thead>
                    <tr>${headers.map(header => `<th>${header}</th>`).join('')}</tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    `;
}

// Display dams data
function displayDams() {
    const container = document.getElementById('dams-content');
    if (!container) return;
    
    const dams = dashboardData.dams || [];
    const view = currentView.dams;
    
    // Update count
    const countElement = document.getElementById('total-dams');
    if (countElement) {
        countElement.textContent = dams.length;
    }
    
    if (view === 'chart') {
        container.innerHTML = createChartsGrid(dams, 'dams');
        setTimeout(() => createAllCharts(dams, 'dams'), 100);
    } else {
        container.innerHTML = createDataTable(dams, 'dams');
    }
}

// Display headworks data
function displayHeadworks() {
    const container = document.getElementById('headworks-content');
    if (!container) return;
    const headworks = dashboardData.headworks || [];
    const groups = dashboardData.headworksByRiver || {};
    const view = currentView.headworks;
    const countElement = document.getElementById('total-headworks');
    if (countElement) countElement.textContent = headworks.length;
    if (view === 'chart') {
        let html = '';
        // Sort rivers with OTHER at the bottom
        const sortedRiversForDisplay = Object.keys(groups).sort((a, b) => {
            if (a === 'OTHER') return 1;
            if (b === 'OTHER') return -1;
            return a.localeCompare(b);
        });
        
        sortedRiversForDisplay.forEach(river => {
            const list = groups[river];
            html += `<div class="river-section"><div class="river-header"><h4 class="river-title" style="color: black;">${river} River</h4><span class="river-count">${list.length}</span></div><div class="charts-container">`;
            list.forEach((item, idx) => {
                const chartId = `chart_headworks_${river}_${idx}`;
                const inflowValue = formatValue(item.inflow_discharge || 0);
                const outflowValue = formatValue(item.outflow_discharge || 0);
                const status = item.status || 'NORMAL';
                
                // Handle inflow trend
                const inflowTrend = (item.inflow_trend || '').toLowerCase();
                const inflowTrendClass = inflowTrend.includes('rise') || inflowTrend.includes('rising') ? 'trend-rising' : 
                                       inflowTrend.includes('fall') || inflowTrend.includes('falling') ? 'trend-falling' : 'trend-steady';
                const inflowTrendLabel = item.inflow_trend || 'N/A';
                
                // Handle outflow trend  
                const outflowTrend = (item.outflow_trend || '').toLowerCase();
                const outflowTrendClass = outflowTrend.includes('rise') || outflowTrend.includes('rising') ? 'trend-rising' : 
                                        outflowTrend.includes('fall') || outflowTrend.includes('falling') ? 'trend-falling' : 'trend-steady';
                const outflowTrendLabel = item.outflow_trend || 'N/A';
                
                html += `<div class="chart-item"><div class="chart-header"><h6 class="chart-title">${item.name}</h6><span class="chart-status ${status.toLowerCase()}">${status}</span></div><div class="chart-canvas" id="${chartId}"></div><div class="chart-info"><div class="flow-values"><div class="flow-item inflow"><div class="flow-label"><i class="fas fa-arrow-down"></i>Inflow</div><div class="flow-value">${inflowValue} cusecs</div><div class="flow-trend ${inflowTrendClass}"><i class="fas fa-chart-line"></i>${inflowTrendLabel}</div></div><div class="flow-item outflow"><div class="flow-label"><i class="fas fa-arrow-up"></i>Outflow</div><div class="flow-value">${outflowValue} cusecs</div><div class="flow-trend ${outflowTrendClass}"><i class="fas fa-chart-line"></i>${outflowTrendLabel}</div></div></div><div class="recording-info"><div class="recording-time"><i class="fas fa-clock"></i><span>Recorded: ${item.recording_time || 'N/A'}</span></div></div></div></div>`;
            });
            html += '</div></div>';
        });
        container.innerHTML = html;
        // Sort rivers with OTHER at the bottom for chart creation
        const sortedRiversForCharts = Object.keys(groups).sort((a, b) => {
            if (a === 'OTHER') return 1;
            if (b === 'OTHER') return -1;
            return a.localeCompare(b);
        });
        
        sortedRiversForCharts.forEach(river => {
            groups[river].forEach(async (item, idx) => {
                const chartId = `chart_headworks_${river}_${idx}`;
                const inflowValue = parseFloat(String(item.inflow_discharge || 0).replace(/,/g, ''));
                const outflowValue = parseFloat(String(item.outflow_discharge || 0).replace(/,/g, ''));
                const history = await fetchHistoricalSeries(item.name, 24);
                const inflowSeries = history?.inflow || generateSyntheticSeries(inflowValue);
                const outflowSeries = history?.outflow || generateSyntheticSeries(outflowValue);
                const chart = createInflowOutflowChart(chartId, item.name, inflowSeries, outflowSeries);
                if (chart) chartsInstances[chartId] = chart;
            });
        });
    } else {
        let html = '';
        // Sort rivers with OTHER at the bottom for table view
        const sortedRiversForTable = Object.keys(groups).sort((a, b) => {
            if (a === 'OTHER') return 1;
            if (b === 'OTHER') return -1;
            return a.localeCompare(b);
        });
        
        sortedRiversForTable.forEach(river => {
            html += `<div class="river-section"><div class="river-header"><h4 class="river-title" style="color: black;">${river} River</h4><span class="river-count">${groups[river].length}</span></div>`;
            html += createDataTable(groups[river], 'headworks');
            html += '</div>';
        });
        container.innerHTML = html;
    }
}

// Create all charts for a section
async function createAllCharts(data, sectionType) {
    for (let idx = 0; idx < data.length; idx++) {
        const item = data[idx];
        const chartId = `chart_${sectionType}_${idx}`;
        const inflowValue = parseFloat(String(item.inflow_discharge || 0).replace(/,/g, ''));
        const outflowValue = parseFloat(String(item.outflow_discharge || 0).replace(/,/g, ''));
        const history = await fetchHistoricalSeries(item.name, 24);
        const inflowSeries = history?.inflow || generateSyntheticSeries(inflowValue);
        const outflowSeries = history?.outflow || generateSyntheticSeries(outflowValue);
        const chart = createInflowOutflowChart(chartId, item.name, inflowSeries, outflowSeries);
        if (chart) chartsInstances[chartId] = chart;
    }
}

// Create inflow/outflow chart
function createInflowOutflowChart(containerId, name, inflowSeries, outflowSeries) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    
    const canvas = document.createElement('canvas');
    canvas.className = 'chart-canvas';
    container.appendChild(canvas);
    
    const inflowData = inflowSeries;
    const outflowData = outflowSeries;
    
    const chart = new Chart(canvas, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Inflow',
                data: inflowData,
                borderColor: colors.primary,
                backgroundColor: colors.primary + '20',
                fill: false,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2
            }, {
                label: 'Outflow',
                data: outflowData,
                borderColor: colors.secondary,
                backgroundColor: colors.secondary + '20',
                fill: false,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 15,
                        font: {
                            size: 11
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.9)',
                    titleColor: '#f9fafb',
                    bodyColor: '#f9fafb',
                    borderColor: colors.primary,
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} cusecs`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        displayFormats: {
                            hour: 'HH:mm'
                        }
                    },
                    grid: {
                        color: colors.gray[200],
                        drawTicks: false
                    },
                    border: {
                        display: false
                    },
                    ticks: {
                        maxTicksLimit: 6,
                        color: colors.gray[500],
                        font: {
                            size: 10
                        }
                    }
                },
                y: {
                    grid: {
                        color: colors.gray[200],
                        drawTicks: false
                    },
                    border: {
                        display: false
                    },
                    ticks: {
                        color: colors.gray[500],
                        font: {
                            size: 10
                        },
                        callback: function(value) {
                            return value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
    
    return chart;
}

// Update statistics overview
function updateStatistics() {
    // Only update the dam and headwork counts now
    const damsCount = (dashboardData.dams || []).length;
    const headworksCount = (dashboardData.headworks || []).length;
    
    document.getElementById('total-dams').textContent = damsCount;
    document.getElementById('total-headworks').textContent = headworksCount;
}

// Main refresh function
async function refreshAllData() {
    if (isRefreshing) return;
    
    isRefreshing = true;
    const refreshBtn = document.querySelector('.refresh-button');
    
    try {
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
            refreshBtn.disabled = true;
        }
        
        console.log('Starting data refresh...');
        
        // Destroy existing charts
        Object.values(chartsInstances).forEach(chart => chart.destroy());
        chartsInstances = {};
        
        // Fetch data
        const [damsResponse, headworksResponse] = await Promise.all([
            fetch('http://localhost:5000/api/ffd-dams'),
            fetch('http://localhost:5000/api/ffd-headworks')
        ]);
        
        if (!damsResponse.ok || !headworksResponse.ok) {
            throw new Error(`API Error: Dams ${damsResponse.status}, Headworks ${headworksResponse.status}`);
        }
        
        const damsData = await damsResponse.json();
        const headworksData = await headworksResponse.json();
        
        console.log('Fetched data:', { damsData, headworksData });
        
        // Update dashboard data
        dashboardData = {
            dams: damsData.dams || [],
            headworks: headworksData.headworks || [],
            headworksByRiver: headworksData.headworks_by_river || {},
            lastUpdated: new Date()
        };
        
        // Display data
        displayDams();
        displayHeadworks();
        updateStatistics();
        updateStatus(true);
        
        console.log('Dashboard updated successfully');
        
    } catch (error) {
        console.error('Error refreshing data:', error);
        updateStatus(false);
    } finally {
        isRefreshing = false;
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
            refreshBtn.disabled = false;
        }
    }
}

// Update connection status
function updateStatus(isOnline) {
    const statusDot = document.querySelector('.dot');
    const lastUpdate = document.getElementById('last-update');
    
    if (statusDot) {
        statusDot.className = isOnline ? 'dot online' : 'dot offline';
    }
    
    if (lastUpdate) {
        lastUpdate.textContent = new Date().toLocaleTimeString();
    }
}

// Auto-sync cloud data when dashboard loads
async function autoSyncCloudData() {
    try {
        console.log('🔄 Checking for cloud data updates...');
        const response = await fetch('http://localhost:5000/api/sync-cloud-data');
        
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                console.log('✅ Cloud data synced successfully:', result.timestamp);
                return true;
            } else {
                console.warn('⚠️ Cloud sync failed:', result.error);
            }
        }
    } catch (error) {
        console.warn('⚠️ Cloud sync unavailable, using local data:', error.message);
    }
    return false;
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Modern professional dashboard initializing...');
    
    // Try to sync cloud data first
    await autoSyncCloudData();
    
    // Add event listeners for toggle buttons
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('toggle-btn')) {
            const section = e.target.dataset.section;
            const view = e.target.dataset.view;
            if (section && view) {
                toggleView(section, view);
            }
        }
    });
    
    // Initial data load
    refreshAllData();
    
    // Auto-refresh every 5 minutes
    setInterval(refreshAllData, 5 * 60 * 1000);
    
    // Auto-sync cloud data every 30 minutes
    setInterval(autoSyncCloudData, 30 * 60 * 1000);
    
    console.log('Modern professional dashboard initialized successfully');
});
