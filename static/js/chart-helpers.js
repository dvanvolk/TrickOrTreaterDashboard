// This file contains helper functions for managing and updating charts displayed on the dashboard.

// Helper functions for chart management
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