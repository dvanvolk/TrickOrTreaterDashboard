// Dashboard state management
let liveStatus = false;
let charts = {};
let historicalData = {};
let currentData = [];

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
    loadHistoricalData();
    setupCharts();
    startLiveTimer();
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

    if (liveStatus) {
        statusElement.textContent = 'Live';
        statusIndicator.className = 'status-indicator status-live';
    } else {
        statusElement.textContent = 'Disabled';
        statusIndicator.className = 'status-indicator';
    }
}

function updateStatsVisibility() {
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.style.display = liveStatus ? 'grid' : 'none';
}

// Live timer functionality
function startLiveTimer() {
    setInterval(updateLiveTimer, 1000);
}

function updateLiveTimer() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    document.getElementById('liveTimer').textContent = timeString;
}

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
        currentData = await response.json();
        updateTimelineChart();
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
                label: 'Current Year',
                data: [],
                borderColor: '#4ecdc4',
                backgroundColor: 'rgba(78, 205, 196, 0.1)',
                tension: 0.4,
                fill: true
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
                        text: 'Trick-or-Treaters'
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
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Time of Day'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Average Trick-or-Treaters'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                title: {
                    display: true,
                    text: 'Year-over-Year Comparison by Time of Day'
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
    timeSlots.push(...Array.from(allTimeSlots).sort());
    
    // Create dataset for each year
    Object.entries(historicalData).forEach(([year, yearData]) => {
        const data = timeSlots.map(timeSlot => {
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
    
    charts.yearComparison.data.labels = timeSlots;
    charts.yearComparison.data.datasets = datasets;
    charts.yearComparison.update();
}

function updateTimelineChart() {
    if (!charts.timeline || !currentData) return;
    
    const labels = currentData.map(entry => {
        const date = new Date(entry.timestamp);
        return date.toLocaleTimeString();
    });
    const data = currentData.map(entry => entry.count);
    
    charts.timeline.data.labels = labels;
    charts.timeline.data.datasets[0].data = data;
    charts.timeline.update();
}

function updateStats() {
    if (!currentData || currentData.length === 0) return;
    
    // Calculate total today
    const totalToday = currentData.reduce((sum, entry) => sum + entry.count, 0);
    document.getElementById('totalToday').textContent = totalToday;
    
    // Calculate current 5-minute period
    const now = new Date();
    const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000);
    const recentData = currentData.filter(entry => 
        new Date(entry.timestamp) >= fiveMinutesAgo
    );
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
        const lastTime = new Date(lastEntry.timestamp).toLocaleTimeString();
        document.getElementById('lastVisitor').textContent = lastTime;
    }
}

// Auto-refresh data when live
setInterval(() => {
    if (liveStatus) {
        loadCurrentData();
    }
}, 30000); // Update every 30 seconds

// Initialize dashboard
function initializeDashboard() {
    updateLiveStatusDisplay();
    updateStatsVisibility();
}