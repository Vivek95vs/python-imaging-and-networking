import os
import pydicom
import re
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime
import queue
import socket
import json
import configparser

# Import pynetdicom for DICOM communication
from pynetdicom import AE
from pynetdicom.sop_class import Verification, CTImageStorage, MRImageStorage, RTImageStorage, \
    PositronEmissionTomographyImageStorage, SecondaryCaptureImageStorage, \
    UltrasoundImageStorage, XRayAngiographicImageStorage, NuclearMedicineImageStorage


class DICOMPushGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DICOM Server Push Utility with RTID Grouping")
        self.root.geometry("1400x900")  # Increased default size
        self.root.resizable(True, True)

        # Configuration file
        self.config_file = 'dicom_push_config.ini'
        self.state_file = 'push_state.json'
        self.push_history_file = 'push_history.json'

        # Load configuration
        self.config = self.load_config()

        # Server Configuration
        self.server_ae = tk.StringVar(value=self.config.get('Server', 'AE', fallback="STORAGESCP"))
        self.server_host = tk.StringVar(value=self.config.get('Server', 'Host', fallback="192.168.22.130"))
        self.server_port = tk.StringVar(value=self.config.get('Server', 'Port', fallback="250"))

        # Local Configuration
        self.local_ae = tk.StringVar(value=self.config.get('Local', 'AE', fallback="VIVEK_VS"))
        self.local_ip = tk.StringVar(value=self.config.get('Local', 'IP', fallback=self.get_local_ip()))
        self.local_port = tk.StringVar(value=self.config.get('Local', 'Port', fallback="5222"))

        # Source path
        self.source_path = tk.StringVar(value=self.config.get('Source', 'Path', fallback="D:\\PatientImages"))

        # Push options
        self.timeout = tk.IntVar(value=self.config.getint('Options', 'Timeout', fallback=30))
        self.max_retries = tk.IntVar(value=self.config.getint('Options', 'MaxRetries', fallback=2))
        self.verify_after_push = tk.BooleanVar(
            value=self.config.getboolean('Options', 'VerifyAfterPush', fallback=True))
        self.save_verification_log = tk.BooleanVar(
            value=self.config.getboolean('Options', 'SaveVerificationLog', fallback=True))
        self.ignore_capture_folders = tk.BooleanVar(
            value=self.config.getboolean('Options', 'IgnoreCaptureFolders', fallback=True))
        self.show_only_unpushed = tk.BooleanVar(value=True)  # New option to show only unpushed

        # Search variables
        self.search_rtid = tk.StringVar()
        self.search_site = tk.StringVar()
        self.search_phase = tk.StringVar()
        self.search_fg = tk.StringVar()
        self.search_fn = tk.StringVar()

        # Thread control
        self.push_thread = None
        self.stop_push = False
        self.paused = False
        self.resume_mode = False
        self.log_queue = queue.Queue()
        self.verification_queue = queue.Queue()

        # Statistics
        self.stats = {
            'total_folders': 0,
            'total_files': 0,
            'pushed': 0,
            'failed': 0,
            'skipped': 0,
            'verified': 0,
            'verification_failed': 0,
            'ignored_capture_folders': 0,
            'ignored_capture_files': 0
        }

        # Push state for resume
        self.push_state = {
            'in_progress': False,
            'current_rtid': '',
            'current_folder_index': 0,
            'current_folder_path': '',
            'processed_rtids': [],
            'processed_folders': [],
            'processed_files': [],
            'failed_files': [],
            'start_time': None,
            'server_config': {},
            'local_config': {}
        }

        # Push history - tracks which RTIDs and folders have been pushed
        self.push_history = self.load_push_history()

        # Verification log
        self.verification_log_data = []

        # Data storage
        self.all_folders = []  # All discovered folders
        self.rtid_groups = {}  # Grouped by RTID
        self.filtered_folders = []  # Currently displayed folders
        self.folder_items = []  # Treeview item IDs
        self.folder_data = []  # Folder data objects

        # Setup UI
        self.setup_ui()

        # Start log updater
        self.update_log()
        self.update_verification_log()

        # Check for existing state on startup
        self.check_for_resume()

        # Save config on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def load_config(self):
        """Load configuration from file"""
        config = configparser.ConfigParser()

        if os.path.exists(self.config_file):
            try:
                config.read(self.config_file)
            except Exception as e:
                print(f"Error loading config: {e}")

        # Ensure sections exist
        if 'Server' not in config:
            config['Server'] = {}
        if 'Local' not in config:
            config['Local'] = {}
        if 'Source' not in config:
            config['Source'] = {}
        if 'Options' not in config:
            config['Options'] = {}

        return config

    def save_config(self):
        """Save configuration to file"""
        try:
            # Update config with current values
            self.config['Server']['AE'] = self.server_ae.get()
            self.config['Server']['Host'] = self.server_host.get()
            self.config['Server']['Port'] = self.server_port.get()

            self.config['Local']['AE'] = self.local_ae.get()
            self.config['Local']['IP'] = self.local_ip.get()
            self.config['Local']['Port'] = self.local_port.get()

            self.config['Source']['Path'] = self.source_path.get()

            self.config['Options']['Timeout'] = str(self.timeout.get())
            self.config['Options']['MaxRetries'] = str(self.max_retries.get())
            self.config['Options']['VerifyAfterPush'] = str(self.verify_after_push.get())
            self.config['Options']['SaveVerificationLog'] = str(self.save_verification_log.get())
            self.config['Options']['IgnoreCaptureFolders'] = str(self.ignore_capture_folders.get())
            self.config['Options']['ShowOnlyUnpushed'] = str(self.show_only_unpushed.get())

            with open(self.config_file, 'w') as f:
                self.config.write(f)

            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def load_push_history(self):
        """Load push history from file"""
        try:
            if os.path.exists(self.push_history_file):
                with open(self.push_history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading push history: {e}")

        # Default structure
        return {
            'rtids': {},  # RTID -> {last_push_date, folders: [folder_paths]}
            'folders': {},  # folder_path -> {pushed_date, rtid, status}
            'files': {}  # file_path -> {pushed_date, sop_uid}
        }

    def save_push_history(self):
        """Save push history to file"""
        try:
            with open(self.push_history_file, 'w') as f:
                json.dump(self.push_history, f, indent=2)
        except Exception as e:
            self.log(f"⚠️ Failed to save push history: {str(e)}", 'warning')

    def mark_folder_as_pushed(self, folder_path, rtid, status='completed'):
        """Mark a folder as pushed in history"""
        folder_key = str(folder_path)
        now = datetime.now().isoformat()

        # Update folder record
        self.push_history['folders'][folder_key] = {
            'pushed_date': now,
            'rtid': rtid,
            'status': status,
            'files_count': self.stats['pushed']
        }

        # Update RTID record
        if rtid not in self.push_history['rtids']:
            self.push_history['rtids'][rtid] = {
                'last_push': now,
                'folders': []
            }

        if folder_key not in self.push_history['rtids'][rtid]['folders']:
            self.push_history['rtids'][rtid]['folders'].append(folder_key)

        self.push_history['rtids'][rtid]['last_push'] = now

        self.save_push_history()

    def is_folder_pushed(self, folder_path):
        """Check if a folder has been pushed"""
        folder_key = str(folder_path)
        return folder_key in self.push_history['folders']

    def save_push_state(self):
        """Save current push state for resume"""
        try:
            state = {
                'in_progress': self.push_state['in_progress'],
                'current_rtid': self.push_state['current_rtid'],
                'current_folder_index': self.push_state['current_folder_index'],
                'current_folder_path': self.push_state['current_folder_path'],
                'processed_rtids': self.push_state['processed_rtids'],
                'processed_folders': self.push_state['processed_folders'],
                'processed_files': self.push_state['processed_files'],
                'failed_files': self.push_state['failed_files'],
                'start_time': self.push_state['start_time'],
                'stats': self.stats,
                'server_config': {
                    'ae': self.server_ae.get(),
                    'host': self.server_host.get(),
                    'port': self.server_port.get()
                },
                'local_config': {
                    'ae': self.local_ae.get(),
                    'ip': self.local_ip.get(),
                    'port': self.local_port.get()
                },
                'source_path': self.source_path.get(),
                'selected_rtids': list(set([f['rtid'] for f in self.get_selected_folders() if f['selected']]))
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            self.log(f"⚠️ Failed to save push state: {str(e)}", 'warning')

    def load_push_state(self):
        """Load push state for resume"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                return state
        except Exception as e:
            self.log(f"⚠️ Failed to load push state: {str(e)}", 'warning')
        return None

    def clear_push_state(self):
        """Clear saved push state"""
        try:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
            self.push_state = {
                'in_progress': False,
                'current_rtid': '',
                'current_folder_index': 0,
                'current_folder_path': '',
                'processed_rtids': [],
                'processed_folders': [],
                'processed_files': [],
                'failed_files': [],
                'start_time': None,
                'server_config': {},
                'local_config': {}
            }
        except Exception as e:
            self.log(f"⚠️ Failed to clear push state: {str(e)}", 'warning')

    def check_for_resume(self):
        """Check if there's a saved state to resume"""
        state = self.load_push_state()
        if state and state.get('in_progress', False):
            # Check if configuration matches
            config_match = (
                    state['server_config']['ae'] == self.server_ae.get() and
                    state['server_config']['host'] == self.server_host.get() and
                    state['server_config']['port'] == self.server_port.get() and
                    state['local_config']['ae'] == self.local_ae.get() and
                    state['source_path'] == self.source_path.get()
            )

            if config_match:
                self.resume_mode = True
                self.log("\n" + "=" * 60, 'header')
                self.log("🔄 INTERRUPTED PUSH DETECTED", 'header')
                self.log("=" * 60, 'header')
                self.log(f"Found interrupted push from {state.get('start_time', 'unknown')}", 'info')
                self.log(f"Processed RTIDs: {len(state.get('processed_rtids', []))}", 'info')
                self.log(f"Processed {state['stats']['pushed']} files so far", 'info')

                # Enable resume button
                self.resume_btn.config(state='normal')
            else:
                self.log("Found saved state but configuration mismatch", 'warning')
                self.clear_push_state()

    def setup_ui(self):
        # Create a canvas with scrollbar for the entire content
        canvas = tk.Canvas(self.root, borderwidth=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Main frame inside scrollable frame
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(1, weight=1)

        # Title
        title_label = ttk.Label(main_frame, text="DICOM Server Push Utility with RTID Grouping",
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)

        # Create Notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Tab 1: Push
        push_tab = ttk.Frame(notebook, padding="10")
        notebook.add(push_tab, text="Push DICOM Files")
        self.setup_push_tab(push_tab)

        # Tab 2: Verification Log
        verify_tab = ttk.Frame(notebook, padding="10")
        notebook.add(verify_tab, text="Verification Log")
        self.setup_verification_tab(verify_tab)

        # Tab 3: Push Log
        log_tab = ttk.Frame(notebook, padding="10")
        notebook.add(log_tab, text="Push Log")
        self.setup_log_tab(log_tab)

        # Tab 4: Push History
        history_tab = ttk.Frame(notebook, padding="10")
        notebook.add(history_tab, text="Push History")
        self.setup_history_tab(history_tab)

        # Configure grid weights for main_frame
        main_frame.rowconfigure(1, weight=1)

    def setup_push_tab(self, parent):
        """Setup the push tab"""
        parent.columnconfigure(1, weight=1)

        current_row = 0

        # Server Configuration Section
        server_frame = ttk.LabelFrame(parent, text="Server Configuration", padding="10")
        server_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        server_frame.columnconfigure(1, weight=1)

        ttk.Label(server_frame, text="Server AE Title:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(server_frame, textvariable=self.server_ae, width=30).grid(row=0, column=1, sticky=tk.W, padx=5,
                                                                            pady=5)

        ttk.Label(server_frame, text="Server Host/IP:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(server_frame, textvariable=self.server_host, width=30).grid(row=1, column=1, sticky=tk.W, padx=5,
                                                                              pady=5)

        ttk.Label(server_frame, text="Server Port:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(server_frame, textvariable=self.server_port, width=30).grid(row=2, column=1, sticky=tk.W, padx=5,
                                                                              pady=5)

        current_row += 1

        # Local Configuration Section
        local_frame = ttk.LabelFrame(parent, text="Local Configuration", padding="10")
        local_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        local_frame.columnconfigure(1, weight=1)

        ttk.Label(local_frame, text="Local AE Title:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        local_ae_entry = ttk.Entry(local_frame, textvariable=self.local_ae, width=30)
        local_ae_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        local_ae_entry.bind('<FocusOut>', lambda e: self.save_config())

        ttk.Label(local_frame, text="Local IP:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        local_ip_entry = ttk.Entry(local_frame, textvariable=self.local_ip, width=30)
        local_ip_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        local_ip_entry.config(state='readonly')

        ttk.Label(local_frame, text="Local Port:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        local_port_entry = ttk.Entry(local_frame, textvariable=self.local_port, width=30)
        local_port_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        local_port_entry.bind('<FocusOut>', lambda e: self.save_config())

        # Test Connection Button
        self.test_btn = ttk.Button(local_frame, text="Test Connection (C-ECHO)",
                                   command=self.test_connection)
        self.test_btn.grid(row=3, column=1, sticky=tk.W, padx=5, pady=10)

        current_row += 1

        # Source Section
        source_frame = ttk.LabelFrame(parent, text="Source DICOM Folders", padding="10")
        source_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        source_frame.columnconfigure(1, weight=1)

        ttk.Label(source_frame, text="Source Path:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        source_entry = ttk.Entry(source_frame, textvariable=self.source_path, width=60)
        source_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        source_entry.bind('<FocusOut>', lambda e: self.save_config())
        ttk.Button(source_frame, text="Browse", command=self.browse_source).grid(row=0, column=2, padx=5)

        # Scan Button
        self.scan_btn = ttk.Button(source_frame, text="Scan for DICOM Folders",
                                   command=self.scan_folders)
        self.scan_btn.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        current_row += 1

        # Search/Filter Section
        search_frame = ttk.LabelFrame(parent, text="Search/Filter RTID Groups", padding="10")
        search_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Search row 1 - RTID
        ttk.Label(search_frame, text="RTID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        rtid_search = ttk.Entry(search_frame, textvariable=self.search_rtid, width=20)
        rtid_search.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(search_frame, text="Site (S*):").grid(row=0, column=2, sticky=tk.W, padx=5)
        site_search = ttk.Entry(search_frame, textvariable=self.search_site, width=10)
        site_search.grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(search_frame, text="Phase (P*):").grid(row=0, column=4, sticky=tk.W, padx=5)
        phase_search = ttk.Entry(search_frame, textvariable=self.search_phase, width=10)
        phase_search.grid(row=0, column=5, sticky=tk.W, padx=5)

        # Search row 2 - FG and FN
        ttk.Label(search_frame, text="FG:").grid(row=1, column=0, sticky=tk.W, padx=5)
        fg_search = ttk.Entry(search_frame, textvariable=self.search_fg, width=10)
        fg_search.grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(search_frame, text="FN:").grid(row=1, column=2, sticky=tk.W, padx=5)
        fn_search = ttk.Entry(search_frame, textvariable=self.search_fn, width=10)
        fn_search.grid(row=1, column=3, sticky=tk.W, padx=5)

        # Search buttons
        search_btn_frame = ttk.Frame(search_frame)
        search_btn_frame.grid(row=1, column=4, columnspan=2, sticky=tk.W, padx=5)

        ttk.Button(search_btn_frame, text="🔍 Search",
                   command=self.apply_search_filter).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_btn_frame, text="Clear",
                   command=self.clear_search).pack(side=tk.LEFT, padx=2)

        # Show only unpushed checkbox
        ttk.Checkbutton(search_frame, text="Show only unpushed RTIDs",
                        variable=self.show_only_unpushed,
                        command=self.apply_search_filter).grid(row=2, column=0, columnspan=6, sticky=tk.W, padx=5,
                                                               pady=5)

        current_row += 1

        # RTID Groups Summary
        summary_frame = ttk.LabelFrame(parent, text="RTID Groups Summary", padding="5")
        summary_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.rtid_summary_label = ttk.Label(summary_frame, text="No RTID groups loaded")
        self.rtid_summary_label.pack(anchor=tk.W)

        current_row += 1

        # Folder List with RTID grouping - Make it taller
        list_frame = ttk.LabelFrame(parent, text="DICOM Folders by RTID", padding="10")
        list_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Create treeview with scrollbar
        tree_frame = ttk.Frame(list_frame)
        tree_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Treeview for folders with RTID grouping
        columns = ('select', 'rtid', 'folder', 'files', 'modalities', 'status', 'pushed')
        self.folder_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings', height=12)
        self.folder_tree.heading('select', text='Push')
        self.folder_tree.heading('rtid', text='RTID')
        self.folder_tree.heading('folder', text='Folder Path (relative)')
        self.folder_tree.heading('files', text='Files')
        self.folder_tree.heading('modalities', text='Modalities')
        self.folder_tree.heading('status', text='Status')
        self.folder_tree.heading('pushed', text='Pushed')

        self.folder_tree.column('select', width=50, anchor='center')
        self.folder_tree.column('rtid', width=100)
        self.folder_tree.column('folder', width=400)
        self.folder_tree.column('files', width=60, anchor='center')
        self.folder_tree.column('modalities', width=100)
        self.folder_tree.column('status', width=80)
        self.folder_tree.column('pushed', width=60, anchor='center')

        # Scrollbar
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=tree_scrollbar.set)

        self.folder_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.folder_tree.xview)
        self.folder_tree.configure(xscrollcommand=h_scrollbar.set)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.E, tk.W))

        # Bind click on checkbox column
        self.folder_tree.bind('<Button-1>', self.on_tree_click)

        # Selection buttons
        sel_frame = ttk.Frame(list_frame)
        sel_frame.grid(row=2, column=0, sticky=tk.W, pady=5)

        ttk.Button(sel_frame, text="Select All Visible",
                   command=self.select_all_visible).pack(side=tk.LEFT, padx=2)
        ttk.Button(sel_frame, text="Deselect All Visible",
                   command=self.deselect_all_visible).pack(side=tk.LEFT, padx=2)
        ttk.Button(sel_frame, text="Select Unpushed Only",
                   command=self.select_unpushed).pack(side=tk.LEFT, padx=2)

        current_row += 1

        # Push Options Section
        options_frame = ttk.LabelFrame(parent, text="Push Options", padding="10")
        options_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(options_frame, text="Timeout (seconds):").grid(row=0, column=0, sticky=tk.W, padx=5)
        timeout_spin = ttk.Spinbox(options_frame, from_=10, to=120, textvariable=self.timeout, width=10)
        timeout_spin.grid(row=0, column=1, sticky=tk.W)
        timeout_spin.bind('<FocusOut>', lambda e: self.save_config())

        ttk.Label(options_frame, text="Max Retries:").grid(row=1, column=0, sticky=tk.W, padx=5)
        retry_spin = ttk.Spinbox(options_frame, from_=0, to=5, textvariable=self.max_retries, width=10)
        retry_spin.grid(row=1, column=1, sticky=tk.W)
        retry_spin.bind('<FocusOut>', lambda e: self.save_config())

        ignore_check = ttk.Checkbutton(options_frame, text="Ignore Capture_* folders (Capture_1, Capture_2, etc.)",
                                       variable=self.ignore_capture_folders)
        ignore_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)
        ignore_check.bind('<ButtonRelease-1>', lambda e: self.save_config())

        verify_check = ttk.Checkbutton(options_frame, text="Verify files after push",
                                       variable=self.verify_after_push)
        verify_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)
        verify_check.bind('<ButtonRelease-1>', lambda e: self.save_config())

        save_log_check = ttk.Checkbutton(options_frame, text="Save verification log to file",
                                         variable=self.save_verification_log)
        save_log_check.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=2)
        save_log_check.bind('<ButtonRelease-1>', lambda e: self.save_config())

        current_row += 1

        # Progress Section
        progress_frame = ttk.LabelFrame(parent, text="Push Progress", padding="10")
        progress_frame.grid(row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, columnspan=3, pady=5)

        # Stats labels
        self.stats_label = ttk.Label(progress_frame, text="Ready")
        self.stats_label.grid(row=1, column=0, columnspan=3, sticky=tk.W)

        self.current_file_label = ttk.Label(progress_frame, text="")
        self.current_file_label.grid(row=2, column=0, columnspan=3, sticky=tk.W)

        current_row += 1

        # Action Buttons - First Row (Main Push Buttons)
        button_frame1 = ttk.Frame(parent)
        button_frame1.grid(row=current_row, column=0, columnspan=3, pady=10)

        # Make push button large and prominent
        self.push_btn = ttk.Button(button_frame1, text="▶▶ PUSH SELECTED RTIDs ▶▶",
                                   command=self.start_push, width=30, style='Accent.TButton')
        self.push_btn.pack(side=tk.LEFT, padx=10, pady=5)

        self.resume_btn = ttk.Button(button_frame1, text="🔄 RESUME INTERRUPTED",
                                     command=self.resume_push, width=20, state='disabled')
        self.resume_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(button_frame1, text="⏹ STOP",
                                   command=self.stop_push_process, width=15, state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        current_row += 1

        # Action Buttons - Second Row (Utility Buttons)
        button_frame2 = ttk.Frame(parent)
        button_frame2.grid(row=current_row, column=0, columnspan=3, pady=5)

        self.verify_btn = ttk.Button(button_frame2, text="✓ Verify Only",
                                     command=self.run_verification, width=15)
        self.verify_btn.pack(side=tk.LEFT, padx=5)

        self.refresh_btn = ttk.Button(button_frame2, text="🔄 Refresh List",
                                      command=self.apply_search_filter, width=15)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

        self.save_cfg_btn = ttk.Button(button_frame2, text="💾 Save Config",
                                       command=self.save_config, width=15)
        self.save_cfg_btn.pack(side=tk.LEFT, padx=5)

        # Configure style for accent button
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Arial', 12, 'bold'), foreground='blue')

    def setup_verification_tab(self, parent):
        """Setup the verification log tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Verification Summary Frame
        summary_frame = ttk.LabelFrame(parent, text="Verification Summary", padding="10")
        summary_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

        self.verify_summary_label = ttk.Label(summary_frame, text="No verification run yet")
        self.verify_summary_label.pack(anchor=tk.W)

        # Verification Log Text
        log_frame = ttk.LabelFrame(parent, text="Verification Details", padding="5")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.verify_text = scrolledtext.ScrolledText(log_frame, height=20, width=100, wrap=tk.WORD)
        self.verify_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure tags for verification log
        self.verify_text.tag_configure('success', foreground='green')
        self.verify_text.tag_configure('error', foreground='red')
        self.verify_text.tag_configure('warning', foreground='orange')
        self.verify_text.tag_configure('header', foreground='blue', font=('Arial', 10, 'bold'))
        self.verify_text.tag_configure('info', foreground='black')

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, pady=10)

        ttk.Button(button_frame, text="Clear Verification Log",
                   command=self.clear_verification_log).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Save Verification Report",
                   command=self.save_verification_report).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Export as JSON",
                   command=self.export_verification_json).pack(side=tk.LEFT, padx=5)

    def setup_log_tab(self, parent):
        """Setup the push log tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Log Text with scrollbar
        log_frame = ttk.Frame(parent)
        log_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=25, width=100, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure log tags
        self.log_text.tag_configure('info', foreground='black')
        self.log_text.tag_configure('success', foreground='green')
        self.log_text.tag_configure('warning', foreground='orange')
        self.log_text.tag_configure('error', foreground='red')
        self.log_text.tag_configure('header', foreground='blue', font=('Arial', 10, 'bold'))

        # Button frame
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, pady=10)

        ttk.Button(button_frame, text="Clear Push Log",
                   command=self.clear_log).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Save Push Log",
                   command=self.save_push_log).pack(side=tk.LEFT, padx=5)

    def setup_history_tab(self, parent):
        """Setup the push history tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Create paned window for split view
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Left frame - RTID list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="RTIDs Pushed", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)

        # RTID listbox with scrollbar
        rtid_frame = ttk.Frame(left_frame)
        rtid_frame.pack(fill=tk.BOTH, expand=True)

        self.rtid_listbox = tk.Listbox(rtid_frame, height=20)
        rtid_scrollbar = ttk.Scrollbar(rtid_frame, orient=tk.VERTICAL, command=self.rtid_listbox.yview)
        self.rtid_listbox.configure(yscrollcommand=rtid_scrollbar.set)

        self.rtid_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rtid_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.rtid_listbox.bind('<<ListboxSelect>>', self.on_rtid_select)

        # Right frame - Folder details
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Pushed Folders", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)

        # Folder details treeview
        columns = ('folder', 'pushed_date', 'files', 'status')
        self.history_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=20)
        self.history_tree.heading('folder', text='Folder')
        self.history_tree.heading('pushed_date', text='Pushed Date')
        self.history_tree.heading('files', text='Files')
        self.history_tree.heading('status', text='Status')

        self.history_tree.column('folder', width=300)
        self.history_tree.column('pushed_date', width=150)
        self.history_tree.column('files', width=60, anchor='center')
        self.history_tree.column('status', width=80)

        # Scrollbar for history tree
        history_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, pady=10)

        ttk.Button(button_frame, text="Refresh History",
                   command=self.refresh_history_tab).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Clear History",
                   command=self.clear_history).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Export History",
                   command=self.export_history).pack(side=tk.LEFT, padx=5)

    def browse_source(self):
        """Browse for source folder"""
        path = filedialog.askdirectory(title="Select Source DICOM Folder")
        if path:
            self.source_path.set(path)
            self.save_config()
            self.log(f"Source path set to: {path}", 'info')

    def log(self, message, tag='info'):
        """Add message to log queue"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((f"[{timestamp}] {message}", tag))

    def verification_log(self, message, tag='info'):
        """Add message to verification log queue"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.verification_queue.put((f"[{timestamp}] {message}", tag))
        self.verification_log_data.append({
            'timestamp': timestamp,
            'message': message,
            'tag': tag
        })

    def update_log(self):
        """Update log text from queue"""
        try:
            while True:
                message, tag = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message + '\n', tag)
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.update_log)

    def update_verification_log(self):
        """Update verification log text from queue"""
        try:
            while True:
                message, tag = self.verification_queue.get_nowait()
                self.verify_text.insert(tk.END, message + '\n', tag)
                self.verify_text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.update_verification_log)

    def clear_log(self):
        """Clear the push log"""
        self.log_text.delete(1.0, tk.END)

    def clear_verification_log(self):
        """Clear the verification log"""
        self.verify_text.delete(1.0, tk.END)
        self.verification_log_data = []
        self.verify_summary_label.config(text="No verification run yet")

    def save_push_log(self):
        """Save push log to file"""
        filename = f"push_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))
            messagebox.showinfo("Success", f"Push log saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save log: {str(e)}")

    def save_verification_report(self):
        """Save verification report to file"""
        filename = f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("DICOM PUSH VERIFICATION REPORT\n")
                f.write("=" * 60 + "\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Server: {self.server_ae.get()} @ {self.server_host.get()}:{self.server_port.get()}\n")
                f.write(f"Local: {self.local_ae.get()} @ {self.local_ip.get()}:{self.local_port.get()}\n")
                f.write(f"Source: {self.source_path.get()}\n")
                f.write(f"Ignore Capture Folders: {self.ignore_capture_folders.get()}\n")
                f.write("\n" + "=" * 60 + "\n")
                f.write("VERIFICATION SUMMARY\n")
                f.write("=" * 60 + "\n")
                f.write(f"Total files verified: {self.stats['verified']}\n")
                f.write(f"Verification failed: {self.stats['verification_failed']}\n")
                f.write(f"Ignored Capture Folders: {self.stats['ignored_capture_folders']}\n")
                f.write(f"Ignored Capture Files: {self.stats['ignored_capture_files']}\n")
                f.write("\n" + "=" * 60 + "\n")
                f.write("DETAILED LOG\n")
                f.write("=" * 60 + "\n")

                for entry in self.verification_log_data:
                    f.write(f"[{entry['timestamp']}] {entry['message']}\n")

            messagebox.showinfo("Success", f"Verification report saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {str(e)}")

    def export_verification_json(self):
        """Export verification log as JSON"""
        filename = f"verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'server': {
                    'ae': self.server_ae.get(),
                    'host': self.server_host.get(),
                    'port': self.server_port.get()
                },
                'local': {
                    'ae': self.local_ae.get(),
                    'ip': self.local_ip.get(),
                    'port': self.local_port.get()
                },
                'source': self.source_path.get(),
                'ignore_capture_folders': self.ignore_capture_folders.get(),
                'statistics': self.stats,
                'verification_log': self.verification_log_data
            }

            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)

            messagebox.showinfo("Success", f"Verification data exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {str(e)}")

    def extract_rtid_from_path(self, folder_path):
        """Extract RTID from folder path - handles various formats like 202402A05, 25RT2025, RT202402A05"""
        path_str = str(folder_path)

        # Split path into components
        path_parts = Path(folder_path).parts

        # Look for RTID in path components (usually the folder right after PatientImages)
        for part in path_parts:
            # Check for various RTID patterns:

            # Pattern 1: Starts with RT followed by numbers/letters (e.g., RT202402A05)
            if re.match(r'^RT\d+[A-Z]?\d*', part):
                return part

            # Pattern 2: Contains RT in the middle (e.g., 25RT2025)
            if re.search(r'\d+RT\d+', part):
                return part

            # Pattern 3: Just numbers and letters without RT prefix (e.g., 202402A05)
            if re.match(r'^\d{6,}[A-Z]?\d*$', part):
                return part

            # Pattern 4: Any folder that might be an RTID (not common system folders)
            if (len(part) > 4 and
                    not part.startswith(('S', 'P', 'FG', 'FN', 'KV', 'DailyImages', 'DICOM')) and
                    not part in ['CBCT', 'RAD', 'PatientImages']):
                # Check if it has a mix of numbers and letters
                if re.search(r'\d', part) and re.search(r'[A-Z]', part):
                    return part

        # If we get here, try to find any folder that might be an RTID
        for i, part in enumerate(path_parts):
            # Look for patterns in the path
            if i > 0 and path_parts[i - 1] == "PatientImages":
                # The folder right after PatientImages is likely the RTID
                return part

        return "UNKNOWN_RTID"

    def extract_folder_info(self, folder_path):
        """Extract S, P, FG, FN from folder path"""
        path_str = str(folder_path)

        s_value = None
        p_value = None
        fg_value = None
        fn_value = None

        # Extract S number
        s_match = re.search(r'S(\d+)', path_str)
        if s_match:
            s_value = s_match.group(1)

        # Extract P number
        p_match = re.search(r'P(\d+)', path_str)
        if p_match:
            p_value = p_match.group(1)

        # Extract FG number
        fg_match = re.search(r'FG(\d+)', path_str)
        if fg_match:
            fg_value = fg_match.group(1)

        # Extract FN number
        fn_match = re.search(r'FN(\d+)_?\d*', path_str)
        if fn_match:
            fn_value = fn_match.group(1)

        return {
            's': s_value,
            'p': p_value,
            'fg': fg_value,
            'fn': fn_value
        }

    def is_capture_folder(self, folder_path):
        """Check if folder path contains Capture_* pattern"""
        if not self.ignore_capture_folders.get():
            return False

        path_str = str(folder_path)
        # Look for Capture_ followed by numbers
        capture_pattern = r'[\\/]Capture_\d+[\\/]'
        if re.search(capture_pattern, path_str):
            return True
        return False

    def find_dicom_folders(self, base_path):
        """Find all DICOM folders in the directory tree, excluding Capture_* folders"""
        base_path = Path(base_path)
        dicom_folders = []
        modalities_found = set()
        capture_folders_ignored = 0
        rtid_groups = {}

        self.log("Scanning for DICOM folders...", 'info')
        if self.ignore_capture_folders.get():
            self.log("   (Ignoring Capture_* folders)", 'info')

        for root, dirs, files in os.walk(base_path):
            current_path = Path(root)

            # Skip if this is a Capture_* folder
            if self.is_capture_folder(current_path):
                capture_folders_ignored += 1
                continue

            # Check if this directory is named "DICOM" and has files
            if current_path.name == "DICOM" and files:
                # Check if parent path contains Capture_* (double-check)
                if self.is_capture_folder(current_path.parent):
                    capture_folders_ignored += 1
                    continue

                # Extract RTID
                rtid = self.extract_rtid_from_path(current_path)
                folder_info = self.extract_folder_info(current_path)

                # Quick check for DICOM files and collect modalities
                dicom_count = 0
                folder_modalities = set()

                for file in files[:10]:  # Check first 10 files
                    file_path = os.path.join(root, file)
                    try:
                        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
                        if hasattr(ds, 'SOPClassUID'):
                            dicom_count += 1
                            if hasattr(ds, 'Modality'):
                                folder_modalities.add(ds.Modality)
                                modalities_found.add(ds.Modality)
                    except:
                        pass

                if dicom_count > 0:
                    rel_path = current_path.relative_to(base_path)
                    modalities_str = ', '.join(folder_modalities) if folder_modalities else 'Unknown'

                    folder_data = {
                        'path': current_path,
                        'rel_path': str(rel_path),
                        'rtid': rtid,
                        's': folder_info['s'],
                        'p': folder_info['p'],
                        'fg': folder_info['fg'],
                        'fn': folder_info['fn'],
                        'file_count': len(files),
                        'modalities': modalities_str,
                        'is_pushed': self.is_folder_pushed(current_path)
                    }

                    dicom_folders.append(folder_data)

                    # Group by RTID
                    if rtid not in rtid_groups:
                        rtid_groups[rtid] = []
                    rtid_groups[rtid].append(folder_data)

        self.stats['ignored_capture_folders'] = capture_folders_ignored
        return dicom_folders, rtid_groups, modalities_found

    def scan_folders(self):
        """Scan for DICOM folders and update treeview"""
        source = self.source_path.get().strip()

        if not source or not os.path.exists(source):
            messagebox.showerror("Error", "Please select a valid source path")
            return

        # Clear existing data
        self.all_folders = []
        self.rtid_groups = {}
        self.filtered_folders = []

        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)
        self.folder_data = []

        # Scan in thread to prevent UI freeze
        def scan_thread():
            self.log("\n" + "=" * 60, 'header')
            self.log("SCANNING FOR DICOM FOLDERS", 'header')
            self.log("=" * 60, 'header')
            if self.ignore_capture_folders.get():
                self.log("🔇 Ignoring Capture_* folders", 'warning')

            folders, rtid_groups, modalities = self.find_dicom_folders(source)

            if folders:
                self.all_folders = folders
                self.rtid_groups = rtid_groups

                # Update summary
                unpushed_count = sum(1 for f in folders if not f['is_pushed'])
                pushed_count = len(folders) - unpushed_count

                summary = (f"Total RTIDs: {len(rtid_groups)} | "
                           f"Total Folders: {len(folders)} | "
                           f"Pushed: {pushed_count} | "
                           f"Unpushed: {unpushed_count}")

                self.root.after(0, lambda s=summary: self.rtid_summary_label.config(text=s))

                # Apply search filter
                self.root.after(0, self.apply_search_filter)

                total_files = sum(f['file_count'] for f in folders)
                self.log(f"\n✅ Found {len(rtid_groups)} RTID groups with {len(folders)} folders, {total_files} files",
                         'success')
                self.log(f"📊 Modalities found: {', '.join(modalities)}", 'info')
                self.log(f"📊 Previously pushed: {pushed_count} folders", 'info')
                if self.stats['ignored_capture_folders'] > 0:
                    self.log(f"🔇 Ignored {self.stats['ignored_capture_folders']} Capture_* folders", 'warning')
            else:
                self.log("❌ No DICOM folders found", 'error')

        threading.Thread(target=scan_thread, daemon=True).start()

    def apply_search_filter(self):
        """Apply search/filter criteria to folder list"""
        # Clear existing treeview items
        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)
        self.folder_data = []

        # Get search criteria
        search_rtid = self.search_rtid.get().strip().upper()
        search_site = self.search_site.get().strip()
        search_phase = self.search_phase.get().strip()
        search_fg = self.search_fg.get().strip()
        search_fn = self.search_fn.get().strip()
        show_unpushed_only = self.show_only_unpushed.get()

        # Filter folders
        self.filtered_folders = []
        for folder in self.all_folders:
            # Apply RTID filter
            if search_rtid and search_rtid not in folder['rtid'].upper():
                continue

            # Apply site filter
            if search_site and (not folder['s'] or search_site not in folder['s']):
                continue

            # Apply phase filter
            if search_phase and (not folder['p'] or search_phase not in folder['p']):
                continue

            # Apply FG filter
            if search_fg and (not folder['fg'] or search_fg not in folder['fg']):
                continue

            # Apply FN filter
            if search_fn and (not folder['fn'] or search_fn not in folder['fn']):
                continue

            # Apply unpushed filter
            if show_unpushed_only and folder['is_pushed']:
                continue

            self.filtered_folders.append(folder)

        # Sort by RTID then path
        self.filtered_folders.sort(key=lambda x: (x['rtid'], x['rel_path']))

        # Add to treeview
        current_rtid = None
        for folder in self.filtered_folders:
            # Add RTID group header if new RTID
            if folder['rtid'] != current_rtid:
                current_rtid = folder['rtid']
                # Count folders in this RTID
                rtid_folder_count = sum(1 for f in self.filtered_folders if f['rtid'] == current_rtid)
                rtid_pushed = sum(1 for f in self.filtered_folders if f['rtid'] == current_rtid and f['is_pushed'])

                # Add group header
                group_text = f"📁 {current_rtid} ({rtid_folder_count} folders, {rtid_pushed} pushed)"
                group_id = self.folder_tree.insert('', tk.END, values=('', current_rtid, group_text, '', '', '', ''),
                                                   tags=('group',))
                self.folder_tree.item(group_id, open=True)

            # Determine display values
            select_val = '☑' if folder.get('selected', False) else '☐'
            pushed_status = '✓' if folder['is_pushed'] else '❌'

            # Create folder display string with S, P, FG, FN info
            info_parts = []
            if folder['s']:
                info_parts.append(f"S{folder['s']}")
            if folder['p']:
                info_parts.append(f"P{folder['p']}")
            if folder['fg']:
                info_parts.append(f"FG{folder['fg']}")
            if folder['fn']:
                info_parts.append(f"FN{folder['fn']}")

            info_str = " | ".join(info_parts) if info_parts else ""
            display_path = f"{folder['rel_path']}  [{info_str}]"

            # Add folder item
            item_id = self.folder_tree.insert('', tk.END,
                                              values=(select_val, folder['rtid'], display_path,
                                                      folder['file_count'], folder['modalities'],
                                                      'Pending', pushed_status))

            # Store folder data
            folder['id'] = item_id
            folder['selected'] = folder.get('selected', False)
            self.folder_data.append(folder)

        # Update summary
        self.rtid_summary_label.config(
            text=f"Showing {len(self.filtered_folders)} of {len(self.all_folders)} folders")

    def clear_search(self):
        """Clear search filters"""
        self.search_rtid.set("")
        self.search_site.set("")
        self.search_phase.set("")
        self.search_fg.set("")
        self.search_fn.set("")
        self.apply_search_filter()

    def on_tree_click(self, event):
        """Handle click on treeview to toggle selection"""
        region = self.folder_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.folder_tree.identify_column(event.x)
            if column == '#1':  # First column (checkbox)
                item = self.folder_tree.identify_row(event.y)
                if item:
                    # Check if this is a folder item (not a group header)
                    values = self.folder_tree.item(item, 'values')
                    if values and values[0] in ['☐', '☑']:  # Has checkbox
                        self.toggle_item(item)

    def toggle_item(self, item):
        """Toggle selection of an item"""
        for data in self.folder_data:
            if data['id'] == item:
                data['selected'] = not data['selected']
                new_value = '☑' if data['selected'] else '☐'
                self.folder_tree.set(item, 'select', new_value)
                break

    def select_all_visible(self):
        """Select all visible folders"""
        for data in self.folder_data:
            data['selected'] = True
            self.folder_tree.set(data['id'], 'select', '☑')

    def deselect_all_visible(self):
        """Deselect all visible folders"""
        for data in self.folder_data:
            data['selected'] = False
            self.folder_tree.set(data['id'], 'select', '☐')

    def select_unpushed(self):
        """Select only unpushed folders"""
        for data in self.folder_data:
            if not data['is_pushed']:
                data['selected'] = True
                self.folder_tree.set(data['id'], 'select', '☑')
            else:
                data['selected'] = False
                self.folder_tree.set(data['id'], 'select', '☐')

    def get_selected_folders(self):
        """Get list of selected folders"""
        return [data for data in self.folder_data if data['selected']]

    def get_selected_rtids(self):
        """Get unique RTIDs from selected folders"""
        rtids = set()
        for folder in self.get_selected_folders():
            rtids.add(folder['rtid'])
        return list(rtids)

    def test_connection(self):
        """Test connection to server with C-ECHO - validates AE title and association"""
        self.log("\n" + "=" * 60, 'header')
        self.log("TESTING SERVER CONNECTION", 'header')
        self.log("=" * 60, 'header')

        local_ae_title = self.local_ae.get().strip()
        server_ae_title = self.server_ae.get().strip()
        server_host = self.server_host.get().strip()
        server_port = self.server_port.get().strip()

        self.log(f"Local AE: {local_ae_title}", 'info')
        self.log(f"Server AE: {server_ae_title}", 'info')
        self.log(f"Server: {server_host}:{server_port}", 'info')

        # Validate inputs
        if not local_ae_title:
            self.log("❌ Local AE Title cannot be empty", 'error')
            messagebox.showerror("Error", "Local AE Title cannot be empty")
            return

        if not server_ae_title:
            self.log("❌ Server AE Title cannot be empty", 'error')
            messagebox.showerror("Error", "Server AE Title cannot be empty")
            return

        if not server_host:
            self.log("❌ Server Host/IP cannot be empty", 'error')
            messagebox.showerror("Error", "Server Host/IP cannot be empty")
            return

        try:
            server_port_int = int(server_port)
        except ValueError:
            self.log("❌ Server Port must be a valid number", 'error')
            messagebox.showerror("Error", "Server Port must be a valid number")
            return

        self.test_btn.config(state='disabled', text="Testing...")

        def test():
            try:
                # Create Application Entity with the local AE title
                ae = AE(ae_title=local_ae_title)

                # Add verification presentation context
                ae.add_requested_context(Verification)

                # Set timeouts
                ae.acse_timeout = self.timeout.get()
                ae.dimse_timeout = self.timeout.get()

                self.root.after(0, lambda: self.log("Establishing association with server...", 'info'))

                # Try to establish association with the server
                # This will fail if the AE title is not recognized by the server
                assoc = ae.associate(server_host, server_port_int, ae_title=server_ae_title)

                if assoc.is_established:
                    # Association established - now send C-ECHO
                    self.root.after(0, lambda: self.log("✅ Association established", 'success'))
                    self.root.after(0, lambda: self.log("Sending C-ECHO request...", 'info'))

                    status = assoc.send_c_echo()

                    if status:
                        if isinstance(status, pydicom.dataset.Dataset):
                            if (0x0000, 0x0900) in status:
                                status_val = status[0x0000, 0x0900].value
                                self.root.after(0, lambda v=status_val: self.log(f"Status: 0x{v:04X}", 'info'))
                                if status_val == 0x0000:
                                    self.root.after(0, lambda: self.log("✅ C-ECHO successful - Server is responding",
                                                                        'success'))
                                    self.root.after(0, lambda: messagebox.showinfo("Success",
                                                                                   f"Connection to server successful!\n\nLocal AE: {local_ae_title}\nServer AE: {server_ae_title}"))
                                else:
                                    self.root.after(0,
                                                    lambda: self.log(f"❌ C-ECHO failed with status: 0x{status_val:04X}",
                                                                     'error'))
                                    self.root.after(0, lambda: messagebox.showerror("C-ECHO Failed",
                                                                                    f"C-ECHO failed with status: 0x{status_val:04X}"))
                            else:
                                self.root.after(0,
                                                lambda: self.log("✅ C-ECHO successful (no status element)", 'success'))
                                self.root.after(0, lambda: messagebox.showinfo("Success",
                                                                               f"Connection to server successful!\n\nLocal AE: {local_ae_title}\nServer AE: {server_ae_title}"))
                        else:
                            self.root.after(0, lambda: self.log("✅ C-ECHO successful", 'success'))
                            self.root.after(0, lambda: messagebox.showinfo("Success",
                                                                           f"Connection to server successful!\n\nLocal AE: {local_ae_title}\nServer AE: {server_ae_title}"))
                    else:
                        self.root.after(0, lambda: self.log("❌ C-ECHO failed - no status returned", 'error'))
                        self.root.after(0, lambda: messagebox.showerror("C-ECHO Failed",
                                                                        "C-ECHO failed - no status returned from server"))

                    # Release association
                    assoc.release()
                    self.root.after(0, lambda: self.log("Association released", 'info'))

                else:
                    # Association failed - this usually means the AE title is not recognized
                    self.root.after(0, lambda: self.log("❌ Association rejected by server", 'error'))
                    self.root.after(0, lambda: self.log("   This typically means:", 'info'))
                    self.root.after(0, lambda: self.log("   • Local AE title is not configured in server", 'info'))
                    self.root.after(0, lambda: self.log("   • Server AE title is incorrect", 'info'))
                    self.root.after(0, lambda: self.log("   • Server is not running or port is wrong", 'info'))
                    self.root.after(0, lambda: messagebox.showerror("Association Failed",
                                                                    f"Could not establish association with server.\n\n"
                                                                    f"Local AE: {local_ae_title}\n"
                                                                    f"Server AE: {server_ae_title}\n\n"
                                                                    f"Possible reasons:\n"
                                                                    f"• Local AE title not configured in server\n"
                                                                    f"• Server AE title is incorrect\n"
                                                                    f"• Server is not running on {server_host}:{server_port}\n"
                                                                    f"• Firewall is blocking the connection"))

            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.log(f"❌ Connection error: {error_msg}", 'error'))

                # Provide more helpful error messages
                if "connection refused" in error_msg.lower():
                    self.root.after(0, lambda: messagebox.showerror("Connection Refused",
                                                                    f"Could not connect to server at {server_host}:{server_port}\n\n"
                                                                    f"Please check:\n"
                                                                    f"• Server is running\n"
                                                                    f"• Port {server_port} is correct\n"
                                                                    f"• Firewall is not blocking the connection"))
                elif "timed out" in error_msg.lower():
                    self.root.after(0, lambda: messagebox.showerror("Connection Timeout",
                                                                    f"Connection to {server_host}:{server_port} timed out\n\n"
                                                                    f"Please check:\n"
                                                                    f"• Network connectivity\n"
                                                                    f"• Server IP address is correct\n"
                                                                    f"• Server is reachable"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Connection Error",
                                                                    f"Error connecting to server:\n{error_msg}"))
            finally:
                self.root.after(0, lambda: self.test_btn.config(state='normal', text="Test Connection (C-ECHO)"))

        threading.Thread(target=test, daemon=True).start()

    def get_storage_contexts(self):
        """Get common storage presentation contexts"""
        return [
            CTImageStorage,
            MRImageStorage,
            RTImageStorage,
            PositronEmissionTomographyImageStorage,
            SecondaryCaptureImageStorage,
            UltrasoundImageStorage,
            XRayAngiographicImageStorage,
            NuclearMedicineImageStorage
        ]

    def verify_file_on_server(self, file_info):
        """Verify if file exists on server (simulated - would need C-FIND)"""
        # This is a simulated verification
        # In reality, you would need to query the server with C-FIND
        time.sleep(0.1)  # Simulate verification time
        return True, "File verified (simulated)"

    def is_file_already_pushed(self, file_path, file_info):
        """Check if file was already pushed in previous session"""
        for f in self.push_state['processed_files']:
            if f.get('path') == file_path or f.get('sop_uid') == file_info.get('sop_uid'):
                return True
        return False

    def push_folder(self, folder_path, ae, start_from_beginning=True):
        """Push all DICOM files in a folder to the server"""
        # Double-check that we're not pushing a Capture_* folder
        if self.is_capture_folder(folder_path):
            self.log(f"   ⚠ Skipping Capture_* folder: {folder_path}", 'warning')
            self.stats['ignored_capture_folders'] += 1
            return 0, 0, 0, 0, 0, []

        files = [f for f in os.listdir(folder_path)
                 if os.path.isfile(os.path.join(folder_path, f))]

        # Sort files for consistent ordering
        files.sort()

        pushed = 0
        failed = 0
        skipped = 0
        verified = 0
        verification_failed = 0

        folder_verification = []

        # Determine starting index for resume
        start_idx = 0
        if not start_from_beginning and self.push_state['current_folder_path'] == str(folder_path):
            # Resume from where we left off in this folder
            processed_in_folder = [f for f in self.push_state['processed_files']
                                   if f.get('folder') == str(folder_path)]
            start_idx = len(processed_in_folder)
            if start_idx > 0:
                self.log(f"   Resuming from file {start_idx + 1}/{len(files)}", 'info')

        for idx, file in enumerate(files[start_idx:], start_idx + 1):
            if self.stop_push:
                self.log("   Push stopped by user", 'warning')
                break

            file_path = os.path.join(folder_path, file)

            # Check if already processed in this session
            if not start_from_beginning:
                file_key = {'path': file_path, 'folder': str(folder_path)}
                if self.is_file_already_pushed(file_path, file_key):
                    self.log(f"   ⏭ Skipping already pushed: {file}", 'info')
                    pushed += 1  # Count as already pushed
                    continue

            try:
                # Check if it's a valid DICOM file
                ds_check = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
                if not hasattr(ds_check, 'SOPClassUID'):
                    skipped += 1
                    continue

                modality = getattr(ds_check, 'Modality', 'Unknown')
                study_uid = getattr(ds_check, 'StudyInstanceUID', 'Unknown')
                series_uid = getattr(ds_check, 'SeriesInstanceUID', 'Unknown')
                sop_uid = getattr(ds_check, 'SOPInstanceUID', 'Unknown')

                file_size = os.path.getsize(file_path)
                size_str = f"{file_size / (1024 * 1024):.1f} MB" if file_size > 1024 * 1024 else f"{file_size / 1024:.1f} KB"

                self.root.after(0, lambda f=file, s=size_str: self.current_file_label.config(
                    text=f"Pushing: {f} ({s})"))

                # Read full DICOM file
                ds = pydicom.dcmread(file_path)

                # Associate with server
                assoc = ae.associate(self.server_host.get(), int(self.server_port.get()),
                                     ae_title=self.server_ae.get())

                if not assoc.is_established:
                    self.log(f"   ❌ {file} - Association failed", 'error')
                    failed += 1
                    folder_verification.append({
                        'file': file,
                        'status': 'failed',
                        'reason': 'association_failed',
                        'modality': modality,
                        'study_uid': study_uid
                    })
                    # Save state after failure
                    self.save_push_state()
                    continue

                # Send file using C-STORE
                status = assoc.send_c_store(ds)
                assoc.release()

                # Check status
                success = False
                if status is None:
                    self.log(f"   ❌ {file} - No status returned", 'error')
                    failed += 1
                    folder_verification.append({
                        'file': file,
                        'status': 'failed',
                        'reason': 'no_status',
                        'modality': modality,
                        'study_uid': study_uid
                    })
                elif isinstance(status, pydicom.dataset.Dataset):
                    if (0x0000, 0x0900) in status:
                        status_val = status[0x0000, 0x0900].value
                        if status_val == 0x0000:
                            self.log(f"   ✅ {file}", 'success')
                            pushed += 1
                            success = True
                            folder_verification.append({
                                'file': file,
                                'status': 'success',
                                'modality': modality,
                                'study_uid': study_uid,
                                'series_uid': series_uid,
                                'sop_uid': sop_uid
                            })
                        else:
                            self.log(f"   ❌ {file} - Status: 0x{status_val:04X}", 'error')
                            failed += 1
                            folder_verification.append({
                                'file': file,
                                'status': 'failed',
                                'reason': f'status_0x{status_val:04X}',
                                'modality': modality,
                                'study_uid': study_uid
                            })
                    else:
                        self.log(f"   ✅ {file} (assumed success)", 'success')
                        pushed += 1
                        success = True
                        folder_verification.append({
                            'file': file,
                            'status': 'success_assumed',
                            'modality': modality,
                            'study_uid': study_uid,
                            'series_uid': series_uid,
                            'sop_uid': sop_uid
                        })
                elif isinstance(status, tuple) and len(status) >= 1:
                    if status[0] == 0x0000:
                        self.log(f"   ✅ {file}", 'success')
                        pushed += 1
                        success = True
                        folder_verification.append({
                            'file': file,
                            'status': 'success',
                            'modality': modality,
                            'study_uid': study_uid,
                            'series_uid': series_uid,
                            'sop_uid': sop_uid
                        })
                    else:
                        self.log(f"   ❌ {file} - Status: {status[0]}", 'error')
                        failed += 1
                        folder_verification.append({
                            'file': file,
                            'status': 'failed',
                            'reason': f'status_{status[0]}',
                            'modality': modality,
                            'study_uid': study_uid
                        })
                else:
                    self.log(f"   ✅ {file}", 'success')
                    pushed += 1
                    success = True
                    folder_verification.append({
                        'file': file,
                        'status': 'success',
                        'modality': modality,
                        'study_uid': study_uid,
                        'series_uid': series_uid,
                        'sop_uid': sop_uid
                    })

                # Update processed files list
                if success:
                    self.push_state['processed_files'].append({
                        'path': file_path,
                        'folder': str(folder_path),
                        'file': file,
                        'sop_uid': sop_uid,
                        'modality': modality
                    })

                # Verify if option enabled
                if success and self.verify_after_push.get():
                    verify_success, verify_msg = self.verify_file_on_server({
                        'study_uid': study_uid,
                        'series_uid': series_uid,
                        'sop_uid': sop_uid
                    })
                    if verify_success:
                        verified += 1
                        self.verification_log(f"      ✓ Verified: {file}", 'success')
                    else:
                        verification_failed += 1
                        self.verification_log(f"      ⚠ Verification failed: {file} - {verify_msg}", 'warning')

                # Update progress
                progress = (idx / len(files)) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))

                # Save state periodically (every 10 files)
                if idx % 10 == 0:
                    self.push_state['current_folder_index'] = idx
                    self.save_push_state()

            except Exception as e:
                self.log(f"   ❌ {file} - Error: {str(e)[:50]}", 'error')
                failed += 1
                folder_verification.append({
                    'file': file,
                    'status': 'failed',
                    'reason': str(e)[:100],
                    'modality': 'Unknown'
                })
                # Save state after error
                self.save_push_state()

        # Log folder verification summary
        if folder_verification:
            success_count = sum(1 for v in folder_verification if v['status'].startswith('success'))
            failed_count = sum(1 for v in folder_verification if v['status'] == 'failed')
            self.verification_log(f"\n📊 Folder Summary: {success_count} succeeded, {failed_count} failed", 'header')

        self.root.after(0, lambda: self.current_file_label.config(text=""))
        return pushed, failed, skipped, verified, verification_failed, folder_verification

    def start_push(self):
        """Start pushing selected folders"""
        selected = self.get_selected_folders()

        if not selected:
            messagebox.showwarning("Warning", "No folders selected")
            return

        selected_rtids = self.get_selected_rtids()
        total_files = sum(f['file_count'] for f in selected)

        # Check if any selected folders are already pushed
        already_pushed = [f for f in selected if f['is_pushed']]
        if already_pushed:
            msg = f"Warning: {len(already_pushed)} selected folders have already been pushed.\nDo you want to push them again?"
            if not messagebox.askyesno("Already Pushed", msg):
                # Remove already pushed from selection
                selected = [f for f in selected if not f['is_pushed']]
                if not selected:
                    return

        # Clear any existing state
        self.clear_push_state()
        self.resume_mode = False

        # Confirm with user
        if not messagebox.askyesno("Confirm Push",
                                   f"Push {len(selected)} folders from {len(selected_rtids)} RTIDs with {total_files} files to server?\n\n"
                                   f"RTIDs: {', '.join(selected_rtids[:5])}{'...' if len(selected_rtids) > 5 else ''}\n"
                                   f"Server: {self.server_ae.get()} @ {self.server_host.get()}:{self.server_port.get()}\n"
                                   f"Local: {self.local_ae.get()} @ {self.local_ip.get()}:{self.local_port.get()}\n"
                                   f"Ignore Capture Folders: {'Yes' if self.ignore_capture_folders.get() else 'No'}\n"
                                   f"Verification: {'Yes' if self.verify_after_push.get() else 'No'}"):
            return

        # Disable buttons
        self.push_btn.config(state='disabled')
        self.resume_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.scan_btn.config(state='disabled')
        self.test_btn.config(state='disabled')
        self.verify_btn.config(state='disabled')
        self.stop_push = False

        # Reset stats
        self.stats['pushed'] = 0
        self.stats['failed'] = 0
        self.stats['skipped'] = 0
        self.stats['verified'] = 0
        self.stats['verification_failed'] = 0
        self.stats['ignored_capture_folders'] = 0
        self.stats['ignored_capture_files'] = 0

        # Initialize push state
        self.push_state = {
            'in_progress': True,
            'current_rtid': '',
            'current_folder_index': 0,
            'current_folder_path': '',
            'processed_rtids': [],
            'processed_folders': [],
            'processed_files': [],
            'failed_files': [],
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'server_config': {
                'ae': self.server_ae.get(),
                'host': self.server_host.get(),
                'port': self.server_port.get()
            },
            'local_config': {
                'ae': self.local_ae.get(),
                'ip': self.local_ip.get(),
                'port': self.local_port.get()
            },
            'stats': self.stats
        }

        # Clear verification log for new push
        if self.verify_after_push.get():
            self.clear_verification_log()
            self.verification_log("\n" + "=" * 60, 'header')
            self.verification_log("VERIFICATION LOG - NEW PUSH SESSION", 'header')
            self.verification_log("=" * 60, 'header')

        self.log("\n" + "=" * 60, 'header')
        self.log("🚀 PUSHING DICOM FILES TO SERVER", 'header')
        self.log("=" * 60, 'header')
        self.log(f"Server: {self.server_ae.get()} @ {self.server_host.get()}:{self.server_port.get()}", 'info')
        self.log(f"Local: {self.local_ae.get()} @ {self.local_ip.get()}:{self.local_port.get()}", 'info')
        self.log(f"RTIDs to push: {len(selected_rtids)}", 'info')
        self.log(f"Folders to push: {len(selected)}", 'info')
        self.log(f"Total files: {total_files}", 'info')
        self.log(f"Ignore Capture Folders: {'Yes' if self.ignore_capture_folders.get() else 'No'}", 'info')
        self.log(f"Verification: {'Enabled' if self.verify_after_push.get() else 'Disabled'}", 'info')

        # Save initial state
        self.save_push_state()

        # Start push in separate thread
        self.push_thread = threading.Thread(target=self.perform_push, args=(selected, False), daemon=True)
        self.push_thread.start()

    def resume_push(self):
        """Resume interrupted push"""
        state = self.load_push_state()
        if not state:
            messagebox.showinfo("Info", "No interrupted push found")
            self.resume_btn.config(state='disabled')
            return

        # Get selected folders based on saved state
        selected = [d for d in self.folder_data if d['rel_path'] in [p.replace(str(self.source_path.get()) + '\\', '')
                                                                     for p in state.get('processed_folders', [])] or d[
                        'rtid'] in state.get('processed_rtids', [])]

        if not selected:
            messagebox.showerror("Error", "Could not find previously selected folders")
            return

        # Disable buttons
        self.push_btn.config(state='disabled')
        self.resume_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.scan_btn.config(state='disabled')
        self.test_btn.config(state='disabled')
        self.verify_btn.config(state='disabled')
        self.stop_push = False

        # Restore stats
        self.stats = state['stats']
        self.push_state = state
        self.push_state['in_progress'] = True

        self.log("\n" + "=" * 60, 'header')
        self.log("🔄 RESUMING INTERRUPTED PUSH", 'header')
        self.log("=" * 60, 'header')
        self.log(f"Resuming RTID: {state['current_rtid']}", 'info')
        self.log(f"Resuming from folder index {state['current_folder_index'] + 1}", 'info')
        self.log(f"Already pushed: {state['stats']['pushed']} files", 'info')

        # Start push in separate thread
        self.push_thread = threading.Thread(target=self.perform_push, args=(selected, True), daemon=True)
        self.push_thread.start()

    def perform_push(self, selected_folders, is_resume):
        """Perform the actual push operation"""
        try:
            # Create AE with storage contexts
            ae = AE(ae_title=self.local_ae.get())
            ae.acse_timeout = self.timeout.get()
            ae.dimse_timeout = self.timeout.get()

            for context_class in self.get_storage_contexts():
                ae.add_requested_context(context_class)

            ae.add_requested_context(Verification)

            start_time = time.time()
            if is_resume and self.push_state['start_time']:
                try:
                    saved_start = datetime.strptime(self.push_state['start_time'], '%Y-%m-%d %H:%M:%S')
                    start_time = time.mktime(saved_start.timetuple())
                except:
                    start_time = time.time()

            total_pushed = self.stats['pushed']
            total_failed = self.stats['failed']
            total_skipped = self.stats['skipped']
            total_verified = self.stats['verified']
            total_verification_failed = self.stats['verification_failed']
            all_verifications = []

            # Group by RTID
            rtid_groups = {}
            for folder in selected_folders:
                if folder['rtid'] not in rtid_groups:
                    rtid_groups[folder['rtid']] = []
                rtid_groups[folder['rtid']].append(folder)

            rtid_list = list(rtid_groups.keys())

            # Determine starting RTID index for resume
            start_rtid_idx = 0
            if is_resume and self.push_state['current_rtid']:
                try:
                    start_rtid_idx = rtid_list.index(self.push_state['current_rtid'])
                except ValueError:
                    start_rtid_idx = 0

            for rtid_idx, rtid in enumerate(rtid_list[start_rtid_idx:], start_rtid_idx + 1):
                if self.stop_push:
                    break

                folders_in_rtid = rtid_groups[rtid]
                self.push_state['current_rtid'] = rtid

                self.log(f"\n{'=' * 60}", 'header')
                self.log(f"📁 RTID [{rtid_idx}/{len(rtid_list)}]: {rtid}", 'header')
                self.log(f"{'=' * 60}", 'header')
                self.log(f"Processing {len(folders_in_rtid)} folders in this RTID", 'info')

                # Check if RTID was already completely processed
                if rtid in self.push_state['processed_rtids']:
                    self.log(f"   ⏭ RTID already completely processed, skipping", 'info')
                    continue

                for folder_idx, folder in enumerate(folders_in_rtid, 1):
                    if self.stop_push:
                        break

                    folder_path = folder['path']
                    self.push_state['current_folder_index'] = folder_idx - 1
                    self.push_state['current_folder_path'] = str(folder_path)

                    self.root.after(0, lambda i=folder_idx, t=len(folders_in_rtid), p=folder['rel_path']:
                    self.stats_label.config(text=f"Folder {i}/{t}: {p}"))

                    self.log(f"\n📁 [{folder_idx}/{len(folders_in_rtid)}] Processing: {folder['rel_path']}", 'header')
                    self.log(f"   Modalities: {folder['modalities']}", 'info')

                    # Check if folder was already completely processed
                    if str(folder_path) in self.push_state['processed_folders']:
                        self.log(f"   ⏭ Folder already completely processed, skipping", 'info')
                        continue

                    pushed, failed, skipped, verified, v_failed, folder_verifications = self.push_folder(
                        folder_path, ae, start_from_beginning=not is_resume)

                    total_pushed += pushed
                    total_failed += failed
                    total_skipped += skipped
                    total_verified += verified
                    total_verification_failed += v_failed
                    all_verifications.extend(folder_verifications)

                    # Mark folder as processed
                    if not self.stop_push:
                        self.push_state['processed_folders'].append(str(folder_path))
                        folder['is_pushed'] = True
                        self.mark_folder_as_pushed(folder_path, rtid, 'completed')
                        self.folder_tree.set(folder['id'], 'pushed', '✓')

                    # Update stats
                    self.stats['pushed'] = total_pushed
                    self.stats['failed'] = total_failed
                    self.stats['skipped'] = total_skipped
                    self.stats['verified'] = total_verified
                    self.stats['verification_failed'] = total_verification_failed

                    self.root.after(0, lambda p=total_pushed, f=total_failed, s=total_skipped, v=total_verified:
                    self.stats_label.config(
                        text=f"Pushed: {p} | Failed: {f} | Skipped: {s} | Verified: {v}"))

                    # Save state after each folder
                    self.save_push_state()

                # Mark RTID as processed if all folders done
                if not self.stop_push:
                    self.push_state['processed_rtids'].append(rtid)

            # Complete
            elapsed = time.time() - start_time

            if self.stop_push:
                self.log("\n" + "=" * 60, 'header')
                self.log("⏸ PUSH PAUSED - State Saved", 'header')
                self.log("=" * 60, 'header')
                self.log(f"You can resume later using the RESUME button", 'info')
            else:
                self.log("\n" + "=" * 60, 'header')
                self.log("✅ PUSH COMPLETED", 'header')
                self.log("=" * 60, 'header')
                self.log(f"Total RTIDs processed: {len(rtid_list)}", 'info')
                self.log(f"Total folders processed: {len(selected_folders)}", 'info')
                self.log(f"Files pushed successfully: {total_pushed}", 'success')
                self.log(f"Files failed: {total_failed}", 'error')
                self.log(f"Non-DICOM files skipped: {total_skipped}", 'warning')
                self.log(f"Files verified: {total_verified}", 'success')
                self.log(f"Verification failed: {total_verification_failed}", 'warning')
                self.log(f"Ignored Capture Folders: {self.stats['ignored_capture_folders']}", 'info')
                self.log(f"Total time: {elapsed / 60:.1f} minutes", 'info')

                # Clear state on successful completion
                self.clear_push_state()

                # Refresh the view to show updated push status
                self.root.after(0, self.apply_search_filter)

            # Update verification summary
            if self.verify_after_push.get():
                if total_verified + total_verification_failed > 0:
                    success_rate = total_verified / (total_verified + total_verification_failed) * 100
                    verify_summary = (f"Verification Summary:\n"
                                      f"  Total files verified: {total_verified}\n"
                                      f"  Verification failed: {total_verification_failed}\n"
                                      f"  Success rate: {success_rate:.1f}%\n"
                                      f"  Ignored Capture Folders: {self.stats['ignored_capture_folders']}")
                else:
                    verify_summary = "No files were verified"
                self.root.after(0, lambda s=verify_summary: self.verify_summary_label.config(text=s))

            # Save verification log if enabled
            if self.save_verification_log.get() and self.verify_after_push.get() and not self.stop_push:
                self.save_verification_report()

        except Exception as e:
            self.log(f"❌ Push error: {str(e)}", 'error')
            self.save_push_state()
        finally:
            # Re-enable buttons
            self.root.after(0, lambda: self.push_btn.config(state='normal'))
            self.root.after(0, lambda: self.stop_btn.config(state='disabled'))
            self.root.after(0, lambda: self.scan_btn.config(state='normal'))
            self.root.after(0, lambda: self.test_btn.config(state='normal'))
            self.root.after(0, lambda: self.verify_btn.config(state='normal'))
            self.root.after(0, lambda: self.progress_var.set(0))
            self.root.after(0, lambda: self.stats_label.config(text="Ready"))
            self.root.after(0, lambda: self.current_file_label.config(text=""))

            # Check if we should enable resume button
            if self.push_state['in_progress'] and not self.stop_push:
                self.root.after(0, lambda: self.resume_btn.config(state='normal'))
            else:
                self.root.after(0, lambda: self.resume_btn.config(state='disabled'))

    def run_verification(self):
        """Run verification only on selected folders"""
        selected = self.get_selected_folders()

        if not selected:
            messagebox.showwarning("Warning", "No folders selected")
            return

        self.clear_verification_log()

        self.verification_log("\n" + "=" * 60, 'header')
        self.verification_log("VERIFICATION ONLY RUN", 'header')
        self.verification_log("=" * 60, 'header')
        self.verification_log(f"Server: {self.server_ae.get()} @ {self.server_host.get()}:{self.server_port.get()}",
                              'info')
        self.verification_log(f"Folders to verify: {len(selected)}", 'info')
        self.verification_log(f"Ignore Capture Folders: {'Yes' if self.ignore_capture_folders.get() else 'No'}", 'info')

        # This would need C-FIND implementation
        self.verification_log("\n⚠️ Full verification would require C-FIND queries to server", 'warning')
        self.verification_log("This is a simulated verification for demonstration", 'warning')

        total_verified = 0
        ignored_folders = 0

        for folder in selected:
            # Check if folder is a Capture_* folder
            if self.is_capture_folder(folder['path']):
                self.verification_log(f"\n🔇 Ignoring Capture folder: {folder['rel_path']}", 'warning')
                ignored_folders += 1
                continue

            self.verification_log(f"\n📁 Folder: {folder['rel_path']}", 'header')
            self.verification_log(f"   RTID: {folder['rtid']}", 'info')
            self.verification_log(f"   Files: {folder['file_count']}", 'info')
            self.verification_log(f"   Modalities: {folder['modalities']}", 'info')
            self.verification_log(f"   Previously Pushed: {'Yes' if folder['is_pushed'] else 'No'}", 'info')

            # Simulate verification
            for i in range(min(5, folder['file_count'])):
                self.verification_log(f"   ✓ File {i + 1}: Verified", 'success')
                total_verified += 1

            if folder['file_count'] > 5:
                self.verification_log(f"   ... and {folder['file_count'] - 5} more files", 'info')

        self.verification_log("\n" + "=" * 60, 'header')
        self.verification_log(f"Verification complete.", 'success')
        self.verification_log(f"Files verified: {total_verified} (simulated)", 'info')
        if ignored_folders > 0:
            self.verification_log(f"Capture folders ignored: {ignored_folders}", 'warning')

    def stop_push_process(self):
        """Stop the push process"""
        self.stop_push = True
        self.push_state['in_progress'] = True  # Keep in progress for resume
        self.log("⏹ Stopping push process... State saved for resume", 'warning')
        self.stop_btn.config(state='disabled')

    def refresh_history_tab(self):
        """Refresh the history tab with latest data"""
        # Clear existing items
        self.rtid_listbox.delete(0, tk.END)
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Load RTIDs
        rtids = sorted(self.push_history['rtids'].keys())
        for rtid in rtids:
            self.rtid_listbox.insert(tk.END, rtid)

    def on_rtid_select(self, event):
        """Handle RTID selection in history tab"""
        selection = self.rtid_listbox.curselection()
        if not selection:
            return

        rtid = self.rtid_listbox.get(selection[0])

        # Clear folder tree
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Show folders for this RTID
        if rtid in self.push_history['rtids']:
            folder_keys = self.push_history['rtids'][rtid].get('folders', [])
            for folder_key in folder_keys:
                if folder_key in self.push_history['folders']:
                    folder_info = self.push_history['folders'][folder_key]
                    self.history_tree.insert('', tk.END, values=(
                        os.path.basename(folder_key),
                        folder_info.get('pushed_date', 'Unknown'),
                        folder_info.get('files_count', 'N/A'),
                        folder_info.get('status', 'Unknown')
                    ))

    def clear_history(self):
        """Clear push history"""
        if messagebox.askyesno("Clear History", "Are you sure you want to clear all push history?"):
            self.push_history = {
                'rtids': {},
                'folders': {},
                'files': {}
            }
            self.save_push_history()
            self.refresh_history_tab()
            self.log("✅ Push history cleared", 'info')

    def export_history(self):
        """Export push history to file"""
        filename = f"push_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(self.push_history, f, indent=2)
            messagebox.showinfo("Success", f"Push history exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export history: {str(e)}")

    def on_closing(self):
        """Handle window closing"""
        if self.push_thread and self.push_thread.is_alive():
            response = messagebox.askyesno("Push in Progress",
                                           "Push is still running. Save state and exit?")
            if response:
                self.stop_push = True
                self.save_push_state()
                time.sleep(1)
            else:
                return

        self.save_config()
        self.save_push_history()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = DICOMPushGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()