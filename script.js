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

// Register zoom plugin if available (CDN global)
try {
    if (window.Chart && window.ChartZoom) {
        Chart.register(window.ChartZoom);
    } else if (window.Chart && window['chartjs-plugin-zoom']) {
        Chart.register(window['chartjs-plugin-zoom']);
    }
} catch (e) {
    console.warn('Chart.js Zoom plugin registration failed:', e);
}

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

// UPDATED: Request 15 days of historical data instead of 24 hours
async function fetchHistoricalSeries(name, days = 15) {
    try {
        // Use days parameter instead of hours
        const res = await fetch(`http://localhost:5000/api/history?name=${encodeURIComponent(name)}&days=${days}`);
        if (!res.ok) throw new Error('history status');
        const data = await res.json();
        if (!data.success) throw new Error('history payload');
        if (data.inflow.length === 0 && data.outflow.length === 0) return null;
        
        console.log(`📊 Historical data for ${name}: ${data.points} data points over ${days} days`);
        
        return {
            inflow: data.inflow.map(p => ({ 
                x: parseTimestamp(p.x), 
                y: p.y,
                originalTime: p.x // Keep original timestamp for tooltip
            })),
            outflow: data.outflow.map(p => ({ 
                x: parseTimestamp(p.x), 
                y: p.y,
                originalTime: p.x // Keep original timestamp for tooltip
            }))
        };
    } catch (e) {
        console.warn('History fetch failed for', name, e);
        return null;
    }
}

// Helper function to parse various timestamp formats
function parseTimestamp(timestamp) {
    if (!timestamp) return new Date();
    
    // If it's already a valid Date object
    if (timestamp instanceof Date) return timestamp;
    
    // If it's in the database format like "19-Aug 06 PST" or "10-Sep 06 PKT", convert for Chart.js
    if (typeof timestamp === 'string' && (timestamp.includes('PST') || timestamp.includes('PKT'))) {
        // Try to convert "19-Aug 06 PST" or "10-Sep 06 PKT" to a parseable format
        const match = timestamp.match(/(\d{1,2})-(\w{3})\s+(\d{2})\s+(\w+)/);
        if (match) {
            const [, day, month, hourStr, timezone] = match;
            const monthMap = {
                'Jan': 0, 'Feb': 1, 'Mar': 2, 'Apr': 3, 'May': 4, 'Jun': 5,
                'Jul': 6, 'Aug': 7, 'Sep': 8, 'Oct': 9, 'Nov': 10, 'Dec': 11
            };
            const monthIndex = monthMap[month];
            if (monthIndex !== undefined) {
                // Parse hour in 24-hour format: 06 = 6 AM, 18 = 6 PM, 00 = midnight
                const hour24 = parseInt(hourStr, 10);
                // Use 2025 as current year for this data
                const year = 2025;
                const parsedDate = new Date(year, monthIndex, parseInt(day), hour24, 0, 0);
                console.log(`Parsed timestamp: "${timestamp}" -> ${parsedDate.toISOString()}`);
                return parsedDate;
            }
        }
    }
    
    // Try parsing as ISO string
    const isoDate = new Date(timestamp);
    if (!isNaN(isoDate.getTime())) return isoDate;
    return new Date();
}

// NEW: Check database storage status for debugging
async function checkStorageStatus() {
    try {
        const res = await fetch('http://localhost:5000/api/storage-status');
        const data = await res.json();
        console.log('📁 Database Storage Status:', data);
        
        if (data.success) {
            const hours = data.hours_since_last_storage;
            const nextDue = new Date(data.next_storage_due);
            console.log(`⏰ Last stored: ${hours?.toFixed(1) || 'Unknown'} hours ago`);
            console.log(`⏰ Next storage due: ${nextDue.toLocaleString()}`);
            console.log(`📊 Total records: ${data.total_records}`);
        }
        
        return data;
    } catch (e) {
        console.warn('Could not check storage status:', e);
        return null;
    }
}

// UPDATED: Generate synthetic data for 15 days instead of 24 hours
function generateSyntheticSeries(currentValue, hours = 360) { // 15 days = 360 hours
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

// Normalize status strings into safe CSS class names
function normalizeStatusClass(status) {
    if (!status) return 'normal';
    // Convert to string, trim, uppercase for logic, but produce lowercase-hyphen class
    const s = String(status).trim();
    // Common normalization rules: spaces/underscores -> hyphens, multiple hyphens collapsed
    const normalized = s.replace(/\s+/g, '-').replace(/_+/g, '-').replace(/[^a-zA-Z0-9-]/g, '').toLowerCase();
    // Map some known variants to canonical names
    if (normalized === 'exceptional' || normalized === 'ex' || normalized === 'ex-high' || normalized === 'exhigh') return 'ex-high';
    if (normalized === 'very-high' || normalized === 'veryhigh' || normalized === 'vhigh') return 'very-high';
    if (normalized === 'high' || normalized === 'h') return 'high';
    if (normalized === 'medium' || normalized === 'med') return 'medium';
    if (normalized === 'low' || normalized === 'l') return 'low';
    if (normalized === 'normal' || normalized === 'ok' || normalized === '') return 'normal';
    return normalized;
}

// UPDATED: Generate historical data for 15 days (360 hours)
function generateHistoricalData(currentValue, hours = 360) {
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
                },
                zoom: {
                    zoom: {
                        wheel: { enabled: true }, // Ctrl+Wheel by default in v2, we'll allow plain wheel
                        pinch: { enabled: true },
                        mode: 'x',
                    },
                    pan: {
                        enabled: true,
                        mode: 'x'
                    },
                    limits: {
                        x: { min: 'original', max: 'original' },
                        y: { min: 'original', max: 'original' }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        displayFormats: {
                            hour: 'HH:mm',
                            day: 'MMM dd'
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
    // Double-click to reset zoom
    canvas.addEventListener('dblclick', () => {
        if (typeof chart.resetZoom === 'function') chart.resetZoom();
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
            <button class="fullscreen-button" onclick="window.toggleFullscreen('${chartId}', '${item.name}', '${status}', '${formattedInflow}', '${formattedOutflow}', '${inflowTrendLabel}', '${outflowTrendLabel}', '${recordingTime}')" title="Toggle Fullscreen">
                <i class="fas fa-expand"></i>
            </button>
            <div class="chart-header">
                <div class="chart-header-content">
                    <h6 class="chart-title">${item.name}</h6>
                    <span class="chart-status ${normalizeStatusClass(status)}">${status}</span>
                </div>
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
    // Ensure recording_time column is always present (per-item timestamp from API) and not duplicated
    const numericParams = Array.from(allParams).filter(p => p !== 'recording_time');
    const paramList = ['recording_time', ...numericParams];
    
    const headers = ['Name', ...paramList.map(param => {
        if (param === 'recording_time') return 'Recording Time';
        return param.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    })];
    
    const rows = data.map(item => {
        const cells = [item.name || 'N/A'];
        paramList.forEach(param => {
            if (param === 'recording_time') {
                const recVal = item.recording_time || item.inflow_time || item.outflow_time || 'N/A';
                cells.push(`<span class="data-value">${recVal}</span>`);
            } else {
                const valueRaw = item[param];
                const value = formatValue(valueRaw);
                const unit = getParameterUnit(param);
                const status = getStatusClass(param, valueRaw);
                cells.push(`<span class="data-value trend-${status === 'normal' ? 'steady' : status === 'high' ? 'rising' : 'falling'}">${value} ${unit}</span>`);
            }
        });
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
            // Normalize river name: capitalize only the first letter, lowercase the rest
            const prettyName = river === 'OTHER' ? 'Other Headworks' : (river.charAt(0).toUpperCase() + river.slice(1).toLowerCase() + ' River');
            const headerLabel = prettyName;
            html += `<div class="river-section"><div class="river-header"><h4 class="river-title" style="color: black;">${headerLabel}</h4><span class="river-count">${list.length}</span></div><div class="charts-container">`;
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
                
                html += `<div class="chart-item">
                    <button class="fullscreen-button" onclick="window.toggleFullscreen('${chartId}', '${item.name}', '${status}', '${inflowValue}', '${outflowValue}', '${inflowTrendLabel}', '${outflowTrendLabel}', '${item.recording_time || 'N/A'}')" title="Toggle Fullscreen">
                        <i class="fas fa-expand"></i>
                    </button>
                    <div class="chart-header">
                        <div class="chart-header-content">
                            <h6 class="chart-title">${item.name}</h6>
                            <span class="chart-status ${normalizeStatusClass(status)}">${status}</span>
                        </div>
                    </div>
                    <div class="chart-canvas" id="${chartId}"></div>
                    <div class="chart-info">
                        <div class="flow-values">
                            <div class="flow-item inflow">
                                <div class="flow-label"><i class="fas fa-arrow-down"></i>Inflow</div>
                                <div class="flow-value">${inflowValue} cusecs</div>
                                <div class="flow-trend ${inflowTrendClass}"><i class="fas fa-chart-line"></i>${inflowTrendLabel}</div>
                            </div>
                            <div class="flow-item outflow">
                                <div class="flow-label"><i class="fas fa-arrow-up"></i>Outflow</div>
                                <div class="flow-value">${outflowValue} cusecs</div>
                                <div class="flow-trend ${outflowTrendClass}"><i class="fas fa-chart-line"></i>${outflowTrendLabel}</div>
                            </div>
                        </div>
                        <div class="recording-info">
                            <div class="recording-time"><i class="fas fa-clock"></i><span>Recorded: ${item.recording_time || 'N/A'}</span></div>
                        </div>
                    </div>
                </div>`;
            });
            html += '</div></div>';
        });
        container.innerHTML = html;
        
        // UPDATED: Create charts with 15 days of data
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
                
                // Request 15 days of historical data
                const history = await fetchHistoricalSeries(item.name, 15);
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
            const tableHeaderLabel = river === 'OTHER' ? 'Other Headworks' : (river.charAt(0).toUpperCase() + river.slice(1).toLowerCase() + ' River');
            html += `<div class="river-section"><div class="river-header"><h4 class="river-title" style="color: black;">${tableHeaderLabel}</h4><span class="river-count">${groups[river].length}</span></div>`;
            html += createDataTable(groups[river], 'headworks');
            html += '</div>';
        });
        container.innerHTML = html;
    }
}

// UPDATED: Create all charts with 15 days of historical data
async function createAllCharts(data, sectionType) {
    for (let idx = 0; idx < data.length; idx++) {
        const item = data[idx];
        const chartId = `chart_${sectionType}_${idx}`;
        const inflowValue = parseFloat(String(item.inflow_discharge || 0).replace(/,/g, ''));
        const outflowValue = parseFloat(String(item.outflow_discharge || 0).replace(/,/g, ''));
        
        // Request 15 days of historical data
        const history = await fetchHistoricalSeries(item.name, 15);
        const inflowSeries = history?.inflow || generateSyntheticSeries(inflowValue);
        const outflowSeries = history?.outflow || generateSyntheticSeries(outflowValue);
        
        const chart = createInflowOutflowChart(chartId, item.name, inflowSeries, outflowSeries);
        if (chart) chartsInstances[chartId] = chart;
    }
}

const floodLevels = {
    'TARBELA': { LOW: 250000, MEDIUM: 375000, HIGH: 500000, VERY_HIGH: 650000, EX_HIGH: 800000 },
    'ATTOCK': { LOW: 250000, MEDIUM: 375000, HIGH: 500000, VERY_HIGH: 650000, EX_HIGH: 800000 },
    'KALABAGH': { LOW: 250000, MEDIUM: 375000, HIGH: 500000, VERY_HIGH: 650000, EX_HIGH: 800000 },
    'CHASHMA': { LOW: 250000, MEDIUM: 375000, HIGH: 500000, VERY_HIGH: 650000, EX_HIGH: 800000 },
    'TAUNSA': { LOW: 250000, MEDIUM: 375000, HIGH: 500000, VERY_HIGH: 650000, EX_HIGH: 800000 },
    'GUDDU': { LOW: 200000, MEDIUM: 350000, HIGH: 500000, VERY_HIGH: 700000, EX_HIGH: 900000 },
    'SUKKUR': { LOW: 200000, MEDIUM: 350000, HIGH: 500000, VERY_HIGH: 700000, EX_HIGH: 900000 },
    'KOTRI': { LOW: 200000, MEDIUM: 300000, HIGH: 450000, VERY_HIGH: 650000, EX_HIGH: 800000 },
    'KOHALA': { LOW: 100000, MEDIUM: 150000, HIGH: 200000, VERY_HIGH: 300000, EX_HIGH: 400000 },
    'MANGLA': { LOW: 75000, MEDIUM: 110000, HIGH: 150000, VERY_HIGH: 225000, EX_HIGH: 300000 },
    'RASUL': { LOW: 75000, MEDIUM: 110000, HIGH: 150000, VERY_HIGH: 225000, EX_HIGH: 300000 },
    'MARALA': { LOW: 100000, MEDIUM: 150000, HIGH: 200000, VERY_HIGH: 400000, EX_HIGH: 600000 },
    'KHANKI': { LOW: 100000, MEDIUM: 150000, HIGH: 200000, VERY_HIGH: 400000, EX_HIGH: 600000 },
    'Q.ABAD': { LOW: 100000, MEDIUM: 150000, HIGH: 200000, VERY_HIGH: 400000, EX_HIGH: 600000 },
    'QADIRABAD': { LOW: 100000, MEDIUM: 150000, HIGH: 200000, VERY_HIGH: 400000, EX_HIGH: 600000 },
    'TRIMMU': { LOW: 150000, MEDIUM: 200000, HIGH: 300000, VERY_HIGH: 450000, EX_HIGH: 600000 },
    'PANJNAD': { LOW: 150000, MEDIUM: 200000, HIGH: 300000, VERY_HIGH: 450000, EX_HIGH: 600000 },
    'JASSAR': { LOW: 50000, MEDIUM: 75000, HIGH: 100000, VERY_HIGH: 150000, EX_HIGH: 200000 },
    'SHAHDARA': { LOW: 40000, MEDIUM: 65000, HIGH: 90000, VERY_HIGH: 135000, EX_HIGH: 180000 },
    'BALLOKI': { LOW: 40000, MEDIUM: 65000, HIGH: 90000, VERY_HIGH: 135000, EX_HIGH: 180000 },
    'SIDHNAI': { LOW: 30000, MEDIUM: 46000, HIGH: 60000, VERY_HIGH: 90000, EX_HIGH: 130000 },
    'SULEMANKI': { LOW: 50000, MEDIUM: 80000, HIGH: 120000, VERY_HIGH: 175000, EX_HIGH: 225000 },
    'ISLAM': { LOW: 50000, MEDIUM: 80000, HIGH: 120000, VERY_HIGH: 175000, EX_HIGH: 225000 }
};

// Flood level colors matching the image
const floodColors = {
    LOW: '#19aec2ff',           // Green - Normal Flow
    MEDIUM: '#0a0edbff',        // Teal - Low Flood  
    HIGH: '#887406ff',          // Blue - Medium Flood
    VERY_HIGH: '#632402ff',     // Orange/Brown - High Flood
    EX_HIGH: '#dc2626'        // Red - Very High/Exceptionally High Flood
};

// Get flood levels for a site
function getFloodLevelsForSite(siteName) {
    const normalizedName = siteName.toUpperCase().replace(/\s+/g, '').replace('DAM', '');
    
    // Handle special cases
    if (normalizedName.includes('TARBELA')) return floodLevels['TARBELA'];
    if (normalizedName.includes('CHASHMA')) return floodLevels['CHASHMA'];
    if (normalizedName.includes('MANGLA')) return floodLevels['MANGLA'];
    if (normalizedName.includes('KALABAGH')) return floodLevels['KALABAGH'];
    if (normalizedName.includes('TAUNSA')) return floodLevels['TAUNSA'];
    if (normalizedName.includes('GUDDU')) return floodLevels['GUDDU'];
    if (normalizedName.includes('SUKKUR')) return floodLevels['SUKKUR'];
    if (normalizedName.includes('KOTRI')) return floodLevels['KOTRI'];
    if (normalizedName.includes('MARALA')) return floodLevels['MARALA'];
    if (normalizedName.includes('KHANKI')) return floodLevels['KHANKI'];
    if (normalizedName.includes('QADIRABAD') || normalizedName.includes('Q.ABAD')) return floodLevels['Q.ABAD'];
    if (normalizedName.includes('TRIMMU')) return floodLevels['TRIMMU'];
    if (normalizedName.includes('PANJNAD')) return floodLevels['PANJNAD'];
    if (normalizedName.includes('JASSAR')) return floodLevels['JASSAR'];
    if (normalizedName.includes('SHAHDARA')) return floodLevels['SHAHDARA'];
    if (normalizedName.includes('BALLOKI')) return floodLevels['BALLOKI'];
    if (normalizedName.includes('SIDHNAI')) return floodLevels['SIDHNAI'];
    if (normalizedName.includes('SULEMANKI')) return floodLevels['SULEMANKI'];
    if (normalizedName.includes('ISLAM')) return floodLevels['ISLAM'];
    if (normalizedName.includes('RASUL')) return floodLevels['RASUL'];
    
    return null;
}

function createInflowOutflowChart(containerId, name, inflowSeries, outflowSeries, isFullscreen = false) {
    const container = document.getElementById(containerId);
    if (!container) return null;

    // For fullscreen, use the container directly; for regular charts, create canvas
    let canvas;
    if (isFullscreen) {
        canvas = container.querySelector('canvas') || document.createElement('canvas');
        if (!container.querySelector('canvas')) {
            container.appendChild(canvas);
        }
    } else {
        canvas = document.createElement('canvas');
        canvas.className = 'chart-canvas';
        container.appendChild(canvas);
    }

    const datasets = [];
    
    // Store original timestamps for tooltip access
    const originalTimestamps = [];

    if (inflowSeries && inflowSeries.length > 0) {
        // Extract original timestamps
        inflowSeries.forEach((point, index) => {
            if (!originalTimestamps[index]) originalTimestamps[index] = {};
            originalTimestamps[index].time = point.originalTime || point.x;
        });
        
        datasets.push({
            label: 'Inflow',
            data: inflowSeries.map(p => ({ x: p.x, y: p.y })), // Simple x,y for Chart.js
            borderColor: '#1d4ed8', // brighter blue
            backgroundColor: '#1d4ed820',
            fill: false,
            tension: 0.4,
            pointRadius: isFullscreen ? 3 : 0,
            pointHoverRadius: isFullscreen ? 8 : 6, // bigger hover point
            borderWidth: isFullscreen ? 4 : 3 // thicker line for fullscreen
        });
    }

    if (outflowSeries && outflowSeries.length > 0) {
        // Extract original timestamps  
        outflowSeries.forEach((point, index) => {
            if (!originalTimestamps[index]) originalTimestamps[index] = {};
            originalTimestamps[index].time = point.originalTime || point.x;
        });
        
        datasets.push({
            label: 'Outflow',
            data: outflowSeries.map(p => ({ x: p.x, y: p.y })), // Simple x,y for Chart.js
            borderColor: '#059669', // brighter green
            backgroundColor: 'rgba(5, 150, 105, 0.25)', // lighter green fill
            fill: true,
            tension: 0.4,
            pointRadius: isFullscreen ? 3 : 0,
            pointHoverRadius: isFullscreen ? 8 : 6,
            borderWidth: isFullscreen ? 4 : 3
        });
    }

    // Flood levels: Only show the next threshold line above the current outflow value, but keep all in legend (hidden by default except next)
    const levels = getFloodLevelsForSite(name);
    if (levels) {
        const baseSeries = outflowSeries?.length ? outflowSeries : inflowSeries;
        if (baseSeries?.length) {
            // Get the latest outflow value
            const latestPoint = baseSeries[baseSeries.length - 1];
            const currentValue = latestPoint?.y || 0;
            // Levels are in order: LOW, MEDIUM, HIGH, VERY_HIGH, EX_HIGH
            const levelOrder = ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH', 'EX_HIGH'];
            let nextLevel = null;
            for (let i = 0; i < levelOrder.length; i++) {
                const levelKey = levelOrder[i];
                const threshold = levels[levelKey];
                if (typeof threshold === 'number' && currentValue < threshold) {
                    nextLevel = levelKey;
                    break;
                }
            }
            // Add all levels, but only nextLevel is visible, others are hidden (can be enabled from legend)
            levelOrder.forEach(levelKey => {
                const value = levels[levelKey];
                datasets.push({
                    label: `${levelKey.replace('_', ' ')} Flood`,
                    data: baseSeries.map(point => ({ x: point.x, y: value })),
                    borderColor: floodColors[levelKey] || '#ef4444',
                    backgroundColor: 'transparent',
                    borderDash: [5, 5],
                    borderWidth: isFullscreen ? 3 : 2,
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    tension: 0,
                    hidden: nextLevel !== levelKey // Only nextLevel is visible, others hidden
                });
            });
        }
    }

    const allYs = datasets.flatMap(ds => ds.data.map(p => p?.y)).filter(v => typeof v === 'number');
    const maxFlow = Math.max(0, ...allYs);

    const chart = new Chart(canvas, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: {
                    display: true,
                    position: isFullscreen ? 'bottom' : 'top',
                    labels: {
                        usePointStyle: true,
                        padding: isFullscreen ? 20 : 8,
                        font: { size: isFullscreen ? 14 : 10 },
                        filter: function (legendItem, chartData) {
                            if (legendItem.text.includes('Inflow') || legendItem.text.includes('Outflow')) {
                                return true;
                            }
                            const firstDataPoint = chartData.datasets[legendItem.datasetIndex]?.data?.[0];
                            const levelValue = firstDataPoint?.y ?? 0;
                            return levelValue <= maxFlow * 5;
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                    titleColor: '#f9fafb',
                    bodyColor: '#f9fafb',
                    borderColor: '#1d4ed8',
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true,
                    titleFont: { size: isFullscreen ? 16 : 12 },
                    bodyFont: { size: isFullscreen ? 14 : 11 },
                    padding: isFullscreen ? 12 : 8,
                    callbacks: {
                        title: function(context) {
                            // Try to get the original timestamp from the stored array
                            const dataIndex = context[0].dataIndex;
                            if (originalTimestamps[dataIndex] && originalTimestamps[dataIndex].time) {
                                const originalTime = originalTimestamps[dataIndex].time;
                                // If it's a string from the database like "19-Aug 06 PST", show it directly
                                if (typeof originalTime === 'string') {
                                    return `Recorded: ${originalTime}`;
                                }
                            }
                            // Fallback to formatted date
                            const date = new Date(context[0].parsed.x);
                            return `Time: ${date.toLocaleString()}`;
                        },
                        label: function (context) {
                            if (context.dataset.label.includes('Flood')) {
                                return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} cusecs (Threshold)`;
                            }
                            return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} cusecs`;
                        }
                    }
                },
                zoom: {
                    zoom: {
                        wheel: { enabled: true },
                        pinch: { enabled: true },
                        mode: 'x'
                    },
                    pan: {
                        enabled: true,
                        mode: 'x'
                    },
                    limits: {
                        x: { min: 'original', max: 'original' },
                        y: { min: 'original', max: 'original' }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: { 
                        displayFormats: { 
                            hour: isFullscreen ? 'MMM dd HH:mm' : 'HH:mm',
                            day: isFullscreen ? 'MMM dd' : 'MMM dd',
                            week: 'MMM dd',
                            month: 'MMM yyyy'
                        },
                        tooltipFormat: 'MMM dd, yyyy HH:mm'
                    },
                    grid: { 
                        color: colors.gray[200], 
                        drawTicks: false,
                        lineWidth: isFullscreen ? 2 : 1
                    },
                    border: { display: false },
                    ticks: {
                        maxTicksLimit: isFullscreen ? 12 : 8, // More ticks for fullscreen
                        color: colors.gray[500],
                        font: { size: isFullscreen ? 14 : 10 }
                    }
                },
                y: {
                    grid: { 
                        color: colors.gray[200], 
                        drawTicks: false,
                        lineWidth: isFullscreen ? 2 : 1
                    },
                    border: { display: false },
                    ticks: {
                        color: colors.gray[500],
                        font: { size: isFullscreen ? 14 : 10 },
                        callback: value => value.toLocaleString()
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

// UPDATED: Main refresh function with storage status logging
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
        
        // Check storage status before refresh
        await checkStorageStatus();
        
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

// UPDATED: Auto-sync cloud data function name changed
async function autoSyncCloudData() {
    try {
        console.log('🔄 Checking for cloud data updates...');
        const response = await fetch('http://localhost:5000/api/sync-remote');
        
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

// NEW: Show storage information in console for debugging
async function showStorageInfo() {
    const status = await checkStorageStatus();
    if (status && status.success) {
        console.group('📊 Database Storage Information');
        console.log(`Total Records: ${status.total_records}`);
        console.log(`Last Stored: ${status.last_stored ? new Date(status.last_stored).toLocaleString() : 'Never'}`);
        console.log(`Hours Since Last: ${status.hours_since_last_storage?.toFixed(1) || 'N/A'}`);
        console.log(`Next Storage Due: ${status.next_storage_due ? new Date(status.next_storage_due).toLocaleString() : 'N/A'}`);
        console.log(`Should Store Now: ${status.should_store_now ? 'Yes' : 'No'}`);
        
        if (status.timestamp_counts?.length > 0) {
            console.log('Recent Storage Events:');
            status.timestamp_counts.forEach((item, idx) => {
                console.log(`  ${idx + 1}. ${new Date(item.timestamp).toLocaleString()} - ${item.count} records`);
            });
        }
        console.groupEnd();
    }
}

// UPDATED: Initialize dashboard with storage monitoring
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Modern professional dashboard initializing...');
    
    // Show storage information on startup
    await showStorageInfo();
    
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
    
    // Check storage status every 15 minutes for debugging
    setInterval(showStorageInfo, 15 * 60 * 1000);
    
    console.log('Modern professional dashboard initialized successfully');
});

// === FULLSCREEN FUNCTIONALITY ===
let fullscreenOverlay = null;
let fullscreenChart = null;
let originalChartInstance = null;
let isFullscreenActive = false;
let currentFullscreenData = null;

// Create fullscreen overlay if it doesn't exist
function createFullscreenOverlay() {
    if (!fullscreenOverlay) {
        fullscreenOverlay = document.createElement('div');
        fullscreenOverlay.className = 'fullscreen-overlay';
        fullscreenOverlay.innerHTML = `
            <div class="fullscreen-chart-container">
                <div class="fullscreen-chart-header">
                    <h2 class="fullscreen-chart-title"></h2>
                    <span class="fullscreen-chart-status"></span>
                    <button class="fullscreen-minimize-button" onclick="window.toggleFullscreen()" title="Minimize">
                        <i class="fas fa-compress"></i>
                    </button>
                </div>
                <div class="fullscreen-chart-canvas" id="fullscreen-chart-canvas"></div>
                <div class="fullscreen-chart-info">
                    <div class="fullscreen-flow-item inflow">
                        <div class="fullscreen-flow-label">
                            <i class="fas fa-arrow-down"></i>
                            Inflow
                        </div>
                        <div class="fullscreen-flow-value" id="fullscreen-inflow-value">N/A</div>
                        <div class="fullscreen-flow-trend trend-steady" id="fullscreen-inflow-trend">N/A</div>
                    </div>
                    <div class="fullscreen-flow-item outflow">
                        <div class="fullscreen-flow-label">
                            <i class="fas fa-arrow-up"></i>
                            Outflow
                        </div>
                        <div class="fullscreen-flow-value" id="fullscreen-outflow-value">N/A</div>
                        <div class="fullscreen-flow-trend trend-steady" id="fullscreen-outflow-trend">N/A</div>
                    </div>
                    <div class="fullscreen-flow-item recording">
                        <div class="fullscreen-flow-label">
                            <i class="fas fa-clock"></i>
                            Recording Time
                        </div>
                        <div class="fullscreen-recording-time" id="fullscreen-recording-time">
                            <span>N/A</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(fullscreenOverlay);
    }
}

// Toggle fullscreen view - handles both expand and minimize
window.toggleFullscreen = async function(chartId, name, status, inflowValue, outflowValue, inflowTrend, outflowTrend, recordingTime) {
    try {
        if (isFullscreenActive) {
            // Minimize - close fullscreen
            await minimizeFullscreen();
        } else {
            // Expand - open fullscreen
            if (!chartId) {
                console.warn('No chart data provided for fullscreen');
                return;
            }
            await expandFullscreen(chartId, name, status, inflowValue, outflowValue, inflowTrend, outflowTrend, recordingTime);
        }
    } catch (error) {
        console.error('Error toggling fullscreen:', error);
        await minimizeFullscreen();
    }
};

// Expand to fullscreen
async function expandFullscreen(chartId, name, status, inflowValue, outflowValue, inflowTrend, outflowTrend, recordingTime) {
    // Create overlay if needed
    createFullscreenOverlay();
    
    // Store current data for potential re-use
    currentFullscreenData = { chartId, name, status, inflowValue, outflowValue, inflowTrend, outflowTrend, recordingTime };
    
    // Get the original chart instance
    originalChartInstance = chartsInstances[chartId];
    if (!originalChartInstance) {
        console.warn('No chart instance found for', chartId);
        return;
    }
    
    // Update header info
    document.querySelector('.fullscreen-chart-title').textContent = name;
    const statusElement = document.querySelector('.fullscreen-chart-status');
    statusElement.textContent = status;
    statusElement.className = `fullscreen-chart-status chart-status ${normalizeStatusClass(status)}`;
    
    // Update flow info
    document.getElementById('fullscreen-inflow-value').textContent = `${inflowValue} cusecs`;
    document.getElementById('fullscreen-outflow-value').textContent = `${outflowValue} cusecs`;
    document.getElementById('fullscreen-recording-time').innerHTML = `<span>${recordingTime}</span>`;
    
    // Update trend classes
    const inflowTrendElement = document.getElementById('fullscreen-inflow-trend');
    const outflowTrendElement = document.getElementById('fullscreen-outflow-trend');
    
    inflowTrendElement.textContent = inflowTrend;
    outflowTrendElement.textContent = outflowTrend;
    
    // Set trend classes
    const inflowTrendClass = getTrendClass(inflowTrend);
    const outflowTrendClass = getTrendClass(outflowTrend);
    
    inflowTrendElement.className = `fullscreen-flow-trend ${inflowTrendClass}`;
    outflowTrendElement.className = `fullscreen-flow-trend ${outflowTrendClass}`;
    
    // Show overlay with animation
    fullscreenOverlay.style.display = 'block';
    document.body.style.overflow = 'hidden';
    
    // Trigger reflow to ensure display:block takes effect
    fullscreenOverlay.offsetHeight;
    
    // Add active class for animation
    fullscreenOverlay.classList.add('active');
    isFullscreenActive = true;
    
    // Update all expand buttons to show compress icon
    updateFullscreenButtons(true);
    
    // Wait for animation, then create the chart
    setTimeout(async () => {
        await createFullscreenChart(chartId, name);
    }, 100);
    
    // Add escape key listener
    document.addEventListener('keydown', handleEscapeKey);
}

// Minimize from fullscreen
async function minimizeFullscreen() {
    if (!fullscreenOverlay || !isFullscreenActive) return;
    
    // Add closing class for animation
    fullscreenOverlay.classList.add('closing');
    fullscreenOverlay.classList.remove('active');
    
    // Update all expand buttons to show expand icon
    updateFullscreenButtons(false);
    
    // Wait for animation to complete
    setTimeout(() => {
        fullscreenOverlay.style.display = 'none';
        fullscreenOverlay.classList.remove('closing');
        document.body.style.overflow = '';
        
        // Destroy fullscreen chart
        if (fullscreenChart) {
            fullscreenChart.destroy();
            fullscreenChart = null;
        }
        
        // Clear canvas container
        const canvasContainer = document.getElementById('fullscreen-chart-canvas');
        if (canvasContainer) {
            canvasContainer.innerHTML = '';
        }
        
        isFullscreenActive = false;
        currentFullscreenData = null;
    }, 400); // Match CSS transition duration
    
    // Remove escape key listener
    document.removeEventListener('keydown', handleEscapeKey);
}

// Update all fullscreen buttons icons
function updateFullscreenButtons(isExpanded) {
    const buttons = document.querySelectorAll('.fullscreen-button i');
    buttons.forEach(icon => {
        if (isExpanded) {
            icon.className = 'fas fa-compress';
        } else {
            icon.className = 'fas fa-expand';
        }
    });
}

// Create the fullscreen chart
async function createFullscreenChart(originalChartId, name) {
    try {
        const canvasContainer = document.getElementById('fullscreen-chart-canvas');
        canvasContainer.innerHTML = ''; // Clear any existing content
        
        const canvas = document.createElement('canvas');
        canvas.id = 'fullscreen-canvas';
        canvasContainer.appendChild(canvas);
        
        // Get original chart data or fetch fresh historical data
        let inflowSeries, outflowSeries;
        
        if (originalChartInstance && originalChartInstance.data && originalChartInstance.data.datasets) {
            // Use data from original chart
            const datasets = originalChartInstance.data.datasets;
            const inflowDataset = datasets.find(d => d.label === 'Inflow');
            const outflowDataset = datasets.find(d => d.label === 'Outflow');
            
            inflowSeries = inflowDataset ? inflowDataset.data : [];
            outflowSeries = outflowDataset ? outflowDataset.data : [];
        } else {
            // Fetch fresh data
            console.log('Fetching fresh data for fullscreen chart:', name);
            const history = await fetchHistoricalSeries(name, 15);
            inflowSeries = history?.inflow || [];
            outflowSeries = history?.outflow || [];
        }
        
        // Create fullscreen chart with the data
        fullscreenChart = createInflowOutflowChart('fullscreen-chart-canvas', name, inflowSeries, outflowSeries, true);
        
        if (fullscreenChart) {
            console.log('Fullscreen chart created successfully');
        }
        
    } catch (error) {
        console.error('Error creating fullscreen chart:', error);
    }
}

// Handle escape key press
function handleEscapeKey(event) {
    if (event.key === 'Escape') {
        window.toggleFullscreen();
    }
}

// Get trend class from trend text
function getTrendClass(trendText) {
    if (!trendText || trendText === 'N/A') return 'trend-steady';
    
    const trend = trendText.toLowerCase();
    if (trend.includes('rise') || trend.includes('rising')) return 'trend-rising';
    if (trend.includes('fall') || trend.includes('falling')) return 'trend-falling';
    return 'trend-steady';
}

// Update createInflowOutflowChart to support fullscreen mode
const originalCreateInflowOutflowChart = createInflowOutflowChart;