import os
import numpy as np
import matplotlib.pyplot as plt
import re

# Define folder path and image parameters
folder_path = "D:/dummymotion/Normalizepath-Not working"  # Update this with your folder path
width, height = 1536, 1536  # Update based on your image size
dtype = np.uint16  # RAW images usually use 16-bit unsigned integer

# Define Rescale Slope and Intercept (Modify if known from DICOM)
RescaleSlope = 1  # Usually from DICOM metadata
RescaleIntercept = -1024  # Default for CT scans


# Function for natural sorting of filenames
def natural_sort_key(text):
    return [int(num) if num.isdigit() else num for num in re.split(r'(\d+)', text)]


# Get all raw files and sort them naturally
files = [f for f in os.listdir(folder_path) if f.endswith(".raw")]
files.sort(key=natural_sort_key)  # Sort filenames correctly

# Process each image
intensity_results = []

for file_name in files:
    file_path = os.path.join(folder_path, file_name)

    # Read the raw image
    raw_data = np.fromfile(file_path, dtype=dtype)
    image = raw_data.reshape((height, width))  # Reshape image

    # ✅ Fix: Convert to int16 to prevent overflow
    image = image.astype(np.int16)

    # Convert to Hounsfield Units (HU)
    hu_image = (image * RescaleSlope) + RescaleIntercept

    # Compute HU metrics
    mean_hu = np.mean(hu_image)
    max_hu = np.max(hu_image)
    min_hu = np.min(hu_image)
    std_hu = np.std(hu_image)

    # Store results
    intensity_results.append({
        "filename": file_name,
        "mean_HU": mean_hu,
        "max_HU": max_hu,
        "min_HU": min_hu,
        "std_HU": std_hu
    })

    # Display the first HU image (optional)
    if file_name == files[0]:
        plt.imshow(hu_image, cmap='gray')
        plt.colorbar(label="Hounsfield Units (HU)")
        plt.title(f"Sample HU Image: {file_name}")
        plt.show()

# Print results in correct order
for result in intensity_results:
    print(f"File: {result['filename']}")
    print(f"  Mean HU: {result['mean_HU']}")
    print(f"  Max HU: {result['max_HU']}")
    print(f"  Min HU: {result['min_HU']}")
    print(f"  Standard Deviation HU: {result['std_HU']}\n")
