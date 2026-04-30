import os
import pydicom
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Define constants
PRIVATE_GROUP = 0x0011
PRIVATE_CREATOR = 'FOLDER_INFO'
PRIVATE_TAG = 0x10
LOG_FILE = "dicom_processing_log.json"


def load_processing_log():
    """Load the processing log from JSON file"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"processed_folders": []}
    return {"processed_folders": []}


def save_processing_log(log_data):
    """Save the processing log to JSON file"""
    with open(LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=2)


def is_folder_in_log(folder_path, log_data):
    """Check if folder path already exists in the log"""
    path_str = str(folder_path)

    for entry in log_data["processed_folders"]:
        if entry["path"] == path_str:
            return True

    return False


def extract_folder_info_from_path(folder_path):
    """
    Extract S, P, FG, FN values from folder path and format as S*_P*_FG*_FN*
    """
    path = Path(folder_path)
    path_parts = path.parts

    # Initialize values
    s_value = None
    p_value = None
    fg_value = None
    fn_value = None

    # Search from the end backwards to find the most specific folders
    for part in reversed(path_parts):
        if not s_value and part.startswith('S'):
            match = re.search(r'S(\d+)', part)
            if match:
                s_value = match.group(1)
        elif not p_value and part.startswith('P'):
            match = re.search(r'P(\d+)', part)
            if match:
                p_value = match.group(1)
        elif not fg_value and part.startswith('FG'):
            match = re.search(r'FG(\d+)', part)
            if match:
                fg_value = match.group(1)
        elif not fn_value and part.startswith('FN'):
            match = re.search(r'FN(\d+)', part)
            if match:
                fn_value = match.group(1)

    # Format the string
    if s_value and p_value and fg_value and fn_value:
        formatted_string = f"S{s_value}_P{p_value}_FG{fg_value}_FN{fn_value}"
    else:
        # If any value is missing, use what we have
        parts = []
        if s_value:
            parts.append(f"S{s_value}")
        if p_value:
            parts.append(f"P{p_value}")
        if fg_value:
            parts.append(f"FG{fg_value}")
        if fn_value:
            parts.append(f"FN{fn_value}")
        formatted_string = "_".join(parts) if parts else None

    return formatted_string, {
        's': s_value,
        'p': p_value,
        'fg': fg_value,
        'fn': fn_value
    }


def find_dicom_folders(base_path, log_data):
    """Find all DICOM folders in the directory tree, checking against log"""
    base_path = Path(base_path)
    dicom_folders = []
    skipped_folders = []

    print(f"\nScanning for DICOM folders in: {base_path}")

    # Walk through all directories
    for root, dirs, files in os.walk(base_path):
        current_path = Path(root)

        # Check if this directory is named "DICOM"
        if current_path.name == "DICOM" and files:
            file_count = len(files)

            # Check if folder is already in log
            if is_folder_in_log(current_path, log_data):
                skipped_folders.append({
                    'path': current_path,
                    'file_count': file_count
                })
                continue

            # Extract folder info
            folder_info_string, individual_values = extract_folder_info_from_path(current_path)

            if folder_info_string and individual_values['fn']:
                dicom_folders.append({
                    'path': current_path,
                    'info_string': folder_info_string,
                    'values': individual_values,
                    'file_count': file_count
                })
                print(f"  ✓ Found new folder: {current_path}")
                print(f"    → Format: {folder_info_string}")
            else:
                print(f"  ⚠ Skipped (no FN): {current_path}")

    # Report skipped folders
    if skipped_folders:
        print(f"\n⏭️  Skipped {len(skipped_folders)} folders (already in log):")
        for folder in skipped_folders[:5]:  # Show first 5
            print(f"    • {folder['path']} ({folder['file_count']} files)")
        if len(skipped_folders) > 5:
            print(f"    ... and {len(skipped_folders) - 5} more")

    return dicom_folders


def has_folder_info_tag(ds):
    """Check if DICOM dataset already has the folder info private tag"""
    try:
        private_block = ds.private_block(PRIVATE_GROUP, PRIVATE_CREATOR)
        if private_block:
            tag = private_block.get_tag(PRIVATE_TAG)
            if tag and tag in ds:
                return True
        return False
    except (KeyError, AttributeError):
        return False


def add_info_to_dicom(dicom_file, info_string):
    """Add formatted info string as private tag to DICOM file"""
    try:
        # Read DICOM file
        ds = pydicom.dcmread(dicom_file)

        # Check if tag already exists
        if has_folder_info_tag(ds):
            return "skipped"

        # Create a private block for folder info
        private_block = ds.private_block(PRIVATE_GROUP, PRIVATE_CREATOR, create=True)

        # Add the formatted string as private tag
        private_block.add_new(PRIVATE_TAG, 'LO', info_string)

        # Save the file
        ds.save_as(dicom_file)
        return "written"

    except Exception as e:
        print(f"    ✗ Error: {os.path.basename(dicom_file)} - {str(e)}")
        return "failed"


def process_dicom_folder(folder_info):
    """Process all DICOM files in a folder"""
    folder_path = folder_info['path']
    info_string = folder_info['info_string']
    values = folder_info['values']

    print(f"\n📁 Processing: {folder_path}")
    print(f"   Format: {info_string}")
    print(f"   Values: S{values['s']}, P{values['p']}, FG{values['fg']}, FN{values['fn']}")

    # Get all files in folder
    files = [f for f in os.listdir(folder_path)
             if os.path.isfile(os.path.join(folder_path, f))]

    print(f"   Files found: {len(files)}")

    written = 0
    skipped = 0
    failed = 0

    for i, file in enumerate(files, 1):
        file_path = os.path.join(folder_path, file)
        result = add_info_to_dicom(file_path, info_string)

        if result == "written":
            written += 1
        elif result == "skipped":
            skipped += 1
        elif result == "failed":
            failed += 1

        # Show progress every 10 files or at the end
        if i % 10 == 0 or i == len(files):
            print(f"   Progress: {i}/{len(files)} files (✓{written} ⏭️{skipped} ✗{failed})", end='\r')

    print()  # New line after progress

    return {"written": written, "skipped": skipped, "failed": failed}


def update_processing_log(folder_info, processed_count, skipped_count, log_data):
    """Update the processing log with folder information"""
    log_data["processed_folders"].append({
        "path": str(folder_info['path']),
        "info_string": folder_info['info_string'],
        "file_count": folder_info['file_count'],
        "processed_files": processed_count,
        "skipped_files": skipped_count,
        "processed_date": datetime.now().isoformat()
    })

    return log_data


def main():
    # Your base path
    base_path = r"D:\PatientImages"

    print("=" * 60)
    print("DICOM FOLDER INFO TAG WRITER")
    print("Format: S*_P*_FG*_FN*")
    print("=" * 60)

    # Load processing log
    log_data = load_processing_log()

    # Show log status
    print(f"\n📋 Found {len(log_data['processed_folders'])} folders in processing log")

    # Simple options
    print("\n" + "=" * 60)
    print("Options:")
    print("1. Process all new folders (skip those already in log)")
    print("2. Force reprocess everything (ignore log)")
    print("3. View processing log")
    print("4. Clear processing log")
    print("5. Exit")

    # choice = input("\nEnter your choice (1-5): ").strip()
    choice ='1'
    if choice == '5':
        print("Exiting...")
        return

    elif choice == '3':
        # View processing log
        print("\n📋 PROCESSING LOG:")
        print("=" * 60)
        if not log_data["processed_folders"]:
            print("No folders have been processed yet.")
        else:
            for i, entry in enumerate(log_data["processed_folders"], 1):
                print(f"{i}. {entry['path']}")
                print(
                    f"   → {entry['info_string']} - {entry['processed_files']} files processed on {entry['processed_date'][:10]}")
        input("\nPress Enter to continue...")
        return

    elif choice == '4':
        # Clear processing log
        confirm = input("Are you sure you want to clear the processing log? (yes/no): ").strip().lower()
        if confirm == 'yes':
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            print("✅ Processing log cleared!")
        return

    # Determine if we should force reprocess
    force_reprocess = (choice == '2')

    # Find DICOM folders
    print("\n🔍 SCANNING FOR DICOM FOLDERS...")

    if force_reprocess:
        print("⚠️  Force mode: Checking ALL folders (ignoring log)")
        # Create empty log for force reprocess
        temp_log = {"processed_folders": []}
        dicom_folders = find_dicom_folders(base_path, temp_log)
    else:
        # Normal mode: skip folders already in log
        dicom_folders = find_dicom_folders(base_path, log_data)

    if not dicom_folders:
        print("\n✅ No new folders to process!")
        return

    print(f"\n✅ Found {len(dicom_folders)} folders to process")

    # Show summary
    print("\n📊 Folders to process:")
    for folder in dicom_folders:
        print(f"   • {folder['info_string']}: {folder['file_count']} files")

    # Ask for confirmation
    print(f"\nTotal files to process: {sum(f['file_count'] for f in dicom_folders)}")
    # confirm = input("\nProceed with processing? (yes/no): ").strip().lower()
    confirm='yes'
    if confirm != 'yes':
        print("Operation cancelled")
        return

    # Process folders
    print("\n" + "=" * 60)
    print("PROCESSING DICOM FOLDERS")
    print("=" * 60)

    total_written = 0
    total_skipped = 0
    total_failed = 0
    processed_count = 0

    for folder_info in dicom_folders:
        result = process_dicom_folder(folder_info)

        written = result.get("written", 0)
        skipped = result.get("skipped", 0)
        failed = result.get("failed", 0)

        total_written += written
        total_skipped += skipped
        total_failed += failed

        # Update log for this folder
        if force_reprocess:
            # For force reprocess, we need to check if folder already exists in log
            if not is_folder_in_log(folder_info['path'], log_data):
                log_data = update_processing_log(folder_info, written, skipped, log_data)
                processed_count += 1
        else:
            # Normal mode - these are all new folders
            log_data = update_processing_log(folder_info, written, skipped, log_data)
            processed_count += 1

        # Save log after each folder
        save_processing_log(log_data)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"New folders processed and logged: {processed_count}")
    print(f"Total folders in log: {len(log_data['processed_folders'])}")
    print(f"Files written: {total_written}")
    print(f"Files skipped (already had tag): {total_skipped}")
    print(f"Files failed: {total_failed}")

    if processed_count > 0:
        print(f"\n✅ Log updated: {LOG_FILE}")
        print("\nNext time you run this script, these folders will be skipped automatically!")


if __name__ == "__main__":
    main()