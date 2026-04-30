import os
import pydicom
from pydicom.uid import generate_uid

# Define input folder containing 512 CBCT DICOM images
input_folder = "D:/Aravinth/2. CBCT/DICOM"
output_folder = "D:/Aravinth/2. output"  # Optional, can be same as input

# Custom values to insert
new_patient_name = "xyz"
new_patient_id = "123"
new_series_uid = generate_uid()  # Generate a new SeriesInstanceUID

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

# Loop through all DICOM files
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".dcm"):
        file_path = os.path.join(input_folder, filename)
        ds = pydicom.dcmread(file_path)

        # Modify Patient Name
        ds.PatientName = new_patient_name
        ds.PatientID = new_patient_id

        # Modify Series Instance UID (RTID equivalent in some CBCT workflows)
        ds.SeriesInstanceUID = new_series_uid

        # --- If you are using a custom/private tag for RTID ---
        # For example, using tag (0019,1001) in private range
        # ds.add_new((0x0019, 0x1001), 'LO', 'MyCustomRTID')

        # Save the modified DICOM file
        out_path = os.path.join(output_folder, filename)
        ds.save_as(out_path)

print("All DICOM files updated and saved.")