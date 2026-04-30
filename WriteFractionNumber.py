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
            return {"processed_folders": {}, "last_run": None}
    return {"processed_folders": {}, "last_run": None}


def save_processing_log(log_data):
    """Save the processing log to JSON file"""
    log_data["last_run"] = datetime.now().isoformat()
    with open(LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=2)


def get_folder_signature(folder_path, file_count, modification_time=None):
    """
    Create a unique signature for a folder based on its path and contents
    """
    path_str = str(folder_path)

    # If modification time not provided, get it
    if modification_time is None:
        try:
            modification_time = os.path.getmtime(folder_path)
        except:
            modification_time = 0

    # Create signature
    signature_data = f"{path_str}|{file_count}|{modification_time}"
    signature = hashlib.md5(signature_data.encode()).hexdigest()

    return signature


def is_folder_processed(folder_path, file_count, log_data):
    """
    Check if folder has already been processed successfully
    """
    path_str = str(folder_path)

    if path_str in log_data["processed_folders"]:
        folder_info = log_data["processed_folders"][path_str]

        # Get current folder modification time
        try:
            current_mtime = os.path.getmtime(folder_path)
        except:
            current_mtime = 0

        # Check if folder has been modified since last processing
        if current_mtime > folder_info.get("modification_time", 0):
            return False  # Folder was modified, reprocess

        # Check if file count changed
        if file_count != folder_info.get("file_count", 0):
            return False  # File count changed, reprocess

        # If we have the same signature, skip processing
        current_signature = get_folder_signature(folder_path, file_count, current_mtime)
        if current_signature == folder_info.get("signature"):
            return True  # Already processed with same signature

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


def find_dicom_folders(base_path, log_data, force_rescan=False):
    """Find all DICOM folders in the directory tree, skipping processed ones"""
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

            # Check if folder was already processed
            if not force_rescan and is_folder_processed(current_path, file_count, log_data):
                skipped_folders.append({
                    'path': current_path,
                    'file_count': file_count,
                    'reason': 'Already in log with same signature'
                })
                continue

            # Extract folder info
            folder_info_string, individual_values = extract_folder_info_from_path(current_path)

            if folder_info_string and individual_values['fn']:
                # Get modification time
                try:
                    mod_time = os.path.getmtime(current_path)
                except:
                    mod_time = 0

                # Create signature
                signature = get_folder_signature(current_path, file_count, mod_time)

                dicom_folders.append({
                    'path': current_path,
                    'info_string': folder_info_string,
                    'values': individual_values,
                    'file_count': file_count,
                    'modification_time': mod_time,
                    'signature': signature
                })
                print(f"  ✓ Found (new/modified): {current_path}")
                print(f"    → Format: {folder_info_string}")
            else:
                print(f"  ⚠ Skipped (no FN): {current_path}")

    # Report skipped folders
    if skipped_folders and not force_rescan:
        print(f"\n⏭️  Skipped {len(skipped_folders)} already processed folders:")
        for folder in skipped_folders[:5]:  # Show first 5
            print(f"    • {folder['path']} ({folder['file_count']} files) - {folder['reason']}")
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


def add_info_to_dicom(dicom_file, info_string, force_overwrite=False, dry_run=False):
    """Add formatted info string as private tag to DICOM file"""
    try:
        # Read DICOM file
        ds = pydicom.dcmread(dicom_file)

        # Check if tag already exists
        if not force_overwrite and has_folder_info_tag(ds):
            return "skipped"

        if dry_run:
            return "would_write"

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


def process_dicom_folder(folder_info, dry_run=True, force_overwrite=False, check_only=False, log_data=None):
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

    if check_only:
        # Just check which files have the tag
        tagged = 0
        untagged = 0
        for file in files:
            file_path = os.path.join(folder_path, file)
            try:
                ds = pydicom.dcmread(file_path, stop_before_pixels=True)
                if has_folder_info_tag(ds):
                    tagged += 1
                else:
                    untagged += 1
            except:
                untagged += 1

        print(f"   Status: {tagged} files already have tag, {untagged} files need update")
        return {"tagged": tagged, "untagged": untagged, "failed": 0}

    if dry_run:
        print(f"   [DRY RUN] Would add '{info_string}' to {len(files)} files")
        return {"written": 0, "skipped": 0, "failed": 0, "would_write": len(files)}

    written = 0
    skipped = 0
    failed = 0

    for i, file in enumerate(files, 1):
        file_path = os.path.join(folder_path, file)
        result = add_info_to_dicom(file_path, info_string, force_overwrite, dry_run)

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
    path_str = str(folder_info['path'])

    log_data["processed_folders"][path_str] = {
        "info_string": folder_info['info_string'],
        "file_count": folder_info['file_count'],
        "processed_files": processed_count,
        "skipped_files": skipped_count,
        "modification_time": folder_info.get('modification_time', 0),
        "signature": folder_info.get('signature'),
        "processed_date": datetime.now().isoformat()
    }

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

    # Show last run info
    if log_data["last_run"]:
        print(f"\n📋 Last run: {log_data['last_run']}")
        print(f"   Processed folders in log: {len(log_data['processed_folders'])}")

    # Ask for mode first
    print("\n" + "=" * 60)
    print("Options:")
    print("1. Quick scan (skip already processed folders)")
    print("2. Full rescan (check all folders again)")
    print("3. Check status (see which files have tags)")
    print("4. Force reprocess specific folders")
    print("5. View processing log")
    print("6. Clear processing log")
    print("7. Exit")

    choice = input("\nEnter your choice (1-7): ").strip()

    if choice == '7':
        print("Exiting...")
        return

    elif choice == '5':
        # View processing log
        print("\n📋 PROCESSING LOG:")
        print("=" * 60)
        if not log_data["processed_folders"]:
            print("No folders have been processed yet.")
        else:
            for path, info in log_data["processed_folders"].items():
                print(f"  • {path}")
                print(f"    → {info['info_string']} - {info['processed_files']} files processed")
        input("\nPress Enter to continue...")
        return

    elif choice == '6':
        # Clear processing log
        confirm = input("Are you sure you want to clear the processing log? (yes/no): ").strip().lower()
        if confirm == 'yes':
            os.remove(LOG_FILE) if os.path.exists(LOG_FILE) else None
            print("✅ Processing log cleared!")
        return

    # Determine scan mode
    force_rescan = (choice == '2')

    # Find DICOM folders
    print("\n🔍 SCANNING FOR DICOM FOLDERS...")
    dicom_folders = find_dicom_folders(base_path, log_data, force_rescan)

    if not dicom_folders:
        print("\n✅ No new or modified DICOM folders found!")
        return

    print(f"\n✅ Found {len(dicom_folders)} new/modified DICOM folders")

    # Show summary
    print("\n📊 Summary of new/modified folders:")
    for folder in dicom_folders:
        print(f"   • {folder['info_string']}: {folder['file_count']} files")

    if choice == '3':
        # Check status mode
        print("\n🔍 CHECK MODE - Scanning for existing tags")
        total_tagged = 0
        total_untagged = 0

        for folder_info in dicom_folders:
            result = process_dicom_folder(folder_info, dry_run=False, check_only=True)
            total_tagged += result["tagged"]
            total_untagged += result["untagged"]

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total files with tags: {total_tagged}")
        print(f"Total files without tags: {total_untagged}")
        return

    elif choice == '4':
        # Force reprocess specific folders
        print("\nAvailable formats:")
        unique_formats = set(f['info_string'] for f in dicom_folders)
        for fmt in sorted(unique_formats):
            count = sum(1 for f in dicom_folders if f['info_string'] == fmt)
            print(f"   {fmt}: {count} folder(s)")

        search_format = input("\nEnter format to reprocess (e.g., S22_P1_FG1_FN1): ").strip()
        folders_to_process = [f for f in dicom_folders if f['info_string'] == search_format]

        if not folders_to_process:
            print(f"No folders found with format: {search_format}")
            return

        force_overwrite = True
        print(f"\n⚠️  FORCE MODE - Reprocessing {len(folders_to_process)} folders")

    else:
        # Normal processing - only update untagged files
        folders_to_process = dicom_folders
        force_overwrite = False

    # Ask for confirmation
    print("\n" + "=" * 60)
    print("Ready to process folders")
    print(f"Mode: {'Force overwrite' if force_overwrite else 'Safe mode (only untagged files)'}")
    print(f"Folders to process: {len(folders_to_process)}")
    print(f"Total files: {sum(f['file_count'] for f in folders_to_process)}")

    confirm = input("\nProceed? (yes/no): ").strip().lower()
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
    processed_folders_count = 0

    for folder_info in folders_to_process:
        result = process_dicom_folder(folder_info, dry_run=False, force_overwrite=force_overwrite)

        written = result.get("written", 0)
        skipped = result.get("skipped", 0)
        failed = result.get("failed", 0)

        total_written += written
        total_skipped += skipped
        total_failed += failed

        # Update log for successfully processed folders
        if written > 0 or skipped > 0:
            log_data = update_processing_log(folder_info, written, skipped, log_data)
            processed_folders_count += 1

        # Save log after each folder
        save_processing_log(log_data)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Folders processed successfully: {processed_folders_count}")
    print(f"Folders in log: {len(log_data['processed_folders'])}")
    print(f"Files written: {total_written}")
    print(f"Files skipped (already had tag): {total_skipped}")
    print(f"Files failed: {total_failed}")

    if processed_folders_count > 0:
        print(f"\n✅ Log updated: {LOG_FILE}")

    # Show next run suggestion
    if processed_folders_count == 0:
        print("\nℹ️  No new folders were processed. Next time use option 1 for quick scan.")


if __name__ == "__main__":
    main()