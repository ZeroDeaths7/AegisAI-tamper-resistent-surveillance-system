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
    status: 'secure',
    alerts: [],
    metrics: {
        blur: { value: 0, status: 'secure' },
        shake: { value: 0, status: 'secure' },
        glare: { value: 0, status: 'secure' },
        liveness: { value: 1, status: 'secure' }
    }
};

const MAX_LOG_ENTRIES = 20;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { hour12: false });
}

function addLogEntry(message, type = 'secure') {
    const time = getCurrentTime();
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    logEntry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-message">${message}</span>
    `;

    detectionLog.insertBefore(logEntry, detectionLog.firstChild);

    while (detectionLog.children.length > MAX_LOG_ENTRIES) {
        detectionLog.removeChild(detectionLog.lastChild);
    }
}

function updateMetric(metricName, value, status = 'secure') {
    const valueElement = document.getElementById(`${metricName}Value`);
    const indicatorElement = document.getElementById(`${metricName}Indicator`);

    valueElement.textContent = typeof value === 'number' ? value.toFixed(2) : value;

    indicatorElement.classList.remove('secure', 'alert', 'warning');
    indicatorElement.classList.add(status);

    systemState.metrics[metricName] = { value, status };
}

function updateSystemStatus(isAlert = false) {
    const newStatus = isAlert ? 'alert' : 'secure';

    if (newStatus !== systemState.status) {
        systemState.status = newStatus;

        statusBadge.classList.remove('secure', 'alert');
        statusBadge.classList.add(newStatus);
        statusBadge.innerHTML = newStatus === 'secure'
            ? '<span class="status-pulse"></span>STATUS: SECURE'
            : '<span class="status-pulse"></span>STATUS: ALERT!';

        alertBanner.classList.toggle('active', isAlert);
    }
}

function triggerAlert(alertType, message) {
    const time = getCurrentTime();

    alertMessage.textContent = `⚠ ${message}`;
    systemState.alerts.push({ type: alertType, time, message });
    updateSystemStatus(true);
    addLogEntry(`${alertType}: ${message}`, 'alert');
    playAlertSound();
}

function checkAndClearAlerts() {
    let hasAlert = false;

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

function playAlertSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
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

socket.on('connect', () => {
    console.log('Connected to server');
    addLogEntry('Connected to Aegis server', 'secure');
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    addLogEntry('Disconnected from server', 'alert');
    triggerAlert('CONNECTION', 'Lost connection to server');
});

socket.on('detection_update', (data) => {
    console.log('Detection update received:', data);
    
    if (data.blur) {
        const blurStatus = data.blur.detected ? 'alert' : 'secure';
        updateMetric('blur', data.blur.variance || 0, blurStatus);

        if (data.blur.detected) {
            triggerAlert('BLUR', 'Camera Obscured - Tamper Detected!');
        }
    }

    if (data.shake) {
        const shakeStatus = data.shake.detected ? 'alert' : 'secure';
        updateMetric('shake', data.shake.magnitude || 0, shakeStatus);

        if (data.shake.detected) {
            triggerAlert('SHAKE', 'Camera Shake Detected!');
        }
    }

    if (data.glare) {
        const glareStatus = data.glare.detected ? 'alert' : 'secure';
        updateMetric('glare', data.glare.detected ? 1 : 0, glareStatus);

        if (data.glare.detected) {
            triggerAlert('GLARE', 'Critical Threat: Glare Attack Detected!');
        }
    }

    if (data.liveness) {
        const livenessStatus = data.liveness.frozen ? 'alert' : 'secure';
        updateMetric('liveness', data.liveness.frozen ? 0 : 1, livenessStatus);

        if (data.liveness.frozen) {
            triggerAlert('LIVENESS', 'Feed Frozen - Potential Replay Attack!');
        }
    }

    checkAndClearAlerts();
});

socket.on('alert', (data) => {
    console.log('Alert received:', data);
    triggerAlert(data.type || 'SYSTEM', data.message || 'Unknown alert');
});

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
    if (event.key.toLowerCase() === 'b') {
        triggerAlert('BLUR', 'Test: Camera Obscured');
        updateMetric('blur', 50, 'alert');
    }

    if (event.key.toLowerCase() === 's') {
        triggerAlert('SHAKE', 'Test: Camera Shake Detected');
        updateMetric('shake', 5.2, 'alert');
    }

    if (event.key.toLowerCase() === 'g') {
        triggerAlert('GLARE', 'Test: Glare Attack Detected');
        updateMetric('glare', 1, 'alert');
    }

    if (event.key.toLowerCase() === 'l') {
        triggerAlert('LIVENESS', 'Test: Feed Frozen');
        updateMetric('liveness', 0, 'alert');
    }

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

    updateMetric('blur', 0, 'secure');
    updateMetric('shake', 0, 'secure');
    updateMetric('glare', 0, 'secure');
    updateMetric('liveness', 1, 'secure');

    addLogEntry('Aegis system initialized', 'secure');
    addLogEntry('Connecting to camera feed...', 'secure');

    startVideoStream();
});

function startVideoStream() {
    setInterval(() => {
        const timestamp = new Date().getTime();
        rawFeed.src = `/video_frame?t=${timestamp}`;
    }, 100);

    setInterval(() => {
        const timestamp = new Date().getTime();
        processedFeed.src = `/processed_frame?t=${timestamp}`;
    }, 100);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        triggerAlert,
        updateMetric,
        updateSystemStatus,
        addLogEntry,
        systemState
    };
}
