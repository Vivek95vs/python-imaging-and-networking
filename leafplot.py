# import pydicom
# import numpy as np
# import pandas as pd
# import matplotlib.pyplot as plt
# import os
#
# # --------------------------------------------------
# # USER SETTINGS
# # --------------------------------------------------
# DICOM_PATH = r"D:/dose/TG244_3Dcrt/Export_002442/RTDOSE_BeamDose_Beam 1.1.2.276.0.7230010.3.1.4.3706580561.8300.1766721854.565.dcm"
# OUTPUT_FOLDER = "D:/dose/TG244_3Dcrt/BankABsplit"
#
# LEAF_WIDTH_MM = 10.0
# NUM_LEAVES = 60
# LEAVES_PER_BANK = NUM_LEAVES // 2
# PLOT_FRAME_INDEX = 0
# # --------------------------------------------------
#
# os.makedirs(OUTPUT_FOLDER, exist_ok=True)
#
# # --------------------------------------------------
# # 1. LOAD RTDOSE
# # --------------------------------------------------
# ds = pydicom.dcmread(DICOM_PATH)
#
# dose_scaling = float(ds.get("DoseGridScaling", 1.0))
# dose_array = ds.pixel_array.astype(np.float32) * dose_scaling * 100.0  # cGy
#
# num_frames, height, width = dose_array.shape
# pixel_spacing = ds.PixelSpacing
# pixel_size_y = float(pixel_spacing[0])
#
# print("Dose shape [Z,Y,X]:", dose_array.shape)
#
# # --------------------------------------------------
# # 2. ARRAYS FOR BANK A & BANK B
# # --------------------------------------------------
# bankA = np.zeros((num_frames, LEAVES_PER_BANK), dtype=np.float64)
# bankB = np.zeros((num_frames, LEAVES_PER_BANK), dtype=np.float64)
#
# # --------------------------------------------------
# # 3. LEAF-WISE BINNING PER FRAME
# # --------------------------------------------------
# for z in range(num_frames):
#     frame = dose_array[z, :, :]  # [Y, X]
#
#     for y in range(height):
#         y_mm = y * pixel_size_y
#         leaf_index = int(y_mm // LEAF_WIDTH_MM)
#
#         if 0 <= leaf_index < NUM_LEAVES:
#             row_sum = np.sum(frame[y, :])
#
#             if leaf_index < LEAVES_PER_BANK:
#                 bankA[z, leaf_index] += row_sum
#             else:
#                 bankB[z, leaf_index - LEAVES_PER_BANK] += row_sum
#
# # --------------------------------------------------
# # 4. NORMALIZATION
# # --------------------------------------------------
# max_val = max(np.max(bankA), np.max(bankB))
# if max_val > 0:
#     bankA /= max_val
#     bankB /= max_val
#
# # --------------------------------------------------
# # 5. SAVE COMBINED CSV
# # --------------------------------------------------
# combined_df = pd.DataFrame({
#     "Frame_Index": np.arange(num_frames)
# })
#
# for i in range(LEAVES_PER_BANK):
#     combined_df[f"BankA_Leaf_{i}"] = bankA[:, i]
#     combined_df[f"BankB_Leaf_{i}"] = bankB[:, i]
#
# combined_csv = os.path.join(OUTPUT_FOLDER, "leaf_bank_A_B_all_frames.csv")
# combined_df.to_csv(combined_csv, index=False)
#
# print("Combined A/B CSV saved:", combined_csv)
#
# # --------------------------------------------------
# # 6. SAVE PER-FRAME CSVs
# # --------------------------------------------------
# for z in range(num_frames):
#     df = pd.DataFrame({
#         "Leaf_Index": np.arange(LEAVES_PER_BANK),
#         "BankA_Intensity": bankA[z],
#         "BankB_Intensity": bankB[z]
#     })
#
#     df.to_csv(
#         os.path.join(OUTPUT_FOLDER, f"leaf_bank_frame_{z:03d}.csv"),
#         index=False
#     )
#
# print("Per-frame A/B CSV files saved.")
#
# # --------------------------------------------------
# # 7. PLOT ONE FRAME (BANK A vs BANK B)
# # --------------------------------------------------
# plt.figure(figsize=(12, 4))
# plt.plot(bankA[PLOT_FRAME_INDEX], label="Bank A", marker='o')
# plt.plot(bankB[PLOT_FRAME_INDEX], label="Bank B", marker='s')
#
# plt.xlabel("Leaf Index (per bank)")
# plt.ylabel("Relative Intensity")
# plt.title(f"Leaf Bank A / B – Frame {PLOT_FRAME_INDEX}")
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
#
# plot_path = os.path.join(
#     OUTPUT_FOLDER, f"leaf_bank_frame_{PLOT_FRAME_INDEX:03d}.png"
# )
# plt.savefig(plot_path, dpi=150)
# plt.show()
#
# print("Plot saved:", plot_path)
#
# # --------------------------------------------------
# # 8. SUMMARY
# # --------------------------------------------------
# summary = {
#     "Frames": [num_frames],
#     "Leaf width (mm)": [LEAF_WIDTH_MM],
#     "Leaves per bank": [LEAVES_PER_BANK],
#     "Pixel spacing Y (mm)": [pixel_size_y],
#     "Max dose (cGy)": [np.max(dose_array)]
# }
#
# pd.DataFrame(summary).to_csv(
#     os.path.join(OUTPUT_FOLDER, "summary.csv"),
#     index=False
# )
#
# print("DONE.")
# ===============================================================================================================================================================================================

# import pydicom
# import numpy as np
# import matplotlib.pyplot as plt
# from scipy import ndimage, signal
# import pandas as pd
# from matplotlib.patches import Rectangle
# import seaborn as sns
# from skimage import measure, filters
#
# # Set style for better visualizations
# plt.style.use('seaborn-v0_8-darkgrid')
# sns.set_palette("husl")
#
#
# class RTDoseMLCAnalyzer:
#     def __init__(self, rtdose_path, leaf_width_mm=10, slice_thickness_mm=2.5, num_leaves=60):
#         """
#         Initialize analyzer with RT Dose file and MLC parameters
#
#         Parameters:
#         -----------
#         rtdose_path : str
#             Path to RT Dose DICOM file
#         leaf_width_mm : float
#             Width of each MLC leaf in mm (default: 10mm)
#         slice_thickness_mm : float
#             Slice thickness in mm (default: 2.5mm)
#         num_leaves : int
#             Total number of MLC leaves (default: 60)
#         """
#         self.rtdose_path = rtdose_path
#         self.leaf_width_mm = leaf_width_mm
#         self.slice_thickness_mm = slice_thickness_mm
#         self.num_leaves = num_leaves
#         self.num_leaf_pairs = num_leaves // 2
#
#         # Load DICOM data
#         self.load_dicom_data()
#
#     def load_dicom_data(self):
#         """Load and parse RT Dose DICOM file"""
#         print(f"Loading RT Dose file: {self.rtdose_path}")
#         self.dose = pydicom.dcmread(self.rtdose_path)
#
#         # Extract dose grid
#         self.dose_grid = self.dose.pixel_array * self.dose.DoseGridScaling
#
#         # Get spatial information
#         if hasattr(self.dose, 'PixelSpacing'):
#             self.pixel_spacing = self.dose.PixelSpacing  # [row, column] in mm
#         else:
#             self.pixel_spacing = [1.0, 1.0]
#             print("Warning: No PixelSpacing found, assuming 1.0 mm")
#
#         if hasattr(self.dose, 'GridFrameOffsetVector'):
#             self.z_positions = self.dose.GridFrameOffsetVector
#         else:
#             self.z_positions = np.arange(self.dose_grid.shape[0]) * self.slice_thickness_mm
#
#         print(f"Dose grid shape: {self.dose_grid.shape}")
#         print(f"Pixel spacing: {self.pixel_spacing} mm")
#         print(f"Dose range: {self.dose_grid.min():.2f} - {self.dose_grid.max():.2f}")
#         print(f"Number of slices: {len(self.z_positions)}")
#
#     def detect_field_boundaries(self, dose_threshold=0.5):
#         """
#         Detect radiation field boundaries in each slice
#
#         Parameters:
#         -----------
#         dose_threshold : float
#             Threshold relative to maximum dose (0.0-1.0)
#         """
#         print("\nDetecting field boundaries...")
#
#         field_data = []
#
#         for slice_idx in range(self.dose_grid.shape[0]):
#             dose_slice = self.dose_grid[slice_idx]
#
#             # Skip slices with very low dose
#             if dose_slice.max() < dose_threshold * self.dose_grid.max():
#                 continue
#
#             # Create binary mask for this slice
#             binary_slice = dose_slice > (dose_threshold * dose_slice.max())
#
#             if np.any(binary_slice):
#                 # Find bounding box of high-dose region
#                 rows = np.any(binary_slice, axis=1)
#                 cols = np.any(binary_slice, axis=0)
#
#                 y_min, y_max = np.where(rows)[0][[0, -1]]
#                 x_min, x_max = np.where(cols)[0][[0, -1]]
#
#                 # Convert to mm
#                 y_min_mm = y_min * self.pixel_spacing[0]
#                 y_max_mm = y_max * self.pixel_spacing[0]
#                 x_min_mm = x_min * self.pixel_spacing[1]
#                 x_max_mm = x_max * self.pixel_spacing[1]
#
#                 field_width_mm = x_max_mm - x_min_mm
#                 field_height_mm = y_max_mm - y_min_mm
#
#                 field_data.append({
#                     'slice_index': slice_idx,
#                     'z_position_mm': self.z_positions[slice_idx] if slice_idx < len(
#                         self.z_positions) else slice_idx * self.slice_thickness_mm,
#                     'x_min_px': x_min,
#                     'x_max_px': x_max,
#                     'y_min_px': y_min,
#                     'y_max_px': y_max,
#                     'x_min_mm': x_min_mm,
#                     'x_max_mm': x_max_mm,
#                     'y_min_mm': y_min_mm,
#                     'y_max_mm': y_max_mm,
#                     'field_width_mm': field_width_mm,
#                     'field_height_mm': field_height_mm,
#                     'dose_slice': dose_slice,
#                     'binary_slice': binary_slice
#                 })
#
#         print(f"Detected fields in {len(field_data)} slices")
#         self.field_data = field_data
#         return field_data
#
#     def analyze_leaf_patterns(self, slice_index=None):
#         """
#         Analyze dose profiles to infer leaf positions
#
#         Parameters:
#         -----------
#         slice_index : int, optional
#             Specific slice to analyze (default: middle slice)
#         """
#         if slice_index is None:
#             slice_index = self.dose_grid.shape[0] // 2
#
#         print(f"\nAnalyzing leaf patterns in slice {slice_index}...")
#
#         dose_slice = self.dose_grid[slice_index]
#
#         # Get multiple profiles at different Y positions - FIXED
#         y_positions = [0.3, 0.5, 0.7]  # 30%, 50%, 70% of field height
#         y_indices = [int(y * dose_slice.shape[0]) for y in y_positions]  # FIXED: Convert to int directly
#
#         leaf_analyses = []
#
#         for y_pos, y_idx in zip(y_positions, y_indices):
#             # Ensure y_idx is within bounds
#             y_idx = min(max(y_idx, 0), dose_slice.shape[0] - 1)
#
#             # Extract X profile
#             x_profile = dose_slice[y_idx, :]
#
#             # Smooth profile to reduce noise
#             x_profile_smooth = filters.gaussian(x_profile, sigma=2.0)
#
#             # Calculate gradient
#             gradient = np.gradient(x_profile_smooth)
#
#             # Find gradient peaks (leaf edges)
#             peaks_positive, _ = signal.find_peaks(gradient,
#                                                   height=np.max(gradient) * 0.1,
#                                                   distance=self.leaf_width_mm / self.pixel_spacing[1] * 0.8)
#             peaks_negative, _ = signal.find_peaks(-gradient,
#                                                   height=np.max(-gradient) * 0.1,
#                                                   distance=self.leaf_width_mm / self.pixel_spacing[1] * 0.8)
#
#             # Combine and sort all peaks
#             all_peaks = np.sort(np.concatenate([peaks_positive, peaks_negative]))
#
#             # Convert to mm
#             peaks_mm = all_peaks * self.pixel_spacing[1]
#
#             # Group peaks into leaf pairs
#             leaf_pairs = []
#             for i in range(0, len(peaks_mm) - 1):
#                 leaf_width = peaks_mm[i + 1] - peaks_mm[i]
#                 if 7 <= leaf_width <= 13:  # Allow ±3mm tolerance around 10mm
#                     leaf_pairs.append({
#                         'left_edge_px': all_peaks[i],
#                         'right_edge_px': all_peaks[i + 1],
#                         'left_edge_mm': peaks_mm[i],
#                         'right_edge_mm': peaks_mm[i + 1],
#                         'center_mm': (peaks_mm[i] + peaks_mm[i + 1]) / 2,
#                         'width_mm': leaf_width
#                     })
#
#             leaf_analyses.append({
#                 'y_position': y_pos,
#                 'y_index': y_idx,
#                 'profile': x_profile,
#                 'profile_smooth': x_profile_smooth,
#                 'gradient': gradient,
#                 'peaks_pixels': all_peaks,
#                 'peaks_mm': peaks_mm,
#                 'leaf_pairs': leaf_pairs,
#                 'num_detected_leaves': len(leaf_pairs)
#             })
#
#         self.leaf_analyses = leaf_analyses
#         return leaf_analyses
#
#     def reconstruct_3d_mlc_shape(self, dose_threshold=0.3):
#         """
#         Reconstruct 3D MLC shape from dose distribution
#         """
#         print("\nReconstructing 3D MLC shape...")
#
#         # Create 3D binary mask
#         binary_3d = self.dose_grid > (dose_threshold * self.dose_grid.max())
#
#         # Label connected components
#         labeled_3d, num_components = ndimage.label(binary_3d)
#
#         # Find the largest component (main field)
#         component_sizes = ndimage.sum(binary_3d, labeled_3d, range(num_components + 1))
#         if len(component_sizes) > 1:
#             largest_component = np.argmax(component_sizes[1:]) + 1
#             main_field = labeled_3d == largest_component
#         else:
#             main_field = binary_3d
#
#         # Create leaf occupancy matrix
#         leaf_occupancy = []
#
#         for z in range(main_field.shape[0]):
#             if np.any(main_field[z]):
#                 # Project to X-axis
#                 x_projection = np.max(main_field[z], axis=0)
#
#                 # Find field extent
#                 field_indices = np.where(x_projection > 0)[0]
#
#                 if len(field_indices) > 0:
#                     field_start_mm = field_indices[0] * self.pixel_spacing[1]
#                     field_end_mm = field_indices[-1] * self.pixel_spacing[1]
#
#                     # Determine which of the 60 leaves would be open
#                     leaf_open = np.zeros(self.num_leaves, dtype=bool)
#
#                     for leaf_idx in range(self.num_leaves):
#                         leaf_center = field_start_mm + leaf_idx * self.leaf_width_mm + self.leaf_width_mm / 2
#                         if field_start_mm <= leaf_center <= field_end_mm:
#                             leaf_open[leaf_idx] = True
#
#                     leaf_occupancy.append({
#                         'slice_z': z * self.slice_thickness_mm,
#                         'slice_index': z,
#                         'leaf_open': leaf_open,
#                         'field_start_mm': field_start_mm,
#                         'field_end_mm': field_end_mm,
#                         'field_width_mm': field_end_mm - field_start_mm
#                     })
#
#         self.leaf_occupancy = leaf_occupancy
#         self.main_field_3d = main_field
#
#         print(f"Reconstructed 3D field with {len(leaf_occupancy)} slices")
#         return leaf_occupancy, main_field
#
#     def generate_inferred_leaf_positions(self):
#         """
#         Generate inferred leaf positions based on analysis
#         """
#         print("\nGenerating inferred leaf positions...")
#
#         if not hasattr(self, 'field_data'):
#             self.detect_field_boundaries()
#
#         leaf_positions = []
#
#         for field in self.field_data:
#             # Generate expected leaf centers based on field width
#             field_width_mm = field['field_width_mm']
#
#             # Estimate number of leaves that fit in this field
#             estimated_leaves = int(field_width_mm / self.leaf_width_mm)
#             estimated_leaves = min(estimated_leaves, self.num_leaves)
#
#             # Calculate offset to center leaves in field
#             offset = (self.num_leaves - estimated_leaves) * self.leaf_width_mm / 2
#
#             for leaf_idx in range(self.num_leaves):
#                 # Calculate leaf position relative to field center
#                 leaf_center_x = field['x_min_mm'] + offset + leaf_idx * self.leaf_width_mm + self.leaf_width_mm / 2
#
#                 # Check if leaf is within field
#                 leaf_in_field = field['x_min_mm'] <= leaf_center_x <= field['x_max_mm']
#
#                 leaf_positions.append({
#                     'slice_z_mm': field['z_position_mm'],
#                     'slice_index': field['slice_index'],
#                     'leaf_index': leaf_idx,
#                     'leaf_pair': leaf_idx // 2,
#                     'leaf_side': 'A' if leaf_idx % 2 == 0 else 'B',
#                     'center_x_mm': leaf_center_x,
#                     'left_edge_mm': leaf_center_x - self.leaf_width_mm / 2,
#                     'right_edge_mm': leaf_center_x + self.leaf_width_mm / 2,
#                     'in_field': leaf_in_field,
#                     'field_width_mm': field_width_mm
#                 })
#
#         self.leaf_positions_df = pd.DataFrame(leaf_positions)
#         return self.leaf_positions_df
#
#     def visualize_complete_analysis(self, save_path='mlc_analysis_results.png'):
#         """
#         Create comprehensive visualization of all analyses
#         """
#         print(f"\nCreating visualizations...")
#
#         fig = plt.figure(figsize=(20, 16))
#
#         # 1. 3D Dose Distribution - Isometric View
#         ax1 = plt.subplot(3, 4, 1, projection='3d')
#         self.plot_3d_dose_isometric(ax1)
#
#         # 2. Middle Slice Dose Distribution
#         ax2 = plt.subplot(3, 4, 2)
#         self.plot_middle_slice_dose(ax2)
#
#         # 3. Dose Profiles with Detected Edges
#         ax3 = plt.subplot(3, 4, 3)
#         self.plot_dose_profiles_with_edges(ax3)
#
#         # 4. Gradient Analysis
#         ax4 = plt.subplot(3, 4, 4)
#         self.plot_gradient_analysis(ax4)
#
#         # 5. Field Boundaries Across Slices
#         ax5 = plt.subplot(3, 4, 5)
#         self.plot_field_boundaries(ax5)
#
#         # 6. Leaf Occupancy Matrix
#         ax6 = plt.subplot(3, 4, 6)
#         self.plot_leaf_occupancy(ax6)
#
#         # 7. Inferred Leaf Positions
#         ax7 = plt.subplot(3, 4, 7)
#         self.plot_inferred_leaf_positions(ax7)
#
#         # 8. 3D Field Reconstruction
#         ax8 = plt.subplot(3, 4, 8)
#         self.plot_3d_field_reconstruction(ax8)
#
#         # 9. Statistics and Summary
#         ax9 = plt.subplot(3, 4, (9, 12))
#         self.plot_summary_statistics(ax9)
#
#         plt.suptitle(f'RT Dose MLC Analysis\nFile: {self.rtdose_path}',
#                      fontsize=16, fontweight='bold', y=1.02)
#         plt.tight_layout()
#
#         if save_path:
#             plt.savefig(save_path, dpi=150, bbox_inches='tight')
#             print(f"Visualization saved to {save_path}")
#
#         plt.show()
#
#         # Also create individual detailed plots
#         self.create_detailed_plots()
#
#     def plot_3d_dose_isometric(self, ax):
#         """Create 3D isometric view of dose distribution"""
#         # Reduce resolution for faster plotting
#         stride = max(1, self.dose_grid.shape[0] // 20)
#         X, Y, Z = np.meshgrid(
#             np.arange(0, self.dose_grid.shape[2], 5),
#             np.arange(0, self.dose_grid.shape[1], 5),
#             np.arange(0, self.dose_grid.shape[0], stride),
#             indexing='ij'
#         )
#
#         dose_sampled = self.dose_grid[::stride, ::5, ::5]
#
#         # Normalize for opacity
#         dose_norm = dose_sampled / dose_sampled.max()
#
#         scatter = ax.scatter(X.flatten(), Y.flatten(), Z.flatten(),
#                              c=dose_sampled.flatten(),
#                              cmap='hot', alpha=0.3, s=1)
#         ax.set_xlabel('X (pixels)')
#         ax.set_ylabel('Y (pixels)')
#         ax.set_zlabel('Slice')
#         ax.set_title('3D Dose Distribution')
#
#     def plot_middle_slice_dose(self, ax):
#         """Plot dose distribution in middle slice"""
#         mid_slice = self.dose_grid.shape[0] // 2
#         dose_slice = self.dose_grid[mid_slice]
#
#         im = ax.imshow(dose_slice, cmap='jet',
#                        extent=[0, dose_slice.shape[1] * self.pixel_spacing[1],
#                                0, dose_slice.shape[0] * self.pixel_spacing[0]])
#         ax.set_xlabel('X (mm)')
#         ax.set_ylabel('Y (mm)')
#         ax.set_title(f'Middle Slice (Z={mid_slice * self.slice_thickness_mm:.1f} mm)')
#
#         # Add isodose contours
#         if dose_slice.max() > 0:
#             levels = [0.2, 0.5, 0.8]
#             contours = ax.contour(dose_slice, levels=levels,
#                                   colors=['white', 'cyan', 'magenta'],
#                                   linewidths=1.5,
#                                   extent=[0, dose_slice.shape[1] * self.pixel_spacing[1],
#                                           0, dose_slice.shape[0] * self.pixel_spacing[0]])
#             ax.clabel(contours, inline=True, fontsize=8)
#
#         plt.colorbar(im, ax=ax, label='Dose')
#
#     def plot_dose_profiles_with_edges(self, ax):
#         """Plot dose profiles with detected leaf edges"""
#         if not hasattr(self, 'leaf_analyses'):
#             self.analyze_leaf_patterns()
#
#         colors = plt.cm.viridis(np.linspace(0, 1, len(self.leaf_analyses)))
#
#         for idx, analysis in enumerate(self.leaf_analyses):
#             x_mm = np.arange(len(analysis['profile'])) * self.pixel_spacing[1]
#
#             ax.plot(x_mm, analysis['profile_smooth'],
#                     color=colors[idx],
#                     label=f'Y={analysis["y_position"] * 100:.0f}%',
#                     linewidth=2, alpha=0.8)
#
#             # Mark detected edges
#             for peak_mm in analysis['peaks_mm']:
#                 ax.axvline(x=peak_mm, color=colors[idx],
#                            alpha=0.3, linestyle='--', linewidth=0.8)
#
#         ax.set_xlabel('X Position (mm)')
#         ax.set_ylabel('Dose (normalized)')
#         ax.set_title('Dose Profiles at Different Y Positions')
#         ax.legend()
#         ax.grid(True, alpha=0.3)
#
#     def plot_gradient_analysis(self, ax):
#         """Plot gradient analysis for leaf edge detection"""
#         if not hasattr(self, 'leaf_analyses'):
#             self.analyze_leaf_patterns()
#
#         analysis = self.leaf_analyses[1]  # Middle profile
#
#         x_mm = np.arange(len(analysis['profile'])) * self.pixel_spacing[1]
#
#         # Plot gradient
#         ax.plot(x_mm, analysis['gradient'], 'b-', label='Gradient', alpha=0.7)
#
#         # Mark detected peaks
#         ax.plot(x_mm[analysis['peaks_pixels']],
#                 analysis['gradient'][analysis['peaks_pixels']],
#                 'ro', label='Detected Edges', markersize=6)
#
#         # Add zero line
#         ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
#
#         ax.set_xlabel('X Position (mm)')
#         ax.set_ylabel('Gradient')
#         ax.set_title('Gradient Analysis for Leaf Edge Detection')
#         ax.legend()
#         ax.grid(True, alpha=0.3)
#
#     def plot_field_boundaries(self, ax):
#         """Plot field boundaries across slices"""
#         if not hasattr(self, 'field_data'):
#             self.detect_field_boundaries()
#
#         slices = [f['slice_index'] for f in self.field_data]
#         widths = [f['field_width_mm'] for f in self.field_data]
#         heights = [f['field_height_mm'] for f in self.field_data]
#         z_positions = [f['z_position_mm'] for f in self.field_data]
#
#         ax.plot(z_positions, widths, 'b-o', label='Field Width', linewidth=2, markersize=4)
#         ax.plot(z_positions, heights, 'r-s', label='Field Height', linewidth=2, markersize=4)
#
#         # Add expected leaf pattern
#         if widths:
#             avg_width = np.mean(widths)
#             ax.axhline(y=avg_width, color='b', alpha=0.3, linestyle='--',
#                        label=f'Avg Width: {avg_width:.1f} mm')
#
#             # Mark expected leaf count
#             expected_leaves = avg_width / self.leaf_width_mm
#             ax.text(0.05, 0.95, f'~{expected_leaves:.1f} leaves\n({self.leaf_width_mm}mm each)',
#                     transform=ax.transAxes, verticalalignment='top',
#                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
#
#         ax.set_xlabel('Z Position (mm)')
#         ax.set_ylabel('Field Dimension (mm)')
#         ax.set_title('Field Boundaries vs Depth')
#         ax.legend()
#         ax.grid(True, alpha=0.3)
#
#     def plot_leaf_occupancy(self, ax):
#         """Plot leaf occupancy matrix"""
#         if not hasattr(self, 'leaf_occupancy'):
#             self.reconstruct_3d_mlc_shape()
#
#         if self.leaf_occupancy:
#             occupancy_matrix = np.array([occ['leaf_open'] for occ in self.leaf_occupancy])
#             z_positions = [occ['slice_z'] for occ in self.leaf_occupancy]
#
#             im = ax.imshow(occupancy_matrix.T, cmap='Blues', aspect='auto',
#                            extent=[z_positions[0], z_positions[-1], 0, self.num_leaves])
#
#             ax.set_xlabel('Z Position (mm)')
#             ax.set_ylabel('Leaf Index')
#             ax.set_title('Leaf Occupancy vs Depth')
#
#             # Add grid for leaf pairs
#             for leaf_pair in range(0, self.num_leaves, 2):
#                 ax.axhline(y=leaf_pair + 0.5, color='gray', alpha=0.2, linewidth=0.5)
#
#             plt.colorbar(im, ax=ax, label='Leaf Open')
#
#     def plot_inferred_leaf_positions(self, ax):
#         """Plot inferred leaf positions"""
#         if not hasattr(self, 'leaf_positions_df'):
#             self.generate_inferred_leaf_positions()
#
#         # Get middle slice data
#         mid_slice_idx = self.dose_grid.shape[0] // 2
#         mid_slice_data = self.leaf_positions_df[
#             self.leaf_positions_df['slice_index'] == mid_slice_idx
#             ]
#
#         # Create visualization
#         for _, leaf in mid_slice_data.iterrows():
#             color = 'green' if leaf['in_field'] else 'red'
#             alpha = 0.7 if leaf['in_field'] else 0.2
#
#             # Draw leaf as rectangle
#             rect = Rectangle(
#                 (leaf['left_edge_mm'], -0.5),
#                 self.leaf_width_mm, 1,
#                 facecolor=color, alpha=alpha,
#                 edgecolor='black', linewidth=0.5
#             )
#             ax.add_patch(rect)
#
#             # Add leaf number for every 5th leaf
#             if leaf['leaf_index'] % 5 == 0:
#                 ax.text(leaf['center_x_mm'], 0, str(leaf['leaf_index']),
#                         ha='center', va='center', fontsize=6)
#
#         ax.set_xlabel('X Position (mm)')
#         ax.set_ylabel('')
#         ax.set_yticks([])
#         ax.set_title(f'Inferred Leaf Positions (Slice {mid_slice_idx})')
#         ax.set_xlim(mid_slice_data['left_edge_mm'].min() - 5,
#                     mid_slice_data['right_edge_mm'].max() + 5)
#         ax.set_ylim(-2, 2)
#
#         # Add legend
#         from matplotlib.patches import Patch
#         legend_elements = [
#             Patch(facecolor='green', alpha=0.7, label='In Field'),
#             Patch(facecolor='red', alpha=0.2, label='Out of Field')
#         ]
#         ax.legend(handles=legend_elements, loc='upper right')
#
#     def plot_3d_field_reconstruction(self, ax):
#         """Plot 3D field reconstruction"""
#         if not hasattr(self, 'main_field_3d'):
#             self.reconstruct_3d_mlc_shape()
#
#         # Create projection
#         if hasattr(self, 'main_field_3d'):
#             projection = np.max(self.main_field_3d, axis=0)
#
#             im = ax.imshow(projection, cmap='Greens', aspect='auto',
#                            extent=[0, projection.shape[1] * self.pixel_spacing[1],
#                                    0, projection.shape[0] * self.pixel_spacing[0]])
#
#             ax.set_xlabel('X (mm)')
#             ax.set_ylabel('Y (mm)')
#             ax.set_title('3D Field Reconstruction (Max Projection)')
#
#             # Add contour at 50% level
#             if projection.max() > 0:
#                 ax.contour(projection, levels=[0.5], colors=['red'],
#                            linewidths=1.5,
#                            extent=[0, projection.shape[1] * self.pixel_spacing[1],
#                                    0, projection.shape[0] * self.pixel_spacing[0]])
#
#     def plot_summary_statistics(self, ax):
#         """Plot summary statistics and information"""
#         ax.axis('off')
#
#         # Calculate statistics
#         max_dose = self.dose_grid.max()
#         mean_dose = self.dose_grid.mean()
#         total_volume = np.prod(self.dose_grid.shape)
#         high_dose_volume = np.sum(self.dose_grid > 0.5 * max_dose)
#
#         if hasattr(self, 'field_data') and self.field_data:
#             avg_field_width = np.mean([f['field_width_mm'] for f in self.field_data])
#             avg_field_height = np.mean([f['field_height_mm'] for f in self.field_data])
#             inferred_leaves = avg_field_width / self.leaf_width_mm
#         else:
#             avg_field_width = avg_field_height = inferred_leaves = 0
#
#         if hasattr(self, 'leaf_analyses') and self.leaf_analyses:
#             detected_edges = len(self.leaf_analyses[0]['leaf_pairs'])
#         else:
#             detected_edges = 0
#
#         # Create summary text
#         summary_text = f"""
#         RT DOSE FILE ANALYSIS SUMMARY
#         {'=' * 40}
#
#         FILE INFORMATION:
#         • File: {self.rtdose_path}
#         • Grid Size: {self.dose_grid.shape[2]} × {self.dose_grid.shape[1]} × {self.dose_grid.shape[0]}
#         • Pixel Spacing: {self.pixel_spacing[0]} × {self.pixel_spacing[1]} mm
#         • Slice Thickness: {self.slice_thickness_mm} mm
#         • Total Slices: {len(self.z_positions)}
#
#         DOSE STATISTICS:
#         • Maximum Dose: {max_dose:.2f}
#         • Mean Dose: {mean_dose:.2f}
#         • Total Voxels: {total_volume:,}
#         • High-Dose Volume (>50% max): {high_dose_volume:,} voxels
#
#         INFERRED MLC PARAMETERS:
#         • Leaf Width: {self.leaf_width_mm} mm
#         • Number of Leaves: {self.num_leaves}
#         • Leaf Pairs: {self.num_leaf_pairs}
#
#         FIELD ANALYSIS:
#         • Average Field Width: {avg_field_width:.1f} mm
#         • Average Field Height: {avg_field_height:.1f} mm
#         • Inferred Leaves in Field: {inferred_leaves:.1f}
#         • Detected Leaf Edges: {detected_edges}
#
#         ANALYSIS NOTES:
#         • These are INFERRED positions from dose distribution
#         • Actual MLC positions require RT Plan file
#         • Accuracy depends on dose gradient sharpness
#         • Referenced Plan UID: {getattr(self.dose, 'ReferencedRTPlanSequence', ['Not found'])[0].ReferencedSOPInstanceUID if hasattr(self.dose, 'ReferencedRTPlanSequence') else 'Not found'}
#
#         RECOMMENDATIONS:
#         1. Obtain RT Plan file for exact MLC data
#         2. Verify with treatment planning system
#         3. Use inferred positions for qualitative analysis only
#         """
#
#         ax.text(0.02, 0.98, summary_text, transform=ax.transAxes,
#                 fontsize=9, verticalalignment='top',
#                 fontfamily='monospace',
#                 bbox=dict(boxstyle='round', facecolor='lightblue',
#                           alpha=0.8, pad=10))
#
#     def create_detailed_plots(self):
#         """Create additional detailed plots"""
#         # 1. Detailed leaf edge detection plot
#         fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
#
#         if hasattr(self, 'leaf_analyses'):
#             analysis = self.leaf_analyses[1]  # Middle profile
#
#             # Plot 1: Dose profile with edges
#             x_mm = np.arange(len(analysis['profile'])) * self.pixel_spacing[1]
#             ax1.plot(x_mm, analysis['profile'], 'b-', label='Original', alpha=0.5)
#             ax1.plot(x_mm, analysis['profile_smooth'], 'r-', label='Smoothed', linewidth=2)
#
#             # Mark leaf pairs
#             for i, pair in enumerate(analysis['leaf_pairs'][:10]):  # Show first 10
#                 ax1.axvspan(pair['left_edge_mm'], pair['right_edge_mm'],
#                             alpha=0.2, color='green')
#                 ax1.text((pair['left_edge_mm'] + pair['right_edge_mm']) / 2,
#                          ax1.get_ylim()[1] * 0.9, f'L{i}',
#                          ha='center', fontsize=8)
#
#             ax1.set_xlabel('X Position (mm)')
#             ax1.set_ylabel('Dose')
#             ax1.set_title('Detailed Leaf Edge Detection')
#             ax1.legend()
#             ax1.grid(True, alpha=0.3)
#
#             # Plot 2: Zoomed view
#             if analysis['leaf_pairs']:
#                 left_edge = analysis['leaf_pairs'][0]['left_edge_mm']
#                 right_edge = analysis['leaf_pairs'][0]['right_edge_mm']
#
#                 mask = (x_mm >= left_edge - 5) & (x_mm <= right_edge + 5)
#                 ax2.plot(x_mm[mask], analysis['profile_smooth'][mask], 'r-', linewidth=2)
#                 ax2.plot(x_mm[mask], analysis['gradient'][mask], 'g-', label='Gradient')
#
#                 ax2.axvline(x=left_edge, color='blue', linestyle='--', label='Left Edge')
#                 ax2.axvline(x=right_edge, color='blue', linestyle='--', label='Right Edge')
#                 ax2.axhline(y=0, color='k', alpha=0.3)
#
#                 ax2.set_xlabel('X Position (mm)')
#                 ax2.set_ylabel('Dose / Gradient')
#                 ax2.set_title(f'Single Leaf Analysis (Width: {analysis["leaf_pairs"][0]["width_mm"]:.1f} mm)')
#                 ax2.legend()
#                 ax2.grid(True, alpha=0.3)
#
#         plt.tight_layout()
#         plt.savefig('detailed_leaf_analysis.png', dpi=150)
#         plt.show()
#
#         # 2. Export data to files
#         self.export_analysis_data()
#
#     def export_analysis_data(self):
#         """Export analysis results to files"""
#         print("\nExporting analysis data...")
#
#         # Export leaf positions to CSV
#         if hasattr(self, 'leaf_positions_df'):
#             self.leaf_positions_df.to_csv('inferred_leaf_positions.csv', index=False)
#             print("✓ Inferred leaf positions saved to 'inferred_leaf_positions.csv'")
#
#         # Export field data
#         if hasattr(self, 'field_data'):
#             field_df = pd.DataFrame(self.field_data)
#             # Remove binary arrays for CSV
#             if 'dose_slice' in field_df.columns:
#                 field_df = field_df.drop(columns=['dose_slice', 'binary_slice'])
#             field_df.to_csv('field_boundaries.csv', index=False)
#             print("✓ Field boundaries saved to 'field_boundaries.csv'")
#
#         # Export summary statistics
#         with open('analysis_summary.txt', 'w') as f:
#             f.write(f"RT Dose MLC Analysis Summary\n")
#             f.write("=" * 40 + "\n\n")
#             f.write(f"File: {self.rtdose_path}\n")
#             f.write(f"Date: {pd.Timestamp.now()}\n\n")
#
#             f.write(f"Dose Grid: {self.dose_grid.shape}\n")
#             f.write(f"Pixel Spacing: {self.pixel_spacing} mm\n")
#             f.write(f"Slice Thickness: {self.slice_thickness_mm} mm\n\n")
#
#             if hasattr(self, 'field_data') and self.field_data:
#                 f.write(
#                     f"Field Width Range: {min(f['field_width_mm'] for f in self.field_data):.1f} - {max(f['field_width_mm'] for f in self.field_data):.1f} mm\n")
#                 f.write(f"Average Field Width: {np.mean([f['field_width_mm'] for f in self.field_data]):.1f} mm\n")
#                 f.write(
#                     f"Inferred Leaves in Field: {np.mean([f['field_width_mm'] for f in self.field_data]) / self.leaf_width_mm:.1f}\n\n")
#
#             f.write("NOTE: These are INFERRED positions. For exact MLC data,\n")
#             f.write("obtain the RT Plan file referenced in the RT Dose.\n")
#
#         print("✓ Summary saved to 'analysis_summary.txt'")
#         print("\nAnalysis complete!")
#
#
# # ============================================================================
# # MAIN EXECUTION
# # ============================================================================
#
# def main():
#     # Use your specific file path
#     rtdose_file = "D:/dose/TG244_3Dcrt/Export_002442/RTDOSE_BeamDose_Beam 1.1.2.276.0.7230010.3.1.4.3706580561.8300.1766721854.565.dcm"
#
#     # Create analyzer instance
#     print("=" * 60)
#     print("RT DOSE MLC POSITION INFERENCE TOOL")
#     print("=" * 60)
#
#     analyzer = RTDoseMLCAnalyzer(
#         rtdose_path=rtdose_file,
#         leaf_width_mm=10.0,  # Your leaf width
#         slice_thickness_mm=2.5,  # Your slice thickness
#         num_leaves=60  # Your leaf count
#     )
#
#     # Run all analyses
#     analyzer.detect_field_boundaries()
#     analyzer.analyze_leaf_patterns()
#     analyzer.reconstruct_3d_mlc_shape()
#     analyzer.generate_inferred_leaf_positions()
#
#     # Create comprehensive visualization
#     analyzer.visualize_complete_analysis(save_path='mlc_analysis_full.png')
#
#     # Print key findings
#     print("\n" + "=" * 60)
#     print("KEY FINDINGS")
#     print("=" * 60)
#
#     if hasattr(analyzer, 'field_data') and analyzer.field_data:
#         avg_width = np.mean([f['field_width_mm'] for f in analyzer.field_data])
#         inferred_leaves = avg_width / analyzer.leaf_width_mm
#
#         print(f"• Average field width: {avg_width:.1f} mm")
#         print(f"• Inferred number of open leaves: {inferred_leaves:.1f}")
#         print(
#             f"• Expected with {analyzer.num_leaves} leaves of {analyzer.leaf_width_mm}mm: {analyzer.num_leaves * analyzer.leaf_width_mm:.0f} mm")
#
#     print("\n⚠️  IMPORTANT: These are INFERRED positions only!")
#     print("For exact MLC positions, obtain the RT Plan file.")
#     print("=" * 60)
#
#
# if __name__ == "__main__":
#     main()
# =============================================================================================================================================================================

import pydicom
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
import os
from tqdm import tqdm
import json
from scipy import ndimage, signal


class CompleteDoseMLCAnalyzer:
    def __init__(self, rtdose_path, leaf_width_mm=10, num_leaves=60):
        """
        Initialize analyzer with RT Dose file and MLC parameters
        """
        self.rtdose_path = rtdose_path
        self.leaf_width_mm = leaf_width_mm
        self.num_leaves = num_leaves
        self.num_leaf_pairs = num_leaves // 2

        # Load and process DICOM
        self.load_dicom()

    def load_dicom(self):
        """Load and process RT Dose DICOM file"""
        print(f"Loading RT Dose file: {self.rtdose_path}")
        self.dose = pydicom.dcmread(self.rtdose_path)

        # Extract dose grid
        self.dose_grid = self.dose.pixel_array * self.dose.DoseGridScaling

        # Get spatial information
        if hasattr(self.dose, 'PixelSpacing'):
            self.pixel_spacing = self.dose.PixelSpacing  # [row, column] in mm
        else:
            self.pixel_spacing = [2.5, 2.5]
            print("Assuming pixel spacing: 2.5 × 2.5 mm")

        if hasattr(self.dose, 'GridFrameOffsetVector'):
            self.z_positions = self.dose.GridFrameOffsetVector
        else:
            self.z_positions = np.arange(self.dose_grid.shape[0]) * 2.5

        print(f"Dose grid shape: {self.dose_grid.shape}")
        print(f"Pixel spacing: {self.pixel_spacing} mm")
        print(f"Dose range: {self.dose_grid.min():.4f} - {self.dose_grid.max():.4f}")
        print(f"Number of slices: {self.dose_grid.shape[0]}")

        # Calculate global statistics
        self.global_max_dose = self.dose_grid.max()
        self.global_mean_dose = self.dose_grid.mean()

    def process_all_173_frames(self):
        """
        Process ALL 173 frames regardless of dose level
        """
        print(f"\nProcessing ALL {self.dose_grid.shape[0]} frames...")

        all_frame_results = []

        for frame_idx in tqdm(range(self.dose_grid.shape[0]), desc="Processing frames"):
            dose_slice = self.dose_grid[frame_idx]
            z_position = self.z_positions[frame_idx] if frame_idx < len(self.z_positions) else frame_idx * 2.5

            # Process EVERY frame, even if low dose
            frame_result = self.analyze_frame(dose_slice, frame_idx, z_position)
            all_frame_results.append(frame_result)

        print(f"\n✓ Processed all {len(all_frame_results)} frames")
        self.frame_results = all_frame_results
        return all_frame_results

    def analyze_frame(self, dose_slice, frame_idx, z_position):
        """Analyze a single frame"""
        # Always analyze, even if dose is zero
        dose_normalized = dose_slice / self.global_max_dose if self.global_max_dose > 0 else dose_slice

        # Try multiple thresholds to detect field
        field_detected = False
        field_bounds = None
        field_stats = None

        for threshold in [0.1, 0.05, 0.01, 0.005]:  # Try decreasing thresholds
            binary_field = dose_normalized > threshold

            if np.any(binary_field):
                rows = np.any(binary_field, axis=1)
                cols = np.any(binary_field, axis=0)

                if np.any(rows) and np.any(cols):
                    y_min, y_max = np.where(rows)[0][[0, -1]]
                    x_min, x_max = np.where(cols)[0][[0, -1]]

                    # Convert to mm
                    x_min_mm = x_min * self.pixel_spacing[1]
                    x_max_mm = x_max * self.pixel_spacing[1]
                    y_min_mm = y_min * self.pixel_spacing[0]
                    y_max_mm = y_max * self.pixel_spacing[0]

                    field_width_mm = x_max_mm - x_min_mm
                    field_height_mm = y_max_mm - y_min_mm
                    field_center_x = (x_min_mm + x_max_mm) / 2
                    field_center_y = (y_min_mm + y_max_mm) / 2

                    field_detected = True
                    field_bounds = {
                        'x_min': x_min, 'x_max': x_max,
                        'y_min': y_min, 'y_max': y_max,
                        'x_min_mm': x_min_mm, 'x_max_mm': x_max_mm,
                        'y_min_mm': y_min_mm, 'y_max_mm': y_max_mm,
                        'threshold_used': threshold
                    }
                    field_stats = {
                        'width_mm': field_width_mm,
                        'height_mm': field_height_mm,
                        'center_x': field_center_x,
                        'center_y': field_center_y,
                        'detected': True
                    }
                    break

        # If no field detected at any threshold, use default values
        if not field_detected:
            # Use center of image as default
            center_x = dose_slice.shape[1] // 2
            center_y = dose_slice.shape[0] // 2

            field_bounds = {
                'x_min': 0, 'x_max': dose_slice.shape[1] - 1,
                'y_min': 0, 'y_max': dose_slice.shape[0] - 1,
                'x_min_mm': 0, 'x_max_mm': (dose_slice.shape[1] - 1) * self.pixel_spacing[1],
                'y_min_mm': 0, 'y_max_mm': (dose_slice.shape[0] - 1) * self.pixel_spacing[0],
                'threshold_used': 0,
                'no_field': True
            }
            field_stats = {
                'width_mm': dose_slice.shape[1] * self.pixel_spacing[1],
                'height_mm': dose_slice.shape[0] * self.pixel_spacing[0],
                'center_x': center_x * self.pixel_spacing[1],
                'center_y': center_y * self.pixel_spacing[0],
                'detected': False
            }

        # Generate leaf positions (always generate them, even if no field)
        leaf_positions = self.generate_leaf_positions_for_frame(
            dose_slice, field_bounds, field_stats
        )

        return {
            'frame_index': frame_idx,
            'z_position': z_position,
            'dose_slice': dose_slice,
            'dose_normalized': dose_normalized,
            'field_bounds': field_bounds,
            'field_stats': field_stats,
            'leaf_positions': leaf_positions,
            'dose_stats': {
                'max': dose_slice.max(),
                'mean': dose_slice.mean(),
                'min': dose_slice.min(),
                'relative_to_global': dose_slice.max() / self.global_max_dose if self.global_max_dose > 0 else 0
            },
            'has_dose': dose_slice.max() > 0.001 * self.global_max_dose
        }

    def generate_leaf_positions_for_frame(self, dose_slice, field_bounds, field_stats):
        """Generate leaf positions for a frame"""
        leaf_positions = []

        # Use field center or image center
        if field_stats['detected']:
            field_center_x = field_stats['center_x']
            x_min_mm = field_bounds['x_min_mm']
            x_max_mm = field_bounds['x_max_mm']
        else:
            # Use image center if no field detected
            field_center_x = (dose_slice.shape[1] // 2) * self.pixel_spacing[1]
            x_min_mm = 0
            x_max_mm = dose_slice.shape[1] * self.pixel_spacing[1]

        # Always generate all 60 leaves
        # Calculate field width for leaf distribution
        field_width_mm = field_stats['width_mm']

        # Determine how many leaves to show based on dose level
        max_dose_relative = dose_slice.max() / self.global_max_dose if self.global_max_dose > 0 else 0

        if max_dose_relative > 0.5:  # High dose
            leaves_in_field = min(int(field_width_mm / self.leaf_width_mm), self.num_leaves)
        elif max_dose_relative > 0.1:  # Medium dose
            leaves_in_field = min(int(field_width_mm / self.leaf_width_mm * 0.7), self.num_leaves)
        else:  # Low or no dose
            leaves_in_field = self.num_leaves // 2  # Show half by default

        # Center leaves
        total_leaf_width = leaves_in_field * self.leaf_width_mm
        start_x = field_center_x - total_leaf_width / 2

        for leaf_idx in range(self.num_leaves):
            center_mm = start_x + leaf_idx * self.leaf_width_mm + self.leaf_width_mm / 2
            left_mm = center_mm - self.leaf_width_mm / 2
            right_mm = center_mm + self.leaf_width_mm / 2

            # Check if leaf is in "field" based on position
            in_field = (x_min_mm <= center_mm <= x_max_mm)

            # Convert to pixel indices
            left_idx = int(left_mm / self.pixel_spacing[1])
            right_idx = int(right_mm / self.pixel_spacing[1])

            # Calculate dose at leaf center
            y_center = dose_slice.shape[0] // 2
            center_px = int(center_mm / self.pixel_spacing[1])
            center_px = max(0, min(center_px, dose_slice.shape[1] - 1))

            # Get dose value (average over small region)
            y_start = max(0, y_center - 2)
            y_end = min(dose_slice.shape[0], y_center + 3)
            x_start = max(0, center_px - 2)
            x_end = min(dose_slice.shape[1], center_px + 3)

            dose_at_leaf = np.mean(dose_slice[y_start:y_end, x_start:x_end]) if dose_slice.size > 0 else 0

            leaf_positions.append({
                'leaf_index': leaf_idx,
                'pair_index': leaf_idx // 2,
                'side': 'A' if leaf_idx % 2 == 0 else 'B',
                'center_mm': center_mm,
                'left_mm': left_mm,
                'right_mm': right_mm,
                'width_mm': self.leaf_width_mm,
                'left_idx': left_idx,
                'right_idx': right_idx,
                'in_field': in_field,
                'dose_at_center': dose_at_leaf,
                'center_px': center_px,
                'y_center': y_center
            })

        return leaf_positions

    def create_all_173_visualizations(self, output_dir="all_173_frames"):
        """
        Create visualizations for ALL 173 frames
        """
        print(f"\nCreating visualizations for all {len(self.frame_results)} frames...")

        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "individual_frames"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "dose_level_groups"), exist_ok=True)

        # Process each frame
        all_viz_data = []

        for frame_result in tqdm(self.frame_results, desc="Creating frame visualizations"):
            viz_data = self.create_frame_visualization(frame_result, output_dir)
            all_viz_data.append(viz_data)

        # Create summary and group visualizations
        self.create_comprehensive_summaries(all_viz_data, output_dir)

        # Export all data
        self.export_all_frame_data(all_viz_data, output_dir)

        print(f"\n✓ Created visualizations for ALL {len(self.frame_results)} frames")
        print(f"✓ Output directory: {output_dir}")

        return all_viz_data

    def create_frame_visualization(self, frame_result, output_dir):
        """Create visualization for a single frame"""
        frame_idx = frame_result['frame_index']
        dose_slice = frame_result['dose_slice']
        dose_normalized = frame_result['dose_normalized']
        field_bounds = frame_result['field_bounds']
        leaf_positions = frame_result['leaf_positions']
        has_dose = frame_result['has_dose']

        # Create figure - simpler layout for all frames
        fig = plt.figure(figsize=(16, 10))

        # 1. Dose distribution with leaf positions
        ax1 = plt.subplot(2, 3, 1)

        # Use appropriate colormap based on dose level
        if has_dose:
            im1 = ax1.imshow(dose_slice, cmap='jet', aspect='auto',
                             extent=[0, dose_slice.shape[1] * self.pixel_spacing[1],
                                     0, dose_slice.shape[0] * self.pixel_spacing[0]])
        else:
            im1 = ax1.imshow(dose_slice, cmap='gray', aspect='auto',
                             extent=[0, dose_slice.shape[1] * self.pixel_spacing[1],
                                     0, dose_slice.shape[0] * self.pixel_spacing[0]])

        # Overlay leaf positions
        leaf_count = 0
        for leaf in leaf_positions:
            if leaf.get('in_field', False):
                # Draw leaf rectangle
                rect = Rectangle(
                    (leaf['left_mm'], field_bounds['y_min_mm']),
                    leaf['width_mm'], field_bounds['y_max_mm'] - field_bounds['y_min_mm'],
                    linewidth=0.5, edgecolor='white', facecolor='none', alpha=0.3
                )
                ax1.add_patch(rect)
                leaf_count += 1

        # Add field boundary if detected
        if field_bounds.get('detected', True) and not field_bounds.get('no_field', False):
            field_rect = Rectangle(
                (field_bounds['x_min_mm'], field_bounds['y_min_mm']),
                field_bounds['x_max_mm'] - field_bounds['x_min_mm'],
                field_bounds['y_max_mm'] - field_bounds['y_min_mm'],
                linewidth=1, edgecolor='red', facecolor='none', linestyle='--', alpha=0.5
            )
            ax1.add_patch(field_rect)

        title_color = 'blue' if has_dose else 'gray'
        ax1.set_title(f'Frame {frame_idx:03d} - Z={frame_result["z_position"]:.1f} mm\n'
                      f'{leaf_count} leaves in field',
                      color=title_color, fontsize=11)
        ax1.set_xlabel('X (mm)')
        ax1.set_ylabel('Y (mm)')
        plt.colorbar(im1, ax=ax1, label='Dose')

        # 2. X Profile with leaf markers
        ax2 = plt.subplot(2, 3, 2)
        y_center = dose_slice.shape[0] // 2
        x_profile = dose_slice[y_center, :]
        x_mm = np.arange(len(x_profile)) * self.pixel_spacing[1]

        ax2.plot(x_mm, x_profile, 'b-' if has_dose else 'gray',
                 linewidth=1.5, alpha=0.8 if has_dose else 0.5)

        # Mark leaf positions
        for leaf in leaf_positions:
            if leaf.get('in_field', False):
                # Shade leaf area
                ax2.axvspan(leaf['left_mm'], leaf['right_mm'],
                            alpha=0.15, color='green' if has_dose else 'gray')

                # Add leaf number for every 3rd leaf
                if leaf['leaf_index'] % 3 == 0:
                    ax2.text(leaf['center_mm'], ax2.get_ylim()[1] * 0.9,
                             f"L{leaf['leaf_index']}", rotation=90,
                             ha='center', va='top', fontsize=6, alpha=0.7)

        ax2.set_xlabel('X Position (mm)')
        ax2.set_ylabel('Dose')
        ax2.set_title('X-Axis Dose Profile')
        ax2.grid(True, alpha=0.2)

        # 3. Leaf position and dose values
        ax3 = plt.subplot(2, 3, 3)

        leaf_indices = [leaf['leaf_index'] for leaf in leaf_positions]
        leaf_centers = [leaf['center_mm'] for leaf in leaf_positions]
        leaf_doses = [leaf['dose_at_center'] for leaf in leaf_positions]
        in_field = [leaf.get('in_field', False) for leaf in leaf_positions]

        # Scatter plot: position vs leaf index, colored by dose
        scatter = ax3.scatter(leaf_centers, leaf_indices,
                              c=leaf_doses, cmap='viridis',
                              s=30, alpha=0.7, edgecolors='black', linewidth=0.5)

        # Mark leaves in field with different marker
        field_x = [cent for cent, inf in zip(leaf_centers, in_field) if inf]
        field_y = [idx for idx, inf in zip(leaf_indices, in_field) if inf]
        if field_x:
            ax3.scatter(field_x, field_y, facecolors='none',
                        edgecolors='red', s=50, linewidth=1, alpha=0.5, marker='s')

        ax3.set_xlabel('Leaf Center (mm)')
        ax3.set_ylabel('Leaf Index')
        ax3.set_title('Leaf Positions with Dose Values')
        ax3.grid(True, alpha=0.2)
        plt.colorbar(scatter, ax=ax3, label='Dose at Leaf')

        # 4. Dose values bar chart (top 20 leaves)
        ax4 = plt.subplot(2, 3, 4)

        # Sort leaves by dose
        sorted_leaves = sorted(leaf_positions, key=lambda x: x['dose_at_center'], reverse=True)
        top_leaves = sorted_leaves[:20]

        if top_leaves:
            leaf_nums = [f"L{leaf['leaf_index']}" for leaf in top_leaves]
            doses = [leaf['dose_at_center'] for leaf in top_leaves]

            bars = ax4.bar(leaf_nums, doses, color='skyblue', edgecolor='navy', alpha=0.7)

            # Add value labels
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax4.text(bar.get_x() + bar.get_width() / 2., height,
                             f'{height:.3f}', ha='center', va='bottom',
                             fontsize=6, rotation=45)

        ax4.set_xlabel('Leaf Index')
        ax4.set_ylabel('Dose')
        ax4.set_title('Top 20 Leaves by Dose')
        ax4.tick_params(axis='x', rotation=45)
        ax4.grid(True, alpha=0.2)

        # 5. Frame statistics
        ax5 = plt.subplot(2, 3, 5)

        # Create pie chart for dose distribution
        total_dose = dose_slice.sum()
        if total_dose > 0:
            # Calculate dose in field vs out of field
            dose_in_leaves = sum(leaf['dose_at_center'] for leaf in leaf_positions if leaf.get('in_field', False))
            dose_out_leaves = sum(leaf['dose_at_center'] for leaf in leaf_positions if not leaf.get('in_field', False))

            sizes = [dose_in_leaves, dose_out_leaves]
            labels = ['In Field', 'Out of Field']
            colors = ['lightgreen', 'lightcoral']

            wedges, texts, autotexts = ax5.pie(sizes, labels=labels, colors=colors,
                                               autopct='%1.1f%%', startangle=90)

            for autotext in autotexts:
                autotext.set_color('black')
                autotext.set_fontsize(8)

            ax5.set_title('Dose Distribution')
        else:
            ax5.text(0.5, 0.5, 'No Significant Dose',
                     ha='center', va='center', fontsize=12, color='gray')
            ax5.set_title('Dose Distribution - No Data')

        # 6. Information panel
        ax6 = plt.subplot(2, 3, 6)
        ax6.axis('off')

        # Frame statistics
        max_dose = frame_result['dose_stats']['max']
        mean_dose = frame_result['dose_stats']['mean']
        relative_dose = frame_result['dose_stats']['relative_to_global']

        leaves_in_field = sum(1 for leaf in leaf_positions if leaf.get('in_field', False))
        avg_dose_in_field = np.mean([leaf['dose_at_center'] for leaf in leaf_positions
                                     if leaf.get('in_field', False)]) if leaves_in_field > 0 else 0

        info_text = f"""
        FRAME {frame_idx:03d} - COMPLETE ANALYSIS
        ===================================

        POSITION:
        • Z = {frame_result['z_position']:.1f} mm
        • Frame {frame_idx} of {len(self.frame_results)}

        DOSE STATISTICS:
        • Max Dose: {max_dose:.4f}
        • Mean Dose: {mean_dose:.4f}
        • Relative to Global Max: {relative_dose:.2%}

        FIELD ANALYSIS:
        • Field Detected: {'Yes' if field_bounds.get('detected', False) else 'No'}
        • Field Width: {frame_result['field_stats']['width_mm']:.1f} mm
        • Threshold Used: {field_bounds.get('threshold_used', 0):.3f}

        LEAF ANALYSIS:
        • Total Leaves: {len(leaf_positions)}
        • Leaves in Field: {leaves_in_field}
        • Avg Dose in Field: {avg_dose_in_field:.4f}

        DOSE LEVEL:
        • {'HIGH DOSE' if relative_dose > 0.5 else
        'MEDIUM DOSE' if relative_dose > 0.1 else
        'LOW DOSE' if relative_dose > 0.01 else 'NO DOSE'}
        """

        ax6.text(0.05, 0.95, info_text, transform=ax6.transAxes,
                 fontsize=8, verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

        plt.suptitle(f'Complete Leaf-Dose Alignment - Frame {frame_idx:03d}',
                     fontsize=14, fontweight='bold', y=1.02)

        plt.tight_layout()

        # Save figure
        output_path = os.path.join(output_dir, "individual_frames",
                                   f"frame_{frame_idx:03d}_analysis.png")
        plt.savefig(output_path, dpi=120, bbox_inches='tight')  # Lower DPI for faster saving
        plt.close(fig)

        # Return metadata
        return {
            'frame_index': frame_idx,
            'output_path': output_path,
            'max_dose': max_dose,
            'leaves_in_field': leaves_in_field,
            'field_width': frame_result['field_stats']['width_mm'],
            'has_dose': has_dose,
            'relative_dose': relative_dose
        }

    def create_comprehensive_summaries(self, all_viz_data, output_dir):
        """Create comprehensive summary visualizations"""

        # 1. Create frames by dose level groups
        high_dose_frames = [d for d in all_viz_data if d['relative_dose'] > 0.5]
        medium_dose_frames = [d for d in all_viz_data if 0.1 < d['relative_dose'] <= 0.5]
        low_dose_frames = [d for d in all_viz_data if 0.01 < d['relative_dose'] <= 0.1]
        no_dose_frames = [d for d in all_viz_data if d['relative_dose'] <= 0.01]

        print(f"\nFrame distribution by dose level:")
        print(f"  • High dose (>50%): {len(high_dose_frames)} frames")
        print(f"  • Medium dose (10-50%): {len(medium_dose_frames)} frames")
        print(f"  • Low dose (1-10%): {len(low_dose_frames)} frames")
        print(f"  • No dose (<1%): {len(no_dose_frames)} frames")

        # Save dose level groups
        groups = {
            'high_dose': high_dose_frames,
            'medium_dose': medium_dose_frames,
            'low_dose': low_dose_frames,
            'no_dose': no_dose_frames
        }

        for group_name, group_frames in groups.items():
            if group_frames:
                group_dir = os.path.join(output_dir, "dose_level_groups", group_name)
                os.makedirs(group_dir, exist_ok=True)

                # Create summary plot for this group
                fig, axes = plt.subplots(2, 2, figsize=(12, 10))
                axes = axes.flatten()

                # Show first 4 frames from this group
                for idx, frame_data in enumerate(group_frames[:4]):
                    if idx < 4:
                        frame_idx = frame_data['frame_index']

                        # Load and display the frame image
                        img_path = frame_data['output_path']
                        if os.path.exists(img_path):
                            img = plt.imread(img_path)
                            axes[idx].imshow(img)
                            axes[idx].set_title(f'Frame {frame_idx}', fontsize=10)
                            axes[idx].axis('off')

                plt.suptitle(f'{group_name.replace("_", " ").title()} Frames',
                             fontsize=14, fontweight='bold')
                plt.tight_layout()
                plt.savefig(os.path.join(group_dir, f"{group_name}_summary.png"),
                            dpi=150, bbox_inches='tight')
                plt.close()

                # Save frame list
                frame_list = [f['frame_index'] for f in group_frames]
                with open(os.path.join(group_dir, f"{group_name}_frames.txt"), 'w') as f:
                    f.write(f"Total frames: {len(frame_list)}\n")
                    f.write("Frame indices:\n")
                    for frame_idx in frame_list:
                        f.write(f"{frame_idx}\n")

        # 2. Create overall summary plot
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Plot 1: Max dose vs frame
        frame_indices = [d['frame_index'] for d in all_viz_data]
        max_doses = [d['max_dose'] for d in all_viz_data]

        axes[0, 0].plot(frame_indices, max_doses, 'b-', linewidth=1.5, alpha=0.7)
        axes[0, 0].fill_between(frame_indices, 0, max_doses, alpha=0.3, color='blue')
        axes[0, 0].set_xlabel('Frame Index')
        axes[0, 0].set_ylabel('Max Dose')
        axes[0, 0].set_title('Maximum Dose per Frame')
        axes[0, 0].grid(True, alpha=0.3)

        # Plot 2: Leaves in field vs frame
        leaves_in_field = [d['leaves_in_field'] for d in all_viz_data]

        axes[0, 1].plot(frame_indices, leaves_in_field, 'g-', linewidth=1.5, alpha=0.7)
        axes[0, 1].set_xlabel('Frame Index')
        axes[0, 1].set_ylabel('Leaves in Field')
        axes[0, 1].set_title('Leaves in Field per Frame')
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].axhline(y=self.num_leaves, color='red', linestyle='--', alpha=0.5,
                           label=f'Max ({self.num_leaves})')
        axes[0, 1].legend()

        # Plot 3: Field width vs frame
        field_widths = [d['field_width'] for d in all_viz_data]

        axes[1, 0].plot(frame_indices, field_widths, 'r-', linewidth=1.5, alpha=0.7)
        axes[1, 0].set_xlabel('Frame Index')
        axes[1, 0].set_ylabel('Field Width (mm)')
        axes[1, 0].set_title('Field Width per Frame')
        axes[1, 0].grid(True, alpha=0.3)

        # Plot 4: Dose level distribution
        dose_levels = ['High', 'Medium', 'Low', 'No Dose']
        dose_counts = [len(high_dose_frames), len(medium_dose_frames),
                       len(low_dose_frames), len(no_dose_frames)]
        colors = ['green', 'yellow', 'orange', 'red']

        axes[1, 1].bar(dose_levels, dose_counts, color=colors, alpha=0.7)
        axes[1, 1].set_xlabel('Dose Level')
        axes[1, 1].set_ylabel('Number of Frames')
        axes[1, 1].set_title('Frame Distribution by Dose Level')

        # Add count labels on bars
        for i, count in enumerate(dose_counts):
            axes[1, 1].text(i, count + 0.5, str(count),
                            ha='center', va='bottom', fontweight='bold')

        plt.suptitle(f'Complete Analysis Summary - {len(all_viz_data)} Frames',
                     fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "complete_summary.png"),
                    dpi=150, bbox_inches='tight')
        plt.close()

        # 3. Create animation-ready frames
        self.create_animation_frames(all_viz_data, output_dir)

    def create_animation_frames(self, all_viz_data, output_dir):
        """Create simplified frames for animation"""
        anim_dir = os.path.join(output_dir, "animation_frames")
        os.makedirs(anim_dir, exist_ok=True)

        print(f"\nCreating animation frames...")

        for viz_data in tqdm(all_viz_data, desc="Animation frames"):
            frame_idx = viz_data['frame_index']

            # Create simple frame for animation
            fig, ax = plt.subplots(figsize=(10, 6))

            # Get frame data
            frame_result = self.frame_results[frame_idx]
            dose_slice = frame_result['dose_slice']
            leaf_positions = frame_result['leaf_positions']

            # Plot dose
            im = ax.imshow(dose_slice, cmap='hot', aspect='auto')

            # Overlay leaf positions
            for leaf in leaf_positions:
                if leaf.get('in_field', False):
                    # Draw vertical line at leaf center
                    ax.axvline(x=leaf['center_px'], color='cyan',
                               alpha=0.3, linewidth=0.5)

            ax.set_title(f'Frame {frame_idx:03d} - Leaf Alignment', fontsize=12)
            ax.set_xlabel('X (pixels)')
            ax.set_ylabel('Y (pixels)')

            plt.colorbar(im, ax=ax, label='Dose')
            plt.tight_layout()

            # Save animation frame
            plt.savefig(os.path.join(anim_dir, f"anim_frame_{frame_idx:03d}.png"),
                        dpi=100, bbox_inches='tight')
            plt.close()

        print(f"✓ Created {len(all_viz_data)} animation frames")

    def export_all_frame_data(self, all_viz_data, output_dir):
        """Export all frame data to files"""

        # Create comprehensive CSV with all data
        all_leaf_data = []

        for frame_result in self.frame_results:
            frame_idx = frame_result['frame_index']

            for leaf in frame_result['leaf_positions']:
                all_leaf_data.append({
                    'frame': frame_idx,
                    'z_position_mm': frame_result['z_position'],
                    'leaf_index': leaf['leaf_index'],
                    'leaf_pair': leaf['pair_index'],
                    'side': leaf['side'],
                    'center_x_mm': leaf['center_mm'],
                    'left_edge_mm': leaf['left_mm'],
                    'right_edge_mm': leaf['right_mm'],
                    'width_mm': leaf['width_mm'],
                    'in_field': leaf.get('in_field', False),
                    'dose_at_center': leaf['dose_at_center'],
                    'max_dose_frame': frame_result['dose_stats']['max'],
                    'mean_dose_frame': frame_result['dose_stats']['mean'],
                    'field_width_mm': frame_result['field_stats']['width_mm'],
                    'field_detected': frame_result['field_stats']['detected'],
                    'has_dose': frame_result['has_dose']
                })

        # Save to CSV
        df = pd.DataFrame(all_leaf_data)

        # Save individual CSVs per frame
        frames_csv_dir = os.path.join(output_dir, "frames_csv")
        os.makedirs(frames_csv_dir, exist_ok=True)

        for frame_idx in range(len(self.frame_results)):
            frame_df = df[df['frame'] == frame_idx]
            if not frame_df.empty:
                frame_df.to_csv(os.path.join(frames_csv_dir, f"frame_{frame_idx:03d}_leaves.csv"),
                                index=False)

        # Save combined CSV
        combined_path = os.path.join(output_dir, "ALL_173_FRAMES_complete_data.csv")
        df.to_csv(combined_path, index=False)
        print(f"\n✓ Complete data saved to: {combined_path}")
        print(f"  • Total entries: {len(df)}")
        print(f"  • Frames: {df['frame'].nunique()}")
        print(f"  • Leaves per frame: {len(df) // df['frame'].nunique()}")

        # Save per-frame summary
        summary_data = []
        for viz_data in all_viz_data:
            summary_data.append({
                'frame': viz_data['frame_index'],
                'z_position_mm': self.frame_results[viz_data['frame_index']]['z_position'],
                'max_dose': viz_data['max_dose'],
                'leaves_in_field': viz_data['leaves_in_field'],
                'field_width_mm': viz_data['field_width'],
                'has_dose': viz_data['has_dose'],
                'relative_dose': viz_data['relative_dose'],
                'image_file': f"frame_{viz_data['frame_index']:03d}_analysis.png"
            })

        summary_df = pd.DataFrame(summary_data)
        summary_path = os.path.join(output_dir, "frame_summary.csv")
        summary_df.to_csv(summary_path, index=False)
        print(f"✓ Frame summary saved to: {summary_path}")

        # Save metadata
        metadata = {
            'analysis_info': {
                'date': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                'software': 'Leaf-Dose Alignment Analyzer',
                'version': '2.0'
            },
            'input_file': self.rtdose_path,
            'dose_grid': {
                'total_frames': self.dose_grid.shape[0],
                'rows': self.dose_grid.shape[1],
                'columns': self.dose_grid.shape[2],
                'pixel_spacing_mm': list(self.pixel_spacing),
                'global_max_dose': float(self.global_max_dose),
                'global_mean_dose': float(self.global_mean_dose)
            },
            'mlc_parameters': {
                'leaf_width_mm': self.leaf_width_mm,
                'num_leaves': self.num_leaves,
                'num_leaf_pairs': self.num_leaf_pairs
            },
            'output_structure': {
                'individual_frames': 'One PNG per frame (173 total)',
                'dose_level_groups': 'Frames grouped by dose level',
                'animation_frames': 'Simplified frames for animation',
                'frames_csv': 'CSV files for each frame',
                'complete_data': 'ALL_173_FRAMES_complete_data.csv',
                'frame_summary': 'frame_summary.csv'
            }
        }

        metadata_path = os.path.join(output_dir, "analysis_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✓ Metadata saved to: {metadata_path}")


# ============================================================================
# MAIN EXECUTION - PROCESS ALL 173 FRAMES
# ============================================================================

def main_process_all_frames():
    """Main function to process ALL 173 frames"""

    # Your RT Dose file
    rtdose_file = "D:/dose/TG244_3Dcrt/Export_002442/RTDOSE_BeamDose_Beam 1.1.2.276.0.7230010.3.1.4.3706580561.8300.1766721854.565.dcm"

    print("=" * 80)
    print("COMPLETE 173-FRAME LEAF-DOSE ALIGNMENT ANALYSIS")
    print("=" * 80)

    # Create analyzer
    print("\nInitializing analyzer...")
    analyzer = CompleteDoseMLCAnalyzer(
        rtdose_path=rtdose_file,
        leaf_width_mm=10.0,
        num_leaves=60
    )

    # Process ALL frames
    print("\n" + "-" * 80)
    print("STEP 1: Processing ALL 173 frames...")
    print("-" * 80)
    all_frames = analyzer.process_all_173_frames()

    # Create visualizations for ALL frames
    print("\n" + "-" * 80)
    print("STEP 2: Creating visualizations for ALL 173 frames...")
    print("-" * 80)
    viz_data = analyzer.create_all_173_visualizations(
        output_dir="COMPLETE_173_FRAMES_ANALYSIS"
    )

    # Final summary
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE - ALL 173 FRAMES PROCESSED!")
    print("=" * 80)

    # Calculate statistics
    frames_with_dose = sum(1 for f in all_frames if f['has_dose'])
    total_leaves_analyzed = sum(len(f['leaf_positions']) for f in all_frames)

    print(f"\n📊 COMPREHENSIVE STATISTICS:")
    print(f"  • Total frames processed: {len(all_frames)}")
    print(f"  • Frames with significant dose: {frames_with_dose}")
    print(f"  • Total leaf position entries: {total_leaves_analyzed:,}")
    print(f"  • Average leaves per frame: {total_leaves_analyzed // len(all_frames)}")
    print(f"  • Global max dose: {analyzer.global_max_dose:.4f}")

    print(f"\n📁 COMPLETE OUTPUT STRUCTURE:")
    print(f"  COMPLETE_173_FRAMES_ANALYSIS/")
    print(f"    ├── individual_frames/")
    print(f"    │   ├── frame_000_analysis.png")
    print(f"    │   ├── frame_001_analysis.png")
    print(f"    │   ├── ...")
    print(f"    │   └── frame_172_analysis.png  ← ALL 173 FRAMES!")
    print(f"    ├── dose_level_groups/")
    print(f"    │   ├── high_dose/")
    print(f"    │   ├── medium_dose/")
    print(f"    │   ├── low_dose/")
    print(f"    │   └── no_dose/")
    print(f"    ├── animation_frames/")
    print(f"    │   ├── anim_frame_000.png")
    print(f"    │   ├── anim_frame_001.png")
    print(f"    │   └── ...")
    print(f"    ├── frames_csv/")
    print(f"    │   ├── frame_000_leaves.csv")
    print(f"    │   ├── frame_001_leaves.csv")
    print(f"    │   └── ...")
    print(f"    ├── ALL_173_FRAMES_complete_data.csv")
    print(f"    ├── frame_summary.csv")
    print(f"    ├── complete_summary.png")
    print(f"    └── analysis_metadata.json")

    print(f"\n🔍 WHAT EACH FRAME VISUALIZATION SHOWS:")
    print(f"  1. Dose distribution with ALL 60 leaf positions overlaid")
    print(f"  2. X-axis dose profile with leaf markers")
    print(f"  3. Leaf position map colored by dose value")
    print(f"  4. Bar chart of dose values at leaf centers")
    print(f"  5. Dose distribution pie chart")
    print(f"  6. Complete statistical summary")

    print(f"\n💾 DATA EXPORTED:")
    print(f"  • 173 individual PNG images (one per frame)")
    print(f"  • 173 individual CSV files (one per frame)")
    print(f"  • 1 combined CSV with ALL data")
    print(f"  • Summary CSV with frame statistics")
    print(f"  • JSON metadata with analysis parameters")

    print(f"\n⚡ PROCESSING DETAILS:")
    print(f"  • Every frame processed, regardless of dose level")
    print(f"  • Adaptive field detection (multiple thresholds)")
    print(f"  • All 60 leaves positioned in every frame")
    print(f"  • Dose values calculated at each leaf center")
    print(f"  • Visual indication of dose level (color coded)")

    print(f"\n⚠️  ANALYSIS NOTES:")
    print(f"  • Frames with very low/no dose still show leaf positions")
    print(f"  • Field detection adapts to dose level")
    print(f"  • Leaf positions are inferred from field boundaries")
    print(f"  • For exact MLC positions, obtain RT Plan file")
    print("=" * 80)


# ============================================================================
# QUICK START - MINIMAL CODE FOR ALL FRAMES
# ============================================================================

def quick_all_frames_analysis(rtdose_path):
    """Quick analysis of all frames with minimal output"""

    print("Quick analysis of all frames...")

    # Load DICOM
    dose = pydicom.dcmread(rtdose_path)
    dose_grid = dose.pixel_array * dose.DoseGridScaling
    pixel_spacing = dose.PixelSpacing if hasattr(dose, 'PixelSpacing') else [2.5, 2.5]

    output_dir = "quick_all_frames"
    os.makedirs(output_dir, exist_ok=True)

    print(f"Processing {dose_grid.shape[0]} frames...")

    for frame_idx in tqdm(range(dose_grid.shape[0]), desc="Frames"):
        dose_slice = dose_grid[frame_idx]

        # Simple visualization
        fig, ax = plt.subplots(figsize=(10, 6))

        im = ax.imshow(dose_slice, cmap='jet')
        ax.set_title(f'Frame {frame_idx} - Leaf Alignment')
        ax.set_xlabel('X (pixels)')
        ax.set_ylabel('Y (pixels)')

        plt.colorbar(im, ax=ax, label='Dose')
        plt.tight_layout()

        # Save
        plt.savefig(os.path.join(output_dir, f"frame_{frame_idx:03d}.png"),
                    dpi=100, bbox_inches='tight')
        plt.close()

    print(f"\n✓ Created {dose_grid.shape[0]} frames in '{output_dir}'")


# ============================================================================
# RUN THE ANALYSIS
# ============================================================================

if __name__ == "__main__":
    # Option 1: Complete analysis of ALL 173 frames
    main_process_all_frames()

    # Option 2: Quick minimal analysis (uncomment if needed)
    # quick_all_frames_analysis(
    #     "D:/dose/TG244_3Dcrt/Export_002442/RTDOSE_BeamDose_Beam 1.1.2.276.0.7230010.3.1.4.3706580561.8300.1766721854.565.dcm"
    # )