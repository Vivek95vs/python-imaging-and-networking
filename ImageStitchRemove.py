import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os


class SeamRemovalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Seam Removal Tool - Medical Image Stitching")
        self.root.geometry("1400x800")

        # Variables
        self.image = None
        self.original_image = None
        self.processed_image = None
        self.display_image_display = None  # For display
        self.seams = []
        self.image_path = None
        self.image_width = 3072
        self.image_height = 3072

        # Parameters
        self.method = tk.StringVar(value="inpaint")
        self.line_width = tk.IntVar(value=5)
        self.blend_width = tk.IntVar(value=40)
        self.blur_height = tk.IntVar(value=15)
        self.filter_size = tk.IntVar(value=5)
        self.seam_threshold = tk.IntVar(value=30)
        self.min_distance = tk.IntVar(value=200)
        self.manual_seam1 = tk.IntVar(value=1024)
        self.manual_seam2 = tk.IntVar(value=2048)
        self.normalize_method = tk.StringVar(value="minmax")  # minmax or percentile
        self.percentile_low = tk.IntVar(value=1)
        self.percentile_high = tk.IntVar(value=99)

        # Intensity correction parameters
        self.intensity_correction = tk.BooleanVar(value=True)
        self.correction_method = tk.StringVar(value="histogram")  # histogram, linear, local
        self.correction_width = tk.IntVar(value=100)  # Width for local correction

        # Create UI
        self.create_ui()

    def create_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Controls
        control_frame = ttk.LabelFrame(main_frame, text="Controls", width=350)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        control_frame.pack_propagate(False)

        # Create a canvas with scrollbar for controls
        control_canvas = tk.Canvas(control_frame)
        control_scrollbar = ttk.Scrollbar(control_frame, orient="vertical", command=control_canvas.yview)
        control_scrollable_frame = ttk.Frame(control_canvas)

        control_scrollable_frame.bind(
            "<Configure>",
            lambda e: control_canvas.configure(scrollregion=control_canvas.bbox("all"))
        )

        control_canvas.create_window((0, 0), window=control_scrollable_frame, anchor="nw")
        control_canvas.configure(yscrollcommand=control_scrollbar.set)

        # File controls
        file_frame = ttk.LabelFrame(control_scrollable_frame, text="File", padding=5)
        file_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(file_frame, text="Load Image", command=self.load_image).pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="Save Image", command=self.save_image).pack(fill=tk.X, pady=2)

        # Method selection
        method_frame = ttk.LabelFrame(control_scrollable_frame, text="Method", padding=5)
        method_frame.pack(fill=tk.X, pady=5, padx=5)

        methods = [
            ("Inpainting (Recommended)", "inpaint"),
            ("Gaussian Blur", "gaussian"),
            ("Median Filter", "median"),
            ("Feather Blending", "feather"),
            ("Gradient Blending", "gradient"),
            ("Combined", "combined")
        ]

        for text, value in methods:
            ttk.Radiobutton(method_frame, text=text, variable=self.method,
                            value=value, command=self.update_preview).pack(anchor=tk.W, pady=2)

        # Intensity Correction Frame
        correction_frame = ttk.LabelFrame(control_scrollable_frame, text="Intensity Correction", padding=5)
        correction_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Checkbutton(correction_frame, text="Enable Intensity Correction",
                        variable=self.intensity_correction, command=self.update_preview).pack(anchor=tk.W, pady=2)

        ttk.Label(correction_frame, text="Correction Method:").pack(anchor=tk.W, pady=(5, 0))

        correction_methods = [
            ("Histogram Matching", "histogram"),
            ("Linear Scaling", "linear"),
            ("Local Adaptive", "local")
        ]

        for text, value in correction_methods:
            ttk.Radiobutton(correction_frame, text=text, variable=self.correction_method,
                            value=value, command=self.update_preview).pack(anchor=tk.W, padx=10)

        ttk.Label(correction_frame, text="Correction Width:").pack(anchor=tk.W, pady=(5, 0))
        ttk.Scale(correction_frame, from_=20, to=200, variable=self.correction_width,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_preview()).pack(fill=tk.X)
        ttk.Label(correction_frame, textvariable=self.correction_width).pack(anchor=tk.W)

        # Display normalization
        norm_frame = ttk.LabelFrame(control_scrollable_frame, text="Display Settings", padding=5)
        norm_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Radiobutton(norm_frame, text="Min-Max Normalization", variable=self.normalize_method,
                        value="minmax", command=self.update_display).pack(anchor=tk.W)
        ttk.Radiobutton(norm_frame, text="Percentile Clip (1-99%)", variable=self.normalize_method,
                        value="percentile", command=self.update_display).pack(anchor=tk.W)

        ttk.Label(norm_frame, text="Low Percentile:").pack(anchor=tk.W)
        ttk.Scale(norm_frame, from_=0, to=10, variable=self.percentile_low,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_display()).pack(fill=tk.X)
        ttk.Label(norm_frame, textvariable=self.percentile_low).pack(anchor=tk.W)

        ttk.Label(norm_frame, text="High Percentile:").pack(anchor=tk.W)
        ttk.Scale(norm_frame, from_=90, to=100, variable=self.percentile_high,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_display()).pack(fill=tk.X)
        ttk.Label(norm_frame, textvariable=self.percentile_high).pack(anchor=tk.W)

        # Parameters frame
        param_frame = ttk.LabelFrame(control_scrollable_frame, text="Parameters", padding=5)
        param_frame.pack(fill=tk.X, pady=5, padx=5)

        # Inpainting parameters
        self.inpaint_frame = ttk.Frame(param_frame)
        ttk.Label(self.inpaint_frame, text="Line Width:").pack(anchor=tk.W)
        ttk.Scale(self.inpaint_frame, from_=1, to=15, variable=self.line_width,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_preview()).pack(fill=tk.X)
        ttk.Label(self.inpaint_frame, textvariable=self.line_width).pack(anchor=tk.W)

        # Gaussian blur parameters
        self.gaussian_frame = ttk.Frame(param_frame)
        ttk.Label(self.gaussian_frame, text="Blur Height:").pack(anchor=tk.W)
        ttk.Scale(self.gaussian_frame, from_=5, to=50, variable=self.blur_height,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_preview()).pack(fill=tk.X)
        ttk.Label(self.gaussian_frame, textvariable=self.blur_height).pack(anchor=tk.W)

        # Median filter parameters
        self.median_frame = ttk.Frame(param_frame)
        ttk.Label(self.median_frame, text="Filter Size:").pack(anchor=tk.W)
        ttk.Scale(self.median_frame, from_=3, to=15, variable=self.filter_size,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_preview()).pack(fill=tk.X)
        ttk.Label(self.median_frame, textvariable=self.filter_size).pack(anchor=tk.W)

        # Feather/Gradient blend parameters
        self.blend_frame = ttk.Frame(param_frame)
        ttk.Label(self.blend_frame, text="Blend Width:").pack(anchor=tk.W)
        ttk.Scale(self.blend_frame, from_=10, to=100, variable=self.blend_width,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_preview()).pack(fill=tk.X)
        ttk.Label(self.blend_frame, textvariable=self.blend_width).pack(anchor=tk.W)

        # Seam detection parameters
        seam_frame = ttk.LabelFrame(control_scrollable_frame, text="Seam Detection", padding=5)
        seam_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(seam_frame, text="Threshold:").pack(anchor=tk.W)
        ttk.Scale(seam_frame, from_=10, to=100, variable=self.seam_threshold,
                  orient=tk.HORIZONTAL, command=lambda x: self.detect_seams()).pack(fill=tk.X)
        ttk.Label(seam_frame, textvariable=self.seam_threshold).pack(anchor=tk.W)

        ttk.Label(seam_frame, text="Min Distance:").pack(anchor=tk.W)
        ttk.Scale(seam_frame, from_=50, to=500, variable=self.min_distance,
                  orient=tk.HORIZONTAL, command=lambda x: self.detect_seams()).pack(fill=tk.X)
        ttk.Label(seam_frame, textvariable=self.min_distance).pack(anchor=tk.W)

        ttk.Button(seam_frame, text="Detect Seams", command=self.detect_seams).pack(fill=tk.X, pady=5)

        # Manual seam positions
        manual_frame = ttk.LabelFrame(control_scrollable_frame, text="Manual Seams", padding=5)
        manual_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(manual_frame, text="Seam 1 Y:").pack(anchor=tk.W)
        ttk.Scale(manual_frame, from_=0, to=self.image_height, variable=self.manual_seam1,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_seams()).pack(fill=tk.X)
        ttk.Label(manual_frame, textvariable=self.manual_seam1).pack(anchor=tk.W)

        ttk.Label(manual_frame, text="Seam 2 Y:").pack(anchor=tk.W)
        ttk.Scale(manual_frame, from_=0, to=self.image_height, variable=self.manual_seam2,
                  orient=tk.HORIZONTAL, command=lambda x: self.update_seams()).pack(fill=tk.X)
        ttk.Label(manual_frame, textvariable=self.manual_seam2).pack(anchor=tk.W)

        ttk.Button(manual_frame, text="Use Manual Seams", command=self.use_manual_seams).pack(fill=tk.X, pady=5)

        # Info display
        info_frame = ttk.LabelFrame(control_scrollable_frame, text="Information", padding=5)
        info_frame.pack(fill=tk.X, pady=5, padx=5)

        self.info_text = tk.Text(info_frame, height=12, width=35)
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # Pack scrollable frame
        control_canvas.pack(side="left", fill="both", expand=True)
        control_scrollbar.pack(side="right", fill="y")

        # Right panel - Image display
        display_frame = ttk.LabelFrame(main_frame, text="Image Preview")
        display_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create canvas for image display
        self.canvas = tk.Canvas(display_frame, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind resize event
        self.canvas.bind('<Configure>', self.on_canvas_resize)

    def histogram_matching(self, source, target):
        """Match histogram of source to target"""
        # Calculate histograms
        hist_source = cv2.calcHist([source], [0], None, [65536], [0, 65536])
        hist_target = cv2.calcHist([target], [0], None, [65536], [0, 65536])

        # Calculate cumulative histograms
        cum_source = np.cumsum(hist_source).astype(float)
        cum_target = np.cumsum(hist_target).astype(float)

        # Normalize
        cum_source = cum_source / cum_source[-1]
        cum_target = cum_target / cum_target[-1]

        # Create lookup table
        lut = np.zeros(65536, dtype=np.uint16)
        for i in range(65536):
            idx = np.argmin(np.abs(cum_target - cum_source[i]))
            lut[i] = idx

        # Apply lookup table
        matched = cv2.LUT(source, lut)
        return matched

    def linear_intensity_correction(self, source, target):
        """Apply linear intensity correction"""
        mean_source = np.mean(source)
        mean_target = np.mean(target)
        std_source = np.std(source)
        std_target = np.std(target)

        if std_target > 0:
            alpha = std_source / std_target
            beta = mean_source - alpha * mean_target
            corrected = (source.astype(np.float32) * alpha + beta).astype(np.uint16)
            return corrected
        return source

    def local_intensity_correction(self, source, target, blend_width):
        """Apply local adaptive intensity correction"""
        corrected = source.copy()

        # Create sliding window for local correction
        for y in range(0, source.shape[0], blend_width // 2):
            for x in range(0, source.shape[1], blend_width // 2):
                # Define window
                y_end = min(y + blend_width, source.shape[0])
                x_end = min(x + blend_width, source.shape[1])

                source_window = source[y:y_end, x:x_end]
                target_window = target[y:y_end, x:x_end]

                if source_window.size > 0 and target_window.size > 0:
                    mean_source = np.mean(source_window)
                    mean_target = np.mean(target_window)
                    std_source = np.std(source_window)
                    std_target = np.std(target_window)

                    if std_target > 0:
                        alpha = std_source / std_target
                        beta = mean_source - alpha * mean_target
                        corrected[y:y_end, x:x_end] = (source_window.astype(np.float32) * alpha + beta).astype(
                            np.uint16)

        return corrected

    def apply_intensity_correction(self, image, seam_y):
        """Apply intensity correction across the seam"""
        if not self.intensity_correction.get():
            return image

        blend_width = self.correction_width.get()
        method = self.correction_method.get()

        result = image.copy()

        # Get regions above and below the seam
        start_y = max(0, seam_y - blend_width)
        end_y = min(image.shape[0], seam_y + blend_width)

        region_above = image[start_y:seam_y, :]
        region_below = image[seam_y:end_y, :]

        if region_above.size == 0 or region_below.size == 0:
            return result

        # Apply selected correction method
        if method == "histogram":
            corrected_below = self.histogram_matching(region_below, region_above)
        elif method == "linear":
            corrected_below = self.linear_intensity_correction(region_below, region_above)
        elif method == "local":
            corrected_below = self.local_intensity_correction(region_below, region_above, 50)
        else:
            corrected_below = region_below

        # Place corrected region back
        result[seam_y:end_y, :] = corrected_below

        return result

    def normalize_for_display(self, image):
        """Normalize 16-bit image to 8-bit for display"""
        if image is None:
            return None

        if self.normalize_method.get() == "minmax":
            # Min-max normalization
            img_min = image.min()
            img_max = image.max()

            if img_max > img_min:
                normalized = (image - img_min) / (img_max - img_min) * 255
            else:
                normalized = np.zeros_like(image, dtype=np.uint8)

        else:  # percentile
            # Percentile-based normalization (removes outliers)
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

    def load_image(self):
        """Load 16-bit raw image"""
        file_path = filedialog.askopenfilename(
            title="Select RAW Image",
            filetypes=[("RAW files", "*.raw"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            self.status_bar.config(text="Loading image...")
            self.root.update()

            # Load image
            with open(file_path, 'rb') as f:
                data = np.fromfile(f, dtype=np.uint16)

            # Try to determine dimensions (assume square)
            total_pixels = len(data)
            self.image_height = int(np.sqrt(total_pixels))
            self.image_width = self.image_height

            if self.image_width * self.image_height != total_pixels:
                # Try common aspect ratios
                for ratio in [1, 4 / 3, 16 / 9, 3 / 2]:
                    width = int(np.sqrt(total_pixels * ratio))
                    height = total_pixels // width
                    if width * height == total_pixels:
                        self.image_width = width
                        self.image_height = height
                        break

            self.original_image = data.reshape((self.image_height, self.image_width))
            self.processed_image = self.original_image.copy()
            self.image_path = file_path

            # Update seam sliders
            self.manual_seam1.set(self.image_height // 3)
            self.manual_seam2.set(2 * self.image_height // 3)

            # Detect seams
            self.detect_seams()

            # Update display
            self.update_display()

            # Update info
            self.update_info()

            self.status_bar.config(
                text=f"Loaded: {os.path.basename(file_path)} ({self.image_width}x{self.image_height})")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")
            self.status_bar.config(text="Error loading image")

    def detect_seams(self):
        """Auto-detect stitching lines"""
        if self.original_image is None:
            return

        try:
            # Calculate vertical gradient
            grad_y = cv2.Sobel(self.original_image, cv2.CV_32F, 0, 1, ksize=3)
            row_grad = np.mean(np.abs(grad_y), axis=1)

            # Find peaks
            threshold = self.seam_threshold.get()
            min_distance = self.min_distance.get()

            self.seams = []
            for y in range(20, len(row_grad) - 20):
                if (row_grad[y] > threshold and
                        row_grad[y] > row_grad[y - 5] and
                        row_grad[y] > row_grad[y + 5]):

                    if not self.seams or (y - self.seams[-1]) > min_distance:
                        self.seams.append(y)

            # Update info
            self.update_info()
            self.update_preview()

        except Exception as e:
            print(f"Seam detection error: {e}")

    def use_manual_seams(self):
        """Use manually specified seam positions"""
        self.seams = [self.manual_seam1.get(), self.manual_seam2.get()]
        self.update_info()
        self.update_preview()

    def update_seams(self):
        """Update seams when manual sliders change"""
        self.seams = [self.manual_seam1.get(), self.manual_seam2.get()]
        self.update_preview()

    def remove_seam_inpaint(self, image, seam_y):
        """Remove seam using inpainting"""
        # Apply intensity correction first if enabled
        if self.intensity_correction.get():
            image = self.apply_intensity_correction(image, seam_y)

        result = image.copy()
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.line(mask, (0, seam_y), (image.shape[1], seam_y), 255, self.line_width.get())

        kernel = np.ones((self.line_width.get(), self.line_width.get()), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

        result = cv2.inpaint(result, mask, 3, cv2.INPAINT_TELEA)
        return result

    def remove_seam_gaussian(self, image, seam_y):
        """Remove seam using Gaussian blur"""
        # Apply intensity correction first if enabled
        if self.intensity_correction.get():
            image = self.apply_intensity_correction(image, seam_y)

        result = image.copy()
        blur_height = self.blur_height.get()
        start_y = max(0, seam_y - blur_height // 2)
        end_y = min(image.shape[0], seam_y + blur_height // 2)

        if end_y > start_y:
            seam_region = result[start_y:end_y, :]
            blurred = cv2.GaussianBlur(seam_region, (5, 5), 2)
            result[start_y:end_y, :] = blurred

        return result

    def remove_seam_median(self, image, seam_y):
        """Remove seam using median filter"""
        # Apply intensity correction first if enabled
        if self.intensity_correction.get():
            image = self.apply_intensity_correction(image, seam_y)

        result = image.copy()
        filter_size = self.filter_size.get()
        # Ensure filter size is odd
        if filter_size % 2 == 0:
            filter_size += 1
        start_y = max(0, seam_y - filter_size)
        end_y = min(image.shape[0], seam_y + filter_size)

        if end_y > start_y:
            seam_region = result[start_y:end_y, :]
            filtered = cv2.medianBlur(seam_region, filter_size)
            result[start_y:end_y, :] = filtered

        return result

    def remove_seam_feather(self, image, seam_y):
        """Remove seam using feather blending"""
        # Apply intensity correction first if enabled
        if self.intensity_correction.get():
            image = self.apply_intensity_correction(image, seam_y)

        result = image.copy()
        blend_width = self.blend_width.get()
        start_y = max(0, seam_y - blend_width)
        end_y = min(image.shape[0], seam_y + blend_width)

        kernel = np.ones((3, 3), np.float32) / 9
        avg = cv2.filter2D(image.astype(np.float32), -1, kernel)

        for y in range(start_y, end_y):
            weight = 1.0 - abs(y - seam_y) / blend_width
            weight = max(0.0, min(1.0, weight))
            result[y, :] = (image[y, :].astype(np.float32) * (1 - weight) + avg[y, :] * weight).astype(np.uint16)

        return result

    def remove_seam_gradient(self, image, seam_y):
        """Remove seam using gradient blending"""
        # Apply intensity correction first if enabled
        if self.intensity_correction.get():
            image = self.apply_intensity_correction(image, seam_y)

        result = image.copy()
        blend_width = self.blend_width.get()
        start_y = max(0, seam_y - blend_width)
        end_y = min(image.shape[0], seam_y + blend_width)

        grad_y = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)

        for y in range(start_y, end_y):
            weight = 1.0 - abs(y - seam_y) / blend_width

            for x in range(image.shape[1]):
                gradient_mag = abs(grad_y[y, x])

                if gradient_mag > 20:
                    y_above = max(0, y - 2)
                    y_below = min(image.shape[0] - 1, y + 2)
                    smoothed = (image[y_above, x].astype(np.float32) + image[y_below, x].astype(np.float32)) // 2
                    blend_weight = min(1.0, gradient_mag / 50.0) * weight
                    result[y, x] = (image[y, x] * (1 - blend_weight) + smoothed * blend_weight).astype(np.uint16)

        return result

    def remove_seams(self):
        """Apply selected seam removal method"""
        if self.original_image is None or not self.seams:
            return self.original_image.copy() if self.original_image is not None else None

        result = self.original_image.copy()
        method = self.method.get()

        for seam in self.seams:
            if method == 'inpaint':
                result = self.remove_seam_inpaint(result, seam)
            elif method == 'gaussian':
                result = self.remove_seam_gaussian(result, seam)
            elif method == 'median':
                result = self.remove_seam_median(result, seam)
            elif method == 'feather':
                result = self.remove_seam_feather(result, seam)
            elif method == 'gradient':
                result = self.remove_seam_gradient(result, seam)
            elif method == 'combined':
                result = self.remove_seam_inpaint(result, seam)
                result = self.remove_seam_median(result, seam)

        return result

    def update_preview(self):
        """Update image preview after processing"""
        if self.original_image is None:
            return

        try:
            self.status_bar.config(text="Processing...")
            self.root.update()

            # Process image
            self.processed_image = self.remove_seams()

            # Update display
            self.update_display()

            self.status_bar.config(text="Ready")

        except Exception as e:
            self.status_bar.config(text=f"Error: {str(e)}")
            print(f"Preview error: {e}")

    def update_display(self):
        """Update the displayed image"""
        if self.processed_image is None:
            return

        try:
            # Normalize for display
            display_img = self.normalize_for_display(self.processed_image)

            if display_img is None:
                return

            # Convert to RGB
            display_img = cv2.cvtColor(display_img, cv2.COLOR_GRAY2RGB)

            # Draw seam lines
            for seam in self.seams:
                if 0 <= seam < display_img.shape[0]:
                    cv2.line(display_img, (0, seam), (display_img.shape[1], seam), (255, 0, 0), 2)

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
            self.display_image_display = ImageTk.PhotoImage(image=Image.fromarray(display_img))

            # Update canvas
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width // 2, canvas_height // 2,
                                     image=self.display_image_display, anchor=tk.CENTER)

        except Exception as e:
            print(f"Display error: {e}")

    def on_canvas_resize(self, event):
        """Handle canvas resize"""
        if self.processed_image is not None:
            self.update_display()

    def update_info(self):
        """Update information display"""
        if self.original_image is None:
            return

        self.info_text.delete(1.0, tk.END)

        info = f"File: {os.path.basename(self.image_path) if self.image_path else 'None'}\n"
        info += f"Image Size: {self.image_width}x{self.image_height}\n"
        info += f"Pixel Range: {self.original_image.min()} - {self.original_image.max()}\n"
        info += f"Mean Value: {self.original_image.mean():.0f}\n"
        info += f"Std Dev: {self.original_image.std():.0f}\n\n"
        info += f"Intensity Correction: {'Enabled' if self.intensity_correction.get() else 'Disabled'}\n"
        if self.intensity_correction.get():
            info += f"Correction Method: {self.correction_method.get()}\n"
            info += f"Correction Width: {self.correction_width.get()} px\n\n"
        info += f"Detected Seams: {len(self.seams)}\n"

        if self.seams:
            info += f"Seam Positions:\n"
            for i, seam in enumerate(self.seams):
                info += f"  Seam {i + 1}: Y={seam}\n"

        self.info_text.insert(1.0, info)

    def save_image(self):
        """Save processed image"""
        if self.processed_image is None:
            messagebox.showwarning("Warning", "No image to save!")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Processed Image",
            defaultextension=".raw",
            filetypes=[("RAW files", "*.raw"), ("PNG files", "*.png"), ("TIFF files", "*.tiff"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.png') or file_path.endswith('.tiff'):
                # Save as PNG/TIFF (normalized for display)
                save_img = self.normalize_for_display(self.processed_image)
                if file_path.endswith('.png'):
                    cv2.imwrite(file_path, save_img)
                else:
                    cv2.imwrite(file_path, save_img, [cv2.IMWRITE_TIFF_COMPRESSION, 1])
            else:
                # Save as raw 16-bit
                with open(file_path, 'wb') as f:
                    f.write(self.processed_image.astype(np.uint16).tobytes())

            messagebox.showinfo("Success", f"Image saved to: {file_path}")
            self.status_bar.config(text=f"Saved: {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image: {str(e)}")


def main():
    root = tk.Tk()
    app = SeamRemovalApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()