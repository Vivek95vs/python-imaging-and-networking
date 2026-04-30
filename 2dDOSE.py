import pydicom
import numpy as np
import pandas as pd
import os

# Load the 2D dose DICOM file
dicom_path = "D:/dose/PSQA data/2D Dose/RD1.2.752.243.1.1.20251223131550741.2400.86588.3.255.2.dcm"  # Adjust path as needed
ds = pydicom.dcmread(dicom_path)

# Check if pixel array is present
if not hasattr(ds, "pixel_array"):
    print("No pixel array found in the DICOM file.")
    exit()

# Extract the pixel data and dose scaling
dose_scaling = ds.get("DoseGridScaling", 1.0)
dose_array = ds.pixel_array.astype(np.float32) * dose_scaling * 100  # Convert to cGy

# Output folder for CSV files
output_folder = "dose_csv_files"
os.makedirs(output_folder, exist_ok=True)

# Save the 2D dose matrix as a single CSV file
csv_path = os.path.join(output_folder, "2D_dose_matrix.csv")
pd.DataFrame(dose_array).to_csv(csv_path, index=False, header=False)
print(f"Dose matrix saved to: {csv_path}")