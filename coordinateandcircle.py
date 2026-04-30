import pandas as pd
import numpy as np
from scipy.interpolate import griddata

# Load CSV file
file_path = "C:/Users/vivek.vs/PycharmProjects/pythonProject/combined_dose_values1.csv"
df = pd.read_csv(file_path, header=None, dtype=str)  # Read as strings to inspect non-numeric values

# Drop the first row

df = df.iloc[1:].reset_index(drop=True)

# Clean and convert to float
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)  # Remove extra spaces
df = df.replace("", np.nan)  # Replace empty strings with NaN
df = df.apply(pd.to_numeric, errors='coerce')  # Convert to float, replacing errors with NaN

# Drop rows and columns that are completely NaN
df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)

# Fill missing values using interpolation
df = df.interpolate(method='linear', axis=0).interpolate(method='linear', axis=1)

# Get center indices
center_row = (df.shape[0] - 1) // 2
center_col = (df.shape[1] - 1) // 2

# Store known (X, Y, Value) points
points = []
values = []

for i in range(df.shape[0]):
    for j in range(df.shape[1]):
        x = j - center_col  # Adjust x coordinate
        y = i - center_row  # Adjust y coordinate
        value = df.iloc[i, j]  # Extract value
        if not np.isnan(value):  # Ensure only valid data points are used
            points.append((x, y))
            values.append(value)

# Convert to NumPy arrays
points = np.array(points)
values = np.array(values)

# Generate a fine grid for interpolation (0.5 step size)
x_min, x_max = points[:, 0].min(), points[:, 0].max()
y_min, y_max = points[:, 1].min(), points[:, 1].max()

x_new = np.arange(x_min, x_max + 0.5, 0.5)
y_new = np.arange(y_min, y_max + 0.5, 0.5)
grid_x, grid_y = np.meshgrid(x_new, y_new)

# Interpolate using griddata
grid_values = griddata(points, values, (grid_x, grid_y), method='linear')

# Define circle radius
circle_radius = 3.0  # cm

# Store values inside the circle
circle_points = []
circle_values = []

for i in range(grid_x.shape[0]):
    for j in range(grid_x.shape[1]):
        x = grid_x[i, j]
        y = grid_y[i, j]
        distance = np.sqrt(x**2 + y**2)  # Euclidean distance from (0,0)

        if distance <= circle_radius:  # Check if inside the circle
            circle_points.append((x, y))
            circle_values.append(grid_values[i, j])

# Convert to DataFrame and save
circle_df = pd.DataFrame(circle_values, index=[f"({x},{y})" for x, y in circle_points], columns=["Value"])
output_path = "C:/Users/vivek.vs/PycharmProjects/pythonProject/values_inside_circle.csv"
circle_df.to_csv(output_path, header=True, index=True)

print(f"Values inside the circle (radius {circle_radius} cm) saved as '{output_path}'")
