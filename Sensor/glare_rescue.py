import cv2
import numpy as np
import matplotlib.pyplot as plt

# --- NEW: MSR (Multi-Scale Retinex) in HSV SPACE ---

def apply_msr_hsv(frame, scales=[11, 81, 251]):
    """
    Applies Multi-Scale Retinex (MSR) to an image's V (Value) channel
    to preserve color integrity.
    """
    # 1. Convert to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    
    # --- NEW: DENOISING ---
    # Denoise the V (Value) channel BEFORE MSR
    # h=10 is the filter strength. Higher = stronger (and slower)
    v_denoised = cv2.fastNlMeansDenoising(v, None, h=10, templateWindowSize=7, searchWindowSize=21)

    # --- MSR on V-channel ---
    # Convert to log space (log(1 + V) to avoid log(0))
    log_v = np.log1p(v.astype(np.float32))
    
    msr_v = np.zeros_like(log_v)
    
    # Process each scale
    for scale in scales:
        # Create the "surround" (blur) image
        # Kernel size must be odd
        k_size = scale if scale % 2 == 1 else scale + 1
        blur = cv2.GaussianBlur(log_v, (k_size, k_size), 0)
        
        # Add the weighted log-difference to the msr_v
        msr_v += (log_v - blur)
    
    # Average the scales
    msr_v = msr_v / len(scales)
    
    # --- Post-processing ---
    # 1. Convert back from log space and normalize
    # This gives the "reflectance" (enhanced V channel)
    reflectance_v = np.expm1(msr_v)
    reflectance_v_normalized = np.zeros_like(reflectance_v, dtype=np.uint8)
    cv2.normalize(reflectance_v, reflectance_v_normalized, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    reflectance_v = reflectance_v_normalized

    # 2. Simple Contrast Stretch on the V channel
    # This often improves the MSR result significantly
    p_low, p_high = np.percentile(reflectance_v, (0.5, 99.5))
    if p_high > p_low:
        enhanced_v = np.clip((reflectance_v - p_low) * (255 / (p_high - p_low)), 0, 255).astype(np.uint8)
    else:
        enhanced_v = reflectance_v # Avoid division by zero
    
    # 3. Merge enhanced V with original H and S
    enhanced_hsv = cv2.merge([h, s, enhanced_v])
    
    # 4. Convert back to BGR
    final_frame = cv2.cvtColor(enhanced_hsv, cv2.COLOR_HSV2BGR)

    return final_frame

# --- Other Helper Functions ---

def apply_unsharp_mask(frame, amount=1.5, kernel_size=(5, 5), sigma=1.0):
    """Applies a simple unsharp mask to sharpen the image."""
    blurred = cv2.GaussianBlur(frame, kernel_size, sigma)
    sharpened = cv2.addWeighted(frame, 1.0 + amount, blurred, -amount, 0)
    return sharpened

def get_image_viability_stats(frame, dark_thresh=40, bright_thresh=250):
    """Analyzes a frame using the "Loss of Detail" metric."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    total_pixels = gray.shape[0] * gray.shape[1]
    
    dark_pixels = np.sum(hist[0:dark_thresh])
    bright_pixels = np.sum(hist[bright_thresh:256])
    mid_tone_pixels = np.sum(hist[dark_thresh:bright_thresh])

    dark_pct = (dark_pixels / total_pixels) * 100
    bright_pct = (bright_pixels / total_pixels) * 100
    mid_pct = (mid_tone_pixels / total_pixels) * 100
    
    # --- "LOSS OF DETAIL" METRIC ---
    threshold_dark_pct = 30.0  
    threshold_bright_pct = 1.0   
    threshold_mid_pct = 60.0   
    
    is_glare = (
        dark_pct > threshold_dark_pct and
        bright_pct > threshold_bright_pct and
        mid_pct < threshold_mid_pct
    )
    
    return is_glare, dark_pct, mid_pct, bright_pct, hist, gray

# --- Standalone Test Harness ---
if __name__ == "__main__":
    
    print("Starting glare rescue test...")
    print("...Press 'm' to toggle rescue mode: CLAHE vs MSR (HSV)")
    print("Press 'q' in the OpenCV window to quit.")

    # --- Setup ---
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open camera.")
        exit()
        
    clahe = cv2.createCLAHE(clipLimit=16.0, tileGridSize=(4, 4))
    
    # --- Rescue Mode State ---
    rescue_mode = 'CLAHE' # Start with CLAHE
    
    # --- Matplotlib Setup ---
    plt.ion() 
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8))
    fig.suptitle('Live Histogram Analysis', fontsize=16)

    ax1.set_title("Continuous Histogram (0-255)")
    x_continuous = np.arange(256)
    line_continuous, = ax1.plot(x_continuous, np.zeros(256), color='b')
    ax1.set_xlim(0, 255)
    ax1.axvline(x=40, color='r', linestyle='--') 
    ax1.axvline(x=250, color='r', linestyle='--')

    ax2.set_title("Bucket-wise Histogram (~10 Intensity Buckets)")
    nbins = 26
    x_bucketed = np.arange(nbins)
    rects_bucketed = ax2.bar(x_bucketed, np.zeros(nbins), width=1.0, color='g')
    ax2.set_xlim(0, nbins - 1)
    
    plt.tight_layout(rect=(0, 0.03, 1, 0.95))

    # --- Main Loop ---
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        is_glare, dark_pct, mid_pct, bright_pct, hist, gray = get_image_viability_stats(
            frame, dark_thresh=50, bright_thresh=252
        )
        
        # 2. --- ACTIVE DEFENSE LOGIC (with TOGGLE) ---
        if is_glare:
            if rescue_mode == 'CLAHE':
                # --- 1. CLAHE Rescue ---
                lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab_frame)
                l_clahe = clahe.apply(l)
                enhanced_lab_frame = cv2.merge((l_clahe, a, b))
                clahe_rescued_frame = cv2.cvtColor(enhanced_lab_frame, cv2.COLOR_LAB2BGR)
                
                # --- 2. Sharpening ---
                processed_frame = apply_unsharp_mask(clahe_rescued_frame, amount=1.0)
                
                # --- 3. NEW HACK: TAME HIGHLIGHTS ---
                # Find the original blown-out highlights
                gray_raw = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                ret, mask = cv2.threshold(gray_raw, 252, 255, cv2.THRESH_BINARY)
                # Set those pixels to a neutral gray
                processed_frame[mask > 0] = (150, 150, 150) 
                # --- END OF HACK ---

                status_text = "GLARE (RESCUE: CLAHE + HACK)"
                text_color = (0, 0, 255) # Red
            
            else: # rescue_mode == 'MSR'
                # --- NEW: MSR in HSV space ---
                processed_frame = apply_msr_hsv(frame)
                
                status_text = "GLARE (RESCUE: MSR)"
                text_color = (0, 165, 255) # Orange
        
        else:
            # No glare
            processed_frame = frame
            status_text = "Status: Normal"
            text_color = (0, 255, 0) # Green
        
        # 3. Add status text
        cv2.putText(processed_frame, status_text, 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.7, text_color, 2)
        
        # 4. Add the percentage stats
        h, w, _ = frame.shape
        stats_text_1 = f"Dark %: {dark_pct:.1f}"
        stats_text_2 = f"Mid %:  {mid_pct:.1f}"
        stats_text_3 = f"Bright %: {bright_pct:.1f}"
        
        cv2.putText(processed_frame, stats_text_1, (10, h - 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(processed_frame, stats_text_2, (10, h - 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(processed_frame, stats_text_3, (10, h - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 5. Calculate Bucketed Histogram
        hist_bucketed = cv2.calcHist([gray], [0], None, [nbins], [0, 256])

        # 6. Update Histogram Plots
        line_continuous.set_ydata(hist.ravel())
        ax1.set_ylim(0, np.max(hist[10:-10]) + 100) 

        for rect, h in zip(rects_bucketed, hist_bucketed.ravel()):
            rect.set_height(h)
        ax2.set_ylim(0, np.max(hist_bucketed[1:-1]) + 100) 

        fig.canvas.draw()
        fig.canvas.flush_events()
        
        # 7. Display BOTH Frames
        cv2.imshow("Aegis Rescued Feed (Press 'm' to toggle, 'q' to quit)", processed_frame)
        cv2.imshow("Raw Feed", frame)

        # --- Keypress Handler ---
        key = cv2.waitKey(1)
        if key == ord('q'):
            break
        if key == ord('m'):
            if rescue_mode == 'CLAHE':
                rescue_mode = 'MSR'
                print("Switched to MSR (HSV) Rescue Mode")
            else:
                rescue_mode = 'CLAHE'
                print("Switched to CLAHE + Unsharp Rescue Mode")

    # --- Cleanup ---
    cap.release()
    cv2.destroyAllWindows()
    plt.ioff()
    plt.close(fig)
    print("Test finished.")