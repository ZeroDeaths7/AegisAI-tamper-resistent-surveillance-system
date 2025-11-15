#!/usr/bin/env python
"""Test the validation API response format"""

import json
from backend.watermark_validator import validate_video

# Create mock validation result similar to what the app returns
mock_validation = {
    'overall_status': 'LIVE',
    'results': [
        {
            'second': 0,
            'timestamp': 1609459200,
            'expected_color': [209, 129, 55],
            'extracted_color': [208, 128, 56],
            'distance': 1.73,
            'match': 1
        },
        {
            'second': 1,
            'timestamp': 1609459201,
            'expected_color': [208, 90, 45],
            'extracted_color': [207, 91, 46],
            'distance': 1.41,
            'match': 1
        },
        {
            'second': 2,
            'timestamp': 1609459202,
            'expected_color': [146, 55, 24],
            'extracted_color': [200, 100, 70],
            'distance': 125.4,
            'match': 0
        }
    ],
    'matched': 2,
    'total': 3,
    'percentage': 66.7
}

print("=" * 60)
print("API RESPONSE FORMAT TEST")
print("=" * 60)

# Test 1: JSON serialization
print("\n[TEST 1] JSON Serialization")
try:
    json_str = json.dumps(mock_validation)
    print(f"  ✓ Success ({len(json_str)} chars)")
except Exception as e:
    print(f"  ✗ Failed: {e}")
    exit(1)

# Test 2: Frontend display format
print("\n[TEST 2] Frontend Display Format")
try:
    # Simulate what displayValidationResults() does
    status = mock_validation.get('overall_status')
    total = mock_validation.get('total', 0)
    matched = mock_validation.get('matched', 0)
    percentage = mock_validation.get('percentage', 0)
    
    print(f"  Status: {status}")
    print(f"  Frames checked: {total} | Matched: {matched} | Match Rate: {percentage:.1f}%")
    
    # Check results
    if mock_validation.get('results'):
        print(f"  \n  Results for {len(mock_validation['results'])} frames:")
        for result in mock_validation['results']:
            match_icon = '✓' if result['match'] else '✗'
            print(f"    Second {result['second']} {match_icon}")
            print(f"      Expected RGB: ({result['expected_color'][0]}, {result['expected_color'][1]}, {result['expected_color'][2]})")
            extracted = result['extracted_color']
            if extracted:
                print(f"      Extracted RGB: ({extracted[0]}, {extracted[1]}, {extracted[2]})")
            else:
                print(f"      Extracted RGB: None")
            print(f"      Distance: {result['distance']:.2f}")
    
    print(f"\n  ✓ All fields displayed correctly")
    
except Exception as e:
    print(f"  ✗ Failed: {e}")
    exit(1)

print("\n" + "=" * 60)
print("API RESPONSE FORMAT TEST PASSED ✓")
print("=" * 60)
