from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from pathlib import Path
import json
import os
from PIL import Image, ImageTk


def show_error(message):
    """ Show an error message box. """
    messagebox.showerror("Error", message)


def combine_images(image_data, num_detectors, detector_height, detector_width, reading_direction):
    """
    Combine image data into a single image based on the reading direction.
    """
    print(1)
    # Image dimensions
    full_image_width = detector_width * num_detectors
    full_image_height = detector_height

    # Initialize the array for the combined image
    sum_image = np.zeros((full_image_height, full_image_width))

    if reading_direction == 'column':
        for row in image_data:
            detectors = np.split(row, num_detectors)
            # Empty image for the current row
            combined_image = np.zeros((full_image_height, full_image_width))

            # Place each detector's pixels side by side
            for i, detector in enumerate(detectors):
                detector_image = detector.reshape((detector_height, detector_width))
                combined_image[:, i * detector_width:(i + 1) * detector_width] = detector_image

            # Add to the array
            sum_image += combined_image

    elif reading_direction == 'row':
        for row in image_data:
            detectors = np.split(row, num_detectors)
            # Empty image for the current row
            combined_image = np.zeros((full_image_height, full_image_width))

            # Place each detector's pixels side by side
            for i, detector in enumerate(detectors):
                detector_image = detector.reshape((detector_width, detector_height)).T
                combined_image[:, i * detector_width:(i + 1) * detector_width] = detector_image

            # Add to the array
            sum_image += combined_image

    else:
        raise ValueError("Invalid reading direction. Use 'row' or 'column'.")

    return sum_image


# Function for no correction
def no_corrections(detector_model, SN, file_path, num_detectors, detector_height, detector_width, reading_direction,
                   start_index, end_index):
    try:
        print(2)
        if not os.path.isfile(file_path):
            raise ValueError("File path does not exist or is invalid.")

        data = np.loadtxt(file_path)
        ending_index = data.shape[0] - end_index

        # Check the data dimensions
        num_pixels_per_image = num_detectors * (detector_height * detector_width)
        assert data.shape[1] == num_pixels_per_image, (
            f"Expected data width to be {num_pixels_per_image}, but got {data.shape[1]}"
        )

        # Calculate the image dimensions
        full_image_width = detector_width * num_detectors
        full_image_height = detector_height

        # Initialize an array to accumulate the sum of all images
        sum_image = np.zeros((full_image_height, full_image_width))

        # Initialize an array to accumulate pixel values
        all_images = []

        for row in data[start_index:ending_index]:
            detectors = np.split(row, num_detectors)
            # Empty image for the current row
            combined_image = np.zeros((full_image_height, full_image_width))

            # Place each detector's pixels side by side
            for i, detector in enumerate(detectors):
                if reading_direction == 'row':
                    # Row by row: reshape directly
                    detector_image = detector.reshape((detector_height, detector_width))
                elif reading_direction == 'column':
                    # Column by column: reshape and then transpose
                    detector_image = detector.reshape((detector_width, detector_height)).T
                else:
                    raise ValueError("Invalid reading direction. Use 'row' or 'column'.")

                # Place the detector image into the combined image
                combined_image[:, i * detector_width:(i + 1) * detector_width] = detector_image

            # Add to the array
            sum_image += combined_image

        # Calculate average
        average_image = sum_image / len(data[start_index:ending_index])

        # Visualization of the averaged image
        bg_color = 'gainsboro'
        fig, ax = plt.subplots(figsize=(12, 8))
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        ax.imshow(average_image, cmap='gray', origin='upper')

        ax.set_title(
            f'Detector: {detector_model}\n'
            f'S/N: {SN}\n'
            '\n'
            'Reconstructed Image (No corrections)',
            fontsize=16, color='black'
        )

        ax.axis('off')

        plt.tight_layout()
        plt.show(block=False)
    except Exception as e:
        show_error(str(e))


# Function for dark correction only
def reconstruct_dark_correction_only(detector_model, SN, file_path, dark_image_path, num_detectors, detector_height,
                                     detector_width, reading_direction, start_index, end_index):
    """
    Calculate and visualize the average image with dark corrections from a .txt file containing multiple images.

    """
    print(3)
    try:
        if not os.path.isfile(file_path):
            raise ValueError("File path does not exist or is invalid.")

        dark_image = np.zeros((detector_height, detector_width)) if not dark_image_path else np.loadtxt(dark_image_path)

        file_path = Path(file_path).as_posix()
        dark_image_path = Path(dark_image_path).as_posix()

        # Load the images from the .txt files
        data = np.loadtxt(file_path)
        dark_image = np.loadtxt(dark_image_path)

        # Ensure shapes match
        assert data.shape == dark_image.shape, (
            "Data and dark image must have the same shape"
        )

        # Check the dimensions
        num_pixels_per_image = num_detectors * (detector_height * detector_width)
        assert data.shape[1] == num_pixels_per_image, (
            f"Expected data width to be {num_pixels_per_image}, but got {data.shape[1]}"
        )

        # Calculate the full image dimensions
        full_image_width = detector_width * num_detectors
        full_image_height = detector_height

        ending_index = data.shape[0] - end_index

        # Apply dark corrections to the entire dataset
        dark_averages = np.mean(dark_image[start_index:ending_index], axis=0)
        dark_correct = data - dark_averages

        # Initialize an array to accumulate the sum of all corrected images
        sum_image = np.zeros((full_image_height, full_image_width))

        for row in dark_correct[start_index:ending_index]:
            detectors = np.split(row, num_detectors)
            # Empty image for the current row
            combined_image = np.zeros((full_image_height, full_image_width))

            # Place each detector's pixels side by side
            for i, detector in enumerate(detectors):
                if reading_direction == 'row':
                    # Column by column: reshape directly
                    detector_image = detector.reshape((detector_height, detector_width))
                elif reading_direction == 'column':
                    # Row by row: reshape and then transpose
                    detector_image = detector.reshape((detector_width, detector_height)).T
                else:
                    raise ValueError("Invalid reading direction. Use 'row' or 'column'.")

                # Place the corrected detector image into the combined image
                combined_image[:, i * detector_width:(i + 1) * detector_width] = detector_image

            # Add to the array
            sum_image += combined_image

        # Calculate average
        average_image = sum_image / len(dark_correct[start_index:ending_index])

        # Visualize the image

        bg_color = 'gainsboro'
        fig, ax = plt.subplots(figsize=(12, 12))
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        ax.imshow(average_image, cmap='gray', origin='upper')

        ax.set_title(
            f'Detector: {detector_model}\n'
            f'S/N: {SN}\n'
            '\n'
            'Reconstructed Image (Only dark correction)',
            fontsize=16, color='black'
        )

        ax.axis('off')

        plt.tight_layout()
        plt.show(block=False)

    except Exception as e:
        show_error(str(e))


# Function for full correction
def reconstruct(detector_model, SN, file_path, dark_image_path, ff_image_path, num_detectors, detector_height,
                detector_width, reading_direction, start_index, end_index):
    """
    Reconstruct an image from any number of any sized detectors with dark and flat-field corrections + some calculations.
    """
    print(4)

    try:
        # Ensure all paths are valid and convert to posix paths
        if not os.path.isfile(file_path):
            raise ValueError("File path does not exist or is invalid.")

        file_path = Path(file_path).as_posix()
        dark_image_path = Path(dark_image_path).as_posix()
        ff_image_path = Path(ff_image_path).as_posix()

        # Load the images
        data = np.loadtxt(file_path)
        dark_images = np.loadtxt(dark_image_path)
        ff_images = np.loadtxt(ff_image_path)

        # Ensure shapes match
        assert data.shape[1] == dark_images.shape[1] == ff_images.shape[1], (
            "Data, dark images, and ff images must have the same width"
        )

        num_pixels_per_image = num_detectors * (detector_height * detector_width)
        assert data.shape[1] == num_pixels_per_image, (
            f"Expected data width to be {num_pixels_per_image}, but got {data.shape[1]}"
        )

        # Image dimensions
        full_image_width = detector_width * num_detectors
        full_image_height = detector_height

        ending_index = data.shape[0] - end_index

        # Calculate averages for each image stack discarding the first 'start_index' rows
        dark_averages = np.mean(dark_images[start_index:ending_index], axis=0)
        ff_averages = np.mean(ff_images[start_index:ending_index], axis=0)
        dark_stddevs = np.std(dark_images[start_index:ending_index], axis=0, ddof=1)

        # Dark correction for ff image and normalization
        dark_corrected_ff = ff_averages - dark_averages
        median_dark_corrected_ff = np.median(dark_corrected_ff)
        normalized_dark_corrected_ff = dark_corrected_ff / median_dark_corrected_ff

        # Dark and ff corrections for data
        dark_corrected_data = data - dark_averages
        corrected_data = np.divide(dark_corrected_data, normalized_dark_corrected_ff)

        # Array for corrected images
        sum_image = np.zeros((full_image_height, full_image_width))

        if reading_direction == 'row':
            for row in corrected_data[start_index:ending_index]:
                detectors = np.split(row, num_detectors)
                # Empty image for the current row
                combined_image = np.zeros((full_image_height, full_image_width))

                # Place each detector's pixels side by side
                for i, detector in enumerate(detectors):
                    detector_image = detector.reshape((detector_height, detector_width))
                    combined_image[:, i * detector_width:(i + 1) * detector_width] = detector_image

                # Add to the array
                sum_image += combined_image

        elif reading_direction == 'column':
            for row in corrected_data[start_index:ending_index]:
                detectors = np.split(row, num_detectors)
                # Empty image for the current row
                combined_image = np.zeros((full_image_height, full_image_width))

                # Place each detector's pixels side by side
                for i, detector in enumerate(detectors):
                    # Reshape, transpose, and then flip vertically
                    detector_image = detector.reshape(detector_width, detector_height).T
                    combined_image[:, i * detector_width:(i + 1) * detector_width] = detector_image

                # Add to the array
                sum_image += combined_image

        else:
            raise ValueError("Invalid reading direction. Use 'row' or 'column'.")

        # Calculate average
        average_image = sum_image / len(corrected_data[start_index:ending_index])

        # Calculate SNR for the dark-corrected flat-field image
        signal_ff = np.mean(dark_corrected_ff)
        noise_ff = np.std(dark_corrected_ff)
        snr_ff = signal_ff / noise_ff

        # Visualization
        bg_color = 'gainsboro'
        fig_reconstructed, ax_reconstructed = plt.subplots(figsize=(12, 12))
        fig_reconstructed.patch.set_facecolor(bg_color)
        ax_reconstructed.set_facecolor(bg_color)
        ax_reconstructed.imshow(average_image, cmap='gray', origin='upper')

        ax_reconstructed.set_title(
            f'Detector: {detector_model}\n'
            f'S/N: {SN}\n'
            '\n'
            'Reconstructed Image\n'
            f'Average Over {len(corrected_data[start_index:ending_index])} frames ({start_index}-{ending_index})'
        )
        ax_reconstructed.axis('off')
        plt.show(block=False)

        # Visualize pixel value deviations from the median. Relative to the min-max difference, does not have any spec.
        deviation_from_median = dark_corrected_ff - median_dark_corrected_ff
        min_deviation = np.min(deviation_from_median)
        max_deviation = np.max(deviation_from_median)

        # Reshape deviation_from_median according to the reading direction
        if reading_direction == 'row':
            deviation_from_median_reshaped = deviation_from_median.reshape(detector_height,
                                                                           detector_width * num_detectors)
        elif reading_direction == 'column':
            deviation_from_median_reshaped = deviation_from_median.reshape(num_detectors,
                                                                           detector_height * detector_width)
            deviation_from_median_reshaped = np.hstack([
                deviation_from_median_reshaped[i].reshape(detector_width, detector_height).T
                for i in range(num_detectors)
            ])
        else:
            raise ValueError("Invalid reading direction. Use 'row' or 'column'.")

        # Create color map with blue for negative deviations and red for positive
        deviation_colors = np.zeros((full_image_height, full_image_width, 3))

        # Set any pixels with zero deviation to a neutral greyish color
        neutral_color = 0.75
        deviation_colors[(deviation_from_median_reshaped == 0)] = [neutral_color, neutral_color, neutral_color]

        # Normalize using max deviation to ensure full color range is used
        blue_component = np.clip(np.abs(deviation_from_median_reshaped / min_deviation), 0, 1)
        red_component = np.clip(deviation_from_median_reshaped / max_deviation, 0, 1)

        # Set blue where deviations are negative, and red where positive
        deviation_colors[:, :, 2] = (deviation_from_median_reshaped < 0) * blue_component
        deviation_colors[:, :, 0] = (deviation_from_median_reshaped >= 0) * red_component

        fig_deviation, ax_deviation = plt.subplots(figsize=(12, 4))
        ax_deviation.imshow(deviation_colors, interpolation='nearest', aspect='equal')
        ax_deviation.set_title(f'Deviation from Median (Flat-field)\nSNR (Flat-field): {snr_ff:.2f}', fontsize=16,
                               color='black')
        ax_deviation.axis('off')
        plt.tight_layout()
        plt.show(block=False)

        # Calculate and plot averages against slices
        avg_reconstructed_image_columns = average_image.mean(axis=0)
        column_indices = np.arange(1, full_image_width + 1)

        # Adjust reshaping based on reading direction
        if reading_direction == 'row':
            dark_averages_reshaped = dark_averages.reshape(detector_height, detector_width * num_detectors)
            ff_averages_reshaped = ff_averages.reshape(detector_height, detector_width * num_detectors)
        elif reading_direction == 'column':
            dark_averages_reshaped = dark_averages.reshape(num_detectors, detector_height * detector_width)
            ff_averages_reshaped = ff_averages.reshape(num_detectors, detector_height * detector_width)
            dark_averages_reshaped = np.hstack([
                dark_averages_reshaped[i].reshape(detector_width, detector_height).T
                for i in range(num_detectors)
            ])
            ff_averages_reshaped = np.hstack([
                ff_averages_reshaped[i].reshape(detector_width, detector_height).T
                for i in range(num_detectors)
            ])
        else:
            raise ValueError("Invalid reading direction. Use 'row' or 'column'.")

        # Average over the height to get column averages
        dark_averages_columns = dark_averages_reshaped.mean(axis=0)
        ff_averages_columns = ff_averages_reshaped.mean(axis=0)

        # Plotting
        fig, ax = plt.subplots(figsize=(14, 8))
        ax.plot(column_indices, dark_averages_columns[:full_image_width], label='Dark Averages', color='black')
        ax.set_title('Dark Averages')
        ax.set_xlabel('Slice')
        ax.set_ylabel('Average Pixel Value')
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        plt.show(block=False)

        fig, ax = plt.subplots(figsize=(14, 8))
        ax.plot(column_indices, ff_averages_columns[:full_image_width], label='Flat-field Averages', color='blue')
        ax.set_title('Flat-field Averages')
        ax.set_xlabel('Slice')
        ax.set_ylabel('Average Pixel Value')
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        plt.show(block=False)

        fig, ax = plt.subplots(figsize=(14, 8))
        ax.plot(column_indices, avg_reconstructed_image_columns[:full_image_width], label='Reconstructed Averages',
                color='red')
        ax.set_title('Reconstructed Image Averages')
        ax.set_xlabel('Slice')
        ax.set_ylabel('Average Pixel Value')
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        plt.show(block=False)

    except Exception as e:
        show_error(str(e))

# --- NO CORRECTIONS: set your parameters and run ---

# Paths to your data (text files)
# file_path: a .txt with shape (num_frames, num_pixels_per_image)
# file_path = r"/path/to/data.txt"
file_path = r"D:/C-Arm/CT_Ref_DT/Machine shop test/New grab line by line/obj1.txt"
print(5)
# Geometry
num_detectors = 3                   # How many individual detector modules
detector_height = 32                # pixels
detector_width  = 32                # pixels
reading_direction = 'column'        # 'row' or 'column'

# Frame window (row indices in the data file)
# Uses data[start_index : (num_rows - end_index)]
# Set end_index = 0 to go all the way to the last row.
start_index = 0
end_index = 0

# Fully optional metadata, can be left empty
detector_model = 'model'
SN = 'sn'

# ---- Run ----
no_corrections(
    detector_model=detector_model,
    SN=SN,
    file_path=file_path,
    num_detectors=num_detectors,
    detector_height=detector_height,
    detector_width=detector_width,
    reading_direction=reading_direction,
    start_index=start_index,
    end_index=end_index
)

# --- DARK CORRECTION ONLY: set your parameters and run ---
print(6)
# Data paths
# file_path = r"/path/to/data.txt"            # same shape as below (width must match)
# dark_image_path = r"/path/to/dark_stack.txt"  # typically (num_dark_frames, num_pixels_per_image)
file_path = r"D:/C-Arm/CT_Ref_DT/Machine shop test/New grab line by line/obj1.txt"            # same shape as below (width must match)
dark_image_path = r"D:/C-Arm/CT_Ref_DT/dark_1000us_g0.txt"  # typically (num_dark_frames, num_pixels_per_image)
# Geometry
num_detectors = 3
detector_height = 32
detector_width  = 32
reading_direction = "row"    # 'row' or 'column'

# Frame window over BOTH data and dark stacks
start_index = 0
end_index = 0

# Fully optional metadata, can be left empty
detector_model = 'model'
SN = 'sn'

# ---- Run ----
reconstruct_dark_correction_only(
    detector_model=detector_model,
    SN=SN,
    file_path=file_path,
    dark_image_path=dark_image_path,
    num_detectors=num_detectors,
    detector_height=detector_height,
    detector_width=detector_width,
    reading_direction=reading_direction,
    start_index=start_index,
    end_index=end_index
)
# --- FULL RECONSTRUCTION: DARK + FLAT-FIELD ---

# Data paths
# file_path      = r"/path/to/data.txt"         # (num_frames, num_pixels_per_image)
# dark_image_path = r"/path/to/dark_stack.txt"  # (num_dark_frames, num_pixels_per_image)
# ff_image_path   = r"/path/to/ff_stack.txt"    # (num_ff_frames,   num_pixels_per_image)

file_path      = r"D:/C-Arm/CT_Ref_DT/Machine shop test/New grab line by line/obj1.txt"         # (num_frames, num_pixels_per_image)
dark_image_path = r"D:/C-Arm/CT_Ref_DT/dark_1000us_g0.txt"  # (num_dark_frames, num_pixels_per_image)
ff_image_path   = r"D:/C-Arm/CT_Ref_DT/dark_1000us_g0.txt"    # (num_ff_frames,   num_pixels_per_image)

# Geometry
num_detectors = 3
detector_height = 32
detector_width  = 32
reading_direction = 'column'     # 'row' or 'column'

# Frame window applied to ALL stacks independently
start_index = 0
end_index = 0

# Fully optional metadata, can be left empty
detector_model = 'model'
SN = 'sn'

# ---- Run ----
reconstruct(
    detector_model=detector_model,
    SN=SN,
    file_path=file_path,
    dark_image_path=dark_image_path,
    ff_image_path=ff_image_path,
    num_detectors=num_detectors,
    detector_height=detector_height,
    detector_width=detector_width,
    reading_direction=reading_direction,
    start_index=start_index,
    end_index=end_index
)


def save_image_stack_as_raw(image_data, num_detectors, detector_height, detector_width, reading_direction,
                            output_file_path):
    """
    Save a stack of 2D images as a single raw binary file.
    """
    try:
        # Open the file in binary write mode
        with open(output_file_path, 'wb') as f:
            # Process each row to create a combined image and write to the .raw file
            for row in image_data:
                combined_image = combine_images(np.expand_dims(row, axis=0), num_detectors, detector_height,
                                                detector_width, reading_direction)

                # Convert to 16-bit image
                combined_image = np.asarray(combined_image, dtype=np.uint32)

                # Write the image data to the .raw file
                f.write(combined_image.tobytes())

    except Exception as e:
        show_error(str(e))


def save_to_stack(file_path, dark_image_path, ff_image_path, num_detectors, detector_height, detector_width,
                  reading_direction, output_directory='raw_images'):
    """
    Process image data and save each dataset as a stacked .raw file.

    """
    try:
        # Ensure all paths are valid and convert to posix paths
        if not os.path.isfile(file_path):
            raise ValueError("File path does not exist or is invalid.")

        file_path = Path(file_path).as_posix()
        dark_image_path = Path(dark_image_path).as_posix()
        ff_image_path = Path(ff_image_path).as_posix()

        # Load the images
        data = np.loadtxt(file_path)
        dark_images = np.loadtxt(dark_image_path)
        ff_images = np.loadtxt(ff_image_path)

        # Ensure shapes match
        assert data.shape[1] == dark_images.shape[1] == ff_images.shape[1], (
            "Data, dark images, and ff images must have the same width"
        )

        num_pixels_per_image = num_detectors * (detector_height * detector_width)
        assert data.shape[1] == num_pixels_per_image, (
            f"Expected data width to be {num_pixels_per_image}, but got {data.shape[1]}"
        )

        # Calculate averages for each image stack discarding the first 'start_index' rows
        dark_averages = np.mean(dark_images, axis=0)
        ff_averages = np.mean(ff_images, axis=0)

        # Dark correction for ff image and normalization
        dark_corrected_ff = ff_averages - dark_averages
        median_dark_corrected_ff = np.median(dark_corrected_ff)
        normalized_dark_corrected_ff = dark_corrected_ff / median_dark_corrected_ff

        # Dark and ff corrections for data
        dark_corrected_data = data - dark_averages
        corrected_data = np.divide(dark_corrected_data, normalized_dark_corrected_ff)

        # Save each dataset as a single raw file. You can rename the files if needed.
        save_image_stack_as_raw(data, num_detectors, detector_height, detector_width, reading_direction,
                                os.path.join(output_directory, 'data.raw'))
        save_image_stack_as_raw(dark_images, num_detectors, detector_height, detector_width, reading_direction,
                                os.path.join(output_directory, 'dark_images.raw'))
        save_image_stack_as_raw(ff_images, num_detectors, detector_height, detector_width, reading_direction,
                                os.path.join(output_directory, 'ff_images.raw'))
        save_image_stack_as_raw(dark_corrected_data, num_detectors, detector_height, detector_width, reading_direction,
                                os.path.join(output_directory, 'dark_corrected_data.raw'))
        save_image_stack_as_raw(corrected_data, num_detectors, detector_height, detector_width, reading_direction,
                                os.path.join(output_directory, 'corrected_data.raw'))

    except Exception as e:
        show_error(str(e))

# --- SAVE ALL STACKS (raw + dark + ff + corrected) ---
#
#
# Will automatically save following files:
# data.raw → raw (uncorrected) data
# dark_images.raw → dark frames
# ff_images.raw → flat-field frames
# dark_corrected_data.raw → dark corrected data
# corrected_data.raw → fully corrected data
#
# Paths
# file_path       = r"/path/to/data.txt"
# dark_image_path = r"/path/to/dark_stack.txt"
# ff_image_path   = r"/path/to/ff_stack.txt"

file_path      = r"D:/C-Arm/CT_Ref_DT/Machine shop test/New grab line by line/obj1.txt"         # (num_frames, num_pixels_per_image)
dark_image_path = r"D:/C-Arm/CT_Ref_DT/dark_1000us_g0.txt"  # (num_dark_frames, num_pixels_per_image)
ff_image_path   = r"D:/C-Arm/CT_Ref_DT/dark_1000us_g0.txt"    # (num_ff_frames,   num_pixels_per_image)

# Geometry
num_detectors = 3
detector_height = 32
detector_width  = 32
reading_direction = "column"     # 'row' or 'column'

# Output directory (will contain multiple .raw files)
# output_directory = r"./raw_images"
output_directory = r"D:/C-Arm/CT_Ref_DT/Output image"
# Make sure directory exists
os.makedirs(output_directory, exist_ok=True)

# ---- Run ----
save_to_stack(
    file_path=file_path,
    dark_image_path=dark_image_path,
    ff_image_path=ff_image_path,
    num_detectors=num_detectors,
    detector_height=detector_height,
    detector_width=detector_width,
    reading_direction=reading_direction,
    output_directory=output_directory
)

print(f"Saved stacks into: {output_directory}")

