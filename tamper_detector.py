import cv2
import numpy as np

def check_blur(gray_frame, threshold=100.0):
    """
    Checks if a grayscale frame is blurry using the Laplacian variance method.
    
    Args:
        gray_frame (numpy.ndarray): The input grayscale image.
        threshold (float): Variance threshold. Below this is blurry.

    Returns:
        bool: True if the image is blurry, False otherwise.
    """
    variance = cv2.Laplacian(gray_frame, cv2.CV_64F).var()
    return variance < threshold, variance

def check_shake(gray_frame, prev_gray_frame, threshold=5.0):
    """
    Checks for camera shake using Dense Optical Flow.
    
    Args:
        gray_frame (numpy.ndarray): The current grayscale frame.
        prev_gray_frame (numpy.ndarray): The previous grayscale frame.
        threshold (float): Average motion magnitude. Above this is shake.

    Returns:
        bool: True if shake is detected, False otherwise.
        float: The average motion magnitude.
    """
    # Pre-allocate flow array
    flow = np.zeros((gray_frame.shape[0], gray_frame.shape[1], 2), dtype=np.float32)
    
    # Calculate dense optical flow
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray_frame, 
        gray_frame, 
        flow, 
        0.5,  # pyr_scale
        3,    # levels
        15,   # winsize
        3,    # iterations
        5,    # poly_n
        1.2,  # poly_sigma
        0     # flags
    )
    
    # Calculate the magnitude (speed) of motion vectors
    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    
    # Convert to NumPy array and get the average magnitude across the entire frame
    magnitude_np = cv2.cvtColor(magnitude.astype(np.uint8), cv2.COLOR_GRAY2BGR) if len(magnitude.shape) == 2 else magnitude
    avg_magnitude = float(magnitude.mean())
    
    # If avg magnitude is high, it means the whole camera is moving (shake)
    return avg_magnitude > threshold, avg_magnitude

def check_glare(frame, threshold_pct=10.0):
    """
    Analyzes a frame to detect glare.
    
    Glare is defined as a high percentage of pixels being "pure white".
    
    Args:
        frame (numpy.ndarray): The BGR video frame from OpenCV.
        threshold_pct (float): The percentage of white pixels that triggers glare detection.

    Returns:
        tuple: (is_glare, percentage, histogram)
            - is_glare (bool): True if glare is detected.
            - percentage (float): The actual percentage of white pixels.
            - histogram (numpy.ndarray): Histogram data for visualization.
    """
    # Convert to grayscale for analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Calculate total number of pixels
    total_pixels = gray.shape[0] * gray.shape[1]
    
    # Find "pure white" pixels (values 250-255)
    white_pixels = np.sum((gray >= 250))
    
    # Calculate the percentage
    percentage = (white_pixels / total_pixels) * 100
    
    # Calculate histogram for visualization (26 buckets of ~10 intensity each)
    histogram = cv2.calcHist([gray], [0], None, [26], [0, 256])
    histogram = histogram.flatten().tolist()  # Convert to list for JSON serialization
    
    # Return stats
    is_glare = percentage > threshold_pct
    return is_glare, percentage, histogram

def fix_blur_unsharp_mask(frame, kernel_size=5, sigma=1.0, strength=1.5):
    """
    Fix blur using Unsharp Masking technique.
    Enhances edges and makes blurry images appear sharper in real-time.
    
    Args:
        frame (numpy.ndarray): Input BGR frame.
        kernel_size (int): Gaussian blur kernel size (must be odd, default 5).
        sigma (float): Standard deviation for Gaussian blur (default 1.0).
        strength (float): How much sharpening to apply. 
                         1.0 = no effect, >1.0 = sharpen (default 1.5).
    
    Returns:
        numpy.ndarray: Sharpened BGR frame with same dimensions as input.
    """
    # Ensure kernel size is odd
    if kernel_size % 2 == 0:
        kernel_size += 1
    
    # Create blurred version (low-pass filter)
    blurred = cv2.GaussianBlur(frame, (kernel_size, kernel_size), sigma)
    
    # Unsharp mask formula: output = original + (original - blurred) * strength
    # This amplifies the high-frequency details (edges)
    sharpened = cv2.addWeighted(frame, 1.0 + strength, blurred, -strength, 0)
    
    # Clip values to valid range [0, 255] and convert to uint8
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    
    return sharpened