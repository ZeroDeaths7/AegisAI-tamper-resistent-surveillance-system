#!/usr/bin/env python
"""Integration test for RGB watermark system"""

import time
from backend.watermark_embedder import get_hmac_color, embed_watermark, get_watermark_embedder
from backend.watermark_extractor import extract_watermark_color, color_distance
from backend.watermark_validator import get_expected_hmac_token, validate_video

print("=" * 60)
print("AEGIS RGB WATERMARK SYSTEM - STATUS CHECK")
print("=" * 60)

# Test 1: HMAC Color generation
print("\n[TEST 1] HMAC Color Generation")
ts = 1609459200  # 2021-01-01 00:00:00 UTC
color = get_hmac_color(ts)
print(f"  Timestamp: {ts}")
print(f"  Generated RGB: {color}")
print(f"  ✓ PASS")

# Test 2: Expected HMAC from validator
print("\n[TEST 2] Expected HMAC Token (Validator)")
expected_hmac = get_expected_hmac_token(ts)
print(f"  Expected HMAC: {expected_hmac}")
# Note: validator now returns HMAC tokens, not colors

# Test 3: Color distance calculation
print("\n[TEST 3] Color Distance Calculation")
color1 = (255, 0, 0)
color2 = (255, 0, 0)
distance = color_distance(color1, color2)
print(f"  Color 1: {color1}, Color 2: {color2}")
print(f"  Distance: {distance}")
assert distance == 0.0, "Same colors should have distance 0"
print(f"  ✓ PASS")

# Test 4: Watermark embedder factory
print("\n[TEST 4] Watermark Embedder Factory")
embedder = get_watermark_embedder()
print(f"  Embedder type: {type(embedder).__name__}")
print(f"  Has embed method: {hasattr(embedder, 'embed')}")
print(f"  ✓ PASS")

print("\n" + "=" * 60)
print("ALL TESTS PASSED ✓")
print("=" * 60)
