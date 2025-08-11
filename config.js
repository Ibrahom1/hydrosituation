// API Configuration for local development
const API_BASE_URL = 'http://localhost:5000';

// Optional remote dataset URL (will be synced into local DB before refresh)
const REMOTE_DATA_URL = window.REMOTE_DATA_URL || null; // set in index.html if desired

// Attempt remote sync (no-op if not configured)
async function attemptRemoteSync() {
    if (!REMOTE_DATA_URL) return;
    try {
        console.log('Attempting remote sync from dataset...');
        const res = await fetch(`${API_BASE_URL}/api/sync-remote?url=${encodeURIComponent(REMOTE_DATA_URL)}`);
        const data = await res.json();
        if (data.success) {
            console.log('Remote dataset applied:', data.message);
        } else {
            console.warn('Remote sync failed:', data.error);
        }
    } catch (e) {
        console.warn('Remote sync error', e);
    }
}

// API functions
async function fetchHistoricalSeries(name, hours = 24) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/history?name=${encodeURIComponent(name)}&hours=${hours}`);
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

// Update main refresh function
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
        
    // Try remote sync first (hybrid approach)
    await attemptRemoteSync();

    // Destroy existing charts
        Object.values(chartsInstances).forEach(chart => chart.destroy());
        chartsInstances = {};
        
        // Fetch data with updated URLs
        const [damsResponse, headworksResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/api/ffd-dams`),
            fetch(`${API_BASE_URL}/api/ffd-headworks`)
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
