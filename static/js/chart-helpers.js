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

/**
 * Format a Date (or timestamp string) to a localized 12-hour time string used across charts.
 * Keeps formatting consistent across the UI.
 * @param {Date|string|number} d - Date object, ISO string, or ms timestamp
 * @param {Object} [opts] - optional formatting options: { seconds: boolean }
 * @returns {string}
 */
function formatTime(d, opts = {}) {
    if (!d) return '';
    let dateObj = d;
    if (typeof d === 'string' || typeof d === 'number') {
        dateObj = new Date(d);
    }
    const formatOpts = {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    };
    if (opts.seconds) {
        formatOpts.second = '2-digit';
    }
    return dateObj.toLocaleTimeString('en-US', formatOpts);
}

/**
 * Convert a Date (or timestamp string) to an ISO timestamp (string) suitable for Chart.js time axis.
 * @param {Date|string|number} d
 * @returns {string}
 */
function toISOStringLocal(d) {
    let dateObj = d;
    if (typeof d === 'string' || typeof d === 'number') dateObj = new Date(d);
    // Use the Date's toISOString (UTC) — Chart.js adapter will interpret correctly.
    return dateObj.toISOString();
}

/**
 * Apply dark-theme defaults to all Chart.js instances.
 * Call once before any charts are created (e.g., top of DOMContentLoaded).
 */
function applyChartDefaults() {
    Chart.defaults.color = 'rgba(255,255,255,0.8)';
    Chart.defaults.font.family = "'Nunito', Arial, sans-serif";
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(13,13,26,0.92)';
    Chart.defaults.plugins.tooltip.titleColor = '#ff6b35';
    Chart.defaults.plugins.tooltip.bodyColor = 'rgba(255,255,255,0.9)';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,107,53,0.35)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.scale.grid = { color: 'rgba(255,255,255,0.1)' };
    Chart.defaults.scale.ticks = { color: 'rgba(255,255,255,0.75)' };
}