import os
import pydicom
import re
from pathlib import Path


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


def find_dicom_folders(base_path):
    """Find all DICOM folders in the directory tree"""
    base_path = Path(base_path)
    dicom_folders = []

    print(f"\nScanning for DICOM folders in: {base_path}")

    # Walk through all directories
    for root, dirs, files in os.walk(base_path):
        current_path = Path(root)

        # Check if this directory is named "DICOM"
        if current_path.name == "DICOM" and files:
            # Extract folder info
            folder_info_string, individual_values = extract_folder_info_from_path(current_path)

            if folder_info_string and individual_values['fn']:
                dicom_folders.append({
                    'path': current_path,
                    'info_string': folder_info_string,
                    'values': individual_values,
                    'file_count': len(files)
                })
                print(f"  ✓ Found: {current_path}")
                print(f"    → Format: {folder_info_string}")
            else:
                print(f"  ⚠ Skipped (no FN): {current_path}")

    return dicom_folders


def add_info_to_dicom(dicom_file, info_string):
    """Add formatted info string as private tag to DICOM file"""
    try:
        # Read DICOM file
        ds = pydicom.dcmread(dicom_file)

        # Create a private block for folder info
        # Using 0x0011 as group, you can change this if needed
        private_block = ds.private_block(0x0011, 'FOLDER_INFO', create=True)

        # Add the formatted string as private tag (0x10)
        # Tag will be (0x0011, 0x10xx) where xx is determined by pydicom
        private_block.add_new(0x10, 'LO', info_string)

        # Save the file
        ds.save_as(dicom_file)
        print(f"    ✓ Added '{info_string}' to: {os.path.basename(dicom_file)}")
        return True

    except Exception as e:
        print(f"    ✗ Error: {os.path.basename(dicom_file)} - {str(e)}")
        return False


def process_dicom_folder(folder_info, dry_run=True):
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

    if dry_run:
        print(f"   [DRY RUN] Would add '{info_string}' to {len(files)} files")
        return len(files), 0

    processed = 0
    failed = 0

    for file in files:
        file_path = os.path.join(folder_path, file)
        if add_info_to_dicom(file_path, info_string):
            processed += 1
        else:
            failed += 1

    return processed, failed


def main():
    # Your base path
    base_path = r"D:\PatientImages"

    print("=" * 60)
    print("DICOM FOLDER INFO TAG WRITER")
    print("Format: S*_P*_FG*_FN*")
    print("=" * 60)

    # Find all DICOM folders
    print("\n🔍 SCANNING FOR DICOM FOLDERS...")
    dicom_folders = find_dicom_folders(base_path)

    if not dicom_folders:
        print("\n❌ No valid DICOM folders found with complete information!")
        return

    print(f"\n✅ Found {len(dicom_folders)} valid DICOM folders")

    # Show summary
    print("\n📊 Summary of found folders:")
    for folder in dicom_folders:
        print(f"   • {folder['info_string']}: {folder['file_count']} files")

    # Ask for mode
    print("\n" + "=" * 60)
    print("Options:")
    print("1. Dry run (show what would be done)")
    print("2. Actual run (modify files)")
    print("3. Process specific format only")
    print("4. Exit")

    #choice = input("\nEnter your choice (1-4): ").strip()
    choice = '2'

    if choice == '4':
        print("Exiting...")
        return

    # Filter folders if specific format requested
    folders_to_process = dicom_folders
    if choice == '3':
        print("\nAvailable formats:")
        unique_formats = set(f['info_string'] for f in dicom_folders)
        for fmt in sorted(unique_formats):
            count = sum(1 for f in dicom_folders if f['info_string'] == fmt)
            print(f"   {fmt}: {count} folder(s)")

        search_format = input("\nEnter format to process (e.g., S22_P1_FG1_FN1): ").strip()
        folders_to_process = [f for f in dicom_folders if f['info_string'] == search_format]

        if not folders_to_process:
            print(f"No folders found with format: {search_format}")
            return
        print(f"Found {len(folders_to_process)} folder(s)")

    dry_run = (choice == '1')

    if dry_run:
        print("\n🔍 DRY RUN MODE - No files will be modified")
    else:
        print("\n⚠️ ACTUAL RUN MODE - Files WILL be modified")
        #confirm = input("Are you sure? (yes/no): ").strip().lower()
        confirm = 'yes'
        if confirm != 'yes':
            print("Operation cancelled")
            return

    # Process folders
    print("\n" + "=" * 60)
    print("PROCESSING DICOM FOLDERS")
    print("=" * 60)

    total_processed = 0
    total_failed = 0

    for folder_info in folders_to_process:
        processed, failed = process_dicom_folder(folder_info, dry_run)
        total_processed += processed
        total_failed += failed

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Folders processed: {len(folders_to_process)}")
    print(f"Total files processed: {total_processed}")
    print(f"Total files failed: {total_failed}")

    if dry_run:
        print("\n🔍 This was a DRY RUN - No files were modified")
        print("Run again with option 2 to actually modify files")
    else:
        print("\n✅ Processing complete!")


# Quick test function to verify format extraction
def test_path_extraction():
    """Test the extraction function with sample paths"""
    test_paths = [
        r"D:\PatientImages\RT202402A05\S22\P1\FG1\FN1_20260107\DailyImages\KV0\CBCT\DICOM",
        r"D:\PatientImages\RT202402A05\S22\P1\FG1\FN2\DailyImages\KV0\CBCT\DICOM",
        r"D:\PatientImages\RT202402A05\S23\P2\FG2\FN3_20260108\DailyImages\KV1\RAD\DICOM",
    ]

    print("\n🔧 Testing format extraction:")
    print("-" * 40)
    for path in test_paths:
        format_string, values = extract_folder_info_from_path(path)
        print(f"Path: {path}")
        print(f"  → Format: {format_string}")
        print(f"  → Values: S{values['s']}, P{values['p']}, FG{values['fg']}, FN{values['fn']}")
        print()


if __name__ == "__main__":
    # Run test first to verify format extraction
    #test_path_extraction()

    # Ask if user wants to continue with actual processing
    response = 'yes'
    if response == 'yes':
        main()
    else:
        print("Exiting...")