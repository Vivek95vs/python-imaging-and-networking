# import os
# import SimpleITK as sitk
#
# # --- INPUT ---
# input_folder = r"D:\\swami siddha\\CBCT1"   # Folder containing original DICOM slices
# output_folder = r"D:\\swami siddha\\output" # Folder for resampled DICOMs
# os.makedirs(output_folder, exist_ok=True)
#
# # --- READ DICOM SERIES ---
# reader = sitk.ImageSeriesReader()
# dicom_names = reader.GetGDCMSeriesFileNames(input_folder)
# reader.SetFileNames(dicom_names)
# image = reader.Execute()
#
# print("Original size:", image.GetSize())
# print("Original spacing:", image.GetSpacing())
#
# # --- TARGET PARAMETERS ---
# new_size = [128, 128, 128]
#
# # Compute new spacing from original spacing and sizes
# orig_size = image.GetSize()
# orig_spacing = image.GetSpacing()
# new_spacing = [
#     orig_spacing[0] * (orig_size[0] / new_size[0]),
#     orig_spacing[1] * (orig_size[1] / new_size[1]),
#     orig_spacing[2] * (orig_size[2] / new_size[2])
# ]
# print("New spacing:", new_spacing)
#
# # --- RESAMPLE IMAGE ---
# resampler = sitk.ResampleImageFilter()
# resampler.SetOutputSpacing(new_spacing)
# resampler.SetSize(new_size)
# resampler.SetInterpolator(sitk.sitkLinear)
# resampler.SetOutputOrigin(image.GetOrigin())
# resampler.SetOutputDirection(image.GetDirection())
# resampled_image = resampler.Execute(image)
#
# print("Resampled size:", resampled_image.GetSize())
#
# # --- SAVE AS DICOM SERIES ---
# # Use the metadata of the original series as a base
# writer = sitk.ImageFileWriter()
# for i in range(resampled_image.GetDepth()):
#     slice_i = resampled_image[:,:,i]
#     slice_i = sitk.Cast(slice_i, sitk.sitkInt16)
#
#     # Copy original DICOM tags from one of the source files
#     original_meta = sitk.ReadImage(dicom_names[min(i, len(dicom_names)-1)])
#     for k in original_meta.GetMetaDataKeys():
#         slice_i.SetMetaData(k, original_meta.GetMetaData(k))
#
#     # Update required geometry tags
#     slice_i.SetMetaData("0028|0030", f"{new_spacing[1]}\\{new_spacing[0]}")  # PixelSpacing
#     slice_i.SetMetaData("0018|0050", str(new_spacing[2]))  # SliceThickness
#     slice_i.SetMetaData("0020|0013", str(i + 1))           # InstanceNumber
#
#     # Output filename
#     filename = os.path.join(output_folder, f"IM_{i:04d}.dcm")
#     writer.SetFileName(filename)
#     writer.Execute(slice_i)
#
# print("✅ Resampled DICOM series saved to:", output_folder)

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# import os
# import SimpleITK as sitk
#
# # --- INPUT ---
# input_folder = r"D:\\swami siddha\\CBCT1"   # Folder with original DICOM series
# output_folder = r"D:\\swami siddha\\output" # Folder for output resampled series
# os.makedirs(output_folder, exist_ok=True)
#
# # --- READ DICOM SERIES ---
# reader = sitk.ImageSeriesReader()
# dicom_names = reader.GetGDCMSeriesFileNames(input_folder)
# reader.SetFileNames(dicom_names)
# image = reader.Execute()
#
# print("Original size:", image.GetSize())
# print("Original spacing:", image.GetSpacing())
#
# # --- TARGET PARAMETERS ---
# target_size = [128, 128, 128]
#
# orig_size = image.GetSize()
# orig_spacing = image.GetSpacing()
#
# # Compute new spacing to preserve physical dimensions
# new_spacing = [
#     orig_spacing[0] * (orig_size[0] / target_size[0]),
#     orig_spacing[1] * (orig_size[1] / target_size[1]),
#     orig_spacing[2] * (orig_size[2] / target_size[2])
# ]
# print("New spacing:", new_spacing)
#
# # --- RESAMPLE IMAGE (using high-quality BSpline) ---
# resampler = sitk.ResampleImageFilter()
# resampler.SetInterpolator(sitk.sitkBSpline)
# resampler.SetOutputSpacing(new_spacing)
# resampler.SetSize(target_size)
# resampler.SetOutputOrigin(image.GetOrigin())
# resampler.SetOutputDirection(image.GetDirection())
# resampled = resampler.Execute(image)
#
# # --- OPTIONAL: Apply mild sharpening ---
# # Unsharp masking to enhance edges
# resampled_f = sitk.Cast(resampled, sitk.sitkFloat32)
# gaussian = sitk.SmoothingRecursiveGaussian(resampled_f, sigma=0.5)
#
# # Unsharp masking: enhance edges slightly
# sharpened_f = resampled_f * 1.5 - gaussian * 0.5
#
# # Clip values to valid range and cast back to int16
# sharpened = sitk.Cast(sitk.Clamp(sharpened_f, lowerBound=-32768, upperBound=32767), sitk.sitkInt16)
#
# print("Resampled size:", sharpened.GetSize())
#
# # --- SAVE AS DICOM SERIES ---
# writer = sitk.ImageFileWriter()
# for i in range(sharpened.GetDepth()):
#     slice_i = sharpened[:,:,i]
#     slice_i = sitk.Cast(slice_i, sitk.sitkInt16)
#
#     original_meta = sitk.ReadImage(dicom_names[min(i, len(dicom_names)-1)])
#     for k in original_meta.GetMetaDataKeys():
#         slice_i.SetMetaData(k, original_meta.GetMetaData(k))
#
#     slice_i.SetMetaData("0028|0030", f"{new_spacing[1]}\\{new_spacing[0]}")  # Pixel Spacing
#     slice_i.SetMetaData("0018|0050", str(new_spacing[2]))                    # Slice Thickness
#     slice_i.SetMetaData("0020|0013", str(i + 1))                             # Instance Number
#
#     filename = os.path.join(output_folder, f"IM_{i:04d}.dcm")
#     writer.SetFileName(filename)
#     writer.Execute(slice_i)
#
# print("✅ High-quality resampled DICOM series saved to:", output_folder)
# ///////////////////////////////////////////////////////////////////////////////////////////////////////////////

# import os
# import SimpleITK as sitk
#
# # --- INPUT ---
# input_folder = r"D:\\swami siddha\\CBCT1"
# output_folder = r"D:\\swami siddha\\output"
# os.makedirs(output_folder, exist_ok=True)
#
# # --- READ ORIGINAL DICOM SERIES ---
# reader = sitk.ImageSeriesReader()
# dicom_names = reader.GetGDCMSeriesFileNames(input_folder)
# reader.SetFileNames(dicom_names)
# image = reader.Execute()
#
# print("Original size:", image.GetSize())
# print("Original spacing:", image.GetSpacing())
#
# orig_size = image.GetSize()
# orig_spacing = image.GetSpacing()
#
# # --- STEP 1: Apply slight edge-preserving smoothing (to prevent aliasing) ---
# smoothed = sitk.CurvatureFlow(image1=image, timeStep=0.125, numberOfIterations=5)
#
# # --- STEP 2: First resample to 256³ ---
# first_size = [256, 256, 256]
# first_spacing = [
#     orig_spacing[0] * (orig_size[0] / first_size[0]),
#     orig_spacing[1] * (orig_size[1] / first_size[1]),
#     orig_spacing[2] * (orig_size[2] / first_size[2])
# ]
#
# resampler = sitk.ResampleImageFilter()
# resampler.SetInterpolator(sitk.sitkBSpline)
# resampler.SetOutputSpacing(first_spacing)
# resampler.SetSize(first_size)
# resampler.SetOutputOrigin(image.GetOrigin())
# resampler.SetOutputDirection(image.GetDirection())
# image_256 = resampler.Execute(smoothed)
#
# # --- STEP 3: Then resample from 256³ → 128³ ---
# second_size = [128, 128, 128]
# second_spacing = [
#     first_spacing[0] * (first_size[0] / second_size[0]),
#     first_spacing[1] * (first_size[1] / second_size[1]),
#     first_spacing[2] * (first_size[2] / second_size[2])
# ]
#
# resampler.SetOutputSpacing(second_spacing)
# resampler.SetSize(second_size)
# image_128 = resampler.Execute(image_256)
#
# # --- STEP 4: Apply mild sharpening (optional) ---
# resampled_f = sitk.Cast(image_128, sitk.sitkFloat32)
# gaussian = sitk.SmoothingRecursiveGaussian(resampled_f, sigma=0.5)
# sharpened_f = resampled_f * 1.3 - gaussian * 0.3
# sharpened = sitk.Cast(
#     sitk.Clamp(
#         sharpened_f,
#         lowerBound=-32768,
#         upperBound=32767
#     ),
#     sitk.sitkInt16
# )
#
# print("Final resampled size:", sharpened.GetSize())
# print("Final spacing:", second_spacing)
#
# # --- STEP 5: Write as DICOM ---
# writer = sitk.ImageFileWriter()
# for i in range(sharpened.GetDepth()):
#     slice_i = sharpened[:,:,i]
#     slice_i = sitk.Cast(slice_i, sitk.sitkInt16)
#
#     original_meta = sitk.ReadImage(dicom_names[min(i, len(dicom_names)-1)])
#     for k in original_meta.GetMetaDataKeys():
#         slice_i.SetMetaData(k, original_meta.GetMetaData(k))
#
#     slice_i.SetMetaData("0028|0030", f"{second_spacing[1]}\\{second_spacing[0]}")  # Pixel spacing
#     slice_i.SetMetaData("0018|0050", str(second_spacing[2]))                        # Slice thickness
#     slice_i.SetMetaData("0020|0013", str(i + 1))                                    # Instance number
#
#     filename = os.path.join(output_folder, f"IM_{i:04d}.dcm")
#     writer.SetFileName(filename)
#     writer.Execute(slice_i)
#
# print("✅ High-quality downsampled DICOM series saved:", output_folder)
# //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# import pydicom
# import numpy as np
# import os
# from scipy import ndimage
# from skimage.transform import resize
# import glob
#
#
# def resize_dicom_volume(input_folder, output_folder, new_size=(128, 128)):
#     """
#     Resize 3D DICOM volume and adjust slice thickness accordingly
#
#     Parameters:
#     input_folder: Path to folder containing input DICOM files
#     output_folder: Path to folder where resized DICOM files will be saved
#     new_size: Target 2D slice size (width, height)
#     """
#
#     # Create output folder if it doesn't exist
#     os.makedirs(output_folder, exist_ok=True)
#
#     # Read all DICOM files
#     dicom_files = glob.glob(os.path.join(input_folder, "*.dcm"))
#     if not dicom_files:
#         print(f"No DICOM files found in {input_folder}")
#         return
#
#     # Read and sort DICOM files by instance number
#     slices = []
#     for file_path in dicom_files:
#         try:
#             ds = pydicom.dcmread(file_path)
#             slices.append(ds)
#         except Exception as e:
#             print(f"Error reading {file_path}: {e}")
#
#     # Sort by instance number
#     slices.sort(key=lambda x: int(x.InstanceNumber))
#
#     if not slices:
#         print("No valid DICOM slices found")
#         return
#
#     print(f"Original volume size: {len(slices)} slices")
#
#     # Get original dimensions and spacing
#     original_rows = slices[0].Rows
#     original_columns = slices[0].Columns
#     original_slice_thickness = float(slices[0].SliceThickness)
#     original_pixel_spacing = [float(x) for x in slices[0].PixelSpacing]
#
#     print(f"Original slice dimensions: {original_rows} x {original_columns}")
#     print(f"Original slice thickness: {original_slice_thickness} mm")
#     print(f"Original pixel spacing: {original_pixel_spacing} mm")
#
#     # Extract pixel data
#     pixel_data = []
#     for slice_ds in slices:
#         pixel_data.append(slice_ds.pixel_array)
#
#     # Convert to numpy array
#     volume_3d = np.stack(pixel_data, axis=0)
#     print(f"Original 3D volume shape: {volume_3d.shape}")
#
#     # Calculate scaling factors
#     scale_factor_x = new_size[0] / original_columns
#     scale_factor_y = new_size[1] / original_rows
#
#     # Calculate new slice thickness (maintain volume proportions)
#     # The scaling in Z direction should be proportional to XY scaling
#     avg_scale_factor = (scale_factor_x + scale_factor_y) / 2
#     new_slice_thickness = original_slice_thickness / avg_scale_factor
#
#     # Calculate new pixel spacing
#     new_pixel_spacing = [
#         original_pixel_spacing[0] / scale_factor_x,
#         original_pixel_spacing[1] / scale_factor_y
#     ]
#
#     print(f"Scale factors - X: {scale_factor_x:.3f}, Y: {scale_factor_y:.3f}")
#     print(f"New slice thickness: {new_slice_thickness:.3f} mm")
#     print(f"New pixel spacing: {[f'{x:.3f}' for x in new_pixel_spacing]} mm")
#
#     # Resize the 3D volume
#     print("Resizing volume...")
#     resized_volume = resize(
#         volume_3d,
#         (int(len(slices) / avg_scale_factor), new_size[1], new_size[0]),
#         mode='constant',
#         cval=volume_3d.min(),
#         anti_aliasing=True,
#         preserve_range=True
#     )
#
#     # Convert back to original data type
#     resized_volume = resized_volume.astype(volume_3d.dtype)
#     print(f"Resized 3D volume shape: {resized_volume.shape}")
#
#     # Create new DICOM files
#     print("Creating new DICOM files...")
#     for i in range(resized_volume.shape[0]):
#         # Use first slice as template
#         new_ds = slices[0].copy()
#
#         # Update image data
#         new_ds.Rows = new_size[1]
#         new_ds.Columns = new_size[0]
#         new_ds.PixelData = resized_volume[i].tobytes()
#
#         # Update spacing information
#         new_ds.PixelSpacing = [str(new_pixel_spacing[0]), str(new_pixel_spacing[1])]
#         new_ds.SliceThickness = str(new_slice_thickness)
#
#         # Update instance number and position
#         new_ds.InstanceNumber = str(i + 1)
#
#         # Update Image Position Patient if it exists
#         if hasattr(new_ds, 'ImagePositionPatient'):
#             original_pos = [float(x) for x in new_ds.ImagePositionPatient]
#             # Adjust Z position based on new slice thickness
#             original_pos[2] = float(slices[0].ImagePositionPatient[2]) + i * new_slice_thickness
#             new_ds.ImagePositionPatient = [str(x) for x in original_pos]
#
#         # Update other relevant tags
#         new_ds.SamplesPerPixel = 1
#         new_ds.PhotometricInterpretation = "MONOCHROME2"
#         new_ds.BitsAllocated = 16
#         new_ds.BitsStored = 16
#         new_ds.HighBit = 15
#
#         # Save new DICOM file
#         output_filename = f"resized_slice_{i + 1:04d}.dcm"
#         output_path = os.path.join(output_folder, output_filename)
#         new_ds.save_as(output_path)
#
#     print(f"Resized DICOM files saved to: {output_folder}")
#
#
# def alternative_resize_method(input_folder, output_folder, new_size=(128, 128)):
#     """
#     Alternative method using simple 2D resizing for each slice
#     """
#
#     os.makedirs(output_folder, exist_ok=True)
#
#     dicom_files = glob.glob(os.path.join(input_folder, "*.dcm"))
#     slices = []
#
#     for file_path in dicom_files:
#         try:
#             ds = pydicom.dcmread(file_path)
#             slices.append(ds)
#         except Exception as e:
#             print(f"Error reading {file_path}: {e}")
#
#     slices.sort(key=lambda x: int(x.InstanceNumber))
#
#     if not slices:
#         return
#
#     original_rows = slices[0].Rows
#     original_columns = slices[0].Columns
#     original_slice_thickness = float(slices[0].SliceThickness)
#     original_pixel_spacing = [float(x) for x in slices[0].PixelSpacing]
#
#     # Calculate scaling factors and new thickness
#     scale_factor_x = new_size[0] / original_columns
#     scale_factor_y = new_size[1] / original_rows
#     avg_scale_factor = (scale_factor_x + scale_factor_y) / 2
#     new_slice_thickness = original_slice_thickness / avg_scale_factor
#     new_pixel_spacing = [
#         original_pixel_spacing[0] / scale_factor_x,
#         original_pixel_spacing[1] / scale_factor_y
#     ]
#
#     print("Using alternative 2D resize method...")
#
#     for i, slice_ds in enumerate(slices):
#         new_ds = slice_ds.copy()
#
#         # Resize 2D slice
#         original_slice = slice_ds.pixel_array
#         resized_slice = resize(
#             original_slice,
#             new_size,
#             mode='constant',
#             cval=original_slice.min(),
#             anti_aliasing=True,
#             preserve_range=True
#         )
#         resized_slice = resized_slice.astype(original_slice.dtype)
#
#         # Update DICOM attributes
#         new_ds.Rows = new_size[1]
#         new_ds.Columns = new_size[0]
#         new_ds.PixelData = resized_slice.tobytes()
#         new_ds.PixelSpacing = [str(new_pixel_spacing[0]), str(new_pixel_spacing[1])]
#         new_ds.SliceThickness = str(new_slice_thickness)
#         new_ds.InstanceNumber = str(i + 1)
#
#         # Save
#         output_filename = f"resized_2d_slice_{i + 1:04d}.dcm"
#         output_path = os.path.join(output_folder, output_filename)
#         new_ds.save_as(output_path)
#
#     print(f"2D resized DICOM files saved to: {output_folder}")
#
#
# # Example usage
# if __name__ == "__main__":
#     # Set your input and output paths
#     input_dicom_folder = "D:\\swami siddha\\CBCT1"
#     output_dicom_folder = "D:\\swami siddha\\output"
#
#     # Method 1: 3D volume resize (recommended)
#     # resize_dicom_volume(input_dicom_folder, output_dicom_folder, new_size=(128, 128))
#
#     # Method 2: 2D slice-by-slice resize (alternative)
#     alternative_resize_method(input_dicom_folder + "_2d", output_dicom_folder + "_2d", new_size=(128, 128))
    # //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

import os
import SimpleITK as sitk

# --- INPUT ---
input_folder = r"D:\\swami siddha\\CBCT1"   # Folder containing original DICOM slices
output_folder = r"D:\\swami siddha\\output" # Folder for resampled DICOMs
os.makedirs(output_folder, exist_ok=True)

# --- READ DICOM SERIES ---
reader = sitk.ImageSeriesReader()
dicom_names = reader.GetGDCMSeriesFileNames(input_folder)
reader.SetFileNames(dicom_names)
image = reader.Execute()

print("Original size:", image.GetSize())
print("Original spacing:", image.GetSpacing())

# --- TARGET PARAMETERS ---
new_size = [256, 256, 256]

# Compute new spacing from original spacing and sizes
orig_size = image.GetSize()
orig_spacing = image.GetSpacing()
new_spacing = [
    orig_spacing[0] * (orig_size[0] / new_size[0]),
    orig_spacing[1] * (orig_size[1] / new_size[1]),
    orig_spacing[2] * (orig_size[2] / new_size[2])
]
print("New spacing:", new_spacing)

# --- RESAMPLE IMAGE ---
resampler = sitk.ResampleImageFilter()
resampler.SetOutputSpacing(new_spacing)
resampler.SetSize(new_size)
resampler.SetInterpolator(sitk.sitkLinear)
resampler.SetOutputOrigin(image.GetOrigin())
resampler.SetOutputDirection(image.GetDirection())
resampled_image = resampler.Execute(image)

print("Resampled size:", resampled_image.GetSize())

# --- SAVE AS DICOM SERIES ---
# Use the metadata of the original series as a base
writer = sitk.ImageFileWriter()
for i in range(resampled_image.GetDepth()):
    slice_i = resampled_image[:,:,i]
    slice_i = sitk.Cast(slice_i, sitk.sitkInt16)

    # Copy original DICOM tags from one of the source files
    original_meta = sitk.ReadImage(dicom_names[min(i, len(dicom_names)-1)])
    for k in original_meta.GetMetaDataKeys():
        slice_i.SetMetaData(k, original_meta.GetMetaData(k))

    # Update required geometry tags
    slice_i.SetMetaData("0028|0030", f"{new_spacing[1]}\\{new_spacing[0]}")  # PixelSpacing
    slice_i.SetMetaData("0018|0050", str(new_spacing[2]))  # SliceThickness
    slice_i.SetMetaData("0020|0013", str(i + 1))           # InstanceNumber

    # Output filename
    filename = os.path.join(output_folder, f"IM_{i:04d}.dcm")
    writer.SetFileName(filename)
    writer.Execute(slice_i)

print("✅ Resampled DICOM series saved to:", output_folder)
