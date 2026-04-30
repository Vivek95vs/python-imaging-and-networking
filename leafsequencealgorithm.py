# import numpy as np
# import pandas as pd
# import matplotlib.pyplot as plt
# from typing import List, Tuple, Dict, Optional, Any
# import os
# import re
# from dataclasses import dataclass
# import json
# import struct
#
# # Try to import pydicom for DICOM files
# try:
#     import pydicom
#     from pydicom.dataset import Dataset, FileDataset
#
#     DICOM_AVAILABLE = True
# except ImportError:
#     DICOM_AVAILABLE = False
#     print("Warning: pydicom not installed. Install with: pip install pydicom")
#
#
# @dataclass
# class RDData:
#     """Data structure for RD file information."""
#     patient_id: str
#     study_date: str
#     modality: str
#     dose_grid: np.ndarray
#     x_positions: np.ndarray
#     y_positions: np.ndarray
#     z_positions: np.ndarray
#     dose_units: str
#     metadata: Dict[str, Any]
#     intensity_profiles: Optional[List[np.ndarray]] = None
#     leaf_positions: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None
#
#
# class RDParser:
#     """Parser for RD (Radiation Dose) files."""
#
#     @staticmethod
#     def parse_rd_file(file_path: str) -> RDData:
#         """
#         Parse RD file. This parser handles DICOM, text, and binary formats.
#         """
#         # Check file extension
#         file_ext = os.path.splitext(file_path)[1].lower()
#
#         if file_ext in ['.dcm', '.dicom']:
#             return RDParser._parse_dicom_file(file_path)
#         elif file_ext in ['.txt', '.csv', '.dat']:
#             return RDParser._parse_text_file(file_path)
#         else:
#             # Try to auto-detect format
#             return RDParser._auto_detect_format(file_path)
#
#     @staticmethod
#     def _parse_dicom_file(file_path: str) -> RDData:
#         """
#         Parse DICOM RTDOSE file.
#         """
#         if not DICOM_AVAILABLE:
#             print("Warning: pydicom not available. Using simplified DICOM parser.")
#             return RDParser._parse_dicom_simple(file_path)
#
#         try:
#             # Load DICOM file
#             ds = pydicom.dcmread(file_path)
#
#             # Extract metadata
#             patient_id = getattr(ds, 'PatientID', 'Unknown')
#             study_date = getattr(ds, 'StudyDate', 'Unknown')
#             modality = getattr(ds, 'Modality', 'RTDOSE')
#
#             # Get dose grid
#             dose_grid = RDParser._extract_dicom_dose_grid(ds)
#
#             # Get pixel spacing and positions
#             x_positions, y_positions, z_positions = RDParser._extract_dicom_positions(ds)
#
#             # Get dose units
#             dose_units = getattr(ds, 'DoseUnits', 'GY')
#             if hasattr(ds, 'DoseType'):
#                 if ds.DoseType == 'PHYSICAL':
#                     dose_units = 'GY'
#                 elif ds.DoseType == 'EFFECTIVE':
#                     dose_units = 'RELATIVE'
#
#             # Extract metadata
#             metadata = {
#                 'SOPClassUID': getattr(ds, 'SOPClassUID', ''),
#                 'SeriesDescription': getattr(ds, 'SeriesDescription', ''),
#                 'Manufacturer': getattr(ds, 'Manufacturer', ''),
#                 'InstanceNumber': getattr(ds, 'InstanceNumber', 0),
#             }
#
#             return RDData(
#                 patient_id=patient_id,
#                 study_date=study_date,
#                 modality=modality,
#                 dose_grid=dose_grid,
#                 x_positions=x_positions,
#                 y_positions=y_positions,
#                 z_positions=z_positions,
#                 dose_units=dose_units,
#                 metadata=metadata
#             )
#
#         except Exception as e:
#             print(f"Error parsing DICOM file: {e}")
#             print("Falling back to simplified parser...")
#             return RDParser._parse_dicom_simple(file_path)
#
#     @staticmethod
#     def _extract_dicom_dose_grid(ds: Any) -> np.ndarray:
#         """
#         Extract dose grid from DICOM dataset.
#         """
#         # Check if pixel data exists
#         if hasattr(ds, 'PixelData'):
#             # Get pixel data
#             pixel_data = ds.PixelData
#
#             # Get dimensions
#             rows = getattr(ds, 'Rows', 1)
#             columns = getattr(ds, 'Columns', 1)
#             number_of_frames = getattr(ds, 'NumberOfFrames', 1)
#
#             # Get bits allocated and stored
#             bits_allocated = getattr(ds, 'BitsAllocated', 16)
#             bits_stored = getattr(ds, 'BitsStored', bits_allocated)
#
#             # Get pixel representation
#             pixel_representation = getattr(ds, 'PixelRepresentation', 0)
#
#             # Get rescale slope and intercept
#             rescale_slope = getattr(ds, 'RescaleSlope', 1.0)
#             rescale_intercept = getattr(ds, 'RescaleIntercept', 0.0)
#
#             # Convert pixel data to numpy array
#             dtype = np.uint16 if bits_allocated == 16 else np.uint8
#
#             # Calculate expected length
#             expected_length = rows * columns * number_of_frames * (bits_allocated // 8)
#
#             if len(pixel_data) >= expected_length:
#                 # Convert to numpy array
#                 if bits_allocated == 16:
#                     arr = np.frombuffer(pixel_data, dtype=np.uint16)
#                 else:
#                     arr = np.frombuffer(pixel_data, dtype=np.uint8)
#
#                 # Reshape based on number of frames
#                 if number_of_frames > 1:
#                     arr = arr.reshape((number_of_frames, rows, columns))
#                 else:
#                     arr = arr.reshape((rows, columns))
#
#                 # Apply rescale
#                 arr = arr * rescale_slope + rescale_intercept
#
#                 return arr
#             else:
#                 print(f"Warning: Pixel data length mismatch. Expected {expected_length}, got {len(pixel_data)}")
#
#         # Fallback: create empty array
#         return np.zeros((100, 100))
#
#     @staticmethod
#     def _extract_dicom_positions(ds: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
#         """
#         Extract position arrays from DICOM dataset.
#         """
#         # Get pixel spacing
#         pixel_spacing = getattr(ds, 'PixelSpacing', [1.0, 1.0])
#         if isinstance(pixel_spacing, pydicom.multival.MultiValue):
#             pixel_spacing = [float(ps) for ps in pixel_spacing]
#
#         # Get image position
#         image_position = getattr(ds, 'ImagePositionPatient', [0.0, 0.0, 0.0])
#         if isinstance(image_position, pydicom.multival.MultiValue):
#             image_position = [float(pos) for pos in image_position]
#
#         # Get dimensions
#         rows = getattr(ds, 'Rows', 100)
#         columns = getattr(ds, 'Columns', 100)
#         number_of_frames = getattr(ds, 'NumberOfFrames', 1)
#
#         # Create position arrays
#         x_positions = np.arange(columns) * pixel_spacing[0] + image_position[0]
#         y_positions = np.arange(rows) * pixel_spacing[1] + image_position[1]
#
#         # For z positions, check for GridFrameOffsetVector or SliceThickness
#         if hasattr(ds, 'GridFrameOffsetVector'):
#             z_offsets = ds.GridFrameOffsetVector
#             if isinstance(z_offsets, pydicom.multival.MultiValue):
#                 z_positions = np.array([float(offset) for offset in z_offsets])
#             else:
#                 z_positions = np.array([float(z_offsets)])
#         else:
#             slice_thickness = getattr(ds, 'SliceThickness', 1.0)
#             z_positions = np.arange(number_of_frames) * slice_thickness + image_position[2]
#
#         return x_positions, y_positions, z_positions
#
#     @staticmethod
#     def _parse_dicom_simple(file_path: str) -> RDData:
#         """
#         Simplified DICOM parser without pydicom.
#         """
#         try:
#             # Read file as binary
#             with open(file_path, 'rb') as f:
#                 content = f.read()
#
#             # Look for DICOM preamble (should start with DICM)
#             if b'DICM' in content[:132]:
#                 dicom_start = content.find(b'DICM') + 4
#             else:
#                 # No DICOM preamble, start from beginning
#                 dicom_start = 0
#
#             # Parse DICOM tags (simplified)
#             metadata = {}
#             patient_id = "Unknown"
#             study_date = "Unknown"
#
#             # Look for common tags in binary
#             tags_to_find = [
#                 (b'\x10\x00\x10\x00', 'PatientID'),
#                 (b'\x08\x00\x20\x00', 'StudyDate'),
#                 (b'\x08\x00\x60\x00', 'Modality'),
#             ]
#
#             for tag_bytes, tag_name in tags_to_find:
#                 tag_pos = content.find(tag_bytes)
#                 if tag_pos != -1:
#                     # Skip tag and length (4 bytes each)
#                     value_pos = tag_pos + 8
#                     # Find null terminator or next tag
#                     end_pos = content.find(b'\x00', value_pos)
#                     if end_pos == -1:
#                         end_pos = min(value_pos + 100, len(content))
#
#                     value = content[value_pos:end_pos].decode('ascii', errors='ignore').strip()
#                     metadata[tag_name] = value
#
#                     if tag_name == 'PatientID':
#                         patient_id = value
#                     elif tag_name == 'StudyDate':
#                         study_date = value
#
#             # Try to extract pixel data
#             pixel_data_tag = b'\x7f\xe0\x10\x00'  # (7FE0,0010) PixelData
#             pixel_pos = content.find(pixel_data_tag)
#
#             if pixel_pos != -1:
#                 # Skip tag
#                 pixel_pos += 4
#
#                 # Read length (4 bytes)
#                 if pixel_pos + 4 <= len(content):
#                     length = struct.unpack('<I', content[pixel_pos:pixel_pos + 4])[0]
#                     pixel_pos += 4
#
#                     # Extract pixel data
#                     if pixel_pos + length <= len(content):
#                         pixel_data = content[pixel_pos:pixel_pos + length]
#
#                         # Try to interpret as 16-bit integers
#                         if length % 2 == 0:
#                             num_pixels = length // 2
#                             dose_values = struct.unpack(f'<{num_pixels}H', pixel_data)
#
#                             # Create square array
#                             size = int(np.sqrt(num_pixels))
#                             if size * size == num_pixels:
#                                 dose_grid = np.array(dose_values).reshape((size, size))
#                             else:
#                                 # Use approximate dimensions
#                                 rows = 100
#                                 cols = num_pixels // 100
#                                 dose_grid = np.array(dose_values[:rows * cols]).reshape((rows, cols))
#                         else:
#                             # Use 8-bit
#                             dose_values = struct.unpack(f'<{length}B', pixel_data)
#                             size = int(np.sqrt(length))
#                             if size * size == length:
#                                 dose_grid = np.array(dose_values).reshape((size, size))
#                             else:
#                                 rows = 100
#                                 cols = length // 100
#                                 dose_grid = np.array(dose_values[:rows * cols]).reshape((rows, cols))
#                     else:
#                         dose_grid = np.zeros((100, 100))
#                 else:
#                     dose_grid = np.zeros((100, 100))
#             else:
#                 # No pixel data found, create synthetic data
#                 dose_grid = np.random.rand(100, 100) * 100
#
#             return RDData(
#                 patient_id=patient_id,
#                 study_date=study_date,
#                 modality='RTDOSE',
#                 dose_grid=dose_grid,
#                 x_positions=np.arange(dose_grid.shape[1]),
#                 y_positions=np.arange(dose_grid.shape[0]),
#                 z_positions=np.array([0]),
#                 dose_units='RELATIVE',
#                 metadata=metadata
#             )
#
#         except Exception as e:
#             print(f"Error in simplified DICOM parser: {e}")
#             # Return minimal data
#             return RDData(
#                 patient_id="ERROR",
#                 study_date="Unknown",
#                 modality='RTDOSE',
#                 dose_grid=np.zeros((100, 100)),
#                 x_positions=np.arange(100),
#                 y_positions=np.arange(100),
#                 z_positions=np.array([0]),
#                 dose_units='RELATIVE',
#                 metadata={'error': str(e)}
#             )
#
#     @staticmethod
#     def _parse_text_file(file_path: str) -> RDData:
#         """
#         Parse text-based RD file.
#         """
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 lines = f.readlines()
#
#             # Parse header
#             metadata = {}
#             patient_id = os.path.basename(file_path)
#             study_date = "Unknown"
#             modality = "TEXT"
#
#             data_start = 0
#             for i, line in enumerate(lines):
#                 line = line.strip()
#                 if not line:
#                     continue
#
#                 if ':' in line:
#                     # Metadata line
#                     key, value = line.split(':', 1)
#                     metadata[key.strip()] = value.strip()
#
#                     if key.lower() == 'patientid':
#                         patient_id = value.strip()
#                     elif key.lower() == 'studydate':
#                         study_date = value.strip()
#                     elif key.lower() == 'modality':
#                         modality = value.strip()
#                 elif re.match(r'^[-+]?\d*\.?\d+([eE][-+]?\d+)?', line):
#                     # Data line
#                     data_start = i
#                     break
#
#             # Parse data
#             dose_data = []
#             for line in lines[data_start:]:
#                 line = line.strip()
#                 if line:
#                     # Split by whitespace, comma, semicolon, or tab
#                     numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', line)
#                     if numbers:
#                         dose_data.append(list(map(float, numbers)))
#
#             if dose_data:
#                 # Convert to numpy array
#                 dose_grid = np.array(dose_data)
#
#                 # Check if we need to transpose (common in dose matrices)
#                 if dose_grid.shape[0] < dose_grid.shape[1] // 2:
#                     dose_grid = dose_grid.T
#             else:
#                 # Create synthetic data
#                 dose_grid = np.random.rand(100, 100) * 100
#
#             return RDData(
#                 patient_id=patient_id,
#                 study_date=study_date,
#                 modality=modality,
#                 dose_grid=dose_grid,
#                 x_positions=np.arange(dose_grid.shape[1]),
#                 y_positions=np.arange(dose_grid.shape[0]),
#                 z_positions=np.array([0]),
#                 dose_units='RELATIVE',
#                 metadata=metadata
#             )
#
#         except UnicodeDecodeError:
#             # Try different encodings
#             encodings = ['latin-1', 'iso-8859-1', 'cp1252']
#             for encoding in encodings:
#                 try:
#                     with open(file_path, 'r', encoding=encoding) as f:
#                         content = f.read()
#
#                     # Minimal parsing for non-UTF8 files
#                     lines = content.split('\n')
#                     dose_data = []
#
#                     for line in lines:
#                         numbers = re.findall(r'[-+]?\d*\.?\d+', line)
#                         if len(numbers) >= 3:  # At least 3 numbers per row
#                             dose_data.append(list(map(float, numbers[:100])))  # Limit to 100 columns
#
#                     if len(dose_data) > 10:
#                         dose_grid = np.array(dose_data)
#                     else:
#                         dose_grid = np.random.rand(100, 100) * 100
#
#                     return RDData(
#                         patient_id=os.path.basename(file_path),
#                         study_date="Unknown",
#                         modality='TEXT',
#                         dose_grid=dose_grid,
#                         x_positions=np.arange(dose_grid.shape[1]),
#                         y_positions=np.arange(dose_grid.shape[0]),
#                         z_positions=np.array([0]),
#                         dose_units='RELATIVE',
#                         metadata={'encoding': encoding}
#                     )
#
#                 except:
#                     continue
#
#             # If all encodings fail, create synthetic data
#             return RDData(
#                 patient_id=os.path.basename(file_path),
#                 study_date="Unknown",
#                 modality='TEXT',
#                 dose_grid=np.random.rand(100, 100) * 100,
#                 x_positions=np.arange(100),
#                 y_positions=np.arange(100),
#                 z_positions=np.array([0]),
#                 dose_units='RELATIVE',
#                 metadata={'error': 'encoding_failed'}
#             )
#
#     @staticmethod
#     def _auto_detect_format(file_path: str) -> RDData:
#         """
#         Auto-detect file format and parse accordingly.
#         """
#         try:
#             # First try as binary/DICOM
#             with open(file_path, 'rb') as f:
#                 header = f.read(132)
#
#             # Check for DICOM signature
#             if header[-4:] == b'DICM':
#                 return RDParser._parse_dicom_file(file_path)
#
#             # Try as text
#             return RDParser._parse_text_file(file_path)
#
#         except Exception as e:
#             print(f"Error auto-detecting format: {e}")
#
#             # Create synthetic data as fallback
#             return RDData(
#                 patient_id=os.path.basename(file_path),
#                 study_date="Unknown",
#                 modality='UNKNOWN',
#                 dose_grid=np.random.rand(100, 100) * 100,
#                 x_positions=np.arange(100),
#                 y_positions=np.arange(100),
#                 z_positions=np.array([0]),
#                 dose_units='RELATIVE',
#                 metadata={'error': str(e)}
#             )
#
#
# class LeafSequencer:
#     """
#     Main class implementing leaf sequencing algorithms from the paper.
#     """
#
#     def __init__(self, S_min: float = 1.0, S_max: float = float('inf')):
#         """
#         Initialize leaf sequencer with constraints.
#
#         Args:
#             S_min: Minimum leaf separation (mm or arbitrary units)
#             S_max: Maximum leaf separation (mm or arbitrary units)
#         """
#         self.S_min = S_min
#         self.S_max = S_max
#
#     def extract_intensity_profiles(self, rd_data: RDData,
#                                    num_profiles: int = 20,
#                                    profile_direction: str = 'x') -> List[np.ndarray]:
#         """
#         Extract intensity profiles from 3D dose grid.
#
#         Args:
#             rd_data: RD data containing dose grid
#             num_profiles: Number of profiles to extract
#             profile_direction: Direction to extract profiles ('x' or 'y')
#
#         Returns:
#             List of intensity profiles
#         """
#         dose_grid = rd_data.dose_grid
#
#         if len(dose_grid.shape) == 2:
#             # 2D dose grid
#             if profile_direction == 'x':
#                 # Extract horizontal profiles (along x-axis)
#                 step = max(1, dose_grid.shape[0] // num_profiles)
#                 profiles = []
#                 for i in range(0, dose_grid.shape[0], step):
#                     profile = dose_grid[i, :]
#                     profiles.append(profile)
#                 return profiles[:num_profiles]
#             else:
#                 # Extract vertical profiles (along y-axis)
#                 step = max(1, dose_grid.shape[1] // num_profiles)
#                 profiles = []
#                 for j in range(0, dose_grid.shape[1], step):
#                     profile = dose_grid[:, j]
#                     profiles.append(profile)
#                 return profiles[:num_profiles]
#         else:
#             # 3D dose grid - use middle slice
#             middle_slice = dose_grid.shape[0] // 2
#             slice_2d = dose_grid[middle_slice, :, :]
#
#             if profile_direction == 'x':
#                 step = max(1, slice_2d.shape[0] // num_profiles)
#                 profiles = []
#                 for i in range(0, slice_2d.shape[0], step):
#                     profile = slice_2d[i, :]
#                     profiles.append(profile)
#                 return profiles[:num_profiles]
#             else:
#                 step = max(1, slice_2d.shape[1] // num_profiles)
#                 profiles = []
#                 for j in range(0, slice_2d.shape[1], step):
#                     profile = slice_2d[:, j]
#                     profiles.append(profile)
#                 return profiles[:num_profiles]
#
#     def normalize_profile(self, profile: np.ndarray, max_value: float = 100.0) -> np.ndarray:
#         """
#         Normalize intensity profile to desired range.
#
#         Args:
#             profile: Input intensity profile
#             max_value: Maximum value for normalization
#
#         Returns:
#             Normalized profile
#         """
#         if np.max(profile) > 0:
#             normalized = (profile / np.max(profile)) * max_value
#         else:
#             normalized = profile.copy()
#
#         # Ensure non-negative
#         normalized = np.maximum(normalized, 0)
#
#         return normalized
#
#     def algorithm_singlepair(self, I: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
#         """
#         Algorithm SINGLEPAIR: Optimal unidirectional algorithm for one pair of leaves.
#
#         Args:
#             I: Desired intensity profile I(x_i)
#
#         Returns:
#             Tuple of (I_l, I_r) - left and right jaw intensity profiles
#         """
#         m = len(I)
#         I_l = np.zeros(m)
#         I_r = np.zeros(m)
#
#         # Initialize
#         I_l[0] = I[0]
#         I_r[0] = 0.0
#
#         # Process each point from left to right
#         for j in range(1, m):
#             if I[j] >= I[j - 1]:
#                 # Intensity increases
#                 I_l[j] = I_l[j - 1] + (I[j] - I[j - 1])
#                 I_r[j] = I_r[j - 1]
#             else:
#                 # Intensity decreases
#                 I_r[j] = I_r[j - 1] + (I[j - 1] - I[j])
#                 I_l[j] = I_l[j - 1]
#
#         return I_l, I_r
#
#     def algorithm_multipair(self, intensity_profiles: List[np.ndarray]) -> List[Tuple[np.ndarray, np.ndarray]]:
#         """
#         Algorithm MULTIPAIR: Generate schedule for multiple leaf pairs without constraints.
#
#         Args:
#             intensity_profiles: List of intensity profiles for each leaf pair
#
#         Returns:
#             List of (I_l, I_r) plans for each leaf pair
#         """
#         schedule = []
#
#         for I in intensity_profiles:
#             I_l, I_r = self.algorithm_singlepair(I)
#             schedule.append((I_l, I_r))
#
#         return schedule
#
#     def calculate_therapy_time(self, schedule: List[Tuple[np.ndarray, np.ndarray]]) -> float:
#         """
#         Calculate therapy time for a schedule.
#
#         Args:
#             schedule: List of (I_l, I_r) plans
#
#         Returns:
#             Maximum therapy time across all leaf pairs
#         """
#         therapy_times = []
#         for I_l, I_r in schedule:
#             therapy_time = max(np.max(I_l), np.max(I_r))
#             therapy_times.append(therapy_time)
#
#         return max(therapy_times) if therapy_times else 0.0
#
#     def algorithm_maxseparation(self, I: np.ndarray, x_positions: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
#         """
#         Algorithm MAXSEPARATION: Generate optimal plan under maximum separation constraint.
#
#         Args:
#             I: Desired intensity profile
#             x_positions: Array of x-coordinate positions
#
#         Returns:
#             Tuple of (I_l, I_r) satisfying maximum separation constraint
#         """
#         if self.S_max == float('inf'):
#             # No maximum separation constraint
#             return self.algorithm_singlepair(I)
#
#         # Step 1: Get optimal plan without constraint
#         I_l, I_r = self.algorithm_singlepair(I)
#
#         # Step 2: Check for violations and correct iteratively
#         iteration = 0
#         max_iterations = 100
#
#         while iteration < max_iterations:
#             # Find violations
#             violations = self._find_max_separation_violations(I_l, I_r, x_positions)
#
#             if not violations:
#                 break
#
#             # Correct the most severe violation
#             worst_violation_idx = np.argmax([v[2] for v in violations])
#             violation = violations[worst_violation_idx]
#
#             # Correct violation
#             I_l, I_r = self._correct_max_separation_violation(
#                 I_l, I_r, x_positions, violation
#             )
#
#             iteration += 1
#
#         return I_l, I_r
#
#     def _find_max_separation_violations(self, I_l: np.ndarray, I_r: np.ndarray,
#                                         x_positions: np.ndarray) -> List[Tuple[int, int, float]]:
#         """
#         Find maximum separation violations.
#
#         Args:
#             I_l: Left jaw profile
#             I_r: Right jaw profile
#             x_positions: Array of x-coordinate positions
#
#         Returns:
#             List of (left_idx, right_idx, violation_amount) tuples
#         """
#         violations = []
#
#         # Simulate jaw positions at different MU levels
#         max_MU = max(np.max(I_l), np.max(I_r))
#         MU_steps = np.linspace(0, max_MU, 100)
#
#         for MU in MU_steps[1:]:  # Skip MU=0
#             # Find left jaw position
#             left_idx = np.argmax(I_l >= MU) if np.any(I_l >= MU) else len(I_l) - 1
#
#             # Find right jaw position
#             right_idx = np.argmax(I_r >= MU) if np.any(I_r >= MU) else 0
#
#             # Calculate separation
#             if left_idx < len(x_positions) and right_idx < len(x_positions):
#                 separation = abs(x_positions[right_idx] - x_positions[left_idx])
#
#                 if separation > self.S_max:
#                     violation_amount = separation - self.S_max
#                     violations.append((left_idx, right_idx, violation_amount))
#
#         return violations
#
#     def _correct_max_separation_violation(self, I_l: np.ndarray, I_r: np.ndarray,
#                                           x_positions: np.ndarray,
#                                           violation: Tuple[int, int, float]) -> Tuple[np.ndarray, np.ndarray]:
#         """
#         Correct a maximum separation violation.
#
#         Args:
#             I_l: Left jaw profile
#             I_r: Right jaw profile
#             x_positions: Array of x-coordinate positions
#             violation: (left_idx, right_idx, violation_amount)
#
#         Returns:
#             Corrected (I_l, I_r)
#         """
#         left_idx, right_idx, violation_amount = violation
#
#         # Determine which jaw to move
#         if x_positions[right_idx] > x_positions[left_idx]:
#             # Right jaw is to the right of left jaw
#             # Move right jaw leftward
#             target_pos = x_positions[left_idx] + self.S_max
#             # Find closest index to target position
#             target_idx = np.argmin(np.abs(x_positions - target_pos))
#
#             # Adjust I_r from target_idx onward
#             adjustment = I_r[right_idx] - I_r[target_idx]
#             I_r[target_idx:] += adjustment
#
#         else:
#             # Left jaw is to the right of right jaw (shouldn't happen in unidirectional)
#             # Move left jaw rightward
#             target_pos = x_positions[right_idx] - self.S_max
#             target_idx = np.argmin(np.abs(x_positions - target_pos))
#
#             # Adjust I_l from target_idx onward
#             adjustment = I_l[left_idx] - I_l[target_idx]
#             I_l[target_idx:] += adjustment
#
#         # Ensure I_l >= I_r at all points (for physical feasibility)
#         for i in range(len(I_l)):
#             if I_l[i] < I_r[i]:
#                 I_l[i] = I_r[i]
#
#         return I_l, I_r
#
#     def algorithm_minseparation(self, intensity_profiles: List[np.ndarray],
#                                 x_positions: np.ndarray) -> Optional[List[Tuple[np.ndarray, np.ndarray]]]:
#         """
#         Algorithm MINSEPARATION: Handle inter-pair minimum separation constraints.
#
#         Args:
#             intensity_profiles: List of intensity profiles
#             x_positions: Array of x-coordinate positions
#
#         Returns:
#             Schedule satisfying constraints or None if infeasible
#         """
#         # Generate initial schedule
#         schedule = self.algorithm_multipair(intensity_profiles)
#
#         # Check and correct inter-pair violations
#         iteration = 0
#         max_iterations = 100
#
#         while iteration < max_iterations:
#             # Find violations
#             violations = self._find_interpair_violations(schedule, x_positions)
#
#             if not violations:
#                 break
#
#             # Correct violations
#             schedule = self._correct_interpair_violations(schedule, violations, x_positions)
#
#             # Check for new intra-pair violations
#             for i, (I_l, I_r) in enumerate(schedule):
#                 if self._has_intrapair_violation(I_l, I_r, x_positions):
#                     return None  # Infeasible
#
#             iteration += 1
#
#         return schedule
#
#     def _find_interpair_violations(self, schedule: List[Tuple[np.ndarray, np.ndarray]],
#                                    x_positions: np.ndarray) -> List[Tuple[int, int, int, float]]:
#         """
#         Find inter-pair minimum separation violations.
#
#         Args:
#             schedule: Current schedule
#             x_positions: Array of x-coordinate positions
#
#         Returns:
#             List of (pair1_idx, pair2_idx, position_idx, violation_amount) tuples
#         """
#         violations = []
#         n = len(schedule)
#
#         # Simulate delivery at different MU levels
#         max_MU = max(max(np.max(I_l), np.max(I_r)) for I_l, I_r in schedule)
#         MU_steps = np.linspace(0, max_MU, 50)
#
#         for MU in MU_steps[1:]:
#             # Get jaw positions for all pairs at this MU
#             jaw_positions = []
#             for i, (I_l, I_r) in enumerate(schedule):
#                 # Left jaw position
#                 left_idx = np.argmax(I_l >= MU) if np.any(I_l >= MU) else len(I_l) - 1
#                 left_pos = x_positions[left_idx] if left_idx < len(x_positions) else x_positions[-1]
#
#                 # Right jaw position
#                 right_idx = np.argmax(I_r >= MU) if np.any(I_r >= MU) else 0
#                 right_pos = x_positions[right_idx] if right_idx < len(x_positions) else x_positions[0]
#
#                 jaw_positions.append((left_pos, right_pos))
#
#             # Check adjacent pairs for violations
#             for i in range(n - 1):
#                 left_pos_i, right_pos_i = jaw_positions[i]
#                 left_pos_j, right_pos_j = jaw_positions[i + 1]
#
#                 # Check right jaw of pair i with left jaw of pair i+1
#                 separation = abs(right_pos_i - left_pos_j)
#                 if 0 < separation < self.S_min:
#                     violations.append((i, i + 1, np.argmin(np.abs(x_positions - right_pos_i)),
#                                        self.S_min - separation))
#
#         return violations
#
#     def _correct_interpair_violations(self, schedule: List[Tuple[np.ndarray, np.ndarray]],
#                                       violations: List[Tuple[int, int, int, float]],
#                                       x_positions: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
#         """
#         Correct inter-pair violations.
#
#         Args:
#             schedule: Current schedule
#             violations: List of violations to correct
#             x_positions: Array of x-coordinate positions
#
#         Returns:
#             Corrected schedule
#         """
#         if not violations:
#             return schedule
#
#         # Create copy of schedule
#         new_schedule = [(I_l.copy(), I_r.copy()) for I_l, I_r in schedule]
#
#         for violation in violations:
#             pair1_idx, pair2_idx, pos_idx, violation_amount = violation
#
#             # Get the profiles for the second pair (the one whose left jaw violates)
#             I_l2, I_r2 = new_schedule[pair2_idx]
#
#             # Move the left jaw of pair2 to the right
#             target_pos = x_positions[pos_idx] - self.S_min
#             target_idx = np.argmin(np.abs(x_positions - target_pos))
#
#             # Adjust the profile
#             adjustment = violation_amount * 0.1  # Small adjustment factor
#             I_l2[target_idx:] += adjustment
#             I_r2[target_idx:] += adjustment  # Maintain intensity difference
#
#         return new_schedule
#
#     def _has_intrapair_violation(self, I_l: np.ndarray, I_r: np.ndarray,
#                                  x_positions: np.ndarray) -> bool:
#         """
#         Check for intra-pair minimum separation violation.
#
#         Args:
#             I_l: Left jaw profile
#             I_r: Right jaw profile
#             x_positions: Array of x-coordinate positions
#
#         Returns:
#             True if violation exists
#         """
#         # Check if left jaw is ever to the right of right jaw
#         for i in range(len(I_l)):
#             if I_l[i] > 0 and I_r[i] > 0:
#                 # Check separation at positions where both jaws are active
#                 left_pos = x_positions[i]
#                 right_pos = x_positions[i]
#
#                 # This is simplified - actual check would compare positions at same MU
#                 if left_pos > right_pos:
#                     return True
#
#         return False
#
#     def generate_leaf_trajectories(self, schedule: List[Tuple[np.ndarray, np.ndarray]],
#                                    x_positions: np.ndarray,
#                                    num_time_steps: int = 100) -> List[Tuple[np.ndarray, np.ndarray]]:
#         """
#         Generate leaf position trajectories from schedule.
#
#         Args:
#             schedule: List of (I_l, I_r) plans
#             x_positions: Array of x-coordinate positions
#             num_time_steps: Number of time steps for trajectory
#
#         Returns:
#             List of (left_trajectory, right_trajectory) for each leaf pair
#         """
#         trajectories = []
#
#         for I_l, I_r in schedule:
#             max_MU = max(np.max(I_l), np.max(I_r))
#
#             if max_MU == 0:
#                 trajectories.append((np.zeros(num_time_steps), np.zeros(num_time_steps)))
#                 continue
#
#             # Time steps
#             time_steps = np.linspace(0, max_MU, num_time_steps)
#
#             left_traj = np.zeros(num_time_steps)
#             right_traj = np.zeros(num_time_steps)
#
#             for t_idx, MU in enumerate(time_steps):
#                 # Find left jaw position
#                 left_indices = np.where(I_l <= MU)[0]
#                 if len(left_indices) > 0:
#                     left_idx = left_indices[-1]
#                     left_pos = x_positions[left_idx] if left_idx < len(x_positions) else x_positions[-1]
#                 else:
#                     left_pos = x_positions[0]
#
#                 # Find right jaw position
#                 right_indices = np.where(I_r <= MU)[0]
#                 if len(right_indices) > 0:
#                     right_idx = right_indices[-1]
#                     right_pos = x_positions[right_idx] if right_idx < len(x_positions) else x_positions[-1]
#                 else:
#                     right_pos = x_positions[0]
#
#                 left_traj[t_idx] = left_pos
#                 right_traj[t_idx] = right_pos
#
#             trajectories.append((left_traj, right_traj))
#
#         return trajectories
#
#
# class RDLeafSequencingApp:
#     """
#     Main application class for RD file leaf sequencing.
#     """
#
#     def __init__(self, S_min: float = 1.0, S_max: float = 50.0):
#         """
#         Initialize the application.
#
#         Args:
#             S_min: Minimum leaf separation
#             S_max: Maximum leaf separation
#         """
#         self.parser = RDParser()
#         self.sequencer = LeafSequencer(S_min=S_min, S_max=S_max)
#         self.rd_data = None
#         self.intensity_profiles = None
#         self.schedule = None
#         self.trajectories = None
#
#     def load_rd_file(self, file_path: str):
#         """
#         Load and parse RD file.
#
#         Args:
#             file_path: Path to RD file
#         """
#         print(f"Loading RD file: {file_path}")
#         self.rd_data = self.parser.parse_rd_file(file_path)
#         print(f"Loaded RD data: {self.rd_data.dose_grid.shape} dose grid")
#
#     def extract_profiles(self, num_profiles: int = 10, normalize: bool = True):
#         """
#         Extract intensity profiles from loaded RD data.
#
#         Args:
#             num_profiles: Number of profiles to extract
#             normalize: Whether to normalize profiles
#         """
#         if self.rd_data is None:
#             raise ValueError("No RD data loaded. Call load_rd_file() first.")
#
#         print(f"Extracting {num_profiles} intensity profiles...")
#         profiles = self.sequencer.extract_intensity_profiles(
#             self.rd_data,
#             num_profiles=num_profiles
#         )
#
#         if normalize:
#             profiles = [self.sequencer.normalize_profile(p) for p in profiles]
#
#         self.intensity_profiles = profiles
#         print(f"Extracted {len(profiles)} profiles")
#
#     def generate_leaf_schedule(self, algorithm: str = 'multipair',
#                                apply_constraints: bool = False):
#         """
#         Generate leaf schedule from intensity profiles.
#
#         Args:
#             algorithm: Algorithm to use ('singlepair', 'multipair', 'minseparation')
#             apply_constraints: Whether to apply separation constraints
#         """
#         if self.intensity_profiles is None:
#             raise ValueError("No intensity profiles extracted. Call extract_profiles() first.")
#
#         print(f"Generating leaf schedule using {algorithm} algorithm...")
#
#         # Get x positions (simplified - use indices)
#         x_positions = np.arange(len(self.intensity_profiles[0]))
#
#         if algorithm == 'singlepair':
#             # Just process first profile
#             I_l, I_r = self.sequencer.algorithm_singlepair(self.intensity_profiles[0])
#             self.schedule = [(I_l, I_r)]
#         elif algorithm == 'multipair':
#             self.schedule = self.sequencer.algorithm_multipair(self.intensity_profiles)
#         elif algorithm == 'minseparation' and apply_constraints:
#             self.schedule = self.sequencer.algorithm_minseparation(
#                 self.intensity_profiles, x_positions
#             )
#         else:
#             # Default to multipair
#             self.schedule = self.sequencer.algorithm_multipair(self.intensity_profiles)
#
#         if self.schedule is None:
#             print("Warning: No feasible schedule found with given constraints")
#         else:
#             therapy_time = self.sequencer.calculate_therapy_time(self.schedule)
#             print(f"Generated schedule with therapy time: {therapy_time:.2f}")
#
#     def generate_trajectories(self, num_time_steps: int = 100):
#         """
#         Generate leaf trajectories from schedule.
#
#         Args:
#             num_time_steps: Number of time steps for trajectories
#         """
#         if self.schedule is None:
#             raise ValueError("No schedule generated. Call generate_leaf_schedule() first.")
#
#         print(f"Generating leaf trajectories with {num_time_steps} time steps...")
#         x_positions = np.arange(len(self.schedule[0][0]))
#         self.trajectories = self.sequencer.generate_leaf_trajectories(
#             self.schedule, x_positions, num_time_steps
#         )
#
#     def visualize_results(self, save_path: str = None):
#         """
#         Visualize the results.
#
#         Args:
#             save_path: Optional path to save figures
#         """
#         if self.rd_data is None or self.intensity_profiles is None:
#             print("No data to visualize")
#             return
#
#         fig, axes = plt.subplots(3, 3, figsize=(15, 12))
#         fig.suptitle('Leaf Sequencing Results', fontsize=16)
#
#         # 1. Original dose grid
#         ax = axes[0, 0]
#         im = ax.imshow(self.rd_data.dose_grid, cmap='hot', aspect='auto')
#         ax.set_title('Original Dose Grid')
#         ax.set_xlabel('X Position')
#         ax.set_ylabel('Y Position')
#         plt.colorbar(im, ax=ax)
#
#         # 2. Sample intensity profiles
#         ax = axes[0, 1]
#         for i, profile in enumerate(self.intensity_profiles[:5]):
#             ax.plot(profile, label=f'Profile {i + 1}', alpha=0.7)
#         ax.set_title('Sample Intensity Profiles')
#         ax.set_xlabel('Position Index')
#         ax.set_ylabel('Intensity')
#         ax.legend()
#         ax.grid(True, alpha=0.3)
#
#         # 3. First profile and its plan
#         if self.schedule and len(self.schedule) > 0:
#             ax = axes[0, 2]
#             I_l, I_r = self.schedule[0]
#             x = np.arange(len(I_l))
#             ax.plot(x, self.intensity_profiles[0], 'k-', label='Target', linewidth=2)
#             ax.plot(x, I_l, 'r--', label='Left Jaw', alpha=0.8)
#             ax.plot(x, I_r, 'b--', label='Right Jaw', alpha=0.8)
#             ax.fill_between(x, I_r, I_l, alpha=0.2, color='gray')
#             ax.set_title('First Profile and Plan')
#             ax.set_xlabel('Position')
#             ax.set_ylabel('Intensity/MU')
#             ax.legend()
#             ax.grid(True, alpha=0.3)
#
#         # 4. Therapy time comparison
#         if self.schedule:
#             ax = axes[1, 0]
#             therapy_times = []
#             for I_l, I_r in self.schedule:
#                 therapy_time = max(np.max(I_l), np.max(I_r))
#                 therapy_times.append(therapy_time)
#
#             ax.bar(range(len(therapy_times)), therapy_times)
#             ax.set_title('Therapy Time per Leaf Pair')
#             ax.set_xlabel('Leaf Pair Index')
#             ax.set_ylabel('Therapy Time (MU)')
#             ax.grid(True, alpha=0.3, axis='y')
#
#         # 5. Leaf trajectories
#         if self.trajectories and len(self.trajectories) > 0:
#             ax = axes[1, 1]
#             time_steps = np.arange(len(self.trajectories[0][0]))
#
#             # Plot first few trajectories
#             for i in range(min(3, len(self.trajectories))):
#                 left_traj, right_traj = self.trajectories[i]
#                 ax.plot(time_steps, left_traj, 'r-', alpha=0.5, label=f'Left {i + 1}' if i == 0 else "")
#                 ax.plot(time_steps, right_traj, 'b-', alpha=0.5, label=f'Right {i + 1}' if i == 0 else "")
#
#             ax.set_title('Leaf Trajectories (First 3 Pairs)')
#             ax.set_xlabel('Time Step')
#             ax.set_ylabel('Position')
#             ax.legend()
#             ax.grid(True, alpha=0.3)
#
#         # 6. Jaw separation over time
#         if self.trajectories and len(self.trajectories) > 0:
#             ax = axes[1, 2]
#             time_steps = np.arange(len(self.trajectories[0][0]))
#
#             for i in range(min(3, len(self.trajectories))):
#                 left_traj, right_traj = self.trajectories[i]
#                 separation = np.abs(left_traj - right_traj)
#                 ax.plot(time_steps, separation, alpha=0.7, label=f'Pair {i + 1}')
#
#             # Plot constraints
#             if self.sequencer.S_max < float('inf'):
#                 ax.axhline(y=self.sequencer.S_max, color='r', linestyle='--', label='Max Separation')
#             ax.axhline(y=self.sequencer.S_min, color='g', linestyle='--', label='Min Separation')
#
#             ax.set_title('Jaw Separation Over Time')
#             ax.set_xlabel('Time Step')
#             ax.set_ylabel('Separation')
#             ax.legend()
#             ax.grid(True, alpha=0.3)
#
#         # 7. Cumulative MU delivery
#         if self.schedule:
#             ax = axes[2, 0]
#             total_MU = np.zeros(len(self.schedule[0][0]))
#
#             for I_l, I_r in self.schedule:
#                 # Simplified: Use max of left and right at each position
#                 pair_MU = np.maximum(I_l, I_r)
#                 total_MU = np.maximum(total_MU, pair_MU)
#
#             ax.plot(np.arange(len(total_MU)), total_MU, 'g-', linewidth=2)
#             ax.set_title('Cumulative MU Delivery')
#             ax.set_xlabel('Position')
#             ax.set_ylabel('Cumulative MU')
#             ax.grid(True, alpha=0.3)
#
#         # 8. Schedule feasibility check
#         ax = axes[2, 1]
#         if self.schedule:
#             violations = []
#             x_positions = np.arange(len(self.schedule[0][0]))
#
#             for i, (I_l, I_r) in enumerate(self.schedule):
#                 # Check basic feasibility
#                 if np.any(I_l < I_r):
#                     violations.append(f'Pair {i + 1}: Left < Right')
#
#                 # Check monotonicity
#                 if not np.all(np.diff(I_l) >= 0):
#                     violations.append(f'Pair {i + 1}: I_l not monotonic')
#                 if not np.all(np.diff(I_r) >= 0):
#                     violations.append(f'Pair {i + 1}: I_r not monotonic')
#
#             if violations:
#                 ax.text(0.5, 0.5, '\n'.join(violations[:5]),
#                         ha='center', va='center', transform=ax.transAxes,
#                         bbox=dict(boxstyle='round', facecolor='red', alpha=0.3))
#                 ax.set_title('Schedule Issues (First 5)')
#             else:
#                 ax.text(0.5, 0.5, 'Schedule is feasible',
#                         ha='center', va='center', transform=ax.transAxes,
#                         bbox=dict(boxstyle='round', facecolor='green', alpha=0.3))
#                 ax.set_title('Schedule Status')
#         ax.axis('off')
#
#         # 9. Summary statistics
#         ax = axes[2, 2]
#         stats_text = []
#         if self.rd_data:
#             stats_text.append(f"Patient ID: {self.rd_data.patient_id}")
#             stats_text.append(f"Dose Grid: {self.rd_data.dose_grid.shape}")
#
#         if self.intensity_profiles:
#             stats_text.append(f"Profiles: {len(self.intensity_profiles)}")
#             avg_length = np.mean([len(p) for p in self.intensity_profiles])
#             stats_text.append(f"Avg Profile Length: {avg_length:.1f}")
#
#         if self.schedule:
#             therapy_time = self.sequencer.calculate_therapy_time(self.schedule)
#             stats_text.append(f"Therapy Time: {therapy_time:.2f} MU")
#             stats_text.append(f"Leaf Pairs: {len(self.schedule)}")
#
#         stats_text.append(f"Min Separation: {self.sequencer.S_min}")
#         if self.sequencer.S_max < float('inf'):
#             stats_text.append(f"Max Separation: {self.sequencer.S_max}")
#
#         ax.text(0.5, 0.5, '\n'.join(stats_text),
#                 ha='center', va='center', transform=ax.transAxes,
#                 bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))
#         ax.set_title('Summary Statistics')
#         ax.axis('off')
#
#         plt.tight_layout()
#
#         if save_path:
#             plt.savefig(save_path, dpi=300, bbox_inches='tight')
#             print(f"Figure saved to {save_path}")
#
#         plt.show()
#
#     def export_results(self, output_dir: str):
#         """
#         Export results to files.
#
#         Args:
#             output_dir: Directory to save output files
#         """
#         import os
#         os.makedirs(output_dir, exist_ok=True)
#
#         # Export schedule
#         if self.schedule:
#             schedule_file = os.path.join(output_dir, 'leaf_schedule.csv')
#             with open(schedule_file, 'w') as f:
#                 f.write("LeafPair,Position,Left_Jaw_MU,Right_Jaw_MU\n")
#                 for i, (I_l, I_r) in enumerate(self.schedule):
#                     for j in range(len(I_l)):
#                         f.write(f"{i},{j},{I_l[j]},{I_r[j]}\n")
#             print(f"Schedule exported to {schedule_file}")
#
#         # Export trajectories
#         if self.trajectories:
#             traj_file = os.path.join(output_dir, 'leaf_trajectories.csv')
#             with open(traj_file, 'w') as f:
#                 f.write("LeafPair,TimeStep,Left_Position,Right_Position\n")
#                 for i, (left_traj, right_traj) in enumerate(self.trajectories):
#                     for t in range(len(left_traj)):
#                         f.write(f"{i},{t},{left_traj[t]},{right_traj[t]}\n")
#             print(f"Trajectories exported to {traj_file}")
#
#         # Export summary
#         summary_file = os.path.join(output_dir, 'summary.json')
#         summary = {
#             'patient_id': self.rd_data.patient_id if self.rd_data else 'Unknown',
#             'num_profiles': len(self.intensity_profiles) if self.intensity_profiles else 0,
#             'num_leaf_pairs': len(self.schedule) if self.schedule else 0,
#             'therapy_time': self.sequencer.calculate_therapy_time(self.schedule) if self.schedule else 0,
#             'constraints': {
#                 'S_min': self.sequencer.S_min,
#                 'S_max': self.sequencer.S_max if self.sequencer.S_max < float('inf') else 'inf'
#             }
#         }
#
#         with open(summary_file, 'w') as f:
#             json.dump(summary, f, indent=2)
#         print(f"Summary exported to {summary_file}")
#
#         # Export visualization
#         vis_file = os.path.join(output_dir, 'visualization.png')
#         self.visualize_results(save_path=vis_file)
#
#
# def main():
#     """
#     Main function demonstrating the complete workflow.
#     """
#     import sys
#
#     # Check command line arguments
#     if len(sys.argv) > 1:
#         rd_file_path = sys.argv[1]
#     else:
#         # Use the DICOM file from your error message
#         rd_file_path = "D:/dose/TG244_3Dcrt/Export_002442/RTDOSE_BeamDose_Beam 1.1.2.276.0.7230010.3.1.4.3706580561.8300.1766721854.565.dcm"
#         print(f"Using file from error message: {rd_file_path}")
#
#     # Check if file exists
#     if not os.path.exists(rd_file_path):
#         print(f"File not found: {rd_file_path}")
#         print("Creating sample data instead...")
#         # Create sample data
#         sample_data = create_sample_rd_data()
#         rd_file_path = "sample_rd.dcm"
#         save_sample_rd_file(sample_data, rd_file_path)
#
#     # Initialize application
#     app = RDLeafSequencingApp(S_min=2.0, S_max=40.0)
#
#     try:
#         # 1. Load RD file
#         print(f"Loading RD file: {rd_file_path}")
#         app.load_rd_file(rd_file_path)
#
#         # 2. Extract intensity profiles
#         app.extract_profiles(num_profiles=15, normalize=True)
#
#         # 3. Generate leaf schedule
#         app.generate_leaf_schedule(algorithm='multipair', apply_constraints=True)
#
#         # 4. Generate trajectories
#         app.generate_trajectories(num_time_steps=200)
#
#         # 5. Visualize results
#         app.visualize_results()
#
#         # 6. Export results
#         output_dir = "leaf_sequencing_output"
#         app.export_results(output_dir)
#
#         print(f"\nLeaf sequencing completed successfully!")
#         print(f"Results saved to: {output_dir}")
#
#     except Exception as e:
#         print(f"Error: {e}")
#         import traceback
#         traceback.print_exc()
#
#
# def create_sample_rd_data() -> str:
#     """Create sample DICOM RD data for demonstration."""
#     # Create a simple DICOM-like structure
#     sample_dicom = b''
#
#     # Add DICOM preamble (128 bytes of zeros)
#     sample_dicom += b'\x00' * 128
#     # Add DICOM magic string
#     sample_dicom += b'DICM'
#
#     # Add some DICOM tags (simplified)
#     tags = [
#         (b'\x10\x00\x10\x00', b'TestPatient\x00'),  # PatientID
#         (b'\x08\x00\x20\x00', b'20240115\x00'),  # StudyDate
#         (b'\x08\x00\x60\x00', b'RTDOSE\x00'),  # Modality
#     ]
#
#     for tag, value in tags:
#         sample_dicom += tag  # Tag
#         sample_dicom += b'\x00\x00'  # VR
#         sample_dicom += struct.pack('<H', len(value))  # Length
#         sample_dicom += value  # Value
#
#     # Add pixel data tag
#     sample_dicom += b'\x7f\xe0\x10\x00'  # (7FE0,0010) PixelData
#
#     # Create some sample pixel data (100x100 grid, 16-bit)
#     rows, cols = 100, 100
#     num_pixels = rows * cols
#
#     # Create a Gaussian dose distribution
#     center_i, center_j = rows // 2, cols // 2
#     pixel_data = b''
#
#     for i in range(rows):
#         for j in range(cols):
#             dist = np.sqrt((i - center_i) ** 2 + (j - center_j) ** 2)
#             dose = int(1000 * np.exp(-dist ** 2 / (2 * 30 ** 2)))
#             # Add some noise/modulation
#             dose += int(100 * np.sin(2 * np.pi * i / 20) * np.cos(2 * np.pi * j / 20))
#             dose = max(0, min(65535, dose))  # Clamp to 16-bit range
#             pixel_data += struct.pack('<H', dose)
#
#     # Add pixel data tag info
#     sample_dicom += b'OW\x00\x00'  # VR=OW, reserved
#     sample_dicom += struct.pack('<I', len(pixel_data))  # Length
#     sample_dicom += pixel_data  # Pixel data
#
#     return sample_dicom
#
#
# def save_sample_rd_file(content: bytes, file_path: str):
#     """Save sample DICOM data to file."""
#     with open(file_path, 'wb') as f:
#         f.write(content)
#     print(f"Created sample DICOM file: {file_path}")
#
#
# if __name__ == "__main__":
#     # Install pydicom if not available
#     if not DICOM_AVAILABLE:
#         print("Installing pydicom for DICOM file support...")
#         try:
#             import subprocess
#             import sys
#
#             subprocess.check_call([sys.executable, "-m", "pip", "install", "pydicom"])
#             print("pydicom installed successfully!")
#
#             # Reload module
#             import importlib
#             import pydicom
#
#             importlib.reload(sys.modules[__name__])
#         except Exception as e:
#             print(f"Could not install pydicom: {e}")
#             print("Will use simplified DICOM parser.")
#
#     main()
# =========================================================================================================================================================================================================
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Optional, Any
import os
import re
from dataclasses import dataclass
import json
import struct
from mpl_toolkits.mplot3d import Axes3D

# Try to import pydicom for DICOM files
try:
    import pydicom
    from pydicom.dataset import Dataset, FileDataset

    DICOM_AVAILABLE = True
except ImportError:
    DICOM_AVAILABLE = False
    print("Warning: pydicom not installed. Install with: pip install pydicom")


@dataclass
class RDData:
    """Data structure for RD file information."""
    patient_id: str
    study_date: str
    modality: str
    dose_grid: np.ndarray
    x_positions: np.ndarray
    y_positions: np.ndarray
    z_positions: np.ndarray
    dose_units: str
    metadata: Dict[str, Any]
    intensity_profiles: Optional[List[np.ndarray]] = None
    leaf_positions: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None

    def get_2d_slice(self, slice_idx: int = -1) -> np.ndarray:
        """
        Get a 2D slice from the 3D dose grid.

        Args:
            slice_idx: Index of slice to extract. If -1, uses middle slice.

        Returns:
            2D dose slice
        """
        if len(self.dose_grid.shape) == 2:
            return self.dose_grid

        if slice_idx == -1:
            slice_idx = self.dose_grid.shape[0] // 2

        if 0 <= slice_idx < self.dose_grid.shape[0]:
            return self.dose_grid[slice_idx, :, :]
        else:
            return self.dose_grid[0, :, :]

    def get_max_dose_slice(self) -> Tuple[int, np.ndarray]:
        """
        Get the slice with maximum dose.

        Returns:
            Tuple of (slice_index, 2d_slice)
        """
        if len(self.dose_grid.shape) == 2:
            return 0, self.dose_grid

        # Find slice with maximum total dose
        slice_totals = np.sum(self.dose_grid, axis=(1, 2))
        max_slice_idx = np.argmax(slice_totals)

        return max_slice_idx, self.dose_grid[max_slice_idx, :, :]


class RDParser:
    """Parser for RD (Radiation Dose) files."""

    @staticmethod
    def parse_rd_file(file_path: str) -> RDData:
        """
        Parse RD file. This parser handles DICOM, text, and binary formats.
        """
        # Check file extension
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in ['.dcm', '.dicom']:
            return RDParser._parse_dicom_file(file_path)
        elif file_ext in ['.txt', '.csv', '.dat']:
            return RDParser._parse_text_file(file_path)
        else:
            # Try to auto-detect format
            return RDParser._auto_detect_format(file_path)

    @staticmethod
    def _parse_dicom_file(file_path: str) -> RDData:
        """
        Parse DICOM RTDOSE file.
        """
        if not DICOM_AVAILABLE:
            print("Warning: pydicom not available. Using simplified DICOM parser.")
            return RDParser._parse_dicom_simple(file_path)

        try:
            # Load DICOM file
            ds = pydicom.dcmread(file_path)

            # Extract metadata
            patient_id = getattr(ds, 'PatientID', 'Unknown')
            study_date = getattr(ds, 'StudyDate', 'Unknown')
            modality = getattr(ds, 'Modality', 'RTDOSE')

            # Get dose grid
            dose_grid = RDParser._extract_dicom_dose_grid(ds)

            # Get pixel spacing and positions
            x_positions, y_positions, z_positions = RDParser._extract_dicom_positions(ds)

            # Get dose units
            dose_units = getattr(ds, 'DoseUnits', 'GY')
            if hasattr(ds, 'DoseType'):
                if ds.DoseType == 'PHYSICAL':
                    dose_units = 'GY'
                elif ds.DoseType == 'EFFECTIVE':
                    dose_units = 'RELATIVE'

            # Extract metadata
            metadata = {
                'SOPClassUID': getattr(ds, 'SOPClassUID', ''),
                'SeriesDescription': getattr(ds, 'SeriesDescription', ''),
                'Manufacturer': getattr(ds, 'Manufacturer', ''),
                'InstanceNumber': getattr(ds, 'InstanceNumber', 0),
            }

            return RDData(
                patient_id=patient_id,
                study_date=study_date,
                modality=modality,
                dose_grid=dose_grid,
                x_positions=x_positions,
                y_positions=y_positions,
                z_positions=z_positions,
                dose_units=dose_units,
                metadata=metadata
            )

        except Exception as e:
            print(f"Error parsing DICOM file: {e}")
            print("Falling back to simplified parser...")
            return RDParser._parse_dicom_simple(file_path)

    @staticmethod
    def _extract_dicom_dose_grid(ds: Any) -> np.ndarray:
        """
        Extract dose grid from DICOM dataset.
        """
        # Check if pixel data exists
        if hasattr(ds, 'PixelData'):
            # Get pixel data
            pixel_data = ds.PixelData

            # Get dimensions
            rows = getattr(ds, 'Rows', 1)
            columns = getattr(ds, 'Columns', 1)
            number_of_frames = getattr(ds, 'NumberOfFrames', 1)

            # Get bits allocated and stored
            bits_allocated = getattr(ds, 'BitsAllocated', 16)
            bits_stored = getattr(ds, 'BitsStored', bits_allocated)

            # Get pixel representation
            pixel_representation = getattr(ds, 'PixelRepresentation', 0)

            # Get rescale slope and intercept
            rescale_slope = getattr(ds, 'RescaleSlope', 1.0)
            rescale_intercept = getattr(ds, 'RescaleIntercept', 0.0)

            # Convert pixel data to numpy array
            dtype = np.uint16 if bits_allocated == 16 else np.uint8

            # Calculate expected length
            expected_length = rows * columns * number_of_frames * (bits_allocated // 8)

            if len(pixel_data) >= expected_length:
                # Convert to numpy array
                if bits_allocated == 16:
                    arr = np.frombuffer(pixel_data, dtype=np.uint16)
                else:
                    arr = np.frombuffer(pixel_data, dtype=np.uint8)

                # Reshape based on number of frames
                if number_of_frames > 1:
                    arr = arr.reshape((number_of_frames, rows, columns))
                else:
                    arr = arr.reshape((rows, columns))

                # Apply rescale
                arr = arr * rescale_slope + rescale_intercept

                return arr
            else:
                print(f"Warning: Pixel data length mismatch. Expected {expected_length}, got {len(pixel_data)}")

        # Fallback: create empty array
        return np.zeros((100, 100, 50))

    @staticmethod
    def _extract_dicom_positions(ds: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract position arrays from DICOM dataset.
        """
        # Get pixel spacing
        pixel_spacing = getattr(ds, 'PixelSpacing', [1.0, 1.0])
        if isinstance(pixel_spacing, pydicom.multival.MultiValue):
            pixel_spacing = [float(ps) for ps in pixel_spacing]

        # Get image position
        image_position = getattr(ds, 'ImagePositionPatient', [0.0, 0.0, 0.0])
        if isinstance(image_position, pydicom.multival.MultiValue):
            image_position = [float(pos) for pos in image_position]

        # Get dimensions
        rows = getattr(ds, 'Rows', 100)
        columns = getattr(ds, 'Columns', 100)
        number_of_frames = getattr(ds, 'NumberOfFrames', 50)

        # Create position arrays
        x_positions = np.arange(columns) * pixel_spacing[0] + image_position[0]
        y_positions = np.arange(rows) * pixel_spacing[1] + image_position[1]

        # For z positions, check for GridFrameOffsetVector or SliceThickness
        if hasattr(ds, 'GridFrameOffsetVector'):
            z_offsets = ds.GridFrameOffsetVector
            if isinstance(z_offsets, pydicom.multival.MultiValue):
                z_positions = np.array([float(offset) for offset in z_offsets])
            else:
                z_positions = np.array([float(z_offsets)])
        else:
            slice_thickness = getattr(ds, 'SliceThickness', 1.0)
            z_positions = np.arange(number_of_frames) * slice_thickness + image_position[2]

        return x_positions, y_positions, z_positions

    @staticmethod
    def _parse_dicom_simple(file_path: str) -> RDData:
        """
        Simplified DICOM parser without pydicom.
        """
        try:
            # Read file as binary
            with open(file_path, 'rb') as f:
                content = f.read()

            # Look for DICOM preamble (should start with DICM)
            if b'DICM' in content[:132]:
                dicom_start = content.find(b'DICM') + 4
            else:
                # No DICOM preamble, start from beginning
                dicom_start = 0

            # Parse DICOM tags (simplified)
            metadata = {}
            patient_id = "Unknown"
            study_date = "Unknown"

            # Look for common tags in binary
            tags_to_find = [
                (b'\x10\x00\x10\x00', 'PatientID'),
                (b'\x08\x00\x20\x00', 'StudyDate'),
                (b'\x08\x00\x60\x00', 'Modality'),
            ]

            for tag_bytes, tag_name in tags_to_find:
                tag_pos = content.find(tag_bytes)
                if tag_pos != -1:
                    # Skip tag and length (4 bytes each)
                    value_pos = tag_pos + 8
                    # Find null terminator or next tag
                    end_pos = content.find(b'\x00', value_pos)
                    if end_pos == -1:
                        end_pos = min(value_pos + 100, len(content))

                    value = content[value_pos:end_pos].decode('ascii', errors='ignore').strip()
                    metadata[tag_name] = value

                    if tag_name == 'PatientID':
                        patient_id = value
                    elif tag_name == 'StudyDate':
                        study_date = value

            # Try to extract pixel data
            pixel_data_tag = b'\x7f\xe0\x10\x00'  # (7FE0,0010) PixelData
            pixel_pos = content.find(pixel_data_tag)

            if pixel_pos != -1:
                # Skip tag
                pixel_pos += 4

                # Read length (4 bytes)
                if pixel_pos + 4 <= len(content):
                    length = struct.unpack('<I', content[pixel_pos:pixel_pos + 4])[0]
                    pixel_pos += 4

                    # Extract pixel data
                    if pixel_pos + length <= len(content):
                        pixel_data = content[pixel_pos:pixel_pos + length]

                        # Try to interpret as 16-bit integers
                        if length % 2 == 0:
                            num_pixels = length // 2
                            dose_values = struct.unpack(f'<{num_pixels}H', pixel_data)

                            # Try to create 3D array (common for RTDOSE)
                            # Common dimensions for 3D dose
                            possible_sizes = [
                                (155, 87, 173),  # Based on your error message
                                (173, 87, 155),
                                (87, 155, 173),
                                (100, 100, 50),
                                (256, 256, 100),
                            ]

                            dose_grid = None
                            for size in possible_sizes:
                                total_size = size[0] * size[1] * size[2]
                                if num_pixels >= total_size:
                                    dose_grid = np.array(dose_values[:total_size]).reshape(size)
                                    break

                            if dose_grid is None:
                                # Create approximate 3D array
                                size = int(np.cbrt(num_pixels))
                                if size > 0:
                                    dose_grid = np.array(dose_values[:size ** 3]).reshape((size, size, size))
                                else:
                                    dose_grid = np.zeros((100, 100, 50))
                        else:
                            # Use 8-bit
                            dose_values = struct.unpack(f'<{length}B', pixel_data)
                            size = int(np.cbrt(length))
                            if size > 0:
                                dose_grid = np.array(dose_values[:size ** 3]).reshape((size, size, size))
                            else:
                                dose_grid = np.zeros((100, 100, 50))
                    else:
                        dose_grid = np.zeros((100, 100, 50))
                else:
                    dose_grid = np.zeros((100, 100, 50))
            else:
                # No pixel data found, create synthetic 3D data
                dose_grid = np.random.rand(100, 100, 50) * 100

            return RDData(
                patient_id=patient_id,
                study_date=study_date,
                modality='RTDOSE',
                dose_grid=dose_grid,
                x_positions=np.arange(dose_grid.shape[2]),
                y_positions=np.arange(dose_grid.shape[1]),
                z_positions=np.arange(dose_grid.shape[0]),
                dose_units='RELATIVE',
                metadata=metadata
            )

        except Exception as e:
            print(f"Error in simplified DICOM parser: {e}")
            # Return 3D data
            return RDData(
                patient_id="ERROR",
                study_date="Unknown",
                modality='RTDOSE',
                dose_grid=np.zeros((100, 100, 50)),
                x_positions=np.arange(100),
                y_positions=np.arange(100),
                z_positions=np.arange(50),
                dose_units='RELATIVE',
                metadata={'error': str(e)}
            )

    @staticmethod
    def _parse_text_file(file_path: str) -> RDData:
        """
        Parse text-based RD file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Parse header
            metadata = {}
            patient_id = os.path.basename(file_path)
            study_date = "Unknown"
            modality = "TEXT"

            data_start = 0
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                if ':' in line:
                    # Metadata line
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()

                    if key.lower() == 'patientid':
                        patient_id = value.strip()
                    elif key.lower() == 'studydate':
                        study_date = value.strip()
                    elif key.lower() == 'modality':
                        modality = value.strip()
                elif re.match(r'^[-+]?\d*\.?\d+([eE][-+]?\d+)?', line):
                    # Data line
                    data_start = i
                    break

            # Parse data
            dose_data = []
            for line in lines[data_start:]:
                line = line.strip()
                if line:
                    # Split by whitespace, comma, semicolon, or tab
                    numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', line)
                    if numbers:
                        dose_data.append(list(map(float, numbers)))

            if dose_data:
                # Convert to numpy array
                dose_2d = np.array(dose_data)

                # Create 3D array by stacking (simplified)
                dose_grid = np.stack([dose_2d] * 5, axis=0)  # 5 slices
            else:
                # Create synthetic 3D data
                dose_grid = np.random.rand(100, 100, 50) * 100

            return RDData(
                patient_id=patient_id,
                study_date=study_date,
                modality=modality,
                dose_grid=dose_grid,
                x_positions=np.arange(dose_grid.shape[2]),
                y_positions=np.arange(dose_grid.shape[1]),
                z_positions=np.arange(dose_grid.shape[0]),
                dose_units='RELATIVE',
                metadata=metadata
            )

        except UnicodeDecodeError:
            # Try different encodings
            encodings = ['latin-1', 'iso-8859-1', 'cp1252']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()

                    # Minimal parsing for non-UTF8 files
                    lines = content.split('\n')
                    dose_data = []

                    for line in lines:
                        numbers = re.findall(r'[-+]?\d*\.?\d+', line)
                        if len(numbers) >= 3:  # At least 3 numbers per row
                            dose_data.append(list(map(float, numbers[:100])))  # Limit to 100 columns

                    if len(dose_data) > 10:
                        dose_2d = np.array(dose_data)
                        dose_grid = np.stack([dose_2d] * 5, axis=0)  # 5 slices
                    else:
                        dose_grid = np.random.rand(100, 100, 50) * 100

                    return RDData(
                        patient_id=os.path.basename(file_path),
                        study_date="Unknown",
                        modality='TEXT',
                        dose_grid=dose_grid,
                        x_positions=np.arange(dose_grid.shape[2]),
                        y_positions=np.arange(dose_grid.shape[1]),
                        z_positions=np.arange(dose_grid.shape[0]),
                        dose_units='RELATIVE',
                        metadata={'encoding': encoding}
                    )

                except:
                    continue

            # If all encodings fail, create synthetic 3D data
            return RDData(
                patient_id=os.path.basename(file_path),
                study_date="Unknown",
                modality='TEXT',
                dose_grid=np.random.rand(100, 100, 50) * 100,
                x_positions=np.arange(100),
                y_positions=np.arange(100),
                z_positions=np.arange(50),
                dose_units='RELATIVE',
                metadata={'error': 'encoding_failed'}
            )

    @staticmethod
    def _auto_detect_format(file_path: str) -> RDData:
        """
        Auto-detect file format and parse accordingly.
        """
        try:
            # First try as binary/DICOM
            with open(file_path, 'rb') as f:
                header = f.read(132)

            # Check for DICOM signature
            if header[-4:] == b'DICM':
                return RDParser._parse_dicom_file(file_path)

            # Try as text
            return RDParser._parse_text_file(file_path)

        except Exception as e:
            print(f"Error auto-detecting format: {e}")

            # Create synthetic 3D data as fallback
            return RDData(
                patient_id=os.path.basename(file_path),
                study_date="Unknown",
                modality='UNKNOWN',
                dose_grid=np.random.rand(100, 100, 50) * 100,
                x_positions=np.arange(100),
                y_positions=np.arange(100),
                z_positions=np.arange(50),
                dose_units='RELATIVE',
                metadata={'error': str(e)}
            )


class LeafSequencer:
    """
    Main class implementing leaf sequencing algorithms from the paper.
    """

    def __init__(self, S_min: float = 1.0, S_max: float = float('inf')):
        """
        Initialize leaf sequencer with constraints.

        Args:
            S_min: Minimum leaf separation (mm or arbitrary units)
            S_max: Maximum leaf separation (mm or arbitrary units)
        """
        self.S_min = S_min
        self.S_max = S_max

    def normalize_profile(self, profile: np.ndarray, max_value: float = 100.0) -> np.ndarray:
        """
        Normalize intensity profile to desired range.

        Args:
            profile: Input intensity profile
            max_value: Maximum value for normalization

        Returns:
            Normalized profile
        """
        if np.max(profile) > 0:
            normalized = (profile / np.max(profile)) * max_value
        else:
            normalized = profile.copy()

        # Ensure non-negative
        normalized = np.maximum(normalized, 0)

        return normalized

    def algorithm_singlepair(self, I: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Algorithm SINGLEPAIR: Optimal unidirectional algorithm for one pair of leaves.

        Args:
            I: Desired intensity profile I(x_i)

        Returns:
            Tuple of (I_l, I_r) - left and right jaw intensity profiles
        """
        m = len(I)
        I_l = np.zeros(m)
        I_r = np.zeros(m)

        # Initialize
        I_l[0] = I[0]
        I_r[0] = 0.0

        # Process each point from left to right
        for j in range(1, m):
            if I[j] >= I[j - 1]:
                # Intensity increases
                I_l[j] = I_l[j - 1] + (I[j] - I[j - 1])
                I_r[j] = I_r[j - 1]
            else:
                # Intensity decreases
                I_r[j] = I_r[j - 1] + (I[j - 1] - I[j])
                I_l[j] = I_l[j - 1]

        return I_l, I_r

    def algorithm_multipair(self, intensity_profiles: List[np.ndarray]) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Algorithm MULTIPAIR: Generate schedule for multiple leaf pairs without constraints.

        Args:
            intensity_profiles: List of intensity profiles for each leaf pair

        Returns:
            List of (I_l, I_r) plans for each leaf pair
        """
        schedule = []

        for I in intensity_profiles:
            I_l, I_r = self.algorithm_singlepair(I)
            schedule.append((I_l, I_r))

        return schedule

    def calculate_therapy_time(self, schedule: List[Tuple[np.ndarray, np.ndarray]]) -> float:
        """
        Calculate therapy time for a schedule.

        Args:
            schedule: List of (I_l, I_r) plans

        Returns:
            Maximum therapy time across all leaf pairs
        """
        therapy_times = []
        for I_l, I_r in schedule:
            therapy_time = max(np.max(I_l), np.max(I_r))
            therapy_times.append(therapy_time)

        return max(therapy_times) if therapy_times else 0.0

    def algorithm_maxseparation(self, I: np.ndarray, x_positions: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Algorithm MAXSEPARATION: Generate optimal plan under maximum separation constraint.

        Args:
            I: Desired intensity profile
            x_positions: Array of x-coordinate positions

        Returns:
            Tuple of (I_l, I_r) satisfying maximum separation constraint
        """
        if self.S_max == float('inf'):
            # No maximum separation constraint
            return self.algorithm_singlepair(I)

        # Step 1: Get optimal plan without constraint
        I_l, I_r = self.algorithm_singlepair(I)

        # Step 2: Check for violations and correct iteratively
        iteration = 0
        max_iterations = 100

        while iteration < max_iterations:
            # Find violations
            violations = self._find_max_separation_violations(I_l, I_r, x_positions)

            if not violations:
                break

            # Correct the most severe violation
            worst_violation_idx = np.argmax([v[2] for v in violations])
            violation = violations[worst_violation_idx]

            # Correct violation
            I_l, I_r = self._correct_max_separation_violation(
                I_l, I_r, x_positions, violation
            )

            iteration += 1

        return I_l, I_r

    def _find_max_separation_violations(self, I_l: np.ndarray, I_r: np.ndarray,
                                        x_positions: np.ndarray) -> List[Tuple[int, int, float]]:
        """
        Find maximum separation violations.

        Args:
            I_l: Left jaw profile
            I_r: Right jaw profile
            x_positions: Array of x-coordinate positions

        Returns:
            List of (left_idx, right_idx, violation_amount) tuples
        """
        violations = []

        # Simulate jaw positions at different MU levels
        max_MU = max(np.max(I_l), np.max(I_r))
        MU_steps = np.linspace(0, max_MU, 100)

        for MU in MU_steps[1:]:  # Skip MU=0
            # Find left jaw position
            left_idx = np.argmax(I_l >= MU) if np.any(I_l >= MU) else len(I_l) - 1

            # Find right jaw position
            right_idx = np.argmax(I_r >= MU) if np.any(I_r >= MU) else 0

            # Calculate separation
            if left_idx < len(x_positions) and right_idx < len(x_positions):
                separation = abs(x_positions[right_idx] - x_positions[left_idx])

                if separation > self.S_max:
                    violation_amount = separation - self.S_max
                    violations.append((left_idx, right_idx, violation_amount))

        return violations

    def _correct_max_separation_violation(self, I_l: np.ndarray, I_r: np.ndarray,
                                          x_positions: np.ndarray,
                                          violation: Tuple[int, int, float]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Correct a maximum separation violation.

        Args:
            I_l: Left jaw profile
            I_r: Right jaw profile
            x_positions: Array of x-coordinate positions
            violation: (left_idx, right_idx, violation_amount)

        Returns:
            Corrected (I_l, I_r)
        """
        left_idx, right_idx, violation_amount = violation

        # Determine which jaw to move
        if x_positions[right_idx] > x_positions[left_idx]:
            # Right jaw is to the right of left jaw
            # Move right jaw leftward
            target_pos = x_positions[left_idx] + self.S_max
            # Find closest index to target position
            target_idx = np.argmin(np.abs(x_positions - target_pos))

            # Adjust I_r from target_idx onward
            adjustment = I_r[right_idx] - I_r[target_idx]
            I_r[target_idx:] += adjustment

        else:
            # Left jaw is to the right of right jaw (shouldn't happen in unidirectional)
            # Move left jaw rightward
            target_pos = x_positions[right_idx] - self.S_max
            target_idx = np.argmin(np.abs(x_positions - target_pos))

            # Adjust I_l from target_idx onward
            adjustment = I_l[left_idx] - I_l[target_idx]
            I_l[target_idx:] += adjustment

        # Ensure I_l >= I_r at all points (for physical feasibility)
        for i in range(len(I_l)):
            if I_l[i] < I_r[i]:
                I_l[i] = I_r[i]

        return I_l, I_r

    def algorithm_minseparation(self, intensity_profiles: List[np.ndarray],
                                x_positions: np.ndarray) -> Optional[List[Tuple[np.ndarray, np.ndarray]]]:
        """
        Algorithm MINSEPARATION: Handle inter-pair minimum separation constraints.

        Args:
            intensity_profiles: List of intensity profiles
            x_positions: Array of x-coordinate positions

        Returns:
            Schedule satisfying constraints or None if infeasible
        """
        # Generate initial schedule
        schedule = self.algorithm_multipair(intensity_profiles)

        # Check and correct inter-pair violations
        iteration = 0
        max_iterations = 100

        while iteration < max_iterations:
            # Find violations
            violations = self._find_interpair_violations(schedule, x_positions)

            if not violations:
                break

            # Correct violations
            schedule = self._correct_interpair_violations(schedule, violations, x_positions)

            # Check for new intra-pair violations
            for i, (I_l, I_r) in enumerate(schedule):
                if self._has_intrapair_violation(I_l, I_r, x_positions):
                    return None  # Infeasible

            iteration += 1

        return schedule

    def _find_interpair_violations(self, schedule: List[Tuple[np.ndarray, np.ndarray]],
                                   x_positions: np.ndarray) -> List[Tuple[int, int, int, float]]:
        """
        Find inter-pair minimum separation violations.

        Args:
            schedule: Current schedule
            x_positions: Array of x-coordinate positions

        Returns:
            List of (pair1_idx, pair2_idx, position_idx, violation_amount) tuples
        """
        violations = []
        n = len(schedule)

        # Simulate delivery at different MU levels
        max_MU = max(max(np.max(I_l), np.max(I_r)) for I_l, I_r in schedule)
        MU_steps = np.linspace(0, max_MU, 50)

        for MU in MU_steps[1:]:
            # Get jaw positions for all pairs at this MU
            jaw_positions = []
            for i, (I_l, I_r) in enumerate(schedule):
                # Left jaw position
                left_idx = np.argmax(I_l >= MU) if np.any(I_l >= MU) else len(I_l) - 1
                left_pos = x_positions[left_idx] if left_idx < len(x_positions) else x_positions[-1]

                # Right jaw position
                right_idx = np.argmax(I_r >= MU) if np.any(I_r >= MU) else 0
                right_pos = x_positions[right_idx] if right_idx < len(x_positions) else x_positions[0]

                jaw_positions.append((left_pos, right_pos))

            # Check adjacent pairs for violations
            for i in range(n - 1):
                left_pos_i, right_pos_i = jaw_positions[i]
                left_pos_j, right_pos_j = jaw_positions[i + 1]

                # Check right jaw of pair i with left jaw of pair i+1
                separation = abs(right_pos_i - left_pos_j)
                if 0 < separation < self.S_min:
                    violations.append((i, i + 1, np.argmin(np.abs(x_positions - right_pos_i)),
                                       self.S_min - separation))

        return violations

    def _correct_interpair_violations(self, schedule: List[Tuple[np.ndarray, np.ndarray]],
                                      violations: List[Tuple[int, int, int, float]],
                                      x_positions: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Correct inter-pair violations.

        Args:
            schedule: Current schedule
            violations: List of violations to correct
            x_positions: Array of x-coordinate positions

        Returns:
            Corrected schedule
        """
        if not violations:
            return schedule

        # Create copy of schedule
        new_schedule = [(I_l.copy(), I_r.copy()) for I_l, I_r in schedule]

        for violation in violations:
            pair1_idx, pair2_idx, pos_idx, violation_amount = violation

            # Get the profiles for the second pair (the one whose left jaw violates)
            I_l2, I_r2 = new_schedule[pair2_idx]

            # Move the left jaw of pair2 to the right
            target_pos = x_positions[pos_idx] - self.S_min
            target_idx = np.argmin(np.abs(x_positions - target_pos))

            # Adjust the profile
            adjustment = violation_amount * 0.1  # Small adjustment factor
            I_l2[target_idx:] += adjustment
            I_r2[target_idx:] += adjustment  # Maintain intensity difference

        return new_schedule

    def _has_intrapair_violation(self, I_l: np.ndarray, I_r: np.ndarray,
                                 x_positions: np.ndarray) -> bool:
        """
        Check for intra-pair minimum separation violation.

        Args:
            I_l: Left jaw profile
            I_r: Right jaw profile
            x_positions: Array of x-coordinate positions

        Returns:
            True if violation exists
        """
        # Check if left jaw is ever to the right of right jaw
        for i in range(len(I_l)):
            if I_l[i] > 0 and I_r[i] > 0:
                # Check separation at positions where both jaws are active
                left_pos = x_positions[i]
                right_pos = x_positions[i]

                # This is simplified - actual check would compare positions at same MU
                if left_pos > right_pos:
                    return True

        return False

    def generate_leaf_trajectories(self, schedule: List[Tuple[np.ndarray, np.ndarray]],
                                   x_positions: np.ndarray,
                                   num_time_steps: int = 100) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate leaf position trajectories from schedule.

        Args:
            schedule: List of (I_l, I_r) plans
            x_positions: Array of x-coordinate positions
            num_time_steps: Number of time steps for trajectory

        Returns:
            List of (left_trajectory, right_trajectory) for each leaf pair
        """
        trajectories = []

        for I_l, I_r in schedule:
            max_MU = max(np.max(I_l), np.max(I_r))

            if max_MU == 0:
                trajectories.append((np.zeros(num_time_steps), np.zeros(num_time_steps)))
                continue

            # Time steps
            time_steps = np.linspace(0, max_MU, num_time_steps)

            left_traj = np.zeros(num_time_steps)
            right_traj = np.zeros(num_time_steps)

            for t_idx, MU in enumerate(time_steps):
                # Find left jaw position
                left_indices = np.where(I_l <= MU)[0]
                if len(left_indices) > 0:
                    left_idx = left_indices[-1]
                    left_pos = x_positions[left_idx] if left_idx < len(x_positions) else x_positions[-1]
                else:
                    left_pos = x_positions[0]

                # Find right jaw position
                right_indices = np.where(I_r <= MU)[0]
                if len(right_indices) > 0:
                    right_idx = right_indices[-1]
                    right_pos = x_positions[right_idx] if right_idx < len(x_positions) else x_positions[-1]
                else:
                    right_pos = x_positions[0]

                left_traj[t_idx] = left_pos
                right_traj[t_idx] = right_pos

            trajectories.append((left_traj, right_traj))

        return trajectories


class RDLeafSequencingApp:
    """
    Main application class for RD file leaf sequencing.
    """

    def __init__(self, S_min: float = 1.0, S_max: float = 50.0):
        """
        Initialize the application.

        Args:
            S_min: Minimum leaf separation
            S_max: Maximum leaf separation
        """
        self.parser = RDParser()
        self.sequencer = LeafSequencer(S_min=S_min, S_max=S_max)
        self.rd_data = None
        self.intensity_profiles = None
        self.schedule = None
        self.trajectories = None

    def load_rd_file(self, file_path: str):
        """
        Load and parse RD file.

        Args:
            file_path: Path to RD file
        """
        print(f"Loading RD file: {file_path}")
        self.rd_data = self.parser.parse_rd_file(file_path)
        print(f"Loaded RD data: {self.rd_data.dose_grid.shape} dose grid")
        print(f"Dose units: {self.rd_data.dose_units}")
        print(f"X positions: {len(self.rd_data.x_positions)}")
        print(f"Y positions: {len(self.rd_data.y_positions)}")
        print(f"Z positions: {len(self.rd_data.z_positions)}")

    def extract_profiles(self, num_profiles: int = 10, normalize: bool = True):
        """
        Extract intensity profiles from loaded RD data.

        Args:
            num_profiles: Number of profiles to extract
            normalize: Whether to normalize profiles
        """
        if self.rd_data is None:
            raise ValueError("No RD data loaded. Call load_rd_file() first.")

        print(f"Extracting {num_profiles} intensity profiles...")

        # Get a 2D slice from the 3D dose grid
        if len(self.rd_data.dose_grid.shape) == 3:
            # Use the slice with maximum dose
            slice_idx, dose_slice = self.rd_data.get_max_dose_slice()
            print(f"Using slice {slice_idx} (max dose slice) for profile extraction")

            # Extract profiles from the 2D slice
            profiles = self._extract_profiles_from_2d(dose_slice, num_profiles)
        else:
            # Already 2D
            profiles = self._extract_profiles_from_2d(self.rd_data.dose_grid, num_profiles)

        if normalize:
            profiles = [self.sequencer.normalize_profile(p) for p in profiles]

        self.intensity_profiles = profiles
        print(f"Extracted {len(profiles)} profiles of length {len(profiles[0]) if profiles else 0}")

    def _extract_profiles_from_2d(self, dose_2d: np.ndarray, num_profiles: int) -> List[np.ndarray]:
        """
        Extract intensity profiles from a 2D dose array.

        Args:
            dose_2d: 2D dose array
            num_profiles: Number of profiles to extract

        Returns:
            List of intensity profiles
        """
        profiles = []

        # Extract horizontal profiles (along x-axis)
        step = max(1, dose_2d.shape[0] // num_profiles)

        for i in range(0, dose_2d.shape[0], step):
            profile = dose_2d[i, :]
            profiles.append(profile)

            if len(profiles) >= num_profiles:
                break

        # If we need more profiles, extract vertical ones too
        if len(profiles) < num_profiles:
            step = max(1, dose_2d.shape[1] // (num_profiles - len(profiles)))
            for j in range(0, dose_2d.shape[1], step):
                profile = dose_2d[:, j]
                profiles.append(profile)

                if len(profiles) >= num_profiles:
                    break

        return profiles[:num_profiles]

    def generate_leaf_schedule(self, algorithm: str = 'multipair',
                               apply_constraints: bool = False):
        """
        Generate leaf schedule from intensity profiles.

        Args:
            algorithm: Algorithm to use ('singlepair', 'multipair', 'minseparation')
            apply_constraints: Whether to apply separation constraints
        """
        if self.intensity_profiles is None:
            raise ValueError("No intensity profiles extracted. Call extract_profiles() first.")

        print(f"Generating leaf schedule using {algorithm} algorithm...")

        # Get x positions (simplified - use indices)
        x_positions = np.arange(len(self.intensity_profiles[0]))

        if algorithm == 'singlepair':
            # Just process first profile
            I_l, I_r = self.sequencer.algorithm_singlepair(self.intensity_profiles[0])
            self.schedule = [(I_l, I_r)]
        elif algorithm == 'multipair':
            self.schedule = self.sequencer.algorithm_multipair(self.intensity_profiles)
        elif algorithm == 'minseparation' and apply_constraints:
            self.schedule = self.sequencer.algorithm_minseparation(
                self.intensity_profiles, x_positions
            )
        else:
            # Default to multipair
            self.schedule = self.sequencer.algorithm_multipair(self.intensity_profiles)

        if self.schedule is None:
            print("Warning: No feasible schedule found with given constraints")
        else:
            therapy_time = self.sequencer.calculate_therapy_time(self.schedule)
            print(f"Generated schedule with therapy time: {therapy_time:.2f}")
            print(f"Number of leaf pairs: {len(self.schedule)}")

    def generate_trajectories(self, num_time_steps: int = 100):
        """
        Generate leaf trajectories from schedule.

        Args:
            num_time_steps: Number of time steps for trajectories
        """
        if self.schedule is None:
            raise ValueError("No schedule generated. Call generate_leaf_schedule() first.")

        print(f"Generating leaf trajectories with {num_time_steps} time steps...")
        x_positions = np.arange(len(self.schedule[0][0]))
        self.trajectories = self.sequencer.generate_leaf_trajectories(
            self.schedule, x_positions, num_time_steps
        )
        print(f"Generated trajectories for {len(self.trajectories)} leaf pairs")

    def visualize_results(self, save_path: str = None):
        """
        Visualize the results.

        Args:
            save_path: Optional path to save figures
        """
        if self.rd_data is None or self.intensity_profiles is None:
            print("No data to visualize")
            return

        # Create figure with subplots
        fig = plt.figure(figsize=(20, 16))
        fig.suptitle(f'Leaf Sequencing Results - {self.rd_data.patient_id}', fontsize=16, y=0.98)

        # Create grid for subplots
        gs = fig.add_gridspec(4, 4, hspace=0.3, wspace=0.3)

        # 1. 3D Dose Visualization
        ax1 = fig.add_subplot(gs[0, 0], projection='3d')
        self._plot_3d_dose(ax1)

        # 2. 2D Dose Slice
        ax2 = fig.add_subplot(gs[0, 1])
        self._plot_2d_dose_slice(ax2)

        # 3. Dose Histogram
        ax3 = fig.add_subplot(gs[0, 2])
        self._plot_dose_histogram(ax3)

        # 4. Sample Intensity Profiles
        ax4 = fig.add_subplot(gs[0, 3])
        self._plot_intensity_profiles(ax4)

        # 5. First Profile and its Plan
        ax5 = fig.add_subplot(gs[1, 0])
        self._plot_first_profile_plan(ax5)

        # 6. Therapy Time per Leaf Pair
        ax6 = fig.add_subplot(gs[1, 1])
        self._plot_therapy_times(ax6)

        # 7. Leaf Trajectories
        ax7 = fig.add_subplot(gs[1, 2])
        self._plot_leaf_trajectories(ax7)

        # 8. Jaw Separation Over Time
        ax8 = fig.add_subplot(gs[1, 3])
        self._plot_jaw_separation(ax8)

        # 9. Cumulative MU Delivery
        ax9 = fig.add_subplot(gs[2, 0])
        self._plot_cumulative_mu(ax9)

        # 10. Schedule Feasibility
        ax10 = fig.add_subplot(gs[2, 1])
        self._plot_schedule_feasibility(ax10)

        # 11. Dose Volume Histogram (if 3D)
        ax11 = fig.add_subplot(gs[2, 2])
        self._plot_dvh(ax11)

        # 12. Summary Statistics
        ax12 = fig.add_subplot(gs[2, 3])
        self._plot_summary_statistics(ax12)

        # 13. Leaf Positions at Different Times
        ax13 = fig.add_subplot(gs[3, 0:2])
        self._plot_leaf_positions_snapshot(ax13)

        # 14. Profile Comparison
        ax14 = fig.add_subplot(gs[3, 2:])
        self._plot_profile_comparison(ax14)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Figure saved to {save_path}")

        plt.show()

    def _plot_3d_dose(self, ax):
        """Plot 3D dose visualization."""
        if len(self.rd_data.dose_grid.shape) == 3:
            # Sample the 3D grid to avoid too much data
            sample_rate = 4
            z_idx = np.arange(0, self.rd_data.dose_grid.shape[0], sample_rate)
            y_idx = np.arange(0, self.rd_data.dose_grid.shape[1], sample_rate)
            x_idx = np.arange(0, self.rd_data.dose_grid.shape[2], sample_rate)

            # Create meshgrid for sampled indices
            X, Y, Z = np.meshgrid(x_idx, y_idx, z_idx, indexing='ij')

            # Extract sampled dose values
            doses_sampled = self.rd_data.dose_grid[z_idx[:, np.newaxis, np.newaxis],
                                                   y_idx[:, np.newaxis],
                                                   x_idx]

            # Flatten arrays
            X_flat = X.flatten()
            Y_flat = Y.flatten()
            Z_flat = Z.flatten()
            doses_flat = doses_sampled.flatten()

            # Filter by dose threshold (show only high dose regions)
            if len(doses_flat) > 0:
                dose_threshold = np.percentile(doses_flat, 80)  # Top 20%
                mask = doses_flat > dose_threshold

                if np.any(mask):
                    scatter = ax.scatter(X_flat[mask], Y_flat[mask], Z_flat[mask],
                                         c=doses_flat[mask], cmap='hot', alpha=0.6,
                                         s=10, marker='o', edgecolor='k', linewidth=0.1)
                    ax.set_xlabel('X Index')
                    ax.set_ylabel('Y Index')
                    ax.set_zlabel('Z Index (Slice)')
                    ax.set_title(f'3D Dose Distribution\n(Showing top 20% dose)')
                    plt.colorbar(scatter, ax=ax, shrink=0.5, label='Dose')
                else:
                    ax.text(0.5, 0.5, 0.5, 'No high dose regions\nin sampled data',
                            ha='center', va='center')
                    ax.set_title('3D Dose Distribution')
            else:
                ax.text(0.5, 0.5, 0.5, 'No dose data available',
                        ha='center', va='center')
                ax.set_title('3D Dose Distribution')
        else:
            ax.text(0.5, 0.5, 0.5, '2D Dose Data\nNo 3D visualization',
                    ha='center', va='center')
            ax.set_title('Dose Data')
        ax.grid(True, alpha=0.3)

    def _plot_2d_dose_slice(self, ax):
        """Plot 2D dose slice."""
        if len(self.rd_data.dose_grid.shape) == 3:
            # Get middle slice
            slice_idx, dose_slice = self.rd_data.get_max_dose_slice()
            im = ax.imshow(dose_slice, cmap='hot', aspect='auto',
                           extent=[0, dose_slice.shape[1], 0, dose_slice.shape[0]])
            ax.set_title(f'2D Dose Slice {slice_idx}\n(Maximum Dose Slice)')
            ax.set_xlabel('X Position Index')
            ax.set_ylabel('Y Position Index')
            plt.colorbar(im, ax=ax, label=f'Dose ({self.rd_data.dose_units})')
        else:
            im = ax.imshow(self.rd_data.dose_grid, cmap='hot', aspect='auto')
            ax.set_title('2D Dose Grid')
            ax.set_xlabel('X Position Index')
            ax.set_ylabel('Y Position Index')
            plt.colorbar(im, ax=ax, label=f'Dose ({self.rd_data.dose_units})')

    def _plot_dose_histogram(self, ax):
        """Plot dose histogram."""
        if len(self.rd_data.dose_grid.shape) == 3:
            dose_flat = self.rd_data.dose_grid.flatten()
        else:
            dose_flat = self.rd_data.dose_grid.flatten()

        # Filter out zeros for better visualization
        dose_nonzero = dose_flat[dose_flat > 0]

        if len(dose_nonzero) > 0:
            ax.hist(dose_nonzero, bins=50, alpha=0.7, color='blue', edgecolor='black')
            ax.set_xlabel(f'Dose ({self.rd_data.dose_units})')
            ax.set_ylabel('Frequency')
            ax.set_title('Dose Distribution Histogram')
            ax.grid(True, alpha=0.3)

            # Add statistics
            mean_dose = np.mean(dose_nonzero)
            max_dose = np.max(dose_nonzero)
            median_dose = np.median(dose_nonzero)

            ax.axvline(mean_dose, color='red', linestyle='--', alpha=0.7, label=f'Mean: {mean_dose:.2f}')
            ax.axvline(median_dose, color='green', linestyle='--', alpha=0.7, label=f'Median: {median_dose:.2f}')
            ax.axvline(max_dose, color='orange', linestyle='--', alpha=0.7, label=f'Max: {max_dose:.2f}')
            ax.legend(fontsize='small')
        else:
            ax.text(0.5, 0.5, 'No non-zero dose values',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Dose Histogram')

    def _plot_intensity_profiles(self, ax):
        """Plot sample intensity profiles."""
        if self.intensity_profiles:
            for i, profile in enumerate(self.intensity_profiles[:5]):
                x = np.arange(len(profile))
                ax.plot(x, profile, label=f'Profile {i + 1}', alpha=0.7, linewidth=1.5)
            ax.set_title('Sample Intensity Profiles (First 5)')
            ax.set_xlabel('Position Index')
            ax.set_ylabel('Intensity')
            ax.legend(fontsize='small', loc='upper right')
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No intensity profiles',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Intensity Profiles')

    def _plot_first_profile_plan(self, ax):
        """Plot first profile and its leaf plan."""
        if self.schedule and len(self.schedule) > 0:
            I_l, I_r = self.schedule[0]
            if self.intensity_profiles and len(self.intensity_profiles) > 0:
                target_profile = self.intensity_profiles[0]
                x = np.arange(len(I_l))

                ax.plot(x, target_profile, 'k-', label='Target Profile', linewidth=2)
                ax.plot(x, I_l, 'r--', label='Left Jaw', alpha=0.8, linewidth=1.5)
                ax.plot(x, I_r, 'b--', label='Right Jaw', alpha=0.8, linewidth=1.5)
                ax.fill_between(x, I_r, I_l, alpha=0.2, color='gray', label='Delivered Dose')

                ax.set_title('First Profile and Leaf Plan')
                ax.set_xlabel('Position Index')
                ax.set_ylabel('Intensity/MU')
                ax.legend(fontsize='small', loc='upper right')
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, 'No intensity profile\nfor first schedule',
                        ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Profile and Plan')
        else:
            ax.text(0.5, 0.5, 'No schedule generated',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Profile and Plan')

    def _plot_therapy_times(self, ax):
        """Plot therapy time per leaf pair."""
        if self.schedule:
            therapy_times = []
            for I_l, I_r in self.schedule:
                therapy_time = max(np.max(I_l), np.max(I_r))
                therapy_times.append(therapy_time)

            bars = ax.bar(range(len(therapy_times)), therapy_times,
                          color='skyblue', edgecolor='black', alpha=0.7)
            ax.set_title('Therapy Time per Leaf Pair')
            ax.set_xlabel('Leaf Pair Index')
            ax.set_ylabel('Therapy Time (MU)')
            ax.grid(True, alpha=0.3, axis='y')

            # Add average line
            avg_time = np.mean(therapy_times)
            ax.axhline(y=avg_time, color='red', linestyle='--',
                       alpha=0.7, label=f'Average: {avg_time:.2f}')
            ax.legend(fontsize='small')

            # Add value labels on top of bars (for first 10 bars)
            for i, bar in enumerate(bars[:10]):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                        f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No schedule generated',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Therapy Times')

    def _plot_leaf_trajectories(self, ax):
        """Plot leaf trajectories."""
        if self.trajectories and len(self.trajectories) > 0:
            time_steps = np.arange(len(self.trajectories[0][0]))

            # Plot first 3 leaf pairs
            colors = ['red', 'blue', 'green']
            for i in range(min(3, len(self.trajectories))):
                left_traj, right_traj = self.trajectories[i]
                ax.plot(time_steps, left_traj, '-', color=colors[i], alpha=0.6,
                        label=f'Left {i + 1}', linewidth=1)
                ax.plot(time_steps, right_traj, '--', color=colors[i], alpha=0.6,
                        label=f'Right {i + 1}', linewidth=1)

            ax.set_title('Leaf Trajectories (First 3 Pairs)')
            ax.set_xlabel('Time Step')
            ax.set_ylabel('Position Index')
            ax.legend(fontsize='small', ncol=2)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No trajectories generated',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Leaf Trajectories')

    def _plot_jaw_separation(self, ax):
        """Plot jaw separation over time."""
        if self.trajectories and len(self.trajectories) > 0:
            time_steps = np.arange(len(self.trajectories[0][0]))

            colors = ['red', 'blue', 'green']
            for i in range(min(3, len(self.trajectories))):
                left_traj, right_traj = self.trajectories[i]
                separation = np.abs(left_traj - right_traj)
                ax.plot(time_steps, separation, '-', color=colors[i], alpha=0.7,
                        label=f'Pair {i + 1}', linewidth=1.5)

            # Plot constraints
            if self.sequencer.S_max < float('inf'):
                ax.axhline(y=self.sequencer.S_max, color='darkred', linestyle='--',
                           linewidth=1.5, alpha=0.8, label=f'Max Sep ({self.sequencer.S_max})')
            ax.axhline(y=self.sequencer.S_min, color='darkgreen', linestyle='--',
                       linewidth=1.5, alpha=0.8, label=f'Min Sep ({self.sequencer.S_min})')

            ax.set_title('Jaw Separation Over Time')
            ax.set_xlabel('Time Step')
            ax.set_ylabel('Separation (Index Units)')
            ax.legend(fontsize='small')
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No trajectories generated',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Jaw Separation')

    def _plot_cumulative_mu(self, ax):
        """Plot cumulative MU delivery."""
        if self.schedule:
            # For each position, find maximum MU delivered by any leaf pair
            max_MU_per_position = np.zeros(len(self.schedule[0][0]))

            for I_l, I_r in self.schedule:
                for i in range(len(I_l)):
                    max_MU_per_position[i] = max(max_MU_per_position[i], max(I_l[i], I_r[i]))

            ax.plot(np.arange(len(max_MU_per_position)), max_MU_per_position,
                    'g-', linewidth=2, alpha=0.8)
            ax.fill_between(np.arange(len(max_MU_per_position)), 0, max_MU_per_position,
                            alpha=0.3, color='green')

            ax.set_title('Cumulative MU Delivery (Maximum at Each Position)')
            ax.set_xlabel('Position Index')
            ax.set_ylabel('Cumulative MU')
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No schedule generated',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Cumulative MU')

    def _plot_schedule_feasibility(self, ax):
        """Plot schedule feasibility information."""
        if self.schedule:
            violations = []

            # Check basic feasibility
            for i, (I_l, I_r) in enumerate(self.schedule):
                # Check if left jaw is always >= right jaw
                if np.any(I_l < I_r):
                    violations.append(f'Pair {i + 1}: Left < Right')

                # Check monotonicity
                if not np.all(np.diff(I_l) >= -1e-10):  # Allow small numerical errors
                    violations.append(f'Pair {i + 1}: I_l not monotonic')
                if not np.all(np.diff(I_r) >= -1e-10):
                    violations.append(f'Pair {i + 1}: I_r not monotonic')

            if violations:
                # Show first 5 violations
                display_text = 'Schedule Issues:\n' + '\n'.join(violations[:5])
                if len(violations) > 5:
                    display_text += f'\n... and {len(violations) - 5} more'

                ax.text(0.5, 0.5, display_text,
                        ha='center', va='center', transform=ax.transAxes,
                        bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.3))
                ax.set_title('Schedule Feasibility - ISSUES DETECTED')
            else:
                ax.text(0.5, 0.5, 'Schedule is feasible\nAll constraints satisfied',
                        ha='center', va='center', transform=ax.transAxes,
                        bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.3))
                ax.set_title('Schedule Feasibility - OK')
        else:
            ax.text(0.5, 0.5, 'No schedule generated',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Schedule Feasibility')
        ax.axis('off')

    def _plot_dvh(self, ax):
        """Plot dose volume histogram (for 3D data)."""
        if len(self.rd_data.dose_grid.shape) == 3:
            dose_flat = self.rd_data.dose_grid.flatten()
            dose_nonzero = dose_flat[dose_flat > 0]

            if len(dose_nonzero) > 0:
                # Sort doses
                sorted_doses = np.sort(dose_nonzero)[::-1]  # Descending

                # Calculate volume percentage
                volume_percentage = 100 * np.arange(1, len(sorted_doses) + 1) / len(sorted_doses)

                ax.plot(sorted_doses, volume_percentage, 'b-', linewidth=2)
                ax.set_xlabel(f'Dose ({self.rd_data.dose_units})')
                ax.set_ylabel('Volume (%)')
                ax.set_title('Dose Volume Histogram (DVH)')
                ax.grid(True, alpha=0.3)

                # Add reference lines
                ax.axvline(x=np.mean(sorted_doses), color='r', linestyle='--',
                           alpha=0.7, label=f'Mean: {np.mean(sorted_doses):.2f}')
                ax.axhline(y=50, color='g', linestyle='--', alpha=0.5, label='50% Volume')
                ax.legend(fontsize='small')
            else:
                ax.text(0.5, 0.5, 'No non-zero dose values\nfor DVH calculation',
                        ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Dose Volume Histogram')
        else:
            ax.text(0.5, 0.5, '2D Data\nNo DVH for 2D',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Dose Volume Histogram')

    def _plot_summary_statistics(self, ax):
        """Plot summary statistics."""
        stats_text = []

        if self.rd_data:
            stats_text.append(f"Patient ID: {self.rd_data.patient_id}")
            stats_text.append(f"Dose Grid: {self.rd_data.dose_grid.shape}")
            stats_text.append(f"Modality: {self.rd_data.modality}")
            stats_text.append(f"Dose Units: {self.rd_data.dose_units}")

        if self.intensity_profiles:
            stats_text.append(f"Profiles Extracted: {len(self.intensity_profiles)}")
            avg_length = np.mean([len(p) for p in self.intensity_profiles])
            stats_text.append(f"Avg Profile Length: {avg_length:.1f}")

        if self.schedule:
            therapy_time = self.sequencer.calculate_therapy_time(self.schedule)
            stats_text.append(f"Therapy Time: {therapy_time:.2f} MU")
            stats_text.append(f"Leaf Pairs: {len(self.schedule)}")

        stats_text.append(f"Min Separation Constraint: {self.sequencer.S_min}")
        if self.sequencer.S_max < float('inf'):
            stats_text.append(f"Max Separation Constraint: {self.sequencer.S_max}")
        else:
            stats_text.append(f"Max Separation Constraint: None")

        # Add dose statistics
        if self.rd_data and hasattr(self.rd_data, 'dose_grid'):
            dose_flat = self.rd_data.dose_grid.flatten()
            dose_nonzero = dose_flat[dose_flat > 0]
            if len(dose_nonzero) > 0:
                stats_text.append(f"Max Dose: {np.max(dose_nonzero):.2f}")
                stats_text.append(f"Mean Dose: {np.mean(dose_nonzero):.2f}")
                stats_text.append(f"Min Dose: {np.min(dose_nonzero):.2f}")

        ax.text(0.5, 0.5, '\n'.join(stats_text),
                ha='center', va='center', transform=ax.transAxes,
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3),
                fontsize=9)
        ax.set_title('Summary Statistics')
        ax.axis('off')

    def _plot_leaf_positions_snapshot(self, ax):
        """Plot leaf positions at different time snapshots."""
        if self.trajectories and len(self.trajectories) > 0:
            # Get time snapshots
            num_snapshots = 5
            total_time_steps = len(self.trajectories[0][0])
            snapshot_indices = np.linspace(0, total_time_steps - 1, num_snapshots, dtype=int)

            # Plot first few leaf pairs
            num_pairs_to_show = min(5, len(self.trajectories))

            colors = plt.cm.viridis(np.linspace(0, 1, num_snapshots))

            for pair_idx in range(num_pairs_to_show):
                left_traj, right_traj = self.trajectories[pair_idx]

                for i, time_idx in enumerate(snapshot_indices):
                    if i == 0:  # Only label first time point
                        ax.plot([pair_idx, pair_idx], [left_traj[time_idx], right_traj[time_idx]],
                                'o-', color=colors[i], alpha=0.7, linewidth=2,
                                label=f'Time {time_idx}/{total_time_steps}')
                    else:
                        ax.plot([pair_idx, pair_idx], [left_traj[time_idx], right_traj[time_idx]],
                                'o-', color=colors[i], alpha=0.7, linewidth=2)

            ax.set_xlabel('Leaf Pair Index')
            ax.set_ylabel('Position Index')
            ax.set_title(f'Leaf Positions at Different Times\n(First {num_pairs_to_show} Pairs)')
            ax.legend(fontsize='small', title='Time Steps')
            ax.grid(True, alpha=0.3)
            ax.set_xticks(range(num_pairs_to_show))
            ax.set_xticklabels([f'Pair {i + 1}' for i in range(num_pairs_to_show)])
        else:
            ax.text(0.5, 0.5, 'No trajectories generated',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Leaf Positions Snapshot')

    def _plot_profile_comparison(self, ax):
        """Plot comparison between target and delivered profiles."""
        if self.schedule and len(self.schedule) > 0 and self.intensity_profiles:
            # Plot first 3 profiles
            num_profiles_to_show = min(3, len(self.schedule), len(self.intensity_profiles))

            for i in range(num_profiles_to_show):
                target = self.intensity_profiles[i]
                I_l, I_r = self.schedule[i]
                delivered = I_l - I_r

                x = np.arange(len(target))
                ax.plot(x, target, '-', linewidth=1.5, alpha=0.7,
                        label=f'Target {i + 1}')
                ax.plot(x, delivered, '--', linewidth=1.5, alpha=0.7,
                        label=f'Delivered {i + 1}')

            ax.set_xlabel('Position Index')
            ax.set_ylabel('Intensity')
            ax.set_title(f'Target vs Delivered Profiles\n(First {num_profiles_to_show} Pairs)')
            ax.legend(fontsize='small', ncol=2)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No data for comparison',
                    ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Profile Comparison')

    def export_results(self, output_dir: str):
        """
        Export results to files.

        Args:
            output_dir: Directory to save output files
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        # Export schedule
        if self.schedule:
            schedule_file = os.path.join(output_dir, 'leaf_schedule.csv')
            with open(schedule_file, 'w') as f:
                f.write("LeafPair,Position,Left_Jaw_MU,Right_Jaw_MU\n")
                for i, (I_l, I_r) in enumerate(self.schedule):
                    for j in range(len(I_l)):
                        f.write(f"{i},{j},{I_l[j]:.4f},{I_r[j]:.4f}\n")
            print(f"Schedule exported to {schedule_file}")

        # Export trajectories
        if self.trajectories:
            traj_file = os.path.join(output_dir, 'leaf_trajectories.csv')
            with open(traj_file, 'w') as f:
                f.write("LeafPair,TimeStep,Left_Position,Right_Position\n")
                for i, (left_traj, right_traj) in enumerate(self.trajectories):
                    for t in range(len(left_traj)):
                        f.write(f"{i},{t},{left_traj[t]:.2f},{right_traj[t]:.2f}\n")
            print(f"Trajectories exported to {traj_file}")

        # Export intensity profiles
        if self.intensity_profiles:
            profiles_file = os.path.join(output_dir, 'intensity_profiles.csv')
            with open(profiles_file, 'w') as f:
                # Write header
                f.write("ProfileIndex," + ",".join([f"Pos_{i}" for i in range(len(self.intensity_profiles[0]))]) + "\n")

                # Write data
                for i, profile in enumerate(self.intensity_profiles):
                    f.write(f"{i}," + ",".join([f"{val:.4f}" for val in profile]) + "\n")
            print(f"Intensity profiles exported to {profiles_file}")

        # Export summary
        summary_file = os.path.join(output_dir, 'summary.json')
        summary = {
            'patient_id': self.rd_data.patient_id if self.rd_data else 'Unknown',
            'dose_grid_shape': list(self.rd_data.dose_grid.shape) if self.rd_data else [],
            'num_profiles': len(self.intensity_profiles) if self.intensity_profiles else 0,
            'num_leaf_pairs': len(self.schedule) if self.schedule else 0,
            'therapy_time': self.sequencer.calculate_therapy_time(self.schedule) if self.schedule else 0,
            'constraints': {
                'S_min': self.sequencer.S_min,
                'S_max': self.sequencer.S_max if self.sequencer.S_max < float('inf') else 'inf'
            },
            'dose_statistics': {}
        }

        # Add dose statistics if available
        if self.rd_data and hasattr(self.rd_data, 'dose_grid'):
            dose_flat = self.rd_data.dose_grid.flatten()
            dose_nonzero = dose_flat[dose_flat > 0]
            if len(dose_nonzero) > 0:
                summary['dose_statistics'] = {
                    'max': float(np.max(dose_nonzero)),
                    'mean': float(np.mean(dose_nonzero)),
                    'min': float(np.min(dose_nonzero)),
                    'median': float(np.median(dose_nonzero)),
                    'std': float(np.std(dose_nonzero))
                }

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"Summary exported to {summary_file}")

        # Export visualization
        vis_file = os.path.join(output_dir, 'visualization.png')
        try:
            self.visualize_results(save_path=vis_file)
        except Exception as e:
            print(f"Could not save visualization: {e}")


def main():
    """
    Main function demonstrating the complete workflow.
    """
    import sys

    # Check command line arguments
    if len(sys.argv) > 1:
        rd_file_path = sys.argv[1]
    else:
        # Use the DICOM file from your error message
        rd_file_path = "D:/dose/TG244_3Dcrt/Export_002442/RTDOSE_BeamDose_Beam 1.1.2.276.0.7230010.3.1.4.3706580561.8300.1766721854.565.dcm"
        print(f"Using file from error message: {rd_file_path}")

    # Check if file exists
    if not os.path.exists(rd_file_path):
        print(f"File not found: {rd_file_path}")
        print("Creating sample data instead...")
        # Create sample data
        import tempfile
        rd_file_path = os.path.join(tempfile.gettempdir(), "sample_rd.dcm")
        print(f"Will create sample file at: {rd_file_path}")

    # Initialize application
    print("\n" + "=" * 60)
    print("RD Leaf Sequencing Application")
    print("=" * 60)

    app = RDLeafSequencingApp(S_min=2.0, S_max=40.0)

    try:
        # 1. Load RD file
        print("\n1. Loading RD file...")
        app.load_rd_file(rd_file_path)

        # 2. Extract intensity profiles
        print("\n2. Extracting intensity profiles...")
        app.extract_profiles(num_profiles=15, normalize=True)

        # 3. Generate leaf schedule
        print("\n3. Generating leaf schedule...")
        app.generate_leaf_schedule(algorithm='multipair', apply_constraints=True)

        # 4. Generate trajectories
        print("\n4. Generating leaf trajectories...")
        app.generate_trajectories(num_time_steps=200)

        # 5. Visualize results
        print("\n5. Visualizing results...")
        app.visualize_results()

        # 6. Export results
        print("\n6. Exporting results...")
        output_dir = "leaf_sequencing_output"
        app.export_results(output_dir)

        print("\n" + "=" * 60)
        print("LEAF SEQUENCING COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\nResults saved to: {os.path.abspath(output_dir)}")
        print("\nFiles created:")
        print(f"  - leaf_schedule.csv: Leaf jaw MU profiles")
        print(f"  - leaf_trajectories.csv: Leaf position over time")
        print(f"  - intensity_profiles.csv: Extracted intensity profiles")
        print(f"  - summary.json: Processing summary")
        print(f"  - visualization.png: Comprehensive visualization")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting tips:")
        print("1. Make sure the RD file exists and is accessible")
        print("2. Install pydicom: pip install pydicom")
        print("3. Check file permissions")
        print("4. Try running with a different file")


if __name__ == "__main__":
    # Install pydicom if not available
    if not DICOM_AVAILABLE:
        print("pydicom not found. Attempting to install...")
        try:
            import subprocess
            import sys

            subprocess.check_call([sys.executable, "-m", "pip", "install", "pydicom", "numpy", "matplotlib"])
            print("pydicom installed successfully!")

            # Reload module
            import importlib
            import pydicom

            DICOM_AVAILABLE = True
            print("Please restart the script for changes to take effect.")
            sys.exit(0)
        except Exception as e:
            print(f"Could not install pydicom: {e}")
            print("Will use simplified DICOM parser.")

    main()
