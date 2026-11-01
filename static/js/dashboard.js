// Dashboard state management
let liveStatus = false;
let charts = {};
let historicalData = {};
let currentData = [];
let detailedHistorical = {};
// Snapshot to avoid re-updating charts if data hasn't changed
let _currentDataSnapshot = null;
let _detailedHistoricalSnapshot = null;
// Summary data saved when live mode is disabled
let savedSummary = null;
// Light on/off times from the server (ISO UTC strings, or null)
let sessionWindow = { start: null, end: null };
// Milestone tracking
let _previousCount = 0;
let _allTimeHigh = 0;
const MILESTONES = [25, 50, 75, 100, 150, 200];
let countdownTarget = null;
let isHalloween = false;

// Trick-or-treat window (local time, minutes since midnight): light is on 5:30-8 PM
const EVENT_START_MIN = 17 * 60 + 30;
const EVENT_END_MIN = 20 * 60;

// Local Date for today's window boundary, or for a given year's Oct 31
function eventTime(minutes, year) {
    const d = year ? new Date(year, 9, 31) : new Date();
    d.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
    return d;
}

// Ordered color palette for years — extends automatically for 2026+
const YEAR_COLOR_PALETTE = [
    '#ff6b35', '#4ecdc4', '#45b7d1', '#96ceb4',
    '#c792ea', '#f7c59f', '#e9c46a', '#e76f51',
];

function getYearColor(year) {
    const idx = (parseInt(year, 10) - 2022 + YEAR_COLOR_PALETTE.length) % YEAR_COLOR_PALETTE.length;
    return YEAR_COLOR_PALETTE[Math.max(0, idx)];
}

// Session bounds: when the light was turned on/off, falling back to the first/last entry
function getSessionBounds(entries) {
    const start = sessionWindow.start ? new Date(sessionWindow.start) : new Date(entries[0].timestamp);
    let end;
    if (sessionWindow.end) end = new Date(sessionWindow.end);
    else if (liveStatus) end = new Date();
    else end = new Date(entries[entries.length - 1].timestamp);
    return { start, end };
}

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    applyChartDefaults();
    initializeDashboard();
    setupCharts();
    loadHistoricalData();
    loadDetailedData();
    loadCountdownTarget();
    setInterval(tickCountdown, 1000);
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
    const summaryContainer = document.getElementById('summaryContainer');
    const weatherContainer = document.getElementById('weatherContainer');

    if (liveStatus) {
        statusElement.textContent = 'On';
        statusIndicator.className = 'status-indicator status-live';
        if (liveTimeContainer) liveTimeContainer.style.display = 'inline';
        if (summaryContainer) summaryContainer.style.display = 'none';
        // Weather container shown/hidden by updateWeatherDisplay() after data loads
        loadWeather();
    } else {
        statusElement.textContent = 'Off';
        statusIndicator.className = 'status-indicator';
        if (liveTimeContainer) liveTimeContainer.style.display = 'none';
        if (summaryContainer) summaryContainer.style.display = 'block';
        if (weatherContainer) weatherContainer.style.display = 'none';
    }
    updateCountdownVisibility();
}

function updateStatsVisibility() {
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.style.display = liveStatus ? 'grid' : 'none';
}

function updateCountdownVisibility() {
    const el = document.getElementById('countdownContainer');
    if (!el) return;
    el.style.display = liveStatus ? 'none' : 'block';
}

async function loadCountdownTarget() {
    try {
        const response = await fetch('/countdown');
        if (!response.ok) return;
        const data = await response.json();
        countdownTarget = new Date(data.target);
        isHalloween = data.is_halloween;
        updateCountdownVisibility();
    } catch (error) {
        console.error('Error loading countdown target:', error);
    }
}

function tickCountdown() {
    if (!countdownTarget || liveStatus) return;
    const diff = countdownTarget - new Date();
    if (diff <= 0) {
        document.getElementById('countdownDays').textContent = '0';
        document.getElementById('countdownHours').textContent = '00';
        document.getElementById('countdownMinutes').textContent = '00';
        document.getElementById('countdownSeconds').textContent = '00';
        return;
    }
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    document.getElementById('countdownDays').textContent = days;
    document.getElementById('countdownHours').textContent = String(hours).padStart(2, '0');
    document.getElementById('countdownMinutes').textContent = String(minutes).padStart(2, '0');
    document.getElementById('countdownSeconds').textContent = String(seconds).padStart(2, '0');
}

// Data loading
async function loadHistoricalData() {
    try {
        const response = await fetch('/historical_data');
        historicalData = await response.json();
        updateYearComparisonChart();
        computeAllTimeHigh();
        computePeakWindows();
        updateCumulativeChart();
    } catch (error) {
        console.error('Error loading historical data:', error);
    }
}

async function loadWeather() {
    try {
        const response = await fetch('/weather');
        if (response.ok) {
            const weather = await response.json();
            updateWeatherDisplay(weather);
        }
    } catch (error) {
        console.error('Error loading weather:', error);
    }
}

function updateWeatherDisplay(weather) {
    const container = document.getElementById('weatherContainer');
    const conditionEl = document.getElementById('weatherCondition');
    const tempEl = document.getElementById('weatherTemp');

    const isUnknown = !weather || !weather.condition || weather.condition === 'Unknown';
    const isStale = !weather?.timestamp ||
        (Date.now() - new Date(weather.timestamp).getTime() > 30 * 60 * 1000);
    const noTemp = weather?.temperature === null || weather?.temperature === undefined;

    if (isUnknown || isStale || noTemp) {
        if (container) container.style.display = 'none';
        return;
    }

    if (container) container.style.display = 'inline';
    if (conditionEl) conditionEl.textContent = weather.condition;
    if (tempEl) tempEl.textContent = Math.round(weather.temperature);
}

async function loadCurrentData() {
    try {
        const response = await fetch('/current_data');

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

        const newSnapshot = {
            len: newData ? newData.length : 0,
            sum: newData ? newData.reduce((s, e) => s + (e.count || 0), 0) : 0,
            last: (newData && newData.length > 0) ? newData[newData.length - 1].timestamp : null
        };

        if (_currentDataSnapshot &&
            _currentDataSnapshot.len === newSnapshot.len &&
            _currentDataSnapshot.sum === newSnapshot.sum &&
            _currentDataSnapshot.last === newSnapshot.last) {
            return;
        }

        currentData = newData;
        _currentDataSnapshot = newSnapshot;

        updateTimelineChart();
        updateMinuteChart();
        updateStats();
    } catch (error) {
        console.error('Error loading current data:', error);
    }
}

async function saveSummaryData() {
    // Fetch current year data (works regardless of live mode status)
    let dataToSave = currentData;
    
    // If we don't have data in memory, fetch it from the server
    if (!dataToSave || dataToSave.length === 0) {
        console.log('Fetching current year data for summary...');
        try {
            const response = await fetch('/current_year_data');
            if (response.ok) {
                dataToSave = await response.json();
            } else {
                console.warn('Failed to fetch current year data for summary');
            }
        } catch (error) {
            console.error('Error fetching data for summary:', error);
        }
    }
    
    if (!dataToSave || dataToSave.length === 0) {
        savedSummary = null;
        console.log('No data available to save summary');
        const summaryContainer = document.getElementById('summaryContainer');
        if (summaryContainer) {
            summaryContainer.innerHTML = '<p style="color: #ff6b35; font-size: 1.2em;">No data from this session</p>';
        }
        return;
    }
    
    console.log(`Creating summary from ${dataToSave.length} entries`);
    
    const totalToday = dataToSave.reduce((sum, entry) => sum + entry.count, 0);
    
    const minuteGroups = {};
    dataToSave.forEach(entry => {
        const localDate = new Date(entry.timestamp);
        const minutes = Math.floor(localDate.getMinutes() / 15) * 15;
        const timeKey = `${localDate.getHours().toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        
        if (!minuteGroups[timeKey]) {
            minuteGroups[timeKey] = 0;
        }
        minuteGroups[timeKey] += entry.count;
    });
    
    const minuteData = {};
    dataToSave.forEach(entry => {
        const localDate = new Date(entry.timestamp);
        const minuteKey = `${localDate.getHours().toString().padStart(2, '0')}:${localDate.getMinutes().toString().padStart(2, '0')}`;
        
        if (!minuteData[minuteKey]) {
            minuteData[minuteKey] = 0;
        }
        minuteData[minuteKey] += entry.count;
    });
    
    const bounds = getSessionBounds(dataToSave);

    savedSummary = {
        total: totalToday,
        minuteGroups: minuteGroups,
        minuteData: minuteData,
        firstTimestamp: bounds.start.toISOString(),
        lastTimestamp: bounds.end.toISOString(),
        year: new Date(dataToSave[0].timestamp).getFullYear()
    };
    
    console.log('Summary saved:', { total: savedSummary.total, year: savedSummary.year });
    displaySummary();
}

function displaySummary() {
    if (!savedSummary) {
        const summaryContainer = document.getElementById('summaryContainer');
        if (summaryContainer) {
            summaryContainer.innerHTML = '<p style="color: #ff6b35; font-size: 1.2em;">No data from previous session</p>';
        }
        return;
    }
    
    const summaryContainer = document.getElementById('summaryContainer');
    if (summaryContainer) {
        summaryContainer.innerHTML = '';

        const heading = document.createElement('h3');
        heading.style.cssText = 'color: var(--accent); margin-bottom: 10px;';
        heading.textContent = `📊 Session Summary (${savedSummary.year})`;

        const totalPara = document.createElement('p');
        totalPara.style.cssText = 'font-size: 1.3em; margin-bottom: 10px;';
        const bold = document.createElement('strong');
        bold.textContent = 'Total Trick-or-Treaters: ';
        const countSpan = document.createElement('span');
        countSpan.style.cssText = 'color: var(--accent-teal); font-size: 1.4em;';
        countSpan.textContent = savedSummary.total;
        totalPara.appendChild(bold);
        totalPara.appendChild(countSpan);

        const timeRange = document.createElement('p');
        timeRange.style.cssText = 'font-size: 0.9em; opacity: 0.8;';
        timeRange.textContent = `Session ran from ${formatTime(new Date(savedSummary.firstTimestamp))} to ${formatTime(new Date(savedSummary.lastTimestamp))}`;

        summaryContainer.append(heading, totalPara, timeRange);
    }
    
    displaySummaryCharts();
}

function displaySummaryCharts() {
    if (!savedSummary) return;
    
    const sortedLabels = Object.keys(savedSummary.minuteGroups).sort();
    const formattedLabels = sortedLabels.map(label => {
        const [hours, minutes] = label.split(':');
        const date = new Date();
        date.setHours(parseInt(hours), parseInt(minutes), 0, 0);
        return formatTime(date);
    });
    const minuteData = sortedLabels.map(label => savedSummary.minuteGroups[label]);
    
    charts.minute.data.labels = formattedLabels;
    charts.minute.data.datasets[0].data = minuteData;
    charts.minute.update();
    
    const firstEntry = new Date(savedSummary.firstTimestamp);
    const lastEntry = new Date(savedSummary.lastTimestamp);
    
    const labels = [];
    const data = [];
    let runningTotal = 0;
    
    const startMinute = new Date(firstEntry.getFullYear(), firstEntry.getMonth(), firstEntry.getDate(), firstEntry.getHours(), firstEntry.getMinutes());
    const endMinute = new Date(lastEntry.getFullYear(), lastEntry.getMonth(), lastEntry.getDate(), lastEntry.getHours(), lastEntry.getMinutes());
    
    for (let current = new Date(startMinute); current <= endMinute; current.setMinutes(current.getMinutes() + 1)) {
        const timeString = formatTime(current);
        const minuteKey = `${current.getHours().toString().padStart(2, '0')}:${current.getMinutes().toString().padStart(2, '0')}`;
        
        if (savedSummary.minuteData[minuteKey]) {
            runningTotal += savedSummary.minuteData[minuteKey];
        }
        
        labels.push(timeString);
        data.push(runningTotal);
    }
    
    charts.timeline.data.labels = labels;
    charts.timeline.data.datasets[0].data = data;
    charts.timeline.update();
}

function clearSummaryData() {
    savedSummary = null;
    currentData = [];
    _currentDataSnapshot = null;
    
    if (charts.minute) {
        charts.minute.data.labels = [];
        charts.minute.data.datasets[0].data = [];
        charts.minute.update();
    }
    
    if (charts.timeline) {
        charts.timeline.data.labels = [];
        charts.timeline.data.datasets[0].data = [];
        charts.timeline.update();
    }
    
    document.getElementById('totalToday').textContent = '0';
    document.getElementById('currentMinute').textContent = '0';
    document.getElementById('peakMinute').textContent = '--';
    document.getElementById('avgPerMinute').textContent = '0.0';
    document.getElementById('lastVisitor').textContent = '--';
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
    setupCumulativeChart();
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

        const newData = await resp.json();
        const newSnapshot = Object.values(newData).reduce((sum, entries) => sum + entries.length, 0);
        if (newSnapshot === _detailedHistoricalSnapshot) return;
        detailedHistorical = newData;
        _detailedHistoricalSnapshot = newSnapshot;
        populateYearSelector();
        updateDetailedYearChart();
        updateDetailedScatterChart();
        computePeakWindows();
        updateCumulativeChart();
    } catch (err) {
        console.error('Error loading detailed historical data:', err);
    }
}

function populateYearSelector() {
    const selector = document.getElementById('yearSelector');
    if (!selector) return;
    
    const currentSelection = selector.value;
    
    selector.innerHTML = '';
    const years = Object.keys(detailedHistorical).map(y => parseInt(y, 10)).sort((a,b) => a - b);
    if (years.length === 0) return;
    
    years.forEach(y => {
        const opt = document.createElement('option');
        opt.value = String(y);
        opt.textContent = String(y);
        selector.appendChild(opt);
    });
    
    if (currentSelection && years.includes(parseInt(currentSelection, 10))) {
        selector.value = currentSelection;
    } else {
        selector.value = String(Math.max(...years));
    }
    
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

    let yearToShow;
    if (typeof yearParam === 'number') yearToShow = yearParam;
    else {
        const selector = document.getElementById('yearSelector');
        if (selector && selector.value) yearToShow = parseInt(selector.value, 10);
        else yearToShow = Math.max(...years);
    }

    const entries = detailedHistorical[yearToShow] || [];

    const titleEl = document.getElementById('detailedScatterTitle');
    if (titleEl) titleEl.textContent = `✨ Visitor Scatter (each dot is one visitor) — Year: ${yearToShow}`;

    const points = [];
    entries.forEach((e, idx) => {
        let ts = e.timestamp;
        if (!ts) return;
        const d = new Date(ts);
        const minutes = d.getHours() * 60 + d.getMinutes() + (d.getSeconds() / 60);
        const jitter = ((idx % 5) - 2) * 0.18;
        points.push({ x: minutes, y: 1 + jitter });
    });

    charts.detailedScatter.data.datasets[0].data = points;

    if (points.length > 0) {
        const xs = points.map(p => p.x);
        const minX = Math.min(...xs) - 5;
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
        else yearToShow = Math.max(...years);
    }

    const labelEl = document.getElementById('detailedYearLabel');
    if (labelEl) labelEl.textContent = String(yearToShow);

    const entries = detailedHistorical[yearToShow] || [];

    const minuteCounts = {};
    entries.forEach(e => {
        let ts = e.timestamp;
        if (!ts) return;
        ts = ts.replace('Z', '');
        const d = new Date(ts);
        const minuteKey = `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
        minuteCounts[minuteKey] = (minuteCounts[minuteKey] || 0) + (e.count || 1);
    });

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
                tension: 0,
                fill: true,
                pointRadius: 3,
                pointHoverRadius: 5,
                stepped: 'after'
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
    const sliceLabelsPlugin = {
        id: 'sliceLabels',
        afterDatasetsDraw(chart) {
            const ctx = chart.ctx;
            const values = chart.data.datasets[0].data;
            const total = values.reduce((sum, v) => sum + v, 0);
            if (!total) return;
            ctx.save();
            ctx.fillStyle = '#fff';
            ctx.font = `bold 12px ${Chart.defaults.font.family}`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            chart.getDatasetMeta(0).data.forEach((arc, idx) => {
                const pos = arc.tooltipPosition();
                ctx.fillText(chart.data.labels[idx], pos.x, pos.y - 8);
                ctx.fillText((values[idx] / total * 100).toFixed(1) + '%', pos.x, pos.y + 8);
            });
            ctx.restore();
        }
    };
    charts.peakActivity = new Chart(ctx, {
        type: 'doughnut',
        plugins: [sliceLabelsPlugin],
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
                    display: false
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
                            const total = context.dataset.data.reduce((sum, v) => sum + v, 0);
                            const pct = total ? (value / total * 100).toFixed(1) : '0.0';
                            return label + ': ' + value + ' visitors (' + pct + '%)';
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
    
    const allTimeSlots = new Set();
    Object.values(historicalData).forEach(yearData => {
        Object.keys(yearData).forEach(timeSlot => allTimeSlots.add(timeSlot));
    });
    
    const sortedTimeSlots = Array.from(allTimeSlots).sort();
    
    const formattedTimeSlots = sortedTimeSlots.map(timeSlot => {
        const [hours, minutes] = timeSlot.split(':');
        const date = new Date();
        date.setHours(parseInt(hours), parseInt(minutes), 0, 0);
        return formatTime(date);
    });
    
    Object.entries(historicalData).forEach(([year, yearData]) => {
        const data = sortedTimeSlots.map(timeSlot => {
            return yearData[timeSlot] ? yearData[timeSlot].average : 0;
        });
        
        datasets.push({
            label: year,
            data: data,
            borderColor: getYearColor(year),
            backgroundColor: getYearColor(year) + '20',
            tension: 0.4,
            pointRadius: 4,
            pointHoverRadius: 6
        });
    });
    
    charts.yearComparison.data.labels = formattedTimeSlots;
    charts.yearComparison.data.datasets = datasets;
    charts.yearComparison.update();
    
    updateYearStatsChart();
    updatePeakActivityChart();
}

function updateTimelineChart() {
    if (!charts.timeline || !currentData) return;
    
    const minuteData = {};
    let runningTotal = 0;
    
    currentData.forEach(entry => {
        const localDate = new Date(entry.timestamp);
        const minuteKey = `${localDate.getHours().toString().padStart(2, '0')}:${localDate.getMinutes().toString().padStart(2, '0')}`;
        
        if (!minuteData[minuteKey]) {
            minuteData[minuteKey] = 0;
        }
        minuteData[minuteKey] += entry.count;
    });
    
    if (currentData.length > 0) {
        const { start: firstEntry, end: lastEntry } = getSessionBounds(currentData);
        
        const labels = [];
        const data = [];
        
        const startMinute = new Date(firstEntry.getFullYear(), firstEntry.getMonth(), firstEntry.getDate(), firstEntry.getHours(), firstEntry.getMinutes());
        const endMinute = new Date(lastEntry.getFullYear(), lastEntry.getMonth(), lastEntry.getDate(), lastEntry.getHours(), lastEntry.getMinutes());
        
        for (let current = new Date(startMinute); current <= endMinute; current.setMinutes(current.getMinutes() + 1)) {
            const timeString = formatTime(current);
            
            const minuteKey = `${current.getHours().toString().padStart(2, '0')}:${current.getMinutes().toString().padStart(2, '0')}`;
            
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
    
    const minuteGroups = {};
    currentData.forEach(entry => {
        const localDate = new Date(entry.timestamp);
        const minutes = Math.floor(localDate.getMinutes() / 15) * 15;
        const timeKey = `${localDate.getHours().toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        
        if (!minuteGroups[timeKey]) {
            minuteGroups[timeKey] = 0;
        }
        minuteGroups[timeKey] += entry.count;
    });
    
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
    
    const totalToday = currentData.reduce((sum, entry) => sum + entry.count, 0);
    document.getElementById('totalToday').textContent = totalToday;
    
    const now = new Date();
    const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000);
    
    const recentData = currentData.filter(entry => {
        const timestamp = entry.timestamp.replace('Z', '');
        const entryTime = new Date(timestamp);
        return entryTime >= fiveMinutesAgo;
    });
    const currentMinute = recentData.reduce((sum, entry) => sum + entry.count, 0);
    document.getElementById('currentMinute').textContent = currentMinute;
    
    let maxPeak = 0;
    for (let i = 0; i < currentData.length; i++) {
        const windowStart = new Date(currentData[i].timestamp).getTime();
        const windowEnd = windowStart + 10 * 60 * 1000;
        let windowSum = 0;
        for (let j = i; j < currentData.length; j++) {
            if (new Date(currentData[j].timestamp).getTime() <= windowEnd) {
                windowSum += currentData[j].count;
            } else {
                break;
            }
        }
        maxPeak = Math.max(maxPeak, windowSum);
    }
    document.getElementById('peakMinute').textContent = maxPeak;

    const { start, end } = getSessionBounds(currentData);
    const elapsedMinutes = (end - start) / 60000;
    const avgPerMinute = elapsedMinutes > 0 ? totalToday / elapsedMinutes : 0;
    document.getElementById('avgPerMinute').textContent = avgPerMinute.toFixed(1);
    
    if (currentData.length > 0) {
        const lastEntry = currentData[currentData.length - 1];
        const localDate = new Date(lastEntry.timestamp);
        const lastTime = formatTime(localDate, { seconds: true });
        document.getElementById('lastVisitor').textContent = lastTime;
    }

    checkMilestones(totalToday);
    updatePaceVsLastYear(totalToday);
    updateProjectedTotal(totalToday);
}

function updateYearStatsChart() {
    if (!charts.yearStats || !historicalData) return;
    
    const years = Object.keys(historicalData).sort();
    const totals = years.map(year => {
        return Object.values(historicalData[year]).reduce((sum, timeData) => sum + timeData.total, 0);
    });
    
    charts.yearStats.data.labels = years;
    charts.yearStats.data.datasets[0].data = totals;
    const grandTotal = totals.reduce((sum, t) => sum + t, 0);
    charts.yearStats.options.plugins.title.text =
        `Total Trick-or-Treaters by Year (${grandTotal} over ${years.length} years)`;
    charts.yearStats.update();
}

function updatePeakActivityChart() {
    if (!charts.peakActivity || !historicalData) return;
    
    const timeSlotTotals = {};
    Object.values(historicalData).forEach(yearData => {
        Object.entries(yearData).forEach(([timeSlot, data]) => {
            if (!timeSlotTotals[timeSlot]) {
                timeSlotTotals[timeSlot] = 0;
            }
            timeSlotTotals[timeSlot] += data.total;
        });
    });
    
    const topTimeSlots = Object.entries(timeSlotTotals)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 6);
    
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

// ── Milestone moments (#11) ────────────────────────────────────────────────

function computeAllTimeHigh() {
    if (!historicalData) return;
    let high = 0;
    Object.values(historicalData).forEach(yearData => {
        const total = Object.values(yearData).reduce((s, d) => s + (d.total || 0), 0);
        if (total > high) high = total;
    });
    _allTimeHigh = high;
}

function showMilestoneBanner(message) {
    const banner = document.getElementById('milestoneBanner');
    if (!banner) return;
    banner.textContent = message;
    banner.hidden = false;
    banner.classList.remove('hiding');
    clearTimeout(banner._hideTimer);
    banner._hideTimer = setTimeout(() => {
        banner.classList.add('hiding');
        setTimeout(() => { banner.hidden = true; banner.classList.remove('hiding'); }, 600);
    }, 6000);
}

function checkMilestones(newCount) {
    if (newCount <= _previousCount) {
        _previousCount = newCount;
        return;
    }
    for (const m of MILESTONES) {
        if (_previousCount < m && newCount >= m) {
            if (typeof confetti === 'function') {
                confetti({ particleCount: 120, spread: 70, origin: { y: 0.6 } });
            }
            showMilestoneBanner(`🎃 Visitor #${m}!`);
            break;
        }
    }
    if (_allTimeHigh > 0 && _previousCount < _allTimeHigh && newCount > _allTimeHigh) {
        if (typeof confetti === 'function') {
            confetti({ particleCount: 200, spread: 90, origin: { y: 0.5 } });
        }
        showMilestoneBanner(`🏆 New Record! ${newCount} visitors and counting!`);
    }
    _previousCount = newCount;
}

// ── Live pace vs. last year (#2) ───────────────────────────────────────────

function updatePaceVsLastYear(currentTotal) {
    const el = document.getElementById('paceVsLastYear');
    if (!el) return;

    const now = new Date();
    const currentYear = now.getFullYear();
    const lastYear = currentYear - 1;

    // Time elapsed since the start of today's window
    const elapsedMs = now - eventTime(EVENT_START_MIN);
    if (elapsedMs <= 0) { el.textContent = '--'; el.className = 'stat-number'; return; }
    const elapsedMin = elapsedMs / 60000;

    let lastYearTotal = 0;
    const lastYearStr = String(lastYear);

    if (detailedHistorical && detailedHistorical[lastYearStr]) {
        // Per-entry data: count entries from last year's Oct 31 within the same elapsed window
        const cutoff = eventTime(EVENT_START_MIN, lastYear);
        const cutoffEnd = new Date(cutoff.getTime() + elapsedMs);
        for (const entry of detailedHistorical[lastYearStr]) {
            const ts = new Date(entry.timestamp);
            if (ts >= cutoff && ts <= cutoffEnd) lastYearTotal += (entry.count || 1);
        }
    } else if (historicalData && historicalData[lastYearStr]) {
        // 15-min bucket data: sum slots up to the elapsed time slot
        const cutoffSlot = new Date(eventTime(EVENT_START_MIN, lastYear).getTime() + elapsedMs);
        const cutoffHHMM = `${String(cutoffSlot.getHours()).padStart(2,'0')}:${String(cutoffSlot.getMinutes()).padStart(2,'0')}`;
        Object.entries(historicalData[lastYearStr]).forEach(([slot, d]) => {
            if (slot <= cutoffHHMM) lastYearTotal += (d.total || 0);
        });
    } else {
        el.textContent = '--';
        el.className = 'stat-number pace-neutral';
        return;
    }

    const delta = currentTotal - lastYearTotal;
    if (delta > 0) {
        el.textContent = `+${delta} vs. ${lastYear}`;
        el.className = 'stat-number pace-positive';
    } else if (delta < 0) {
        el.textContent = `${delta} vs. ${lastYear}`;
        el.className = 'stat-number pace-negative';
    } else {
        el.textContent = `even vs. ${lastYear}`;
        el.className = 'stat-number pace-neutral';
    }
}

// ── Busiest 15-min stat (#3) ───────────────────────────────────────────────

function computePeakWindows() {
    const display = document.getElementById('peakWindowDisplay');
    if (!display) return;

    const peaks = {};

    // From historicalData (all years, 15-min buckets)
    if (historicalData) {
        Object.entries(historicalData).forEach(([year, yearData]) => {
            let bestSlot = null, bestTotal = 0;
            Object.entries(yearData).forEach(([slot, d]) => {
                if ((d.total || 0) > bestTotal) { bestTotal = d.total; bestSlot = slot; }
            });
            if (bestSlot) peaks[year] = { slot: bestSlot, count: bestTotal };
        });
    }

    // Override with per-entry data for years that have it (more precise)
    if (detailedHistorical) {
        Object.entries(detailedHistorical).forEach(([year, entries]) => {
            const buckets = {};
            entries.forEach(e => {
                if (!e.timestamp) return;
                const d = new Date(e.timestamp);
                const min15 = Math.floor(d.getMinutes() / 15) * 15;
                const key = `${String(d.getHours()).padStart(2,'0')}:${String(min15).padStart(2,'0')}`;
                buckets[key] = (buckets[key] || 0) + (e.count || 1);
            });
            let bestSlot = null, bestCount = 0;
            Object.entries(buckets).forEach(([k, v]) => { if (v > bestCount) { bestCount = v; bestSlot = k; } });
            if (bestSlot) peaks[year] = { slot: bestSlot, count: bestCount };
        });
    }

    const years = Object.keys(peaks).sort();
    if (years.length === 0) { display.innerHTML = ''; return; }

    display.innerHTML = years.map(year => {
        const { slot, count } = peaks[year];
        const [hh, mm] = slot.split(':');
        const start = new Date(); start.setHours(parseInt(hh), parseInt(mm), 0, 0);
        const end = new Date(start.getTime() + 15 * 60 * 1000);
        const range = `${formatTime(start)}–${formatTime(end)}`;
        return `<span class="peak-chip">${year}: ${count} visitors · ${range}</span>`;
    }).join('');
}

// ── Projected total (#7) ───────────────────────────────────────────────────

function updateProjectedTotal(currentTotal) {
    const card = document.getElementById('projectedCard');
    const el = document.getElementById('projectedTotal');
    if (!card || !el) return;

    const now = new Date();
    const windowStart = eventTime(EVENT_START_MIN);
    const windowEnd = eventTime(EVENT_END_MIN);
    const totalPossibleMs = windowEnd - windowStart;
    const elapsedMs = now - windowStart;

    if (currentTotal < 3 || elapsedMs <= 0 || now >= windowEnd) {
        card.style.display = 'none';
        return;
    }

    const projected = Math.round((currentTotal / elapsedMs) * totalPossibleMs);
    el.textContent = `~${projected}`;
    card.style.display = '';
}

// ── Cumulative arrivals chart (#1) ─────────────────────────────────────────

function setupCumulativeChart() {
    const ctx = document.getElementById('cumulativeChart');
    if (!ctx) return;

    function minsToLabel(val) {
        if (typeof val !== 'number' || !isFinite(val)) return '';
        const h = Math.floor(val / 60);
        const m = String(Math.round(val % 60)).padStart(2, '0');
        const ampm = h >= 12 ? 'PM' : 'AM';
        const h12 = h > 12 ? h - 12 : (h === 0 ? 12 : h);
        return `${h12}:${m} ${ampm}`;
    }

    charts.cumulative = new Chart(ctx, {
        type: 'scatter',
        data: { datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            datasets: { scatter: { showLine: true } },
            scales: {
                x: {
                    type: 'linear',
                    min: EVENT_START_MIN - 30,
                    max: EVENT_END_MIN + 30,
                    title: { display: true, text: 'Time of Evening' },
                    ticks: { callback: minsToLabel, maxTicksLimit: 9 }
                },
                y: {
                    title: { display: true, text: 'Cumulative Visitors' },
                    beginAtZero: true
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        title: items => items.length ? minsToLabel(items[0].parsed.x) : '',
                        label: item => `${item.dataset.label} — visitor #${item.parsed.y}`
                    }
                }
            }
        }
    });
}

function getCumulativePoints(year) {
    const points = [];

    if (detailedHistorical && detailedHistorical[year]) {
        // Per-entry data: each entry → a point (minutes since midnight, running total)
        const entries = [...detailedHistorical[year]].sort((a, b) =>
            new Date(a.timestamp) - new Date(b.timestamp)
        );
        let running = 0;
        entries.forEach(e => {
            if (!e.timestamp) return;
            const d = new Date(e.timestamp);
            const minOfDay = d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
            if (minOfDay < EVENT_START_MIN - 60 || minOfDay > EVENT_END_MIN + 60) return;
            running += (e.count || 1);
            points.push({ x: minOfDay, y: running });
        });
    } else if (historicalData && historicalData[year]) {
        // 15-min bucket data: sorted slots → stepped cumulative
        const slots = Object.entries(historicalData[year])
            .map(([slot, d]) => ({ slot, total: d.total || 0 }))
            .sort((a, b) => a.slot.localeCompare(b.slot));
        let running = 0;
        slots.forEach(({ slot, total }) => {
            const [hh, mm] = slot.split(':');
            const minOfDay = parseInt(hh) * 60 + parseInt(mm);
            if (minOfDay < EVENT_START_MIN - 60 || minOfDay > EVENT_END_MIN + 60) return;
            running += total;
            points.push({ x: minOfDay, y: running });
        });
    }
    return points;
}

function updateCumulativeChart() {
    updateYearBreakdown();
    if (!charts.cumulative) return;

    const datasets = [];
    const allYears = new Set([
        ...Object.keys(historicalData || {}),
        ...Object.keys(detailedHistorical || {})
    ]);

    allYears.forEach(year => {
        const points = getCumulativePoints(year);
        if (points.length === 0) return;
        const color = getYearColor(year);
        datasets.push({
            showLine: true,
            label: String(year),
            data: points,
            borderColor: color,
            backgroundColor: color + '20',
            borderWidth: 2,
            pointRadius: 2,
            pointHoverRadius: 5,
            tension: 0.3,
        });
    });

    datasets.sort((a, b) => a.label.localeCompare(b.label));
    charts.cumulative.data.datasets = datasets;
    charts.cumulative.update();
}

// ── Year-by-year breakdown (stacked, aligned rows) ─────────────────────────

let breakdownMode = 'arrivals';
const breakdownCharts = {};
let breakdownSignature = '';

function minsToClock(val) {
    const h = Math.floor(val / 60);
    const m = String(Math.round(val % 60)).padStart(2, '0');
    const h12 = h > 12 ? h - 12 : (h === 0 ? 12 : h);
    return `${h12}:${m} ${h >= 12 ? 'PM' : 'AM'}`;
}

function setupBreakdownToggle() {
    document.querySelectorAll('.breakdown-toggle button').forEach(btn => {
        btn.addEventListener('click', () => {
            breakdownMode = btn.dataset.mode;
            document.querySelectorAll('.breakdown-toggle button').forEach(b =>
                b.classList.toggle('active', b === btn));
            showBreakdownMode();
        });
    });
}

function showBreakdownMode() {
    const stacked = breakdownMode === 'arrivals' || breakdownMode === 'cumulative';
    document.getElementById('yearBreakdown').style.display = stacked ? '' : 'none';
    document.getElementById('overlayPanel').style.display = breakdownMode === 'overlay' ? '' : 'none';
    document.getElementById('overlayCumulativePanel').style.display =
        breakdownMode === 'overlayCumulative' ? '' : 'none';
    if (stacked) {
        updateYearBreakdown();
    } else {
        const chart = breakdownMode === 'overlay' ? charts.yearComparison : charts.cumulative;
        if (chart) { chart.resize(); chart.update('none'); }
    }
}

function isNarrowScreen() {
    return window.innerWidth < 600;
}

function updateYearBreakdown() {
    const host = document.getElementById('yearBreakdown');
    if (!host || (breakdownMode !== 'arrivals' && breakdownMode !== 'cumulative')) return;

    const years = Array.from(new Set([
        ...Object.keys(historicalData || {}),
        ...Object.keys(detailedHistorical || {})
    ])).sort().reverse();

    // Shared x categories / y max so every row lines up
    const slots = Array.from(new Set(
        Object.values(historicalData || {}).flatMap(y => Object.keys(y))
    )).sort();
    const labels = slots.map(s => {
        const [h, m] = s.split(':');
        return formatTime(new Date(2000, 0, 1, parseInt(h), parseInt(m)));
    });

    const rows = years.map(year => {
        if (breakdownMode === 'arrivals') {
            const yearData = (historicalData || {})[year] || {};
            const data = slots.map(s => yearData[s] ? yearData[s].average : 0);
            return { year, data, total: data.reduce((a, b) => a + b, 0), max: Math.max(0, ...data) };
        }
        const data = getCumulativePoints(year);
        const total = data.length ? data[data.length - 1].y : 0;
        return { year, data, total, max: total };
    }).filter(r => r.max > 0);

    const yMax = Math.max(1, ...rows.map(r => r.max));
    const signature = breakdownMode + '|' + rows.map(r => r.year).join(',');

    if (signature !== breakdownSignature) {
        Object.values(breakdownCharts).forEach(c => c.destroy());
        Object.keys(breakdownCharts).forEach(k => delete breakdownCharts[k]);
        host.innerHTML = '';
        rows.forEach(r => {
            const card = document.createElement('div');
            card.className = 'chart-container year-row';
            card.innerHTML = `<div class="year-row-title" style="color:${getYearColor(r.year)}"></div>` +
                '<div class="year-row-canvas"><canvas></canvas></div>';
            card.dataset.year = r.year;
            host.appendChild(card);
            breakdownCharts[r.year] = createBreakdownChart(card.querySelector('canvas'), r.year);
        });
        breakdownSignature = signature;
    }

    rows.forEach(r => {
        const chart = breakdownCharts[r.year];
        if (!chart) return;
        const title = host.querySelector(`[data-year="${r.year}"] .year-row-title`);
        if (title) {
            title.textContent = breakdownMode === 'arrivals'
                ? `${r.year} — ${Math.round(r.total)} total`
                : `${r.year} — ${r.total} visitors`;
        }
        if (breakdownMode === 'arrivals') chart.data.labels = labels;
        chart.data.datasets[0].data = r.data;
        chart.options.scales.y.max = yMax;
        chart.update('none');
    });
}

function createBreakdownChart(canvas, year) {
    const color = getYearColor(year);
    const cumulative = breakdownMode === 'cumulative';
    const yAxis = {
        beginAtZero: true,
        afterFit: scale => { scale.width = isNarrowScreen() ? 32 : 45; }  // same plot-left edge on every row
    };
    return new Chart(canvas, {
        type: cumulative ? 'scatter' : 'bar',
        data: {
            labels: [],
            datasets: [{
                data: [],
                borderColor: color,
                backgroundColor: cumulative ? color + '20' : color + 'cc',
                showLine: cumulative,
                borderWidth: 2,
                pointRadius: cumulative ? 1 : 0,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: cumulative ? {
                    type: 'linear',
                    min: EVENT_START_MIN - 30,
                    max: EVENT_END_MIN + 30,
                    ticks: { callback: minsToClock, maxTicksLimit: isNarrowScreen() ? 4 : 9 }
                } : {
                    ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: isNarrowScreen() ? 4 : 14 }
                },
                y: yAxis
            },
            plugins: {
                legend: { display: false },
                tooltip: cumulative ? {
                    callbacks: {
                        title: items => items.length ? minsToClock(items[0].parsed.x) : '',
                        label: item => `visitor #${item.parsed.y}`
                    }
                } : {}
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', setupBreakdownToggle);

// ── Polling intervals ──────────────────────────────────────────────────────

// Auto-refresh trick-or-treater data when live (2-second poll)
setInterval(() => {
    if (liveStatus) {
        loadCurrentData();
    }
}, 2000);

// Detailed historical charts update at most once per minute (rate limit: 200/hr)
setInterval(() => {
    if (liveStatus) {
        loadDetailedData();
    }
}, 60 * 1000);

// Weather changes slowly — poll every 5 minutes
setInterval(() => {
    if (liveStatus) {
        loadWeather();
    }
}, 5 * 60 * 1000);

// Initialize dashboard
function initializeDashboard() {
    updateLiveStatusDisplay();
    updateStatsVisibility();
}
