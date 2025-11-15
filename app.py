"""
AEGIS: Active Defense System - Main Flask Server
Streams live video feed with tamper detection and real-time alerts via Socket.IO
"""

from flask import Flask, render_template, Response, send_from_directory
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import tamper_detector
from tamper_detector import fix_blur_unsharp_mask
import os
import threading
import time
import speech_recognition

# Try to import glare rescue functions, but make them optional
try:
    from Sensor.glare_rescue import apply_msr_hsv, apply_unsharp_mask, get_image_viability_stats
    GLARE_RESCUE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Glare rescue functions not available: {e}")
    GLARE_RESCUE_AVAILABLE = False
    # Dummy functions
    def apply_msr_hsv(frame):
        return frame
    def apply_unsharp_mask(frame, amount=1.0):
        return frame

# ============================================================================
# INITIALIZATION
# ============================================================================

app = Flask(__name__, 
            template_folder='./frontend',
            static_folder='./frontend',
            static_url_path='')

socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
BLUR_THRESHOLD = 100.0
SHAKE_THRESHOLD = 6.0
REPOSITION_THRESHOLD = 5.0  # Threshold for directional shift magnitude - lower for easier detection
CAMERA_INDEX = 0
BLUR_FIX_ENABLED = True
BLUR_FIX_STRENGTH = 5
GLARE_RESCUE_ENABLED = True  # Disabled for now - enable after testing
GLARE_RESCUE_MODE = 'MSR'  # Options: 'CLAHE', 'MSR'

# Sensor enable/disable configuration - all enabled by default
sensor_config = {
    'blur': True,           # Blur detection
    'shake': True,          # Shake detection
    'glare': True,          # Glare detection
    'liveness': True,       # Liveness detection
    'reposition': True,     # Reposition detection
    'blur_fix': True,       # Blur correction
    'glare_rescue': True,   # Glare rescue
    'audio_alerts': True    # Audio alerts/logging
}
sensor_config_lock = threading.Lock()  # Thread-safe config updates

# Liveness detection configuration
LIVENESS_THRESHOLD = 2.0        # LOW threshold: detects freezing/static feed
MAJOR_TAMPER_THRESHOLD = 60.0   # HIGH threshold: detects sudden, massive scene change
BLACKOUT_BRIGHTNESS_THRESHOLD = 25.0  # Mean pixel intensity threshold for blackout (0-255 range)
LIVENESS_CHECK_INTERVAL = 3.0   # Time (in seconds) between capturing a new reference frame
LIVENESS_ACTIVATION_TIME = 10.0 # Time (s) after startup before "FROZEN FEED ALERT" becomes active

# Global variables
cap = None
prev_gray = None
current_frame = None  # Raw frame without text
processed_frame = None  # Frame with detection text
frame_lock = threading.Lock()
reposition_alert_active = False
reposition_alert_shown = False  # Track if we've already shown the alert for this event
reposition_alert_frames = 0

# Liveness detection globals
liveness_reference_frame = None
liveness_reference_time = None
liveness_startup_time = None
liveness_is_frozen = False
liveness_status_text = "INITIALIZING"

# Initialize frames with blank black images (640x480) so they display while loading
current_frame = np.zeros((480, 640, 3), dtype=np.uint8)
processed_frame = np.zeros((480, 640, 3), dtype=np.uint8)

# Audio logging globals
LOG_AUDIO_SUBTITLES = False
audio_logging_lock = threading.Lock()
detection_data_cache = None

# ============================================================================
# CAMERA AND DETECTION FUNCTIONS
# ============================================================================

def initialize_camera():
    """Initialize the camera capture object."""
    global cap
    
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return False
    
    # Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    print("Camera initialized successfully.")
    return True

def audio_logging_thread():
    """
    Audio logging thread that continuously listens for speech when triggered.
    Runs in a separate daemon thread and sends recognized speech to the frontend.
    """
    global LOG_AUDIO_SUBTITLES
    
    r = speech_recognition.Recognizer()
    print("[AUDIO] Audio logger thread started - waiting for tamper detection...")
    
    while True:
        # Thread-safe check of audio logging flag
        with audio_logging_lock:
            should_log = LOG_AUDIO_SUBTITLES
        
        if should_log:
            try:
                with speech_recognition.Microphone() as source:
                    print("[AUDIO] Listening for speech...")
                    audio = r.listen(source, timeout=3, phrase_time_limit=5)
                    print("[AUDIO] Audio received, recognizing...")
                
                try:
                    text = r.recognize_google(audio)
                    print(f"[AUDIO] Recognized speech: {text}")
                    
                    # Send the subtitle to the frontend
                    try:
                        with app.app_context():
                            socketio.emit('subtitle', {
                                'type': 'SPEECH',
                                'text': text,
                                'is_blackbox': False
                            }, namespace='/', skip_sid=None)
                            print(f"[AUDIO] ✓ Subtitle emitted: {text}")
                    except Exception as e:
                        print(f"[AUDIO] ✗ Error emitting subtitle: {e}")
                except speech_recognition.UnknownValueError:
                    print("[AUDIO] Could not understand audio")
                except speech_recognition.RequestError as e:
                    print(f"[AUDIO] API Error: {e}")
                
            except speech_recognition.WaitTimeoutError:
                print("[AUDIO] No speech detected (timeout)")
            except speech_recognition.MicrophoneError as e:
                print(f"[AUDIO] Microphone error: {e}")
            except Exception as e:
                print(f"[AUDIO] ✗ Error: {e}")
        else:
            time.sleep(1)  # Sleep when not logging

def camera_thread():
    """
    Continuously capture frames and run detections.
    This runs in a separate thread to avoid blocking.
    """
    global prev_gray, current_frame, processed_frame, frame_lock, detection_data_cache
    global liveness_reference_frame, liveness_reference_time, liveness_startup_time
    global liveness_is_frozen, liveness_status_text
    
    print("[CAMERA] Camera thread starting...")
    
    if cap is None:
        print("[CAMERA] ERROR: Camera not initialized!")
        return
    
    ret, first_frame = cap.read()
    if not ret:
        print("[CAMERA] Error: Could not read first frame.")
        return
    
    prev_gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
    liveness_reference_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
    liveness_reference_time = time.time()
    liveness_startup_time = time.time()  # Grace period tracker
    frame_count = 0
    
    print("[CAMERA] Camera thread initialized successfully. Starting main loop...")
    print(f"[CAMERA] Frame size: {first_frame.shape}")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[CAMERA] Error: Could not read frame.")
            break
        
        frame_count += 1
        if frame_count == 1:
            print("[CAMERA] ✓ First frame captured! Stream is live.")
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        current_time = time.time()
        
        # --- RUN DETECTIONS ---
        is_blurred, blur_variance = tamper_detector.check_blur(gray, threshold=BLUR_THRESHOLD)
        is_shaken, shake_magnitude = tamper_detector.check_shake(gray, prev_gray, threshold=SHAKE_THRESHOLD)
        is_repositioned, shift_magnitude, shift_x, shift_y = tamper_detector.detect_camera_reposition(
            gray, prev_gray, threshold_shift=REPOSITION_THRESHOLD
        )
        is_glare, glare_percentage, glare_histogram = tamper_detector.check_glare(frame, threshold_pct=10.0)
        
        # --- LIVENESS DETECTION ---
        diff_frame = cv2.absdiff(gray, liveness_reference_frame)
        mean_diff = np.mean(diff_frame)
        mean_brightness = np.mean(gray)
        
        # Check if grace period (10s startup) has passed
        is_liveness_active = (current_time - liveness_startup_time) > LIVENESS_ACTIVATION_TIME
        
        # Determine liveness state
        is_blackout = mean_brightness < BLACKOUT_BRIGHTNESS_THRESHOLD
        is_major_tamper = mean_diff > MAJOR_TAMPER_THRESHOLD
        is_frozen = False
        
        if is_liveness_active and mean_diff < LIVENESS_THRESHOLD:
            is_frozen = True
        
        # Update liveness status text
        if is_blackout:
            liveness_status_text = "BLACKOUT DETECTED"
        elif is_major_tamper:
            liveness_status_text = "MAJOR TAMPER DETECTED"
        elif is_frozen:
            liveness_status_text = "FROZEN FEED ALERT"
        elif not is_liveness_active:
            time_left = LIVENESS_ACTIVATION_TIME - (current_time - liveness_startup_time)
            liveness_status_text = f"INITIALIZING... ({time_left:.1f}s)"
        else:
            liveness_status_text = "LIVE"
        
        # Update reference frame if check interval has passed
        if current_time - liveness_reference_time >= LIVENESS_CHECK_INTERVAL:
            liveness_reference_frame = gray.copy()
            liveness_reference_time = current_time
        
        # Store frozen state globally
        liveness_is_frozen = is_frozen
        
        # Read sensor configuration (thread-safe)
        with sensor_config_lock:
            sensor_enabled = sensor_config.copy()
        
        # Respect sensor configuration - disable detections if sensor is disabled
        if not sensor_enabled['blur']:
            is_blurred = False
        if not sensor_enabled['shake']:
            is_shaken = False
        if not sensor_enabled['glare']:
            is_glare = False
        if not sensor_enabled['liveness']:
            is_frozen = is_blackout = is_major_tamper = False
            liveness_status_text = "INITIALIZING"
        if not sensor_enabled['reposition']:
            is_repositioned = False
        
        # Determine if ANY tamper is detected (for audio logging trigger)
        any_tamper_detected = is_blurred or is_shaken or is_glare or is_frozen or is_blackout or is_major_tamper
        
        # Manage repositioning alert state
        global reposition_alert_active, reposition_alert_shown, reposition_alert_frames
        if is_repositioned:
            reposition_alert_frames = 0
            # Only set alert_active ONCE per repositioning event
            if not reposition_alert_shown:
                reposition_alert_shown = True
                reposition_alert_active = True  # Send alert to frontend ONLY on first detection
                print(f"🚨 REPOSITION DETECTED - Magnitude: {shift_magnitude:.2f}px, Shift: ({shift_x:.2f}, {shift_y:.2f})")
            else:
                # Motion still detected but we've already shown alert, keep it inactive
                reposition_alert_active = False
        else:
            reposition_alert_frames += 1
            if reposition_alert_frames > 30:  # Clear alert after 30 frames without detection
                reposition_alert_shown = False  # Reset flag when motion fully stops
            # Always keep alert inactive when motion isn't detected
            reposition_alert_active = False
        
        # Prepare detection data for frontend
        detection_data = {
            'blur': {
                'detected': bool(is_blurred),
                'variance': float(blur_variance)
            },
            'shake': {
                'detected': bool(is_shaken),
                'magnitude': float(shake_magnitude)
            },
            'reposition': {
                'detected': bool(is_repositioned),
                'magnitude': float(shift_magnitude),
                'shift_x': float(shift_x),
                'shift_y': float(shift_y),
                'alert_active': bool(reposition_alert_active)
            },
            'glare': {
                'detected': bool(is_glare),
                'percentage': float(glare_percentage),
                'histogram': glare_histogram.tolist() if glare_histogram is not None and hasattr(glare_histogram, 'tolist') else (list(glare_histogram) if glare_histogram else [])
            },
            'liveness': {
                'frozen': bool(is_frozen),
                'blackout': bool(is_blackout),
                'major_tamper': bool(is_major_tamper),
                'status': liveness_status_text,
                'mean_diff': float(mean_diff),
                'mean_brightness': float(mean_brightness),
                'is_active': bool(is_liveness_active)
            }
        }
        
        # --- AUDIO LOGGING TRIGGER ---
        # Audio logging is triggered when ANY tamper (blur, shake, glare) is detected
        global LOG_AUDIO_SUBTITLES
        should_enable_audio = any_tamper_detected and sensor_enabled['audio_alerts']
        
        with audio_logging_lock:
            current_audio_state = LOG_AUDIO_SUBTITLES
        
        if should_enable_audio:
            if not current_audio_state:
                with audio_logging_lock:
                    LOG_AUDIO_SUBTITLES = True
                print(f"[TRIGGER] ✓ Audio logging ENABLED - Detections: Blur={is_blurred}, Shake={is_shaken}, Glare={is_glare}, Frozen={is_frozen}")
                try:
                    with app.app_context():
                        socketio.emit('alert', {
                            'type': 'AUDIO_LOGGING',
                            'message': 'ALERT: TAMPER DETECTED! Audio logging engaged.'
                        }, namespace='/', skip_sid=None)
                except Exception as e:
                    print(f"[TRIGGER] ✗ Error emitting alert: {e}")
        else:
            if current_audio_state:
                with audio_logging_lock:
                    LOG_AUDIO_SUBTITLES = False
                print(f"[TRIGGER] ✓ Audio logging DISABLED - No tampering detected")
                try:
                    with app.app_context():
                        socketio.emit('alert_clear', {}, namespace='/', skip_sid=None)
                except Exception as e:
                    print(f"[TRIGGER] ✗ Error emitting alert_clear: {e}")
        
        # Cache detection data
        detection_data_cache = detection_data
        
        # Emit detection update to all connected clients
        try:
            with app.app_context():
                socketio.emit('detection_update', detection_data, namespace='/', skip_sid=None)
            if frame_count % 30 == 0:
                print(f"Emitted detection data: Blur={blur_variance:.2f}, Shake={shake_magnitude:.2f}, Glare={glare_percentage:.2f}%")
        except Exception as e:
            print(f"Error emitting detection data: {e}")
        
        # --- GLARE RESCUE (Applied FIRST, before blur fixing) ---
        frame_for_processing = frame.copy()  # Start with original frame
        if is_glare and GLARE_RESCUE_ENABLED and sensor_enabled['glare_rescue']:
            try:
                print(f"[GLARE] Applying glare rescue (mode: {GLARE_RESCUE_MODE})...")
                if GLARE_RESCUE_MODE == 'MSR':
                    # MSR (Multi-Scale Retinex) in HSV space - better for color preservation
                    frame_for_processing = apply_msr_hsv(frame_for_processing)
                else:
                    # CLAHE + Unsharp mask - proven method
                    lab_frame = cv2.cvtColor(frame_for_processing, cv2.COLOR_BGR2LAB)
                    l, a, b = cv2.split(lab_frame)
                    clahe = cv2.createCLAHE(clipLimit=12.0, tileGridSize=(4, 4))
                    l_clahe = clahe.apply(l)
                    enhanced_lab_frame = cv2.merge((l_clahe, a, b))
                    frame_for_processing = cv2.cvtColor(enhanced_lab_frame, cv2.COLOR_LAB2BGR)
                    frame_for_processing = apply_unsharp_mask(frame_for_processing, amount=1.0)
                print(f"[GLARE] Rescue applied successfully!")
            except Exception as e:
                print(f"[GLARE] Rescue error: {e}")
                frame_for_processing = frame.copy()
        
        # Create processed frame with blur fixing (applied AFTER glare rescue)
        if BLUR_FIX_ENABLED and sensor_enabled['blur_fix']:
            # Always apply unsharp masking, but dynamically adjust strength based on blur variance
            # Lower variance = more blurry = higher strength
            # Variance range: typically 0-300+
            # Map to strength range: 5.0 to 8.5 (higher base for inherently blurry camera)
            if blur_variance < 50:
                dynamic_strength = 8.5  # Very blurry - maximum sharpening
            elif blur_variance < 100:
                dynamic_strength = 3 + (100 - blur_variance) / 8  # Scale between 5.0-8.5
            else:
                dynamic_strength = max(3, 8.5 - (blur_variance - 100) / 40)  # Scale down, but keep at 5.0 minimum
            
            # Apply unsharp masking with dynamic strength to the glare-rescued frame
            processed_frame_final = fix_blur_unsharp_mask(frame_for_processing, kernel_size=5, sigma=1.0, strength=dynamic_strength)
        else:
            # Blur fix disabled, use glare-rescued frame as-is
            processed_frame_final = frame_for_processing
        
        # Update previous frame
        prev_gray = gray
        
        # Store frames for streaming
        with frame_lock:
            current_frame = frame.copy()  # Raw unmodified frame
            processed_frame = processed_frame_final.copy()  # Frame with glare rescue + blur fix applied
        
        # Small delay to prevent CPU overload
        if frame_count % 10 == 0:
            print(f"Frame {frame_count}: Blur={blur_variance:.2f}, Shake={shake_magnitude:.2f}")
        
        # Sleep briefly to avoid 100% CPU usage (~30 FPS)
        time.sleep(0.01)

def gen_frames():
    """
    Generator function that yields frames as MJPEG encoded frames.
    """
    global current_frame, frame_lock
    
    while True:
        if current_frame is None:
            continue
        
        with frame_lock:
            if current_frame is None:
                continue
            frame = current_frame.copy()
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        
        frame_bytes = buffer.tobytes()
        
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n'
               + frame_bytes + b'\r\n')

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the main dashboard HTML."""
    return send_from_directory('./Frontend', 'index.html')

@app.route('/video_frame')
def video_frame():
    """Serve a single JPEG frame from the raw feed (without detection text)."""
    global current_frame, frame_lock
    
    if current_frame is None or frame_lock is None:
        return "No frame available", 503
    
    try:
        with frame_lock:
            if current_frame is None:
                return "No frame available", 503
            frame = current_frame.copy()
    except:
        return "Error accessing frame", 500
    
    # Encode frame as JPEG
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ret:
        return "Could not encode frame", 500
    
    return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route('/processed_frame')
def get_processed_frame():
    """Serve a single JPEG frame from the processed feed (with detection text)."""
    global processed_frame, frame_lock
    
    if processed_frame is None or frame_lock is None:
        return "No frame available", 503
    
    try:
        with frame_lock:
            if processed_frame is None:
                return "No frame available", 503
            frame = processed_frame.copy()
    except:
        return "Error accessing frame", 500
    
    # Encode frame as JPEG
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ret:
        return "Could not encode frame", 500
    
    return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route('/api/detection')
def get_detection():
    """Get the latest detection data as JSON."""
    global detection_data_cache
    
    if detection_data_cache is None:
        return {"error": "No detection data available"}, 503
    
    return detection_data_cache

@app.route('/video_feed')
def video_feed():
    """Stream the raw video feed with detections."""
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/processed_feed')
def processed_feed():
    """Stream processed video feed (same as raw for now)."""
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/style.css')
def serve_css():
    """Serve the CSS file."""
    return send_from_directory('./Frontend', 'style.css')

@app.route('/script.js')
def serve_js():
    """Serve the JavaScript file."""
    return send_from_directory('./Frontend', 'script.js')

# ============================================================================
# SOCKET.IO EVENT HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print("Client connected")
    emit('status_update', {'status': 'healthy', 'message': 'Connected to Aegis server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print("Client disconnected")

@socketio.on('test_alert')
def handle_test_alert(data):
    """Emit a test alert to all clients."""
    emit('alert', {
        'type': 'TEST',
        'message': data.get('message', 'Test alert from server')
    }, broadcast=True)

@socketio.on('dismiss_reposition_alert')
def handle_dismiss_reposition_alert():
    """Handle reposition alert dismissal from frontend."""
    global reposition_alert_shown
    reposition_alert_shown = False
    print("Reposition alert dismissed by user")

@socketio.on('get_sensor_states')
def handle_get_sensor_states():
    """Send current sensor configuration to client."""
    with sensor_config_lock:
        emit('sensor_states', sensor_config)

@socketio.on('set_sensor_enabled')
def handle_set_sensor_enabled(data):
    """Handle sensor enable/disable request from frontend."""
    sensor = data.get('sensor')
    enabled = data.get('enabled', True)
    
    if sensor in sensor_config:
        with sensor_config_lock:
            sensor_config[sensor] = enabled
        print(f"Sensor '{sensor}' set to {enabled}")
        emit('status_update', {'status': 'healthy', 'message': f'{sensor} toggled to {enabled}'})
    else:
        print(f"Warning: Unknown sensor '{sensor}'")

# ============================================================================
# STARTUP AND SHUTDOWN
# ============================================================================

def startup():
    """Initialize the application."""
    print("=" * 60)
    print("AEGIS: ACTIVE DEFENSE SYSTEM")
    print("=" * 60)
    print(f"Blur Threshold: {BLUR_THRESHOLD}")
    print(f"Shake Threshold: {SHAKE_THRESHOLD}")
    print("-" * 60)
    
    if not initialize_camera():
        print("FATAL: Could not initialize camera. Exiting.")
        return False
    
    return True

if __name__ == '__main__':
    if startup():
        # Start audio logging thread
        audio_thread = threading.Thread(target=audio_logging_thread, daemon=True)
        audio_thread.start()
        print("Audio logging thread started.")
        
        # Start camera thread
        camera_thread_obj = threading.Thread(target=camera_thread, daemon=True)
        camera_thread_obj.start()
        print("Camera thread started.")
        
        print("Starting Flask server...")
        print("Open your browser and go to: http://localhost:5000")
        print("Press Ctrl+C to stop the server.")
        print("-" * 60)
        
        try:
            socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            if cap:
                cap.release()
            print("Goodbye!")
