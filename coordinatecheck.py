import pandas as pd
import numpy as np

# Load the CSV file
df = pd.read_csv("C:/Users/vivek.vs/PycharmProjects/pythonProject/combined_dose_values1.csv", header=None)  # Use header=None if no headers are present

# # Drop extra spaces and NaN values if present
# df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x).dropna(how='all', axis=1).dropna(how='all', axis=0)
#
# # Get the center row and column indices
# center_row = (df.shape[0] - 1) // 2
# center_col = (df.shape[1] - 1) // 2
#
# # Get the center value (handling NaN)
# center_value = df.iloc[center_row, center_col]
#
# if pd.isna(center_value):
#     print("Warning: Center value is NaN. Please check the CSV file for missing data.")
# else:
#     print(f"Center Coordinate: (0,0)")
#     print(f"Center Value: {center_value}")

# Drop the first row
df = df.iloc[1:].reset_index(drop=True)  # Reset index after dropping

# Drop extra spaces and NaN values if present
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x).dropna(how='all', axis=1).dropna(how='all', axis=0)

# Get center indices
center_row = (df.shape[0] - 1) // 2
center_col = (df.shape[1] - 1) // 2

# Print all coordinates with values
for i in range(df.shape[0]):
    for j in range(df.shape[1]):
        x = j - center_col  # Adjust x coordinate
        y = center_row - i  # Adjust y coordinate (invert y-axis)
        value = df.iloc[i, j]
        print(f"Coordinate ({x}, {y}): Value {value}")