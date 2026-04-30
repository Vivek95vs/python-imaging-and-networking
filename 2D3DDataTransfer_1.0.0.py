import os
import shutil
import hashlib
from pathlib import Path
import logging
from datetime import datetime
import time
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import socket


class DicomCopyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DICOM Folder Copy Utility - Local to Remote")
        self.root.geometry("850x750")
        self.root.resizable(True, True)

        # Variables
        self.source_path = tk.StringVar(value="D:\\PatientImages")
        self.dest_ip = tk.StringVar(value="192.168.10.210")
        self.dest_path = tk.StringVar(value="D\\PatientImages")
        self.dest_username = tk.StringVar(value="")
        self.dest_password = tk.StringVar(value="")
        self.use_credentials = tk.BooleanVar(value=False)

        self.copy_thread = None
        self.stop_copy = False
        self.progress_tracker = None
        self.network_drive_letter = "Z:"  # Default mapped drive letter

        # Style
        style = ttk.Style()
        style.theme_use('clam')

        self.setup_ui()

    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Title
        title_label = ttk.Label(main_frame, text="DICOM Folder Copy Utility",
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)

        # Source Section (Local)
        source_frame = ttk.LabelFrame(main_frame, text="Source (Local PC)", padding="10")
        source_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        source_frame.columnconfigure(1, weight=1)

        ttk.Label(source_frame, text="Source Path (local):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        source_entry = ttk.Entry(source_frame, textvariable=self.source_path, width=60)
        source_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(source_frame, text="Browse", command=self.browse_source).grid(row=0, column=2, padx=5)

        # Destination Section (Remote)
        dest_frame = ttk.LabelFrame(main_frame, text="Destination (Remote PC)", padding="10")
        dest_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        dest_frame.columnconfigure(1, weight=1)

        # Destination IP
        ttk.Label(dest_frame, text="Destination PC IP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(dest_frame, textvariable=self.dest_ip, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(dest_frame, text="e.g., 192.168.10.210").grid(row=0, column=2, sticky=tk.W, padx=5)

        # Destination Path
        ttk.Label(dest_frame, text="Destination Path (on remote):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(dest_frame, textvariable=self.dest_path, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5,
                                                                          pady=5)
        ttk.Label(dest_frame, text="Format: D\\PatientImages or SharedFolder\\PatientImages").grid(row=2, column=1,
                                                                                                    sticky=tk.W, padx=5)

        # Build full destination path display
        self.dest_full_label = ttk.Label(dest_frame, text="", foreground="blue")
        self.dest_full_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        self.update_dest_path_display()

        # Bind to update display when IP or path changes
        self.dest_ip.trace('w', lambda *args: self.update_dest_path_display())
        self.dest_path.trace('w', lambda *args: self.update_dest_path_display())

        # Network Credentials (Optional)
        cred_frame = ttk.Frame(dest_frame)
        cred_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.cred_check = ttk.Checkbutton(cred_frame, text="Use network credentials",
                                          variable=self.use_credentials,
                                          command=self.toggle_credentials)
        self.cred_check.grid(row=0, column=0, sticky=tk.W)

        # Credentials entry (initially disabled)
        self.cred_frame = ttk.Frame(dest_frame)
        self.cred_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(self.cred_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(self.cred_frame, textvariable=self.dest_username, width=30).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(self.cred_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, padx=5)
        pwd_entry = ttk.Entry(self.cred_frame, textvariable=self.dest_password, width=30, show="*")
        pwd_entry.grid(row=1, column=1, sticky=tk.W, padx=5)

        # Initially hide credentials
        self.cred_frame.grid_remove()

        # Connection buttons
        conn_frame = ttk.Frame(dest_frame)
        conn_frame.grid(row=6, column=0, columnspan=3, pady=10)

        self.test_conn_btn = ttk.Button(conn_frame, text="🔌 Test Connection",
                                        command=self.test_connection, width=20)
        self.test_conn_btn.grid(row=0, column=0, padx=5)

        self.map_drive_btn = ttk.Button(conn_frame, text="💻 Map Network Drive",
                                        command=self.map_network_drive, width=20)
        self.map_drive_btn.grid(row=0, column=1, padx=5)

        # Mapped drive letter selection
        drive_frame = ttk.Frame(dest_frame)
        drive_frame.grid(row=7, column=0, columnspan=3, pady=5)

        ttk.Label(drive_frame, text="Mapped Drive Letter:").grid(row=0, column=0, padx=5)
        self.drive_letter = tk.StringVar(value="Z:")
        drive_combo = ttk.Combobox(drive_frame, textvariable=self.drive_letter,
                                   values=['Z:', 'Y:', 'X:', 'W:', 'V:'], width=5)
        drive_combo.grid(row=0, column=1, padx=5)
        ttk.Label(drive_frame, text="(for mapped drive)").grid(row=0, column=2, padx=5)

        # Options Section
        options_frame = ttk.LabelFrame(main_frame, text="Copy Options", padding="10")
        options_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Verify files after copy (slower but safer)",
                        variable=self.verify_var).grid(row=0, column=0, sticky=tk.W)

        self.overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Overwrite existing files",
                        variable=self.overwrite_var).grid(row=1, column=0, sticky=tk.W)

        self.resume_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Resume interrupted transfer",
                        variable=self.resume_var).grid(row=2, column=0, sticky=tk.W)

        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.preview_btn = ttk.Button(button_frame, text="🔍 Preview",
                                      command=self.preview_copy, width=15)
        self.preview_btn.grid(row=0, column=0, padx=5)

        self.start_btn = ttk.Button(button_frame, text="▶ Start Copy",
                                    command=self.start_copy, width=15)
        self.start_btn.grid(row=0, column=1, padx=5)

        self.stop_btn = ttk.Button(button_frame, text="⏹ Stop",
                                   command=self.stop_copy_process, width=15, state='disabled')
        self.stop_btn.grid(row=0, column=2, padx=5)

        self.scan_btn = ttk.Button(button_frame, text="📊 Quick Scan",
                                   command=self.quick_scan, width=15)
        self.scan_btn.grid(row=0, column=3, padx=5)

        # Progress Section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(1, weight=1)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

        # Status label
        self.status_label = ttk.Label(progress_frame, text="Ready", font=('Arial', 10))
        self.status_label.grid(row=1, column=0, sticky=tk.W, pady=2)

        # Log text area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=80, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure log text tags for colors
        self.log_text.tag_configure('info', foreground='black')
        self.log_text.tag_configure('success', foreground='green')
        self.log_text.tag_configure('warning', foreground='orange')
        self.log_text.tag_configure('error', foreground='red')
        self.log_text.tag_configure('header', foreground='blue', font=('Arial', 10, 'bold'))

        # Configure grid weights for main_frame
        main_frame.rowconfigure(6, weight=1)

    def toggle_credentials(self):
        """Show/hide credentials entry"""
        if self.use_credentials.get():
            self.cred_frame.grid()
        else:
            self.cred_frame.grid_remove()

    def update_dest_path_display(self):
        """Update the displayed full destination path"""
        ip = self.dest_ip.get().strip()
        path = self.dest_path.get().strip()
        if ip and path:
            full_path = f"\\\\{ip}\\{path}"
            self.dest_full_label.config(text=f"Full Destination Path: {full_path}")
        else:
            self.dest_full_label.config(text="")

    def get_full_dest_path(self):
        """Get the complete destination path (UNC format)"""
        ip = self.dest_ip.get().strip()
        path = self.dest_path.get().strip()
        if ip and path:
            return f"\\\\{ip}\\{path}"
        return None

    def browse_source(self):
        """Browse for source folder (local)"""
        path = filedialog.askdirectory(title="Select Source Folder (Local)")
        if path:
            self.source_path.set(path)
            self.log(f"Source set to: {path}", 'info')

    def log(self, message, tag='info'):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def test_connection(self):
        """Test connection to destination PC"""
        ip = self.dest_ip.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter destination IP address")
            return

        self.log("Testing connection...", 'info')
        self.test_conn_btn.config(state='disabled', text="Testing...")

        def test():
            try:
                # Test network connectivity
                socket.gethostbyname(ip)
                self.root.after(0, lambda: self.log(f"✅ Network connectivity to {ip} OK", 'success'))

                # Test SMB share access
                dest_path = self.get_full_dest_path()
                if dest_path:
                    try:
                        if os.path.exists(dest_path):
                            self.root.after(0, lambda: self.log(f"✅ Successfully accessed {dest_path}", 'success'))
                            self.root.after(0, lambda: messagebox.showinfo("Success", f"Connected to {dest_path}"))
                        else:
                            self.root.after(0, lambda: self.log(f"⚠️ Path exists but cannot access: {dest_path}",
                                                                'warning'))
                            self.root.after(0, lambda: messagebox.showwarning("Warning",
                                                                              f"Path exists but may need credentials\nTry mapping network drive"))
                    except Exception as e:
                        self.root.after(0, lambda: self.log(f"❌ Cannot access share: {str(e)}", 'error'))
                        self.root.after(0, lambda: messagebox.showerror("Access Error",
                                                                        f"Cannot access {dest_path}\n\nTry mapping network drive with credentials"))

            except Exception as e:
                self.root.after(0, lambda: self.log(f"❌ Connection failed: {str(e)}", 'error'))
                self.root.after(0, lambda: messagebox.showerror("Connection Failed", str(e)))
            finally:
                self.root.after(0, lambda: self.test_conn_btn.config(state='normal', text="🔌 Test Connection"))

        threading.Thread(target=test, daemon=True).start()

    def map_network_drive(self):
        """Map a network drive to the destination"""
        ip = self.dest_ip.get().strip()
        path = self.dest_path.get().strip()

        if not ip or not path:
            messagebox.showerror("Error", "Please enter destination IP and path")
            return

        drive = self.drive_letter.get()
        unc_path = f"\\\\{ip}\\{path}"

        self.log(f"Mapping {drive} to {unc_path}...", 'info')

        def map_drive():
            try:
                # First, check if drive is already mapped
                import subprocess

                # Unmount if already exists
                subprocess.run(f'net use {drive} /delete /y', shell=True, capture_output=True)

                # Map with or without credentials
                if self.use_credentials.get():
                    username = self.dest_username.get().strip()
                    password = self.dest_password.get().strip()

                    if username and password:
                        cmd = f'net use {drive} {unc_path} /user:{username} {password} /persistent:yes'
                    else:
                        cmd = f'net use {drive} {unc_path} /persistent:yes'
                else:
                    cmd = f'net use {drive} {unc_path} /persistent:yes'

                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                if result.returncode == 0:
                    self.root.after(0, lambda: self.log(f"✅ Successfully mapped {drive} to {unc_path}", 'success'))
                    self.root.after(0, lambda: messagebox.showinfo("Success",
                                                                   f"Drive {drive} mapped successfully!\n\nYou can now use {drive} as destination path."))

                    # Update destination path to use mapped drive
                    mapped_path = str(Path(drive) / Path(path).name)
                    self.root.after(0, lambda: self.dest_path.set(mapped_path))
                else:
                    error_msg = result.stderr or "Unknown error"
                    self.root.after(0, lambda: self.log(f"❌ Map failed: {error_msg}", 'error'))
                    self.root.after(0, lambda: messagebox.showerror("Map Failed", error_msg))

            except Exception as e:
                self.root.after(0, lambda: self.log(f"❌ Error mapping drive: {str(e)}", 'error'))

        threading.Thread(target=map_drive, daemon=True).start()

    def find_dicom_folders(self, source_base_path):
        """Find all DICOM folders in the source directory"""
        source_base = Path(source_base_path)
        dicom_folders = []

        self.log(f"Scanning for DICOM folders in: {source_base}")

        total_folders = 0
        for root, dirs, files in os.walk(source_base):
            current_path = Path(root)

            if current_path.name == "DICOM" and files:
                # Calculate total size
                total_size = 0
                for f in files:
                    try:
                        file_path = os.path.join(root, f)
                        if os.path.isfile(file_path):
                            total_size += os.path.getsize(file_path)
                    except:
                        pass

                rel_path = current_path.relative_to(source_base)
                dicom_folders.append({
                    'source_path': current_path,
                    'relative_path': rel_path,
                    'file_count': len(files),
                    'total_size': total_size,
                    'files': files
                })
                total_folders += 1
                if total_folders % 10 == 0:
                    self.log(f"Found {total_folders} DICOM folders so far...")

        self.log(f"Total DICOM folders found: {len(dicom_folders)}")
        return dicom_folders

    def get_file_size_str(self, size_bytes):
        """Convert file size to human readable format"""
        if size_bytes == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def quick_scan(self):
        """Quick scan to see what will be copied"""
        source = self.source_path.get().strip()

        if not source:
            messagebox.showerror("Error", "Please enter source path")
            return

        if not os.path.exists(source):
            messagebox.showerror("Error", f"Source path does not exist: {source}")
            return

        self.log("\n" + "=" * 50, 'header')
        self.log("QUICK SCAN STARTED", 'header')
        self.log("=" * 50, 'header')

        def scan():
            try:
                dicom_folders = self.find_dicom_folders(source)

                if dicom_folders:
                    total_files = sum(f['file_count'] for f in dicom_folders)
                    total_size = sum(f['total_size'] for f in dicom_folders)

                    self.root.after(0, lambda: self.log(f"\n📊 Scan Results:", 'header'))
                    self.root.after(0, lambda: self.log(f"   Total DICOM folders: {len(dicom_folders)}", 'info'))
                    self.root.after(0, lambda: self.log(f"   Total files: {total_files}", 'info'))
                    self.root.after(0, lambda: self.log(f"   Total size: {self.get_file_size_str(total_size)}", 'info'))

                    # Show sample
                    self.root.after(0, lambda: self.log(f"\n📁 Sample folders (first 5):", 'header'))
                    for folder in dicom_folders[:5]:
                        rel_path = str(folder['relative_path'])
                        self.root.after(0, lambda f=folder, r=rel_path: self.log(
                            f"   • {r}\n     Files: {f['file_count']}, Size: {self.get_file_size_str(f['total_size'])}",
                            'info'))
                else:
                    self.root.after(0, lambda: self.log("No DICOM folders found", 'warning'))

            except Exception as e:
                self.root.after(0, lambda: self.log(f"Scan error: {str(e)}", 'error'))

        threading.Thread(target=scan, daemon=True).start()

    def preview_copy(self):
        """Preview what will be copied"""
        source = self.source_path.get().strip()
        dest = self.get_full_dest_path()

        if not source or not dest:
            messagebox.showerror("Error", "Please enter source and destination paths")
            return

        if not os.path.exists(source):
            messagebox.showerror("Error", f"Source path does not exist: {source}")
            return

        self.log("\n" + "=" * 50, 'header')
        self.log("PREVIEW MODE", 'header')
        self.log("=" * 50, 'header')

        def preview():
            try:
                dicom_folders = self.find_dicom_folders(source)

                if dicom_folders:
                    total_files = sum(f['file_count'] for f in dicom_folders)
                    total_size = sum(f['total_size'] for f in dicom_folders)

                    self.root.after(0, lambda: self.log(f"\n📋 Preview Summary:", 'header'))
                    self.root.after(0, lambda: self.log(f"   Source: {source}", 'info'))
                    self.root.after(0, lambda: self.log(f"   Destination: {dest}", 'info'))
                    self.root.after(0, lambda: self.log(f"   Folders to copy: {len(dicom_folders)}", 'info'))
                    self.root.after(0, lambda: self.log(f"   Files to copy: {total_files}", 'info'))
                    self.root.after(0, lambda: self.log(f"   Total size: {self.get_file_size_str(total_size)}", 'info'))

                    # Check if destination is accessible
                    try:
                        if os.path.exists(dest):
                            # Check destination space
                            dest_free = shutil.disk_usage(dest).free
                            self.root.after(0, lambda: self.log(
                                f"   Destination free space: {self.get_file_size_str(dest_free)}", 'info'))

                            if dest_free < total_size:
                                self.root.after(0, lambda: self.log(
                                    f"⚠️ WARNING: Destination may have insufficient space!", 'warning'))
                        else:
                            self.root.after(0, lambda: self.log(
                                f"ℹ️ Destination path doesn't exist yet (will be created)", 'info'))
                    except Exception as e:
                        self.root.after(0, lambda: self.log(
                            f"⚠️ Cannot access destination: {str(e)}", 'warning'))
                        self.root.after(0, lambda: self.log(
                            f"   You may need to map network drive first", 'warning'))
                else:
                    self.root.after(0, lambda: self.log("No DICOM folders found to copy", 'warning'))

            except Exception as e:
                self.root.after(0, lambda: self.log(f"Preview error: {str(e)}", 'error'))

        threading.Thread(target=preview, daemon=True).start()

    def start_copy(self):
        """Start the copy process"""
        source = self.source_path.get().strip()
        dest = self.get_full_dest_path()

        if not source or not dest:
            messagebox.showerror("Error", "Please enter source and destination paths")
            return

        if not os.path.exists(source):
            messagebox.showerror("Error", f"Source path does not exist: {source}")
            return

        # Check if destination is accessible
        try:
            # Try to create destination directory if it doesn't exist
            Path(dest).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            response = messagebox.askyesno("Destination Warning",
                                           f"Cannot access destination: {dest}\n\nError: {str(e)}\n\nDo you want to try mapping a network drive first?")
            if response:
                self.map_network_drive()
            return

        # Confirm with user
        if not messagebox.askyesno("Confirm", "Start copy operation?"):
            return

        # Disable buttons during copy
        self.preview_btn.config(state='disabled')
        self.start_btn.config(state='disabled')
        self.scan_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.stop_copy = False

        self.log("\n" + "=" * 50, 'header')
        self.log("COPY OPERATION STARTED", 'header')
        self.log("=" * 50, 'header')
        self.log(f"Source: {source}", 'info')
        self.log(f"Destination: {dest}", 'info')
        self.log(f"Verify: {self.verify_var.get()}", 'info')
        self.log(f"Overwrite: {self.overwrite_var.get()}", 'info')
        self.log(f"Resume: {self.resume_var.get()}", 'info')

        # Start copy in separate thread
        self.copy_thread = threading.Thread(target=self.perform_copy,
                                            args=(source, dest),
                                            daemon=True)
        self.copy_thread.start()

    def perform_copy(self, source, dest):
        """Perform the actual copy operation"""
        try:
            # Initialize progress tracker for resume
            if self.resume_var.get():
                self.progress_tracker = CopyProgress(self)

            # Find all DICOM folders
            self.root.after(0, lambda: self.log("Scanning for DICOM folders...", 'info'))
            dicom_folders = self.find_dicom_folders(source)

            if not dicom_folders:
                self.root.after(0, lambda: self.log("No DICOM folders found!", 'warning'))
                return

            total_folders = len(dicom_folders)
            total_files = sum(f['file_count'] for f in dicom_folders)
            total_size = sum(f['total_size'] for f in dicom_folders)

            self.root.after(0, lambda: self.log(f"\nFound {total_folders} folders, {total_files} files, "
                                                f"{self.get_file_size_str(total_size)} total", 'info'))

            # Copy each folder
            copied_files = 0
            failed_files = 0
            start_time = time.time()

            for idx, folder in enumerate(dicom_folders, 1):
                if self.stop_copy:
                    self.root.after(0, lambda: self.log("Copy stopped by user", 'warning'))
                    break

                # Update progress bar
                progress = (idx / total_folders) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))

                rel_path = str(folder['relative_path'])
                self.root.after(0, lambda i=idx, t=total_folders, r=rel_path: self.log(
                    f"\n📁 [{i}/{t}] Copying: {r}", 'header'))

                stats = self.copy_folder(folder, dest, start_time)
                copied_files += stats['copied']
                failed_files += stats['failed']

                # Update status
                self.root.after(0, lambda c=copied_files, t=total_files, f=failed_files:
                self.status_label.config(text=f"Copied: {c}/{t} files, Failed: {f}"))

            # Complete
            elapsed = time.time() - start_time
            self.root.after(0, lambda: self.log(
                f"\n✅ Copy completed in {elapsed / 60:.1f} minutes", 'success'))
            self.root.after(0, lambda: self.log(
                f"Files copied: {copied_files}, Failed: {failed_files}", 'info'))

            # Clear progress state on successful completion
            if self.progress_tracker:
                self.progress_tracker.clear_state()

        except Exception as e:
            self.root.after(0, lambda: self.log(f"Copy error: {str(e)}", 'error'))
        finally:
            # Re-enable buttons
            self.root.after(0, lambda: self.preview_btn.config(state='normal'))
            self.root.after(0, lambda: self.start_btn.config(state='normal'))
            self.root.after(0, lambda: self.scan_btn.config(state='normal'))
            self.root.after(0, lambda: self.stop_btn.config(state='disabled'))
            self.root.after(0, lambda: self.progress_var.set(0))

    def copy_folder(self, folder_info, dest_base_path, start_time):
        """Copy a single folder"""
        source_path = folder_info['source_path']
        relative_path = folder_info['relative_path']
        dest_path = Path(dest_base_path) / relative_path

        # Create destination directory
        try:
            dest_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ Cannot create destination directory: {str(e)}", 'error'))
            return {'copied': 0, 'failed': 0, 'skipped': 0}

        source_files = list(source_path.glob("*"))
        copied = 0
        failed = 0
        skipped = 0

        for idx, source_file in enumerate(source_files, 1):
            if self.stop_copy:
                break

            if not source_file.is_file():
                continue

            dest_file = dest_path / source_file.name
            file_key = str(source_file.relative_to(source_path))

            # Check if already copied (for resume)
            if self.progress_tracker and self.progress_tracker.is_copied(file_key):
                self.root.after(0, lambda f=source_file: self.log(
                    f"   ⏭ Already copied: {f.name}", 'info'))
                copied += 1
                continue

            # Check if exists and not overwrite
            if dest_file.exists() and not self.overwrite_var.get():
                self.root.after(0, lambda f=source_file: self.log(
                    f"   ⚠ Skipping (exists): {f.name}", 'warning'))
                skipped += 1
                continue

            # Copy file
            try:
                file_size = source_file.stat().st_size
                self.root.after(0, lambda f=source_file, s=file_size: self.log(
                    f"   Copying: {f.name} ({self.get_file_size_str(s)})", 'info'))

                shutil.copy2(source_file, dest_file)
                copied += 1

                # Verify if requested
                if self.verify_var.get():
                    if self.verify_file(source_file, dest_file):
                        self.root.after(0, lambda f=source_file: self.log(
                            f"     ✅ Verified: {f.name}", 'success'))
                    else:
                        self.root.after(0, lambda f=source_file: self.log(
                            f"     ❌ Verification failed: {f.name}", 'error'))
                        try:
                            dest_file.unlink()
                        except:
                            pass
                        failed += 1
                        copied -= 1

                # Mark as copied
                if self.progress_tracker:
                    self.progress_tracker.mark_copied(file_key)

            except Exception as e:
                self.root.after(0, lambda f=source_file, e=e: self.log(
                    f"   ❌ Failed: {f.name} - {str(e)}", 'error'))
                failed += 1

        return {'copied': copied, 'failed': failed, 'skipped': skipped}

    def verify_file(self, source_file, dest_file):
        """Verify file integrity"""
        try:
            if not dest_file.exists():
                return False

            source_hash = hashlib.md5()
            dest_hash = hashlib.md5()

            with open(source_file, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    source_hash.update(chunk)

            with open(dest_file, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    dest_hash.update(chunk)

            return source_hash.hexdigest() == dest_hash.hexdigest()
        except:
            return False

    def stop_copy_process(self):
        """Stop the copy process"""
        self.stop_copy = True
        self.log("Stopping copy process...", 'warning')
        self.stop_btn.config(state='disabled')


class CopyProgress:
    """Track copy progress for resume capability"""

    def __init__(self, gui):
        self.gui = gui
        self.state_file = "copy_state.json"
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                return {'copied_files': []}
        return {'copied_files': []}

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def is_copied(self, file_path):
        return file_path in self.state.get('copied_files', [])

    def mark_copied(self, file_path):
        if 'copied_files' not in self.state:
            self.state['copied_files'] = []
        if file_path not in self.state['copied_files']:
            self.state['copied_files'].append(file_path)
            self.save_state()

    def clear_state(self):
        self.state = {'copied_files': []}
        if os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
            except:
                pass


def main():
    root = tk.Tk()
    app = DicomCopyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()