import pandas as pd
import numpy as np
import scipy.interpolate as interp

# Load CSV file
df = pd.read_csv("C:/Users/vivek.vs/PycharmProjects/pythonProject/combined_dose_values1.csv", header=None)

# Drop the first row
df = df.iloc[1:].reset_index(drop=True)  # Reset index after dropping

# Drop extra spaces and NaN values if present
df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x).dropna(how='all', axis=1).dropna(how='all', axis=0)

# Get center indices
center_row = (df.shape[0] - 1) // 2
center_col = (df.shape[1] - 1) // 2

# Create a new DataFrame to store updated values
updated_data = df.copy()

# Iterate through all rows and columns
for i in range(df.shape[0]):
    for j in range(df.shape[1]):
        x = j - center_col  # Adjust x coordinate
        y = center_row - i  # Adjust y coordinate (invert y-axis)
        existing_value = df.iloc[i, j]

        # Append (x,y) coordinates to existing value
        updated_data.iloc[i, j] = f"{existing_value} ({x},{y})"

# Save the updated DataFrame to CSV
updated_data.to_csv("C:/Users/vivek.vs/PycharmProjects/pythonProject/Update_values1.csv", header=False, index=False)

print("Updated CSV saved as 'updated_coordinates.csv' with (X,Y) coordinates added to existing values.")

