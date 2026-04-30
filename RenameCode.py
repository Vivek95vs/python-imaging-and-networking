import os
import re

# Folder containing images
folder_path = "D:\\dummymotion\\kv1"

# Pattern to match files like projD1_6.raw
pattern = re.compile(r"Proj_(\d+)\.raw")

# Collect matching files and sort by number
files = []
for filename in os.listdir(folder_path):
    match = pattern.match(filename)
    if match:
        files.append((int(match.group(1)), filename))

# Sort files based on extracted numbers
files.sort()

# Rename files sequentially
for index, (_, filename) in enumerate(files, start=1):
    new_filename = f"projD2_{index}.raw"
    old_path = os.path.join(folder_path, filename)
    new_path = os.path.join(folder_path, new_filename)

    os.rename(old_path, new_path)
    print(f"Renamed: {filename} → {new_filename}")

print("Renaming complete!")
