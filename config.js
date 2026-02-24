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

        const parseHistoryPointTime = (raw) => {
            if (!raw) return null;
            const value = String(raw).trim();
            const match = value.match(/^(\d{1,2})-([A-Za-z]{3})(?:-(\d{2,4}))?\s+(\d{1,2})(?::(\d{2}))?\s*(PKT|PST)?\s*$/i);
            if (match) {
                const monthMap = {
                    Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5,
                    Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11
                };
                const monthText = match[2].slice(0, 1).toUpperCase() + match[2].slice(1, 3).toLowerCase();
                const monthIndex = monthMap[monthText];
                if (monthIndex === undefined) return null;

                const currentYear = new Date().getFullYear();
                let year = currentYear;
                if (match[3]) {
                    const parsedYear = Number(match[3]);
                    if (!Number.isNaN(parsedYear)) {
                        year = match[3].length === 2 ? 2000 + parsedYear : parsedYear;
                    }
                }

                const day = Number(match[1]);
                const hour = Number(match[4]);
                const minute = match[5] !== undefined ? Number(match[5]) : 0;
                const dt = new Date(year, monthIndex, day, hour, minute, 0, 0);
                return Number.isNaN(dt.getTime()) ? null : dt;
            }

            const nativeParsed = new Date(value);
            return Number.isNaN(nativeParsed.getTime()) ? null : nativeParsed;
        };

        const inflow = data.inflow
            .map(p => ({ x: parseHistoryPointTime(p.x), y: p.y }))
            .filter(p => p.x instanceof Date && !Number.isNaN(p.x.getTime()));
        const outflow = data.outflow
            .map(p => ({ x: parseHistoryPointTime(p.x), y: p.y }))
            .filter(p => p.x instanceof Date && !Number.isNaN(p.x.getTime()));

        return {
            inflow,
            outflow
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
