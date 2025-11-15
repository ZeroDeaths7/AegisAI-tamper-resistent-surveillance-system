#!/usr/bin/env python
"""Test HMAC token generation matches dynamic_watermarker format"""

import time
from backend.watermark_validator import get_expected_hmac_token

print("=" * 60)
print("HMAC TOKEN FORMAT TEST")
print("=" * 60)

# Test with fixed timestamp
test_timestamp = 1609459200
expected_token = get_expected_hmac_token(test_timestamp)

print(f"\n[TEST 1] Token generation")
print(f"  Timestamp: {test_timestamp}")
print(f"  Generated Token: {expected_token}")
print(f"  Format: 4-digit string (0000-9999)")
assert len(expected_token) == 4, "Token should be 4 digits"
assert expected_token.isdigit(), "Token should be all digits"
print(f"  ✓ PASS - Token is 4-digit format")

# Test with current timestamp
current_token = get_expected_hmac_token(int(time.time()))
print(f"\n[TEST 2] Current timestamp token")
print(f"  Current Token: {current_token}")
print(f"  ✓ PASS")

# Test multiple timestamps
print(f"\n[TEST 3] Multiple timestamps")
for i in range(5):
    ts = int(time.time()) + i
    token = get_expected_hmac_token(ts)
    print(f"  Second +{i}: {token}")
    assert len(token) == 4 and token.isdigit(), f"Invalid token: {token}"
print(f"  ✓ PASS - All tokens are 4-digit format")

print("\n" + "=" * 60)
print("HMAC TOKEN FORMAT TEST PASSED ✓")
print("=" * 60)
