import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import json


class DICOMBatchCopier:
    def __init__(self, root):
        self.root = root
        self.root.title("DICOM Batch Copier - Copy Only .dcm Files (No Folders)")
        self.root.geometry("750x600")

        # Variables
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.progress_var = tk.DoubleVar()
        self.processed_log_file = "processed_folders.json"

        self.setup_ui()

    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Input Path Section
        ttk.Label(main_frame, text="Input Path:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.input_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_input).grid(row=0, column=2, padx=5, pady=5)

        # Output Path Section
        ttk.Label(main_frame, text="Output Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_path, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_output).grid(row=1, column=2, padx=5, pady=5)

        # Options Frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="5")
        options_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        self.skip_processed = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip already processed folders",
                        variable=self.skip_processed).pack(anchor=tk.W)

        self.overwrite_files = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Overwrite existing .dcm files",
                        variable=self.overwrite_files).pack(anchor=tk.W)

        # Progress Bar
        ttk.Label(main_frame, text="Progress:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # Status Text
        ttk.Label(main_frame, text="Status:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.status_text = tk.Text(main_frame, height=18, width=85)
        self.status_text.grid(row=5, column=0, columnspan=3, pady=5)

        # Scrollbar for status text
        scrollbar = ttk.Scrollbar(main_frame, command=self.status_text.yview)
        scrollbar.grid(row=5, column=3, sticky=(tk.N, tk.S))
        self.status_text.config(yscrollcommand=scrollbar.set)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)

        self.start_button = ttk.Button(button_frame, text="Start Copying", command=self.start_copying)
        self.start_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Clear Status", command=self.clear_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset Processed Log", command=self.reset_processed_log).pack(side=tk.LEFT,
                                                                                                    padx=5)

    def browse_input(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_path.set(directory)

    def browse_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_path.set(directory)

    def clear_status(self):
        self.status_text.delete(1.0, tk.END)

    def log_message(self, message):
        """Add a message to the status text widget"""
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.root.update()

    def load_processed_folders(self):
        """Load the list of already processed folders from JSON file"""
        if os.path.exists(self.processed_log_file):
            try:
                with open(self.processed_log_file, 'r') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()

    def save_processed_folder(self, folder_path):
        """Save a processed folder to the JSON file"""
        processed = self.load_processed_folders()
        processed.add(folder_path)
        with open(self.processed_log_file, 'w') as f:
            json.dump(list(processed), f)

    def reset_processed_log(self):
        """Reset the processed folders log"""
        if os.path.exists(self.processed_log_file):
            os.remove(self.processed_log_file)
            self.log_message("✓ Processed folders log has been reset!")
            messagebox.showinfo("Success", "Processed log has been reset!")
        else:
            messagebox.showinfo("Info", "No processed log file found!")

    def find_all_dcm_files(self, input_path):
        """
        Recursively find ALL .dcm files in the input path and group them by their top-level patient folder
        Returns a dictionary: {patient_folder_name: [list_of_dcm_files_with_full_path]}
        """
        patient_dcm_files = {}
        processed_folders = self.load_processed_folders() if self.skip_processed.get() else set()

        # Walk through all directories recursively
        for root, dirs, files in os.walk(input_path):
            # Check for .dcm files in current directory
            dcm_files = [f for f in files if f.lower().endswith('.dcm')]

            if dcm_files:
                # Get the relative path from input_path
                rel_path = os.path.relpath(root, input_path)

                # Get the top-level patient folder (first part of relative path)
                if rel_path == '.':
                    patient_folder = os.path.basename(root)
                else:
                    patient_folder = rel_path.split(os.sep)[0]

                # Full path to the folder containing DICOM files
                folder_full_path = root

                # Check if this folder has been processed before
                if folder_full_path in processed_folders:
                    self.log_message(f"⏭ Skipping already processed folder: {rel_path}")
                    continue

                # Add DICOM files to the patient's list
                if patient_folder not in patient_dcm_files:
                    patient_dcm_files[patient_folder] = []

                for dcm_file in dcm_files:
                    full_dcm_path = os.path.join(root, dcm_file)
                    patient_dcm_files[patient_folder].append({
                        'full_path': full_dcm_path,
                        'filename': dcm_file,
                        'source_folder': folder_full_path
                    })

                # Mark this specific folder as processed (not the whole patient)
                self.log_message(f"  Found {len(dcm_files)} .dcm files in: {rel_path}")

        return patient_dcm_files

    def copy_dicom_files(self):
        """Copy ONLY .dcm files - NO folders at all, just files directly in batch folders"""
        input_path = self.input_path.get()
        output_path = self.output_path.get()

        if not input_path or not output_path:
            messagebox.showerror("Error", "Please select both input and output paths")
            return False

        if not os.path.exists(input_path):
            messagebox.showerror("Error", "Input path does not exist")
            return False

        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create output directory: {str(e)}")
                return False

        # Find ALL .dcm files recursively
        self.log_message("🔍 Scanning ALL subfolders for DICOM files...")
        patient_dcm_files = self.find_all_dcm_files(input_path)

        if not patient_dcm_files:
            self.log_message("❌ No .dcm files found!")
            if self.skip_processed.get():
                self.log_message("💡 All folders may have been processed already. Try resetting the processed log.")
            return False

        # Convert to list of patients with their DICOM files
        patient_list = list(patient_dcm_files.items())
        total_patients = len(patient_list)
        self.log_message(f"✅ Found {total_patients} patient(s) with DICOM files")

        # Count total DICOM files
        total_dcm_files = sum(len(files) for files in patient_dcm_files.values())
        self.log_message(f"📄 Total .dcm files found: {total_dcm_files}")

        # Process in batches of 10 patients
        batch_size = 10
        total_batches = (total_patients + batch_size - 1) // batch_size

        self.log_message(f"📁 Will create {total_batches} batch folders (10 patients per batch)")

        total_files_copied = 0

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_patients)
            batch_patients = patient_list[start_idx:end_idx]

            # Create batch folder (1, 2, 3, etc.)
            batch_folder_name = str(batch_num + 1)
            batch_output_path = os.path.join(output_path, batch_folder_name)
            os.makedirs(batch_output_path, exist_ok=True)

            self.log_message(f"\n{'=' * 70}")
            self.log_message(f"📦 Processing Batch {batch_num + 1}/{total_batches} -> Folder: '{batch_folder_name}'")
            self.log_message(f"👥 Patients in this batch: {len(batch_patients)}")

            # Process each patient
            for patient_idx, (patient_name, dcm_files_list) in enumerate(batch_patients):
                self.log_message(f"\n  👤 Patient: {patient_name}")
                self.log_message(f"  📄 Found {len(dcm_files_list)} DICOM files for this patient")

                files_copied_in_patient = 0

                # Copy each .dcm file directly to batch folder (NO subfolders!)
                for dcm_info in dcm_files_list:
                    source_file = dcm_info['full_path']
                    original_filename = dcm_info['filename']

                    # Create a unique filename: patientName_originalFilename.dcm
                    # Remove any path separators from patient name
                    safe_patient_name = patient_name.replace(os.sep, '_').replace('/', '_').replace('\\', '_')
                    dest_filename = f"{safe_patient_name}_{original_filename}"
                    dest_file = os.path.join(batch_output_path, dest_filename)

                    # If file exists and overwrite is off, add counter
                    if os.path.exists(dest_file) and not self.overwrite_files.get():
                        name, ext = os.path.splitext(dest_filename)
                        counter = 1
                        while os.path.exists(os.path.join(batch_output_path, f"{name}_{counter}{ext}")):
                            counter += 1
                        dest_file = os.path.join(batch_output_path, f"{name}_{counter}{ext}")
                        dest_filename = f"{name}_{counter}{ext}"

                    try:
                        shutil.copy2(source_file, dest_file)
                        files_copied_in_patient += 1
                        total_files_copied += 1
                        self.log_message(f"    ✅ Copied: {dest_filename}")
                    except Exception as e:
                        self.log_message(f"    ❌ Error copying {original_filename}: {str(e)}")

                # Mark each source folder as processed
                unique_folders = set(dcm_info['source_folder'] for dcm_info in dcm_files_list)
                for folder in unique_folders:
                    self.save_processed_folder(folder)

                self.log_message(
                    f"  ✅ Copied {files_copied_in_patient}/{len(dcm_files_list)} .dcm files for patient: {patient_name}")

                # Update progress
                progress = ((batch_num * batch_size + patient_idx + 1) / total_patients) * 100
                self.progress_var.set(progress)
                self.root.update()

            self.log_message(f"\n✅ Batch {batch_num + 1} completed! {len(batch_patients)} patients processed")
            self.log_message(f"📁 Files saved in: {batch_output_path}")

        self.progress_var.set(100)
        self.log_message("\n" + "=" * 70)
        self.log_message("🎉🎉🎉 COPYING COMPLETED SUCCESSFULLY! 🎉🎉🎉")
        self.log_message(f"📊 Total patients processed: {total_patients}")
        self.log_message(f"📄 Total .dcm files copied: {total_files_copied}")
        self.log_message(f"📁 Output saved in: {output_path}")

        return True

    def start_copying(self):
        """Start the copying process in a separate thread"""
        self.start_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.clear_status()

        thread = threading.Thread(target=self.copying_thread)
        thread.daemon = True
        thread.start()

    def copying_thread(self):
        """Thread function for copying"""
        try:
            success = self.copy_dicom_files()
            if not success:
                self.log_message("❌ Copying failed!")
        except Exception as e:
            self.log_message(f"❌ Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            self.start_button.config(state=tk.NORMAL)


def main():
    root = tk.Tk()
    app = DICOMBatchCopier(root)
    root.mainloop()


if __name__ == "__main__":
    main()