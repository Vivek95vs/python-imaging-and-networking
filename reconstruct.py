import os
import numpy as np
import SimpleITK as sitk

def load_raw_slices(folder_path, width=1536, height=1536, dtype=np.uint16):
    files = sorted([f for f in os.listdir(folder_path) if f.endswith('.raw')])
    volume = []

    for file in files:
        file_path = os.path.join(folder_path, file)
        data = np.fromfile(file_path, dtype=dtype).reshape((height, width))
        volume.append(data)

    volume_array = np.stack(volume, axis=0)  # Shape: (slices, height, width)
    return volume_array

def convert_to_sitk(volume_array, spacing=(1.0, 1.0, 2.5)):  # Original spacing (x, y, z)
    img = sitk.GetImageFromArray(volume_array)  # Converts numpy (z,y,x) -> sitk image
    img.SetSpacing(spacing)
    return img

def resample_volume(sitk_image, new_spacing=(1.0, 1.0, 1.0)):
    original_spacing = sitk_image.GetSpacing()
    original_size = sitk_image.GetSize()

    new_size = [
        int(round(original_size[0] * (original_spacing[0] / new_spacing[0]))),
        int(round(original_size[1] * (original_spacing[1] / new_spacing[1]))),
        int(round(original_size[2] * (original_spacing[2] / new_spacing[2])))
    ]

    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing(new_spacing)
    resampler.SetSize(new_size)
    resampler.SetOutputDirection(sitk_image.GetDirection())
    resampler.SetOutputOrigin(sitk_image.GetOrigin())
    resampler.SetInterpolator(sitk.sitkLinear)

    return resampler.Execute(sitk_image)

# ----------------------------
# 🔧 Parameters
raw_folder = "D:/Iray Bunker test/HU/120_80_25/Raw1"
image_width = 1536
image_height = 1536
pixel_dtype = np.uint16  # or np.uint8
original_spacing = (1.0, 1.0, 2.5)  # (x, y, z) in mm
new_spacing = (1.0, 1.0, 1.0)

# ----------------------------
# 📥 Load and Resample
volume_np = load_raw_slices(raw_folder, image_width, image_height, pixel_dtype)
volume_sitk = convert_to_sitk(volume_np, spacing=original_spacing)
resampled_volume = resample_volume(volume_sitk, new_spacing)

# ----------------------------
# 💾 Save
sitk.WriteImage(resampled_volume, "resampled_volume.nii.gz")
print("✅ Volume resampled and saved.")
