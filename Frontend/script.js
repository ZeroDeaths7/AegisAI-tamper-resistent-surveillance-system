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
const subtitleLog = document.getElementById('subtitleLog');
const audioIndicator = document.getElementById('audioIndicator');
const rawFeed = document.getElementById('rawFeed');
const processedFeed = document.getElementById('processedFeed');

// Metric elements
const blurValue = document.getElementById('blurValue');
const shakeValue = document.getElementById('shakeValue');
const repositionValue = document.getElementById('repositionValue');
const glareValue = document.getElementById('glareValue');
const livenessValue = document.getElementById('livenessValue');

const blurIndicator = document.getElementById('blurIndicator');
const shakeIndicator = document.getElementById('shakeIndicator');
const repositionIndicator = document.getElementById('repositionIndicator');
const glareIndicator = document.getElementById('glareIndicator');
const livenessIndicator = document.getElementById('livenessIndicator');

const glareHistogramContainer = document.getElementById('glareHistogram');
const repositionAlertModal = document.getElementById('repositionAlertModal');
const repositionDetails = document.getElementById('repositionDetails');

// ============================================================================
// HISTOGRAM VISUALIZATION
// ============================================================================

/**
 * Update and display the glare histogram visually
 */
function updateGlareHistogram(histogramData, isAlert = false) {
    // Clear previous bars
    glareHistogramContainer.innerHTML = '';
    
    if (!histogramData || histogramData.length === 0) {
        glareHistogramContainer.innerHTML = '<div style="width: 100%; text-align: center; color: #888;">No data</div>';
        return;
    }
    
    // Find max value for scaling
    const maxValue = Math.max(...histogramData);
    
    // Prevent division by zero or invalid histogram
    if (maxValue === 0 || !isFinite(maxValue)) {
        glareHistogramContainer.innerHTML = '<div style="width: 100%; text-align: center; color: #888;">No signal</div>';
        return;
    }
    
    // Create bars for each histogram bucket
    for (let i = 0; i < histogramData.length; i++) {
        const bar = document.createElement('div');
        bar.className = `bar ${isAlert ? 'alert' : ''}`;
        
        // Scale height proportionally (min 2px to be visible)
        const heightPercent = (histogramData[i] / maxValue) * 100;
        bar.style.height = `${Math.max(2, heightPercent)}%`;
        
        glareHistogramContainer.appendChild(bar);
    }
}

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let systemState = {
    status: 'secure',
    alerts: [],
    repositionAlertShownThisCycle: false,  // Track if alert was already shown for current reposition event
    metrics: {
        blur: { value: 0, status: 'secure' },
        shake: { value: 0, status: 'secure' },
        glare: { value: 0, status: 'secure' },
        liveness: { value: 'INITIALIZING...', status: 'secure' }
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
}

function showRepositionAlert() {
    repositionAlertModal.classList.remove('hidden');
}

function dismissRepositionAlert() {
    repositionAlertModal.classList.add('hidden');
    systemState.repositionAlertShownThisCycle = false;  // Reset flag
    // Tell backend that alert was dismissed so it can reset tracking
    socket.emit('dismiss_reposition_alert');
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

function updateAudioIndicator(isRecording) {
    const indicator = document.getElementById('audioIndicator');
    if (isRecording) {
        indicator.classList.add('recording');
        indicator.querySelector('.recording-text').textContent = 'Audio Logging: ON';
    } else {
        indicator.classList.remove('recording');
        indicator.querySelector('.recording-text').textContent = 'Audio Logging: OFF';
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
            triggerAlert('SHAKE', '⚠️ Camera Vibration Detected - Minor Movement');
        }
    }

    if (data.reposition) {
        if (data.reposition.alert_active && !systemState.repositionAlertShownThisCycle) {
            // Only show alert once per repositioning event
            systemState.repositionAlertShownThisCycle = true;
            showRepositionAlert();
            triggerAlert('REPOSITION', '🚨 CAMERA REPOSITIONING DETECTED - SUSTAINED MOVEMENT!');
        } else if (!data.reposition.alert_active) {
            // Reset flag when alert clears
            systemState.repositionAlertShownThisCycle = false;
        }
    }

    if (data.glare) {
        const glareStatus = data.glare.detected ? 'alert' : 'secure';
        
        // Show percentage value
        glareValue.textContent = data.glare.percentage ? data.glare.percentage.toFixed(1) + '%' : '-';
        
        // Update histogram visualization
        if (data.glare.histogram) {
            systemState.metrics.glare.histogram = data.glare.histogram;
            updateGlareHistogram(data.glare.histogram, data.glare.detected);
        }
        
        // Update indicator
        glareIndicator.classList.remove('secure', 'alert', 'warning');
        glareIndicator.classList.add(glareStatus);

        if (data.glare.detected) {
            triggerAlert('GLARE', `Critical Threat: Glare Detected (${data.glare.percentage.toFixed(1)}%)!`);
        }
    }

    if (data.liveness) {
        // Display status text instead of numeric value
        let livenessStatus = 'secure';
        if (data.liveness.frozen || data.liveness.blackout || data.liveness.major_tamper) {
            livenessStatus = 'alert';
        } else if (!data.liveness.is_active) {
            livenessStatus = 'warning';
        }
        
        // Show the text status instead of numeric value
        updateMetric('liveness', data.liveness.status, livenessStatus);

        if (data.liveness.frozen) {
            triggerAlert('LIVENESS', 'Frozen Feed Detected - Potential Replay Attack!');
        } else if (data.liveness.blackout) {
            triggerAlert('LIVENESS', 'Blackout Detected - Camera Covered!');
        } else if (data.liveness.major_tamper) {
            triggerAlert('LIVENESS', 'Major Tamper Detected - Scene Change!');
        }
    }

    checkAndClearAlerts();
});

socket.on('alert', (data) => {
    console.log('Alert received:', data);
    triggerAlert(data.type || 'SYSTEM', data.message || 'Unknown alert');
    
    // If it's an audio logging alert, update the indicator
    if (data.type === 'AUDIO_LOGGING') {
        updateAudioIndicator(true);
        
        // Update placeholder text when audio logging starts
        if (subtitleLog.children.length === 1 && 
            subtitleLog.children[0].textContent.includes('Audio logging disabled')) {
            const placeholderEntry = subtitleLog.children[0];
            placeholderEntry.querySelector('.log-message').textContent = 'Audio logging enabled';
        }
    }
});

socket.on('subtitle', (data) => {
    console.log('Subtitle received:', data);
    const time = getCurrentTime();
    
    // Clear placeholder if this is the first real entry
    if (subtitleLog.children.length === 1 && 
        subtitleLog.children[0].textContent.includes('Audio logging disabled')) {
        subtitleLog.innerHTML = '';
    }
    
    const subtitleEntry = document.createElement('div');
    subtitleEntry.className = `log-entry ${data.is_blackbox ? 'warning' : 'secure'}`;
    subtitleEntry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-message">[${data.type}] ${data.text}</span>
    `;
    
    subtitleLog.insertBefore(subtitleEntry, subtitleLog.firstChild);
    
    // Keep only last 30 entries
    while (subtitleLog.children.length > 30) {
        subtitleLog.removeChild(subtitleLog.lastChild);
    }
});

socket.on('alert_clear', () => {
    console.log('Alert cleared');
    updateAudioIndicator(false);
    
    // Change back to "disabled" if no actual entries yet
    if (subtitleLog.children.length === 1 && 
        subtitleLog.children[0].textContent.includes('Audio logging enabled')) {
        const placeholderEntry = subtitleLog.children[0];
        placeholderEntry.querySelector('.log-message').textContent = 'Audio logging disabled';
    }
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
        triggerAlert('LIVENESS', 'Test: Frozen Feed Detected');
        updateMetric('liveness', 'FROZEN FEED ALERT', 'alert');
    }

    if (event.key.toLowerCase() === 'r') {
        updateSystemStatus(false);
        updateMetric('blur', 75, 'secure');
        updateMetric('shake', 0.5, 'secure');
        updateMetric('glare', 0, 'secure');
        updateMetric('liveness', 'LIVE', 'secure');
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
    
    // Setup tab switching
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.dataset.tab;
            
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active state from all buttons
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            button.classList.add('active');
        });
    });

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
    
    // Poll the HTTP API for detection data as fallback
    setInterval(() => {
        fetch('/api/detection')
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                console.log('Detection data from API:', data);
                
                if (data.blur) {
                    const blurStatus = data.blur.detected ? 'alert' : 'secure';
                    updateMetric('blur', data.blur.variance || 0, blurStatus);
                }

                if (data.shake) {
                    const shakeStatus = data.shake.detected ? 'alert' : 'secure';
                    updateMetric('shake', data.shake.magnitude || 0, shakeStatus);
                }

                if (data.glare) {
                    const glareStatus = data.glare.detected ? 'alert' : 'secure';
                    updateMetric('glare', data.glare.detected ? 1 : 0, glareStatus);
                }

                if (data.liveness) {
                    let livenessStatus = 'secure';
                    if (data.liveness.frozen || data.liveness.blackout || data.liveness.major_tamper) {
                        livenessStatus = 'alert';
                    } else if (!data.liveness.is_active) {
                        livenessStatus = 'warning';
                    }
                    updateMetric('liveness', data.liveness.status, livenessStatus);
                }
            })
            .catch(error => {
                // Silently fail - Socket.IO should handle this
            });
    }, 200);
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
