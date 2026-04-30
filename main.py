import pydicom
import numpy as np
import pandas as pd
import os

# Load the DICOM dose file
dicom_path = "D:/RDose/2D dose/RD1.2D_Dose_Coronal.dcm"  # Replace with your actual DICOM file path
ds = pydicom.dcmread(dicom_path)
print(ds)
# Extract dose grid scaling factor
dose_scaling = ds.get("DoseGridScaling", 1)  # If missing, assume 1

# Extract dose values and apply scaling
if hasattr(ds, "pixel_array"):
    dose_values = ds.pixel_array * dose_scaling  # Convert to Gy
else:
    print("No pixel array found in the DICOM file.")
    exit()

# Create a folder to store CSV files
output_folder = "dose_csv_files"
os.makedirs(output_folder, exist_ok=True)

# Save each frame as a separate CSV file
for i in range(dose_values.shape[0]):  # Loop through frames (slices)
    df = pd.DataFrame(dose_values[i])  # Convert to Pandas DataFrame
    csv_filename = os.path.join(output_folder, f"dose_frame_{i+1}.csv")
    df.to_csv(csv_filename, index=False, header=False)
    print(f"Saved {csv_filename}")

# Optionally: Save all frames in a single CSV file (appending each frame)
combined_csv_path = os.path.join(output_folder, "combined_dose_values.csv")
with open(combined_csv_path, "w") as f:
    for i in range(dose_values.shape[0]):
        df = pd.DataFrame(dose_values[i])
        f.write(f"Frame {i+1}\n")  # Label each frame
        df.to_csv(f, index=False, header=False)
        f.write("\n")  # Add space between frames

print(f"All frames saved to {combined_csv_path}")


