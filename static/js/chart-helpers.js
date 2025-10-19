// This file contains helper functions for managing and updating charts displayed on the dashboard.

let liveStatus = false;

function setLiveStatus(status) {
    liveStatus = status;
    updateCounterVisibility();
}

function updateCounterVisibility() {
    const counterElements = document.querySelectorAll('.stat-card');
    counterElements.forEach(card => {
        card.style.display = liveStatus ? 'block' : 'none';
    });
}

function updateLiveStatusIndicator() {
    const statusIndicator = document.getElementById('status');
    statusIndicator.textContent = liveStatus ? 'Status: Live' : 'Status: Disabled';
}

// Call this function to initialize the live status on page load
function initializeLiveStatus(initialStatus) {
    setLiveStatus(initialStatus);
    updateLiveStatusIndicator();
}