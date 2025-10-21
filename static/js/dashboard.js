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
        statusElement.textContent = 'Live';
        statusIndicator.className = 'status-indicator status-live';
        if (liveTimeContainer) liveTimeContainer.style.display = 'inline';
    } else {
        statusElement.textContent = 'Disabled';
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
        currentData = await response.json();
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
        return date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
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
            const timeString = current.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
            
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
        return date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
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
        const lastTime = new Date(timestamp).toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        });
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
    
    const labels = topTimeSlots.map(([timeSlot]) => timeSlot);
    const data = topTimeSlots.map(([, total]) => total);
    
    charts.peakActivity.data.labels = labels;
    charts.peakActivity.data.datasets[0].data = data;
    charts.peakActivity.update();
}

// Auto-refresh data when live
setInterval(() => {
    if (liveStatus) {
        loadCurrentData();
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