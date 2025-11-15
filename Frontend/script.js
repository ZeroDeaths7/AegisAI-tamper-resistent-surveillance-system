// ============================================================================
// AEGIS: ACTIVE DEFENSE SYSTEM - CLIENT-SIDE SCRIPT
// Real-time alert handling and Socket.IO communication
// ============================================================================

// Initialize Socket.IO connection
const socket = io();

// DOM Elements
const statusBadge = document.getElementById('statusBadge');
const alertBanner = document.getElementById('alertBanner');
const alertMessage = document.querySelector('.alert-message');
const detectionLog = document.getElementById('detectionLog');
const rawFeed = document.getElementById('rawFeed');
const processedFeed = document.getElementById('processedFeed');

// Metric elements
const blurValue = document.getElementById('blurValue');
const shakeValue = document.getElementById('shakeValue');
const glareValue = document.getElementById('glareValue');
const livenessValue = document.getElementById('livenessValue');

const blurIndicator = document.getElementById('blurIndicator');
const shakeIndicator = document.getElementById('shakeIndicator');
const glareIndicator = document.getElementById('glareIndicator');
const livenessIndicator = document.getElementById('livenessIndicator');

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let systemState = {
    status: 'secure', // 'secure' or 'alert'
    alerts: [],
    metrics: {
        blur: { value: 0, status: 'ok' },
        shake: { value: 0, status: 'ok' },
        glare: { value: 0, status: 'ok' },
        liveness: { value: 0, status: 'ok' }
    }
};

const MAX_LOG_ENTRIES = 20;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Get current timestamp in HH:MM:SS format
 */
function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { hour12: false });
}

/**
 * Add an entry to the detection log
 */
function addLogEntry(message, type = 'secure') {
    const time = getCurrentTime();
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    logEntry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-message">${message}</span>
    `;

    detectionLog.insertBefore(logEntry, detectionLog.firstChild);

    // Keep only the last MAX_LOG_ENTRIES
    while (detectionLog.children.length > MAX_LOG_ENTRIES) {
        detectionLog.removeChild(detectionLog.lastChild);
    }
}

/**
 * Update the metric display
 */
function updateMetric(metricName, value, status = 'ok') {
    const valueElement = document.getElementById(`${metricName}Value`);
    const indicatorElement = document.getElementById(`${metricName}Indicator`);

    valueElement.textContent = typeof value === 'number' ? value.toFixed(2) : value;

    // Remove all status classes and add the new one
    indicatorElement.classList.remove('secure', 'alert', 'warning');
    indicatorElement.classList.add(status);

    // Update state
    systemState.metrics[metricName] = { value, status };
}

/**
 * Update system status badge and alert banner
 */
function updateSystemStatus(isAlert = false) {
    const newStatus = isAlert ? 'alert' : 'secure';

    if (newStatus !== systemState.status) {
        systemState.status = newStatus;

        // Update status badge
        statusBadge.classList.remove('secure', 'alert');
        statusBadge.classList.add(newStatus);
        statusBadge.innerHTML = newStatus === 'secure'
            ? '<span class="status-pulse"></span>STATUS: SECURE'
            : '<span class="status-pulse"></span>STATUS: ALERT!';

        // Update alert banner styling
        alertBanner.classList.toggle('active', isAlert);
    }
}

/**
 * Trigger an alert with sound and visual feedback
 */
function triggerAlert(alertType, message) {
    const time = getCurrentTime();

    // Update alert banner
    alertMessage.textContent = `⚠ ${message}`;

    // Add to system alerts
    systemState.alerts.push({ type: alertType, time, message });

    // Update status to alert
    updateSystemStatus(true);

    // Log the alert
    addLogEntry(`${alertType}: ${message}`, 'alert');

    // Optional: Play a subtle alert sound (if available)
    playAlertSound();
}

/**
 * Clear alerts if all threats are resolved
 */
function checkAndClearAlerts() {
    let hasAlert = false;

    // Check if any metric is in alert state
    Object.values(systemState.metrics).forEach(metric => {
        if (metric.status === 'alert' || metric.status === 'warning') {
            hasAlert = true;
        }
    });

    if (!hasAlert) {
        updateSystemStatus(false);
        alertMessage.textContent = '✓ System Active - All Sensors Online';
        addLogEntry('All threats cleared', 'secure');
    }
}

/**
 * Play an alert sound (optional)
 */
function playAlertSound() {
    // Create a simple beep using Web Audio API
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800; // Hz
        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.1);
    } catch (e) {
        console.log('Audio context not available');
    }
}

// ============================================================================
// SOCKET.IO EVENT HANDLERS
// ============================================================================

/**
 * Connection established
 */
socket.on('connect', () => {
    console.log('Connected to server');
    addLogEntry('Connected to Aegis server', 'secure');
});

/**
 * Connection lost
 */
socket.on('disconnect', () => {
    console.log('Disconnected from server');
    addLogEntry('Disconnected from server', 'alert');
    triggerAlert('CONNECTION', 'Lost connection to server');
});

/**
 * Receive detection updates from the server
 * Expected payload:
 * {
 *     blur: { detected: boolean, variance: number },
 *     shake: { detected: boolean, magnitude: number },
 *     glare: { detected: boolean },
 *     liveness: { frozen: boolean }
 * }
 */
socket.on('detection_update', (data) => {
    // Handle Blur Detection
    if (data.blur) {
        const blurStatus = data.blur.detected ? 'alert' : 'secure';
        updateMetric('blur', data.blur.variance || 0, blurStatus);

        if (data.blur.detected) {
            triggerAlert('BLUR', 'Camera Obscured - Tamper Detected!');
        }
    }

    // Handle Shake Detection
    if (data.shake) {
        const shakeStatus = data.shake.detected ? 'alert' : 'secure';
        updateMetric('shake', data.shake.magnitude || 0, shakeStatus);

        if (data.shake.detected) {
            triggerAlert('SHAKE', 'Camera Shake Detected!');
        }
    }

    // Handle Glare Detection
    if (data.glare) {
        const glareStatus = data.glare.detected ? 'alert' : 'secure';
        updateMetric('glare', data.glare.detected ? 1 : 0, glareStatus);

        if (data.glare.detected) {
            triggerAlert('GLARE', 'Critical Threat: Glare Attack Detected!');
        }
    }

    // Handle Liveness Check
    if (data.liveness) {
        const livenessStatus = data.liveness.frozen ? 'alert' : 'secure';
        updateMetric('liveness', data.liveness.frozen ? 0 : 1, livenessStatus);

        if (data.liveness.frozen) {
            triggerAlert('LIVENESS', 'Feed Frozen - Potential Replay Attack!');
        }
    }

    // Check if we should clear alerts
    checkAndClearAlerts();
});

/**
 * Receive direct alert from server
 */
socket.on('alert', (data) => {
    console.log('Alert received:', data);
    triggerAlert(data.type || 'SYSTEM', data.message || 'Unknown alert');
});

/**
 * Receive status update from server
 */
socket.on('status_update', (data) => {
    console.log('Status update:', data);
    if (data.status === 'healthy') {
        updateSystemStatus(false);
    } else if (data.status === 'threat') {
        updateSystemStatus(true);
    }
});

// ============================================================================
// KEYBOARD CONTROLS (Optional - for testing)
// ============================================================================

document.addEventListener('keydown', (event) => {
    // Press 'B' to simulate blur alert
    if (event.key.toLowerCase() === 'b') {
        triggerAlert('BLUR', 'Test: Camera Obscured');
        updateMetric('blur', 50, 'alert');
    }

    // Press 'S' to simulate shake alert
    if (event.key.toLowerCase() === 's') {
        triggerAlert('SHAKE', 'Test: Camera Shake Detected');
        updateMetric('shake', 5.2, 'alert');
    }

    // Press 'G' to simulate glare alert
    if (event.key.toLowerCase() === 'g') {
        triggerAlert('GLARE', 'Test: Glare Attack Detected');
        updateMetric('glare', 1, 'alert');
    }

    // Press 'L' to simulate liveness alert
    if (event.key.toLowerCase() === 'l') {
        triggerAlert('LIVENESS', 'Test: Feed Frozen');
        updateMetric('liveness', 0, 'alert');
    }

    // Press 'R' to reset/clear all alerts
    if (event.key.toLowerCase() === 'r') {
        updateSystemStatus(false);
        updateMetric('blur', 75, 'secure');
        updateMetric('shake', 0.5, 'secure');
        updateMetric('glare', 0, 'secure');
        updateMetric('liveness', 1, 'secure');
        alertMessage.textContent = '✓ System Active - All Sensors Online';
        addLogEntry('System reset', 'secure');
    }
});

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('Aegis Dashboard initialized');

    // Initialize metrics display
    updateMetric('blur', 0, 'secure');
    updateMetric('shake', 0, 'secure');
    updateMetric('glare', 0, 'secure');
    updateMetric('liveness', 1, 'secure');

    // Add welcome message
    addLogEntry('Aegis system initialized', 'secure');
    addLogEntry('Connecting to camera feed...', 'secure');

    // Start streaming video frames
    startVideoStream();
});

/**
 * Start streaming video frames from the server
 */
function startVideoStream() {
    // Stream raw feed
    setInterval(() => {
        const timestamp = new Date().getTime();
        rawFeed.src = `/video_frame?t=${timestamp}`;
    }, 100); // Update every 100ms (10 FPS)

    // Stream processed feed
    setInterval(() => {
        const timestamp = new Date().getTime();
        processedFeed.src = `/processed_frame?t=${timestamp}`;
    }, 100); // Update every 100ms (10 FPS)
}

// ============================================================================
// EXPORT FOR TESTING (if needed)
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        triggerAlert,
        updateMetric,
        updateSystemStatus,
        addLogEntry,
        systemState
    };
}
