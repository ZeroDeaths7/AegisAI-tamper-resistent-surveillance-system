import hmac
import hashlib
import time
import random
from datetime import datetime

# --- CONFIGURATION (MUST MATCH LIVE SERVER SETTINGS) ---
SERVER_SECRET_KEY = b"YourUnbreakableWatermarkSecretKey12345" 
TOKEN_CHANGE_INTERVAL_SECONDS = 1 
# ---

# --- 1. VALIDATOR'S CRYPTOGRAPHIC TOKEN LOGIC ---

def calculate_expected_hmac_token(timestamp_seconds):
    """
    The Validator's deterministic function to predict the Token at any given time,
    using the HMAC-SHA256 algorithm and the shared secret key.
    """
    # 1. Prepare the message (time)
    message = str(timestamp_seconds).encode('utf-8')
    
    # 2. Compute the HMAC hash
    hmac_digest = hmac.new(
        key=SERVER_SECRET_KEY, 
        msg=message, 
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # 3. TRUNCATE and Convert to a small integer (0000-9999)
    last_4_hex = hmac_digest[-4:]
    token_int = int(last_4_hex, 16)
    final_token = token_int % 10000
    
    return f"{final_token:04d}"

# --- 2. SIMULATED ATTACK & VALIDATION ---

def simulate_hmac_attack_and_validate():
    print("-------------------------------------------------------")
    print("--- 🧪 HMAC-TST LOOP DETECTION TEST STARTING ---")
    print("-------------------------------------------------------")
    
    # Establish the initial time when the thief starts recording
    real_start_time = int(time.time())
    
    # 1. GENERATE THE REAL STREAM LOG
    # We run the real stream long enough to capture the loop segment and the subsequent 
    # expected tokens after the loop point.
    REAL_LOG_DURATION = 15
    real_stream_log = []
    
    print(f"\n[SERVER] Generating {REAL_LOG_DURATION} seconds of non-sequential TST sequence...")
    for i in range(REAL_LOG_DURATION):
        current_time = real_start_time + i
        token = calculate_expected_hmac_token(current_time)
        real_stream_log.append((current_time, token))
        print(f" Real Time: {i:02d}s | Token: {token}")

    # 2. SIMULATE THE THIEF'S RECORDING
    # The thief records 5 seconds (5 tokens) from the stream (Index 5 to 10)
    RECORD_START_INDEX = 5
    RECORD_END_INDEX = 10
    
    # The actual tokens captured by the thief
    thief_recorded_segment = [log[1] for log in real_stream_log[RECORD_START_INDEX:RECORD_END_INDEX]]
    
    print(f"\n[THIEF] Thief recorded segment (5 tokens): {thief_recorded_segment}")
    
    # 3. SIMULATE THE THIEF'S LOOPING ATTACK
    # The thief loops this 5-token segment three times.
    THIEF_LOOP_COUNT = 3 
    thief_attack_sequence = thief_recorded_segment * THIEF_LOOP_COUNT
    
    print(f"[THIEF] Looping 5-token segment 3 times: {thief_attack_sequence}")
    
    # --- 4. VALIDATOR ANALYSIS ---
    
    # The Validator starts monitoring immediately after the recorded segment ends.
    validation_start_time = real_start_time + RECORD_END_INDEX 
    
    print(f"\n[VALIDATOR] Starting comparison after Real Time {RECORD_END_INDEX}s...")
    
    mismatch_found = False
    
    # Loop through the thief's looped sequence and compare against what the Validator expects.
    for i, observed_token in enumerate(thief_attack_sequence):
        # Time the Validator expects this token to be shown
        expected_time = validation_start_time + i
        
        # Validator calculates the TRUE token for that expected time
        expected_token = calculate_expected_hmac_token(expected_time)
        
        comparison_time = expected_time - real_start_time
        
        # Check for Mismatch (The loop will instantly fail because the token is non-sequential)
        if observed_token != expected_token:
            mismatch_found = True
            print("-------------------------------------------------------")
            print(f"🚨 **FAKE FEED DETECTED** at Time: {comparison_time:02d}s")
            print(f"   Observed Token (Thief): {observed_token}")
            print(f"   Expected Token (Real):  {expected_token}")
            print("   Reason: The token sequence failed the non-sequential HMAC calculation.")
            print("-------------------------------------------------------")
            break
            
    if not mismatch_found:
        print("Test failed: No decisive mismatch found (check secret key and time).")
    else:
        print("\n✅ **TEST PASSED: HMAC-TST LOGIC VALIDATED.**")


# --- EXECUTION ---
simulate_hmac_attack_and_validate()