import sys
import numpy as np
import pydicom
from pydicom.dataset import Dataset
from pydicom.uid import generate_uid
import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import os
import json
import traceback
from typing import Tuple


class Contour:
    def __init__(self, name: str, color: Tuple[int, int, int] = (255, 0, 0)):
        self.name = name
        self.color = list(color)  # Store as list instead of tuple
        self.contours = {}

    def add_contour(self, slice_idx: int, polygon: np.ndarray):
        if slice_idx not in self.contours:
            self.contours[slice_idx] = []
        self.contours[slice_idx].append(polygon)

    def remove_last_contour(self, slice_idx: int):
        if slice_idx in self.contours and self.contours[slice_idx]:
            self.contours[slice_idx].pop()
            if not self.contours[slice_idx]:
                del self.contours[slice_idx]
            return True
        return False


class CTViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ct_slices = []
        self.current_slice = 0
        self.contours = {}
        self.current_contour = None
        self.current_polygon = []
        self.drawing_mode = False
        self.window_level = 40
        self.window_width = 400
        self.zoom_level = 1.0
        self.log_messages = []

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('CT Contour Drawing Tool - RT Structure Creator')
        self.setGeometry(100, 100, 1500, 900)

        # Set style
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; }
            QLabel, QGroupBox { color: white; }
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 1px solid #5a5a5a;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #5a5a5a; }
            QListWidget {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #4a4a4a;
            }
            QListWidget::item:selected { background-color: #4a7a9a; }
            QLineEdit {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #4a4a4a;
                padding: 3px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                font-family: monospace;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left panel
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel)

        # Center panel for image
        center_panel = self.create_center_panel()
        main_layout.addWidget(center_panel)

        # Right panel for log
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel)

        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 3)
        main_layout.setStretch(2, 1)

        self.log_message("Application started. Ready to load CT images.")

    def create_left_panel(self):
        left_panel = QWidget()
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)

        # File controls
        file_group = QGroupBox("File Controls")
        file_layout = QVBoxLayout()

        self.load_btn = QPushButton("1. Load CT Series")
        self.load_btn.clicked.connect(self.load_ct_series)
        file_layout.addWidget(self.load_btn)

        self.save_rt_btn = QPushButton("2. Save as RT Structure")
        self.save_rt_btn.clicked.connect(self.save_rt_structure)
        self.save_rt_btn.setEnabled(False)
        self.save_rt_btn.setStyleSheet("background-color: #2a5a2a;")
        file_layout.addWidget(self.save_rt_btn)

        self.save_json_btn = QPushButton("Export as JSON (Backup)")
        self.save_json_btn.clicked.connect(self.export_json)
        self.save_json_btn.setEnabled(False)
        file_layout.addWidget(self.save_json_btn)

        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)

        # Structure management
        structure_group = QGroupBox("Structures")
        structure_layout = QVBoxLayout()

        self.structure_list = QListWidget()
        self.structure_list.itemClicked.connect(self.on_structure_selected)
        structure_layout.addWidget(self.structure_list)

        add_layout = QHBoxLayout()
        self.structure_name_input = QLineEdit()
        self.structure_name_input.setPlaceholderText("Structure name (e.g., Tumor)")
        add_layout.addWidget(self.structure_name_input)

        self.add_structure_btn = QPushButton("Add Structure")
        self.add_structure_btn.clicked.connect(self.add_structure)
        add_layout.addWidget(self.add_structure_btn)
        structure_layout.addLayout(add_layout)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(30, 20)
        self.color_preview.setStyleSheet("background-color: red; border: 1px solid white;")
        color_layout.addWidget(self.color_preview)

        self.color_btn = QPushButton("Change Color")
        self.color_btn.clicked.connect(self.change_color)
        self.color_btn.setEnabled(False)
        color_layout.addWidget(self.color_btn)
        structure_layout.addLayout(color_layout)

        self.delete_structure_btn = QPushButton("Delete Structure")
        self.delete_structure_btn.clicked.connect(self.delete_structure)
        self.delete_structure_btn.setEnabled(False)
        structure_layout.addWidget(self.delete_structure_btn)

        self.clear_slice_btn = QPushButton("Clear Slice Contours")
        self.clear_slice_btn.clicked.connect(self.clear_current_slice)
        self.clear_slice_btn.setEnabled(False)
        structure_layout.addWidget(self.clear_slice_btn)

        self.undo_btn = QPushButton("Undo Last Contour")
        self.undo_btn.clicked.connect(self.undo_last_contour)
        self.undo_btn.setEnabled(False)
        structure_layout.addWidget(self.undo_btn)

        structure_group.setLayout(structure_layout)
        left_layout.addWidget(structure_group)

        # Navigation
        nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout()

        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.valueChanged.connect(self.on_slice_changed)
        nav_layout.addWidget(self.slice_slider)

        self.slice_label = QLabel("Slice: 0 / 0")
        nav_layout.addWidget(self.slice_label)

        nav_buttons = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.previous_slice)
        self.prev_btn.setEnabled(False)
        nav_buttons.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_slice)
        self.next_btn.setEnabled(False)
        nav_buttons.addWidget(self.next_btn)

        nav_layout.addLayout(nav_buttons)
        nav_group.setLayout(nav_layout)
        left_layout.addWidget(nav_group)

        # Display controls
        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout()

        display_layout.addWidget(QLabel("Window Level:"))
        self.level_slider = QSlider(Qt.Horizontal)
        self.level_slider.setMinimum(-1000)
        self.level_slider.setMaximum(1000)
        self.level_slider.setValue(40)
        self.level_slider.valueChanged.connect(self.update_display)
        display_layout.addWidget(self.level_slider)

        display_layout.addWidget(QLabel("Window Width:"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setMinimum(1)
        self.width_slider.setMaximum(2000)
        self.width_slider.setValue(400)
        self.width_slider.valueChanged.connect(self.update_display)
        display_layout.addWidget(self.width_slider)

        zoom_layout = QHBoxLayout()
        self.zoom_in_btn = QPushButton("Zoom +")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("Zoom -")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(self.zoom_out_btn)

        self.reset_zoom_btn = QPushButton("Reset")
        self.reset_zoom_btn.clicked.connect(self.reset_zoom)
        zoom_layout.addWidget(self.reset_zoom_btn)

        display_layout.addLayout(zoom_layout)
        display_group.setLayout(display_layout)
        left_layout.addWidget(display_group)

        # Instructions
        info_group = QGroupBox("Instructions")
        info_layout = QVBoxLayout()
        info_text = QLabel(
            "1. Load CT folder\n"
            "2. Add a structure (e.g., 'Tumor')\n"
            "3. Press 'D' to toggle drawing mode\n"
            "4. Left click: Add points\n"
            "5. Right click: Close contour\n"
            "6. Navigate slices with slider or arrow keys\n"
            "7. Click 'Save as RT Structure'"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        self.drawing_mode_label = QLabel("✏️ Drawing Mode: OFF")
        self.drawing_mode_label.setStyleSheet("color: red; font-weight: bold; font-size: 12px;")
        info_layout.addWidget(self.drawing_mode_label)

        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)

        left_layout.addStretch()
        return left_panel

    def create_center_panel(self):
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        center_panel.setLayout(center_layout)

        self.figure = Figure(figsize=(12, 10), dpi=100, facecolor='#2b2b2b')
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, center_panel)

        center_layout.addWidget(self.toolbar)
        center_layout.addWidget(self.canvas)

        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')

        return center_panel

    def create_right_panel(self):
        right_panel = QWidget()
        right_panel.setMaximumWidth(400)
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        log_group = QGroupBox("Log / Debug Info")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.clear_log)
        log_layout.addWidget(clear_log_btn)

        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        info_group = QGroupBox("Contour Summary")
        info_layout = QVBoxLayout()

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(200)
        info_layout.addWidget(self.summary_text)

        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)

        return right_panel

    def log_message(self, message):
        """Add message to log"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_text.append(log_entry)
        print(log_entry)  # Also print to console

    def clear_log(self):
        self.log_text.clear()

    def update_summary(self):
        """Update contour summary"""
        summary = "Contour Summary:\n"
        summary += "=" * 40 + "\n"

        if not self.contours:
            summary += "No structures defined\n"
        else:
            for name, contour in self.contours.items():
                total_contours = sum(len(polygons) for polygons in contour.contours.values())
                slices_with_contours = len(contour.contours)
                summary += f"\n📌 {name}:\n"
                summary += f"   Color: RGB{contour.color}\n"
                summary += f"   Slices: {slices_with_contours}\n"
                summary += f"   Contours: {total_contours}\n"

        self.summary_text.setText(summary)

    def load_ct_series(self):
        folder = QFileDialog.getExistingDirectory(self, "Select CT DICOM Folder")
        if not folder:
            return

        self.log_message(f"Loading CT series from: {folder}")

        try:
            dcm_files = []
            for file in os.listdir(folder):
                if file.endswith('.dcm'):
                    try:
                        ds = pydicom.dcmread(os.path.join(folder, file))
                        if hasattr(ds, 'Modality') and ds.Modality == 'CT':
                            dcm_files.append(ds)
                    except Exception as e:
                        self.log_message(f"Warning: Could not read {file}: {e}")

            if not dcm_files:
                QMessageBox.warning(self, "Error", "No CT DICOM files found")
                return

            # Sort by slice location
            self.ct_slices = sorted(dcm_files, key=lambda x: float(x.ImagePositionPatient[2]))

            self.log_message(f"Successfully loaded {len(self.ct_slices)} CT slices")
            self.log_message(f"Image size: {self.ct_slices[0].pixel_array.shape}")
            self.log_message(f"Pixel spacing: {self.ct_slices[0].PixelSpacing}")

            # Update UI
            self.slice_slider.setMaximum(len(self.ct_slices) - 1)
            self.slice_slider.setEnabled(True)
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self.save_rt_btn.setEnabled(True)
            self.save_json_btn.setEnabled(True)

            self.current_slice = 0
            self.slice_slider.setValue(0)
            self.slice_label.setText(f"Slice: 1 / {len(self.ct_slices)}")

            self.update_display()
            self.log_message("CT series loaded successfully. Add a structure to start drawing.")

        except Exception as e:
            error_msg = f"Failed to load CT series: {str(e)}\n{traceback.format_exc()}"
            self.log_message(error_msg)
            QMessageBox.critical(self, "Error", error_msg)

    def add_structure(self):
        name = self.structure_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Warning", "Please enter a structure name")
            return

        if name in self.contours:
            QMessageBox.warning(self, "Warning", f"Structure '{name}' already exists")
            return

        import random
        color = [random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]  # Use list

        contour = Contour(name, color)
        self.contours[name] = contour

        self.structure_list.addItem(name)
        self.structure_name_input.clear()

        self.log_message(f"Added structure: {name} (Color: {color})")
        self.update_summary()

    def on_structure_selected(self, item):
        self.current_contour = self.contours[item.text()]
        self.color_preview.setStyleSheet(
            f"background-color: rgb({self.current_contour.color[0]}, {self.current_contour.color[1]}, {self.current_contour.color[2]}); border: 1px solid white;")
        self.color_btn.setEnabled(True)
        self.delete_structure_btn.setEnabled(True)
        self.clear_slice_btn.setEnabled(True)
        self.undo_btn.setEnabled(True)
        self.log_message(f"Selected structure: {self.current_contour.name}")
        self.update_display()

    def change_color(self):
        if not self.current_contour:
            return

        color = QColorDialog.getColor()
        if color.isValid():
            self.current_contour.color = [color.red(), color.green(), color.blue()]  # Use list
            self.color_preview.setStyleSheet(
                f"background-color: rgb({self.current_contour.color[0]}, {self.current_contour.color[1]}, {self.current_contour.color[2]}); border: 1px solid white;")
            self.log_message(f"Changed color of {self.current_contour.name} to RGB{self.current_contour.color}")
            self.update_display()

    def delete_structure(self):
        if not self.current_contour:
            return

        reply = QMessageBox.question(self, 'Confirm Delete',
                                     f'Delete structure "{self.current_contour.name}"?',
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.log_message(f"Deleted structure: {self.current_contour.name}")
            del self.contours[self.current_contour.name]
            current_row = self.structure_list.currentRow()
            self.structure_list.takeItem(current_row)
            self.current_contour = None

            if len(self.contours) == 0:
                self.color_btn.setEnabled(False)
                self.delete_structure_btn.setEnabled(False)
                self.clear_slice_btn.setEnabled(False)
                self.undo_btn.setEnabled(False)

            self.update_display()
            self.update_summary()

    def clear_current_slice(self):
        if not self.current_contour:
            QMessageBox.warning(self, "Warning", "Please select a structure")
            return

        if self.current_slice in self.current_contour.contours:
            num_contours = len(self.current_contour.contours[self.current_slice])
            del self.current_contour.contours[self.current_slice]
            self.log_message(
                f"Cleared {num_contours} contour(s) from slice {self.current_slice + 1} for structure {self.current_contour.name}")
            self.update_display()
            self.update_summary()

    def undo_last_contour(self):
        if not self.current_contour:
            QMessageBox.warning(self, "Warning", "Please select a structure")
            return

        if self.current_contour.remove_last_contour(self.current_slice):
            self.log_message(f"Undid last contour on slice {self.current_slice + 1} for {self.current_contour.name}")
            self.update_display()
            self.update_summary()

    def on_slice_changed(self):
        self.current_slice = self.slice_slider.value()
        self.slice_label.setText(f"Slice: {self.current_slice + 1} / {len(self.ct_slices)}")
        self.update_display()

    def previous_slice(self):
        if self.current_slice > 0:
            self.current_slice -= 1
            self.slice_slider.setValue(self.current_slice)

    def next_slice(self):
        if self.current_slice < len(self.ct_slices) - 1:
            self.current_slice += 1
            self.slice_slider.setValue(self.current_slice)

    def update_display(self):
        if not self.ct_slices:
            return

        self.ax.clear()

        ds = self.ct_slices[self.current_slice]
        image = ds.pixel_array.astype(np.float32)

        if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
            image = image * ds.RescaleSlope + ds.RescaleIntercept

        min_val = self.level_slider.value() - self.width_slider.value() / 2
        max_val = self.level_slider.value() + self.width_slider.value() / 2
        image = np.clip(image, min_val, max_val)
        image = (image - min_val) / (max_val - min_val)

        self.ax.imshow(image, cmap='gray')

        # Draw contours
        for contour_name, contour_obj in self.contours.items():
            if self.current_slice in contour_obj.contours:
                for polygon in contour_obj.contours[self.current_slice]:
                    color = tuple(c / 255 for c in contour_obj.color)
                    self.ax.plot(polygon[:, 0], polygon[:, 1], color=color, linewidth=2)
                    self.ax.fill(polygon[:, 0], polygon[:, 1], alpha=0.3, color=color)

        # Draw current polygon
        if self.current_polygon and self.drawing_mode and self.current_contour:
            points = np.array(self.current_polygon)
            color = tuple(c / 255 for c in self.current_contour.color)
            self.ax.plot(points[:, 0], points[:, 1], color=color, linewidth=2, linestyle='--')
            self.ax.plot(points[:, 0], points[:, 1], 'o', color=color, markersize=4)

        self.ax.set_title(
            f"Slice {self.current_slice + 1} - {self.current_contour.name if self.current_contour else 'No Structure Selected'}")
        self.ax.axis('off')

        image_shape = image.shape
        self.ax.set_xlim(0, image_shape[1] / self.zoom_level)
        self.ax.set_ylim(image_shape[0] / self.zoom_level, 0)

        self.canvas.draw()

    def on_mouse_press(self, event):
        if not self.drawing_mode or not self.current_contour:
            return

        if event.inaxes != self.ax:
            return

        if event.button == 1:  # Left click
            x, y = event.xdata, event.ydata
            if x is not None and y is not None:
                self.current_polygon.append([x, y])
                self.update_display()

        elif event.button == 3 and len(self.current_polygon) > 2:  # Right click
            self.finish_contour()

    def on_mouse_move(self, event):
        if not self.drawing_mode or not self.current_contour or not self.current_polygon:
            return

        if event.inaxes != self.ax:
            return

        if event.xdata and event.ydata and len(self.current_polygon) > 0:
            self.update_display()
            points = np.array(self.current_polygon + [[event.xdata, event.ydata]])
            color = tuple(c / 255 for c in self.current_contour.color)
            self.ax.plot(points[-2:, 0], points[-2:, 1], color=color, linewidth=2, alpha=0.5)
            self.canvas.draw()

    def finish_contour(self):
        if len(self.current_polygon) > 2:
            polygon = np.array(self.current_polygon)
            self.current_contour.add_contour(self.current_slice, polygon)
            self.log_message(
                f"Added contour with {len(polygon)} points to {self.current_contour.name} on slice {self.current_slice + 1}")
            self.current_polygon = []
            self.update_display()
            self.update_summary()

    def zoom_in(self):
        self.zoom_level *= 1.2
        self.update_display()

    def zoom_out(self):
        self.zoom_level /= 1.2
        self.update_display()

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.update_display()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_D:
            self.drawing_mode = not self.drawing_mode
            if self.drawing_mode:
                if not self.current_contour:
                    QMessageBox.warning(self, "Warning", "Please select or create a structure first")
                    self.drawing_mode = False
                else:
                    self.drawing_mode_label.setText("✏️ Drawing Mode: ON")
                    self.drawing_mode_label.setStyleSheet("color: green; font-weight: bold; font-size: 12px;")
                    self.log_message("Drawing mode enabled")
                    self.current_polygon = []
            else:
                if self.current_polygon:
                    self.finish_contour()
                self.drawing_mode_label.setText("✏️ Drawing Mode: OFF")
                self.drawing_mode_label.setStyleSheet("color: red; font-weight: bold; font-size: 12px;")
                self.log_message("Drawing mode disabled")

        elif event.key() == Qt.Key_Escape:
            if self.current_polygon:
                self.current_polygon = []
                self.update_display()
                self.log_message("Drawing cancelled")

        elif event.key() == Qt.Key_Space:
            if self.current_polygon:
                self.finish_contour()

        elif event.key() == Qt.Key_Left:
            self.previous_slice()

        elif event.key() == Qt.Key_Right:
            self.next_slice()

    def save_rt_structure(self):
        """Save as DICOM RT Structure with detailed logging"""
        if not self.ct_slices:
            QMessageBox.warning(self, "Warning", "No CT series loaded")
            return

        if not self.contours:
            QMessageBox.warning(self, "Warning", "No contours to save. Please draw some contours first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save RT Structure", "", "DICOM Files (*.dcm)")
        if not file_path:
            return

        self.log_message("=" * 60)
        self.log_message("Starting RT Structure creation...")

        try:
            # Validate contours before saving
            total_contours = sum(
                len(polygons) for contour in self.contours.values() for polygons in contour.contours.values())
            if total_contours == 0:
                self.log_message("ERROR: No contours found to save!")
                QMessageBox.warning(self, "Error", "No contours found to save. Please draw some contours first.")
                return

            self.log_message(f"Found {len(self.contours)} structure(s) with {total_contours} total contour(s)")

            # Create RT Structure
            self.create_rt_structure(file_path)

            self.log_message(f"✅ RT Structure successfully saved to: {file_path}")
            self.log_message("=" * 60)

            QMessageBox.information(self, "Success",
                                    f"RT Structure saved successfully!\n\n"
                                    f"File: {os.path.basename(file_path)}\n"
                                    f"Structures: {len(self.contours)}\n"
                                    f"Total contours: {total_contours}\n\n"
                                    f"The file can be imported into treatment planning systems.")

        except Exception as e:
            error_msg = f"❌ Failed to save RT Structure:\n{str(e)}\n\n{traceback.format_exc()}"
            self.log_message(error_msg)

            # Show detailed error in message box
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("RT Structure Save Error")
            error_dialog.setText("Failed to save RT Structure")
            error_dialog.setDetailedText(traceback.format_exc())
            error_dialog.exec_()

    def create_rt_structure(self, filename):
        """Create DICOM RT Structure Set with validation"""

        self.log_message("Creating DICOM RT Structure Set...")

        # Get first CT slice for reference
        first_ct = self.ct_slices[0]

        # Create file meta
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.3'  # RTSTRUCT
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'  # Explicit VR Little Endian
        file_meta.ImplementationClassUID = generate_uid()
        file_meta.ImplementationVersionName = 'PYTHON_RTSTRUCT_1.0'

        # Create main dataset
        ds = Dataset()
        ds.file_meta = file_meta
        ds.is_little_endian = True
        ds.is_implicit_VR = False

        # Patient information - convert to proper DICOM format
        patient_name = first_ct.get('PatientName', 'Unknown^Patient')
        ds.PatientName = patient_name
        ds.PatientID = first_ct.get('PatientID', 'Unknown')
        ds.PatientBirthDate = first_ct.get('PatientBirthDate', '19000101')
        ds.PatientSex = first_ct.get('PatientSex', 'O')

        # Study information
        ds.StudyInstanceUID = first_ct.get('StudyInstanceUID', generate_uid())
        ds.StudyDate = first_ct.get('StudyDate', datetime.datetime.now().strftime('%Y%m%d'))
        ds.StudyTime = first_ct.get('StudyTime', datetime.datetime.now().strftime('%H%M%S'))
        ds.StudyDescription = first_ct.get('StudyDescription', 'CT Study')

        # Series information
        ds.SeriesInstanceUID = generate_uid()
        ds.Modality = 'RTSTRUCT'
        ds.SeriesNumber = 200
        ds.SeriesDescription = 'RT Structure Set'
        ds.SeriesDate = datetime.datetime.now().strftime('%Y%m%d')
        ds.SeriesTime = datetime.datetime.now().strftime('%H%M%S')

        # SOP information
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID

        # Instance information
        ds.InstanceCreationDate = datetime.datetime.now().strftime('%Y%m%d')
        ds.InstanceCreationTime = datetime.datetime.now().strftime('%H%M%S')
        ds.InstanceNumber = 1

        # Manufacturer
        ds.Manufacturer = 'Python CT Contour Tool'
        ds.ManufacturerModelName = 'RT Structure Creator'

        # Referenced Frame of Reference
        ds.ReferencedFrameOfReferenceSequence = []
        ref_frame = Dataset()
        ref_frame.FrameOfReferenceUID = first_ct.get('FrameOfReferenceUID', generate_uid())

        # RT Referenced Study
        rt_ref_study = Dataset()
        rt_ref_study.ReferencedSOPClassUID = '1.2.840.10008.3.1.2.3.2'
        rt_ref_study.ReferencedSOPInstanceUID = ds.StudyInstanceUID

        # RT Referenced Series
        rt_ref_series = Dataset()
        rt_ref_series.SeriesInstanceUID = first_ct.SeriesInstanceUID

        # Contour Image Sequence (limit to slices that have contours to save space)
        # But include all slices for proper referencing
        rt_ref_series.ContourImageSequence = []
        for ct_slice in self.ct_slices:
            ref_image = Dataset()
            ref_image.ReferencedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
            ref_image.ReferencedSOPInstanceUID = ct_slice.SOPInstanceUID
            rt_ref_series.ContourImageSequence.append(ref_image)

        rt_ref_study.RTReferencedSeriesSequence = [rt_ref_series]
        ref_frame.RTReferencedStudySequence = [rt_ref_study]
        ds.ReferencedFrameOfReferenceSequence.append(ref_frame)

        self.log_message(f"Referenced Frame of Reference UID: {ref_frame.FrameOfReferenceUID}")
        self.log_message(f"Referenced {len(self.ct_slices)} CT slices")

        # Structure Set ROI Sequence
        ds.StructureSetROISequence = []
        ds.ROIContourSequence = []
        ds.RTROIObservationsSequence = []

        roi_number = 1
        total_contours_saved = 0

        for contour_name, contour_obj in self.contours.items():
            self.log_message(f"Processing structure: {contour_name}")

            # Structure Set ROI
            structure_roi = Dataset()
            structure_roi.ROINumber = roi_number
            structure_roi.ReferencedFrameOfReferenceUID = ref_frame.FrameOfReferenceUID
            structure_roi.ROIName = contour_name
            structure_roi.ROIGenerationAlgorithm = 'MANUAL'
            ds.StructureSetROISequence.append(structure_roi)

            # ROI Contour
            roi_contour = Dataset()
            roi_contour.ReferencedROINumber = roi_number
            # FIX: Convert tuple to list for ROIDisplayColor
            roi_contour.ROIDisplayColor = list(contour_obj.color)  # Convert tuple to list
            roi_contour.ContourSequence = []

            # Add contours for each slice
            for slice_idx, polygons in contour_obj.contours.items():
                if slice_idx >= len(self.ct_slices):
                    self.log_message(f"  Warning: Slice {slice_idx} out of range, skipping")
                    continue

                ct_slice = self.ct_slices[slice_idx]
                self.log_message(f"  Adding {len(polygons)} contour(s) for slice {slice_idx + 1}")

                for poly_idx, polygon in enumerate(polygons):
                    contour = Dataset()
                    contour.Number = len(roi_contour.ContourSequence) + 1

                    # Convert pixel coordinates to DICOM patient coordinates
                    points_3d = []
                    for point in polygon:
                        x = float(point[0]) * float(ct_slice.PixelSpacing[0]) + float(ct_slice.ImagePositionPatient[0])
                        y = float(point[1]) * float(ct_slice.PixelSpacing[1]) + float(ct_slice.ImagePositionPatient[1])
                        z = float(ct_slice.ImagePositionPatient[2])
                        points_3d.extend([x, y, z])

                    contour.ContourData = points_3d
                    contour.ContourGeometricType = 'CLOSED_PLANAR'
                    contour.NumberOfContourPoints = len(polygon)

                    # Referenced image
                    ref_image = Dataset()
                    ref_image.ReferencedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
                    ref_image.ReferencedSOPInstanceUID = ct_slice.SOPInstanceUID
                    contour.ContourImageSequence = [ref_image]

                    roi_contour.ContourSequence.append(contour)
                    total_contours_saved += 1

            if roi_contour.ContourSequence:
                ds.ROIContourSequence.append(roi_contour)

                # RT ROI Observations
                rt_roi_obs = Dataset()
                rt_roi_obs.ObservationNumber = roi_number
                rt_roi_obs.ReferencedROINumber = roi_number
                rt_roi_obs.ROIObservationLabel = contour_name
                rt_roi_obs.RTROIInterpretedType = 'ORGAN'
                ds.RTROIObservationsSequence.append(rt_roi_obs)

                self.log_message(f"  ✓ Added {len(roi_contour.ContourSequence)} contours for {contour_name}")
            else:
                self.log_message(f"  ✗ No valid contours for {contour_name}, skipping")

            roi_number += 1

        self.log_message(f"Total contours saved: {total_contours_saved}")
        self.log_message(f"Total structures saved: {len(ds.StructureSetROISequence)}")

        # Ensure sequences exist
        if not ds.StructureSetROISequence:
            ds.StructureSetROISequence = []
        if not ds.ROIContourSequence:
            ds.ROIContourSequence = []
        if not ds.RTROIObservationsSequence:
            ds.RTROIObservationsSequence = []

        # Save the file with proper error handling
        self.log_message(f"Saving to: {filename}")
        try:
            ds.save_as(filename, write_like_original=False)
            self.log_message("File saved successfully")

            # Verify file was created
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                self.log_message(f"File size: {file_size} bytes")
                if file_size < 1000:
                    self.log_message("Warning: File size is very small, may be invalid")
            else:
                raise Exception("File was not created successfully")

        except Exception as e:
            self.log_message(f"Error during save: {str(e)}")
            raise

    def export_json(self):
        """Export contours as JSON"""
        if not self.ct_slices or not self.contours:
            QMessageBox.warning(self, "Warning", "No contours to export")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export as JSON", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            export_data = {
                'study_uid': self.ct_slices[0].StudyInstanceUID,
                'series_uid': self.ct_slices[0].SeriesInstanceUID,
                'structures': {}
            }

            for contour_name, contour_obj in self.contours.items():
                structure_data = {
                    'color': contour_obj.color,
                    'contours': {}
                }

                for slice_idx, polygons in contour_obj.contours.items():
                    structure_data['contours'][str(slice_idx)] = [polygon.tolist() for polygon in polygons]

                export_data['structures'][contour_name] = structure_data

            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            self.log_message(f"Exported contours to JSON: {file_path}")
            QMessageBox.information(self, "Success", f"Exported to {file_path}")

        except Exception as e:
            self.log_message(f"Error exporting JSON: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")


def main():
    app = QApplication(sys.argv)
    viewer = CTViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()