/**
 * OO Automator Chart Utilities
 * Uses Chart.js for visualizing backtest results
 */

// Default chart colors for dark theme
const chartColors = {
    primary: '#4e9af1',
    success: '#4caf50',
    warning: '#ff9800',
    error: '#f44336',
    text: '#eee',
    grid: '#333',
    background: '#1a1a2e'
};

// Default chart options for dark theme
const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: chartColors.text
            }
        }
    },
    scales: {
        x: {
            ticks: { color: chartColors.text },
            grid: { color: chartColors.grid }
        },
        y: {
            ticks: { color: chartColors.text },
            grid: { color: chartColors.grid }
        }
    }
};

/**
 * Create a P/L bar chart
 * @param {string} canvasId - Canvas element ID
 * @param {Array} labels - Parameter values
 * @param {Array} data - P/L values
 */
function createPLChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const colors = data.map(val => val >= 0 ? chartColors.success : chartColors.error);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'P/L ($)',
                data: data,
                backgroundColor: colors,
                borderColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            ...defaultOptions,
            plugins: {
                ...defaultOptions.plugins,
                title: {
                    display: true,
                    text: 'Profit/Loss by Parameter',
                    color: chartColors.text
                }
            }
        }
    });
}

/**
 * Create a CAGR line chart
 * @param {string} canvasId - Canvas element ID
 * @param {Array} labels - Parameter values
 * @param {Array} data - CAGR percentages
 */
function createCAGRChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'CAGR (%)',
                data: data,
                borderColor: chartColors.primary,
                backgroundColor: chartColors.primary + '33',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            ...defaultOptions,
            plugins: {
                ...defaultOptions.plugins,
                title: {
                    display: true,
                    text: 'CAGR by Parameter',
                    color: chartColors.text
                }
            }
        }
    });
}

/**
 * Create a metrics comparison radar chart
 * @param {string} canvasId - Canvas element ID
 * @param {Object} metrics - Object with metric names and values
 */
function createMetricsRadar(canvasId, metrics) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels: Object.keys(metrics),
            datasets: [{
                label: 'Performance',
                data: Object.values(metrics),
                borderColor: chartColors.primary,
                backgroundColor: chartColors.primary + '33',
                pointBackgroundColor: chartColors.primary
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: { color: chartColors.text }
                }
            },
            scales: {
                r: {
                    ticks: { color: chartColors.text },
                    grid: { color: chartColors.grid },
                    pointLabels: { color: chartColors.text }
                }
            }
        }
    });
}

/**
 * Create a progress doughnut chart
 * @param {string} canvasId - Canvas element ID
 * @param {number} completed - Completed tasks
 * @param {number} failed - Failed tasks
 * @param {number} pending - Pending tasks
 */
function createProgressChart(canvasId, completed, failed, pending) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Completed', 'Failed', 'Pending'],
            datasets: [{
                data: [completed, failed, pending],
                backgroundColor: [
                    chartColors.success,
                    chartColors.error,
                    chartColors.grid
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: chartColors.text }
                }
            }
        }
    });
}

// Export for use in templates
window.OOCharts = {
    createPLChart,
    createCAGRChart,
    createMetricsRadar,
    createProgressChart,
    colors: chartColors
};
