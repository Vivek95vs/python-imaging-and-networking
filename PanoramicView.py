"""
Dental CBCT Panoramic: Select Slice → Draw Curve → Generate Panoramic
Complete Single Solution
"""

import numpy as np
import pydicom
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.interpolate import interp1d
import warnings
warnings.filterwarnings('ignore')

class DentalPanoramicCreator:
    def __init__(self, slices_dir):
        """
        Select slice → Draw curve → Generate panoramic

        Args:
            slices_dir: Directory with DICOM slices
        """
        self.slices_dir = Path(slices_dir)
        self.volume = None
        self.selected_slice_idx = None
        self.curve_points = None
        self.panoramic_image = None

    def load_all_slices(self):
        """Load all DICOM slices into 3D volume"""
        print("📂 Loading DICOM slices...")

        # Get all DICOM files
        dcm_files = sorted(self.slices_dir.glob("*.dcm"))
        if not dcm_files:
            dcm_files = sorted(self.slices_dir.glob("slice_*.dcm"))

        if not dcm_files:
            raise FileNotFoundError(f"No DICOM files found in {self.slices_dir}")

        print(f"📊 Found {len(dcm_files)} slices")

        # Load first slice for dimensions
        ds0 = pydicom.dcmread(str(dcm_files[0]))
        rows, cols = ds0.Rows, ds0.Columns
        num_slices = len(dcm_files)

        # Create volume
        self.volume = np.zeros((num_slices, rows, cols), dtype=np.float32)

        # Load all slices
        for i, dcm_file in enumerate(dcm_files):
            ds = pydicom.dcmread(str(dcm_file))
            self.volume[i] = ds.pixel_array.astype(np.float32)

        print(f"✅ Loaded volume: {self.volume.shape}")
        return self.volume

    def select_slice_interactive(self):
        """
        Interactive slice selection with preview
        Returns selected slice index
        """
        if self.volume is None:
            self.load_all_slices()

        print("\n🎯 SLICE SELECTION")
        print("="*50)
        print(f"Total slices available: {self.volume.shape[0]}")
        print("Viewing slice range...")

        # Show slice preview
        self._preview_slices()

        # Ask user to select slice
        while True:
            try:
                print("\n" + "-"*50)
                slice_idx = int(input(f"Enter slice number to draw on (0-{self.volume.shape[0]-1}): "))

                if 0 <= slice_idx < self.volume.shape[0]:
                    self.selected_slice_idx = slice_idx
                    print(f"✅ Selected slice {slice_idx}")

                    # Show selected slice
                    self._show_selected_slice()

                    # Confirm selection
                    confirm = input("Use this slice? (y/n): ").lower()
                    if confirm == 'y':
                        break
                    else:
                        print("Select another slice...")
                else:
                    print(f"❌ Invalid! Enter 0 to {self.volume.shape[0]-1}")

            except ValueError:
                print("❌ Please enter a valid number")

        return self.selected_slice_idx

    def _preview_slices(self):
        """Show preview of different slices"""
        num_slices = self.volume.shape[0]

        # Show slices at different positions
        positions = [0, num_slices//4, num_slices//2, 3*num_slices//4, num_slices-1]

        fig, axes = plt.subplots(1, len(positions), figsize=(15, 4))

        for idx, (pos, ax) in enumerate(zip(positions, axes)):
            slice_img = self.volume[pos]
            ax.imshow(slice_img, cmap='gray')
            ax.set_title(f'Slice {pos}\n({pos/num_slices*100:.0f}%)')
            ax.axis('off')

            # Highlight if this is a good dental slice
            if pos == num_slices//2:
                ax.text(0.5, -0.1, '← Good for dental arch',
                       transform=ax.transAxes, ha='center', color='red')

        plt.suptitle(f"Slice Preview (Total: {num_slices} slices)")
        plt.tight_layout()
        plt.show()

        print("\n💡 TIP: For dental panoramic, usually select middle slice")

    def _show_selected_slice(self):
        """Display the selected slice"""
        if self.selected_slice_idx is None:
            return

        selected_slice = self.volume[self.selected_slice_idx]

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.imshow(selected_slice, cmap='gray')
        ax.set_title(f'Selected Slice: {self.selected_slice_idx}')
        ax.set_xlabel('X (Columns)')
        ax.set_ylabel('Y (Rows)')
        ax.grid(True, alpha=0.3)

        # Add intensity info
        min_val = selected_slice.min()
        max_val = selected_slice.max()
        mean_val = selected_slice.mean()
        ax.text(0.02, 0.98, f'Min: {min_val:.0f}\nMax: {max_val:.0f}\nMean: {mean_val:.0f}',
                transform=ax.transAxes, color='yellow',
                verticalalignment='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.5))

        plt.tight_layout()
        plt.show()

    def draw_curve_on_selected_slice(self):
        """
        Draw dental arch curve on selected slice
        """
        if self.selected_slice_idx is None:
            print("⚠️ No slice selected. Selecting middle slice...")
            self.select_slice_interactive()

        print("\n🎨 DRAW DENTAL ARCH CURVE")
        print("="*50)
        print("INSTRUCTIONS:")
        print("1. Click points along the DENTAL ARCH")
        print("2. Start from RIGHT side → move to LEFT side")
        print("3. Follow the curve of teeth/jawbone")
        print("4. Press ENTER when done")
        print("5. Right-click to remove last point")
        print("="*50)

        # Get selected slice
        axial_slice = self.volume[self.selected_slice_idx]

        # Show slice for drawing
        fig, ax = plt.subplots(figsize=(12, 12))
        ax.imshow(axial_slice, cmap='gray')
        ax.set_title(f'Slice {self.selected_slice_idx}: Draw Dental Arch Curve\n(Right → Left)')
        ax.set_xlabel('X (Columns)')
        ax.set_ylabel('Y (Rows)')
        ax.grid(True, alpha=0.3)
        ax.axis('on')

        # Get user clicks
        print("\n🖱️  Start clicking points now...")
        points = plt.ginput(n=-1, timeout=0, show_clicks=True, mouse_pop=2, mouse_stop=3)
        plt.close()

        if len(points) < 3:
            print("❌ Need at least 3 points! Using default curve.")
            points = self._create_default_curve(axial_slice.shape)

        # Convert to (y, x) format for internal use
        self.curve_points = [(int(p[1]), int(p[0])) for p in points]

        print(f"✅ Drawn {len(points)} points on slice {self.selected_slice_idx}")

        # Show the drawn curve
        self._show_drawn_curve(axial_slice, np.array(points))

        return self.curve_points

    def _create_default_curve(self, slice_shape):
        """Create default dental arch curve"""
        rows, cols = slice_shape

        # Default dental arch shape
        center_y = rows // 2
        center_x = cols // 2
        radius = min(rows, cols) // 3

        # Generate arc points
        angles = np.linspace(np.pi, 2*np.pi, 30)  # 180 to 360 degrees

        points = []
        for angle in angles:
            x = center_x + radius * np.cos(angle)
            y = center_y + radius * np.sin(angle)
            points.append((x, y))

        print("⚠️ Using default dental arch curve")
        return points

    def _show_drawn_curve(self, axial_slice, points_array):
        """Display the drawn curve"""
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(axial_slice, cmap='gray')

        # Plot curve
        ax.plot(points_array[:, 0], points_array[:, 1], 'r-', linewidth=3, label='Dental Arch')
        ax.scatter(points_array[:, 0], points_array[:, 1], c='yellow', s=50,
                  edgecolors='red', zorder=5)

        # Add direction arrows
        if len(points_array) > 1:
            step = max(1, len(points_array) // 5)
            for i in range(0, len(points_array)-1, step):
                dx = points_array[i+1, 0] - points_array[i, 0]
                dy = points_array[i+1, 1] - points_array[i, 1]
                ax.arrow(points_array[i, 0], points_array[i, 1], dx*0.7, dy*0.7,
                        head_width=8, head_length=8, fc='cyan', ec='cyan', alpha=0.8)

        ax.set_title(f'Dental Arch Curve (Slice {self.selected_slice_idx})')
        ax.set_xlabel('X (Columns)')
        ax.set_ylabel('Y (Rows)')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.2)

        plt.tight_layout()
        plt.show()

    def select_slice_range_for_panoramic(self):
        """
        Select which slices to include in panoramic view
        """
        if self.volume is None:
            self.load_all_slices()

        print("\n📏 SELECT SLICE RANGE FOR PANORAMIC")
        print("="*50)
        print(f"Total slices: {self.volume.shape[0]}")

        # Show slice positions with dental arch
        self._show_dental_arch_range()

        # Get user input for range
        while True:
            try:
                print("\n" + "-"*50)
                print("💡 Dental panoramic usually uses 30-70% of slices")
                start_percent = float(input("Start percentage (e.g., 30): ")) / 100
                end_percent = float(input("End percentage (e.g., 70): ")) / 100

                if 0 <= start_percent < end_percent <= 1:
                    start_slice = int(self.volume.shape[0] * start_percent)
                    end_slice = int(self.volume.shape[0] * end_percent)

                    print(f"✅ Selected slices: {start_slice} to {end_slice}")
                    print(f"   ({end_slice - start_slice} slices total)")

                    # Preview the range
                    self._preview_selected_range(start_slice, end_slice)

                    confirm = input("Use this range? (y/n): ").lower()
                    if confirm == 'y':
                        return start_slice, end_slice
                else:
                    print("❌ Invalid range! Start must be less than end.")

            except ValueError:
                print("❌ Please enter valid numbers")

    def _show_dental_arch_range(self):
        """Show where dental arch is typically located"""
        num_slices = self.volume.shape[0]

        # Show coronal view to help select range
        coronal_slice = self.volume[:, self.volume.shape[1]//2, :]

        fig, ax = plt.subplots(figsize=(12, 6))
        im = ax.imshow(coronal_slice, cmap='gray', aspect='auto')
        ax.set_title('Coronal View (for selecting slice range)')
        ax.set_xlabel('X (Columns)')
        ax.set_ylabel('Slice Number')

        # Mark typical dental arch range
        typical_start = int(num_slices * 0.3)
        typical_end = int(num_slices * 0.7)

        ax.axhline(y=typical_start, color='yellow', linestyle='--',
                  label=f'Typical start (30%) - Slice {typical_start}')
        ax.axhline(y=typical_end, color='cyan', linestyle='--',
                  label=f'Typical end (70%) - Slice {typical_end}')

        ax.legend()
        plt.colorbar(im, ax=ax, label='Intensity')
        plt.tight_layout()
        plt.show()

        print(f"\n💡 TIP: Dental arch is usually between slices {typical_start}-{typical_end}")

    def _preview_selected_range(self, start_slice, end_slice):
        """Preview selected slice range"""
        # Show slices at start, middle, and end of range
        positions = [start_slice, (start_slice + end_slice)//2, end_slice-1]

        fig, axes = plt.subplots(1, 3, figsize=(12, 4))

        for idx, (pos, ax) in enumerate(zip(positions, axes)):
            slice_img = self.volume[pos]
            ax.imshow(slice_img, cmap='gray')
            ax.set_title(f'Slice {pos}\n({pos/self.volume.shape[0]*100:.0f}%)')
            ax.axis('off')

        plt.suptitle(f"Selected Range: Slices {start_slice} to {end_slice}")
        plt.tight_layout()
        plt.show()

    def generate_panoramic_view(self, start_slice=None, end_slice=None, slab_thickness=5):
        """
        Generate panoramic view from drawn curve

        Args:
            start_slice: First slice to include
            end_slice: Last slice to include
            slab_thickness: Thickness perpendicular to curve

        Returns:
            Panoramic image
        """
        if self.curve_points is None:
            print("⚠️ No curve drawn! Drawing curve first...")
            self.draw_curve_on_selected_slice()

        if start_slice is None or end_slice is None:
            print("⚠️ No slice range selected. Selecting range...")
            start_slice, end_slice = self.select_slice_range_for_panoramic()

        print(f"\n🔄 GENERATING PANORAMIC VIEW")
        print("="*50)
        print(f"Curve drawn on slice: {self.selected_slice_idx}")
        print(f"Using slices: {start_slice} to {end_slice}")
        print(f"Slab thickness: {slab_thickness} pixels")
        print("="*50)

        # Generate panoramic
        self.panoramic_image = self._create_panoramic(
            start_slice, end_slice, slab_thickness
        )

        print(f"✅ Panoramic created: {self.panoramic_image.shape}")
        return self.panoramic_image

    def _create_panoramic(self, start_slice, end_slice, slab_thickness):
        """Create panoramic view along curve"""
        # Convert curve points
        curve_array = np.array(self.curve_points)  # (y, x)

        # Calculate curve length
        distances = np.zeros(len(curve_array))
        for i in range(1, len(curve_array)):
            dist = np.linalg.norm(curve_array[i] - curve_array[i-1])
            distances[i] = distances[i-1] + dist

        if distances[-1] == 0:
            distances[-1] = 1

        # Normalize
        distances = distances / distances[-1]

        # Create interpolation
        fx = interp1d(distances, curve_array[:, 1], kind='cubic', fill_value='extrapolate')
        fy = interp1d(distances, curve_array[:, 0], kind='cubic', fill_value='extrapolate')

        # Output dimensions
        output_width = int(distances[-1] * 150)  # Good resolution
        output_height = end_slice - start_slice

        panoramic = np.zeros((output_height, output_width), dtype=np.float32)

        print("⏳ Processing...", end='')

        # For each position along curve
        for u in range(output_width):
            t = u / output_width

            try:
                # Get curve point
                curve_x = int(fx(t))
                curve_y = int(fy(t))

                # Get normal at this point
                normal = self._calculate_normal(t, distances, curve_array)

                # For each slice
                for v in range(output_height):
                    slice_idx = start_slice + v

                    # Sample along normal
                    values = []
                    for d in range(-slab_thickness//2, slab_thickness//2 + 1):
                        x = curve_x + int(normal[0] * d)
                        y = curve_y + int(normal[1] * d)

                        if (0 <= slice_idx < self.volume.shape[0] and
                            0 <= y < self.volume.shape[1] and
                            0 <= x < self.volume.shape[2]):
                            values.append(self.volume[slice_idx, y, x])

                    if values:
                        panoramic[v, u] = np.max(values)  # MIP
            except:
                continue

        print(" Done!")

        # Normalize
        if panoramic.max() > panoramic.min():
            panoramic = (panoramic - panoramic.min()) / (panoramic.max() - panoramic.min())

        return panoramic

    def _calculate_normal(self, t, distances, curve_array):
        """Calculate normal vector at point on curve"""
        idx = np.searchsorted(distances, t)

        if idx < 1:
            idx = 1
        if idx >= len(curve_array):
            idx = len(curve_array) - 1

        # Tangent from adjacent points
        if idx < len(curve_array) - 1:
            p1 = curve_array[idx-1]
            p2 = curve_array[idx+1]
        else:
            p1 = curve_array[idx-2]
            p2 = curve_array[idx]

        # Tangent (dx, dy)
        tangent = np.array([p2[1] - p1[1], p2[0] - p1[0]])

        if np.linalg.norm(tangent) > 0:
            tangent = tangent / np.linalg.norm(tangent)
            # Rotate 90° clockwise for normal
            normal = np.array([tangent[1], -tangent[0]])
        else:
            normal = np.array([0, 1])

        return normal

    def display_final_results(self):
        """Display all results"""
        if self.panoramic_image is None:
            print("⚠️ Generate panoramic first!")
            return

        print("\n📊 FINAL RESULTS")
        print("="*50)

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Selected slice with curve
        selected_slice = self.volume[self.selected_slice_idx]
        axes[0, 0].imshow(selected_slice, cmap='gray')
        if self.curve_points:
            curve_array = np.array(self.curve_points)
            axes[0, 0].plot(curve_array[:, 1], curve_array[:, 0], 'r-', linewidth=2)
            axes[0, 0].scatter(curve_array[:, 1], curve_array[:, 0], c='yellow', s=30)
        axes[0, 0].set_title(f'Slice {self.selected_slice_idx} with Curve')
        axes[0, 0].set_xlabel('X')
        axes[0, 0].set_ylabel('Y')

        # 2. Panoramic view
        axes[0, 1].imshow(self.panoramic_image, cmap='gray', aspect='auto')
        axes[0, 1].set_title('Panoramic View')
        axes[0, 1].set_xlabel('Position along dental arch')
        axes[0, 1].set_ylabel('Slice number')

        # 3. Enhanced panoramic
        enhanced = self._enhance_panoramic()
        axes[1, 0].imshow(enhanced, cmap='gray', aspect='auto')
        axes[1, 0].set_title('Enhanced Panoramic')
        axes[1, 0].set_xlabel('Position along dental arch')
        axes[1, 0].set_ylabel('Slice number')

        # 4. Color-coded panoramic
        axes[1, 1].imshow(enhanced, cmap='hot')
        axes[1, 1].set_title('Color-coded Panoramic')
        axes[1, 1].set_xlabel('Position along dental arch')
        axes[1, 1].set_ylabel('Slice number')

        plt.tight_layout()
        plt.show()

        # Save results
        self._save_all_results()

    def _enhance_panoramic(self):
        """Enhance panoramic image contrast"""
        if self.panoramic_image.max() > self.panoramic_image.min():
            normalized = (self.panoramic_image - self.panoramic_image.min()) / \
                        (self.panoramic_image.max() - self.panoramic_image.min())
        else:
            normalized = self.panoramic_image

        # Gamma correction
        gamma = 0.6
        enhanced = np.power(normalized, gamma)

        return enhanced

    def _save_all_results(self):
        """Save all results to files"""
        output_dir = Path("dental_panoramic_results")
        output_dir.mkdir(exist_ok=True)

        # Save panoramic
        plt.imsave(output_dir / "panoramic.png", self.panoramic_image, cmap='gray')

        # Save enhanced
        enhanced = self._enhance_panoramic()
        plt.imsave(output_dir / "panoramic_enhanced.png", enhanced, cmap='gray')

        # Save numpy data
        np.save(output_dir / "panoramic_data.npy", self.panoramic_image)

        # Save curve points
        if self.curve_points:
            np.save(output_dir / "curve_points.npy", np.array(self.curve_points))

        # Save slice info
        with open(output_dir / "info.txt", 'w') as f:
            f.write(f"Dental Panoramic Generation Results\n")
            f.write(f"===================================\n\n")
            f.write(f"Selected slice: {self.selected_slice_idx}\n")
            f.write(f"Total slices: {self.volume.shape[0]}\n")
            f.write(f"Curve points: {len(self.curve_points) if self.curve_points else 0}\n")
            f.write(f"Panoramic shape: {self.panoramic_image.shape}\n")

        print(f"\n💾 All results saved to: {output_dir}")
        print(f"   - panoramic.png")
        print(f"   - panoramic_enhanced.png")
        print(f"   - panoramic_data.npy")
        print(f"   - curve_points.npy")
        print(f"   - info.txt")

    def run_complete_workflow(self):
        """Complete workflow: Select → Draw → Generate → Save"""
        print("="*60)
        print("DENTAL PANORAMIC WORKFLOW")
        print("="*60)

        # Step 1: Load slices
        print("\n1️⃣  LOADING SLICES...")
        self.load_all_slices()

        # Step 2: Select slice
        print("\n2️⃣  SELECTING SLICE...")
        self.select_slice_interactive()

        # Step 3: Draw curve
        print("\n3️⃣  DRAWING CURVE...")
        self.draw_curve_on_selected_slice()

        # Step 4: Select slice range
        print("\n4️⃣  SELECTING SLICE RANGE...")
        start_slice, end_slice = self.select_slice_range_for_panoramic()

        # Step 5: Generate panoramic
        print("\n5️⃣  GENERATING PANORAMIC...")
        self.generate_panoramic_view(start_slice, end_slice)

        # Step 6: Show results
        print("\n6️⃣  DISPLAYING RESULTS...")
        self.display_final_results()

        print("\n" + "="*60)
        print("✅ PANORAMIC CREATION COMPLETE!")
        print("="*60)


# ============================================================================
# MAIN FUNCTION - SINGLE SOLUTION
# ============================================================================

def main():
    """
    MAIN: Single solution for dental panoramic creation
    """
    print("🦷 DENTAL CBCT PANORAMIC CREATOR")
    print("="*60)
    print("Workflow: Select Slice → Draw Curve → Generate Panoramic")
    print("="*60)

    # ========== SET YOUR SLICES DIRECTORY HERE ==========
    YOUR_SLICES_DIR = "D:/Dental CBCT/Dental Data"  # ⬅️ CHANGE THIS

    # Or use command line argument
    import sys
    if len(sys.argv) > 1:
        YOUR_SLICES_DIR = sys.argv[1]

    print(f"📁 Slices directory: {YOUR_SLICES_DIR}")
    print("="*60)

    # Check if directory exists
    if not Path(YOUR_SLICES_DIR).exists():
        print(f"❌ ERROR: Directory not found!")
        print(f"Please check: {YOUR_SLICES_DIR}")
        print("\n💡 Make sure you have extracted slices first")
        return

    # Create panoramic creator
    creator = DentalPanoramicCreator(YOUR_SLICES_DIR)

    # Run complete workflow
    creator.run_complete_workflow()


# ============================================================================
# QUICK START EXAMPLE
# ============================================================================

def quick_example():
    """Quick example showing how to use"""
    # 1. Create instance with your slices
    creator = DentalPanoramicCreator("your_slices_folder")

    # 2. Load slices
    creator.load_all_slices()

    # 3. Select which slice to draw on
    creator.select_slice_interactive()

    # 4. Draw curve on selected slice
    creator.draw_curve_on_selected_slice()

    # 5. Select slice range for panoramic
    start, end = creator.select_slice_range_for_panoramic()

    # 6. Generate panoramic
    creator.generate_panoramic_view(start, end)

    # 7. View results
    creator.display_final_results()


# ============================================================================
# RUN THE SCRIPT
# ============================================================================

if __name__ == "__main__":
    main()