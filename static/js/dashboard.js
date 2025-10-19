let liveStatus = false;

function toggleLiveStatus() {
    liveStatus = !liveStatus;
    updateLiveStatusDisplay();
}

function updateLiveStatusDisplay() {
    const statusElement = document.getElementById('status');
    const counterElement = document.getElementById('counter');

    if (liveStatus) {
        statusElement.textContent = "Status: Live";
        statusElement.querySelector('.status-indicator').classList.add('status-live');
        counterElement.style.display = 'block'; // Show counter
    } else {
        statusElement.textContent = "Status: Offline";
        statusElement.querySelector('.status-indicator').classList.remove('status-live');
        counterElement.style.display = 'none'; // Hide counter
    }
}

// Call this function to initialize the dashboard
function initializeDashboard() {
    updateLiveStatusDisplay();
}

// Example of how to call toggleLiveStatus from a button click
document.getElementById('toggleLiveButton').addEventListener('click', toggleLiveStatus);

// Initialize the dashboard on page load
initializeDashboard();