import SimpleITK as sitk
import numpy as np
import pydicom
from pathlib import Path
import logging


class SimpleITKVolumeResampler:
    """Resampler using SimpleITK for better medical image handling."""

    def __init__(self, input_dicom_dir: str, input_rtstruct_path: str, output_dir: str):
        self.input_dicom_dir = Path(input_dicom_dir)
        self.input_rtstruct_path = Path(input_rtstruct_path)
        self.output_dir = Path(output_dir)

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Create output directories
        for size in [(128, 128), (256, 256)]:
            (self.output_dir / f"{size[0]}x{size[1]}").mkdir(parents=True, exist_ok=True)

    def read_dicom_series(self) -> sitk.Image:
        """Read DICOM series as SimpleITK image."""
        reader = sitk.ImageSeriesReader()
        dicom_names = reader.GetGDCMSeriesFileNames(str(self.input_dicom_dir))
        reader.SetFileNames(dicom_names)
        image = reader.Execute()
        self.logger.info(f"Read volume: {image.GetSize()}")
        return image

    def resample_image(self, image: sitk.Image, target_size: tuple) -> sitk.Image:
        """Resample image to target size."""
        original_size = image.GetSize()
        original_spacing = image.GetSpacing()

        # Calculate new spacing
        new_spacing = [
            original_spacing[0] * (original_size[0] / target_size[0]),
            original_spacing[1] * (original_size[1] / target_size[1]),
            original_spacing[2]
        ]

        # Create resampler
        resampler = sitk.ResampleImageFilter()
        resampler.SetSize([target_size[0], target_size[1], original_size[2]])
        resampler.SetOutputSpacing(new_spacing)
        resampler.SetOutputOrigin(image.GetOrigin())
        resampler.SetOutputDirection(image.GetDirection())
        resampler.SetInterpolator(sitk.sitkLinear)

        resampled = resampler.Execute(image)
        self.logger.info(f"Resampled to: {resampled.GetSize()}")

        return resampled

    def save_as_dicom(self, image: sitk.Image, output_dir: Path):
        """Save SimpleITK image as DICOM series."""
        # Convert to DICOM series
        writer = sitk.ImageSeriesWriter()

        # Get original DICOM tags from first file
        first_dicom = next(self.input_dicom_dir.glob("*.dcm"))
        reader = sitk.ImageFileReader()
        reader.SetFileName(str(first_dicom))
        reader.LoadPrivateTagsOn()
        reader.ReadImageInformation()

        # Copy tags to resampled image
        for key in reader.GetMetaDataKeys():
            image.SetMetaData(key, reader.GetMetaData(key))

        # Update image size tags
        image.SetMetaData("0028|0010", str(image.GetSize()[1]))  # Rows
        image.SetMetaData("0028|0011", str(image.GetSize()[0]))  # Columns
        image.SetMetaData("0028|0030", f"{image.GetSpacing()[0]}\\{image.GetSpacing()[1]}")  # Pixel Spacing

        # Write series
        writer.SetFileNames([str(output_dir / f"slice_{i:04d}.dcm")
                             for i in range(image.GetSize()[2])])
        writer.Execute(image)

        self.logger.info(f"Saved DICOM series to {output_dir}")

    def process(self):
        """Main processing function."""
        self.logger.info("Reading DICOM series...")
        image = self.read_dicom_series()

        for target_size in [(128, 128), (256, 256)]:
            self.logger.info(f"\nResampling to {target_size[0]}x{target_size[1]}...")

            # Resample
            resampled = self.resample_image(image, target_size)

            # Save
            output_subdir = self.output_dir / f"{target_size[0]}x{target_size[1]}"
            self.save_as_dicom(resampled, output_subdir)

            # Copy and resample RTSTRUCT (simplified)
            self.copy_and_update_rtstruct(target_size, output_subdir)

    def copy_and_update_rtstruct(self, target_size: tuple, output_dir: Path):
        """Copy RTSTRUCT and update contour coordinates."""
        rtstruct = pydicom.dcmread(str(self.input_rtstruct_path))

        # Calculate scale factors
        original_dicom = next(self.input_dicom_dir.glob("*.dcm"))
        ds = pydicom.dcmread(str(original_dicom))
        original_size = (ds.Rows, ds.Columns)

        scale_x = target_size[1] / original_size[1]
        scale_y = target_size[0] / original_size[0]

        # Update contours
        if hasattr(rtstruct, 'ROIContourSequence'):
            for roi in rtstruct.ROIContourSequence:
                if hasattr(roi, 'ContourSequence'):
                    for contour in roi.ContourSequence:
                        points = np.array(contour.ContourData).reshape(-1, 3)
                        points[:, 0] *= scale_x
                        points[:, 1] *= scale_y
                        contour.ContourData = points.flatten().tolist()

        # Save
        rtstruct.save_as(str(output_dir / "rtstruct.dcm"))
        self.logger.info(f"Saved RTSTRUCT to {output_dir}")


if __name__ == "__main__":
    # Usage
    resampler = SimpleITKVolumeResampler(
        input_dicom_dir="/path/to/512/dicom/slices/",
        input_rtstruct_path="/path/to/rtstruct.dcm",
        output_dir="/path/to/output/"
    )
    resampler.process()