// API Base URL - Change this to your Flask backend URL
const API_BASE_URL = 'http://localhost:5000/api';

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initializing...');
    setupEventListeners();
    calculatePercentages();
    updateHeaderWithCurrentDate();
    
    // Load current media after a short delay to ensure all elements are ready
    setTimeout(() => {
        loadCurrentMedia();
    }, 500);
    
    // Load FFD dam data
    loadFFDDamData();
    
    // Load custom dashboard data
    loadCustomDashboardData();
    
    // Auto-refresh every 5 minutes (but keep the date updated)
    setInterval(() => {
        updateHeaderWithCurrentDate();
        loadFFDDamData(); // Also refresh dam data
        loadCustomDashboardData(); // Also refresh custom data
    }, 300000);
    
    console.log('Dashboard initialized');
});


// Display uploaded media in map projection area
function displayMedia(filename, fileType) {
    const mediaDisplay = document.getElementById('media-display');
    const placeholderContent = document.getElementById('placeholder-content');
    const uploadedImage = document.getElementById('uploaded-image');
    const uploadedVideo = document.getElementById('uploaded-video');
    const mediaInfo = document.getElementById('media-info');
    const mediaFilename = document.getElementById('media-filename');
    
    console.log('DisplayMedia called with:', filename, fileType);
    console.log('Elements found:', {
        mediaDisplay: !!mediaDisplay,
        placeholderContent: !!placeholderContent,
        uploadedImage: !!uploadedImage,
        uploadedVideo: !!uploadedVideo
    });
    
    if (!mediaDisplay || !placeholderContent) {
        console.error('Required elements not found');
        return;
    }
    
    // Hide placeholder
    placeholderContent.style.display = 'none';
    
    // Show media display
    mediaDisplay.style.display = 'block';
    mediaDisplay.classList.remove('d-none');
    
    // Hide both media elements initially
    if (uploadedImage) {
        uploadedImage.style.display = 'none';
        uploadedImage.classList.add('d-none');
    }
    if (uploadedVideo) {
        uploadedVideo.style.display = 'none';
        uploadedVideo.classList.add('d-none');
    }
    
    const mediaURL = `${API_BASE_URL}/media/${filename}`;
    console.log('Media URL:', mediaURL);
    
    if (fileType.startsWith('image/')) {
        if (uploadedImage) {
            uploadedImage.src = mediaURL;
            uploadedImage.style.display = 'block';
            uploadedImage.classList.remove('d-none');
            console.log('Image displayed');
        }
    } else if (fileType.startsWith('video/')) {
        if (uploadedVideo) {
            uploadedVideo.src = mediaURL;
            uploadedVideo.style.display = 'block';
            uploadedVideo.classList.remove('d-none');
            console.log('Video displayed');
        }
    }
    
    // Show filename
    if (mediaFilename) {
        mediaFilename.textContent = filename;
    }
    if (mediaInfo) {
        mediaInfo.classList.remove('d-none');
    }
}

// Load FFD dam data and populate table
async function loadFFDDamData() {
    try {
        showNotification('Updating dam data...', 'info');
        
        const response = await fetch(`${API_BASE_URL}/ffd-dam-data`);
        const result = await response.json();
        
        if (response.ok && result.success && result.dams) {
            populateDamTable(result.dams);
            showNotification('Dam data updated successfully!', 'success');
        } else {
            showNotification(`Failed to fetch dam data: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error loading FFD dam data:', error);
        showNotification('Error loading dam data', 'error');
    }
}

// Populate dam table with FFD data
function populateDamTable(damData) {
    // Map of dam names to table rows
    const damRowMap = {
        'Tarbela': 0,
        'Mangla': 1,
        'Chashma': 2
    };
    
    const tableBody = document.querySelector('.card:first-child tbody');
    if (!tableBody) return;
    
    const rows = tableBody.querySelectorAll('tr');
    
    // Update each dam row with FFD data
    Object.keys(damRowMap).forEach(damName => {
        const data = damData[damName];
        const rowIndex = damRowMap[damName];
        const row = rows[rowIndex];
        
        if (data && row) {
            // Update current level input
            const currentLevelInput = row.cells[2].querySelector('input');
            if (currentLevelInput && data.current_level !== 'n/a') {
                currentLevelInput.value = data.current_level;
                currentLevelInput.placeholder = data.current_level.toString();
            }
            
            // Update inflow input
            const inflowInput = row.cells[3].querySelector('input');
            if (inflowInput && data.inflow_discharge !== 'n/a') {
                const formattedInflow = formatNumber(data.inflow_discharge);
                inflowInput.value = formattedInflow;
                inflowInput.placeholder = formattedInflow;
            }
            
            // Update outflow input
            const outflowInput = row.cells[4].querySelector('input');
            if (outflowInput && data.outflow_discharge !== 'n/a') {
                const formattedOutflow = formatNumber(data.outflow_discharge);
                outflowInput.value = formattedOutflow;
                outflowInput.placeholder = formattedOutflow;
            }
            
            // Update percentage badge
            const percentageBadge = row.cells[5].querySelector('.percentage-badge');
            if (percentageBadge && data.percentage_filled !== 'n/a') {
                percentageBadge.textContent = `${data.percentage_filled}%`;
                percentageBadge.className = `badge percentage-badge fs-6 px-3 py-2 ${data.badge_class}`;
            }
            
            // Add tooltip with additional information
            const damNameCell = row.cells[0];
            if (damNameCell) {
                damNameCell.setAttribute('title', 
                    `Status: ${data.status || 'n/a'}\n` +
                    `Recording Time: ${data.recording_time || 'n/a'}\n` +
                    `Inflow Trend: ${data.inflow_trend || 'n/a'}\n` +
                    `Outflow Trend: ${data.outflow_trend || 'n/a'}`
                );
                damNameCell.setAttribute('data-bs-toggle', 'tooltip');
                damNameCell.setAttribute('data-bs-placement', 'top');
            }
        }
    });
    
    // Reinitialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Format numbers with commas for display
function formatNumber(value) {
    if (value === 'n/a' || value === null || value === undefined) {
        return 'n/a';
    }
    
    try {
        const num = parseFloat(value);
        if (isNaN(num)) return 'n/a';
        return num.toLocaleString();
    } catch (error) {
        console.warn('Error formatting number:', value, error);
        return value.toString();
    }
}

// Load custom dashboard data and populate forms
async function loadCustomDashboardData() {
    try {
        console.log('Loading custom dashboard data...');
        const response = await fetch(`${API_BASE_URL}/custom-dashboard-data`);
        const result = await response.json();
        
        console.log('Custom dashboard data response:', result);
        
        if (response.ok && result.success && result.data) {
            console.log('Populating custom data:', result.data);
            populateCustomData(result.data);
            console.log('Custom dashboard data loaded successfully');
        } else {
            console.log('No custom dashboard data found or failed to load:', result);
        }
    } catch (error) {
        console.error('Error loading custom dashboard data:', error);
    }
}

// Populate custom data into form fields
function populateCustomData(data) {
    console.log('Populating custom data with:', data);
    
    // Store the custom data globally for percentage calculations
    window.customDashboardData = data;
    
    // Populate Pakistan dams data
    if (data.pakistan_dams) {
        console.log('Populating Pakistan dams:', data.pakistan_dams);
        // Find Pakistan dams table by looking for the card with "Pakistan Dams" title
        const pakistanCard = Array.from(document.querySelectorAll('.card')).find(card => {
            const title = card.querySelector('.card-title');
            return title && title.textContent.includes('Pakistan Dams');
        });
        
        console.log('Pakistan card found:', !!pakistanCard);
        
        if (pakistanCard) {
            const pakistanTable = pakistanCard.querySelector('tbody');
            console.log('Pakistan table found:', !!pakistanTable);
            if (pakistanTable) {
                const rows = pakistanTable.querySelectorAll('tr');
                console.log('Pakistan rows found:', rows.length);
                
                // Map dam names to row indices
                const damRowMap = {
                    'Tarbela': 0,
                    'Mangla': 1, 
                    'Chashma': 2
                };
                
                Object.keys(data.pakistan_dams).forEach(damName => {
                    const damData = data.pakistan_dams[damName];
                    const rowIndex = damRowMap[damName];
                    const row = rows[rowIndex];
                    
                    console.log(`Processing ${damName}:`, damData, 'Row found:', !!row);
                    
                    if (row && damData) {
                        // Update current level input if value exists
                        const currentLevelInput = row.cells[2].querySelector('input');
                        console.log(`${damName} input found:`, !!currentLevelInput, 'Current level:', damData.current_level);
                        if (currentLevelInput && damData.current_level) {
                            currentLevelInput.value = damData.current_level;
                            currentLevelInput.placeholder = damData.current_level;
                            console.log(`${damName} level updated to:`, damData.current_level);
                        }
                        
                        // Update percentage badge with manual percentage or calculate if not provided
                        const percentageBadge = row.querySelector('.percentage-badge');
                        if (percentageBadge) {
                            if (damData.fill_percentage) {
                                percentageBadge.textContent = `${damData.fill_percentage}%`;
                                percentageBadge.className = 'badge percentage-badge bg-primary text-white';
                            } else {
                                // Recalculate percentage for the row
                                calculateRowPercentage(row);
                            }
                        }
                    }
                });
            }
        }
    }
    
    // Populate Indian dams data
    if (data.indian_dams) {
        // Find Indian dams table by looking for the card with "Indian Dams" title
        const indianCard = Array.from(document.querySelectorAll('.card')).find(card => {
            const title = card.querySelector('.card-title');
            return title && title.textContent.includes('Indian Dams');
        });
        
        if (indianCard) {
            const indianTable = indianCard.querySelector('tbody');
            if (indianTable) {
                const rows = indianTable.querySelectorAll('tr');
                
                // Map dam names to row indices
                const damRowMap = {
                    'Pong': 0,
                    'Bhakra': 1,
                    'Thein': 2
                };
                
                Object.keys(data.indian_dams).forEach(damName => {
                    const damData = data.indian_dams[damName];
                    const rowIndex = damRowMap[damName];
                    const row = rows[rowIndex];
                    
                    if (row && damData) {
                        // Update current level input
                        const currentLevelInput = row.cells[2].querySelector('input');
                        if (currentLevelInput && damData.current_level) {
                            currentLevelInput.value = damData.current_level;
                            currentLevelInput.placeholder = damData.current_level;
                        }
                        
                        // Update percentage badge with manual percentage or calculate if not provided
                        const percentageBadge = row.cells[3].querySelector('.percentage-badge');
                        if (percentageBadge) {
                            if (damData.fill_percentage) {
                                percentageBadge.textContent = `${damData.fill_percentage}%`;
                                percentageBadge.className = 'badge percentage-badge fs-6 px-3 py-2 bg-primary text-white';
                            } else {
                                // Recalculate percentage for Indian dam
                                calculateIndianDamPercentage(row, damName);
                            }
                        }
                    }
                });
            }
        }
    }
    
    // Populate weather forecast data
    if (data.weather_forecast) {
        // Find weather forecast table by looking for the card with "Weather Forecast" title
        const weatherCard = Array.from(document.querySelectorAll('.card')).find(card => {
            const title = card.querySelector('.card-title');
            return title && title.textContent.includes('Weather Forecast');
        });
        
        if (weatherCard) {
            const weatherTable = weatherCard.querySelector('tbody');
            if (weatherTable) {
                const rows = weatherTable.querySelectorAll('tr');
                
                // Map province names to row indices
                const provinceRowMap = {
                    'AJ&K': 0,
                    'Islamabad': 1,
                    'GB': 2,
                    'KP': 3,
                    'Punjab': 4,
                    'Sindh': 5,
                    'Balochistan': 6
                };
                
                Object.keys(data.weather_forecast).forEach(province => {
                    const forecast = data.weather_forecast[province];
                    const rowIndex = provinceRowMap[province];
                    const row = rows[rowIndex];
                    
                    if (row && forecast) {
                        const inputField = row.cells[1].querySelector('input');
                        if (inputField) {
                            inputField.value = forecast;
                            inputField.placeholder = forecast;
                        }
                    }
                });
            }
        }
    }
}

// Calculate percentage for Indian dams
function calculateIndianDamPercentage(row, damName) {
    const percentageBadge = row.cells[3].querySelector('.percentage-badge');
    
    if (percentageBadge) {
        // Check if we have custom data loaded with manual percentage
        if (window.customDashboardData && 
            window.customDashboardData.indian_dams && 
            window.customDashboardData.indian_dams[damName] &&
            window.customDashboardData.indian_dams[damName].fill_percentage) {
            
            const manualPercentage = window.customDashboardData.indian_dams[damName].fill_percentage;
            percentageBadge.textContent = `${manualPercentage}%`;
            percentageBadge.className = 'badge percentage-badge fs-6 px-3 py-2 bg-primary text-white';
            return;
        }
        
        // Fallback to calculated percentage if no manual percentage is set
        const maxLevels = {
            'Pong': 1390,
            'Bhakra': 1680,
            'Thein': 1732
        };
        
        const currentLevelInput = row.cells[2].querySelector('input');
        
        if (currentLevelInput) {
            const maxLevel = maxLevels[damName];
            const currentLevel = parseFloat(currentLevelInput.value);
            
            if (!isNaN(currentLevel) && maxLevel > 0) {
                const percentage = Math.round((currentLevel / maxLevel) * 100);
                percentageBadge.textContent = `${percentage}%`;
                percentageBadge.className = 'badge percentage-badge fs-6 px-3 py-2 bg-primary text-white';
            }
        }
    }
}

// Manual refresh function for dam data
function refreshDamData() {
    loadFFDDamData();
    loadCustomDashboardData();
}

// Load current media on page load
async function loadCurrentMedia() {
    try {
        console.log('Loading current media...');
        const response = await fetch(`${API_BASE_URL}/current-media`);
        console.log('Current media response:', response.status);
        
        if (response.ok) {
            const result = await response.json();
            console.log('Current media result:', result);
            
            if (result.filename && result.file_type) {
                console.log('Displaying current media:', result.filename);
                displayMedia(result.filename, result.file_type);
            } else {
                console.log('No current media found');
            }
        }
    } catch (error) {
        console.error('Failed to load current media:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    // Auto-calculate percentages when current levels change
    const currentLevelInputs = document.querySelectorAll('input[type="number"]');
    currentLevelInputs.forEach(input => {
        input.addEventListener('input', function() {
            const row = this.closest('tr');
            calculateRowPercentage(row);
        });
    });

    // Form validation
    const forms = document.querySelectorAll('input, textarea');
    forms.forEach(form => {
        form.addEventListener('blur', validateInput);
    });
}

// Calculate percentage for a specific row
function calculateRowPercentage(row) {
    const percentageBadge = row.querySelector('.percentage-badge');
    
    if (percentageBadge) {
        // For Pakistan dams, get percentage from custom data if available
        const damNameCell = row.cells[0];
        if (damNameCell) {
            const damName = damNameCell.textContent.trim();
            
            // Check if we have custom data loaded with manual percentage
            if (window.customDashboardData && 
                window.customDashboardData.pakistan_dams && 
                window.customDashboardData.pakistan_dams[damName] &&
                window.customDashboardData.pakistan_dams[damName].fill_percentage) {
                
                const manualPercentage = window.customDashboardData.pakistan_dams[damName].fill_percentage;
                percentageBadge.textContent = `${manualPercentage}%`;
                percentageBadge.className = 'badge percentage-badge bg-primary text-white';
                return;
            }
        }
        
        // Fallback to calculated percentage if no manual percentage is set
        const maxLevelCell = row.cells[1];
        const currentLevelInput = row.querySelector('input[type="number"]');
        
        if (maxLevelCell && currentLevelInput) {
            const maxLevel = parseFloat(maxLevelCell.textContent);
            const currentLevel = parseFloat(currentLevelInput.value);
            
            if (!isNaN(maxLevel) && !isNaN(currentLevel) && maxLevel > 0) {
                const percentage = Math.round((currentLevel / maxLevel) * 100);
                percentageBadge.textContent = `${percentage}%`;
                percentageBadge.className = 'badge percentage-badge bg-primary text-white';
            }
        }
    }
}

// Calculate all percentages on load
function calculatePercentages() {
    const rows = document.querySelectorAll('tbody tr');
    rows.forEach(row => {
        calculateRowPercentage(row);
    });
}

// Validate input fields
function validateInput(event) {
    const input = event.target;
    const value = input.value;
    
    if (input.type === 'number') {
        if (value < 0) {
            input.value = 0;
            showNotification('Negative values are not allowed', 'error');
        }
    }
    
    if (input.tagName === 'TEXTAREA') {
        if (value.length > 500) {
            input.value = value.substring(0, 500);
            showNotification('Text limit reached (500 characters)', 'warning');
        }
    }
}

// Control Panel Functions
function updateData() {
    showNotification('Updating data...', 'info');
    
    // Update FFD dam data
    loadFFDDamData();
    
    // Update custom dashboard data
    loadCustomDashboardData();
    
    // Update header with current date
    updateHeaderWithCurrentDate();
    
    setTimeout(() => {
        showNotification('Data updated successfully!', 'success');
    }, 2000);
}

function exportData() {
    const data = {
        timestamp: new Date().toISOString(),
        pakistanDams: [],
        indianDams: [],
        weatherForecast: []
    };
    
    // Collect Pakistan dams data
    const pakistanRows = document.querySelectorAll('.card:first-child tbody tr');
    pakistanRows.forEach(row => {
        const cells = row.cells;
        data.pakistanDams.push({
            name: cells[0].textContent,
            maxLevel: cells[1].textContent,
            currentLevel: cells[2].querySelector('input')?.value || '',
            inflow: cells[3].querySelector('input')?.value || '',
            outflow: cells[4].querySelector('input')?.value || '',
            percentage: cells[5].textContent
        });
    });
    
    // Collect Indian dams data
    const indianRows = document.querySelectorAll('.card:nth-child(2) tbody tr');
    indianRows.forEach(row => {
        const cells = row.cells;
        data.indianDams.push({
            name: cells[0].textContent,
            maxLevel: cells[1].textContent,
            currentLevel: cells[2].querySelector('input')?.value || '',
            percentage: cells[3].textContent
        });
    });
    
    // Collect weather forecast data
    const weatherRows = document.querySelectorAll('.card:nth-child(3) tbody tr');
    weatherRows.forEach(row => {
        const cells = row.cells;
        data.weatherForecast.push({
            province: cells[0].textContent,
            forecast: cells[1].querySelector('input')?.value || ''
        });
    });
    
    // Download as JSON
    const dataStr = JSON.stringify(data, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `situation_update_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    
    showNotification('Data exported successfully!', 'success');
}

// Update header with current date but keep static time
function updateHeaderWithCurrentDate() {
    const now = new Date();
    const dateString = now.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
    
    const headerElement = document.getElementById('situation-update-title');
    if (headerElement) {
        headerElement.innerHTML = `Situation Update - 20:00 Hours ${dateString}`;
    }
}

// Update timestamp in header (kept for backward compatibility but modified)
function updateTimestamp() {
    updateHeaderWithCurrentDate();
}

// Show notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Real-time clock
setInterval(() => {
    const now = new Date();
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = now.toLocaleTimeString();
    }
}, 1000);

// Responsive table handling
function handleResponsiveTable() {
    const tables = document.querySelectorAll('.table');
    tables.forEach(table => {
        if (window.innerWidth < 768) {
            table.style.fontSize = '0.7rem';
        } else {
            table.style.fontSize = '';
        }
    });
}

// Handle window resize
window.addEventListener('resize', handleResponsiveTable);

// Print functionality
function printReport() {
    window.print();
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey) {
        switch(e.key) {
            case 's':
                e.preventDefault();
                exportData();
                break;
            case 'r':
                e.preventDefault();
                updateData();
                break;
            case 'p':
                e.preventDefault();
                printReport();
                break;
        }
    }
});

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
