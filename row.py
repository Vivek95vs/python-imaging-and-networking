import pandas as pd
import numpy as np

# Load data
df = pd.read_csv("C:/Users/vivek.vs/PycharmProjects/pythonProject/dose_csv_files/combined_dose_values.csv", header=None)

# Define the number of rows per column
rows_per_column = 362

# Calculate the number of columns needed
num_columns = int(np.ceil(len(df) / rows_per_column))

# Split the data into multiple parts
reshaped_data = [df.iloc[i * rows_per_column: (i + 1) * rows_per_column].reset_index(drop=True)
                 for i in range(num_columns)]

# Combine into a DataFrame with columns
new_df = pd.concat(reshaped_data, axis=1)
# Save the new data into a CSV file
new_df.to_csv("C:/Users/vivek.vs/PycharmProjects/pythonProject/combined_dose_values1.csv", index=False, header=False)