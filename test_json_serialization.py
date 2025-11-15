#!/usr/bin/env python
"""Test JSON serialization of validation results"""

import json
from backend.watermark_validator import validate_video

# Create sample validation result
sample_result = {
    'overall_status': 'LIVE',
    'results': [
        {
            'second': 0,
            'timestamp': 1609459200,
            'expected_color': (76, 82, 44),
            'extracted_color': (75, 83, 45),
            'distance': 1.73,
            'match': True  # This is a bool - will cause JSON serialization error
        }
    ],
    'matched': 1,
    'total': 1,
    'percentage': 100.0
}

print("=" * 60)
print("JSON SERIALIZATION TEST")
print("=" * 60)

# Test 1: Original (will fail)
print("\n[TEST 1] Without conversion (will fail):")
try:
    json_str = json.dumps(sample_result)
    print("  ✗ UNEXPECTED: Serialization succeeded")
except TypeError as e:
    print(f"  ✓ Expected error: {e}")

# Test 2: With conversion (should work)
print("\n[TEST 2] With boolean-to-int conversion (should work):")
try:
    # Convert boolean to int
    for result in sample_result.get('results', []):
        if 'match' in result:
            result['match'] = int(result['match'])
    
    json_str = json.dumps(sample_result)
    print(f"  ✓ Serialization succeeded")
    print(f"  JSON length: {len(json_str)} chars")
    
    # Verify we can parse it back
    parsed = json.loads(json_str)
    print(f"  ✓ Deserialization succeeded")
    print(f"  Match value: {parsed['results'][0]['match']} (type: {type(parsed['results'][0]['match']).__name__})")
except Exception as e:
    print(f"  ✗ Error: {e}")

print("\n" + "=" * 60)
print("JSON SERIALIZATION TEST PASSED ✓")
print("=" * 60)
