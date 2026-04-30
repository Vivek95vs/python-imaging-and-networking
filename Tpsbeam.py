import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import SimpleITK as sitk
import os
from scipy import ndimage
from scipy.spatial import distance
from matplotlib.patches import Rectangle, Polygon, Ellipse, Circle
import matplotlib.gridspec as gridspec
from matplotlib.path import Path
import warnings

warnings.filterwarnings('ignore')


class CTBeamSimulator:
    def __init__(self, ct_data=None, pixel_spacing=[1.0, 1.0, 1.0]):
        """
        Initialize CT Beam Simulator

        Parameters:
        -----------
        ct_data : 3D numpy array
            CT volume data (z, y, x) - DICOM order
        pixel_spacing : list
            [z_spacing, y_spacing, x_spacing] in mm
        """
        self.ct_data = ct_data
        self.pixel_spacing = pixel_spacing

        # Beam parameters
        self.beam_center = None
        self.beam_size = [50, 50]  # [width, height] in mm
        self.beam_angle = 0  # degrees
        self.beam_energy = 6  # MV

        # Visualization parameters
        self.axial_slice = 0
        self.sagittal_slice = 0
        self.coronal_slice = 0

        # Figure and axes
        self.fig = None
        self.ax_axial = None
        self.ax_sagittal = None
        self.ax_coronal = None

        # For angle adjustment
        self.angle_dragging = False
        self.angle_start_point = None
        self.angle_patches = []

    def load_dicom_series(self, folder_path):
        """Load DICOM series from folder"""
        print(f"Loading DICOM series from: {folder_path}")

        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        # Read DICOM series using SimpleITK
        reader = sitk.ImageSeriesReader()
        dicom_names = reader.GetGDCMSeriesFileNames(folder_path)

        if len(dicom_names) == 0:
            raise ValueError(f"No DICOM files found in {folder_path}")

        reader.SetFileNames(dicom_names)
        image = reader.Execute()

        # Convert to numpy array - SimpleITK returns (z, y, x)
        self.ct_data = sitk.GetArrayFromImage(image)

        # Get pixel spacing
        spacing = image.GetSpacing()  # (x, y, z) spacing in mm
        # Convert to (z, y, x) order
        self.pixel_spacing = [spacing[2], spacing[1], spacing[0]]

        # Get origin and direction for proper orientation
        self.origin = image.GetOrigin()
        self.direction = image.GetDirection()

        print(f"Loaded CT volume shape: {self.ct_data.shape}")
        print(f"Pixel spacing (z, y, x): {self.pixel_spacing} mm")

        # Set initial beam center to middle of volume
        if self.ct_data is not None:
            self.beam_center = [
                self.ct_data.shape[0] // 2,
                self.ct_data.shape[1] // 2,
                self.ct_data.shape[2] // 2
            ]

        return self.ct_data

    def normalize_ct(self, data, window_center=40, window_width=400):
        """Normalize CT values for better visualization"""
        min_val = window_center - window_width / 2
        max_val = window_center + window_width / 2

        data_normalized = np.clip(data, min_val, max_val)
        data_normalized = (data_normalized - min_val) / (max_val - min_val)

        return np.clip(data_normalized, 0, 1)

    def get_rotated_beam_corners(self, center_x, center_y, width, height, angle):
        """Get corners of rotated rectangle"""
        angle_rad = np.deg2rad(angle)

        # Half dimensions
        half_w = width / 2
        half_h = height / 2

        # Original corners (unrotated)
        corners = np.array([
            [-half_w, -half_h],
            [half_w, -half_h],
            [half_w, half_h],
            [-half_w, half_h]
        ])

        # Rotation matrix
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        rotation_matrix = np.array([[cos_a, -sin_a], [sin_a, cos_a]])

        # Rotate corners
        rotated_corners = np.dot(corners, rotation_matrix.T)

        # Translate to center
        rotated_corners[:, 0] += center_x
        rotated_corners[:, 1] += center_y

        return rotated_corners

    def update_beam_visualization(self):
        """Update beam visualization on all views"""
        if self.beam_center is None or self.ct_data is None:
            return

        # Clear existing patches and lines
        for ax in [self.ax_axial, self.ax_sagittal, self.ax_coronal]:
            if ax:
                # Remove all patches and lines except the image
                for artist in ax.patches + ax.lines:
                    artist.remove()

        # Convert beam size from mm to pixels for each view
        # Beam size: [width, height] in mm

        # 1. Axial view (x-y plane at z = beam_center[0])
        if self.axial_slice == self.beam_center[0]:
            beam_width_px = self.beam_size[0] / self.pixel_spacing[2]  # x direction
            beam_height_px = self.beam_size[1] / self.pixel_spacing[1]  # y direction

            corners = self.get_rotated_beam_corners(
                self.beam_center[2],  # x center
                self.beam_center[1],  # y center
                beam_width_px,
                beam_height_px,
                self.beam_angle
            )

            # Create polygon for rotated beam
            beam_poly = Polygon(corners, closed=True,
                                linewidth=2, edgecolor='red',
                                facecolor='none', alpha=0.7)
            self.ax_axial.add_patch(beam_poly)

            # Add beam center marker
            self.ax_axial.plot(self.beam_center[2], self.beam_center[1],
                               'r+', markersize=10, markeredgewidth=2)

        # 2. Sagittal view (y-z plane at x = beam_center[2])
        # In sagittal view, x-axis = y, y-axis = z
        beam_width_px = self.beam_size[0] / self.pixel_spacing[1]  # y direction
        beam_height_px = self.beam_size[1] / self.pixel_spacing[0]  # z direction

        corners = self.get_rotated_beam_corners(
            self.beam_center[1],  # y center
            self.beam_center[0],  # z center
            beam_width_px,
            beam_height_px,
            self.beam_angle
        )

        beam_poly = Polygon(corners, closed=True,
                            linewidth=2, edgecolor='red',
                            facecolor='none', alpha=0.7)
        self.ax_sagittal.add_patch(beam_poly)

        # Add beam center marker
        self.ax_sagittal.plot(self.beam_center[1], self.beam_center[0],
                              'r+', markersize=10, markeredgewidth=2)

        # 3. Coronal view (x-z plane at y = beam_center[1])
        # In coronal view, x-axis = x, y-axis = z
        beam_width_px = self.beam_size[0] / self.pixel_spacing[2]  # x direction
        beam_height_px = self.beam_size[1] / self.pixel_spacing[0]  # z direction

        corners = self.get_rotated_beam_corners(
            self.beam_center[2],  # x center
            self.beam_center[0],  # z center
            beam_width_px,
            beam_height_px,
            self.beam_angle
        )

        beam_poly = Polygon(corners, closed=True,
                            linewidth=2, edgecolor='red',
                            facecolor='none', alpha=0.7)
        self.ax_coronal.add_patch(beam_poly)

        # Add beam center marker
        self.ax_coronal.plot(self.beam_center[2], self.beam_center[0],
                             'r+', markersize=10, markeredgewidth=2)

        # Add angle adjustment handles
        self.add_angle_handles()

        # Update controls text
        self.update_controls_text()

        self.fig.canvas.draw_idle()

    def add_angle_handles(self):
        """Add handles for interactive angle adjustment"""
        # Remove old handles
        for patch in self.angle_patches:
            if patch in self.ax_axial.patches or patch in self.ax_axial.lines:
                patch.remove()
        self.angle_patches.clear()

        # Add angle adjustment handle on axial view
        if self.ax_axial and self.beam_center:
            # Calculate handle position (at edge of beam)
            angle_rad = np.deg2rad(self.beam_angle)
            handle_distance = max(self.beam_size[0], self.beam_size[1]) / self.pixel_spacing[2] / 2 + 10

            handle_x = self.beam_center[2] + handle_distance * np.cos(angle_rad)
            handle_y = self.beam_center[1] + handle_distance * np.sin(angle_rad)

            # Create handle
            handle = Circle((handle_x, handle_y), radius=5,
                            facecolor='yellow', edgecolor='black',
                            alpha=0.7, picker=True, zorder=10)
            self.ax_axial.add_patch(handle)
            self.angle_patches.append(handle)

            # Add line from center to handle
            line = self.ax_axial.plot([self.beam_center[2], handle_x],
                                      [self.beam_center[1], handle_y],
                                      'y--', alpha=0.5, linewidth=1.5)[0]
            self.angle_patches.append(line)

    def update_controls_text(self):
        """Update the controls text display"""
        if hasattr(self, 'controls_text') and self.controls_text:
            self.controls_text.set_text(
                f"Current Angle: {self.beam_angle:.1f}°\n"
                f"Beam Size: {self.beam_size[0]}×{self.beam_size[1]} mm\n"
                f"Center: ({self.beam_center[2]}, {self.beam_center[1]}, {self.beam_center[0]})"
            )

    def on_press(self, event):
        """Handle mouse press events for angle adjustment"""
        if event.inaxes == self.ax_axial:
            # Check if angle handle was clicked
            if event.inaxes and len(self.angle_patches) > 0:
                handle = self.angle_patches[0]
                contains, _ = handle.contains(event)
                if contains:
                    self.angle_dragging = True
                    self.angle_start_point = (event.xdata, event.ydata)
                    return True  # Stop event propagation

    def on_motion(self, event):
        """Handle mouse motion for angle adjustment"""
        if self.angle_dragging and event.inaxes == self.ax_axial:
            if event.xdata is not None and event.ydata is not None:
                # Calculate new angle
                dx = event.xdata - self.beam_center[2]
                dy = event.ydata - self.beam_center[1]

                # Calculate angle in degrees (0-360)
                new_angle = np.degrees(np.arctan2(dy, dx)) % 360

                # Update beam angle
                self.beam_angle = new_angle

                # Update visualization
                self.update_beam_visualization()

    def on_release(self, event):
        """Handle mouse release events"""
        self.angle_dragging = False
        self.angle_start_point = None

    def on_click(self, event):
        """Handle mouse clicks to set beam center"""
        if event.inaxes is None or self.angle_dragging:
            return

        if event.inaxes == self.ax_axial:
            # Axial view click - set x,y coordinates
            x, y = int(event.xdata), int(event.ydata)
            self.beam_center = [self.axial_slice, y, x]
            print(f"Beam center set to: ({x}, {y}, {self.axial_slice}) [x, y, z]")

        elif event.inaxes == self.ax_sagittal:
            # Sagittal view click - set y,z coordinates
            y, z = int(event.xdata), int(event.ydata)
            self.beam_center = [z, y, self.sagittal_slice]
            print(f"Beam center set to: ({self.sagittal_slice}, {y}, {z}) [x, y, z]")

        elif event.inaxes == self.ax_coronal:
            # Coronal view click - set x,z coordinates
            x, z = int(event.xdata), int(event.ydata)
            self.beam_center = [z, self.coronal_slice, x]
            print(f"Beam center set to: ({x}, {self.coronal_slice}, {z}) [x, y, z]")

        # Update visualization
        self.update_beam_visualization()

    def visualize_three_views(self):
        """Create interactive visualization with three views"""
        if self.ct_data is None:
            raise ValueError("No CT data loaded. Please load CT data first.")

        # Create figure with subplots
        self.fig = plt.figure(figsize=(16, 10))
        gs = gridspec.GridSpec(2, 4, height_ratios=[4, 1], width_ratios=[1, 1, 1, 0.3])

        # Create axes for CT views
        self.ax_axial = plt.subplot(gs[0, 0])
        self.ax_sagittal = plt.subplot(gs[0, 1])
        self.ax_coronal = plt.subplot(gs[0, 2])
        ax_controls = plt.subplot(gs[0, 3])

        # Create axes for sliders
        ax_slider_axial = plt.subplot(gs[1, 0])
        ax_slider_sagittal = plt.subplot(gs[1, 1])
        ax_slider_coronal = plt.subplot(gs[1, 2])

        # Normalize CT data for visualization
        ct_normalized = self.normalize_ct(self.ct_data)

        # Initial slice indices
        self.axial_slice = self.ct_data.shape[0] // 2
        self.sagittal_slice = self.ct_data.shape[2] // 2
        self.coronal_slice = self.ct_data.shape[1] // 2

        # Display axial view (z-slice)
        axial_slice_data = ct_normalized[self.axial_slice, :, :]
        self.img_axial = self.ax_axial.imshow(
            axial_slice_data,
            cmap='gray',
            aspect='auto',
            origin='lower',
            extent=[0, axial_slice_data.shape[1], 0, axial_slice_data.shape[0]]
        )
        self.ax_axial.set_title(f'Axial View (Z={self.axial_slice})')
        self.ax_axial.set_xlabel('X position')
        self.ax_axial.set_ylabel('Y position')
        self.ax_axial.grid(True, alpha=0.3, linestyle='--')

        # Display sagittal view (x-slice) - PROPERLY ORIENTED
        sagittal_slice_data = ct_normalized[:, :, self.sagittal_slice]
        self.img_sagittal = self.ax_sagittal.imshow(
            sagittal_slice_data.T,  # Transpose for correct orientation
            cmap='gray',
            aspect='auto',
            origin='lower',
            extent=[0, sagittal_slice_data.shape[1], 0, sagittal_slice_data.shape[0]]
        )
        self.ax_sagittal.set_title(f'Sagittal View (X={self.sagittal_slice})')
        self.ax_sagittal.set_xlabel('Y position')
        self.ax_sagittal.set_ylabel('Z position')
        self.ax_sagittal.grid(True, alpha=0.3, linestyle='--')

        # Display coronal view (y-slice) - PROPERLY ORIENTED
        coronal_slice_data = ct_normalized[:, self.coronal_slice, :]
        self.img_coronal = self.ax_coronal.imshow(
            coronal_slice_data.T,  # Transpose for correct orientation
            cmap='gray',
            aspect='auto',
            origin='lower',
            extent=[0, coronal_slice_data.shape[1], 0, coronal_slice_data.shape[0]]
        )
        self.ax_coronal.set_title(f'Coronal/Frontal View (Y={self.coronal_slice})')
        self.ax_coronal.set_xlabel('X position')
        self.ax_coronal.set_ylabel('Z position')
        self.ax_coronal.grid(True, alpha=0.3, linestyle='--')

        # Add controls panel
        ax_controls.axis('off')
        ax_controls.set_title('Controls', fontsize=12, fontweight='bold')

        # Add controls text
        controls_info = [
            'INSTRUCTIONS:',
            '1. Click on any view to',
            '   set beam center',
            '',
            '2. Drag YELLOW CIRCLE to',
            '   adjust beam angle',
            '',
            '3. Use sliders below to',
            '   navigate slices',
            '',
            'BEAM INFO:',
            f'Angle: {self.beam_angle:.1f}°',
            f'Size: {self.beam_size[0]}×{self.beam_size[1]} mm'
        ]

        for i, line in enumerate(controls_info):
            color = 'blue' if 'INSTRUCTIONS' in line else ('red' if 'BEAM INFO' in line else 'black')
            weight = 'bold' if 'INSTRUCTIONS' in line or 'BEAM INFO' in line else 'normal'
            ax_controls.text(0.05, 0.95 - i * 0.05, line,
                             transform=ax_controls.transAxes,
                             fontsize=9, verticalalignment='top',
                             color=color, fontweight=weight)

        # Create dynamic text for beam info
        self.controls_text = ax_controls.text(0.05, 0.45, '',
                                              transform=ax_controls.transAxes,
                                              fontsize=9, verticalalignment='top')
        self.update_controls_text()

        # Create sliders
        slider_axial = Slider(
            ax_slider_axial,
            'Axial Slice (Z)',
            0, self.ct_data.shape[0] - 1,
            valinit=self.axial_slice,
            valstep=1,
            color='lightblue'
        )

        slider_sagittal = Slider(
            ax_slider_sagittal,
            'Sagittal Slice (X)',
            0, self.ct_data.shape[2] - 1,
            valinit=self.sagittal_slice,
            valstep=1,
            color='lightgreen'
        )

        slider_coronal = Slider(
            ax_slider_coronal,
            'Coronal Slice (Y)',
            0, self.ct_data.shape[1] - 1,
            valinit=self.coronal_slice,
            valstep=1,
            color='lightcoral'
        )

        # Update functions for sliders
        def update_axial(val):
            self.axial_slice = int(val)
            self.img_axial.set_data(ct_normalized[self.axial_slice, :, :])
            self.ax_axial.set_title(f'Axial View (Z={self.axial_slice})')
            self.update_beam_visualization()
            self.fig.canvas.draw_idle()

        def update_sagittal(val):
            self.sagittal_slice = int(val)
            slice_data = ct_normalized[:, :, self.sagittal_slice]
            self.img_sagittal.set_data(slice_data.T)
            self.ax_sagittal.set_title(f'Sagittal View (X={self.sagittal_slice})')
            self.update_beam_visualization()
            self.fig.canvas.draw_idle()

        def update_coronal(val):
            self.coronal_slice = int(val)
            slice_data = ct_normalized[:, self.coronal_slice, :]
            self.img_coronal.set_data(slice_data.T)
            self.ax_coronal.set_title(f'Coronal View (Y={self.coronal_slice})')
            self.update_beam_visualization()
            self.fig.canvas.draw_idle()

        # Connect sliders to update functions
        slider_axial.on_changed(update_axial)
        slider_sagittal.on_changed(update_sagittal)
        slider_coronal.on_changed(update_coronal)

        # Connect mouse events
        self.fig.canvas.mpl_connect('button_press_event', self.on_press)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)

        # Add beam visualization
        self.update_beam_visualization()

        plt.tight_layout()
        plt.show()

    def create_beam_mask(self, view='axial'):
        """Create beam mask for the specified view"""
        if self.beam_center is None:
            raise ValueError("Beam center not set")

        if view == 'axial':
            # Create meshgrid
            y, x = np.mgrid[:self.ct_data.shape[1], :self.ct_data.shape[2]]

            # Convert to distances from beam center
            dx = (x - self.beam_center[2]) * self.pixel_spacing[2]
            dy = (y - self.beam_center[1]) * self.pixel_spacing[1]

            # Rotate coordinates
            angle_rad = np.deg2rad(self.beam_angle)
            cos_a = np.cos(angle_rad)
            sin_a = np.sin(angle_rad)

            x_rot = dx * cos_a + dy * sin_a
            y_rot = -dx * sin_a + dy * cos_a

            # Create mask
            mask = (np.abs(x_rot) <= self.beam_size[0] / 2) & \
                   (np.abs(y_rot) <= self.beam_size[1] / 2)

        elif view == 'sagittal':
            # Sagittal view: y-z plane
            z, y = np.mgrid[:self.ct_data.shape[0], :self.ct_data.shape[1]]

            dx = (y - self.beam_center[1]) * self.pixel_spacing[1]
            dy = (z - self.beam_center[0]) * self.pixel_spacing[0]

            angle_rad = np.deg2rad(self.beam_angle)
            cos_a = np.cos(angle_rad)
            sin_a = np.sin(angle_rad)

            x_rot = dx * cos_a + dy * sin_a
            y_rot = -dx * sin_a + dy * cos_a

            mask = (np.abs(x_rot) <= self.beam_size[0] / 2) & \
                   (np.abs(y_rot) <= self.beam_size[1] / 2)

        elif view == 'coronal':
            # Coronal view: x-z plane
            z, x = np.mgrid[:self.ct_data.shape[0], :self.ct_data.shape[2]]

            dx = (x - self.beam_center[2]) * self.pixel_spacing[2]
            dy = (z - self.beam_center[0]) * self.pixel_spacing[0]

            angle_rad = np.deg2rad(self.beam_angle)
            cos_a = np.cos(angle_rad)
            sin_a = np.sin(angle_rad)

            x_rot = dx * cos_a + dy * sin_a
            y_rot = -dx * sin_a + dy * cos_a

            mask = (np.abs(x_rot) <= self.beam_size[0] / 2) & \
                   (np.abs(y_rot) <= self.beam_size[1] / 2)

        return mask

    def calculate_dose_simulation(self, view='axial'):
        """Simple dose calculation simulation"""
        mask = self.create_beam_mask(view)

        if view == 'axial':
            center = [self.beam_center[2], self.beam_center[1]]
            shape = (self.ct_data.shape[1], self.ct_data.shape[2])
        elif view == 'sagittal':
            center = [self.beam_center[1], self.beam_center[0]]
            shape = (self.ct_data.shape[0], self.ct_data.shape[1])
        elif view == 'coronal':
            center = [self.beam_center[2], self.beam_center[0]]
            shape = (self.ct_data.shape[0], self.ct_data.shape[2])

        # Create grid for Gaussian
        y, x = np.ogrid[:shape[0], :shape[1]]
        distance = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)

        # Apply Gaussian dose distribution
        sigma = min(shape) / 6
        dose = np.exp(-distance ** 2 / (2 * sigma ** 2))
        dose[~mask] = 0

        return dose

    def plot_dose_distribution(self):
        """Plot dose distribution for all three views"""
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        dose_axial = self.calculate_dose_simulation('axial')
        dose_sagittal = self.calculate_dose_simulation('sagittal')
        dose_coronal = self.calculate_dose_simulation('coronal')

        # Plot axial dose
        im1 = axes[0].imshow(dose_axial, cmap='hot', alpha=0.7,
                             aspect='auto', origin='lower')
        axes[0].set_title(f'Dose - Axial View\nAngle: {self.beam_angle:.1f}°')
        axes[0].set_xlabel('X')
        axes[0].set_ylabel('Y')
        plt.colorbar(im1, ax=axes[0], label='Relative Dose')

        # Plot sagittal dose
        im2 = axes[1].imshow(dose_sagittal, cmap='hot', alpha=0.7,
                             aspect='auto', origin='lower')
        axes[1].set_title(f'Dose - Sagittal View\nAngle: {self.beam_angle:.1f}°')
        axes[1].set_xlabel('Y')
        axes[1].set_ylabel('Z')
        plt.colorbar(im2, ax=axes[1], label='Relative Dose')

        # Plot coronal dose
        im3 = axes[2].imshow(dose_coronal, cmap='hot', alpha=0.7,
                             aspect='auto', origin='lower')
        axes[2].set_title(f'Dose - Coronal View\nAngle: {self.beam_angle:.1f}°')
        axes[2].set_xlabel('X')
        axes[2].set_ylabel('Z')
        plt.colorbar(im3, ax=axes[2], label='Relative Dose')

        plt.tight_layout()
        plt.show()


# Utility functions
def create_sample_ct_data():
    """Create synthetic CT data for demonstration"""
    print("Creating synthetic CT data...")

    # Create a simple phantom
    size = (100, 256, 256)  # (z, y, x)
    ct_data = np.random.normal(0, 20, size)  # Background noise

    z_center, y_center, x_center = size[0] // 2, size[1] // 2, size[2] // 2

    # Create ellipsoid phantom (body)
    for z in range(size[0]):
        for y in range(size[1]):
            for x in range(size[2]):
                # Body (water)
                body_dist = ((y - y_center) / 100) ** 2 + ((x - x_center) / 100) ** 2
                if body_dist < 1:
                    ct_data[z, y, x] = 0  # Water HU

                # Spine (bone)
                spine_dist = ((z - z_center) / 30) ** 2 + ((y - y_center) / 10) ** 2 + ((x - x_center) / 10) ** 2
                if spine_dist < 1:
                    ct_data[z, y, x] = 400  # Bone HU

                # Tumor
                tumor_dist = ((z - z_center) / 15) ** 2 + ((y - y_center - 30) / 20) ** 2 + (
                            (x - x_center - 30) / 20) ** 2
                if tumor_dist < 1:
                    ct_data[z, y, x] = 60  # Soft tissue HU

                # Lung (on other side)
                lung_dist = ((z - z_center) / 40) ** 2 + ((y - y_center + 40) / 60) ** 2 + (
                            (x - x_center + 40) / 60) ** 2
                if lung_dist < 1:
                    ct_data[z, y, x] = -500  # Lung HU

    # Add some Gaussian smoothing
    ct_data = ndimage.gaussian_filter(ct_data, sigma=1)

    return ct_data


# Main execution
if __name__ == "__main__":
    # Create simulator instance
    simulator = CTBeamSimulator()

    print("=" * 60)
    print("CT BEAM SIMULATOR with Interactive Angle Control")
    print("=" * 60)

    # Use your DICOM folder path
    dicom_folder = r"D:\Subam site\25-11-2025\F0\Imaging data\ReferenceImages\CT\RawCT"

    print(f"Loading DICOM data from: {dicom_folder}")

    try:
        # Try to load DICOM data
        simulator.load_dicom_series(dicom_folder)
        print("✓ DICOM data loaded successfully!")

    except Exception as e:
        print(f"✗ Error loading DICOM data: {e}")
        print("Using synthetic data instead...")
        simulator.ct_data = create_sample_ct_data()
        simulator.pixel_spacing = [2.0, 1.0, 1.0]

    # Set initial parameters
    if simulator.ct_data is not None:
        simulator.beam_center = [
            simulator.ct_data.shape[0] // 2,
            simulator.ct_data.shape[1] // 2,
            simulator.ct_data.shape[2] // 2
        ]

        simulator.beam_size = [60, 40]  # Width x Height in mm
        simulator.beam_angle = 30  # Initial angle

        print(f"\nCT Data Info:")
        print(f"  Shape: {simulator.ct_data.shape}")
        print(f"  Spacing: {simulator.pixel_spacing} mm")
        print(f"  Beam Center: {simulator.beam_center}")

        print("\n" + "=" * 60)
        print("INTERACTIVE CONTROLS:")
        print("1. Click on any view to set beam center")
        print("2. Drag the YELLOW CIRCLE to adjust beam angle")
        print("3. Use sliders to navigate through slices")
        print("=" * 60)

        # Launch interactive viewer
        simulator.visualize_three_views()

        # Optional: Show dose distribution
        try:
            show_dose = input("\nShow dose distribution? (y/n): ").strip().lower()
            if show_dose == 'y':
                simulator.plot_dose_distribution()
        except:
            print("\nWindow closed.")

        print("\nSimulation completed successfully!")
    else:
        print("ERROR: No CT data available. Exiting...")
#====================================orientation issue=====================================

