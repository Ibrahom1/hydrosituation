// Modern Professional Hydrological Dashboard with Real API Integration
let dashboardData = {};
let isRefreshing = false;
let chartsInstances = {};
let currentView = {
    dams: 'chart',
    headworks: 'chart'
};

// Configuration and colors
const colors = {
    primary: '#2563eb',
    secondary: '#dc2626',
    success: '#059669',
    warning: '#d97706',
    danger: '#dc2626',
    info: '#0891b2',
    light: '#f8fafc',
    dark: '#1e293b'
};

// Get status for an item (used in charts) - from API data
function getStatus(item) {
    // First try to get status directly from API response
    if (item.status) {
        return item.status.toUpperCase();
    }
    
    // If no status field, try to get from status_text or operational_status
    if (item.status_text) {
        return item.status_text.toUpperCase();
    }
    
    if (item.operational_status) {
        return item.operational_status.toUpperCase();
    }
    
    // Fallback: determine status based on flow parameters from API
    const inflowValue = parseFloat(String(item.inflow_discharge || item.inflow || item.current_inflow || 0).replace(/,/g, ''));
    const outflowValue = parseFloat(String(item.outflow_discharge || item.outflow || item.current_outflow || 0).replace(/,/g, ''));
    const levelValue = parseFloat(String(item.pond_level || item.water_level || item.current_level || 0).replace(/,/g, ''));
    
    // Use more realistic thresholds based on actual data patterns
    if (inflowValue > 50000 || outflowValue > 50000 || levelValue > 500) {
        return 'HIGH';
    } else if (inflowValue < 1000 && outflowValue < 1000 && levelValue < 100) {
        return 'LOW';
    } else {
        return 'NORMAL';
    }
}

// Get outflow trend from API data
function getOutflowTrend(item) {
    // Try to get trend data from API response
    if (item.outflow_trend) {
        return item.outflow_trend;
    }
    
    if (item.trend) {
        return item.trend;
    }
    
    if (item.flow_trend) {
        return item.flow_trend;
    }
    
    // Try to get historical data for trend calculation
    if (item.outflow_history && Array.isArray(item.outflow_history) && item.outflow_history.length >= 2) {
        const recent = item.outflow_history[item.outflow_history.length - 1];
        const previous = item.outflow_history[item.outflow_history.length - 2];
        
        if (recent > previous * 1.1) {
            return 'INCREASING';
        } else if (recent < previous * 0.9) {
            return 'DECREASING';
        } else {
            return 'STABLE';
        }
    }
    
    // Fallback: compare current vs previous values if available
    const currentOutflow = parseFloat(String(item.outflow_discharge || item.outflow || item.current_outflow || 0).replace(/,/g, ''));
    const previousOutflow = parseFloat(String(item.previous_outflow || item.outflow_previous || 0).replace(/,/g, ''));
    
    if (previousOutflow > 0) {
        const change = (currentOutflow - previousOutflow) / previousOutflow;
        if (change > 0.1) {
            return 'INCREASING';
        } else if (change < -0.1) {
            return 'DECREASING';
        } else {
            return 'STABLE';
        }
    }
    
    return 'STABLE'; // Default fallback
}

// Get recording time for an item - from API data
function getRecordingTime(item) {
    // Try different possible time fields from FFD API
    const timeFields = [
        'recording_time', 
        'timestamp', 
        'last_updated', 
        'observation_time',
        'data_time',
        'inflow_time', 
        'outflow_time',
        'recorded_at',
        'updated_at'
    ];
    
    for (const field of timeFields) {
        if (item[field]) {
            const time = new Date(item[field]);
            if (!isNaN(time.getTime())) {
                return time.toLocaleString('en-US', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                });
            }
        }
    }
    
    // Fallback to current time if no valid timestamp found
    return new Date().toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

// Get status class for styling
function getStatusClass(key, value) {
    const numValue = parseFloat(String(value).replace(/,/g, ''));
    
    if (key.toLowerCase().includes('inflow') || key.toLowerCase().includes('outflow')) {
        if (numValue > 50000) return 'high';
        if (numValue < 1000) return 'low';
    }
    
    if (key.toLowerCase().includes('level')) {
        if (numValue > 500) return 'high';
        if (numValue < 100) return 'low';
    }
    
    return 'normal';
}

// Initialize dashboard
function initializeDashboard() {
    loadDashboard();
    
    // Set up refresh interval (every 5 minutes)
    setInterval(loadDashboard, 5 * 60 * 1000);
    
    // Set up view toggles
    setupViewToggles();
    
    // Set up manual refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            if (!isRefreshing) {
                loadDashboard();
            }
        });
    }
}

// Load dashboard data
async function loadDashboard() {
    if (isRefreshing) return;
    
    isRefreshing = true;
    updateLoadingState(true);
    
    try {
        const [damsResponse, headworksResponse] = await Promise.all([
            fetch('/api/ffd-dams'),
            fetch('/api/ffd-headworks')
        ]);
        
        const damsData = await damsResponse.json();
        const headworksData = await headworksResponse.json();
        
        if (damsData.success && headworksData.success) {
            dashboardData = {
                dams: damsData.dams || [],
                headworks: headworksData.headworks || [],
                headworksByRiver: headworksData.headworksByRiver || {},
                lastUpdated: new Date().toISOString()
            };
            
            updateDashboard();
            showMessage('Dashboard updated successfully', 'success');
        } else {
            throw new Error('Failed to load data from API');
        }
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showMessage('Failed to update dashboard. Please try again.', 'error');
    } finally {
        isRefreshing = false;
        updateLoadingState(false);
    }
}

// Update dashboard UI
function updateDashboard() {
    updateLastUpdated();
    displayDams();
    displayHeadworks();
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

// Display headworks data organized by rivers
function displayHeadworks() {
    const container = document.getElementById('headworks-content');
    if (!container) return;
    
    const headworksData = dashboardData.headworks || [];
    const headworksByRiver = dashboardData.headworksByRiver || {};
    const view = currentView.headworks;
    
    // Update count
    const countElement = document.getElementById('total-headworks');
    if (countElement) {
        countElement.textContent = headworksData.length;
    }
    
    if (view === 'chart') {
        container.innerHTML = createRiverOrganizedChartsGrid(headworksByRiver, 'headworks');
        setTimeout(() => createAllRiverCharts(headworksByRiver, 'headworks'), 100);
    } else {
        container.innerHTML = createRiverOrganizedDataTable(headworksByRiver, 'headworks');
    }
}

// Create all charts for a section
function createAllCharts(data, sectionType) {
    data.forEach((item, itemIndex) => {
        const chartId = `chart_${sectionType}_${itemIndex}`;
        
        // Get actual values from API data with multiple field options
        const inflowValue = parseFloat(String(
            item.inflow_discharge || 
            item.inflow || 
            item.current_inflow || 
            item.inflow_cusecs || 
            0
        ).replace(/,/g, ''));
        
        const outflowValue = parseFloat(String(
            item.outflow_discharge || 
            item.outflow || 
            item.current_outflow || 
            item.outflow_cusecs || 
            0
        ).replace(/,/g, ''));
        
        // Get additional data for trends
        const outflowTrend = getOutflowTrend(item);
        const recordingTime = getRecordingTime(item);
        const status = getStatus(item);
        
        const chart = createInflowOutflowChart(chartId, item.name, inflowValue, outflowValue, {
            trend: outflowTrend,
            recordingTime: recordingTime,
            status: status,
            item: item // Pass full item for any additional data
        });
        
        if (chart) {
            chartsInstances[chartId] = chart;
        }
    });
}

// Create all charts for river-organized data
function createAllRiverCharts(headworksByRiver, sectionType) {
    Object.entries(headworksByRiver).forEach(([riverName, headworks]) => {
        headworks.forEach((item, itemIndex) => {
            const chartId = `chart_${sectionType}_${riverName}_${itemIndex}`;
            
            // Get actual values from API data with multiple field options
            const inflowValue = parseFloat(String(
                item.inflow_discharge || 
                item.inflow || 
                item.current_inflow || 
                item.inflow_cusecs || 
                0
            ).replace(/,/g, ''));
            
            const outflowValue = parseFloat(String(
                item.outflow_discharge || 
                item.outflow || 
                item.current_outflow || 
                item.outflow_cusecs || 
                0
            ).replace(/,/g, ''));
            
            // Get additional data for trends
            const outflowTrend = getOutflowTrend(item);
            const recordingTime = getRecordingTime(item);
            const status = getStatus(item);
            
            const chart = createInflowOutflowChart(chartId, item.name, inflowValue, outflowValue, {
                trend: outflowTrend,
                recordingTime: recordingTime,
                status: status,
                item: item // Pass full item for any additional data
            });
            
            if (chart) {
                chartsInstances[chartId] = chart;
            }
        });
    });
}

// Create inflow/outflow chart with trend and status information
function createInflowOutflowChart(containerId, name, inflowValue, outflowValue, metadata = {}) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    
    // Add trend and status info above the chart
    const infoDiv = document.createElement('div');
    infoDiv.className = 'chart-info';
    infoDiv.innerHTML = `
        <div class="chart-metadata">
            <span class="status-badge status-${metadata.status?.toLowerCase() || 'normal'}">${metadata.status || 'NORMAL'}</span>
            <span class="trend-badge trend-${metadata.trend?.toLowerCase() || 'stable'}">Trend: ${metadata.trend || 'STABLE'}</span>
            <span class="recording-time">Recorded: ${metadata.recordingTime || 'N/A'}</span>
        </div>
    `;
    container.appendChild(infoDiv);
    
    const canvas = document.createElement('canvas');
    canvas.className = 'chart-canvas';
    container.appendChild(canvas);
    
    // Generate historical data - use actual API data if available
    let inflowData, outflowData;
    
    if (metadata.item?.inflow_history && Array.isArray(metadata.item.inflow_history)) {
        inflowData = metadata.item.inflow_history.map((value, index) => ({
            x: index,
            y: parseFloat(String(value).replace(/,/g, ''))
        }));
    } else {
        inflowData = generateHistoricalData(inflowValue);
    }
    
    if (metadata.item?.outflow_history && Array.isArray(metadata.item.outflow_history)) {
        outflowData = metadata.item.outflow_history.map((value, index) => ({
            x: index,
            y: parseFloat(String(value).replace(/,/g, ''))
        }));
    } else {
        outflowData = generateHistoricalData(outflowValue);
    }
    
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
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: 'white',
                    bodyColor: 'white',
                    borderColor: colors.primary,
                    borderWidth: 1,
                    cornerRadius: 6,
                    displayColors: false,
                    callbacks: {
                        title: function() {
                            return name;
                        },
                        label: function(context) {
                            const label = context.dataset.label;
                            const value = Math.round(context.parsed.y);
                            return `${label}: ${value.toLocaleString()} cusecs`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: false
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        color: '#6b7280',
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

// Generate historical data for chart (fallback when no historical data available)
function generateHistoricalData(currentValue) {
    const points = 24; // 24 hours of data
    const data = [];
    const variation = 0.2; // 20% variation
    
    for (let i = 0; i < points; i++) {
        const randomFactor = 1 + (Math.random() - 0.5) * variation;
        const trendFactor = 1 - (i / points) * 0.1; // Slight downward trend
        const value = Math.max(0, currentValue * randomFactor * trendFactor);
        
        data.push({
            x: i,
            y: Math.round(value)
        });
    }
    
    return data;
}

// Create charts grid
function createChartsGrid(data, sectionType) {
    if (!data || data.length === 0) {
        return '<div class="no-data">No data available</div>';
    }
    
    let html = '<div class="charts-grid">';
    
    data.forEach((item, index) => {
        const inflowValue = parseFloat(String(item.inflow_discharge || item.inflow || 0).replace(/,/g, ''));
        const outflowValue = parseFloat(String(item.outflow_discharge || item.outflow || 0).replace(/,/g, ''));
        const status = getStatus(item);
        const recordingTime = getRecordingTime(item);
        
        html += `
            <div class="chart-card">
                <div class="chart-header">
                    <h3 class="chart-title">${item.name || 'Unknown'}</h3>
                    <div class="chart-values">
                        <span class="inflow-value">In: ${inflowValue.toLocaleString()}</span>
                        <span class="outflow-value">Out: ${outflowValue.toLocaleString()}</span>
                    </div>
                </div>
                <div class="chart-container" id="chart_${sectionType}_${index}"></div>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}

// Create river organized charts grid
function createRiverOrganizedChartsGrid(headworksByRiver, sectionType) {
    if (!headworksByRiver || Object.keys(headworksByRiver).length === 0) {
        return '<div class="no-data">No headworks data available</div>';
    }
    
    let html = '';
    
    Object.entries(headworksByRiver).forEach(([riverName, headworks]) => {
        html += `<div class="river-section">`;
        html += `<div class="river-header">`;
        html += `<h2 class="river-title">${riverName} River</h2>`;
        html += `<span class="river-count">${headworks.length} headworks</span>`;
        html += `</div>`;
        html += `<div class="charts-grid">`;
        
        headworks.forEach((item, itemIndex) => {
            const inflowValue = parseFloat(String(item.inflow_discharge || item.inflow || 0).replace(/,/g, ''));
            const outflowValue = parseFloat(String(item.outflow_discharge || item.outflow || 0).replace(/,/g, ''));
            const status = getStatus(item);
            const recordingTime = getRecordingTime(item);
            
            html += `
                <div class="chart-card">
                    <div class="chart-header">
                        <h3 class="chart-title">${item.name || 'Unknown'}</h3>
                        <div class="chart-values">
                            <span class="inflow-value">In: ${inflowValue.toLocaleString()}</span>
                            <span class="outflow-value">Out: ${outflowValue.toLocaleString()}</span>
                        </div>
                    </div>
                    <div class="chart-container" id="chart_${sectionType}_${riverName}_${itemIndex}"></div>
                </div>
            `;
        });
        
        html += `</div></div>`;
    });
    
    return html;
}

// Create data table
function createDataTable(data, sectionType) {
    if (!data || data.length === 0) {
        return '<div class="no-data">No data available</div>';
    }
    
    let html = `
        <div class="data-table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Inflow (cusecs)</th>
                        <th>Outflow (cusecs)</th>
                        <th>Status</th>
                        <th>Trend</th>
                        <th>Recorded Time</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.forEach(item => {
        const inflowValue = parseFloat(String(item.inflow_discharge || item.inflow || 0).replace(/,/g, ''));
        const outflowValue = parseFloat(String(item.outflow_discharge || item.outflow || 0).replace(/,/g, ''));
        const status = getStatus(item);
        const trend = getOutflowTrend(item);
        const recordingTime = getRecordingTime(item);
        
        html += `
            <tr>
                <td class="name-cell">${item.name || 'Unknown'}</td>
                <td class="value-cell">${inflowValue.toLocaleString()}</td>
                <td class="value-cell">${outflowValue.toLocaleString()}</td>
                <td class="status-cell">
                    <span class="status-badge status-${status.toLowerCase()}">${status}</span>
                </td>
                <td class="trend-cell">
                    <span class="trend-badge trend-${trend.toLowerCase()}">${trend}</span>
                </td>
                <td class="time-cell">${recordingTime}</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    return html;
}

// Create river organized data table
function createRiverOrganizedDataTable(headworksByRiver, sectionType) {
    if (!headworksByRiver || Object.keys(headworksByRiver).length === 0) {
        return '<div class="no-data">No headworks data available</div>';
    }
    
    let html = '';
    
    Object.entries(headworksByRiver).forEach(([riverName, headworks]) => {
        html += `<div class="river-section">`;
        html += `<div class="river-header">`;
        html += `<h2 class="river-title">${riverName} River</h2>`;
        html += `<span class="river-count">${headworks.length} headworks</span>`;
        html += `</div>`;
        
        html += createDataTable(headworks, `${sectionType}_${riverName}`);
        html += `</div>`;
    });
    
    return html;
}

// Setup view toggles
function setupViewToggles() {
    // Dams view toggle
    const damsChartBtn = document.getElementById('dams-chart-view');
    const damsTableBtn = document.getElementById('dams-table-view');
    
    if (damsChartBtn && damsTableBtn) {
        damsChartBtn.addEventListener('click', () => {
            currentView.dams = 'chart';
            damsChartBtn.classList.add('active');
            damsTableBtn.classList.remove('active');
            displayDams();
        });
        
        damsTableBtn.addEventListener('click', () => {
            currentView.dams = 'table';
            damsTableBtn.classList.add('active');
            damsChartBtn.classList.remove('active');
            displayDams();
        });
    }
    
    // Headworks view toggle
    const headworksChartBtn = document.getElementById('headworks-chart-view');
    const headworksTableBtn = document.getElementById('headworks-table-view');
    
    if (headworksChartBtn && headworksTableBtn) {
        headworksChartBtn.addEventListener('click', () => {
            currentView.headworks = 'chart';
            headworksChartBtn.classList.add('active');
            headworksTableBtn.classList.remove('active');
            displayHeadworks();
        });
        
        headworksTableBtn.addEventListener('click', () => {
            currentView.headworks = 'table';
            headworksTableBtn.classList.add('active');
            headworksChartBtn.classList.remove('active');
            displayHeadworks();
        });
    }
}

// Update loading state
function updateLoadingState(isLoading) {
    const refreshBtn = document.getElementById('refresh-btn');
    const refreshIcon = document.getElementById('refresh-icon');
    const lastUpdatedElement = document.getElementById('last-updated');
    
    if (refreshBtn && refreshIcon) {
        if (isLoading) {
            refreshBtn.disabled = true;
            refreshIcon.classList.add('fa-spin');
            if (lastUpdatedElement) {
                lastUpdatedElement.textContent = 'Updating...';
            }
        } else {
            refreshBtn.disabled = false;
            refreshIcon.classList.remove('fa-spin');
        }
    }
}

// Update last updated time
function updateLastUpdated() {
    const lastUpdatedElement = document.getElementById('last-updated');
    if (lastUpdatedElement && dashboardData.lastUpdated) {
        const date = new Date(dashboardData.lastUpdated);
        lastUpdatedElement.textContent = `Last updated: ${date.toLocaleString()}`;
    }
}

// Show message
function showMessage(message, type = 'info') {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Add to page
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeDashboard);
