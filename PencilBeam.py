"""
Medical Linear Accelerator Dose Engine - Python Implementation (FIXED)
Replicates all functionality from the JavaScript version
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import warnings
import math
from scipy.interpolate import interp1d, RegularGridInterpolator
from scipy.special import expit  # sigmoid function

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class FieldConfig:
    """Configuration for radiation field"""
    mode: str = "sym"  # "sym" or "asym"
    fs_x: float = 10.0  # symmetric field size X (cm)
    fs_y: float = 10.0  # symmetric field size Y (cm)
    jaw_x1: float = -5.0  # left jaw position (cm)
    jaw_x2: float = 5.0   # right jaw position (cm)
    jaw_y1: float = -5.0  # bottom jaw position (cm)
    jaw_y2: float = 5.0   # top jaw position (cm)

    @property
    def total_width_x(self) -> float:
        return abs(self.jaw_x2 - self.jaw_x1)

    @property
    def total_height_y(self) -> float:
        return abs(self.jaw_y2 - self.jaw_y1)

    @property
    def field_center_x(self) -> float:
        return (self.jaw_x1 + self.jaw_x2) / 2

    @property
    def field_center_y(self) -> float:
        return (self.jaw_y1 + self.jaw_y2) / 2

    @property
    def is_symmetric(self) -> bool:
        if self.mode == "sym":
            return True
        # For asymmetric mode, check if jaws are centered
        return abs(self.jaw_x1 + self.jaw_x2) < 0.01 and abs(self.jaw_y1 + self.jaw_y2) < 0.01


class EnergyType(Enum):
    MV6 = "6MV"
    MV10 = "10MV"
    FFF6 = "6FFF"
    FFF10 = "10FFF"


class DetectorType(Enum):
    ION = "ion"
    DIODE = "diode"


class ScanType(Enum):
    PDD = "pdd"
    PROFILE = "profile"


class PlotMode(Enum):
    NORMALIZED = "norm"
    CURRENT = "na"
    CHARGE = "nc"


# ============================================================================
# CSV Data Loaders
# ============================================================================

def parse_csv_data(csv_text: str) -> Tuple[List[float], Dict[float, Tuple[np.ndarray, np.ndarray]]]:
    """
    Parse CSV data for PDD or profile measurements

    Format expected:
    - First column: depth/position values
    - First row: field sizes (e.g., "2x2", "5x5", or just numbers)
    - Values: measured dose/OAR values

    Returns:
        fields_cm: List of field sizes
        series: Dict mapping field size to (x_values, y_values)
    """
    lines = [l.strip() for l in csv_text.strip().split('\n') if l.strip()]
    if len(lines) < 2:
        raise ValueError("CSV must have at least header and one data row")

    # Parse header
    header = [h.strip() for h in lines[0].split(',')]

    # Parse field sizes from header (skip first column which is coordinate)
    fields_cm = []
    for h in header[1:]:
        fs = parse_field_size_cm(h)
        if np.isfinite(fs):
            fields_cm.append(fs)

    if not fields_cm:
        raise ValueError("No valid field sizes found in header")

    # Initialize series
    series = {fs: ([], []) for fs in fields_cm}

    # Parse data rows
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(',')]
        if not parts:
            continue

        # Parse coordinate value
        raw_coord = parse_float(parts[0])
        if not np.isfinite(raw_coord):
            continue

        # Convert to cm (handles mm vs cm)
        coord_cm = coord_to_cm(raw_coord, header[0])

        # Parse values for each field
        for c in range(1, min(len(parts), len(fields_cm) + 1)):
            fs = fields_cm[c - 1]
            val = parse_float(parts[c])
            if np.isfinite(val):
                x_list, y_list = series[fs]
                x_list.append(coord_cm)
                y_list.append(val)

    # Convert to numpy arrays and sort
    result_series = {}
    for fs in fields_cm:
        x_list, y_list = series[fs]
        if x_list:
            sorted_indices = np.argsort(x_list)
            result_series[fs] = (
                np.array(x_list)[sorted_indices],
                np.array(y_list)[sorted_indices]
            )
        else:
            result_series[fs] = (np.array([]), np.array([]))

    return fields_cm, result_series


def parse_field_size_cm(header: str) -> float:
    """Parse field size from header like '10x10', '10X10', '10x10 cm', '10x10 mm'"""
    s = header.lower().strip()

    # Try to extract numbers like "10x10"
    import re
    match = re.search(r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)', s)
    if match:
        a = float(match.group(1))
        b = float(match.group(2))
        eq = np.sqrt(a * b)

        # Convert mm to cm if needed
        if 'mm' in s and 'cm' not in s:
            return eq / 10.0
        return eq

    # Try plain number
    try:
        val = float(s)
        # If value seems like mm (large number), convert
        if val > 50 and 'mm' in s:
            return val / 10.0
        return val
    except ValueError:
        return np.nan


def coord_to_cm(value: float, header: str) -> float:
    """Convert coordinate to cm based on header hint"""
    s = header.lower()
    if 'mm' in s and 'cm' not in s:
        return value / 10.0
    return value


def parse_float(v: str) -> float:
    """Safe float parsing"""
    try:
        return float(v.strip())
    except (ValueError, AttributeError):
        return np.nan


# ============================================================================
# Output Factor Table
# ============================================================================

class OutputFactorTable:
    """2D output factor table with bilinear interpolation"""

    def __init__(self, x_sizes: List[float], y_sizes: List[float], of_values: np.ndarray):
        """
        Args:
            x_sizes: X field sizes (cm), sorted
            y_sizes: Y field sizes (cm), sorted
            of_values: 2D array of output factors (y_idx, x_idx)
        """
        self.x_sizes = np.array(x_sizes)
        self.y_sizes = np.array(y_sizes)
        self.of_values = np.array(of_values)

        # Create interpolator
        self.interpolator = RegularGridInterpolator(
            (self.y_sizes, self.x_sizes),
            self.of_values,
            method='linear',
            bounds_error=False,
            fill_value=None
        )

    @classmethod
    def from_csv(cls, csv_text: str) -> 'OutputFactorTable':
        """Load output factor table from CSV"""
        lines = [l.strip() for l in csv_text.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            raise ValueError("CSV must have at least header and one data row")

        # Parse header - first cell is label, rest are X sizes
        header = [h.strip() for h in lines[0].split(',')]
        x_sizes = []
        for h in header[1:]:
            fs = parse_field_size_cm(h)
            if np.isfinite(fs):
                x_sizes.append(fs)

        if not x_sizes:
            raise ValueError("No valid X sizes found in header")

        # Parse data rows
        y_sizes = []
        of_rows = []

        for line in lines[1:]:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue

            y = parse_float(parts[0])
            if not np.isfinite(y):
                continue

            values = []
            for c in range(1, min(len(parts), len(x_sizes) + 1)):
                v = parse_float(parts[c])
                if np.isfinite(v):
                    values.append(v)
                else:
                    values.append(np.nan)

            if len(values) >= 2:
                y_sizes.append(y)
                of_rows.append(values)

        if len(y_sizes) < 2:
            raise ValueError("Not enough valid rows in OF table")

        # Ensure we have the right number of columns
        of_array = np.array(of_rows)

        return cls(x_sizes, y_sizes, of_array)

    def get_of(self, x_cm: float, y_cm: float) -> float:
        """Get output factor for given field size (bilinear interpolation)"""
        # Clamp to valid range
        x = np.clip(x_cm, self.x_sizes[0], self.x_sizes[-1])
        y = np.clip(y_cm, self.y_sizes[0], self.y_sizes[-1])

        return float(self.interpolator([[y, x]])[0])


# ============================================================================
# Interpolation Utilities
# ============================================================================

def linear_interp(x: float, xs: np.ndarray, ys: np.ndarray) -> float:
    """Linear interpolation with extrapolation"""
    if len(xs) == 0:
        return np.nan

    # Create interpolator
    interp = interp1d(xs, ys, kind='linear', bounds_error=False, fill_value=(ys[0], ys[-1]))
    return float(interp(x))


def find_bracket(arr: np.ndarray, x: float) -> Tuple[int, int, float]:
    """Find bracketing indices and interpolation factor"""
    if len(arr) == 0:
        return (0, 0, 0.0)

    if x <= arr[0]:
        return (0, 0, 0.0)
    if x >= arr[-1]:
        return (len(arr) - 1, len(arr) - 1, 0.0)

    lo, hi = 0, len(arr) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if arr[mid] <= x:
            lo = mid
        else:
            hi = mid

    x0, x1 = arr[lo], arr[hi]
    t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
    return (lo, hi, t)


def mayneord_factor(ssd_ref: float, ssd_user: float, dmax: float, depth: float) -> float:
    """Calculate Mayneord F factor for SSD correction"""
    if not all(np.isfinite([ssd_ref, ssd_user, dmax, depth])):
        return 1.0
    if ssd_user <= 0:
        return 1.0

    a = (ssd_user + dmax) / (ssd_ref + dmax)
    b = (ssd_ref + depth) / (ssd_user + depth)
    return (a * a) * (b * b)


# ============================================================================
# PDD Data Class
# ============================================================================

class PDDData:
    """Percentage Depth Dose data for a given energy"""

    def __init__(self, csv_text: str, ssd_ref: float = 100.0, dmax_default: float = 1.5):
        self.ssd_ref = ssd_ref
        self.dmax_default = dmax_default

        # Parse CSV
        self.fields_cm, self.series = parse_csv_data(csv_text)

        # Pre-compute dmax for each field size
        self.dmax_by_field = {}
        for fs in self.fields_cm:
            xs, ys = self.series[fs]
            if len(xs) > 0:
                max_idx = np.argmax(ys)
                self.dmax_by_field[fs] = xs[max_idx]
            else:
                self.dmax_by_field[fs] = dmax_default

    def get_pdd(self, depth_cm: float, fs_eq_cm: float, ssd_cm: Optional[float] = None) -> float:
        """Get PDD at given depth and field size"""
        if ssd_cm is None:
            ssd_cm = self.ssd_ref

        # Interpolate over field size
        def value_at_fs(fs):
            if fs not in self.series:
                return np.nan
            xs, ys = self.series[fs]
            return linear_interp(depth_cm, xs, ys)

        pdd_ref = self._interp_over_field_size(fs_eq_cm, value_at_fs)

        if not np.isfinite(pdd_ref):
            return np.nan

        # Apply SSD correction if needed
        if abs(ssd_cm - self.ssd_ref) < 1e-9:
            return pdd_ref

        dmax = self.get_dmax(fs_eq_cm)
        return pdd_ref * mayneord_factor(self.ssd_ref, ssd_cm, dmax, depth_cm)

    def get_dmax(self, fs_eq_cm: float) -> float:
        """Get dmax for given field size"""
        def value_at_fs(fs):
            return self.dmax_by_field.get(fs, self.dmax_default)

        return self._interp_over_field_size(fs_eq_cm, value_at_fs)

    def _interp_over_field_size(self, fs_cm: float, value_func: Callable) -> float:
        """Interpolate a function over field sizes"""
        if not self.fields_cm:
            return np.nan

        if fs_cm <= self.fields_cm[0]:
            return value_func(self.fields_cm[0])
        if fs_cm >= self.fields_cm[-1]:
            return value_func(self.fields_cm[-1])

        lo_idx, hi_idx, t = find_bracket(np.array(self.fields_cm), fs_cm)
        f1 = self.fields_cm[lo_idx]
        f2 = self.fields_cm[hi_idx]

        v1 = value_func(f1)
        v2 = value_func(f2)

        if not np.isfinite(v1):
            return v2
        if not np.isfinite(v2):
            return v1

        return v1 + t * (v2 - v1)


# ============================================================================
# Profile Data Class
# ============================================================================

class ProfileData:
    """Off-Axis Ratio (profile) data for a given energy"""

    def __init__(self, profiles_by_depth: Dict[float, str], ssd_ref: float = 100.0):
        """
        Args:
            profiles_by_depth: Dict mapping depth (cm) to CSV file path or content
            ssd_ref: Reference SSD (cm)
        """
        self.ssd_ref = ssd_ref
        self.profiles = {}  # depth -> (fields_cm, series)
        self.available_depths = []

        for depth, csv_content in profiles_by_depth.items():
            # Parse CSV content
            if isinstance(csv_content, str):
                # Assume it's file content
                fields_cm, series = parse_csv_data(csv_content)
            else:
                fields_cm, series = csv_content

            self.profiles[depth] = (fields_cm, series)
            self.available_depths.append(depth)

        self.available_depths = sorted(self.available_depths)

    def get_oar(self, off_axis_cm: float, fs_cm: float, depth_cm: float) -> float:
        """Get OAR at given off-axis distance, field size, and depth"""
        # Find bracketing depths
        if depth_cm <= self.available_depths[0]:
            return self._sample_at_depth(off_axis_cm, fs_cm, self.available_depths[0])
        if depth_cm >= self.available_depths[-1]:
            return self._sample_at_depth(off_axis_cm, fs_cm, self.available_depths[-1])

        # Find bracketing depths
        d1 = self.available_depths[0]
        d2 = self.available_depths[1]
        for i in range(len(self.available_depths) - 1):
            a = self.available_depths[i]
            b = self.available_depths[i + 1]
            if a <= depth_cm <= b:
                d1, d2 = a, b
                break

        v1 = self._sample_at_depth(off_axis_cm, fs_cm, d1)
        v2 = self._sample_at_depth(off_axis_cm, fs_cm, d2)

        if not np.isfinite(v1):
            return v2
        if not np.isfinite(v2):
            return v1

        t = (depth_cm - d1) / (d2 - d1)
        return v1 + t * (v2 - v1)

    def _sample_at_depth(self, off_axis_cm: float, fs_cm: float, depth_cm: float) -> float:
        """Sample OAR at a specific depth"""
        if depth_cm not in self.profiles:
            return np.nan

        fields_cm, series = self.profiles[depth_cm]
        if not fields_cm:
            return np.nan

        # Interpolate over field size
        if fs_cm <= fields_cm[0]:
            xs, ys = series[fields_cm[0]]
            return linear_interp(off_axis_cm, xs, ys)
        if fs_cm >= fields_cm[-1]:
            xs, ys = series[fields_cm[-1]]
            return linear_interp(off_axis_cm, xs, ys)

        # Find bracketing field sizes
        lo_idx, hi_idx, t = find_bracket(np.array(fields_cm), fs_cm)
        f1 = fields_cm[lo_idx]
        f2 = fields_cm[hi_idx]

        # Scale off-axis distance for penumbra consistency
        x1 = off_axis_cm * (f1 / fs_cm)
        x2 = off_axis_cm * (f2 / fs_cm)

        xs1, ys1 = series[f1]
        xs2, ys2 = series[f2]

        v1 = linear_interp(x1, xs1, ys1)
        v2 = linear_interp(x2, xs2, ys2)

        if not np.isfinite(v1):
            return v2
        if not np.isfinite(v2):
            return v1

        return v1 + t * (v2 - v1)

    def get_available_field_sizes(self) -> List[float]:
        """Get all available field sizes from the shallowest depth"""
        if not self.available_depths:
            return []
        depth = self.available_depths[0]
        fields_cm, _ = self.profiles[depth]
        return fields_cm


# ============================================================================
# Main Dose Engine
# ============================================================================

class DoseEngine:
    """
    Medical Linear Accelerator Dose Engine

    Handles:
    - PDD, Profile, and Output Factor calculations
    - Symmetric and asymmetric fields
    - SSD corrections
    - Penumbra modeling
    """

    def __init__(
        self,
        pdd_data: PDDData,
        profile_data: ProfileData,
        of_table: OutputFactorTable,
        ssd_ref: float = 100.0,
        penumbra_width: float = 0.8,
        penumbra_steepness: float = 4.5
    ):
        """
        Args:
            pdd_data: PDD data object
            profile_data: Profile data object
            of_table: Output factor table
            ssd_ref: Reference SSD (cm)
            penumbra_width: Penumbra width in cm (for asymmetric fields)
            penumbra_steepness: Steepness of penumbra sigmoid
        """
        self.pdd = pdd_data
        self.profile = profile_data
        self.of_table = of_table
        self.ssd_ref = ssd_ref
        self.penumbra_width = penumbra_width
        self.penumbra_steepness = penumbra_steepness

    @classmethod
    def from_files(
        cls,
        pdd_csv: str,
        of_csv: str,
        profiles_by_depth: Dict[float, str],
        ssd_ref: float = 100.0,
        dmax_default: float = 1.5
    ) -> 'DoseEngine':
        """
        Create DoseEngine from CSV files

        Args:
            pdd_csv: Path or content of PDD CSV
            of_csv: Path or content of Output Factor CSV
            profiles_by_depth: Dict mapping depth to profile CSV path/content
            ssd_ref: Reference SSD
            dmax_default: Default dmax value
        """
        # Load PDD
        pdd_data = PDDData(pdd_csv, ssd_ref, dmax_default)

        # Load profiles
        profile_data = ProfileData(profiles_by_depth, ssd_ref)

        # Load OF table
        of_table = OutputFactorTable.from_csv(of_csv)

        return cls(pdd_data, profile_data, of_table, ssd_ref)

    # ========================================================================
    # Core Dose Calculation
    # ========================================================================

    def get_dose_at_point(
        self,
        x_cm: float = 0,
        y_cm: float = 0,
        depth_cm: float = 1.5,
        ssd_cm: float = 100.0,
        field: Optional[FieldConfig] = None
    ) -> float:
        """
        Calculate relative dose at a point

        Args:
            x_cm: X position relative to isocenter (cm)
            y_cm: Y position relative to isocenter (cm)
            depth_cm: Depth in water (cm)
            ssd_cm: Source-to-surface distance (cm)
            field: Field configuration (uses default symmetric if None)

        Returns:
            Relative dose (0-1 range, normalized to 1 at reference point)
        """
        if field is None:
            field = FieldConfig()

        # Calculate actual field dimensions
        actual_width_x = field.total_width_x
        actual_width_y = field.total_height_y
        fs_eq = np.sqrt(actual_width_x * actual_width_y)

        # Calculate OAR for both directions
        oar_x = self.get_oar_for_any_field(x_cm, field.jaw_x1, field.jaw_x2, depth_cm)
        oar_y = self.get_oar_for_any_field(y_cm, field.jaw_y1, field.jaw_y2, depth_cm)

        # Handle invalid OAR values
        oar_x_safe = max(0, oar_x) if np.isfinite(oar_x) else 1.0
        oar_y_safe = max(0, oar_y) if np.isfinite(oar_y) else 1.0

        # If both OARs are near 0, return 0
        if oar_x_safe < 0.001 and oar_y_safe < 0.001:
            return 0.0

        # Calculate PDD
        pdd_val = self.pdd.get_pdd(depth_cm, fs_eq, ssd_cm)

        if not np.isfinite(pdd_val):
            return np.nan

        # Output factor
        of = self.of_table.get_of(actual_width_x, actual_width_y)
        of_safe = of if np.isfinite(of) else 1.0

        # Final dose calculation
        return pdd_val * of_safe * oar_x_safe * oar_y_safe

    # ========================================================================
    # Asymmetric Field OAR Functions
    # ========================================================================

    def get_oar_for_any_field(
        self,
        off_axis_cm: float,
        jaw1: float,
        jaw2: float,
        depth_cm: float
    ) -> float:
        """Get OAR for symmetric or asymmetric field"""
        # Check if symmetric field
        is_symmetric = abs(jaw1 + jaw2) < 0.01

        if is_symmetric:
            field_width = abs(jaw2 - jaw1)
            return self.get_oar(off_axis_cm, field_width, depth_cm)
        else:
            return self.get_asymmetric_profile_optimized(off_axis_cm, jaw1, jaw2, depth_cm)

    def get_oar(self, off_axis_cm: float, field_width_cm: float, depth_cm: float) -> float:
        """Get OAR for symmetric field"""
        return self.profile.get_oar(off_axis_cm, field_width_cm, depth_cm)

    def get_asymmetric_profile_simple(
        self,
        position: float,
        jaw1: float,
        jaw2: float,
        depth_cm: float
    ) -> float:
        """
        Simple asymmetric profile: treat as blocked symmetric field

        This is the simplest approach - assumes the beam is symmetric and
        jaws just block part of it.
        """
        left_jaw = min(jaw1, jaw2)
        right_jaw = max(jaw1, jaw2)

        # Check if symmetric
        if abs(jaw1 + jaw2) < 0.01:
            field_width = right_jaw - left_jaw
            return self.get_oar(position, field_width, depth_cm) or 0.0

        # For asymmetric field: use full symmetric field based on max jaw
        max_jaw = max(abs(left_jaw), abs(right_jaw))
        full_field_size = 2 * max_jaw

        # Get OAR from full symmetric field
        full_oar = self.get_oar(position, full_field_size, depth_cm)
        if not np.isfinite(full_oar):
            return 0.0

        # Apply blocking factor
        blocking_factor = 1.0

        if position < left_jaw:
            # Blocked by left jaw
            distance = left_jaw - position
            blocking_factor = np.exp(-distance * 0.8)
        elif position > right_jaw:
            # Blocked by right jaw
            distance = position - right_jaw
            blocking_factor = np.exp(-distance * 0.8)

        return full_oar * blocking_factor

    def get_asymmetric_profile_direct(
        self,
        position: float,
        jaw1: float,
        jaw2: float,
        depth_cm: float
    ) -> float:
        """
        Direct asymmetric profile: treat left and right sides independently

        For points on left side, use left jaw distance to determine reference field.
        For points on right side, use right jaw distance.
        """
        left_jaw = min(jaw1, jaw2)
        right_jaw = max(jaw1, jaw2)

        # Check if symmetric
        if abs(jaw1 + jaw2) < 0.01:
            field_width = right_jaw - left_jaw
            return self.get_oar(position, field_width, depth_cm) or 0.0

        # Find nearest available field size
        available_sizes = self.profile.get_available_field_sizes()
        if not available_sizes:
            return self.get_asymmetric_profile_simple(position, jaw1, jaw2, depth_cm)

        if position <= 0:
            # Left side of beam center
            left_distance = abs(left_jaw)
            symmetric_field_size = 2 * left_distance

            # Find nearest available size
            nearest_size = min(available_sizes, key=lambda x: abs(x - symmetric_field_size))

            # Scale position
            scaled_position = position * (nearest_size / symmetric_field_size)

            oar = self.get_oar(scaled_position, nearest_size, depth_cm)
            return oar if np.isfinite(oar) else 0.0
        else:
            # Right side of beam center
            right_distance = abs(right_jaw)
            symmetric_field_size = 2 * right_distance

            # Find nearest available size
            nearest_size = min(available_sizes, key=lambda x: abs(x - symmetric_field_size))

            # Scale position
            scaled_position = position * (nearest_size / symmetric_field_size)

            oar = self.get_oar(scaled_position, nearest_size, depth_cm)
            return oar if np.isfinite(oar) else 0.0

    def get_asymmetric_profile_accurate(
        self,
        position: float,
        jaw1: float,
        jaw2: float,
        depth_cm: float
    ) -> float:
        """
        Accurate asymmetric profile with S-shaped penumbra

        Uses sigmoid function for realistic penumbra shape
        """
        left_jaw = min(jaw1, jaw2)
        right_jaw = max(jaw1, jaw2)

        # Check if symmetric
        if abs(jaw1 + jaw2) < 0.01:
            field_width = right_jaw - left_jaw
            return self.get_oar(position, field_width, depth_cm) or 0.0

        # For points inside the field, use direct approach
        if left_jaw <= position <= right_jaw:
            return self.get_asymmetric_profile_direct(position, jaw1, jaw2, depth_cm)

        # For points outside, use penumbra modeling
        # Determine which side we're on
        if position < left_jaw:
            # Left penumbra
            left_distance = abs(left_jaw)
            symmetric_field_size = 2 * left_distance

            # Get OAR at the jaw edge
            edge_oar = self.get_asymmetric_profile_direct(left_jaw, jaw1, jaw2, depth_cm)

            # Distance beyond jaw
            distance_beyond = left_jaw - position

            # Sigmoid function for penumbra
            # expit is the logistic sigmoid: 1/(1+exp(-x))
            # We want: 1 at jaw edge, 0 far outside
            # Scale so that 50% point is at half the penumbra width
            offset = self.penumbra_width * 0.5
            k = self.penumbra_steepness / self.penumbra_width

            # Normalize distance
            x = k * (distance_beyond - offset)
            sigmoid = 1.0 / (1.0 + np.exp(x))

            return edge_oar * sigmoid
        else:
            # Right penumbra
            right_distance = abs(right_jaw)
            symmetric_field_size = 2 * right_distance

            # Get OAR at the jaw edge
            edge_oar = self.get_asymmetric_profile_direct(right_jaw, jaw1, jaw2, depth_cm)

            # Distance beyond jaw
            distance_beyond = position - right_jaw

            # Sigmoid function
            offset = self.penumbra_width * 0.5
            k = self.penumbra_steepness / self.penumbra_width
            x = k * (distance_beyond - offset)
            sigmoid = 1.0 / (1.0 + np.exp(x))

            return edge_oar * sigmoid

    def get_asymmetric_profile_optimized(
        self,
        position: float,
        jaw1: float,
        jaw2: float,
        depth_cm: float
    ) -> float:
        """
        Optimized asymmetric profile combining direct and accurate methods

        For points inside field: use direct approach (more accurate to measured data)
        For points outside: use accurate approach with penumbra modeling
        """
        left_jaw = min(jaw1, jaw2)
        right_jaw = max(jaw1, jaw2)

        # Check if symmetric
        if abs(jaw1 + jaw2) < 0.01:
            field_width = right_jaw - left_jaw
            return self.get_oar(position, field_width, depth_cm) or 0.0

        # For points inside the field, use direct approach
        if left_jaw <= position <= right_jaw:
            return self.get_asymmetric_profile_direct(position, jaw1, jaw2, depth_cm)

        # For points outside, use accurate approach with penumbra
        return self.get_asymmetric_profile_accurate(position, jaw1, jaw2, depth_cm)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_available_field_sizes(self) -> List[float]:
        """Get all available field sizes from profile data"""
        return self.profile.get_available_field_sizes()

    def find_nearest_field_size(self, target_size: float) -> float:
        """Find nearest available field size"""
        available = self.get_available_field_sizes()
        if not available:
            return target_size
        return min(available, key=lambda x: abs(x - target_size))

    def test_asymmetric_profile(
        self,
        jaw1: float,
        jaw2: float,
        depth: float,
        step: float = 0.5,
        start: float = -12,
        end: float = 12
    ) -> List[Tuple[float, float]]:
        """Test asymmetric profile and return results"""
        left_jaw = min(jaw1, jaw2)
        right_jaw = max(jaw1, jaw2)
        field_center = (left_jaw + right_jaw) / 2
        is_symmetric = abs(jaw1 + jaw2) < 0.01

        print(f"\n=== Testing Profile ===")
        print(f"Jaws: [{jaw1}, {jaw2}]")
        print(f"Field: {left_jaw:.1f}cm to {right_jaw:.1f}cm")
        print(f"Width: {(right_jaw - left_jaw):.1f}cm")
        print(f"Field Center: {field_center:.1f}cm")
        print(f"Beam Center (Isocenter): 0cm")
        print(f"Symmetric: {'YES' if is_symmetric else 'NO'}")
        print(f"Depth: {depth}cm")
        print(f"\nPosition (cm)\tOAR")

        results = []
        pos = start
        while pos <= end + 0.001:
            oar = self.get_oar_for_any_field(pos, jaw1, jaw2, depth)
            results.append((pos, oar))

            # Add markers
            marker = ""
            if abs(pos) < 0.1:
                marker = " <- BEAM CENTER"
            elif abs(pos - left_jaw) < 0.1:
                marker = " <- LEFT JAW"
            elif abs(pos - right_jaw) < 0.1:
                marker = " <- RIGHT JAW"
            elif not is_symmetric and abs(pos - field_center) < 0.1:
                marker = " <- FIELD CENTER"

            # FIXED: Proper string formatting
            oar_str = f"{oar:.4f}" if np.isfinite(oar) else "NaN"
            print(f"{pos:8.1f}\t{oar_str}{marker}")
            pos += step

        return results

    def calibrate_penumbra(self, jaw1: float, jaw2: float, depth: float, measured_data: List[Tuple[float, float]]):
        """
        Calibrate penumbra parameters based on measured data

        Args:
            jaw1, jaw2: Jaw positions
            depth: Measurement depth
            measured_data: List of (position, measured_oar) tuples
        """
        print("\n=== Penumbra Calibration ===")

        # Test different penumbra parameters
        widths = [0.6, 0.7, 0.8, 0.9, 1.0]
        steepness = [3.5, 4.0, 4.5, 5.0, 5.5]

        best_width = self.penumbra_width
        best_steepness = self.penumbra_steepness
        best_error = float('inf')

        # Save original parameters
        original_width = self.penumbra_width
        original_steepness = self.penumbra_steepness

        left_jaw = min(jaw1, jaw2)
        right_jaw = max(jaw1, jaw2)

        for width in widths:
            for k in steepness:
                self.penumbra_width = width
                self.penumbra_steepness = k

                total_error = 0.0
                count = 0

                for pos, measured in measured_data:
                    # Only evaluate points in penumbra region
                    if pos < left_jaw - 1 or pos > right_jaw + 1:
                        continue

                    calculated = self.get_oar_for_any_field(pos, jaw1, jaw2, depth)
                    if np.isfinite(calculated) and np.isfinite(measured):
                        error = abs(calculated - measured)
                        total_error += error
                        count += 1

                if count > 0:
                    mse = total_error / count
                    if mse < best_error:
                        best_error = mse
                        best_width = width
                        best_steepness = k
                        print(f"Width: {width}cm, Steepness: {k}, MSE: {mse:.6f}")

        # Restore best parameters
        self.penumbra_width = best_width
        self.penumbra_steepness = best_steepness

        print(f"\nBest parameters: Width={best_width}cm, Steepness={best_steepness}, MSE={best_error:.6f}")


# ============================================================================
# Example Usage
# ============================================================================

def create_engine_from_files_example():
    """Example: Create dose engine from CSV files"""

    # Example file paths (replace with your actual CSV files)
    pdd_csv = """Depth (cm),2x2,5x5,10x10,20x20
0,20,25,30,35
0.5,40,45,50,55
1,70,75,80,85
1.5,100,100,100,100
2,95,98,99,100
5,80,85,90,95
10,60,65,70,80
20,30,35,40,50
30,15,20,25,35"""

    of_csv = """X/Y,2,5,10,20
2,0.8,0.85,0.9,0.95
5,0.85,0.9,0.95,1.0
10,0.9,0.95,1.0,1.05
20,0.95,1.0,1.05,1.1"""

    profiles_by_depth = {
        1.5: """Off-axis (cm),2x2,5x5,10x10,20x20
0,1,1,1,1
1,0.95,0.98,0.99,1
2,0.8,0.9,0.95,0.98
3,0.5,0.7,0.85,0.95
4,0.2,0.4,0.7,0.9
5,0.05,0.2,0.5,0.85
6,0,0.05,0.3,0.75
7,0,0,0.15,0.6
8,0,0,0.05,0.4
9,0,0,0,0.2
10,0,0,0,0.05""",

        10.0: """Off-axis (cm),2x2,5x5,10x10,20x20
0,1,1,1,1
1,0.96,0.98,0.99,1
2,0.85,0.92,0.96,0.98
3,0.6,0.75,0.88,0.95
4,0.3,0.5,0.75,0.9
5,0.1,0.25,0.55,0.85
6,0,0.1,0.35,0.75
7,0,0,0.2,0.6
8,0,0,0.08,0.4
9,0,0,0,0.2
10,0,0,0,0.05"""
    }

    # Create engine
    engine = DoseEngine.from_files(
        pdd_csv=pdd_csv,
        of_csv=of_csv,
        profiles_by_depth=profiles_by_depth,
        ssd_ref=100.0,
        dmax_default=1.5
    )

    return engine


def demo_symmetric_field():
    """Demonstrate symmetric field calculations"""
    engine = create_engine_from_files_example()

    field = FieldConfig(mode="sym", fs_x=10.0, fs_y=10.0)

    print("\n=== Symmetric Field Demo ===")
    print(f"Field: {field.fs_x} x {field.fs_y} cm")

    # Calculate dose at various points
    points = [
        (0, 0, 1.5, "Center, dmax"),
        (0, 0, 10.0, "Center, 10cm depth"),
        (3, 0, 10.0, "3cm off-axis, 10cm depth"),
        (5, 0, 10.0, "5cm off-axis (penumbra), 10cm depth"),
        (8, 0, 10.0, "8cm off-axis (outside field), 10cm depth"),
    ]

    for x, y, depth, desc in points:
        dose = engine.get_dose_at_point(x, y, depth, field=field)
        print(f"  {desc}: {dose:.4f}")


def demo_asymmetric_field():
    """Demonstrate asymmetric field calculations"""
    engine = create_engine_from_files_example()

    # Asymmetric field: X1=5, X2=10 (field center at 2.5cm)
    field = FieldConfig(
        mode="asym",
        jaw_x1=-5.0,   # Left jaw at -5cm
        jaw_x2=10.0,   # Right jaw at +10cm
        jaw_y1=-5.0,
        jaw_y2=5.0
    )

    print("\n=== Asymmetric Field Demo ===")
    print(f"Jaws: X[{field.jaw_x1:.1f}, {field.jaw_x2:.1f}] cm")
    print(f"Field Center X: {field.field_center_x:.1f} cm")
    print(f"Field Width: {field.total_width_x:.1f} cm")

    # Calculate dose at various points
    points = [
        (0, 0, 1.5, "Beam center (isocenter), dmax"),
        (field.field_center_x, 0, 1.5, "Field center, dmax"),
        (3, 0, 1.5, "3cm (between isocenter and field center), dmax"),
        (8, 0, 1.5, "8cm (in field, right side), dmax"),
        (-3, 0, 1.5, "-3cm (outside left jaw), dmax"),
    ]

    for x, y, depth, desc in points:
        dose = engine.get_dose_at_point(x, y, depth, field=field)
        print(f"  {desc}: {dose:.4f}")


def demo_scan_simulation():
    """Simulate a profile scan across an asymmetric field"""
    engine = create_engine_from_files_example()

    # Asymmetric field
    field = FieldConfig(
        mode="asym",
        jaw_x1=-5.0,
        jaw_x2=10.0,
        jaw_y1=-5.0,
        jaw_y2=5.0
    )

    depth = 10.0  # cm

    print("\n=== Profile Scan Simulation ===")
    print(f"Scanning X-axis at depth {depth}cm")
    print(f"Jaws: [{field.jaw_x1:.1f}, {field.jaw_x2:.1f}] cm")
    print(f"Field center: {field.field_center_x:.1f} cm")
    print("\nPos (cm)\tDose")

    positions = np.arange(-12, 13, 0.5)
    for x in positions:
        dose = engine.get_dose_at_point(x, 0, depth, field=field)
        # Limit bar length for readability
        bar_length = min(int(dose * 50), 80)
        bar = "#" * bar_length
        print(f"{x:6.1f}\t{dose:.4f}  {bar}")


if __name__ == "__main__":
    print("=" * 60)
    print("Medical Linear Accelerator Dose Engine - Python Demo")
    print("=" * 60)

    demo_symmetric_field()
    demo_asymmetric_field()
    demo_scan_simulation()

    # Test asymmetric profile
    engine = create_engine_from_files_example()
    print("\n" + "=" * 60)
    engine.test_asymmetric_profile(jaw1=-5, jaw2=10, depth=10.0, step=1.0)