"""
Liveness Video Watermark Validation Module
Extracts and validates HMAC watermark tokens from video frames.
"""

import cv2
import hmac
import hashlib
import re
import json
from typing import Dict, List, Tuple
import os

# Configuration - MUST MATCH dynamic_watermarker.py
SERVER_SECRET_KEY = b"YourUnbreakableWatermarkSecretKey12345"


def calculate_expected_hmac_token(timestamp_seconds):
    """
    Calculates the expected HMAC-SHA256 token for a given timestamp.
    This matches the logic in dynamic_watermarker.py generate_hmac_token()
    """
    message = str(timestamp_seconds).encode('utf-8')
    
    hmac_digest = hmac.new(
        key=SERVER_SECRET_KEY,
        msg=message,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Truncate to last 4 hex chars and convert to 0000-9999
    last_4_hex = hmac_digest[-4:]
    token_int = int(last_4_hex, 16)
    final_token = token_int % 10000
    
    return f"{final_token:04d}"


def extract_hmac_token_from_frame(frame):
    """
    Extracts the HMAC token from a video frame using OCR/regex.
    Looks for pattern: TST-H:XXXX
    
    Args:
        frame: OpenCV frame (BGR)
    
    Returns:
        Extracted token string (XXXX) or None if not found
    """
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        
        # Get the region of interest (bottom-right corner where watermark is)
        h, w = frame.shape[:2]
        roi = frame[max(0, h-100):h, max(0, w-300):w]
        
        # Convert BGR to RGB for PIL
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(roi_rgb)
        
        # Use Tesseract to extract text
        extracted_text = pytesseract.image_to_string(pil_image)
        
        # Look for TST-H:XXXX pattern
        match = re.search(r'TST-H:(\d{4})', extracted_text)
        if match:
            return match.group(1)
        
        return None
    
    except ImportError:
        # Fallback: simple regex pattern matching on frame text
        # This is a basic approach that works if text is clear
        return extract_hmac_token_fallback(frame)


def extract_hmac_token_fallback(frame):
    """
    Fallback method to extract HMAC token from frame without OCR.
    Uses template matching and contour detection.
    """
    try:
        h, w = frame.shape[:2]
        roi = frame[max(0, h-120):h, max(0, w-320):w]
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to isolate text
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        # This is a very basic fallback - in production, use pytesseract
        # For now, return None to indicate OCR is needed
        return None
    
    except Exception as e:
        print(f"[WATERMARK] Fallback extraction failed: {e}")
        return None


def validate_video_watermarks(video_file_path, video_start_timestamp=None):
    """
    Validates watermarks in a video file by checking HMAC tokens at 1-second intervals.
    
    Args:
        video_file_path: Path to the video file
        video_start_timestamp: Unix timestamp when video recording started (if known)
                              If not provided, uses video creation time or current time
    
    Returns:
        Dict with validation results:
        {
            'overall_status': 'PASS' or 'FAIL',
            'tampered_frames': [list of problematic frame info],
            'frame_results': {
                'second_0': {'expected_token': 'XXXX', 'extracted_token': 'YYYY', 'status': 'PASS'},
                'second_1': {...},
                ...
            },
            'total_frames_checked': int,
            'tampered_count': int
        }
    """
    if not os.path.exists(video_file_path):
        return {
            'overall_status': 'FAIL',
            'error': f'Video file not found: {video_file_path}',
            'frame_results': {},
            'total_frames_checked': 0,
            'tampered_count': 0,
            'tampered_frames': []
        }
    
    cap = cv2.VideoCapture(video_file_path)
    
    if not cap.isOpened():
        return {
            'overall_status': 'FAIL',
            'error': f'Could not open video file: {video_file_path}',
            'frame_results': {},
            'total_frames_checked': 0,
            'tampered_count': 0,
            'tampered_frames': []
        }
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    
    frame_interval = int(fps)  # Check every 1 second (fps frames)
    
    # Determine video start timestamp
    if video_start_timestamp is None:
        # Use file modification time as fallback
        import time as time_module
        video_start_timestamp = int(time_module.time())
    
    frame_results = {}
    tampered_frames = []
    frame_count = 0
    checked_count = 0
    tampered_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Check frame at 1-second intervals
            if frame_count % frame_interval == 0:
                second_index = frame_count // frame_interval
                expected_timestamp = video_start_timestamp + second_index
                expected_token = calculate_expected_hmac_token(expected_timestamp)
                
                # Try to extract token from frame
                extracted_token = extract_hmac_token_from_frame(frame)
                
                frame_key = f'second_{second_index}'
                
                if extracted_token is None:
                    # Could not extract token - mark as suspicious
                    status = 'UNKNOWN'
                    tampered_count += 1
                    frame_results[frame_key] = {
                        'expected_token': expected_token,
                        'extracted_token': None,
                        'status': status,
                        'timestamp': expected_timestamp,
                        'note': 'Could not extract watermark from frame'
                    }
                    tampered_frames.append({
                        'second': second_index,
                        'status': status,
                        'reason': 'Watermark extraction failed'
                    })
                
                elif extracted_token == expected_token:
                    # Token matches - PASS
                    frame_results[frame_key] = {
                        'expected_token': expected_token,
                        'extracted_token': extracted_token,
                        'status': 'PASS',
                        'timestamp': expected_timestamp
                    }
                
                else:
                    # Token mismatch - FAIL (fake feed detected)
                    status = 'FAIL'
                    tampered_count += 1
                    frame_results[frame_key] = {
                        'expected_token': expected_token,
                        'extracted_token': extracted_token,
                        'status': status,
                        'timestamp': expected_timestamp,
                        'note': 'Watermark token mismatch - possible replay attack'
                    }
                    tampered_frames.append({
                        'second': second_index,
                        'status': status,
                        'expected_token': expected_token,
                        'extracted_token': extracted_token,
                        'reason': 'Token mismatch detected'
                    })
                
                checked_count += 1
            
            frame_count += 1
    
    except Exception as e:
        print(f"[WATERMARK] Error processing video: {e}")
        return {
            'overall_status': 'FAIL',
            'error': str(e),
            'frame_results': frame_results,
            'total_frames_checked': checked_count,
            'tampered_count': tampered_count,
            'tampered_frames': tampered_frames
        }
    
    finally:
        cap.release()
    
    # Determine overall status
    overall_status = 'PASS' if tampered_count == 0 else 'FAIL'
    
    return {
        'overall_status': overall_status,
        'frame_results': frame_results,
        'total_frames_checked': checked_count,
        'tampered_count': tampered_count,
        'tampered_frames': tampered_frames,
        'success': True
    }


def validate_video_watermarks_basic(video_file_path, video_start_timestamp=None):
    """
    Basic watermark validation that works without OCR.
    Checks if watermark presence is consistent throughout video.
    """
    if not os.path.exists(video_file_path):
        return {
            'overall_status': 'FAIL',
            'error': f'Video file not found: {video_file_path}',
            'frame_results': {},
            'total_frames_checked': 0
        }
    
    cap = cv2.VideoCapture(video_file_path)
    
    if not cap.isOpened():
        return {
            'overall_status': 'FAIL',
            'error': f'Could not open video file: {video_file_path}',
            'frame_results': {},
            'total_frames_checked': 0
        }
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    
    frame_interval = int(fps)
    frame_results = {}
    frame_count = 0
    checked_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                second_index = frame_count // frame_interval
                frame_key = f'second_{second_index}'
                
                # Basic check: look for white text in bottom-right corner
                h, w = frame.shape[:2]
                roi = frame[max(0, h-120):h, max(0, w-320):w]
                
                # Check if there's significant white content (watermark)
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                white_pixels = (gray > 200).sum()
                white_ratio = white_pixels / (roi.shape[0] * roi.shape[1])
                
                has_watermark = white_ratio > 0.01  # At least 1% white pixels
                
                frame_results[frame_key] = {
                    'has_watermark': has_watermark,
                    'white_pixel_ratio': float(white_ratio),
                    'status': 'PASS' if has_watermark else 'UNKNOWN'
                }
                
                checked_count += 1
            
            frame_count += 1
    
    finally:
        cap.release()
    
    # Check consistency
    has_watermark_frames = [v for v in frame_results.values() if v.get('has_watermark', False)]
    watermark_consistency = len(has_watermark_frames) / max(1, len(frame_results))
    
    overall_status = 'PASS' if watermark_consistency > 0.8 else 'SUSPICIOUS'
    
    return {
        'overall_status': overall_status,
        'frame_results': frame_results,
        'total_frames_checked': checked_count,
        'watermark_consistency': watermark_consistency
    }
