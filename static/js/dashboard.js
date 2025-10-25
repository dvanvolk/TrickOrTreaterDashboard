// Dashboard state management
let liveStatus = false;
let charts = {};
let historicalData = {};
let currentData = [];
let detailedHistorical = {};
// Snapshot to avoid re-updating charts if data hasn't changed
let _currentDataSnapshot = null;

// Chart colors for different years
const yearColors = {
    2022: '#ff6b35',
    2023: '#4ecdc4', 
    2024: '#45b7d1',
    2025: '#96ceb4'
};

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    setupCharts();
    loadHistoricalData();
    loadDetailedData();
});

// Live status management
function toggleLiveStatus() {
    liveStatus = !liveStatus;
    updateLiveStatusDisplay();
    updateStatsVisibility();
}

function updateLiveStatusDisplay() {
    const statusElement = document.getElementById('liveStatus');
    const statusIndicator = document.getElementById('statusIndicator');
    const liveTimeContainer = document.getElementById('liveTimeContainer');

    if (liveStatus) {
        statusElement.textContent = 'On';
        statusIndicator.className = 'status-indicator status-live';
        if (liveTimeContainer) liveTimeContainer.style.display = 'inline';
    } else {
        statusElement.textContent = 'Off';
        statusIndicator.className = 'status-indicator';
        if (liveTimeContainer) liveTimeContainer.style.display = 'none';
    }
}

function updateStatsVisibility() {
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.style.display = liveStatus ? 'grid' : 'none';
}

// Live timer display is driven by server-reported elapsed time in inline script

// Data loading
async function loadHistoricalData() {
    try {
        const response = await fetch('/historical_data');
        historicalData = await response.json();
        updateYearComparisonChart();
    } catch (error) {
        console.error('Error loading historical data:', error);
    }
}

async function loadCurrentData() {
    try {
        const response = await fetch('/current_data');

        // Handle rate limiting and non-JSON responses gracefully
        if (response.status === 429) {
            console.warn('/current_data returned 429 Too Many Requests');
            return;
        }

        if (!response.ok) {
            console.warn(`/current_data returned HTTP ${response.status}`);
            return;
        }

        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            const text = await response.text();
            console.warn('Unexpected non-JSON response from /current_data:', text.slice(0, 400));
            return;
        }

        const newData = await response.json();

        // Compute a small snapshot (length, sum of counts, last timestamp)
        const newSnapshot = {
            len: newData ? newData.length : 0,
            sum: newData ? newData.reduce((s, e) => s + (e.count || 0), 0) : 0,
            last: (newData && newData.length > 0) ? newData[newData.length - 1].timestamp : null
        };

        // If snapshot unchanged, skip updating charts to avoid visual refresh flicker
        if (_currentDataSnapshot &&
            _currentDataSnapshot.len === newSnapshot.len &&
            _currentDataSnapshot.sum === newSnapshot.sum &&
            _currentDataSnapshot.last === newSnapshot.last) {
            // no change
            return;
        }

        // Update stored data and snapshot
        currentData = newData;
        _currentDataSnapshot = newSnapshot;

        updateTimelineChart();
        updateMinuteChart();
        updateStats();
    } catch (error) {
        console.error('Error loading current data:', error);
    }
}

// Chart setup
function setupCharts() {
    setupMinuteChart();
    setupTimelineChart();
    setupYearComparisonChart();
    setupYearStatsChart();
    setupPeakActivityChart();
    setupDetailedYearChart();
    setupDetailedScatterChart();
}

function setupDetailedScatterChart() {
    const ctx = document.getElementById('detailedScatterChart').getContext('2d');
    charts.detailedScatter = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Visitor',
                data: [],
                backgroundColor: 'rgba(69,183,209,0.9)',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'linear',
                    title: { display: true, text: 'Time of Day' },
                    ticks: {
                        callback: function(value, index, ticks) {
                            // value is minutes since midnight
                            const hh = Math.floor(value / 60) % 24;
                            const mm = Math.round(value % 60);
                            const dt = new Date();
                            dt.setHours(hh, mm, 0, 0);
                            return formatTime(dt);
                        }
                    }
                },
                y: {
                    display: false,
                    suggestedMin: -1,
                    suggestedMax: 3
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const val = context[0].parsed.x;
                            const hh = Math.floor(val / 60) % 24;
                            const mm = Math.floor(val % 60);
                            const dt = new Date(); dt.setHours(hh, mm, 0, 0);
                            return formatTime(dt);
                        },
                        label: function() { return 'Visitor'; }
                    }
                }
            }
        }
    });
}

function setupDetailedYearChart() {
    const ctx = document.getElementById('detailedYearChart').getContext('2d');
    charts.detailedYear = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Arrivals per Minute',
                data: [],
                backgroundColor: '#45b7d1',
                borderColor: '#2b9fb3',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: { display: true, text: 'Time of Day' }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Visitors (per minute)' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: function(context) { return context[0].label; },
                        label: function(context) { return 'Arrivals: ' + context.parsed.y; }
                    }
                }
            }
        }
    });
}

async function loadDetailedData() {
    try {
        const resp = await fetch('/detailed_historical');

        if (resp.status === 429) {
            console.warn('/detailed_historical returned 429 Too Many Requests');
            return;
        }

        if (!resp.ok) {
            console.warn(`/detailed_historical returned HTTP ${resp.status}`);
            return;
        }

        const contentType = resp.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            const text = await resp.text();
            console.warn('Unexpected non-JSON response from /detailed_historical:', text.slice(0, 400));
            return;
        }

        detailedHistorical = await resp.json();
        populateYearSelector();
        updateDetailedYearChart();
        updateDetailedScatterChart();
    } catch (err) {
        console.error('Error loading detailed historical data:', err);
    }
}

    function populateYearSelector() {
        const selector = document.getElementById('yearSelector');
        if (!selector) return;
        // Clear
        selector.innerHTML = '';
        const years = Object.keys(detailedHistorical).map(y => parseInt(y, 10)).sort((a,b) => a - b);
        if (years.length === 0) return;
        // Add options
        years.forEach(y => {
            const opt = document.createElement('option');
            opt.value = String(y);
            opt.textContent = String(y);
            selector.appendChild(opt);
        });
        // Default selection: prefer 2024 if present, else latest
        const preferred = years.includes(2024) ? 2024 : Math.max(...years);
        selector.value = String(preferred);
        // When changed, update charts
        selector.onchange = () => {
            const year = parseInt(selector.value, 10);
            updateDetailedYearChart(year);
            updateDetailedScatterChart(year);
        };
    }

function updateDetailedScatterChart(yearParam) {
    if (!charts.detailedScatter || !detailedHistorical) return;

    const years = Object.keys(detailedHistorical).map(y => parseInt(y, 10));
    if (years.length === 0) return;

    // Determine which year to show: explicit param > selector > prefer 2024 > most recent
    let yearToShow;
    if (typeof yearParam === 'number') yearToShow = yearParam;
    else {
        const selector = document.getElementById('yearSelector');
        if (selector && selector.value) yearToShow = parseInt(selector.value, 10);
        else yearToShow = years.includes(2024) ? 2024 : Math.max(...years);
    }

    const entries = detailedHistorical[yearToShow] || [];

    // Create scatter points: x = minutes since midnight (including fractional), y = small jitter
    const points = [];
    entries.forEach((e, idx) => {
        let ts = e.timestamp;
        if (!ts) return;
        ts = ts.replace('Z', '');
        const d = new Date(ts);
        const minutes = d.getHours() * 60 + d.getMinutes() + (d.getSeconds() / 60);
        // small deterministic jitter based on index to separate overlapping points
        const jitter = ((idx % 5) - 2) * 0.18; // values between -0.36..0.36
        points.push({ x: minutes, y: 1 + jitter });
    });

    charts.detailedScatter.data.datasets[0].data = points;

    // Optionally adjust x-axis range to fit data
    if (points.length > 0) {
        const xs = points.map(p => p.x);
        const minX = Math.min(...xs) - 5; // pad 5 minutes
        const maxX = Math.max(...xs) + 5;
        charts.detailedScatter.options.scales.x.min = Math.max(0, minX);
        charts.detailedScatter.options.scales.x.max = Math.min(24 * 60, maxX);
    }

    charts.detailedScatter.update();
}

function updateDetailedYearChart(yearParam) {
    if (!charts.detailedYear || !detailedHistorical) return;

    const years = Object.keys(detailedHistorical).map(y => parseInt(y, 10));
    if (years.length === 0) return;

    let yearToShow;
    if (typeof yearParam === 'number') yearToShow = yearParam;
    else {
        const selector = document.getElementById('yearSelector');
        if (selector && selector.value) yearToShow = parseInt(selector.value, 10);
        else yearToShow = years.includes(2024) ? 2024 : Math.max(...years);
    }

    // Update label in UI
    const labelEl = document.getElementById('detailedYearLabel');
    if (labelEl) labelEl.textContent = String(yearToShow);

    const entries = detailedHistorical[yearToShow] || [];

    // Compute counts per minute (HH:MM)
    const minuteCounts = {};
    entries.forEach(e => {
        // Normalize timestamp
        let ts = e.timestamp;
        if (!ts) return;
        ts = ts.replace('Z', '');
        const d = new Date(ts);
        const minuteKey = `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
        minuteCounts[minuteKey] = (minuteCounts[minuteKey] || 0) + (e.count || 1);
    });

    // Sort minute keys
    const sortedKeys = Object.keys(minuteCounts).sort();
    const labels = sortedKeys.map(k => {
        const [hh, mm] = k.split(':');
        const dt = new Date();
        dt.setHours(parseInt(hh,10), parseInt(mm,10), 0, 0);
        return formatTime(dt);
    });
    const data = sortedKeys.map(k => minuteCounts[k]);

    charts.detailedYear.data.labels = labels;
    charts.detailedYear.data.datasets[0].data = data;
    charts.detailedYear.update();
}

function setupMinuteChart() {
    const ctx = document.getElementById('minuteChart').getContext('2d');
    charts.minute = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Trick-or-Treaters',
                data: [],
                backgroundColor: '#ff6b35',
                borderColor: '#ff6b35',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

function setupTimelineChart() {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    charts.timeline = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Running Total',
                data: [],
                borderColor: '#4ecdc4',
                backgroundColor: 'rgba(78, 205, 196, 0.1)',
                tension: 0, // No smoothing for step pattern
                fill: true,
                pointRadius: 3,
                pointHoverRadius: 5,
                stepped: 'after' // Create step pattern
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Total Trick-or-Treaters'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            return 'Time: ' + context[0].label;
                        },
                        label: function(context) {
                            return 'Total: ' + context.parsed.y + ' visitors';
                        }
                    }
                }
            }
        }
    });
}

function setupYearComparisonChart() {
    const ctx = document.getElementById('yearComparisonChart').getContext('2d');
    charts.yearComparison = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: []
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Time of Day'
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0,0,0,0.1)'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Trick-or-Treaters'
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0,0,0,0.1)'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                title: {
                    display: true,
                    text: 'Year-over-Year Comparison: Trick-or-Treater Activity by Time',
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: 'white',
                    bodyColor: 'white',
                    borderColor: 'rgba(255,255,255,0.2)',
                    borderWidth: 1,
                    callbacks: {
                        title: function(context) {
                            return 'Time: ' + context[0].label;
                        },
                        label: function(context) {
                            return context.dataset.label + ': ' + context.parsed.y + ' visitors';
                        }
                    }
                }
            },
            elements: {
                line: {
                    tension: 0.4,
                    borderWidth: 3
                },
                point: {
                    radius: 5,
                    hoverRadius: 8,
                    borderWidth: 2
                }
            }
        }
    });
}

function setupYearStatsChart() {
    const ctx = document.getElementById('yearStatsChart').getContext('2d');
    charts.yearStats = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Total Trick-or-Treaters',
                data: [],
                backgroundColor: '#4ecdc4',
                borderColor: '#4ecdc4',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Total Count'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Year'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Total Trick-or-Treaters by Year'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Total: ' + context.parsed.y + ' visitors';
                        }
                    }
                }
            }
        }
    });
}

function setupPeakActivityChart() {
    const ctx = document.getElementById('peakActivityChart').getContext('2d');
    charts.peakActivity = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#ff6b35',
                    '#4ecdc4', 
                    '#45b7d1',
                    '#96ceb4',
                    '#feca57',
                    '#ff9ff3'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true
                    }
                },
                title: {
                    display: true,
                    text: 'Peak Activity Distribution'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed;
                            return label + ': ' + value + ' visitors';
                        }
                    }
                }
            }
        }
    });
}

// Chart updates
function updateYearComparisonChart() {
    if (!charts.yearComparison || !historicalData) return;
    
    const timeSlots = [];
    const datasets = [];
    
    // Get all unique time slots
    const allTimeSlots = new Set();
    Object.values(historicalData).forEach(yearData => {
        Object.keys(yearData).forEach(timeSlot => allTimeSlots.add(timeSlot));
    });
    
    // Sort time slots
    const sortedTimeSlots = Array.from(allTimeSlots).sort();
    
    // Format time slots to 12-hour format
    const formattedTimeSlots = sortedTimeSlots.map(timeSlot => {
        const [hours, minutes] = timeSlot.split(':');
        const date = new Date();
        date.setHours(parseInt(hours), parseInt(minutes), 0, 0);
        return formatTime(date);
    });
    
    // Create dataset for each year
    Object.entries(historicalData).forEach(([year, yearData]) => {
        const data = sortedTimeSlots.map(timeSlot => {
            return yearData[timeSlot] ? yearData[timeSlot].average : 0;
        });
        
        datasets.push({
            label: year,
            data: data,
            borderColor: yearColors[year] || '#666',
            backgroundColor: yearColors[year] + '20' || '#66620',
            tension: 0.4,
            pointRadius: 4,
            pointHoverRadius: 6
        });
    });
    
    charts.yearComparison.data.labels = formattedTimeSlots;
    charts.yearComparison.data.datasets = datasets;
    charts.yearComparison.update();
    
    // Update additional charts
    updateYearStatsChart();
    updatePeakActivityChart();
}

function updateTimelineChart() {
    if (!charts.timeline || !currentData) return;
    
    // Create minute-by-minute data
    const minuteData = {};
    let runningTotal = 0;
    
    // Process each entry and group by minute
    currentData.forEach(entry => {
        // Remove 'Z' suffix and treat as local time
        const timestamp = entry.timestamp.replace('Z', '');
        const date = new Date(timestamp);
        const minuteKey = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
        
        if (!minuteData[minuteKey]) {
            minuteData[minuteKey] = 0;
        }
        minuteData[minuteKey] += entry.count;
    });
    
    // Get all minutes from first to last entry
    if (currentData.length > 0) {
        const firstTimestamp = currentData[0].timestamp.replace('Z', '');
        const lastTimestamp = currentData[currentData.length - 1].timestamp.replace('Z', '');
        const firstEntry = new Date(firstTimestamp);
        const lastEntry = new Date(lastTimestamp);
        
        const labels = [];
        const data = [];
        
        // Create minute-by-minute timeline
        const startMinute = new Date(firstEntry.getFullYear(), firstEntry.getMonth(), firstEntry.getDate(), firstEntry.getHours(), firstEntry.getMinutes());
        const endMinute = new Date(lastEntry.getFullYear(), lastEntry.getMonth(), lastEntry.getDate(), lastEntry.getHours(), lastEntry.getMinutes());
        
        for (let current = new Date(startMinute); current <= endMinute; current.setMinutes(current.getMinutes() + 1)) {
            // Format time in 12-hour format
            const timeString = formatTime(current);
            
            // Also create minute key for data lookup
            const minuteKey = `${current.getHours().toString().padStart(2, '0')}:${current.getMinutes().toString().padStart(2, '0')}`;
            
            // Add any new arrivals for this minute
            if (minuteData[minuteKey]) {
                runningTotal += minuteData[minuteKey];
            }
            
            labels.push(timeString);
            data.push(runningTotal);
        }
        
        charts.timeline.data.labels = labels;
        charts.timeline.data.datasets[0].data = data;
        charts.timeline.update();
    }
}

function updateMinuteChart() {
    if (!charts.minute || !currentData) return;
    
    // Group data by 10-minute intervals
    const minuteGroups = {};
    currentData.forEach(entry => {
        const date = new Date(entry.timestamp);
        const minutes = Math.floor(date.getMinutes() / 10) * 10;
        const timeKey = `${date.getHours().toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        
        if (!minuteGroups[timeKey]) {
            minuteGroups[timeKey] = 0;
        }
        minuteGroups[timeKey] += entry.count;
    });
    
    // Sort labels and convert to 12-hour format
    const sortedLabels = Object.keys(minuteGroups).sort();
    const formattedLabels = sortedLabels.map(label => {
        const [hours, minutes] = label.split(':');
        const date = new Date();
        date.setHours(parseInt(hours), parseInt(minutes), 0, 0);
        return formatTime(date);
    });
    const data = sortedLabels.map(label => minuteGroups[label]);
    
    charts.minute.data.labels = formattedLabels;
    charts.minute.data.datasets[0].data = data;
    charts.minute.update();
}

function updateStats() {
    if (!currentData || currentData.length === 0) return;
    
    // Calculate total today
    const totalToday = currentData.reduce((sum, entry) => sum + entry.count, 0);
    document.getElementById('totalToday').textContent = totalToday;
    
    // Calculate current 5-minute period
    const now = new Date();
    const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000);
    
    const recentData = currentData.filter(entry => {
        // Remove 'Z' suffix and treat as local time
        const timestamp = entry.timestamp.replace('Z', '');
        const entryTime = new Date(timestamp);
        return entryTime >= fiveMinutesAgo;
    });
    const currentMinute = recentData.reduce((sum, entry) => sum + entry.count, 0);
    document.getElementById('currentMinute').textContent = currentMinute;
    
    // Calculate peak 10-minute period
    let maxPeak = 0;
    for (let i = 0; i < currentData.length - 1; i++) {
        const windowData = currentData.slice(i, i + 2); // 10-minute window
        const windowSum = windowData.reduce((sum, entry) => sum + entry.count, 0);
        maxPeak = Math.max(maxPeak, windowSum);
    }
    document.getElementById('peakMinute').textContent = maxPeak;
    
    // Calculate average per minute
    const avgPerMinute = totalToday / Math.max(currentData.length, 1);
    document.getElementById('avgPerMinute').textContent = avgPerMinute.toFixed(1);
    
    // Last visitor time
    if (currentData.length > 0) {
        const lastEntry = currentData[currentData.length - 1];
        // Remove 'Z' suffix and treat as local time
        const timestamp = lastEntry.timestamp.replace('Z', '');
        const lastTime = formatTime(new Date(timestamp), { seconds: true });
        document.getElementById('lastVisitor').textContent = lastTime;
    }
}

function updateYearStatsChart() {
    if (!charts.yearStats || !historicalData) return;
    
    const years = Object.keys(historicalData).sort();
    const totals = years.map(year => {
        return Object.values(historicalData[year]).reduce((sum, timeData) => sum + timeData.total, 0);
    });
    
    charts.yearStats.data.labels = years;
    charts.yearStats.data.datasets[0].data = totals;
    charts.yearStats.update();
}

function updatePeakActivityChart() {
    if (!charts.peakActivity || !historicalData) return;
    
    // Find the top 6 most active time slots across all years
    const timeSlotTotals = {};
    Object.values(historicalData).forEach(yearData => {
        Object.entries(yearData).forEach(([timeSlot, data]) => {
            if (!timeSlotTotals[timeSlot]) {
                timeSlotTotals[timeSlot] = 0;
            }
            timeSlotTotals[timeSlot] += data.total;
        });
    });
    
    // Sort by total activity and take top 6
    const topTimeSlots = Object.entries(timeSlotTotals)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 6);
    
    // Format peak time slots to 12-hour format for labels
    const labels = topTimeSlots.map(([timeSlot]) => {
        const [hours, minutes] = timeSlot.split(':');
        const d = new Date();
        d.setHours(parseInt(hours, 10), parseInt(minutes, 10), 0, 0);
        return formatTime(d);
    });
    const data = topTimeSlots.map(([, total]) => total);
    
    charts.peakActivity.data.labels = labels;
    charts.peakActivity.data.datasets[0].data = data;
    charts.peakActivity.update();
}

// Auto-refresh data when live
setInterval(() => {
    if (liveStatus) {
        loadCurrentData();
        // Refresh detailed chart periodically while live
        loadDetailedData();
    }
}, 2000); // Update every 2 seconds when live

// Manual controls removed from UI

// Check serial status
async function checkSerialStatus() {
    try {
        const response = await fetch('/stats');
        const data = await response.json();
        // Log serial connection status to console for debugging
        console.debug('Serial connected:', data.serial_connected);

        return data.serial_connected;
    } catch (error) {
        console.error('Error checking serial status:', error);
        return false;
    }
}

// Initialize dashboard
function initializeDashboard() {
    updateLiveStatusDisplay();
    updateStatsVisibility();
    // Serial status UI removed; continue to log status to console for debugging
    checkSerialStatus();
    setInterval(checkSerialStatus, 10000);
}