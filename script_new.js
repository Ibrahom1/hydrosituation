// Modern Professional Hydrological Dashboard
let dashboardData = {};
let isRefreshing = false;
let chartsInstances = {};
let currentView = { dams: 'chart', headworks: 'chart' };

// Chart.js global configuration
Chart.defaults.font.family = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.color = '#6b7280';

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

// Create charts grid HTML
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
        const parameters = Object.entries(item)
            .filter(([key]) => !['name', 'location', 'id', 'lat', 'long', 'inflow_time', 'outflow_time', 'inflow_trend', 'outflow_trend'].includes(key))
            .filter(([key, value]) => value && value !== '' && !isNaN(parseFloat(String(value).replace(/,/g, ''))))
            .slice(0, 4);
        
        if (parameters.length === 0) {
            return `
                <div class="chart-item">
                    <div class="chart-header">
                        <h6 class="chart-title">${item.name}</h6>
                        <span class="chart-status normal">NO DATA</span>
                    </div>
                    <div class="loading-placeholder">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>No numeric data available</p>
                    </div>
                </div>
            `;
        }
        
        return parameters.map(([key, value], paramIndex) => {
            const chartId = `chart_${sectionType}_${itemIndex}_${paramIndex}`;
            const unit = getParameterUnit(key);
            const status = getStatusClass(key, value);
            const formattedValue = formatValue(value);
            const paramName = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            
            return `
                <div class="chart-item">
                    <div class="chart-header">
                        <h6 class="chart-title">${item.name} - ${paramName}</h6>
                        <span class="chart-status ${status}">${status.toUpperCase()}</span>
                    </div>
                    <div class="chart-canvas" id="${chartId}"></div>
                    <div class="chart-values">
                        <div class="value-item">
                            <div class="value-label">Current</div>
                            <div class="value-number">${formattedValue} ${unit}</div>
                        </div>
                        <div class="value-item">
                            <div class="value-label">Status</div>
                            <div class="value-number">${status}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
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
    document.getElementById('total-dams').textContent = dams.length;
    
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
    const view = currentView.headworks;
    
    // Update count
    document.getElementById('total-headworks').textContent = headworks.length;
    
    if (view === 'chart') {
        container.innerHTML = createChartsGrid(headworks, 'headworks');
        setTimeout(() => createAllCharts(headworks, 'headworks'), 100);
    } else {
        container.innerHTML = createDataTable(headworks, 'headworks');
    }
}

// Create all charts for a section
function createAllCharts(data, sectionType) {
    data.forEach((item, itemIndex) => {
        const parameters = Object.entries(item)
            .filter(([key]) => !['name', 'location', 'id', 'lat', 'long', 'inflow_time', 'outflow_time', 'inflow_trend', 'outflow_trend'].includes(key))
            .filter(([key, value]) => value && value !== '' && !isNaN(parseFloat(String(value).replace(/,/g, ''))))
            .slice(0, 4);
        
        parameters.forEach(([key, value], paramIndex) => {
            const chartId = `chart_${sectionType}_${itemIndex}_${paramIndex}`;
            const unit = getParameterUnit(key);
            const chart = createChart(chartId, item.name, key, value, unit);
            
            if (chart) {
                chartsInstances[chartId] = chart;
            }
        });
    });
}

// Update statistics overview
function updateStatistics() {
    const totalFlow = [...(dashboardData.dams || []), ...(dashboardData.headworks || [])]
        .reduce((sum, item) => {
            const inflow = parseFloat(String(item.inflow_discharge || 0).replace(/,/g, ''));
            const outflow = parseFloat(String(item.outflow_discharge || 0).replace(/,/g, ''));
            return sum + (isNaN(inflow) ? 0 : inflow) + (isNaN(outflow) ? 0 : outflow);
        }, 0);
    
    document.getElementById('total-flow').textContent = totalFlow.toLocaleString();
    document.getElementById('total-alerts').textContent = '0';
    
    // Update flow trend
    const flowTrend = document.getElementById('flow-trend');
    if (flowTrend) {
        flowTrend.className = 'stat-change positive';
        flowTrend.innerHTML = '<i class="fas fa-arrow-up"></i><span>Rising</span>';
    }
}

// Create overview charts
function createOverviewCharts() {
    // Flow Analysis Chart
    const flowChart = document.getElementById('flow-analysis-chart');
    if (flowChart) {
        new Chart(flowChart, {
            type: 'area',
            data: {
                labels: Array.from({length: 24}, (_, i) => new Date(Date.now() - (23-i) * 60 * 60 * 1000)),
                datasets: [{
                    label: 'Total Flow',
                    data: Array.from({length: 24}, () => Math.random() * 1000000 + 500000),
                    borderColor: colors.primary,
                    backgroundColor: colors.primary + '20',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'hour' }
                    }
                }
            }
        });
    }
    
    // Level Monitoring Chart
    const levelChart = document.getElementById('level-monitoring-chart');
    if (levelChart) {
        new Chart(levelChart, {
            type: 'bar',
            data: {
                labels: ['Tarbela', 'Chashma', 'Mangla'],
                datasets: [{
                    label: 'Water Level (ft)',
                    data: [1550, 649, 1242],
                    backgroundColor: [colors.primary, colors.secondary, colors.success]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }
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
    const alertTime = document.getElementById('alert-time');
    
    if (statusDot) {
        statusDot.className = isOnline ? 'dot online' : 'dot offline';
    }
    
    if (lastUpdate) {
        lastUpdate.textContent = new Date().toLocaleTimeString();
    }
    
    if (alertTime) {
        alertTime.textContent = new Date().toLocaleTimeString();
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('Modern professional dashboard initializing...');
    
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
    
    // Create overview charts
    setTimeout(createOverviewCharts, 500);
    
    // Initial data load
    refreshAllData();
    
    // Auto-refresh every 5 minutes
    setInterval(refreshAllData, 5 * 60 * 1000);
    
    console.log('Modern professional dashboard initialized successfully');
});
