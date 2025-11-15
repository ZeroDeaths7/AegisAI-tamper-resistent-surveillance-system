import cv2
import numpy as np
import matplotlib.pyplot as plt

def get_glare_stats(frame, threshold_pct=10.0):
    """
    Analyzes a single frame to detect glare and returns stats.
    
    Glare is defined as a high percentage of pixels
    being "pure white" (pixel value 255).
    
    Args:
        frame: The BGR video frame from OpenCV.
        threshold_pct: The percentage of white pixels
                       that triggers a glare detection.
                       
    Returns:
        (is_glare, percentage): A tuple containing:
            - is_glare (Boolean): True if glare is detected.
            - percentage (float): The actual percentage of white pixels.
    """
    # 1. Convert to grayscale for analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 2. Calculate total number of pixels
    total_pixels = gray.shape[0] * gray.shape[1]
    
    # 3. Find "pure white" pixels (value 255)
    white_pixels = np.sum((gray == 255) | (gray == 254) | (gray == 253) | (gray == 252))  # Consider top 4 values as glare
    
    # 4. Calculate the percentage
    percentage = (white_pixels / total_pixels) * 100
    
    # 5. Return stats
    is_glare = percentage > threshold_pct
    return is_glare, percentage

# --- Standalone Test Harness ---
# This block runs only when you execute `python glare_detection.py`
if __name__ == "__main__":
    
    print("Starting glare detection test...")
    print("Point a flashlight at the camera to test.")
    print("Watch the histograms spike, especially at bin 255.")
    print("Press 'q' in the OpenCV window to quit.")

    # --- Setup ---
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open camera.")
        exit()
        
    # We will test with a 25% threshold
    GLARE_THRESHOLD_PERCENTAGE = 25.0 
    
    # --- Matplotlib Setup for Live Graphs ---
    plt.ion() # Turn on interactive mode
    
    # Create a figure with two subplots, one on top of the other
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8))
    fig.suptitle('Live Histogram Analysis', fontsize=16)

    # Setup for Plot 1: Continuous (256 bins)
    ax1.set_title("Continuous Histogram (0-255)")
    ax1.set_xlabel("Pixel Value (0-255)")
    ax1.set_ylabel("Frequency")
    x_continuous = np.arange(256)
    line_continuous, = ax1.plot(x_continuous, np.zeros(256), color='b') # Plot empty data
    ax1.set_xlim(0, 255) # Fix x-axis

    # Setup for Plot 2: Buckets (26 bins of ~10 intensity)
    ax2.set_title("Bucket-wise Histogram (~10 Intensity Buckets)")
    ax2.set_xlabel("Intensity Bucket (0-25)")
    ax2.set_ylabel("Frequency")
    nbins = 26 # 256 / 10 = 25.6, so we use 26 bins
    x_bucketed = np.arange(nbins)
    rects_bucketed = ax2.bar(x_bucketed, np.zeros(nbins), width=1.0, color='g') # Plot empty data
    ax2.set_xlim(0, nbins - 1)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to make room for suptitle

    # --- Main Loop ---
    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Can't receive frame.")
            break
            
        # 1. Run the glare detection logic
        is_glare, white_pixel_percentage = get_glare_stats(frame, GLARE_THRESHOLD_PERCENTAGE)
            
        # 2. Set status text based on glare
        if is_glare:
            status_text = "GLARE DETECTED"
            text_color = (0, 0, 255) # Red
        else:
            status_text = "Status: Normal"
            text_color = (0, 255, 0) # Green
        
        cv2.putText(frame, status_text, 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.7, text_color, 2)
        
        # --- NEW ---
        # 3. Add the percentage text to the corner
        percent_text = f"White Pixel %: {white_pixel_percentage:.2f}%"
        cv2.putText(frame, percent_text, 
                    (10, frame.shape[0] - 10), # (10, height - 10) for bottom-left
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.6, (0, 0, 0), 2) # Black color
        
        # 4. Calculate Histograms (Requires grayscale)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist_continuous = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_bucketed = cv2.calcHist([gray], [0], None, [nbins], [0, 256])

        # 5. Update Histogram Plots
        line_continuous.set_ydata(hist_continuous.ravel())
        ax1.set_ylim(0, np.max(hist_continuous[10:]) + 100) # Auto-scale Y

        for rect, h in zip(rects_bucketed, hist_bucketed.ravel()):
            rect.set_height(h)
        ax2.set_ylim(0, np.max(hist_bucketed[1:]) + 100) # Auto-scale Y

        fig.canvas.draw()
        fig.canvas.flush_events()
        
        # 6. Display the OpenCV Frame
        cv2.imshow("Aegis Glare Test (Press 'q' to quit)", frame)

        if cv2.waitKey(1) == ord('q'):
            break

    # --- Cleanup ---
    cap.release()
    cv2.destroyAllWindows()
    plt.ioff()
    plt.close(fig)
    print("Test finished.")