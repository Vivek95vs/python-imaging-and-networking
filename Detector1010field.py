# import pandas as pd
# import numpy as np
# from scipy.interpolate import griddata
#
# # STEP 1: Load your Excel file
# #input_file = '40aa8247-a801-4f94-a0c5-afd999de0258.png'  # Replace this with .xlsx if you're using an Excel file
# # If it's an Excel file like 'your_file.xlsx', then:
# # df = pd.read_excel('your_file.xlsx', index_col=0)
# # Since you uploaded an image (PNG), please confirm if you meant an Excel sheet.
#
# # Example only for actual Excel:
# df = pd.read_excel("D:\\1008\\Detector1.xlsx", index_col=0)
#
# # STEP 2: Extract axes and Z-values
# xs = df.columns.astype(float).values  # X-coordinates (e.g., -130, -125, ..., 130)
# ys = df.index.astype(float).values    # Y-coordinates (e.g., 160, 155, ..., -160)
# Z = df.values                         # Shape (len(ys), len(xs))
#
# # STEP 3: Create fine 0.5mm grid
# dx = dy = 0.5
# xi = np.arange(xs.min(), xs.max() + dx, dx)
# yi = np.arange(ys.min(), ys.max() + dy, dy)
# XI, YI = np.meshgrid(xi, yi)
#
# # STEP 4: Interpolation
# # Prepare known data points (non-NaN)
# X_known, Y_known = np.meshgrid(xs, ys)
# known_points = np.vstack((X_known.ravel(), Y_known.ravel())).T
# known_values = Z.ravel()
# valid_mask = ~np.isnan(known_values)
#
# # Interpolate using cubic (or 'linear' if preferred)
# ZI = griddata(
#     points=known_points[valid_mask],
#     values=known_values[valid_mask],
#     xi=(XI, YI),
#     method='nearest'  # or 'linear', 'nearest',cubic
# )
#
# # STEP 5: Save output to Excel
# df_fine = pd.DataFrame(ZI, index=yi, columns=xi)
# df_fine.to_excel("D:\\1008\\interpolated_0p5mm_output-bilinear.xlsx")
#
# print("Interpolation complete. Saved as interpolated_0p5mm_output.xlsx")

import pandas as pd
import numpy as np
from scipy.interpolate import griddata

# STEP 1: Load your Excel file
df = pd.read_excel("D:\\1008\\Detector1.xlsx", index_col=0)

# STEP 2: Extract axes and Z-values
xs = df.columns.astype(float).values  # X-coordinates (e.g., -130, -125, ..., 130)
ys = df.index.astype(float).values    # Y-coordinates (e.g., 160, 155, ..., -160)
Z = df.values                         # Shape (len(ys), len(xs))

# STEP 3: Create fine 0.5mm grid that includes original points
dx = dy = 0.5
xi = np.arange(xs.min(), xs.max() + dx, dx)
yi = np.arange(ys.min(), ys.max() + dy, dy)

# Ensure original points are included in the new grid
xi = np.unique(np.sort(np.concatenate([xi, xs])))
yi = np.unique(np.sort(np.concatenate([yi, ys])))

XI, YI = np.meshgrid(xi, yi)

# STEP 4: Create mask of original points
original_mask = np.zeros_like(XI, dtype=bool)
for x in xs:
    for y in ys:
        x_idx = np.where(np.isclose(xi, x))[0][0]
        y_idx = np.where(np.isclose(yi, y))[0][0]
        original_mask[y_idx, x_idx] = True

# STEP 5: Interpolation
# Prepare known data points
X_known, Y_known = np.meshgrid(xs, ys)
known_points = np.vstack((X_known.ravel(), Y_known.ravel())).T
known_values = Z.ravel()
valid_mask = ~np.isnan(known_values)

# First do nearest neighbor interpolation to get exact original values
ZI_nearest = griddata(
    points=known_points[valid_mask],
    values=known_values[valid_mask],
    xi=(XI, YI),
    method='nearest'
)

# Then do cubic interpolation for smooth results
ZI_cubic = griddata(
    points=known_points[valid_mask],
    values=known_values[valid_mask],
    xi=(XI, YI),
    method='cubic'
)

# Combine - use nearest for original points, cubic elsewhere
ZI = np.where(original_mask, ZI_nearest, ZI_cubic)

# STEP 6: Verify all original points are preserved
for x in xs:
    for y in ys:
        orig_val = df.loc[y, x]
        x_idx = np.where(np.isclose(xi, x))[0][0]
        y_idx = np.where(np.isclose(yi, y))[0][0]
        interp_val = ZI[y_idx, x_idx]
        if not np.isclose(orig_val, interp_val, atol=1e-6):
            print(f"Warning: Mismatch at ({x},{y}) - Original: {orig_val}, Interpolated: {interp_val}")

# STEP 7: Save output to Excel
df_fine = pd.DataFrame(ZI, index=yi, columns=xi)
output_path = "D:\\1008\\interpolated_0.5mm_output_hybrid.xlsx"
df_fine.to_excel(output_path)

print(f"Interpolation complete. Saved as {output_path}")
print("All original data points have been preserved exactly in the output.")
