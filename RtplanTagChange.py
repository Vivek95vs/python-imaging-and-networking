import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QFileDialog, QLineEdit, QMessageBox
)
import pydicom
from pydicom.tag import Tag
from pydicom.valuerep import DS


class RTPlanEditor(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RT Plan Editor")
        self.setGeometry(300, 200, 500, 300)

        self.dataset = None
        self.file_path = None

        # UI Elements
        self.label_file = QLabel("No RTPLAN loaded")

        self.btn_load = QPushButton("Load RTPLAN")
        self.btn_load.clicked.connect(self.load_file)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Manufacturer Model Name (0008,1090)")

        self.machine_input = QLineEdit()
        self.machine_input.setPlaceholderText("Treatment Machine Name (300A,00B2)")

        self.energy_input = QLineEdit()
        self.energy_input.setPlaceholderText("Nominal Beam Energy (300A,0114)")

        self.btn_apply = QPushButton("Apply Changes")
        self.btn_apply.clicked.connect(self.apply_changes)

        self.btn_save = QPushButton("Save RTPLAN")
        self.btn_save.clicked.connect(self.save_file)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.label_file)
        layout.addWidget(self.btn_load)
        layout.addWidget(self.model_input)
        layout.addWidget(self.machine_input)
        layout.addWidget(self.energy_input)
        layout.addWidget(self.btn_apply)
        layout.addWidget(self.btn_save)

        self.setLayout(layout)

    # -----------------------------
    # Load RTPLAN
    # -----------------------------
    def load_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open RTPLAN", "", "DICOM Files (*.dcm)"
        )

        if file_name:
            try:
                self.dataset = pydicom.dcmread(file_name)
                self.file_path = file_name
                self.label_file.setText(f"Loaded: {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # -----------------------------
    # Recursive Tag Update
    # -----------------------------
    def update_tag_recursive(self, ds, tag, value):
        """
        Recursively update all occurrences of a DICOM tag
        """
        for elem in ds:
            if elem.tag == tag:
                elem.value = value

            if elem.VR == "SQ":  # Sequence
                for item in elem.value:
                    self.update_tag_recursive(item, tag, value)

    # -----------------------------
    # Apply Changes
    # -----------------------------
    def apply_changes(self):
        if not self.dataset:
            QMessageBox.warning(self, "Error", "Load a RTPLAN first")
            return

        model_name = self.model_input.text().strip()
        machine_name = self.machine_input.text().strip()
        energy_text = self.energy_input.text().strip()

        try:
            # (0008,1090) Manufacturer Model Name
            if model_name:
                self.update_tag_recursive(
                    self.dataset,
                    Tag(0x0008, 0x1090),
                    model_name
                )

            # (300A,00B2) Treatment Machine Name
            if machine_name:
                self.update_tag_recursive(
                    self.dataset,
                    Tag(0x300A, 0x00B2),
                    machine_name
                )

            # (300A,0114) Nominal Beam Energy
            if energy_text:
                energy_val = DS(energy_text)
                self.update_tag_recursive(
                    self.dataset,
                    Tag(0x300A, 0x0114),
                    energy_val
                )

            QMessageBox.information(self, "Success", "All tags updated successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # -----------------------------
    # Save RTPLAN
    # -----------------------------
    def save_file(self):
        if not self.dataset:
            QMessageBox.warning(self, "Error", "Nothing to save")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save RTPLAN", "", "DICOM Files (*.dcm)"
        )

        if save_path:
            try:
                self.dataset.save_as(save_path)
                QMessageBox.information(self, "Saved", "RTPLAN saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


# -----------------------------
# Run Application
# -----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RTPlanEditor()
    window.show()
    sys.exit(app.exec_())