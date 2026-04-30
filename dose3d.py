import pydicom
import numpy as np
import pandas as pd
import os

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

print(f"Dose array shape: {dose_array.shape}")
print(f"Dose array dimensions: {dose_array.ndim}D")

# Output folder for CSV files
output_folder = "dose_csv_files"
os.makedirs(output_folder, exist_ok=True)

# Handle both 2D and 3D dose arrays
if dose_array.ndim == 2:
    # Save single 2D slice
    csv_path = os.path.join(output_folder, "2D_dose_matrix.csv")
    pd.DataFrame(dose_array).to_csv(csv_path, index=False, header=False)
    print(f"2D dose matrix saved to: {csv_path}")

elif dose_array.ndim == 3:
    # Save each slice as a separate CSV file
    num_slices = dose_array.shape[0]

    # Create a summary file with metadata
    metadata = {
        'Shape': [dose_array.shape],
        'Number of slices': [num_slices],
        'Voxel dimensions (mm)': [
            f"{ds.PixelSpacing[0]} x {ds.PixelSpacing[1]} x {ds.SliceThickness if hasattr(ds, 'SliceThickness') else 'N/A'}"],
        'Dose units': ['cGy'],
        'Max dose': [np.max(dose_array)],
        'Min dose': [np.min(dose_array)],
        'Mean dose': [np.mean(dose_array)]
    }

    summary_path = os.path.join(output_folder, "dose_summary.csv")
    pd.DataFrame(metadata).to_csv(summary_path, index=False)
    print(f"Dose summary saved to: {summary_path}")

    # Save each slice
    for slice_idx in range(num_slices):
        slice_data = dose_array[slice_idx, :, :]
        csv_path = os.path.join(output_folder, f"dose_slice_{slice_idx:03d}.csv")
        pd.DataFrame(slice_data).to_csv(csv_path, index=False, header=False)

    print(f"Saved {num_slices} dose slices to {output_folder}/")

    # Optional: Save a representative middle slice
    middle_slice = dose_array[num_slices // 2, :, :]
    middle_csv_path = os.path.join(output_folder, "dose_middle_slice.csv")
    pd.DataFrame(middle_slice).to_csv(middle_csv_path, index=False, header=False)
    print(f"Middle slice (slice {num_slices // 2}) saved to: {middle_csv_path}")

    # Flatten with slice information
    num_slices, rows, cols = dose_array.shape
    flat_data = dose_array.reshape(num_slices * rows, cols)
    csv_path = os.path.join(output_folder, "3D_dose_flattened.csv")
    pd.DataFrame(flat_data).to_csv(csv_path, index=False, header=False)
    print(f"Flattened 3D dose saved to: {csv_path}")

else:
    print(f"Unexpected array dimensions: {dose_array.ndim}D")