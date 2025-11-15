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