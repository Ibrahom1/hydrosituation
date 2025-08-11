// API Base URL
const API_BASE_URL = 'http://localhost:5000/api';

// Global data storage
let globalData = {
    dams: [],
    headworks: [],
    lastUpdated: null
};

// Chart instances storage
const chartInstances = {};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Hydrological Dashboard initializing...');
    refreshAllData();
    
    // Auto-refresh every 5 minutes
    setInterval(refreshAllData, 300000);
    
    console.log('Dashboard initialized');
});

// Refresh all data
async function refreshAllData() {
    console.log('Refreshing all data...');
    
    try {
        // Update refresh button state
        const refreshBtn = document.querySelector('.refresh-btn');
        const icon = refreshBtn.querySelector('i');
        icon.classList.add('fa-spin');
        refreshBtn.disabled = true;
        
        // Fetch data from API
        const response = await fetch(`${API_BASE_URL}/ffd-telemetries`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            globalData = {
                dams: data.dams || [],
                headworks: data.headworks || [],
                lastUpdated: data.last_updated || new Date().toLocaleString()
            };
            
            // Update UI
            updateTimestamp(data.last_updated);
            displayDams(globalData.dams);
            displayHeadworks(globalData.headworks);
            
            // Update status indicators
            updateStatusIndicator('dams-status', 'online');
            updateStatusIndicator('headworks-status', 'online');
            
            console.log(`Loaded ${globalData.dams.length} dams and ${globalData.headworks.length} headworks`);
        } else {
            throw new Error(data.error || 'Failed to fetch data');
        }
        
    } catch (error) {
        console.error('Error refreshing data:', error);
        showError('dams-content', 'Failed to load dam data: ' + error.message);
        showError('headworks-content', 'Failed to load headwork data: ' + error.message);
        
        // Update status indicators
        updateStatusIndicator('dams-status', 'offline');
        updateStatusIndicator('headworks-status', 'offline');
        
    } finally {
        // Reset refresh button
        const refreshBtn = document.querySelector('.refresh-btn');
        const icon = refreshBtn.querySelector('i');
        icon.classList.remove('fa-spin');
        refreshBtn.disabled = false;
    }
}

// Update timestamp
function updateTimestamp(timestamp) {
    const timestampElement = document.getElementById('update-timestamp');
    if (timestampElement) {
        timestampElement.textContent = timestamp || new Date().toLocaleString();
    }
}

// Update status indicator
function updateStatusIndicator(elementId, status) {
    const indicator = document.getElementById(elementId);
    if (indicator) {
        indicator.className = `status-indicator status-${status}`;
    }
}

// Display dams data
function displayDams(dams) {
    const container = document.getElementById('dams-content');
    const countElement = document.getElementById('dams-count');
    
    if (!container) return;
    
    // Update count
    if (countElement) {
        countElement.textContent = dams.length;
    }
    
    if (dams.length === 0) {
        container.innerHTML = '<div class="text-center text-muted">No dam data available</div>';
        return;
    }
    
    // Create table
    let html = `
        <div class="table-responsive">
            <table class="table table-hover table-sm">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Location</th>
                        <th>Water Level (ft)</th>
                        <th>Inflow (cusecs)</th>
                        <th>Outflow (cusecs)</th>
                        <th>Storage (%)</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    dams.forEach((dam, index) => {
        const name = dam.name || 'Unknown';
        const location = dam.location || dam.province || '-';
        const waterLevel = formatValue(dam.water_level || dam.current_level || dam.reservoir_level);
        const inflow = formatValue(dam.inflow);
        const outflow = formatValue(dam.outflow);
        const storage = formatValue(dam.storage_percentage || dam.percentage_filled);
        
        html += `
            <tr>
                <td class="fw-bold">${name}</td>
                <td>${location}</td>
                <td class="data-value">${waterLevel}</td>
                <td class="data-value">${inflow}</td>
                <td class="data-value">${outflow}</td>
                <td class="data-value">${storage}${storage !== '-' ? '%' : ''}</td>
                <td>
                    <div class="chart-container">
                        <canvas id="dam-chart-${index}" width="100" height="40"></canvas>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    container.innerHTML = html;
    
    // Create charts for each dam
    dams.forEach((dam, index) => {
        createMiniChart(`dam-chart-${index}`, generateSampleData(dam));
    });
}

// Display headworks data
function displayHeadworks(headworks) {
    const container = document.getElementById('headworks-content');
    const countElement = document.getElementById('headworks-count');
    
    if (!container) return;
    
    // Update count
    if (countElement) {
        countElement.textContent = headworks.length;
    }
    
    if (headworks.length === 0) {
        container.innerHTML = '<div class="text-center text-muted">No headwork data available</div>';
        return;
    }
    
    // Create table
    let html = `
        <div class="table-responsive">
            <table class="table table-hover table-sm">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Location</th>
                        <th>Water Level (ft)</th>
                        <th>Discharge (cusecs)</th>
                        <th>Gate Position</th>
                        <th>Status</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    headworks.forEach((headwork, index) => {
        const name = headwork.name || 'Unknown';
        const location = headwork.location || headwork.province || '-';
        const waterLevel = formatValue(headwork.water_level || headwork.current_level);
        const discharge = formatValue(headwork.discharge || headwork.outflow);
        const gatePosition = formatValue(headwork.gate_position || headwork.gates);
        const status = headwork.status || 'Operational';
        
        html += `
            <tr>
                <td class="fw-bold">${name}</td>
                <td>${location}</td>
                <td class="data-value">${waterLevel}</td>
                <td class="data-value">${discharge}</td>
                <td class="data-value">${gatePosition}</td>
                <td>
                    <span class="badge ${getStatusBadgeClass(status)}">${status}</span>
                </td>
                <td>
                    <div class="chart-container">
                        <canvas id="headwork-chart-${index}" width="100" height="40"></canvas>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    container.innerHTML = html;
    
    // Create charts for each headwork
    headworks.forEach((headwork, index) => {
        createMiniChart(`headwork-chart-${index}`, generateSampleData(headwork));
    });
}

// Create mini chart for trends
function createMiniChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    // Destroy existing chart if it exists
    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
    }
    
    const ctx = canvas.getContext('2d');
    
    chartInstances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: true,
                    displayColors: false,
                    callbacks: {
                        title: () => '',
                        label: (context) => `Value: ${context.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: {
                    display: false
                },
                y: {
                    display: false,
                    beginAtZero: false
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

// Generate sample data for charts (since we don't have historical data)
function generateSampleData(item) {
    const labels = [];
    const values = [];
    const baseValue = parseFloat(item.water_level || item.current_level || 100);
    
    // Generate 12 data points (representing last 12 hours)
    for (let i = 11; i >= 0; i--) {
        labels.push(`-${i}h`);
        // Generate realistic variations around the base value
        const variation = (Math.random() - 0.5) * 10; // ±5 units variation
        values.push(Math.max(0, baseValue + variation));
    }
    
    return { labels, values };
}

// Format value for display
function formatValue(value) {
    if (value === null || value === undefined || value === '') {
        return '-';
    }
    
    const num = parseFloat(value);
    if (isNaN(num)) {
        return String(value);
    }
    
    // Format numbers with appropriate decimal places
    if (num >= 1000) {
        return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
    } else if (num >= 10) {
        return num.toFixed(1);
    } else {
        return num.toFixed(2);
    }
}

// Get badge class for status
function getStatusBadgeClass(status) {
    const statusLower = (status || '').toLowerCase();
    
    if (statusLower.includes('operational') || statusLower.includes('normal')) {
        return 'bg-success';
    } else if (statusLower.includes('warning') || statusLower.includes('maintenance')) {
        return 'bg-warning';
    } else if (statusLower.includes('critical') || statusLower.includes('offline')) {
        return 'bg-danger';
    } else {
        return 'bg-secondary';
    }
}

// Show error message
function showError(containerId, message) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `<div class="error"><i class="fas fa-exclamation-triangle me-2"></i>${message}</div>`;
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    if (event.key === 'F5' || (event.ctrlKey && event.key === 'r')) {
        event.preventDefault();
        refreshAllData();
    }
});

console.log('Hydrological Dashboard script loaded');
