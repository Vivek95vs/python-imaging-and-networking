import cv2
import numpy as np
import glob
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom


def fisheye_calibration(image_folder, chessboard_size=(8, 5), square_size=28.0):
    """
    Perform fisheye camera calibration using chessboard images
    """

    # Prepare object points
    objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
    objp = objp * square_size

    # Arrays to store object points and image points
    objpoints = []
    imgpoints = []

    # Get all images
    image_paths = []
    for ext in ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']:
        image_paths.extend(glob.glob(os.path.join(image_folder, ext)))
    image_paths = list(set(image_paths))

    print(f"Found {len(image_paths)} unique images")

    successful_images = []
    image_size = None

    # Process each image
    for image_path in image_paths:
        img = cv2.imread(image_path)
        if img is None:
            continue

        if image_size is None:
            image_size = (img.shape[1], img.shape[0])

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Find chessboard corners
        ret, corners = cv2.findChessboardCorners(gray, chessboard_size, None,
                                                 cv2.CALIB_CB_ADAPTIVE_THRESH +
                                                 cv2.CALIB_CB_NORMALIZE_IMAGE)

        if ret:
            # Refine corners
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            objpoints.append(objp)
            imgpoints.append(corners2)
            successful_images.append(image_path)
            print(f"✓ {os.path.basename(image_path)}")
        else:
            print(f"✗ {os.path.basename(image_path)}")

    print(f"\nSuccessfully detected: {len(successful_images)}/{len(image_paths)} images")

    if len(objpoints) < 10:
        print(f"⚠️ Only {len(objpoints)} images. Need at least 10-15 for good calibration.")
        if len(objpoints) < 3:
            print("❌ Insufficient images!")
            return None

    # Perform standard calibration
    print("\nPerforming camera calibration...")

    try:
        ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            objpoints, imgpoints, image_size, None, None
        )

        print(f"✅ Calibration successful!")
        print(f"Reprojection error: {ret:.6f}")

        # Print distortion coefficients
        k1, k2, p1, p2, k3 = dist_coeffs[0]
        print(f"\nDistortion coefficients:")
        print(f"k1 = {k1:.6f}")
        print(f"k2 = {k2:.6f}")
        print(f"p1 = {p1:.6f}")
        print(f"p2 = {p2:.6f}")
        print(f"k3 = {k3:.6f}")

        return {
            'camera_matrix': camera_matrix,
            'dist_coeffs': dist_coeffs,
            'rms': ret,
            'image_size': image_size,
            'successful_images': len(successful_images)
        }

    except Exception as e:
        print(f"Calibration failed: {str(e)}")
        return None


def save_calibration_xml(calibration_data, output_path="camera_calibration.xml"):
    """
    Save camera matrix and distortion coefficients to XML file
    """

    root = ET.Element("opencv_storage")

    # Camera Matrix
    camera_matrix_elem = ET.SubElement(root, "camera_matrix", type_id="opencv-matrix")
    rows_elem = ET.SubElement(camera_matrix_elem, "rows")
    rows_elem.text = "3"
    cols_elem = ET.SubElement(camera_matrix_elem, "cols")
    cols_elem.text = "3"
    dt_elem = ET.SubElement(camera_matrix_elem, "dt")
    dt_elem.text = "d"
    data_elem = ET.SubElement(camera_matrix_elem, "data")
    cm_data = calibration_data['camera_matrix'].flatten()
    data_elem.text = " ".join([f"{x:.12e}" for x in cm_data])

    # Distortion Coefficients
    dist_coeffs_elem = ET.SubElement(root, "distortion_coefficients", type_id="opencv-matrix")
    rows_elem = ET.SubElement(dist_coeffs_elem, "rows")
    rows_elem.text = "1"
    cols_elem = ET.SubElement(dist_coeffs_elem, "cols")
    cols_elem.text = "5"
    dt_elem = ET.SubElement(dist_coeffs_elem, "dt")
    dt_elem.text = "d"
    data_elem = ET.SubElement(dist_coeffs_elem, "data")
    dc_data = calibration_data['dist_coeffs'].flatten()
    data_elem.text = " ".join([f"{x:.12e}" for x in dc_data])

    # Write XML
    xml_str = ET.tostring(root, encoding='utf-8')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent="  ")
    pretty_xml = pretty_xml.replace('<?xml version="1.0" ?>', '')
    pretty_xml = pretty_xml.replace('<?xml version="1.0" encoding="utf-8"?>', '')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(pretty_xml)

    print(f"\n✅ Calibration saved to: {output_path}")


def correct_images_alpha0(calibration_data, image_folder):
    """
    Correct images using alpha=0 (cropped, no black borders)
    """
    # Get all images
    image_paths = []
    for ext in ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']:
        image_paths.extend(glob.glob(os.path.join(image_folder, ext)))
    image_paths = list(set(image_paths))

    # Create output directory
    output_dir = "corrected_images_alpha0"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"\n{'=' * 60}")
    print(f"CORRECTING IMAGES WITH ALPHA=0 (CROPPED)")
    print(f"{'=' * 60}")

    h, w = calibration_data['image_size'][1], calibration_data['image_size'][0]

    # Get new camera matrix with alpha=0 (crops image to remove black borders)
    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
        calibration_data['camera_matrix'],
        calibration_data['dist_coeffs'],
        (w, h),
        0,  # alpha=0 for cropping
        (w, h)
    )

    print(f"Original image size: {w} x {h}")
    if roi != (0, 0, 0, 0):
        x, y, w_roi, h_roi = roi
        print(f"Cropped image size: {w_roi} x {h_roi}")
        print(f"Crop region: x={x}, y={y}, width={w_roi}, height={h_roi}")

    # Create a sample comparison image
    sample_count = min(5, len(image_paths))
    print(f"\nProcessing {len(image_paths)} images...")

    for idx, image_path in enumerate(image_paths, 1):
        img = cv2.imread(image_path)
        if img is None:
            continue

        # Undistort image
        undistorted = cv2.undistort(
            img,
            calibration_data['camera_matrix'],
            calibration_data['dist_coeffs'],
            None,
            new_camera_matrix
        )

        # Crop the image to remove black borders (if roi is available)
        if roi != (0, 0, 0, 0):
            x, y, w_roi, h_roi = roi
            undistorted = undistorted[y:y + h_roi, x:x + w_roi]

        # Save corrected image
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        save_path = os.path.join(output_dir, f"{base_name}_corrected.jpg")
        cv2.imwrite(save_path, undistorted)

        # Create comparison for first few images
        if idx <= 5:
            # Resize for display
            img_resized = cv2.resize(img, (640, 480))
            corrected_resized = cv2.resize(undistorted, (640, 480))

            # Stack horizontally
            comparison = np.hstack([img_resized, corrected_resized])

            # Add labels
            cv2.putText(comparison, "ORIGINAL (FISHEYE)", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(comparison, "CORRECTED (ALPHA=0)", (650, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Save comparison
            comparison_path = os.path.join(output_dir, f"comparison_{idx}_{base_name}.jpg")
            cv2.imwrite(comparison_path, comparison)

            # Display
            cv2.imshow(f'Correction Result {idx}', comparison)
            cv2.waitKey(1000)  # Show each for 1 second

        print(f"[{idx}/{len(image_paths)}] ✓ Corrected: {base_name}")

    cv2.destroyAllWindows()

    print(f"\n✅ All corrected images saved to: {output_dir}/")
    print(f"✅ Comparison images saved for first 5 images")

    return output_dir


def print_calibration_values(calibration_data):
    """
    Print camera matrix and distortion coefficients in a clean format
    """
    print("\n" + "=" * 60)
    print("CAMERA MATRIX AND DISTORTION COEFFICIENTS")
    print("=" * 60)

    print("\nCamera Matrix (3x3):")
    print("-" * 40)
    print("[[{:>12.6f} {:>12.6f} {:>12.6f}]".format(
        calibration_data['camera_matrix'][0, 0],
        calibration_data['camera_matrix'][0, 1],
        calibration_data['camera_matrix'][0, 2]
    ))
    print(" [{:>12.6f} {:>12.6f} {:>12.6f}]".format(
        calibration_data['camera_matrix'][1, 0],
        calibration_data['camera_matrix'][1, 1],
        calibration_data['camera_matrix'][1, 2]
    ))
    print(" [{:>12.6f} {:>12.6f} {:>12.6f}]]".format(
        calibration_data['camera_matrix'][2, 0],
        calibration_data['camera_matrix'][2, 1],
        calibration_data['camera_matrix'][2, 2]
    ))

    print("\nDistortion Coefficients (k1, k2, p1, p2, k3):")
    print("-" * 40)
    k1, k2, p1, p2, k3 = calibration_data['dist_coeffs'][0]
    print(f"k1 = {k1:.12f}")
    print(f"k2 = {k2:.12f}")
    print(f"p1 = {p1:.12f}")
    print(f"p2 = {p2:.12f}")
    print(f"k3 = {k3:.12f}")

    # Also print as array format for easy copying
    print("\nPython array format (easy to copy):")
    print("-" * 40)
    print("camera_matrix = np.array([")
    print(
        f"    [{calibration_data['camera_matrix'][0, 0]:.12f}, {calibration_data['camera_matrix'][0, 1]:.12f}, {calibration_data['camera_matrix'][0, 2]:.12f}],")
    print(
        f"    [{calibration_data['camera_matrix'][1, 0]:.12f}, {calibration_data['camera_matrix'][1, 1]:.12f}, {calibration_data['camera_matrix'][1, 2]:.12f}],")
    print(
        f"    [{calibration_data['camera_matrix'][2, 0]:.12f}, {calibration_data['camera_matrix'][2, 1]:.12f}, {calibration_data['camera_matrix'][2, 2]:.12f}]")
    print("])")
    print("\ndist_coeffs = np.array([")
    print(f"    [{k1:.12f}, {k2:.12f}, {p1:.12f}, {p2:.12f}, {k3:.12f}]")
    print("])")


def main():
    # Configuration
    image_folder = r"D:\HDR\Capture"
    chessboard_size = (8, 5)  # INNER corners
    square_size = 28.0  # mm

    print("=" * 60)
    print("FISHEYE CAMERA CALIBRATION")
    print("=" * 60)
    print(f"Image folder: {image_folder}")
    print(f"Chessboard: {chessboard_size[0]}x{chessboard_size[1]} inner corners")
    print(f"Square size: {square_size} mm")
    print("=" * 60)

    if not os.path.exists(image_folder):
        print(f"❌ Folder not found: {image_folder}")
        return

    # Perform calibration
    calibration_data = fisheye_calibration(image_folder, chessboard_size, square_size)

    if calibration_data:
        # Print calibration values
        print_calibration_values(calibration_data)

        # Save to XML
        save_calibration_xml(calibration_data, "camera_calibration.xml")

        # Also save as text file
        with open("calibration_values.txt", "w") as f:
            f.write("Camera Matrix:\n")
            f.write(str(calibration_data['camera_matrix']))
            f.write("\n\nDistortion Coefficients:\n")
            f.write(str(calibration_data['dist_coeffs']))
            f.write(f"\n\nReprojection Error: {calibration_data['rms']:.6f}")

        print(f"\n✅ Calibration values saved to: calibration_values.txt")

        # Ask if user wants to correct images
        print("\n" + "=" * 60)
        correct_choice = input("Do you want to correct images with alpha=0? (y/n): ").strip().lower()

        if correct_choice == 'y':
            correct_images_alpha0(calibration_data, image_folder)

            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print("✅ Camera matrix and distortion coefficients saved to:")
            print("   - camera_calibration.xml")
            print("   - calibration_values.txt")
            print("\n✅ Corrected images (alpha=0) saved to:")
            print("   - corrected_images_alpha0/")
            print("\n✅ Comparison images saved for first 5 images")

    else:
        print("\n❌ Calibration failed!")


if __name__ == "__main__":
    main()