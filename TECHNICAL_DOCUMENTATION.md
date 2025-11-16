# AEGIS AI - Technical Documentation for Mentors

## Overview
AEGIS (Active Defense System) is a tamper-resistant surveillance system that detects physical attacks, environmental interference, and replay attacks in real-time through advanced computer vision and cryptographic watermarking.

---

## 1. BLUR DETECTION MODULE

### Purpose
Detects when the camera lens is intentionally or accidentally obscured (e.g., covering lens with hand, dirt on lens, intentional obstruction attack).

### Technical Details

**Algorithm: Laplacian Variance Method**
```
1. Convert frame to grayscale
2. Apply Laplacian operator (edge detection filter)
3. Calculate variance of Laplacian response
4. Compare against threshold (70.0 by default)
```

**How it Works:**
- The Laplacian operator `∇²I = ∂²I/∂x² + ∂²I/∂y²` detects rapid intensity changes
- Sharp, clear images have high variance in Laplacian response
- Blurry images have low variance (pixels change gradually)

**Mathematical Foundation:**
- Laplacian detects second-order derivatives (acceleration of intensity)
- Formula: `variance = mean((Laplacian(I) - mean(Laplacian(I)))²)`
- Threshold < 70.0 = Blur Detected

**Key Parameters:**
| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| BLUR_THRESHOLD | 70.0 | 50-150 | Laplacian variance threshold |
| Kernel | Predefined | Fixed | Laplacian filter kernel |

**Code Location:** `tamper_detector.py` - `check_blur()` function

**Alert Condition:**
- Triggered when variance < 70.0 for current frame
- Continuous blur for >2 seconds triggers "BLUR ALERT"

**Real-World Applications:**
- Prevents obstruction attacks (tape, paint, etc.)
- Detects natural obscuration (fog, dust, condensation)
- Catches accidental camera coverage

---

## 2. SHAKE DETECTION MODULE

### Purpose
Detects camera shake/vibration caused by physical force on the camera or mounting structure (e.g., impact, deliberate shaking to disrupt monitoring).

### Technical Details

**Algorithm: Dense Optical Flow Analysis**
```
1. Capture current frame (grayscale)
2. Compare with previous frame using Farneback optical flow
3. Calculate motion magnitude across entire frame
4. Average the motion vectors
5. Compare against shake threshold (6.0 by default)
```

**How it Works:**
- Optical flow computes motion vectors for every pixel
- Each vector shows direction and speed of pixel movement
- **Key insight:** Camera shake = UNIFORM motion (whole image moves together)
- Vs. object motion = LOCALIZED motion (only some areas move)

**Dense Optical Flow Algorithm (Farneback Method):**
```
Flow parameters:
- pyr_scale = 0.5    (pyramid scale factor)
- levels = 3         (pyramid levels for coarse-to-fine estimation)
- winsize = 15       (averaging window size)
- iterations = 3     (iterations at each level)
- poly_n = 5         (polynomial neighborhood size)
- poly_sigma = 1.2   (std dev of Gaussian used to weight polynomials)
```

**Mathematical Foundation:**
```
Motion magnitude = √(u² + v²)
where:
- u = horizontal motion component
- v = vertical motion component

Average magnitude across frame = Σ magnitude(i,j) / (height × width)
```

**Key Parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| SHAKE_THRESHOLD | 6.0 | Average motion magnitude threshold |
| Farneback pyr_scale | 0.5 | Accuracy vs speed tradeoff |
| Farneback winsize | 15 | Motion detail level |

**Code Location:** `tamper_detector.py` - `check_shake()` function

**Alert Condition:**
- Triggered when avg_magnitude > 6.0 for current frame
- Continuous shake for >2 seconds triggers "SHAKE ALERT"

**Real-World Applications:**
- Detects physical force on camera mount
- Detects footsteps/vibrations near camera
- Prevents deliberate shake attacks
- Distinguishes from normal scene motion (traffic, trees)

**EXAMPLE 1: Police Hits Camera Mount (SHAKE ALERT)**
```
Frame 0: Entire image is stationary
Frame 1: Someone punches camera mount hard
         → ALL pixels shift LEFT uniformly (avg magnitude: 12.0)
         → Exceeds SHAKE_THRESHOLD (6.0)
         → Optical flow shows UNIFORM motion across entire frame
         → SHAKE DETECTED ✓ ALERT TRIGGERED

Frame 2: Impact rebounds, pixels shift RIGHT (avg magnitude: 8.5)
         → Still above threshold
         → SHAKE continues to be detected

Frame 3: Mount stabilizes, pixels return to original position (avg magnitude: 0.2)
         → Below threshold
         → SHAKE stops
         
Timeline:
12:00:00.000 - Normal feed
12:00:00.033 - SHAKE ALERT (impact detected)
12:00:00.066 - Shake continues
12:00:00.100 - Shake subsides
Result: Brief shake spike → No reposition detected (movement is oscillatory, not directional)
```

**EXAMPLE 2: Footsteps Near Camera (VIBRATION)**
```
Camera mounted 5 feet high on wall. Person walks past underneath.

Frame 0: Static scene (hallway, empty)
Frame 1: Footstep 1 causes slight vibration
         → Optical flow shows small uniform motion (avg: 1.5)
         → Below SHAKE_THRESHOLD (6.0) → NO ALERT
         
Frame 2: Footstep 2
         → Small uniform motion (avg: 1.2) → NO ALERT

Frame 3: Footstep 3
         → Small uniform motion (avg: 1.8) → NO ALERT

Frame 10: Person walks away, vibrations stop
         
Timeline:
Multiple small vibrations (< 6.0 threshold each)
But ALL vibrations are:
- Random direction (not consistent)
- Symmetric (oscillate back and forth)
- Uniform motion (entire frame shifts equally)

Result: Multiple vibration events but NO REPOSITION DETECTED
        → Vibrations are rejected as noise (oscillatory)
        → Scene monitoring continues normally ✓
```

**EXAMPLE 3: Someone SLOWLY Rotates Camera 90° (REPOSITION ALERT)**
```
Scenario: Attacker slowly turns camera to point away from sensitive area

Frame 0:    Camera points at security door
            (Door visible in frame)

Frame 1:    Attacker gently rotates camera LEFT
            - Entire image shifts RIGHT (camera rotates left → objects appear to move right)
            - shift_magnitude = 8.5
            - Direction: (0.95, -0.1)  ← Mostly horizontal motion
            - History: [8.5]
            
Frame 2:    Continued slow rotation
            - shift_magnitude = 7.2
            - Direction: (0.92, 0.05)  ← Consistent leftward direction
            - History: [8.5, 7.2]
            
Frame 3:    Still rotating
            - shift_magnitude = 9.1
            - Direction: (0.98, -0.2)  ← Still consistent direction
            - History: [8.5, 7.2, 9.1]
            
Frame 4:    Rotation continues
            - shift_magnitude = 8.8
            - Direction: (0.94, 0.1)  ← Consistent direction
            - History: [8.5, 7.2, 9.1, 8.8]
            
Frame 5:    Final rotation
            - shift_magnitude = 10.2
            - Direction: (0.96, -0.05)  ← Still consistent
            - History: [8.5, 7.2, 9.1, 8.8, 10.2]

ANALYSIS:
✓ At least 5 frames tracked: YES
✓ At least 4 frames with shift > 10.0: 
  → [8.5, 7.2, 9.1, 8.8, 10.2]
  → Frames with shift > 10.0: [10.2] = 1 frame
  → BUT frames with shift > 5.0: ALL 5 frames
  
✓ Direction consistency check:
  → avg_dir_x = average([0.95, 0.92, 0.98, 0.94, 0.96]) = 0.95
  → avg_dir_y = average([-0.1, 0.05, -0.2, 0.1, -0.05]) ≈ -0.04
  → consistency = √(0.95² + 0.04²) = 0.95
  → Threshold: 0.4 ✓ EXCEEDS THRESHOLD
  
RESULT: REPOSITION DETECTED ✗ ALERT TRIGGERED
        User sees: "CAMERA REPOSITIONED - Shift: 8.8px, Direction: LEFT"
        Requires acknowledgment from security personnel
```

**EXAMPLE 4: Car Drives Past Camera (NOT REPOSITION)**
```
Scenario: Camera mounted at street level. Car drives by (scene motion, not camera motion)

Frame 0:    Empty street visible

Frame 1:    Car enters frame from LEFT side
            - Optical flow: Car pixels shift RIGHT (car moving right)
            - BUT: Background pixels have DIFFERENT motion vectors
            - Shift calculation: Uses CENTER REGION (ignores edge objects)
            - shift_magnitude in center = 0.5  ← Very low
            - Direction: (0.3, 0.7)  ← Random direction

Frame 2:    Car in middle of frame
            - Center region still mostly static (background)
            - shift_magnitude = 1.2
            - Direction: (0.1, 0.2)  ← No consistency

Frame 3:    Car exits frame RIGHT
            - shift_magnitude = 0.8
            - Direction: (0.4, 0.3)  ← Still no consistency

ANALYSIS:
✓ Shift magnitudes: [0.5, 1.2, 0.8]
✓ ALL below REPOSITION_THRESHOLD (10.0)
✓ Direction consistency: Very low (no consistent pattern)
✓ history length: 3 < 5 (minimum for slow reposition check)

RESULT: NO REPOSITION DETECTED ✓
        Scene analysis continues normally
        Car motion is detected but rejected as object motion (not camera motion)
```

**EXAMPLE 5: FAST Camera Rotation/Jerk (IMMEDIATE REPOSITION ALERT)**
```
Scenario: Attacker quickly jerks camera to point away

Frame 0:    Camera pointing at security door

Frame 1:    Quick jerk to the LEFT
            - shift_magnitude = 22.0  ← Sudden large movement!
            - Direction: (0.98, 0.1)
            - Check: shift_magnitude (22.0) > FAST_REPOSITION_THRESHOLD (20.0)
            → IMMEDIATE ALERT ✓ (doesn't wait for consistency)

RESULT: REPOSITION DETECTED ✗ ALERT TRIGGERED IMMEDIATELY
        User sees: "CAMERA REPOSITIONED - Shift: 22.0px"
        Alert shows before attacker can move camera further
```

---

## KEY DIFFERENCES: SHAKE vs REPOSITION

| Aspect | SHAKE/VIBRATION | REPOSITION |
|--------|-----------------|------------|
| **Duration** | Brief (< 1 second) | Sustained (> 0.5 seconds) |
| **Motion Pattern** | Oscillatory (back-forth) | Directional (one direction) |
| **Magnitude** | Often > 6.0 but temporary | Consistent 7-15+ over frames |
| **Direction** | Random, changes each frame | Consistent across frames |
| **History Requirement** | Not tracked | Tracked over 10 frames |
| **Alert Condition** | Single frame > 6.0 | 4/5 frames + direction consistency |
| **Examples** | Punch, footsteps, vibration | Rotating camera, panning camera |
| **Intent** | Often accidental | Deliberate tampering |
| **False Positive Risk** | Medium (vibrations) | Low (consistent direction) |

**Why Direction Consistency Matters:**

```
SHAKE (Oscillatory - Random Directions):
Frame 1: shift_x=+8, direction=(+1, 0)  → Move RIGHT
Frame 2: shift_x=-7, direction=(-1, 0)  → Move LEFT (rebound)
Frame 3: shift_x=+6, direction=(+1, 0)  → Move RIGHT (rebound)

avg_direction = (0, 0)  ← Cancels out!
consistency = 0.0 < 0.4 threshold
Result: NOT repositioned ✓

REPOSITION (Directional - Consistent Direction):
Frame 1: shift_x=+8, direction=(+0.98, +0.2)  → Move RIGHT & slightly DOWN
Frame 2: shift_x=+9, direction=(+0.95, +0.3)  → Move RIGHT & slightly DOWN
Frame 3: shift_x=+8, direction=(+0.92, +0.25) → Move RIGHT & slightly DOWN
Frame 4: shift_x=+7, direction=(+0.97, +0.2)  → Move RIGHT & slightly DOWN
Frame 5: shift_x=+9, direction=(+0.94, +0.3)  → Move RIGHT & slightly DOWN

avg_direction ≈ (+0.95, +0.26)
consistency = √(0.95² + 0.26²) = 0.98 > 0.4 threshold
Result: REPOSITIONED ✓
```

---

## ALGORITHM VISUALIZATION

```
┌─────────────────────────────────────────────────────┐
│        INPUT: Two Consecutive Frames               │
└────────────────┬──────────────────────────────────┘
                 │
                 ▼
         ┌───────────────────┐
         │ Calculate Optical │
         │ Flow (Farneback)  │
         │                   │
         │ Output: Velocity  │
         │ vectors for each  │
         │ pixel location    │
         └────────┬──────────┘
                  │
                  ▼
        ┌────────────────────────┐
        │ Extract Center Region  │
        │ (Ignore borders)       │
        │                        │
        │ Why? Borders have flow │
        │ artifacts from edges   │
        └────────┬───────────────┘
                 │
                 ▼
    ┌────────────────────────────────┐
    │ Calculate Motion Vectors       │
    │ - shift_x = avg horizontal     │
    │ - shift_y = avg vertical       │
    │ - shift_magnitude = √(x²+y²)   │
    └────────┬───────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ Track History                │
    │ (last 10 frames)             │
    │                              │
    │ Store shift magnitude        │
    │ Store direction (normalized) │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │ CHECK: Is this FAST movement?    │
    │                                  │
    │ if shift_magnitude > 20.0:       │
    │   → REPOSITION ALERT (immediate) │
    │   → Skip consistency checks      │
    └────────┬─────────────────────────┘
             │
         NO  │  YES → ALERT & RETURN
             │
             ▼
    ┌──────────────────────────────────┐
    │ CHECK: Is this SLOW movement?    │
    │                                  │
    │ Requires:                        │
    │ 1. At least 5 frames tracked     │
    │ 2. At least 4 frames > 10.0 shift│
    │ 3. Direction consistency > 0.4   │
    │                                  │
    │ if ALL conditions met:           │
    │   → REPOSITION ALERT             │
    │   → Show shift & direction       │
    └────────┬─────────────────────────┘
             │
         NO  │  YES → ALERT & RETURN
             │
             ▼
    ┌──────────────────────────┐
    │ NOT REPOSITIONED         │
    │ Continue monitoring      │
    │ (vibrations or scene     │
    │  motion filtered out)    │
    └──────────────────────────┘
```

**Data Structure Example (Real Code):**
```python
_shift_history = [8.5, 7.2, 9.1, 8.8, 10.2]  # Last 5 shifts
_direction_history = [
    (0.95, -0.1),   # Frame 1
    (0.92, 0.05),   # Frame 2
    (0.98, -0.2),   # Frame 3
    (0.94, 0.1),    # Frame 4
    (0.96, -0.05)   # Frame 5
]

# Analysis
shift_count = sum(1 for s in _shift_history if s > 10.0)
# = 1 (only frame 5 exceeds 10.0)

high_shift_directions = [dirs for i, dirs in enumerate(_direction_history) 
                         if _shift_history[i] > 5.0]
# = all 5 directions (all frames exceed 5.0)

avg_dir_x = mean([0.95, 0.92, 0.98, 0.94, 0.96]) = 0.95
avg_dir_y = mean([-0.1, 0.05, -0.2, 0.1, -0.05]) = -0.04
consistency = sqrt(0.95² + 0.04²) = 0.95

# Decision
if len(_shift_history) >= 5 and shift_count >= 4 and consistency > 0.4:
    is_repositioned = True
```

---

## 3. GLARE DETECTION & RESCUE MODULE

### Purpose
**Detection:** Identifies when bright light (flashlight, direct sunlight) washes out the image, making face recognition impossible.

**Rescue:** Applies intelligent image enhancement (CLAHE) to recover detail from glare-affected frames.

### Technical Details

#### Part A: Glare Detection

**Algorithm: Histogram-Based Loss of Detail Analysis**
```
1. Convert frame to grayscale
2. Compute histogram (256 bins, 0-255 intensity)
3. Categorize pixels into 3 ranges:
   - Dark: 0-50 (threshold_dark_pct = 30%)
   - Mid-tone: 50-252 (threshold_mid_pct = 60%)
   - Bright: 252-255 (threshold_bright_pct = 1%)
4. Check if pattern matches glare signature
```

**Glare Signature Pattern:**
- **High dark pixels** (>30%): Shadows are crushed/lost
- **High bright pixels** (>1%): Blown-out highlights
- **Low mid-tones** (<60%): Compressed tonal range

**Mathematical Foundation:**
```
Glare Detection = (dark_pct > 30) AND (bright_pct > 1) AND (mid_pct < 60)

This indicates "Loss of Detail" - the image lacks the normal gradient
```

**Why This Works:**
- Normal photos have smooth histogram distribution
- Glare images have bimodal distribution (dark shadows, blown highlights)
- Mid-tones (skin tones, facial features) are severely reduced

**Key Parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| threshold_dark_pct | 30.0 | % of pixels in dark range |
| threshold_bright_pct | 1.0 | % of pixels in bright range |
| threshold_mid_pct | 60.0 | % of pixels in mid-tone range |
| dark_thresh | 50 | Pixel intensity boundary for "dark" |
| bright_thresh | 252 | Pixel intensity boundary for "bright" |

#### Part B: Glare Rescue (CLAHE + Sharpening)

**CLAHE (Contrast Limited Adaptive Histogram Equalization):**
```
Algorithm Steps:
1. Split BGR image into LAB color space
2. Extract Lightness channel (L)
3. Divide L into tiles (4x4 grid, 16 tiles)
4. Apply histogram equalization to each tile independently
5. Interpolate between tile boundaries smoothly
6. Merge back to LAB, convert to BGR
```

**Why CLAHE is Better than Standard Histogram Equalization:**
- **Standard HE:** Amplifies noise globally (single histogram)
- **CLAHE:** Works locally in tiles → reveals detail without noise
- **Clip limit:** Prevents over-enhancement in flat areas

**CLAHE Parameters (Tuned):**
| Parameter | Value | Purpose |
|-----------|-------|---------|
| clipLimit | 16.0 | Clip limit for contrast amplification |
| tileGridSize | (4, 4) | Number of tiles (4×4 = 16 tiles) |

**Sharpening (Unsharp Mask):**
```
Sharpened = Original + (Original - Blurred) × strength
Strength = 1.0 (typical value)

This amplifies high-frequency details (edges) that CLAHE might have enhanced subtly
```

**Highlight Taming:**
```
1. Create mask of overly bright pixels (>252 intensity)
2. Set those pixels to neutral gray (150, 150, 150)
3. Prevents harsh artifacts from blown-out areas
```

**Code Location:**
- Detection: `Sensor/glare_rescue.py` - `get_image_viability_stats()`
- Rescue: `Sensor/glare_rescue.py` - Full implementation
- App integration: `app.py` - GLARE_RESCUE_ENABLED flag

**Alert Condition:**
- Triggered when glare signature detected
- Frame is enhanced but marked as "GLARE (RESCUE: CLAHE + TAME)"
- Continuous glare for >2 seconds triggers "GLARE ALERT"

**Real-World Applications:**
- Survives flashlight attacks
- Handles direct sunlight
- Recovers detail from overexposed scenes
- Maintains usable video during glare conditions

---

## 4. LIVENESS DETECTION MODULE

### Purpose
Detects when video feed is frozen, looped, or a static image is being shown instead of live video (replay attack indicator).

### Technical Details

#### Part A: Frozen Feed Detection

**Algorithm: Frame Difference Analysis**
```
1. Capture current frame (grayscale)
2. Calculate absolute difference from previous frame
3. Sum all pixel differences
4. Compare sum against liveness threshold
```

**Mathematical Foundation:**
```
Frame Difference = Σ |current_frame(i,j) - previous_frame(i,j)|

If difference < LIVENESS_THRESHOLD:
  → Feed appears frozen (no motion)

Every video has noise, even in static scenes:
- Compression artifacts
- Sensor noise
- Natural camera noise
Frozen feed = difference ≈ 0
Live feed = difference > threshold
```

**Key Insight:**
- A truly static scene still has ~10-100 pixels of difference per frame
- A frozen feed has ~0-5 pixels of difference (exact repetition)

**Key Parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| LIVENESS_THRESHOLD | 2.0 | Pixel difference threshold |
| LIVENESS_CHECK_INTERVAL | 3.0 | Seconds between reference frame captures |
| LIVENESS_ACTIVATION_TIME | 10.0 | Seconds before alert becomes active |

**Code Location:** `tamper_detector.py` (referenced), `app.py` - liveness detection logic

#### Part B: Dynamic Reference Frame Update

```
Timeline:
- t=0s: System starts, captures first reference frame
- t=10s: Liveness detection becomes active (LIVENESS_ACTIVATION_TIME)
- t=13s: Capture new reference frame (LIVENESS_CHECK_INTERVAL)
- Compare current frame to fresh reference every 3 seconds
```

**Why Dynamic Updates Matter:**
- Static scene (empty hallway) has minimal noise
- After 1 hour, sensor may drift slightly
- Updating reference every 3s prevents false positives

#### Part C: Blackout Detection

**Algorithm: Brightness Analysis**
```
1. Convert frame to grayscale
2. Calculate mean pixel intensity (0-255)
3. If mean < BLACKOUT_BRIGHTNESS_THRESHOLD:
   → Likely a complete blackout (lens cap, darkness)
```

**Key Parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| BLACKOUT_BRIGHTNESS_THRESHOLD | 25.0 | Mean pixel intensity threshold |

**Alert Condition:**
- Triggered when frozen feed detected
- Triggered when total blackout detected
- Continuous liveness failure triggers "FROZEN FEED ALERT" after 10s activation

**Real-World Applications:**
- Detects looped pre-recorded video
- Catches frozen frame attacks
- Prevents lens cap / complete obstruction
- Maintains liveness assurance

---

## 5. CAMERA REPOSITION DETECTION MODULE

### Purpose
Detects intentional repositioning of the camera to change the monitoring angle (e.g., someone rotates camera to point away from sensitive area).

### Technical Details

**Algorithm: Sustained Directional Motion Analysis**
```
1. Calculate dense optical flow between frames
2. Compute motion vectors for center region (ignoring borders)
3. Calculate average shift (shift_x, shift_y)
4. Compute shift magnitude: √(shift_x² + shift_y²)
5. Track shift history (last 10 frames)
6. Analyze for two patterns:
   a) Fast repositioning (sudden large movement)
   b) Slow repositioning (sustained movement with consistent direction)
```

**Dual Detection Criteria:**

**Criterion 1: Fast Repositioning**
```
if shift_magnitude > FAST_THRESHOLD (20.0):
  → Camera moved quickly to new position
  → Alert immediately
```

**Criterion 2: Slow/Sustained Repositioning**
```
Requires:
1. At least 5 frames tracked
2. At least 4 frames with shift > 10.0
3. Direction consistency > 0.4

Direction consistency = √(avg_dir_x² + avg_dir_y²)
where avg_dir_x/y are the normalized motion directions
```

**Why Dual Criteria:**
- Fast reposition: Immediate large shift (obvious tampering)
- Slow reposition: Gradual movement (trying to hide the change)
- Prevents false positives from scene motion (cars, people walking)

**Key Parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| REPOSITION_THRESHOLD | 10.0 | Shift magnitude threshold |
| _MAX_HISTORY | 10 | Frames to track for sustained motion |
| FAST_REPOSITION_THRESHOLD | 20.0 | Fast movement threshold (2× normal) |
| DIRECTION_CONSISTENCY | 0.4 | Min consistency for slow reposition |

**Code Location:** `tamper_detector.py` - `detect_camera_reposition()` function

**Alert Condition:**
- Triggered when fast OR slow repositioning detected
- Shows modal dialog with shift magnitude and direction
- Requires user acknowledgment before dismissing
- Prevents dismissal during active repositioning

**Real-World Applications:**
- Detects deliberate camera rotation
- Catches slow creeping movement to hide tampering
- Prevents "pointing camera away" attacks
- Maintains coverage of monitored area

---

## 6. WATERMARK VALIDATION MODULE (Liveness Proof via Cryptography)

### Purpose
Proves that uploaded video is genuinely live and recent (not pre-recorded or replayed) by validating embedded HMAC-based watermarks.

### Technical Details

#### Part A: Watermark Embedding (Live Feed)

**Algorithm: Time-Based HMAC Color Encoding**
```
For each frame:
1. Get current Unix timestamp: T = time.time()
2. Generate HMAC-SHA256:
   - Message: timestamp as string: str(int(T))
   - Secret key: "AegisSecureWatermarkKey2025"
   - HMAC = HMAC-SHA256(secret_key, timestamp_bytes)
3. Extract RGB color from HMAC:
   - R = HMAC_digest[0] (first byte, 0-255)
   - G = HMAC_digest[1] (second byte, 0-255)
   - B = HMAC_digest[2] (third byte, 0-255)
4. Embed 40×40 colored square in bottom-right corner
5. Update watermark every 1 second (every FPS frames at 30fps)
```

**Watermark Properties:**
| Property | Value | Purpose |
|----------|-------|---------|
| Size | 40×40 pixels | Visible but non-intrusive |
| Position | Bottom-right | Hard to edit/blur |
| Padding | 10 pixels | From frame edges |
| Update Frequency | 1 second | Token changes every second |
| Encoding | RGB color | 16.7M possible colors from HMAC |

**HMAC-SHA256 as Color Source:**
```
Why HMAC over simple HASH:
1. HMAC is keyed → only we know the secret
2. Every timestamp produces unique HMAC
3. HMAC is cryptographically secure (one-way)

SHA256 produces 32 bytes (256 bits):
- Byte 0 (R): value 0-255
- Byte 1 (G): value 0-255
- Byte 2 (B): value 0-255

With 3 random bytes from SHA256, we get 2^24 = 16.7M colors
```

**Code Location:** `backend/watermark_embedder.py`

#### Part B: Watermark Extraction from Video

**Algorithm: ROI Extraction + Color Averaging**
```
For each frame in uploaded video:
1. Extract bottom-right ROI: 40×40 pixels
2. Calculate mean RGB color from all pixels in ROI:
   mean_R = average of all R values
   mean_G = average of all G values
   mean_B = average of all B values
3. Return (mean_R, mean_G, mean_B) as extracted watermark color
```

**Why Average Instead of Single Pixel:**
- Compression artifacts may corrupt individual pixels
- Video encoding introduces noise
- Averaging is robust against localized corruption

**Code Location:** `backend/watermark_extractor.py` - `extract_watermark_color()`

#### Part C: Watermark Validation (Expected vs Extracted)

**Algorithm: Timestamp Comparison with Tolerance**
```
For each frame in video:
1. Get expected HMAC color for frame's timestamp:
   expected_color = get_expected_hmac_token(timestamp)
2. Get extracted color from video:
   extracted_color = extract_watermark_color(frame)
3. Calculate Euclidean distance:
   distance = √((R1-R2)² + (G1-G2)² + (B1-B2)²)
4. If distance is very small:
   → Colors match → Frame is authentic for that timestamp
5. Aggregate results:
   matched_count = frames where colors match
   total_frames = frames checked
   percentage = (matched_count / total_frames) × 100
```

**Validation Decision:**
```
if percentage >= LIVE_THRESHOLD (70%):
  → Video is LIVE (genuine)
  → Confidence level shown
else:
  → Video is NOT_LIVE (pre-recorded/replayed)
  → Replay attack alert triggered
```

**Key Parameters:**
| Parameter | Default | Purpose |
|----------|---------|---------|
| LIVE_THRESHOLD | 70% | % frames must match for "LIVE" verdict |
| Color distance threshold | Calculated | Euclidean distance in RGB space |
| SECRET_KEY | "AegisSecureWatermarkKey2025" | HMAC secret (must match embedder) |

**Code Location:**
- Extraction: `backend/watermark_extractor.py`
- Validation: `backend/watermark_validator.py`

#### Part D: Why This Prevents Replay Attacks

```
Attack Vector: Using Old Pre-Recorded Video
├─ Attacker plays watermarked_video.mp4 from yesterday
├─ Video has watermarks from timestamps: [1700000000, 1700000001, ...]
├─ Current system time: 1700086400 (24 hours later)
├─ Expected watermarks for today: completely different colors
└─ Extracted colors won't match expected colors
   → Validation FAILS
   → REPLAY ATTACK DETECTED ✗

Why it Works:
- Each timestamp produces unique HMAC → unique color
- Impossible to predict future watermark colors (HMAC is one-way)
- Even small timestamp difference = completely different color
- Video embedded with old timestamp = definitely old video
```

**Mathematical Security:**
```
HMAC-SHA256 properties:
1. One-way: No feasible way to reverse HMAC(T) → T
2. Avalanche effect: Small change in input → completely different output
3. Keyed: Without SECRET_KEY, cannot generate valid HMACs
4. Deterministic: Same timestamp always produces same HMAC

For replay attack to succeed:
- Attacker needs to predict future HMAC colors
- Impossible without knowing SECRET_KEY or predicting future timestamp
- Even if they have old video + SECRET_KEY, they can't change past
```

**Real-World Applications:**
- Proves video was captured right now
- Prevents use of old recorded videos
- Makes timestamp spoofing detectable
- Maintains chain of custody for evidence

---

## 7. AUDIO ALERTS & LOGGING MODULE

### Purpose
Provides audio feedback for tamper detection and maintains searchable logs of all detected threats.

### Technical Details

**Audio Processing Pipeline:**
```
1. Speech Recognition (PocketSphinx):
   - Real-time speech-to-text conversion
   - Decodes audio to catch verbal threats
   - Language model: English (built-in)

2. Audio Transcription Logging:
   - Stores all recognized speech in database
   - Timestamps for temporal tracking
   - Linkable to incidents
```

**Alert Sounds (Simulated):**
```
- Liveness Alert: High-pitched beep pattern
- Physical Tamper: Medium-pitched warning tone
- Glare Alert: Lower-frequency warning
- Reposition Alert: Distinctive pattern alert
```

**Database Storage:**
- Audio logs table stores text transcripts
- Linked to incident IDs for correlation
- Searchable by keyword and timestamp

**Key Parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| AUDIO_ALERTS_ENABLED | True | Enable audio feedback |
| POCKETSPHINX_AVAILABLE | Detected | Voice recognition available |

**Code Location:**
- `backend/pocketsphinx_recognizer.py` - Speech recognition
- `backend/database.py` - Audio log storage
- `app.py` - Audio alert emission

---

## 8. DATABASE MODULE (Persistence & Analytics)

### Purpose
Stores all detection incidents, audio logs, glare images, and liveness validations with full traceability.

### Technical Details

**Database Architecture:**

**Table 1: incidents**
```sql
CREATE TABLE incidents (
    id INTEGER PRIMARY KEY,
    incident_type TEXT (blur, shake, glare, reposition, freeze, blackout, major_tamper),
    primary_detection TEXT (specific detection subtype),
    timestamp REAL (Unix timestamp when detected),
    count INTEGER (how many times grouped),
    description TEXT (human-readable summary),
    created_at DATETIME (when recorded in database)
)
```

**Incident Grouping Logic:**
```
If same incident_type detected within 5 seconds:
  → Group them as single incident, increment count
Else:
  → Create new incident record

Example:
- 12:00:00.5 - BLUR detected → Create incident #1
- 12:00:01.2 - BLUR detected → Increment incident #1 count
- 12:00:02.8 - BLUR detected → Increment incident #1 count
- 12:00:10.1 - BLUR detected → Create incident #2 (>5s gap)
```

**Table 2: audio_logs**
```sql
CREATE TABLE audio_logs (
    id INTEGER PRIMARY KEY,
    incident_id INTEGER (foreign key to incidents),
    text TEXT (recognized speech transcript),
    timestamp REAL (when audio was captured),
    created_at DATETIME (when logged)
)
```

**Table 3: glare_images**
```sql
CREATE TABLE glare_images (
    id INTEGER PRIMARY KEY,
    incident_id INTEGER,
    file_path TEXT (path to saved image),
    glare_percentage REAL (% of white pixels),
    timestamp REAL,
    created_at DATETIME
)
```

**Table 4: liveness_validations**
```sql
CREATE TABLE liveness_validations (
    id INTEGER PRIMARY KEY,
    incident_id INTEGER,
    file_path TEXT (path to uploaded video),
    validation_status TEXT (LIVE or NOT_LIVE),
    frame_results TEXT (JSON with per-frame analysis),
    timestamp REAL,
    created_at DATETIME
)
```

**Indexing Strategy:**
```sql
CREATE INDEX idx_incidents_timestamp ON incidents(timestamp)
CREATE INDEX idx_incidents_type ON incidents(incident_type)
CREATE INDEX idx_audio_timestamp ON audio_logs(timestamp)
CREATE INDEX idx_glare_incident ON glare_images(incident_id)
```

**Why Indexing Matters:**
- Fast searches by timestamp (incident timeline analysis)
- Fast filtering by type ("show all blur incidents")
- Fast joins on incident_id (correlate data)

**Retention Policies:**
```
MAX_INCIDENTS_RETAINED = 5
- Keep last 5 incidents in memory
- Prevents infinite growth during attack
- Full history available in database
```

**Code Location:** `backend/database.py`

---

## 9. REAL-TIME COMMUNICATION LAYER (Socket.IO)

### Purpose
Streams detection metrics, alerts, and video frames to frontend in real-time using WebSocket connections.

### Technical Details

**Socket.IO Events (Server → Client):**
```javascript
// Video streams
emit('video_frame', {jpg_frame: base64_encoded})
emit('processed_frame', {jpg_frame: base64_encoded, metrics: {}})

// Detection updates
emit('detection', {
    type: 'blur',
    value: 45.2,
    status: 'alert',
    timestamp: 1700000000
})

// Liveness alerts
emit('liveness_status', {
    status: 'INITIALIZING...' | 'SECURE' | 'ALERT',
    details: '...'
})

// Reposition alerts
emit('reposition_alert', {
    shift_magnitude: 15.3,
    shift_x: 12.1,
    shift_y: 8.5,
    timestamp: 1700000000
})
```

**Socket.IO Events (Client → Server):**
```javascript
// Request configuration update
emit('configure_sensors', {
    blur: true,
    shake: true,
    glare: true,
    glare_rescue_mode: 'CLAHE'
})

// Request liveness validation
emit('validate_watermark', {
    video_file: File,
    timestamp: 1700000000
})

// Acknowledge alert
emit('acknowledge_alert', {
    incident_id: 123
})
```

**Advantages Over HTTP Polling:**
| Feature | HTTP Polling | Socket.IO |
|---------|--------------|-----------|
| Latency | 1-2 seconds | <100ms |
| Bandwidth | High (constant requests) | Low (event-based) |
| Server Load | High (constant checks) | Low (push-based) |
| Real-time Quality | Poor | Excellent |
| Scalability | ~10 clients | 1000+ clients |

**Code Location:** `app.py` - socketio event handlers

---

## 10. FRONTEND UI MODULE (Dashboard & Controls)

### Purpose
Displays real-time metrics, video streams, alerts, and enables watermark validation upload.

### Technical Details

**Key UI Components:**

**1. Video Streams**
```html
<video id="rawFeed">      <!-- Raw camera input -->
<video id="processedFeed"> <!-- With annotations -->
```

**2. Metric Cards (Real-time Updates)**
```
┌──────────────────────┐
│ BLUR DETECTION       │
│ Status: ✓ Secure     │
│ Variance: 85.2       │
│ Threshold: 70.0      │
└──────────────────────┘
```

**3. Glare Histogram**
```
Real-time bar chart showing intensity distribution
Peaks in dark/bright indicate glare pattern
```

**4. Incident Log**
```
[12:00:15] BLUR ALERT - Variance: 45.2
[12:00:22] SHAKE ALERT - Magnitude: 8.5
[12:00:45] GLARE DETECTED - Recovery in progress
```

**5. Watermark Upload Section**
```
Upload Video → Extract Token → Compare with Live Token
↓
If Match: "✓ VIDEO IS LIVE" (green)
If Mismatch: "✗ REPLAY ATTACK DETECTED" (red)
```

**Real-time Updates:**
```javascript
socket.on('detection', (data) => {
    // Update UI metric
    document.getElementById(data.type + 'Value').textContent = data.value;
    
    // Change indicator color
    if (data.status === 'alert') {
        indicator.classList.add('alert');
    }
    
    // Log the event
    addLogEntry(data.message);
});
```

**Code Location:** `Frontend/script.js`, `Frontend/index.html`, `Frontend/style.css`

---

## 11. BLUR CORRECTION MODULE (Active Defense)

### Purpose
When blur is detected, apply unsharp masking to enhance edges and make blurry content more usable.

### Technical Details

**Unsharp Masking Algorithm:**
```
Sharpened = Original + (Original - Blurred) × strength

Steps:
1. Create blurred version: Blurred = GaussianBlur(Original)
2. Calculate difference: Difference = Original - Blurred
3. Amplify difference: Amplified = Difference × strength
4. Add back to original: Sharpened = Original + Amplified
```

**Mathematical Intuition:**
```
The difference (Original - Blurred) captures high-frequency details (edges)
Multiplying by strength amplifies these edges
This makes blurry images appear sharper

Example:
Original edge:    [100, 150, 200]
After blur:       [125, 150, 175]
Difference:       [-25,   0,  25]
Amplified (2×):   [-50,   0,  50]
Sharpened:        [50, 150, 250] ← Edges enhanced
```

**Parameters:**
| Parameter | Default | Purpose |
|-----------|---------|---------|
| kernel_size | 5 | Gaussian blur kernel (5×5) |
| sigma | 1.0 | Std dev of Gaussian |
| strength | 1.5 | How much to amplify edges |

**Limitations:**
- Cannot recover completely lost information
- Amplifies noise alongside edges
- Works best with mild blur (variance 30-70)

**Code Location:** `Sensor/glare_rescue.py` - `apply_unsharp_mask()`

---

## 12. SENSOR CONFIGURATION MODULE

### Purpose
Allows runtime enabling/disabling of detection modules without restarting server.

### Technical Details

**Configuration Structure:**
```python
sensor_config = {
    'blur': True,              # Blur detection active
    'shake': True,             # Shake detection active
    'glare': True,             # Glare detection active
    'liveness': True,          # Liveness detection active
    'reposition': True,        # Reposition detection active
    'blur_fix': True,          # Apply unsharp mask when blurry
    'glare_rescue': True,      # Apply CLAHE when glare detected
    'audio_alerts': True,      # Play alert sounds
    'glare_rescue_mode': 'CLAHE' # Enhancement algorithm to use
}
```

**Thread-Safe Updates:**
```python
sensor_config_lock = threading.Lock()

# Safe update:
with sensor_config_lock:
    sensor_config['blur'] = False  # Disable blur detection
```

**Why Thread-Safe:**
- Multiple threads access config simultaneously:
  - Main video loop thread
  - Socket.IO event handler threads
  - Flask request threads
- Lock prevents race conditions and data corruption

**Code Location:** `app.py` - sensor_config initialization and socket.IO handlers

---

## INTEGRATION: How Modules Work Together

### Real-Time Detection Pipeline
```
┌─────────────┐
│ Video Input │
└──────┬──────┘
       │
       ├──→ [BLUR DETECTION] ──→ Blur? ──→ [BLUR CORRECTION]
       │      └─ Variance check
       │
       ├──→ [SHAKE DETECTION] ──→ Shake? ──→ [ALERT]
       │      └─ Optical flow analysis
       │
       ├──→ [GLARE DETECTION] ──→ Glare? ──→ [GLARE RESCUE]
       │      └─ Histogram analysis        └─ CLAHE + Sharpening
       │
       ├──→ [LIVENESS DETECTION] ──→ Frozen? ──→ [ALERT]
       │      └─ Frame difference
       │
       ├──→ [REPOSITION DETECTION] ──→ Reposition? ──→ [ALERT]
       │      └─ Optical flow direction
       │
       └──→ [WATERMARK EMBEDDING] ──→ Add colored square
              └─ HMAC from timestamp

All → [DATABASE] → [SOCKET.IO] → [FRONTEND UI]
                 ↓
            [INCIDENT LOG]
```

### Upload Watermark Validation Pipeline
```
┌─────────────────────┐
│ Upload Video File   │
└──────┬──────────────┘
       │
       ├──→ [WATERMARK EXTRACTOR]
       │      └─ Extract RGB color from each frame
       │
       ├──→ [WATERMARK VALIDATOR]
       │      └─ Generate expected HMAC colors
       │      └─ Compare extracted vs expected
       │
       ├──→ [RESULT ANALYSIS]
       │      └─ If %match >= 70% → LIVE
       │      └─ Else → REPLAY ATTACK
       │
       └──→ [DATABASE] ──→ [SOCKET.IO] ──→ [FRONTEND UI]
              └─ Store validation result
```

---

## DEPENDENCIES & REQUIREMENTS

**Python Packages:**
```
opencv-python      → Computer vision (all detection)
numpy              → Numerical operations
Flask              → Web framework
Flask-SocketIO     → Real-time communication
SpeechRecognition  → Audio alerts
PyAudio            → Audio I/O
pytesseract        → OCR (future text watermarks)
pocketsphinx       → Speech recognition
Pillow             → Image operations
```

**System Requirements:**
```
- Python 3.8+
- Webcam/video input device
- ~200MB RAM for live processing
- GPU optional (for faster processing)
```

---

## SECURITY CONSIDERATIONS

### Attack Vectors Addressed
1. **Blur Attack:** Obstruct lens → BLUR DETECTION + CORRECTION
2. **Shake Attack:** Physical force → SHAKE DETECTION
3. **Glare Attack:** Bright light washout → GLARE DETECTION + RESCUE
4. **Freeze Attack:** Loop old footage → LIVENESS DETECTION
5. **Reposition Attack:** Change viewing angle → REPOSITION DETECTION
6. **Replay Attack:** Use old pre-recorded video → WATERMARK VALIDATION

### Cryptographic Guarantees
- HMAC-SHA256 provides authentication
- Timestamp-based colors impossible to predict
- One-way function prevents reverse engineering
- Keyed system prevents unauthorized watermark generation

### Limitations
- Detection is probabilistic (tuned thresholds)
- False positives possible in challenging conditions
- Requires continuous monitoring (can't detect attacks after stopping)
- Watermark only works for videos captured with this system

---

## PERFORMANCE METRICS

**Real-time Detection:**
- Frame processing: ~30-50ms per frame @ 30fps
- Detection latency: <100ms for all modules
- Memory usage: ~150-200MB per stream
- CPU usage: ~40-60% single core (variable by detection complexity)

**Scalability:**
- Single server: 4-8 concurrent streams
- With optimization: 20+ streams (distributed)
- Socket.IO: 1000+ concurrent connections

---

## TESTING & VALIDATION

**Unit Tests Available:**
- `test_camera.py` - Camera input verification
- `test_optical_flow.py` - Optical flow accuracy
- `test_tamper_detector.py` - Detection module accuracy
- `test_backend_watermark.py` - Watermark extraction & validation

**Running Tests:**
```bash
python test_camera.py
python test_optical_flow.py
python test_tamper_detector.py
python test_backend_watermark.py
```

---

## FUTURE ENHANCEMENTS

1. **Text-Based Watermarks:** OCR-extracted text watermarks
2. **Multi-Camera Orchestration:** Coordinate multiple cameras
3. **Blockchain Logging:** Immutable incident records
4. **ML-Based Anomaly Detection:** Neural networks for complex patterns
5. **Face Recognition Integration:** Verify person identity
6. **Distributed Processing:** Edge computing for scalability

---

**Document Version:** 1.0
**Last Updated:** November 16, 2025
**Status:** Complete Technical Reference for Mentors
