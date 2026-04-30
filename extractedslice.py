"""
DICOM Slice Extractor with 3D Volume Preservation
Specifically for Dental CBCT data
"""

import pydicom
import os
import numpy as np
from pathlib import Path
from tqdm import tqdm
import json
from datetime import datetime
from pydicom.uid import generate_uid, ExplicitVRLittleEndian
import warnings
import math

warnings.filterwarnings('ignore')

class CBCTSliceExtractor:
    def __init__(self, dcm_file_path):
        """
        Extract Dental CBCT slices with proper 3D coordinates

        Args:
            dcm_file_path: Path to multi-frame CBCT DICOM file
        """
        self.input_path = Path(dcm_file_path)
        self.ds = None
        self.volume = None
        self.num_slices = 0
        self.slice_positions = []  # Store slice positions for 3D reconstruction

    def load_cbct_data(self):
        """Load CBCT data and extract 3D information"""
        print(f"🔬 Loading Dental CBCT data: {self.input_path.name}")

        self.ds = pydicom.dcmread(str(self.input_path), force=True)
        self.volume = self.ds.pixel_array

        # Get number of slices
        if hasattr(self.ds, 'NumberOfFrames'):
            self.num_slices = int(self.ds.NumberOfFrames)
        else:
            self.num_slices = self.volume.shape[0]

        print(f"✅ CBCT Volume: {self.num_slices} slices")
        print(f"📐 Slice dimensions: {self.volume.shape[1]} x {self.volume.shape[2]}")
        print(f"🎯 Data type: {self.volume.dtype}")

        # Extract CBCT-specific metadata
        self._extract_cbct_metadata()

        # Calculate slice positions for 3D reconstruction
        self._calculate_slice_positions()

        return self.volume

    def _extract_cbct_metadata(self):
        """Extract CBCT-specific metadata"""
        self.metadata = {
            'PatientID': getattr(self.ds, 'PatientID', 'Unknown'),
            'Modality': getattr(self.ds, 'Modality', 'CT'),
            'Manufacturer': getattr(self.ds, 'Manufacturer', 'Unknown'),
            'KVP': getattr(self.ds, 'KVP', 'Unknown'),
            'ExposureTime': getattr(self.ds, 'ExposureTime', 'Unknown'),
            'XRayTubeCurrent': getattr(self.ds, 'XRayTubeCurrent', 'Unknown'),
        }

        # Spatial information (CRITICAL for 3D reconstruction)
        self.pixel_spacing = getattr(self.ds, 'PixelSpacing', [1.0, 1.0])
        self.slice_thickness = float(getattr(self.ds, 'SliceThickness', 1.0))
        self.spacing_between_slices = float(getattr(self.ds, 'SpacingBetweenSlices', self.slice_thickness))

        # Try to get Image Position and Orientation
        if hasattr(self.ds, 'ImagePositionPatient'):
            self.image_position = [float(x) for x in self.ds.ImagePositionPatient]
        else:
            self.image_position = [0.0, 0.0, 0.0]

        if hasattr(self.ds, 'ImageOrientationPatient'):
            self.image_orientation = [float(x) for x in self.ds.ImageOrientationPatient]
        else:
            # Default orientation: axial slices
            self.image_orientation = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]

        print(f"\n📊 CBCT METADATA:")
        print(f"   Patient ID: {self.metadata['PatientID']}")
        print(f"   Pixel Spacing: {self.pixel_spacing} mm")
        print(f"   Slice Thickness: {self.slice_thickness} mm")
        print(f"   Image Position: {self.image_position}")
        print(f"   Image Orientation: {self.image_orientation}")

    def _calculate_slice_positions(self):
        """Calculate 3D positions for each slice"""
        print("\n🧮 Calculating 3D slice positions...")

        # Direction cosines from orientation
        row_cosine = np.array(self.image_orientation[:3])
        col_cosine = np.array(self.image_orientation[3:])
        slice_cosine = np.cross(row_cosine, col_cosine)

        # Pixel spacing
        row_spacing = float(self.pixel_spacing[0])
        col_spacing = float(self.pixel_spacing[1])

        # Calculate position for each slice
        self.slice_positions = []
        for slice_idx in range(self.num_slices):
            # Move along slice normal vector
            slice_offset = slice_cosine * slice_idx * self.spacing_between_slices
            position = np.array(self.image_position) + slice_offset

            self.slice_positions.append(position.tolist())

        print(f"✅ Calculated positions for {self.num_slices} slices")
        print(f"   First slice position: {self.slice_positions[0]}")
        print(f"   Last slice position: {self.slice_positions[-1]}")

    def extract_with_3d_coordinates(self, output_dir=None):
        """
        Extract slices with proper 3D coordinates for volume reconstruction

        Args:
            output_dir: Output directory for slices
        """
        if self.volume is None:
            self.load_cbct_data()

        # Create output directory
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"cbct_slices_3d_{timestamp}"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\n📤 Exporting to: {output_path}")

        # Save volume info for 3D reconstruction
        self._save_volume_info(output_path)

        # Extract each slice with 3D coordinates
        print(f"⏳ Extracting {self.num_slices} slices with 3D coordinates...")

        successful = 0
        for slice_idx in tqdm(range(self.num_slices), desc="Extracting", unit="slice"):
            try:
                output_file = output_path / f"slice_{slice_idx+1:04d}.dcm"
                self._create_cbct_slice(slice_idx, output_file)
                successful += 1
            except Exception as e:
                print(f"\n⚠️ Error slice {slice_idx+1}: {str(e)[:50]}...")

        print(f"\n✅ Successfully exported {successful}/{self.num_slices} slices")
        print(f"📁 Location: {output_path}")

        return output_path

    def _create_cbct_slice(self, slice_idx, output_file):
        """
        Create individual CBCT slice with proper 3D coordinates
        """
        # Create new dataset
        new_ds = pydicom.Dataset()

        # Copy essential metadata
        self._copy_essential_metadata(new_ds)

        # Get slice data
        slice_data = self.volume[slice_idx]

        # ===== SET 3D SPATIAL INFORMATION =====

        # Instance number
        new_ds.InstanceNumber = str(slice_idx + 1)

        # Image Position (Patient) - CRITICAL for 3D reconstruction
        position = self.slice_positions[slice_idx]
        new_ds.ImagePositionPatient = [str(coord) for coord in position]

        # Image Orientation (Patient) - CRITICAL for 3D reconstruction
        new_ds.ImageOrientationPatient = [str(coord) for coord in self.image_orientation]

        # Slice Location
        new_ds.SliceLocation = str(position[2])  # Z-coordinate

        # Pixel Spacing
        new_ds.PixelSpacing = [str(self.pixel_spacing[0]), str(self.pixel_spacing[1])]

        # Slice Thickness
        new_ds.SliceThickness = str(self.slice_thickness)

        # Spacing Between Slices
        new_ds.SpacingBetweenSlices = str(self.spacing_between_slices)

        # ===== SET IMAGE PROPERTIES =====

        new_ds.Rows = slice_data.shape[0]
        new_ds.Columns = slice_data.shape[1]

        # Pixel data properties
        new_ds.BitsAllocated = 16
        new_ds.BitsStored = 16
        new_ds.HighBit = 15
        new_ds.PixelRepresentation = 0
        new_ds.SamplesPerPixel = 1
        new_ds.PhotometricInterpretation = "MONOCHROME2"

        # For Dental CBCT, often has windowing settings
        if hasattr(self.ds, 'WindowCenter'):
            new_ds.WindowCenter = self.ds.WindowCenter
        if hasattr(self.ds, 'WindowWidth'):
            new_ds.WindowWidth = self.ds.WindowWidth

        # Handle pixel data
        if slice_data.dtype == np.uint16:
            new_ds.PixelData = slice_data.tobytes()
        else:
            # Normalize to uint16
            norm_data = ((slice_data - slice_data.min()) /
                        (slice_data.max() - slice_data.min()) * 65535)
            new_ds.PixelData = norm_data.astype(np.uint16).tobytes()

        # ===== SET FILE METADATA =====

        new_ds.file_meta = pydicom.Dataset()
        new_ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        new_ds.file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'  # CT Image Storage

        # Generate unique UID for this slice
        slice_uid = generate_uid()
        new_ds.file_meta.MediaStorageSOPInstanceUID = slice_uid
        new_ds.SOPInstanceUID = slice_uid
        new_ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.2'

        # Save the file
        pydicom.filewriter.write_file(
            str(output_file),
            new_ds,
            write_like_original=False
        )

    def _copy_essential_metadata(self, new_ds):
        """Copy essential metadata from original"""
        # Patient info
        if hasattr(self.ds, 'PatientID'):
            new_ds.PatientID = self.ds.PatientID
        if hasattr(self.ds, 'PatientName'):
            new_ds.PatientName = self.ds.PatientName
        if hasattr(self.ds, 'PatientBirthDate'):
            new_ds.PatientBirthDate = self.ds.PatientBirthDate
        if hasattr(self.ds, 'PatientSex'):
            new_ds.PatientSex = self.ds.PatientSex

        # Study info
        if hasattr(self.ds, 'StudyInstanceUID'):
            new_ds.StudyInstanceUID = self.ds.StudyInstanceUID
        if hasattr(self.ds, 'StudyDate'):
            new_ds.StudyDate = self.ds.StudyDate
        if hasattr(self.ds, 'StudyTime'):
            new_ds.StudyTime = self.ds.StudyTime

        # Series info
        if hasattr(self.ds, 'SeriesInstanceUID'):
            new_ds.SeriesInstanceUID = self.ds.SeriesInstanceUID
        if hasattr(self.ds, 'SeriesNumber'):
            new_ds.SeriesNumber = self.ds.SeriesNumber
        if hasattr(self.ds, 'SeriesDescription'):
            new_ds.SeriesDescription = self.ds.SeriesDescription

        # Modality and manufacturer
        if hasattr(self.ds, 'Modality'):
            new_ds.Modality = self.ds.Modality
        if hasattr(self.ds, 'Manufacturer'):
            new_ds.Manufacturer = self.ds.Manufacturer

    def _save_volume_info(self, output_path):
        """Save volume reconstruction information"""
        volume_info = {
            'original_file': str(self.input_path),
            'extraction_date': datetime.now().isoformat(),
            'volume_dimensions': {
                'slices': int(self.num_slices),
                'rows': int(self.volume.shape[1]),
                'columns': int(self.volume.shape[2])
            },
            'spacing': {
                'pixel_spacing': [float(x) for x in self.pixel_spacing],
                'slice_thickness': float(self.slice_thickness),
                'spacing_between_slices': float(self.spacing_between_slices)
            },
            'coordinate_system': {
                'image_position': self.image_position,
                'image_orientation': self.image_orientation,
                'slice_positions': self.slice_positions
            },
            'metadata': self.metadata
        }

        # Save as JSON
        with open(output_path / "volume_reconstruction_info.json", 'w') as f:
            json.dump(volume_info, f, indent=2, default=str)

        # Save as Python script for easy loading
        self._save_reconstruction_script(output_path, volume_info)

    def _save_reconstruction_script(self, output_path, volume_info):
        """Save a Python script to reconstruct the volume"""
        script = '''"""
Script to reconstruct 3D volume from extracted CBCT slices
"""

import pydicom
import numpy as np
import os
from pathlib import Path

def reconstruct_cbct_volume(slices_dir):
    """
    Reconstruct 3D volume from individual DICOM slices
    
    Args:
        slices_dir: Directory containing extracted DICOM slices
    
    Returns:
        3D numpy array and slice positions
    """
    slices_dir = Path(slices_dir)
    
    # Get all DICOM files
    dcm_files = sorted(slices_dir.glob("slice_*.dcm"))
    
    if not dcm_files:
        raise ValueError(f"No DICOM slices found in {slices_dir}")
    
    print(f"Found {len(dcm_files)} slices")
    
    # Read first slice to get dimensions
    first_slice = pydicom.dcmread(str(dcm_files[0]))
    rows = first_slice.Rows
    cols = first_slice.Columns
    
    # Create empty volume
    volume = np.zeros((len(dcm_files), rows, cols), dtype=np.uint16)
    slice_positions = []
    
    # Load all slices
    for i, dcm_file in enumerate(dcm_files):
        ds = pydicom.dcmread(str(dcm_file))
        
        # Store slice data
        volume[i] = ds.pixel_array
        
        # Store slice position
        if hasattr(ds, 'ImagePositionPatient'):
            position = [float(x) for x in ds.ImagePositionPatient]
            slice_positions.append(position)
    
    print(f"Reconstructed volume shape: {volume.shape}")
    
    return volume, slice_positions

def create_mha_file(volume, output_path, spacing):
    """
    Create MHA file for 3D visualization (e.g., in 3D Slicer)
    
    Args:
        volume: 3D numpy array
        output_path: Path to save .mha file
        spacing: Tuple of (x_spacing, y_spacing, z_spacing)
    """
    try:
        import SimpleITK as sitk
        
        # Create SimpleITK image
        img = sitk.GetImageFromArray(volume)
        
        # Set spacing
        img.SetSpacing(spacing)
        
        # Save as MHA
        sitk.WriteImage(img, str(output_path))
        print(f"Saved MHA file: {output_path}")
        
    except ImportError:
        print("Install SimpleITK for MHA export: pip install SimpleITK")

# ===== USAGE =====
if __name__ == "__main__":
    # Point to your extracted slices directory
    SLICES_DIR = "."

    # Reconstruct volume
    volume, positions = reconstruct_cbct_volume(SLICES_DIR)
    
    # Save volume as numpy file
    np.save("reconstructed_volume.npy", volume)
    print("Saved reconstructed_volume.npy")
    
    # Optional: Create MHA for 3D Slicer
    # create_mha_file(volume, "volume.mha", (0.15, 0.15, 0.15))
'''

        with open(output_path / "reconstruct_volume.py", 'w') as f:
            f.write(script)

        # Make it executable
        os.chmod(output_path / "reconstruct_volume.py", 0o755)

    def extract_for_3d_slicer(self, output_dir=None):
        """
        Extract in format ready for 3D Slicer
        """
        if output_dir is None:
            output_dir = f"cbct_3dslicer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Extract with 3D coordinates
        self.extract_with_3d_coordinates(output_dir)

        # Also save as NIfTI for 3D Slicer
        self._save_as_nifti(output_path)

        return output_path

    def _save_as_nifti(self, output_path):
        """Save as NIfTI format (for 3D Slicer, ITK-SNAP)"""
        try:
            import nibabel as nib

            # Create affine matrix from DICOM orientation
            affine = np.eye(4)

            # Set pixel spacing
            affine[0, 0] = float(self.pixel_spacing[0])
            affine[1, 1] = float(self.pixel_spacing[1])
            affine[2, 2] = float(self.spacing_between_slices)

            # Create NIfTI image
            nifti_img = nib.Nifti1Image(self.volume, affine)

            # Save
            nifti_path = output_path / "cbct_volume.nii.gz"
            nib.save(nifti_img, nifti_path)

            print(f"✅ Saved NIfTI: {nifti_path}")

        except ImportError:
            print("⚠️  Install nibabel for NIfTI export: pip install nibabel")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    print("=" * 70)
    print("DENTAL CBCT 3D SLICE EXTRACTOR")
    print("=" * 70)

    # ===== SET YOUR FILE PATH HERE =====
    CBCT_FILE = "D:/Dental CBCT/ImplaStation-DEMO-DICOM.dcm"

    # Or use command line argument
    import sys
    if len(sys.argv) > 1:
        CBCT_FILE = sys.argv[1]

    print(f"Input file: {CBCT_FILE}")

    # Check file exists
    if not Path(CBCT_FILE).exists():
        print(f"\n❌ File not found: {CBCT_FILE}")
        print("\n💡 Please provide the correct path to your CBCT DICOM file")
        return

    # Create extractor
    extractor = CBCTSliceExtractor(CBCT_FILE)

    try:
        # Load data
        volume = extractor.load_cbct_data()

        print("\n" + "=" * 70)
        print("EXPORT OPTIONS:")
        print("=" * 70)
        print("1. Extract with 3D coordinates (for custom reconstruction)")
        print("2. Extract for 3D Slicer (includes NIfTI)")
        print("3. Quick preview of volume")
        print("=" * 70)

        choice = input("\nChoose option (1-3): ").strip()

        if choice == '1':
            output = extractor.extract_with_3d_coordinates()
        elif choice == '2':
            output = extractor.extract_for_3d_slicer()
        elif choice == '3':
            preview_cbct_volume(volume)
            return
        else:
            print("Defaulting to option 1...")
            output = extractor.extract_with_3d_coordinates()

        print(f"\n✅ DONE! Files saved in: {output}")
        print("\n📋 To reconstruct 3D volume, run:")
        print(f"   cd \"{output}\"")
        print(f"   python reconstruct_volume.py")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def preview_cbct_volume(volume):
    """Quick preview of CBCT volume"""
    try:
        import matplotlib.pyplot as plt

        print("\n📊 Volume preview...")

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        # Axial view (middle slice)
        axial_slice = volume[volume.shape[0] // 2]
        axes[0].imshow(axial_slice, cmap='gray')
        axes[0].set_title(f'Axial (Slice {volume.shape[0] // 2})')
        axes[0].axis('off')

        # Sagittal view (middle column)
        sagittal_slice = volume[:, :, volume.shape[2] // 2]
        axes[1].imshow(sagittal_slice.T, cmap='gray', aspect='auto')
        axes[1].set_title('Sagittal')
        axes[1].axis('off')

        # Coronal view (middle row)
        coronal_slice = volume[:, volume.shape[1] // 2, :]
        axes[2].imshow(coronal_slice.T, cmap='gray', aspect='auto')
        axes[2].set_title('Coronal')
        axes[2].axis('off')

        plt.tight_layout()
        plt.show()

        print(f"Volume shape: {volume.shape}")
        print(f"Intensity range: {volume.min()} to {volume.max()}")

    except ImportError:
        print("Install matplotlib for preview: pip install matplotlib")

# ============================================================================
# QUICK FIX - If above doesn't work
# ============================================================================

def quick_cbct_fix(input_file, output_dir="cbct_fixed"):
    """
    Quick fix for CBCT volume reconstruction
    """
    print("🔄 Applying quick fix for CBCT volume...")

    ds = pydicom.dcmread(input_file, force=True)
    volume = ds.pixel_array

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"Volume shape: {volume.shape}")

    # Save as raw volume with metadata
    volume.tofile(output_path / "volume.raw")

    # Save shape and spacing
    with open(output_path / "volume_info.txt", 'w') as f:
        f.write(f"Shape: {volume.shape}\n")
        f.write(f"Data type: {volume.dtype}\n")

        # Try to get spacing
        if hasattr(ds, 'PixelSpacing'):
            f.write(f"Pixel spacing: {ds.PixelSpacing}\n")
        if hasattr(ds, 'SliceThickness'):
            f.write(f"Slice thickness: {ds.SliceThickness}\n")

    print(f"✅ Saved raw volume to: {output_path}")
    print("💡 Load in Python with:")
    print(f"   data = np.fromfile('{output_path}/volume.raw', dtype=np.{volume.dtype})")
    print(f"   data = data.reshape({volume.shape})")

if __name__ == "__main__":
    main()