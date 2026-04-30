import os
import numpy as np
import matplotlib.pyplot as plt
import re

# Define paths
input_folder = "D:/dummymotion/Normalizepath-Not working"  # Update with your input folder path
output_folder = "D:/dummymotion/Modified intensity"  # Update with your output folder path

# Ensure output folder exists
os.makedirs(output_folder, exist_ok=True)

# Image parameters
width, height = 1536, 1536  # Update based on image size
dtype = np.uint16  # Update based on bit-depth
intensity_reduction = 100  # Value to subtract


# Function for natural sorting
def natural_sort_key(text):
    return [int(num) if num.isdigit() else num for num in re.split(r'(\d+)', text)]


# Get all raw files and sort them naturally
files = [f for f in os.listdir(input_folder) if f.endswith(".raw")]
files.sort(key=natural_sort_key)  # Sort filenames correctly

# Process each image
intensity_results = []

for file_name in files:
    input_path = os.path.join(input_folder, file_name)
    output_path = os.path.join(output_folder, file_name)  # Output file path

    # Read the raw image
    raw_data = np.fromfile(input_path, dtype=dtype)
    image = raw_data.reshape((height, width))  # Reshape image

    # Reduce intensity safely (avoid negative values)
    adjusted_image = np.maximum(image - intensity_reduction, 0)

    # Compute intensity metrics
    mean_intensity = np.mean(adjusted_image)
    max_intensity = np.max(adjusted_image)
    min_intensity = np.min(adjusted_image)
    std_intensity = np.std(adjusted_image)

    # Store results
    intensity_results.append({
        "filename": file_name,
        "mean_intensity": mean_intensity,
        "max_intensity": max_intensity,
        "min_intensity": min_intensity,
        "std_intensity": std_intensity
    })

    # Save the adjusted image
    adjusted_image.astype(dtype).tofile(output_path)

    # Display the first image (optional)
    if file_name == files[0]:
        plt.imshow(adjusted_image, cmap='gray')
        plt.colorbar(label="Intensity")
        plt.title(f"Sample Image (Reduced Intensity): {file_name}")
        plt.show()

# Print results in correct order
for result in intensity_results:
    print(f"File: {result['filename']}")
    print(f"  Mean Intensity: {result['mean_intensity']}")
    print(f"  Max Intensity: {result['max_intensity']}")
    print(f"  Min Intensity: {result['min_intensity']}")
    print(f"  Standard Deviation: {result['std_intensity']}\n")

print(f"\n✅ Process completed! Adjusted images saved in: {output_folder}")
