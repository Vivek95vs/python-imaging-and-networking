# import os
# import pydicom
#
# # === Define the input directory with DICOM files ===
# dicom_dir = "D:/Image_tag_change"
#
# # === Define the tags and their new values ===
# # Format: (Group, Element): "New Value"
# tags_to_update = {
#     (0x0010, 0x0010): "John Doe",         # PatientName
#     (0x0010, 0x0020): "123456789",        # PatientID
#     (0x0008, 0x1030): "Brain MRI Study"   # StudyDescription
# }
#
# # === Walk through all DICOM files in the directory ===
# for filename in os.listdir(dicom_dir):
#     filepath = os.path.join(dicom_dir, filename)
#
#     # Process only files with .dcm extension
#     if not filename.lower().endswith(".dcm"):
#         continue
#
#     try:
#         # Load DICOM file
#         ds = pydicom.dcmread(filepath)
#
#         # Update tags
#         for tag, value in tags_to_update.items():
#             if tag in ds:
#                 ds[tag].value = value
#             else:
#                 ds.add_new(tag, 'LO', value)  # Default VR = 'LO'; adjust as needed
#
#         # Save back to the same file (overwrite)
#         ds.save_as(filepath)
#         print(f"Updated: {filename}")
#
#     except Exception as e:
#         print(f"Failed to process {filename}: {e}")



import os
import pydicom

# === Define the input directory with DICOM files ===
dicom_dir = "D:/Aravinth/3.LilacAcquiredImage"

# === Define tags to update manually (other than PatientAge) ===
# Format: (Group, Element): "New Value"
tags_to_update = {
    (0x0010, 0x0010): "John Doe",         # PatientName
    (0x0010, 0x0020): "123456789",        # PatientID
    (0x0008, 0x1030): "Brain MRI Study",   # StudyDescription
    (0x0018, 0x0015): "BREAST",
    (0x0018, 0x1700): "RECTANGULAR",
    (0x0018, 0x1147): "RECTANGLE",
    (0X0018, 0X7050): "ALUMINUM",
}

# === Tag for PatientAge ===
patient_age_tag = (0x0010, 0x1010)  # PatientAge

# === Walk through all DICOM files in the directory ===
for filename in os.listdir(dicom_dir):
    filepath = os.path.join(dicom_dir, filename)

    if not filename.lower().endswith(".dcm"):
        continue

    try:
        # Load the DICOM file
        ds = pydicom.dcmread(filepath)

        # Update static tags
        for tag, value in tags_to_update.items():
            if tag in ds:
                ds[tag].value = value
            else:
                ds.add_new(tag, 'LO', value)

        # Handle PatientAge formatting (e.g., 65 -> '065Y')
        if patient_age_tag in ds:
            raw_age = str(ds[patient_age_tag].value).strip()

            # Extract numeric part (safe handling)
            if raw_age.isdigit():
                formatted_age = f"{int(raw_age):03d}Y"
                ds[patient_age_tag].value = formatted_age
            elif raw_age.endswith('Y') and raw_age[:-1].isdigit():
                # Already in proper format, just pad if needed
                formatted_age = f"{int(raw_age[:-1]):03d}Y"
                ds[patient_age_tag].value = formatted_age
            else:
                print(f"Warning: Unexpected age format in {filename}: {raw_age}")
        else:
            print(f"PatientAge not found in {filename}, skipping age formatting.")

        tag = (0x0018, 0x1702)

        if tag in ds:
            val = str(ds[tag].value).strip().replace('<', '').replace('>', '')
            try:
                float_val = float(val)
                int_val = int(float_val)  # truncate decimals
                ds[tag].value = str(int_val)  # Set as string for IS VR
            except Exception as e:
                print(f"Warning: Failed to convert Collimator Left Vertical Edge in {filename}: {val} ({e})")

        tag = (0x0018, 0x1704)

        if tag in ds:
            val = str(ds[tag].value).strip().replace('<', '').replace('>', '')
            try:
                float_val = float(val)
                int_val = int(float_val)  # truncate decimals
                ds[tag].value = str(int_val)  # Set as string for IS VR
            except Exception as e:
                print(f"Warning: Failed to convert Collimator Left Vertical Edge in {filename}: {val} ({e})")

        tag = (0x0018, 0x1706)

        if tag in ds:
            val = str(ds[tag].value).strip().replace('<', '').replace('>', '')
            try:
                float_val = float(val)
                int_val = int(float_val)  # truncate decimals
                ds[tag].value = str(int_val)  # Set as string for IS VR
            except Exception as e:
                print(f"Warning: Failed to convert Collimator Left Vertical Edge in {filename}: {val} ({e})")

        tag = (0x0018, 0x11A0)

        if tag in ds:
            val = str(ds[tag].value).strip().replace('<', '').replace('>', '')
            try:
                float_val = float(val)
                int_val = int(float_val)  # truncate decimals
                ds[tag].value = str(int_val)  # Set as string for IS VR
            except Exception as e:
                print(f"Warning: Failed to convert Collimator Left Vertical Edge in {filename}: {val} ({e})")

        tag = (0x0018, 0x1150)

        if tag in ds:
            val = str(ds[tag].value).strip().replace('<', '').replace('>', '')
            try:
                float_val = float(val)
                int_val = int(float_val)  # truncate decimals
                ds[tag].value = str(int_val)  # Set as string for IS VR
            except Exception as e:
                print(f"Warning: Failed to convert Collimator Left Vertical Edge in {filename}: {val} ({e})")

        tag = (0x0018, 0x1151)

        if tag in ds:
            val = str(ds[tag].value).strip().replace('<', '').replace('>', '')
            try:
                float_val = float(val)
                int_val = int(float_val)  # truncate decimals
                ds[tag].value = str(int_val)  # Set as string for IS VR
            except Exception as e:
                print(f"Warning: Failed to convert Collimator Left Vertical Edge in {filename}: {val} ({e})")

        institution_address_tag = (0x0008, 0x0081)

        if institution_address_tag in ds:
            raw_address = str(ds[institution_address_tag].value)
            cleaned_address = raw_address.replace(',', '')  # remove all commas
            ds[institution_address_tag].value = cleaned_address
        else:
            print(f"Institution Address tag not found in {filename}, skipping update.")

        # Save changes
        ds.save_as(filepath)
        print(f"✅ Updated: {filename}")

    except Exception as e:
        print(f"❌ Failed to process {filename}: {e}")

