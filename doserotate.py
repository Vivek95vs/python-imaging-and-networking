import pydicom
import numpy as np
import pandas as pd
import os
from scipy import ndimage

# Load the DICOM dose file
dicom_path = "D:/dose/PSQA data/3D Dose/RD1.2.752.243.1.1.20251223131550741.2400.86588.dcm"
ds = pydicom.dcmread(dicom_path)

# Check if pixel array is present
if not hasattr(ds, "pixel_array"):
    print("No pixel array found in the DICOM file.")
    exit()

# Extract the pixel data and dose scaling
dose_scaling = ds.get("DoseGridScaling", 1.0)
dose_array = ds.pixel_array.astype(np.float32) * dose_scaling * 100  # Convert to cGy

print(f"Original dose array shape: {dose_array.shape}")
print(f"Original dose array dimensions: {dose_array.ndim}D")

# Rotate the dose array by 90 degrees (only in the axial plane)
if dose_array.ndim == 3:
    # For 90-degree rotation with reshape=True, the dimensions will swap
    num_slices, rows, cols = dose_array.shape

    # Create a new array with swapped dimensions for rows and cols
    rotated_dose_array = np.zeros((num_slices, cols, rows), dtype=dose_array.dtype)

    for slice_idx in range(num_slices):
        # Rotate each 2D slice by 90 degrees with reshape=True (dimensions will swap)
        rotated_slice = ndimage.rotate(dose_array[slice_idx, :, :], 45, reshape=True)
        rotated_dose_array[slice_idx, :, :] = rotated_slice

    print(f"Rotated dose array shape: {rotated_dose_array.shape}")
    print(f"Applied 90-degree rotation to all slices")

    # Use the rotated array for further processing
    dose_array = rotated_dose_array

elif dose_array.ndim == 2:
    # For 2D case, rotate the single slice
    rows, cols = dose_array.shape
    dose_array = ndimage.rotate(dose_array, 45, reshape=True)
    print(f"Applied 90-degree rotation to 2D dose matrix. New shape: {dose_array.shape}")

# Alternative approach: If you want to keep the original dimensions (with reshape=False)
# This will crop or pad to maintain the original shape
if False:  # Set to True to use this alternative approach
    if dose_array.ndim == 3:
        rotated_dose_array = np.zeros_like(dose_array)
        for slice_idx in range(dose_array.shape[0]):
            rotated_slice = ndimage.rotate(dose_array[slice_idx, :, :], 45, reshape=False, mode='constant', cval=0)
            rotated_dose_array[slice_idx, :, :] = rotated_slice
        dose_array = rotated_dose_array
        print("Used reshape=False to maintain original dimensions")

# Output folder for CSV files
output_folder = "dose_csv_files_rotated_45"
os.makedirs(output_folder, exist_ok=True)

# Handle both 2D and 3D dose arrays
if dose_array.ndim == 2:
    # Save single 2D slice
    csv_path = os.path.join(output_folder, "2D_dose_matrix_rotated_45.csv")
    pd.DataFrame(dose_array).to_csv(csv_path, index=False, header=False)
    print(f"2D dose matrix saved to: {csv_path}")
    print(f"Final shape: {dose_array.shape}")

elif dose_array.ndim == 3:
    # Save each slice as a separate CSV file
    num_slices = dose_array.shape[0]

    # Create a summary file with metadata
    metadata = {
        'Original shape': ['(113, 67, 147)'],
        'Rotated shape': [dose_array.shape],
        'Number of slices': [num_slices],
        'Rotation applied': ['45 degrees'],
        'Rows': [dose_array.shape[1]],
        'Columns': [dose_array.shape[2]],
        'Voxel dimensions (mm)': [
            f"{ds.PixelSpacing[0]} x {ds.PixelSpacing[1]} x {ds.SliceThickness if hasattr(ds, 'SliceThickness') else 'N/A'}"],
        'Dose units': ['cGy'],
        'Max dose': [np.max(dose_array)],
        'Min dose': [np.min(dose_array)],
        'Mean dose': [np.mean(dose_array)]
    }

    summary_path = os.path.join(output_folder, "dose_summary_rotated_45.csv")
    pd.DataFrame(metadata).to_csv(summary_path, index=False)
    print(f"Dose summary saved to: {summary_path}")

    # Save each slice
    for slice_idx in range(num_slices):
        slice_data = dose_array[slice_idx, :, :]
        csv_path = os.path.join(output_folder, f"dose_slice_{slice_idx:03d}_rotated_45.csv")
        pd.DataFrame(slice_data).to_csv(csv_path, index=False, header=False)

    print(f"Saved {num_slices} rotated dose slices to {output_folder}/")

    # Save a representative middle slice
    middle_slice = dose_array[num_slices // 2, :, :]
    middle_csv_path = os.path.join(output_folder, "dose_middle_slice_rotated_45.csv")
    pd.DataFrame(middle_slice).to_csv(middle_csv_path, index=False, header=False)
    print(f"Middle slice (slice {num_slices // 2}) saved to: {middle_csv_path}")

    # Flatten with slice information
    num_slices, rows, cols = dose_array.shape
    flat_data = dose_array.reshape(num_slices * rows, cols)
    csv_path = os.path.join(output_folder, "3D_dose_flattened_rotated_45.csv")
    pd.DataFrame(flat_data).to_csv(csv_path, index=False, header=False)
    print(f"Flattened 3D dose saved to: {csv_path}")
    print(f"Flattened shape: {flat_data.shape}")

else:
    print(f"Unexpected array dimensions: {dose_array.ndim}D")

print(f"\nAll rotated dose files saved to: {os.path.abspath(output_folder)}")