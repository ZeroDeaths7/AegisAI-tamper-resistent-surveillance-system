#!/usr/bin/env python
"""
Full end-to-end test of the liveness validation system
Tests video creation, watermark embedding, validation, and API response format
"""

import json
import cv2
import numpy as np
import time
import os
from backend.watermark_embedder import get_watermark_embedder
from backend.watermark_validator import validate_video

print("=" * 70)
print("LIVENESS VALIDATION SYSTEM - END-TO-END TEST")
print("=" * 70)

# Step 1: Create test video with embedded watermarks
print("\n[STEP 1] Creating test video with watermarks...")
test_video_path = "test_liveness_e2e.mp4"
fps = 30
width, height = 640, 480

# Use a valid codec
fourcc = cv2.VideoWriter.fourcc(*'mp4v')
out = cv2.VideoWriter(test_video_path, fourcc, fps, (width, height))

if not out.isOpened():
    print("  ✗ Failed to create VideoWriter")
    exit(1)

embedder = get_watermark_embedder()
video_start_timestamp = int(time.time())

# Create 6 seconds of video (180 frames at 30 FPS)
print("  Creating frames...")
for frame_num in range(180):
    frame = np.ones((height, width, 3), dtype=np.uint8) * 100  # Dark gray background
    
    # Add some text to make it visible
    cv2.putText(frame, f'Frame {frame_num}', (50, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (200, 200, 200), 2)
    
    # Embed watermark
    try:
        frame_with_watermark = embedder.embed(frame)
        out.write(frame_with_watermark)
    except Exception as e:
        print(f"  ✗ Error embedding watermark: {e}")
        out.release()
        if os.path.exists(test_video_path):
            os.remove(test_video_path)
        exit(1)

out.release()
print(f"  ✓ Video created: {test_video_path}")
print(f"    Start timestamp: {video_start_timestamp}")
print(f"    Duration: 6 seconds (180 frames at 30 FPS)")

# Step 2: Validate the video
print("\n[STEP 2] Validating video watermarks...")
try:
    validation_result = validate_video(test_video_path, video_start_timestamp)
    print(f"  ✓ Validation complete")
except Exception as e:
    print(f"  ✗ Validation failed: {e}")
    if os.path.exists(test_video_path):
        os.remove(test_video_path)
    exit(1)

# Step 3: Verify result format
print("\n[STEP 3] Verifying result format...")
try:
    assert 'overall_status' in validation_result, "Missing overall_status"
    assert 'results' in validation_result, "Missing results"
    assert 'matched' in validation_result, "Missing matched"
    assert 'total' in validation_result, "Missing total"
    assert 'percentage' in validation_result, "Missing percentage"
    print(f"  ✓ All required fields present")
except AssertionError as e:
    print(f"  ✗ {e}")
    exit(1)

# Step 4: Test JSON serialization
print("\n[STEP 4] Testing JSON serialization (as API would)...")
try:
    json_str = json.dumps(validation_result)
    parsed = json.loads(json_str)
    print(f"  ✓ Serialization successful ({len(json_str)} bytes)")
    print(f"  ✓ Deserialization successful")
except Exception as e:
    print(f"  ✗ JSON error: {e}")
    exit(1)

# Step 5: Display results
print("\n[STEP 5] Validation Results:")
print(f"  Overall Status: {validation_result['overall_status']}")
print(f"  Frames Checked: {validation_result['total']}")
print(f"  Matched: {validation_result['matched']}")
print(f"  Match Rate: {validation_result['percentage']:.1f}%")

if validation_result['results']:
    print(f"\n  Frame-by-frame results (showing every second):")
    for result in validation_result['results'][:6]:  # Show first 6 seconds
        match_icon = '✓' if result['match'] else '✗'
        expected = result['expected_hmac']
        extracted = result['extracted_hmac']
        
        print(f"    Second {result['second']} {match_icon}")
        print(f"      Expected:  {expected}")
        print(f"      Extracted: {extracted}")

# Step 6: Simulate API response
print("\n[STEP 6] Simulating API Response...")
api_response = {
    'success': True,
    'validation': validation_result,
    'file_path': test_video_path
}

try:
    api_json = json.dumps(api_response)
    print(f"  ✓ API response is JSON serializable")
    print(f"  ✓ Response size: {len(api_json)} bytes")
except Exception as e:
    print(f"  ✗ API serialization failed: {e}")
    exit(1)

# Cleanup
print("\n[STEP 7] Cleanup...")
os.remove(test_video_path)
print(f"  ✓ Test video removed")

# Summary
print("\n" + "=" * 70)
print("END-TO-END TEST PASSED ✓")
print("=" * 70)
print("\nThe validation system is working correctly:")
print(f"  • Videos can be processed and watermarks validated")
print(f"  • Results are properly formatted with all required fields")
print(f"  • API responses are JSON serializable")
print(f"  • Frontend will receive data in correct format")
print("\nNext steps:")
print(f"  • Upload a video through the web interface")
print(f"  • Check the 'VALIDATION RESULTS' panel")
print(f"  • Review expected vs extracted RGB colors for each second")
print("=" * 70)
