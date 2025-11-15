#!/usr/bin/env python
"""Test video validation JSON serialization"""

import json
import cv2
import numpy as np
import time
import os
from backend.watermark_embedder import get_watermark_embedder
from backend.watermark_validator import validate_video

print("=" * 60)
print("VIDEO VALIDATION JSON SERIALIZATION TEST")
print("=" * 60)

# Step 1: Create a simple test video with watermarks
print("\n[STEP 1] Creating test video with watermarks...")
test_video_path = "test_video_with_watermark.mp4"

# Create a simple 3-second video (90 frames at 30 FPS)
fps = 30
width, height = 640, 480
fourcc = cv2.VideoWriter.fourcc(*'mp4v')
out = cv2.VideoWriter(test_video_path, fourcc, fps, (width, height))

# Get watermark embedder
embedder = get_watermark_embedder()

# Record video start time
video_start_timestamp = int(time.time())

for frame_num in range(90):  # 3 seconds of video
    # Create a solid color frame
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (200, 200, 200)  # Light gray background
    
    # Calculate timestamp for this frame (assuming 30 FPS)
    frame_timestamp = video_start_timestamp + (frame_num / fps)
    
    # Embed watermark
    frame_with_watermark = embedder.embed(frame)
    
    # Write frame
    out.write(frame_with_watermark)

out.release()
print(f"  ✓ Test video created: {test_video_path} ({video_start_timestamp})")

# Step 2: Validate the video
print("\n[STEP 2] Validating video watermarks...")
validation_result = validate_video(test_video_path, video_start_timestamp)
print(f"  ✓ Validation complete")

# Step 3: Test JSON serialization
print("\n[STEP 3] Testing JSON serialization...")
try:
    json_str = json.dumps(validation_result)
    print(f"  ✓ JSON serialization succeeded ({len(json_str)} chars)")
    
    # Verify we can parse it back
    parsed = json.loads(json_str)
    print(f"  ✓ JSON deserialization succeeded")
    
    # Verify structure
    assert parsed['overall_status'] in ['LIVE', 'NOT_LIVE', 'ERROR'], "Invalid status"
    assert isinstance(parsed['matched'], int), "matched should be int"
    assert isinstance(parsed['total'], int), "total should be int"
    assert isinstance(parsed['percentage'], float), "percentage should be float"
    assert isinstance(parsed['results'], list), "results should be list"
    
    if parsed['results']:
        first_result = parsed['results'][0]
        assert isinstance(first_result['expected_color'], list), "expected_color should be list"
        assert isinstance(first_result['extracted_color'], list) or first_result['extracted_color'] is None, "extracted_color should be list or None"
        assert isinstance(first_result['match'], int), "match should be int (0 or 1)"
        assert isinstance(first_result['distance'], (int, float)) or first_result['distance'] is None, "distance should be number or None"
    
    print(f"  ✓ All JSON fields have correct types")
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    raise

# Step 4: Display results
print("\n[STEP 4] Validation Results:")
print(f"  Overall Status: {validation_result['overall_status']}")
print(f"  Matched Frames: {validation_result['matched']}/{validation_result['total']}")
print(f"  Match Percentage: {validation_result['percentage']:.1f}%")
if validation_result['results']:
    print(f"\n  First Frame Result:")
    r = validation_result['results'][0]
    print(f"    Second: {r['second']}")
    print(f"    Expected Color: {r['expected_color']}")
    print(f"    Extracted Color: {r['extracted_color']}")
    print(f"    Distance: {r['distance']}")
    print(f"    Match: {bool(r['match'])}")

# Cleanup
os.remove(test_video_path)
print(f"\n  ✓ Test video removed")

print("\n" + "=" * 60)
print("JSON SERIALIZATION TEST PASSED ✓")
print("=" * 60)
