import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, Scale, HORIZONTAL
from PIL import Image, ImageTk
import threading
import queue
import time


class LiveStreamTuner:
    def __init__(self, stream_url="http://192.168.10.69:8080/?action=stream"):
        self.stream_url = stream_url
        self.frame_queue = queue.Queue(maxsize=1)

        # Default coefficients for Arducam 120°
        self.k1 = -0.38  # Barrel distortion (negative for barrel, positive for pincushion)
        self.k2 = 0.18  # Secondary radial
        self.p1 = 0.0005  # Tangential distortion x
        self.p2 = 0.0005  # Tangential distortion y
        self.k3 = 0.0  # Higher order radial
        self.balance = 0.2  # Balance between correction and cropping (0-1)

        # Initialize camera matrix
        self.width = 1080
        self.height = 1080
        self.camera_matrix = np.array([
            [self.width, 0, self.width / 2],
            [0, self.height, self.height / 2],
            [0, 0, 1]
        ], dtype=np.float32)

        # Start streaming thread
        self.streaming = True
        self.stream_thread = threading.Thread(target=self.capture_stream)
        self.stream_thread.daemon = True
        self.stream_thread.start()

        # Wait for first frame
        time.sleep(2)

        # Setup GUI
        self.setup_gui()

    def capture_stream(self):
        """Capture frames from the MJPEG stream"""
        cap = cv2.VideoCapture(self.stream_url)

        if not cap.isOpened():
            print(f"Error: Cannot open stream {self.stream_url}")
            return

        print(f"Connected to stream: {self.stream_url}")

        while self.streaming:
            ret, frame = cap.read()
            if not ret:
                print("Stream disconnected, reconnecting...")
                time.sleep(1)
                cap = cv2.VideoCapture(self.stream_url)
                continue

            # Update dimensions from first frame
            if self.width != frame.shape[1] or self.height != frame.shape[0]:
                self.width = frame.shape[1]
                self.height = frame.shape[0]
                self.camera_matrix = np.array([
                    [self.width, 0, self.width / 2],
                    [0, self.height, self.height / 2],
                    [0, 0, 1]
                ], dtype=np.float32)
                print(f"Updated resolution: {self.width}x{self.height}")

            # Put frame in queue (replace if full)
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass

            try:
                self.frame_queue.put(frame.copy(), block=False)
            except queue.Full:
                pass

        cap.release()

    def undistort_frame(self, frame):
        """Apply distortion correction to frame"""
        if frame is None:
            return None

        # Create distortion coefficients
        dist_coeffs = np.array([self.k1, self.k2, self.p1, self.p2, self.k3], dtype=np.float32)

        # Get optimal new camera matrix
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, dist_coeffs, (self.width, self.height),
            self.balance, (self.width, self.height)
        )

        # Undistort
        undistorted = cv2.undistort(frame, self.camera_matrix, dist_coeffs, None, new_camera_matrix)

        # Crop to ROI if not keeping all pixels
        if self.balance < 1.0:
            x, y, w, h = roi
            if w > 0 and h > 0:
                undistorted = undistorted[y:y + h, x:x + w]

        return undistorted

    def update_image(self):
        """Update the displayed image with current settings"""
        try:
            # Get latest frame
            frame = self.frame_queue.get_nowait()
        except queue.Empty:
            # No new frame, skip update
            self.root.after(50, self.update_image)
            return

        # Apply correction
        corrected = self.undistort_frame(frame)

        if corrected is not None:
            # Resize for display
            display_size = (1200, 800)
            display_frame = cv2.resize(corrected, display_size)

            # Add grid overlay for visual reference
            self.add_grid_overlay(display_frame)

            # Add text overlay
            cv2.putText(display_frame, f"k1={self.k1:.4f} k2={self.k2:.4f}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, f"p1={self.p1:.6f} p2={self.p2:.6f}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, f"Balance={self.balance:.2f}",
                        (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Convert to RGB for Tkinter
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            imgtk = ImageTk.PhotoImage(image=img)

            # Update label
            self.image_label.imgtk = imgtk
            self.image_label.configure(image=imgtk)

        # Schedule next update
        self.root.after(33, self.update_image)  # ~30 FPS

    def add_grid_overlay(self, frame):
        """Add grid to frame for visual distortion assessment"""
        h, w = frame.shape[:2]
        grid_size = 150

        # Draw grid lines
        for x in range(0, w, grid_size):
            cv2.line(frame, (x, 0), (x, h), (0, 255, 255), 1)
        for y in range(0, h, grid_size):
            cv2.line(frame, (0, y), (w, y), (0, 255, 255), 1)

        # Draw center cross
        cv2.line(frame, (w // 2, 0), (w // 2, h), (0, 0, 255), 2)
        cv2.line(frame, (0, h // 2), (w, h // 2), (0, 0, 255), 2)

        # Draw edge markers
        cv2.circle(frame, (10, 10), 5, (255, 0, 0), -1)  # Top-left
        cv2.circle(frame, (w - 10, 10), 5, (255, 0, 0), -1)  # Top-right
        cv2.circle(frame, (10, h - 10), 5, (255, 0, 0), -1)  # Bottom-left
        cv2.circle(frame, (w - 10, h - 10), 5, (255, 0, 0), -1)  # Bottom-right

    def on_k1_change(self, val):
        self.k1 = float(val)
        self.k1_label.config(text=f"k1: {self.k1:.4f}")

    def on_k2_change(self, val):
        self.k2 = float(val)
        self.k2_label.config(text=f"k2: {self.k2:.4f}")

    def on_p1_change(self, val):
        self.p1 = float(val)
        self.p1_label.config(text=f"p1: {self.p1:.6f}")

    def on_p2_change(self, val):
        self.p2 = float(val)
        self.p2_label.config(text=f"p2: {self.p2:.6f}")

    def on_balance_change(self, val):
        self.balance = float(val)
        self.balance_label.config(text=f"Balance: {self.balance:.2f}")

    def save_coefficients(self):
        """Save current coefficients to file"""
        coeffs = {
            'k1': self.k1,
            'k2': self.k2,
            'p1': self.p1,
            'p2': self.p2,
            'k3': self.k3,
            'balance': self.balance,
            'image_size': (self.width, self.height),
            'camera_matrix': self.camera_matrix,
            'camera': 'Arducam 120° IMX708',
            'stream_url': self.stream_url,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Save as numpy file
        np.save('arducam_coefficients.npy', coeffs)

        # Save as OpenCV YAML
        fs = cv2.FileStorage('arducam_calibration.yml', cv2.FILE_STORAGE_WRITE)
        fs.write('camera_matrix', self.camera_matrix)
        fs.write('distortion_coefficients', np.array([[self.k1, self.k2, self.p1, self.p2, self.k3]]))
        fs.write('image_width', self.width)
        fs.write('image_height', self.height)
        fs.release()

        # Save calibration parameters as XML file
        fs = cv2.FileStorage('arducam_calibration.xml', cv2.FILE_STORAGE_WRITE)
        fs.write('camera_matrix', self.camera_matrix)
        fs.write('distortion_coefficients', np.array([[self.k1, self.k2, self.p1, self.p2, self.k3]]))
        fs.write('image_width', self.width)
        fs.write('image_height', self.height)
        fs.release()

        # Save as simple text file
        with open('arducam_coefficients.txt', 'w') as f:
            f.write(f"# Arducam 120° Camera Calibration\n")
            f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Stream URL: {self.stream_url}\n\n")
            f.write(f"# Distortion Coefficients\n")
            f.write(f"k1 = {self.k1:.6f}  # Radial distortion 1\n")
            f.write(f"k2 = {self.k2:.6f}  # Radial distortion 2\n")
            f.write(f"p1 = {self.p1:.6f}  # Tangential distortion 1\n")
            f.write(f"p2 = {self.p2:.6f}  # Tangential distortion 2\n")
            f.write(f"k3 = {self.k3:.6f}  # Radial distortion 3\n\n")
            f.write(f"# Camera Matrix\n")
            f.write(f"fx = {self.camera_matrix[0, 0]:.2f}\n")
            f.write(f"fy = {self.camera_matrix[1, 1]:.2f}\n")
            f.write(f"cx = {self.camera_matrix[0, 2]:.2f}\n")
            f.write(f"cy = {self.camera_matrix[1, 2]:.2f}\n\n")
            f.write(f"# Balance (0=crop more, 1=keep all pixels)\n")
            f.write(f"balance = {self.balance:.2f}\n")

        print(f"\n✓ Coefficients saved:")
        print(f"  k1={self.k1:.4f}, k2={self.k2:.4f}")
        print(f"  p1={self.p1:.6f}, p2={self.p2:.6f}")
        print(f"  balance={self.balance:.2f}")
        print(f"  Files: arducam_coefficients.npy, .yml, .txt")

    def reset_to_default(self):
        """Reset to Arducam 120° default values"""
        self.k1 = -0.38
        self.k2 = 0.18
        self.p1 = 0.0005
        self.p2 = 0.0005
        self.k3 = 0.0
        self.balance = 0.2

        # Update sliders
        self.k1_slider.set(self.k1)
        self.k2_slider.set(self.k2)
        self.p1_slider.set(self.p1)
        self.p2_slider.set(self.p2)
        self.balance_slider.set(self.balance)

        # Update labels
        self.k1_label.config(text=f"k1: {self.k1:.4f}")
        self.k2_label.config(text=f"k2: {self.k2:.4f}")
        self.p1_label.config(text=f"p1: {self.p1:.6f}")
        self.p2_label.config(text=f"p2: {self.p2:.6f}")
        self.balance_label.config(text=f"Balance: {self.balance:.2f}")

        print("✓ Reset to Arducam 120° defaults")

    def setup_gui(self):
        """Setup the Tkinter GUI"""
        self.root = tk.Tk()
        self.root.title(f"Arducam 120° Live Stream Tuner - {self.stream_url}")
        self.root.geometry("1200x800")

        # Create frames
        left_frame = ttk.Frame(self.root, padding="10")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        right_frame = ttk.Frame(self.root, padding="10")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Image display
        ttk.Label(right_frame, text="Live Corrected Stream",
                  font=("Arial", 16, "bold")).pack(pady=5)

        # Placeholder image
        placeholder = np.zeros((360, 640, 3), dtype=np.uint8)
        placeholder_rgb = cv2.cvtColor(placeholder, cv2.COLOR_BGR2RGB)
        placeholder_img = Image.fromarray(placeholder_rgb)
        self.imgtk = ImageTk.PhotoImage(image=placeholder_img)

        self.image_label = ttk.Label(right_frame, image=self.imgtk)
        self.image_label.pack(pady=10)

        # Connection status
        self.status_label = ttk.Label(right_frame, text="Connecting to stream...",
                                      font=("Arial", 10))
        self.status_label.pack(pady=5)

        # Controls frame
        controls_frame = ttk.LabelFrame(left_frame, text="Distortion Controls", padding="15")
        controls_frame.pack(fill="both", expand=True, pady=10)

        # k1 slider (Radial distortion 1 - MAIN CONTROL)
        ttk.Label(controls_frame, text="k1 - Barrel Distortion:",
                  font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.k1_slider = Scale(controls_frame, from_=-1.0, to=0.0, resolution=0.001,
                               orient=HORIZONTAL, length=400, command=self.on_k1_change)
        self.k1_slider.set(self.k1)
        self.k1_slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.k1_label = ttk.Label(controls_frame, text=f"k1: {self.k1:.4f}")
        self.k1_label.grid(row=2, column=0, sticky="w")
        ttk.Label(controls_frame, text="← More barrel | More pincushion →",
                  font=("Arial", 9)).grid(row=2, column=1, sticky="e")

        # k2 slider (Radial distortion 2)
        ttk.Label(controls_frame, text="k2 - Radial Distortion 2:").grid(row=3, column=0, sticky="w", pady=(10, 5))
        self.k2_slider = Scale(controls_frame, from_=0.0, to=0.5, resolution=0.001,
                               orient=HORIZONTAL, length=400, command=self.on_k2_change)
        self.k2_slider.set(self.k2)
        self.k2_slider.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.k2_label = ttk.Label(controls_frame, text=f"k2: {self.k2:.4f}")
        self.k2_label.grid(row=5, column=0, sticky="w")

        # p1 slider (Tangential distortion x)
        ttk.Label(controls_frame, text="p1 - Tangential Distortion X:").grid(row=6, column=0, sticky="w", pady=(10, 5))
        self.p1_slider = Scale(controls_frame, from_=-0.01, to=0.01, resolution=0.0001,
                               orient=HORIZONTAL, length=400, command=self.on_p1_change)
        self.p1_slider.set(self.p1)
        self.p1_slider.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.p1_label = ttk.Label(controls_frame, text=f"p1: {self.p1:.6f}")
        self.p1_label.grid(row=8, column=0, sticky="w")

        # p2 slider (Tangential distortion y)
        ttk.Label(controls_frame, text="p2 - Tangential Distortion Y:").grid(row=9, column=0, sticky="w", pady=(10, 5))
        self.p2_slider = Scale(controls_frame, from_=-0.01, to=0.01, resolution=0.0001,
                               orient=HORIZONTAL, length=400, command=self.on_p2_change)
        self.p2_slider.set(self.p2)
        self.p2_slider.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.p2_label = ttk.Label(controls_frame, text=f"p2: {self.p2:.6f}")
        self.p2_label.grid(row=11, column=0, sticky="w")

        # Balance slider
        ttk.Label(controls_frame, text="Balance (Crop vs Black Borders):",
                  font=("Arial", 11, "bold")).grid(row=12, column=0, sticky="w", pady=(20, 5))
        self.balance_slider = Scale(controls_frame, from_=0.0, to=1.0, resolution=0.01,
                                    orient=HORIZONTAL, length=400, command=self.on_balance_change)
        self.balance_slider.set(self.balance)
        self.balance_slider.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.balance_label = ttk.Label(controls_frame, text=f"Balance: {self.balance:.2f}")
        self.balance_label.grid(row=14, column=0, sticky="w")
        ttk.Label(controls_frame, text="← Crop more | Keep all pixels →",
                  font=("Arial", 9)).grid(row=14, column=1, sticky="e")

        # Button frame
        button_frame = ttk.Frame(controls_frame)
        button_frame.grid(row=15, column=0, columnspan=2, pady=(30, 10))

        ttk.Button(button_frame, text="Save Coefficients",
                   command=self.save_coefficients, width=20).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Reset to Default",
                   command=self.reset_to_default, width=20).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Exit",
                   command=self.root.quit, width=20).pack(side="left", padx=5)

        # Instructions
        instructions = ttk.LabelFrame(left_frame, text="Tuning Instructions", padding="10")
        instructions.pack(fill="x", pady=10)

        instruction_text = """1. Start with k1 ≈ -0.38 (Arducam 120° default)
2. Adjust k1 until straight lines at edges are straight
3. Use balance=0.2 for side-only correction
4. Check grid lines - they should be straight
5. Save when edges look straight but center unchanged
6. Blue dots at corners should align with grid"""

        ttk.Label(instructions, text=instruction_text, justify="left",
                  font=("Arial", 9)).pack()

        # Start image update loop
        self.root.after(100, self.update_image)

    def run(self):
        self.root.mainloop()
        self.streaming = False
        self.stream_thread.join(timeout=2.0)


# Run the tuner
if __name__ == "__main__":
    # Update this URL to match your Raspberry Pi IP
    stream_url = "http://192.168.10.69:8080/?action=stream"

    print("=" * 60)
    print("Arducam 120° Live Stream Distortion Tuner")
    print("=" * 60)
    print(f"Connecting to: {stream_url}")
    print("\nTuning Guide:")
    print("1. k1 controls barrel distortion (negative values straighten edges)")
    print("2. Start with k1 = -0.38 and adjust until edges are straight")
    print("3. Use balance=0.2 for focusing correction on sides")
    print("4. Grid lines help visualize straightness")
    print("=" * 60)

    tuner = LiveStreamTuner(stream_url)
    tuner.run()