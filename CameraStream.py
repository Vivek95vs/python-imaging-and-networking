import cv2
import numpy as np
import os
from datetime import datetime
import sys
import xml.etree.ElementTree as ET

# ==============================
# Stream URL
# ==============================
stream_url = "http://192.168.12.221:8080/?action=stream"

# ==============================
# Save path
# ==============================
save_path = "captured_images"
os.makedirs(save_path, exist_ok=True)

# ==============================
# Camera calibration file path
# ==============================
calibration_file = r"D:\HDR\camera_calibration.xml"


# ==============================
# Alternative method to load calibration using OpenCV FileStorage
# ==============================
def load_calibration_opencv(xml_file):
    """Load calibration using OpenCV FileStorage"""
    try:
        # Check if file exists
        if not os.path.exists(xml_file):
            print(f"File not found: {xml_file}")
            return None, None

        # Try different flags
        fs = cv2.FileStorage(xml_file, cv2.FILE_STORAGE_READ)

        if not fs.isOpened():
            print("Failed to open file with OpenCV FileStorage")
            return None, None

        # Try to get camera matrix
        camera_matrix = None
        for name in ["camera_matrix", "CameraMatrix", "K", "cameraMatrix", "intrinsic"]:
            node = fs.getNode(name)
            if node is not None and not node.empty():
                camera_matrix = node.mat()
                print(f"Found camera matrix: {name}")
                break

        # Try to get distortion coefficients
        dist_coeffs = None
        for name in ["distortion_coefficients", "DistortionCoefficients", "D", "distCoeffs", "distortion"]:
            node = fs.getNode(name)
            if node is not None and not node.empty():
                dist_coeffs = node.mat()
                print(f"Found distortion coefficients: {name}")
                break

        fs.release()
        return camera_matrix, dist_coeffs

    except Exception as e:
        print(f"OpenCV method failed: {e}")
        return None, None


# ==============================
# Alternative method using XML parsing
# ==============================
def load_calibration_xml_parser(xml_file):
    """Load calibration using XML parser (more robust)"""
    try:
        # Check if file exists
        if not os.path.exists(xml_file):
            print(f"File not found: {xml_file}")
            return None, None

        # Parse XML file
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Find camera matrix
        camera_matrix = None
        dist_coeffs = None

        # Look for camera matrix in various possible locations
        for matrix_name in ["camera_matrix", "CameraMatrix", "K", "cameraMatrix"]:
            elem = root.find(f".//{matrix_name}")
            if elem is not None:
                # Find data element
                data_elem = elem.find("data")
                if data_elem is not None:
                    data_text = data_elem.text.strip()
                    data_values = [float(x) for x in data_text.split()]
                    if len(data_values) == 9:
                        camera_matrix = np.array(data_values, dtype=np.float64).reshape(3, 3)
                        print(f"Found camera matrix: {matrix_name}")
                        break

        # Look for distortion coefficients
        for dist_name in ["distortion_coefficients", "DistortionCoefficients", "D", "distCoeffs"]:
            elem = root.find(f".//{dist_name}")
            if elem is not None:
                data_elem = elem.find("data")
                if data_elem is not None:
                    data_text = data_elem.text.strip()
                    data_values = [float(x) for x in data_text.split()]
                    dist_coeffs = np.array(data_values, dtype=np.float64).reshape(1, -1)
                    print(f"Found distortion coefficients: {dist_name}")
                    break

        return camera_matrix, dist_coeffs

    except Exception as e:
        print(f"XML parser method failed: {e}")
        return None, None


# ==============================
# Manual hardcoded values (fallback)
# ==============================
def get_fallback_calibration():
    """Return hardcoded calibration values as fallback"""
    print("\nUsing fallback hardcoded calibration values")
    camera_matrix = np.array([
        [595.2207, 0, 828.5167],
        [0, 593.1516, 571.7868],
        [0, 0, 1]
    ], dtype=np.float64)

    dist_coeffs = np.array([
        [-0.2414565, 0.0596008, -0.00100905, 0.00262168, -0.00631019]
    ], dtype=np.float64)

    return camera_matrix, dist_coeffs


# ==============================
# Main calibration loader
# ==============================
def load_calibration(xml_file):
    """Try multiple methods to load calibration"""

    print(f"Attempting to load calibration from: {xml_file}")

    # Method 1: Try OpenCV FileStorage
    camera_matrix, dist_coeffs = load_calibration_opencv(xml_file)

    # Method 2: If failed, try XML parser
    if camera_matrix is None or dist_coeffs is None:
        print("\nTrying alternativeparsingmethod...")
        camera_matrix, dist_coeffs = load_calibration_xml_parser(xml_file)

    # Method 3: If still failed, use hardcoded fallback
    if camera_matrix is None or dist_coeffs is None:
        print("\nWARNING: Could not read XML file. Using hardcoded values.")
        camera_matrix, dist_coeffs = get_fallback_calibration()

    # Validate loaded data
    if camera_matrix is not None and dist_coeffs is not None:
        print("\n == = Calibration Parameters Loaded Successfully == =")
        print(f"Camera Matrix shape: {camera_matrix.shape}")
        print(f"Camera Matrix:\n{camera_matrix}")
        print(f"Distortion Coefficients shape: {dist_coeffs.shape}")
        print(f"Distortion Coefficients:\n{dist_coeffs}")
        print("==================================================\n")
        return camera_matrix, dist_coeffs
    else:
        print("ERROR: Failed to load calibration parameters")
        return None, None


# ==============================
# Create a simple calibration XML file if needed
# ==============================
def create_sample_xml(output_file):
    """Create a sample XML calibration file"""
    try:
        root = ET.Element("opencv_storage")

        # Camera matrix
        cam_matrix = ET.SubElement(root, "camera_matrix")
        cam_matrix.set("type_id", "opencv-matrix")

        rows = ET.SubElement(cam_matrix, "rows")
        rows.text = "3"
        cols = ET.SubElement(cam_matrix, "cols")
        cols.text = "3"
        dt = ET.SubElement(cam_matrix, "dt")
        dt.text = "d"
        data = ET.SubElement(cam_matrix, "data")
        data.text = "595.2207 0. 828.5167 0. 593.1516 571.7868 0. 0. 1."

        # Distortion coefficients
        dist_coeffs = ET.SubElement(root, "distortion_coefficients")
        dist_coeffs.set("type_id", "opencv-matrix")

        rows = ET.SubElement(dist_coeffs, "rows")
        rows.text = "1"
        cols = ET.SubElement(dist_coeffs, "cols")
        cols.text = "5"
        dt = ET.SubElement(dist_coeffs, "dt")
        dt.text = "d"
        data = ET.SubElement(dist_coeffs, "data")
        data.text = "-0.2414565 0.0596008 -0.00100905 0.00262168 -0.00631019"

        # Write to file
        tree = ET.ElementTree(root)
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        print(f"Sample XML file created at: {output_file}")
        return True
    except Exception as e:
        print(f"Failed to create sample XML: {e}")
        return False


# ==============================
# Main execution
# ==============================

# Check if calibration file exists, if not create a sample
if not os.path.exists(calibration_file):
    print(f"Calibration file not found at: {calibration_file}")
    print("Creating a sample calibration file...")
    create_sample_xml(calibration_file)

# Load calibration data
camera_matrix, dist_coeffs = load_calibration(calibration_file)

if camera_matrix is None or dist_coeffs is None:
    print("ERROR: Failed to load calibration parameters. Exiting...")
    sys.exit(1)

# ==============================
# Open stream
# ==============================
cap = cv2.VideoCapture(stream_url)

if not cap.isOpened():
    print("Error: Cannot open stream")
    sys.exit()

# Read first frame to get size
ret, frame = cap.read()
if not ret:
    print("Error: Cannot read stream")
    sys.exit()

h, w = frame.shape[:2]

# ==============================
# Precompute undistortion maps (FAST)
# ==============================
new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
    camera_matrix, dist_coeffs, (w, h), 1, (w, h)
)

map1, map2 = cv2.initUndistortRectifyMap(
    camera_matrix,
    dist_coeffs,
    None,
    new_camera_matrix,
    (w, h),
    cv2.CV_16SC2
)

# ==============================
# Global frame for capture
# ==============================
current_frame = None

# Button coordinates
BTN_X1, BTN_Y1 = 10, 10
BTN_X2, BTN_Y2 = 130, 45


# ==============================
# Mouse callback
# ==============================
def capture_image(event, x, y, flags, param):
    global current_frame

    if event == cv2.EVENT_LBUTTONDOWN:
        if BTN_X1 <= x <= BTN_X2 and BTN_Y1 <= y <= BTN_Y2:
            if current_frame is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(save_path, f"{timestamp}.jpg")
                cv2.imwrite(filename, current_frame)
                print(f"Saved: {filename}")


# ==============================
# Window setup
# ==============================
cv2.namedWindow("Camera (Undistorted)", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Camera (Undistorted)", 640, 480)
cv2.setMouseCallback("Camera (Undistorted)", capture_image)

print("Click CAPTURE button to save image")
print("Press 'q' or ESC to exit")
print(f"Using calibration from: {calibration_file}")

# ==============================
# Main loop
# ==============================
while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break

    # ==========================
    # Undistort frame (FAST)
    # ==========================
    undistorted = cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR)

    # Crop valid region if ROI is valid
    x, y, w_roi, h_roi = roi
    if w_roi > 0 and h_roi > 0:
        undistorted = undistorted[y:y + h_roi, x:x + w_roi]

    # Save frame for capture
    current_frame = undistorted.copy()

    # Display resize
    display_frame = cv2.resize(undistorted, (640, 480))

    # Draw button
    cv2.rectangle(display_frame, (BTN_X1, BTN_Y1), (BTN_X2, BTN_Y2), (0, 255, 0), -1)
    cv2.putText(display_frame, "CAPTURE", (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    # Add calibration info text
    cv2.putText(display_frame, "Calibration: Loaded from XML", (10, 470),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    # Show window
    cv2.imshow("Camera (Undistorted)", display_frame)

    # Exit keys
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27:
        print("Exiting...")
        break

# ==============================
# Cleanup
# ==============================
cap.release()
cv2.destroyAllWindows()
sys.exit()