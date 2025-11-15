"""
AEGIS: Active Defense System - Main Flask Server
Streams live video feed with tamper detection and real-time alerts via Socket.IO
"""

from flask import Flask, render_template, Response, send_from_directory
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import tamper_detector
import os
import threading
import time

# ============================================================================
# INITIALIZATION
# ============================================================================

app = Flask(__name__, 
            template_folder='./frontend',
            static_folder='./frontend',
            static_url_path='')

socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
BLUR_THRESHOLD = 90.0
SHAKE_THRESHOLD = 6.0
CAMERA_INDEX = 0

# Global variables
cap = None
prev_gray = None
current_frame = None  # Raw frame without text
processed_frame = None  # Frame with detection text
frame_lock = None

# ============================================================================
# CAMERA AND DETECTION FUNCTIONS
# ============================================================================

def initialize_camera():
    """Initialize the camera capture object."""
    global cap, frame_lock
    
    frame_lock = threading.Lock()
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

def camera_thread():
    """
    Continuously capture frames and run detections.
    This runs in a separate thread to avoid blocking.
    """
    global prev_gray, current_frame, processed_frame, frame_lock, detection_data_cache
    
    ret, first_frame = cap.read()
    if not ret:
        print("Error: Could not read first frame.")
        return
    
    prev_gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
        
        frame_count += 1
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # --- RUN DETECTIONS ---
        is_blurred, blur_variance = tamper_detector.check_blur(gray, threshold=BLUR_THRESHOLD)
        is_shaken, shake_magnitude = tamper_detector.check_shake(gray, prev_gray, threshold=SHAKE_THRESHOLD)
        is_glare, glare_percentage, glare_histogram = tamper_detector.check_glare(frame, threshold_pct=10.0)
        
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
            'glare': {
                'detected': bool(is_glare),
                'percentage': float(glare_percentage),
                'histogram': glare_histogram
            },
            'liveness': {
                'frozen': False,
                'value': 1
            }
        }
        
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
        
        # Create processed frame (no text overlays - metrics shown in dashboard below)
        frame_with_text = frame.copy()
        
        # Update previous frame
        prev_gray = gray
        
        # Store frames for streaming
        with frame_lock:
            current_frame = frame.copy()  # Raw frame without text
            processed_frame = frame_with_text.copy()  # Frame with detection text
        
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
