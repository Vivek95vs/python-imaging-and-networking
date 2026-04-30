import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import threading


class ImageStitchingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Stitching Tool - Medical Image Processing")
        self.root.geometry("1400x900")

        # Variables
        self.images = []  # List of loaded images
        self.image_paths = []  # List of image paths
        self.stitched_image = None
        self.processed_image = None
        self.display_image = None
        self.image_width = 0
        self.image_height = 0
        self.common_width = 3022  # Common width from your cropping

        # Stitching parameters
        self.stitch_direction = tk.StringVar(value="vertical")  # vertical or horizontal
        self.blend_method = tk.StringVar(value="feather")  # feather, gaussian, median, multiband
        self.blend_width = tk.IntVar(value=50)
        self.blur_radius = tk.IntVar(value=10)
        self.intensity_correction = tk.BooleanVar(value=True)
        self.alpha = tk.DoubleVar(value=0.5)  # For alpha blending

        # Display parameters
        self.normalize_method = tk.StringVar(value="minmax")
        self.percentile_low = tk.IntVar(value=1)
        self.percentile_high = tk.IntVar(value=99)

        # Create UI
        self.create_ui()

    def create_ui(self):
        # Main container
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - Controls
        control_frame = ttk.Frame(main_paned)
        main_paned.add(control_frame, weight=1)

        # Create canvas with scrollbar for controls
        control_canvas = tk.Canvas(control_frame, height=800)
        control_scrollbar = ttk.Scrollbar(control_frame, orient="vertical", command=control_canvas.yview)
        control_scrollable_frame = ttk.Frame(control_canvas)

        control_scrollable_frame.bind(
            "<Configure>",
            lambda e: control_canvas.configure(scrollregion=control_canvas.bbox("all"))
        )

        control_canvas.create_window((0, 0), window=control_scrollable_frame, anchor="nw")
        control_canvas.configure(yscrollcommand=control_scrollbar.set)

        # File management
        file_frame = ttk.LabelFrame(control_scrollable_frame, text="File Management", padding=5)
        file_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(file_frame, text="Add Images", command=self.add_images).pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="Clear All", command=self.clear_images).pack(fill=tk.X, pady=2)

        # Image list
        list_frame = ttk.LabelFrame(control_scrollable_frame, text="Images to Stitch", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

        self.image_listbox = tk.Listbox(list_frame, height=8)
        self.image_listbox.pack(fill=tk.BOTH, expand=True)

        ttk.Button(list_frame, text="Remove Selected", command=self.remove_selected).pack(fill=tk.X, pady=2)
        ttk.Button(list_frame, text="Move Up", command=lambda: self.move_image(-1)).pack(fill=tk.X, pady=2)
        ttk.Button(list_frame, text="Move Down", command=lambda: self.move_image(1)).pack(fill=tk.X, pady=2)

        # Stitching direction
        direction_frame = ttk.LabelFrame(control_scrollable_frame, text="Stitching Direction", padding=5)
        direction_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Radiobutton(direction_frame, text="Vertical (Stack)", variable=self.stitch_direction,
                        value="vertical", command=self.update_preview).pack(anchor=tk.W)
        ttk.Radiobutton(direction_frame, text="Horizontal (Side by Side)", variable=self.stitch_direction,
                        value="horizontal", command=self.update_preview).pack(anchor=tk.W)

        # Blending method
        blend_frame = ttk.LabelFrame(control_scrollable_frame, text="Blending Method", padding=5)
        blend_frame.pack(fill=tk.X, pady=5, padx=5)

        methods = [
            ("Feather Blending", "feather"),
            ("Gaussian Blur", "gaussian"),
            ("Median Filter", "median"),
            ("Alpha Blending", "alpha"),
            ("No Blending", "none")
        ]

        for text, value in methods:
            ttk.Radiobutton(blend_frame, text=text, variable=self.blend_method,
                            value=value, command=self.update_preview).pack(anchor=tk.W, pady=2)

        # Blending parameters
        param_frame = ttk.LabelFrame(control_scrollable_frame, text="Blending Parameters", padding=5)
        param_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(param_frame, text="Blend Width:").pack(anchor=tk.W)
        blend_width_scale = ttk.Scale(param_frame, from_=10, to=200, variable=self.blend_width,
                                      orient=tk.HORIZONTAL, command=lambda x: self.update_preview())
        blend_width_scale.pack(fill=tk.X)
        ttk.Label(param_frame, textvariable=self.blend_width).pack(anchor=tk.W)

        ttk.Label(param_frame, text="Blur/Filter Radius:").pack(anchor=tk.W)
        blur_scale = ttk.Scale(param_frame, from_=3, to=30, variable=self.blur_radius,
                               orient=tk.HORIZONTAL, command=lambda x: self.update_preview())
        blur_scale.pack(fill=tk.X)
        ttk.Label(param_frame, textvariable=self.blur_radius).pack(anchor=tk.W)

        ttk.Label(param_frame, text="Alpha (for Alpha Blending):").pack(anchor=tk.W)
        alpha_scale = ttk.Scale(param_frame, from_=0, to=1, variable=self.alpha,
                                orient=tk.HORIZONTAL, command=lambda x: self.update_preview())
        alpha_scale.pack(fill=tk.X)
        ttk.Label(param_frame, textvariable=self.alpha).pack(anchor=tk.W)

        ttk.Checkbutton(param_frame, text="Intensity Correction",
                        variable=self.intensity_correction, command=self.update_preview).pack(anchor=tk.W, pady=5)

        # Display settings
        display_frame = ttk.LabelFrame(control_scrollable_frame, text="Display Settings", padding=5)
        display_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Radiobutton(display_frame, text="Min-Max Normalization", variable=self.normalize_method,
                        value="minmax", command=self.update_display).pack(anchor=tk.W)
        ttk.Radiobutton(display_frame, text="Percentile Clip", variable=self.normalize_method,
                        value="percentile", command=self.update_display).pack(anchor=tk.W)

        ttk.Label(display_frame, text="Low Percentile:").pack(anchor=tk.W)
        low_scale = ttk.Scale(display_frame, from_=0, to=10, variable=self.percentile_low,
                              orient=tk.HORIZONTAL, command=lambda x: self.update_display())
        low_scale.pack(fill=tk.X)
        ttk.Label(display_frame, textvariable=self.percentile_low).pack(anchor=tk.W)

        ttk.Label(display_frame, text="High Percentile:").pack(anchor=tk.W)
        high_scale = ttk.Scale(display_frame, from_=90, to=100, variable=self.percentile_high,
                               orient=tk.HORIZONTAL, command=lambda x: self.update_display())
        high_scale.pack(fill=tk.X)
        ttk.Label(display_frame, textvariable=self.percentile_high).pack(anchor=tk.W)

        # Action buttons
        action_frame = ttk.LabelFrame(control_scrollable_frame, text="Actions", padding=5)
        action_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(action_frame, text="Stitch Images", command=self.stitch_images).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="Save Result", command=self.save_result).pack(fill=tk.X, pady=2)

        # Info display
        info_frame = ttk.LabelFrame(control_scrollable_frame, text="Information", padding=5)
        info_frame.pack(fill=tk.X, pady=5, padx=5)

        self.info_text = tk.Text(info_frame, height=8, width=35)
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # Pack scrollable frame
        control_canvas.pack(side="left", fill="both", expand=True)
        control_scrollbar.pack(side="right", fill="y")

        # Right panel - Image display
        display_frame = ttk.LabelFrame(main_paned, text="Preview")
        main_paned.add(display_frame, weight=3)

        # Create canvas for image display
        self.canvas = tk.Canvas(display_frame, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind resize event
        self.canvas.bind('<Configure>', self.on_canvas_resize)

    def add_images(self):
        """Add images to stitch"""
        files = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[("RAW files", "*.raw"), ("PNG files", "*.png"),
                       ("JPEG files", "*.jpg"), ("All files", "*.*")]
        )

        for file_path in files:
            try:
                # Load image based on extension
                if file_path.lower().endswith('.raw'):
                    # Load 16-bit raw
                    with open(file_path, 'rb') as f:
                        data = np.fromfile(f, dtype=np.uint16)

                    # Detect dimensions (assuming square or using common width)
                    total_pixels = len(data)
                    height = total_pixels // self.common_width
                    if height * self.common_width == total_pixels:
                        img = data.reshape((height, self.common_width))
                    else:
                        # Try to detect square
                        size = int(np.sqrt(total_pixels))
                        if size * size == total_pixels:
                            img = data.reshape((size, size))
                        else:
                            raise ValueError(f"Cannot determine dimensions for {file_path}")
                else:
                    # Load regular image
                    img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                    if img is None:
                        raise ValueError(f"Cannot load {file_path}")

                    # Convert to grayscale if needed
                    if len(img.shape) == 3:
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                    # Convert to 16-bit if needed
                    if img.dtype == np.uint8:
                        img = img.astype(np.uint16) * 256

                self.images.append(img)
                self.image_paths.append(file_path)
                self.image_listbox.insert(tk.END, os.path.basename(file_path))

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load {file_path}: {str(e)}")

        self.update_info()

    def clear_images(self):
        """Clear all loaded images"""
        self.images = []
        self.image_paths = []
        self.image_listbox.delete(0, tk.END)
        self.stitched_image = None
        self.processed_image = None
        self.update_display()
        self.update_info()

    def remove_selected(self):
        """Remove selected image from list"""
        selection = self.image_listbox.curselection()
        if selection:
            index = selection[0]
            self.image_listbox.delete(index)
            del self.images[index]
            del self.image_paths[index]
            self.update_info()

    def move_image(self, direction):
        """Move image up or down in the list"""
        selection = self.image_listbox.curselection()
        if selection:
            index = selection[0]
            new_index = index + direction
            if 0 <= new_index < len(self.images):
                # Swap in list
                self.images[index], self.images[new_index] = self.images[new_index], self.images[index]
                self.image_paths[index], self.image_paths[new_index] = self.image_paths[new_index], self.image_paths[
                    index]

                # Update listbox
                self.image_listbox.delete(0, tk.END)
                for path in self.image_paths:
                    self.image_listbox.insert(tk.END, os.path.basename(path))
                self.image_listbox.selection_set(new_index)
                self.update_info()

    def correct_intensity(self, img1, img2, blend_width):
        """Correct intensity differences between images"""
        # Get overlapping region statistics
        if self.stitch_direction.get() == "vertical":
            overlap1 = img1[-blend_width:, :]
            overlap2 = img2[:blend_width, :]
        else:
            overlap1 = img1[:, -blend_width:]
            overlap2 = img2[:, :blend_width]

        # Calculate mean and std
        mean1 = np.mean(overlap1)
        mean2 = np.mean(overlap2)
        std1 = np.std(overlap1)
        std2 = np.std(overlap2)

        # Apply correction
        if std2 > 0:
            alpha = std1 / std2
            beta = mean1 - alpha * mean2
            img2_corrected = (img2.astype(np.float32) * alpha + beta).astype(np.uint16)
            return img2_corrected
        return img2

    def blend_feather(self, img1, img2, blend_width):
        """Feather blending"""
        if self.stitch_direction.get() == "vertical":
            h1, w = img1.shape
            h2 = img2.shape[0]
            result = np.zeros((h1 + h2 - blend_width, w), dtype=np.uint16)

            # Copy non-overlapping parts
            result[:h1 - blend_width] = img1[:h1 - blend_width]
            result[h1:] = img2[blend_width:]

            # Blend overlapping region
            for i in range(blend_width):
                alpha = i / blend_width
                beta = 1 - alpha
                result[h1 - blend_width + i] = (img1[h1 - blend_width + i] * beta +
                                                img2[i] * alpha).astype(np.uint16)
        else:
            w1, h = img1.shape
            w2 = img2.shape[1]
            result = np.zeros((h, w1 + w2 - blend_width), dtype=np.uint16)

            # Copy non-overlapping parts
            result[:, :w1 - blend_width] = img1[:, :w1 - blend_width]
            result[:, w1:] = img2[:, blend_width:]

            # Blend overlapping region
            for i in range(blend_width):
                alpha = i / blend_width
                beta = 1 - alpha
                result[:, w1 - blend_width + i] = (img1[:, w1 - blend_width + i] * beta +
                                                   img2[:, i] * alpha).astype(np.uint16)

        return result

    def blend_gaussian(self, img1, img2, blend_width):
        """Gaussian blur blending"""
        result = self.blend_feather(img1, img2, blend_width)

        if self.stitch_direction.get() == "vertical":
            seam_y = img1.shape[0] - blend_width
            blur_radius = self.blur_radius.get()
            start_y = max(0, seam_y - blur_radius)
            end_y = min(result.shape[0], seam_y + blur_radius)
            result[start_y:end_y, :] = cv2.GaussianBlur(result[start_y:end_y, :].astype(np.float32),
                                                        (5, 5), blur_radius).astype(np.uint16)
        else:
            seam_x = img1.shape[1] - blend_width
            blur_radius = self.blur_radius.get()
            start_x = max(0, seam_x - blur_radius)
            end_x = min(result.shape[1], seam_x + blur_radius)
            result[:, start_x:end_x] = cv2.GaussianBlur(result[:, start_x:end_x].astype(np.float32),
                                                        (5, 5), blur_radius).astype(np.uint16)

        return result

    def blend_median(self, img1, img2, blend_width):
        """Median filter blending"""
        result = self.blend_feather(img1, img2, blend_width)

        filter_size = self.blur_radius.get()
        if filter_size % 2 == 0:
            filter_size += 1

        if self.stitch_direction.get() == "vertical":
            seam_y = img1.shape[0] - blend_width
            start_y = max(0, seam_y - filter_size)
            end_y = min(result.shape[0], seam_y + filter_size)
            result[start_y:end_y, :] = cv2.medianBlur(result[start_y:end_y, :].astype(np.uint16), filter_size)
        else:
            seam_x = img1.shape[1] - blend_width
            start_x = max(0, seam_x - filter_size)
            end_x = min(result.shape[1], seam_x + filter_size)
            result[:, start_x:end_x] = cv2.medianBlur(result[:, start_x:end_x].astype(np.uint16), filter_size)

        return result

    def blend_alpha(self, img1, img2, blend_width):
        """Alpha blending"""
        alpha = self.alpha.get()

        if self.stitch_direction.get() == "vertical":
            h1, w = img1.shape
            h2 = img2.shape[0]
            result = np.zeros((h1 + h2 - blend_width, w), dtype=np.uint16)

            result[:h1 - blend_width] = img1[:h1 - blend_width]
            result[h1:] = img2[blend_width:]

            for i in range(blend_width):
                result[h1 - blend_width + i] = (img1[h1 - blend_width + i] * (1 - alpha) +
                                                img2[i] * alpha).astype(np.uint16)
        else:
            w1, h = img1.shape
            w2 = img2.shape[1]
            result = np.zeros((h, w1 + w2 - blend_width), dtype=np.uint16)

            result[:, :w1 - blend_width] = img1[:, :w1 - blend_width]
            result[:, w1:] = img2[:, blend_width:]

            for i in range(blend_width):
                result[:, w1 - blend_width + i] = (img1[:, w1 - blend_width + i] * (1 - alpha) +
                                                   img2[:, i] * alpha).astype(np.uint16)

        return result

    def stitch_two_images(self, img1, img2):
        """Stitch two images with blending"""
        blend_width = self.blend_width.get()
        blend_method = self.blend_method.get()

        # Apply intensity correction if enabled
        if self.intensity_correction.get():
            img2 = self.correct_intensity(img1, img2, blend_width)

        # Apply blending
        if blend_method == "feather":
            return self.blend_feather(img1, img2, blend_width)
        elif blend_method == "gaussian":
            return self.blend_gaussian(img1, img2, blend_width)
        elif blend_method == "median":
            return self.blend_median(img1, img2, blend_width)
        elif blend_method == "alpha":
            return self.blend_alpha(img1, img2, blend_width)
        else:  # no blending
            if self.stitch_direction.get() == "vertical":
                return np.vstack([img1, img2])
            else:
                return np.hstack([img1, img2])

    def stitch_images(self):
        """Stitch all loaded images"""
        if len(self.images) < 2:
            messagebox.showwarning("Warning", "Need at least 2 images to stitch!")
            return

        try:
            self.status_bar.config(text="Stitching images...")
            self.root.update()

            # Start with first image
            self.stitched_image = self.images[0].copy()

            # Stitch sequentially
            for i in range(1, len(self.images)):
                self.status_bar.config(text=f"Stitching image {i + 1}/{len(self.images)}...")
                self.root.update()
                self.stitched_image = self.stitch_two_images(self.stitched_image, self.images[i])

            self.processed_image = self.stitched_image.copy()
            self.update_display()
            self.update_info()

            self.status_bar.config(text="Stitching completed!")
            # messagebox.showinfo("Success", f"Stitched {len(self.images)} images successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to stitch: {str(e)}")
            self.status_bar.config(text="Error during stitching")

    def normalize_for_display(self, image):
        """Normalize 16-bit image to 8-bit for display"""
        if image is None:
            return None

        if self.normalize_method.get() == "minmax":
            img_min = image.min()
            img_max = image.max()

            if img_max > img_min:
                normalized = (image - img_min) / (img_max - img_min) * 255
            else:
                normalized = np.zeros_like(image, dtype=np.uint8)
        else:
            low_perc = self.percentile_low.get()
            high_perc = self.percentile_high.get()

            low_val = np.percentile(image, low_perc)
            high_val = np.percentile(image, high_perc)

            if high_val > low_val:
                normalized = (image - low_val) / (high_val - low_val) * 255
                normalized = np.clip(normalized, 0, 255)
            else:
                normalized = np.zeros_like(image, dtype=np.uint8)

        return normalized.astype(np.uint8)

    def update_display(self):
        """Update the displayed image"""
        if self.processed_image is None:
            return

        try:
            # Normalize for display
            display_img = self.normalize_for_display(self.processed_image)

            if display_img is None:
                return

            # Convert to RGB for display
            display_img = cv2.cvtColor(display_img, cv2.COLOR_GRAY2RGB)

            # Calculate scale to fit canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                img_height, img_width = display_img.shape[:2]
                scale = min(canvas_width / img_width, canvas_height / img_height)
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)

                display_img = cv2.resize(display_img, (new_width, new_height), interpolation=cv2.INTER_AREA)

            # Convert to PhotoImage
            self.display_image = ImageTk.PhotoImage(image=Image.fromarray(display_img))

            # Update canvas
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width // 2, canvas_height // 2,
                                     image=self.display_image, anchor=tk.CENTER)

        except Exception as e:
            print(f"Display error: {e}")

    def update_preview(self):
        """Update preview after parameter changes"""
        if len(self.images) >= 2:
            # Re-stitch with new parameters
            threading.Thread(target=self.stitch_images, daemon=True).start()

    def on_canvas_resize(self, event):
        """Handle canvas resize"""
        if self.processed_image is not None:
            self.update_display()

    def update_info(self):
        """Update information display"""
        self.info_text.delete(1.0, tk.END)

        info = f"Images loaded: {len(self.images)}\n\n"

        for i, (img, path) in enumerate(zip(self.images, self.image_paths)):
            info += f"Image {i + 1}: {os.path.basename(path)}\n"
            info += f"  Size: {img.shape[1]}x{img.shape[0]}\n"
            info += f"  Range: {img.min()}-{img.max()}\n"
            info += f"  Mean: {img.mean():.0f}\n\n"

        if self.stitched_image is not None:
            info += f"Stitched result:\n"
            info += f"  Size: {self.stitched_image.shape[1]}x{self.stitched_image.shape[0]}\n"
            info += f"  Range: {self.stitched_image.min()}-{self.stitched_image.max()}\n"

        self.info_text.insert(1.0, info)

    def save_result(self):
        """Save stitched image"""
        if self.processed_image is None:
            messagebox.showwarning("Warning", "No image to save!")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Stitched Image",
            defaultextension=".raw",
            filetypes=[("RAW files", "*.raw"), ("PNG files", "*.png"),
                       ("TIFF files", "*.tiff"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.png') or file_path.endswith('.tiff'):
                save_img = self.normalize_for_display(self.processed_image)
                cv2.imwrite(file_path, save_img)
            else:
                with open(file_path, 'wb') as f:
                    f.write(self.processed_image.astype(np.uint16).tobytes())

            messagebox.showinfo("Success", f"Image saved to: {file_path}")
            self.status_bar.config(text=f"Saved: {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")


def main():
    root = tk.Tk()
    app = ImageStitchingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()