import os
import numpy as np
import matplotlib.pyplot as plt
import re

# Define folder path and image parameters
folder_path = "D:/dummymotion/Modified intensity"  # Update this with your folder path
width, height = 1536, 1536  # Update based on image size
dtype = np.uint16  # Update based on bit-depth


# Function for natural sorting
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

    # Compute intensity metrics
    mean_intensity = np.mean(image)
    max_intensity = np.max(image)
    min_intensity = np.min(image)
    std_intensity = np.std(image)

    # Store results
    intensity_results.append({
        "filename": file_name,
        "mean_intensity": mean_intensity,
        "max_intensity": max_intensity,
        "min_intensity": min_intensity,
        "std_intensity": std_intensity
    })

    # Display the first image (optional)
    if file_name == files[0]:
        plt.imshow(image, cmap='gray')
        plt.colorbar(label="Intensity")
        plt.title(f"Sample Image: {file_name}")
        plt.show()

# Print results in correct order
for result in intensity_results:
    print(f"File: {result['filename']}")
    print(f"  Mean Intensity: {result['mean_intensity']}")
    print(f"  Max Intensity: {result['max_intensity']}")
    print(f"  Min Intensity: {result['min_intensity']}")
    print(f"  Standard Deviation: {result['std_intensity']}\n")
