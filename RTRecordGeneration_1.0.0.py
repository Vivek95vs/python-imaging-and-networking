import sys
import os
import pyodbc
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QTextEdit, QProgressBar, QGroupBox, QFormLayout,
                             QMessageBox, QDateEdit, QTabWidget, QFileDialog,
                             QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QSplitter)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QDateTime
from PyQt5.QtGui import QFont, QTextCursor, QColor
from datetime import datetime, timedelta
import logging
import traceback
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import socket
import re

# ==================== DICOM UID Constants ====================
RT_RECORD_STORAGE_UID = "1.2.840.10008.5.1.4.1.1.481.4"
RT_PLAN_STORAGE_UID = "1.2.840.10008.5.1.4.1.1.481.5"


# ==================== ODBC Driver Helper ====================
def get_available_odbc_drivers():
    """Get list of available ODBC drivers"""
    drivers = []
    try:
        drivers = pyodbc.drivers()
    except:
        pass
    return drivers


def get_sql_server_driver():
    """Get the best available SQL Server ODBC driver"""
    drivers = get_available_odbc_drivers()

    # Preferred drivers in order
    preferred_drivers = [
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "ODBC Driver 11 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server Native Client 10.0",
        "SQL Server"
    ]

    for preferred in preferred_drivers:
        for driver in drivers:
            if preferred.lower() in driver.lower():
                return driver

    # Return first SQL Server compatible driver if found
    for driver in drivers:
        if "sql" in driver.lower() or "server" in driver.lower():
            return driver

    return None


# ==================== Data Models ====================
@dataclass
class PatientInfo:
    """Patient information model from WORKS table"""
    patient_name: str = ""
    patient_id: str = ""
    birth_date: str = ""
    sex: str = ""
    study_date: str = ""
    study_time: str = ""
    accession_number: str = ""
    referring_physician: str = ""
    study_instance_uid: str = ""
    study_id: str = ""
    modality: str = "RTRECORD"
    series_description: str = ""
    study_description: str = ""
    operators_name: str = ""
    series_number: str = ""
    manufacturer: str = ""
    manufacturer_model_name: str = ""
    device_serial_number: str = ""
    current_treatment_status: str = ""
    verification_status: str = ""
    work_ref_id: str = ""
    site_ref_id: str = ""
    phase_no: str = ""


@dataclass
class FractionInfo:
    """Fraction information from TreatmentSchedulings table"""
    fraction_number: str = ""
    fraction_group: str = ""
    treatment_date: str = ""
    treatment_time: str = ""
    treatment_datetime: str = ""  # Full datetime for matching
    work_ref_id: str = ""
    site_ref_id: str = ""
    approval_status: str = ""
    treatment_status: str = ""
    study_instance_uid: str = ""


@dataclass
class BeamInfo:
    """Beam information model"""
    beam_number: str = ""
    radiation_type: str = ""
    number_of_wedges: int = 0
    number_of_compensators: int = 0
    number_of_boli: int = 0
    number_of_blocks: int = 0
    number_of_control_points: int = 0
    primary_dosimeter_unit: str = ""
    beam_name: str = ""
    beam_id: str = ""
    beam_sequence_ref: str = ""
    wedge_sequences: List[Dict] = field(default_factory=list)


@dataclass
class ControlPointInfo:
    """Control point information model with proper numeric types"""
    control_point_index: int = 0
    cumulative_meterset_weight: float = 0.0
    nominal_beam_energy: float = 6.0
    dose_rate_set: float = 0.0
    gantry_angle: float = 0.0
    gantry_rotation_direction: str = "NONE"
    beam_limiting_device_angle: float = 0.0
    beam_limiting_device_rotation_direction: str = "NONE"
    patient_support_angle: float = 0.0
    patient_support_rotation_direction: str = "NONE"
    table_top_eccentric_angle: float = 0.0
    table_top_eccentric_rotation_direction: str = "NONE"
    table_top_vertical_position: float = 0.0
    table_top_longitudinal_position: float = 0.0
    table_top_lateral_position: float = 0.0
    table_top_pitch_angle: float = 0.0
    table_top_pitch_rotation_direction: str = "NONE"
    table_top_roll_angle: float = 0.0
    table_top_roll_rotation_direction: str = "NONE"
    treatment_control_point_date: str = ""
    treatment_control_point_time: str = ""
    treatment_control_point_datetime: str = ""  # Full datetime for matching
    specified_meterset: float = 0.0
    delivered_meterset: float = 0.0
    dose_rate_delivered: float = 0.0
    source_to_surface_distance: float = 0.0
    isocenter_position: str = ""
    beam_sequence_ref: str = ""
    asymx_positions: str = ""
    asymy_positions: str = ""
    mlcx_positions: str = ""


# ==================== Logging Handler ====================
class QTextEditLogger(logging.Handler):
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.text_edit.append(msg)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_edit.setTextCursor(cursor)


# ==================== Database Manager ====================
class DatabaseManager:
    """Manages all database operations"""

    def __init__(self, logger=None):
        self.service_conn = None
        self.treatment_conn = None
        self.logger = logger or print
        self.driver_name = None

    def log(self, message, level="INFO"):
        if self.logger:
            self.logger(message, level)

    def get_driver(self):
        """Get the best available SQL Server driver"""
        if self.driver_name:
            return self.driver_name

        self.driver_name = get_sql_server_driver()
        if not self.driver_name:
            self.log("No SQL Server ODBC driver found!", "ERROR")
            self.log("Please install ODBC Driver 17 for SQL Server from:", "ERROR")
            self.log("https://go.microsoft.com/fwlink/?linkid=2222570", "ERROR")
            return None

        self.log(f"Using ODBC Driver: {self.driver_name}")
        return self.driver_name

    def connect(self, server_ip, username=None, password=None, trusted=False) -> bool:
        """Establish database connections"""
        try:
            driver = self.get_driver()
            if not driver:
                return False

            self.log(f"Connecting to SQL Server at IP: {server_ip}")

            # Test TCP connection
            if not self._test_tcp_connection(server_ip):
                return False

            # Connect to service database
            if not self._connect_service_db(server_ip, username, password, trusted, driver):
                return False

            # Connect to treatment database
            if not self._connect_treatment_db(server_ip, username, password, trusted, driver):
                return False

            return True

        except Exception as e:
            self.log(f"Connection error: {str(e)}", "ERROR")
            return False

    def _test_tcp_connection(self, server_ip: str) -> bool:
        """Test TCP connection to SQL Server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((server_ip, 1433))
            sock.close()

            if result == 0:
                self.log(f"✓ TCP connection to {server_ip}:1433 successful")
                return True
            else:
                self.log(f"✗ TCP connection failed", "ERROR")
                return False
        except Exception as e:
            self.log(f"TCP connection test error: {str(e)}", "ERROR")
            return False

    def _get_connection_string(self, driver, server: str, database: str, username=None, password=None,
                               trusted=False) -> str:
        """Build ODBC connection string with dynamic driver"""
        server_formatted = server.strip()
        if trusted:
            return f"DRIVER={{{driver}}};SERVER={server_formatted};DATABASE={database};Trusted_Connection=yes;"
        else:
            return f"DRIVER={{{driver}}};SERVER={server_formatted};DATABASE={database};UID={username};PWD={password};"

    def _connect_service_db(self, server_ip: str, username=None, password=None, trusted=False, driver=None) -> bool:
        """Connect to CCB_Service database"""
        try:
            if trusted:
                conn_str = self._get_connection_string(driver, server_ip, "CCB_Service", trusted=True)
            else:
                conn_str = self._get_connection_string(driver, server_ip, "CCB_Service", username, password)

            self.service_conn = pyodbc.connect(conn_str, timeout=30, autocommit=True)
            self.log("✓ Connected to CCB_Service database")
            return True
        except Exception as e:
            self.log(f"✗ Failed to connect to CCB_Service: {str(e)}", "ERROR")
            return False

    def _connect_treatment_db(self, server_ip: str, username=None, password=None, trusted=False, driver=None) -> bool:
        """Connect to treatment database"""
        try:
            # Get connection string from service database
            cursor = self.service_conn.cursor()
            cursor.execute("SELECT ConnectionStringTreatment FROM ConfigurationModels")
            row = cursor.fetchone()

            if not row:
                self.log("✗ No connection string found in ConfigurationModels", "ERROR")
                return False

            conn_string = self._parse_connection_string(row[0])
            database = conn_string.get('initial catalog', 'CCB_Treatment_4_0_0')

            self.log(f"Connecting to treatment database: {database}")

            if trusted:
                treatment_conn_str = self._get_connection_string(driver, server_ip, database, trusted=True)
            else:
                treatment_conn_str = self._get_connection_string(
                    driver, server_ip, database,
                    conn_string.get('user id', username),
                    conn_string.get('password', password)
                )

            self.treatment_conn = pyodbc.connect(treatment_conn_str, timeout=30, autocommit=True)
            self.log("✓ Connected to treatment database")
            return True

        except Exception as e:
            self.log(f"✗ Failed to connect to treatment database: {str(e)}", "ERROR")
            return False

    def _parse_connection_string(self, conn_string: str) -> Dict[str, str]:
        """Parse database connection string"""
        result = {}
        parts = conn_string.split(';')
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                result[key.lower().strip()] = value.strip()
        return result

    def close(self):
        """Close database connections"""
        try:
            if self.service_conn:
                self.service_conn.close()
            if self.treatment_conn:
                self.treatment_conn.close()
            self.log("Database connections closed")
        except Exception as e:
            self.log(f"Error closing connections: {str(e)}", "ERROR")


# ==================== Data Fetcher ====================
class RTRecordDataFetcher:
    """Fetches all data needed for RT Record generation using column names"""

    def __init__(self, db_manager: DatabaseManager, logger=None):
        self.db = db_manager
        self.logger = logger or print

    def log(self, message, level="INFO"):
        if self.logger:
            self.logger(message, level)

    def get_fractions_in_date_range(self, start_date: str, end_date: str) -> List[FractionInfo]:
        """Get all fractions with treatment dates between start_date and end_date"""
        fractions = []
        try:
            cursor = self.db.treatment_conn.cursor()

            # Query TreatmentSchedulings for fractions in date range
            query = """
                SELECT Id, SiteRefId, PhaseNum, FractionNumber, FractionGroup, 
                       ApprovalStatus, CurrentTreatmentStatus30080200, TreatmentDate,
                       StudyInstanceUid0020000D, WorkRefId, ImportStatus, 
                       RTRecordStatus, TokenNumber, CopyStatus
                FROM TreatmentSchedulings
                WHERE CAST(TreatmentDate AS DATE) BETWEEN ? AND ?
                ORDER BY TreatmentDate, WorkRefId, FractionNumber
            """
            cursor.execute(query, (start_date, end_date))

            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()

            self.log(f"Found {len(rows)} treatment records between {start_date} and {end_date}")

            for row in rows:
                row_dict = dict(zip(columns, row))

                # Parse treatment date and time
                treatment_datetime = row_dict.get('TreatmentDate', '')
                treatment_date = ''
                treatment_time = ''
                treatment_datetime_str = ''

                if treatment_datetime:
                    # Store the full datetime string for matching
                    if hasattr(treatment_datetime, 'strftime'):
                        # It's a datetime object
                        treatment_datetime_str = treatment_datetime.strftime('%Y-%m-%d %H:%M:%S')
                        treatment_date = treatment_datetime.strftime('%Y-%m-%d')
                        treatment_time = treatment_datetime.strftime('%H:%M:%S')
                    else:
                        # It's already a string
                        treatment_datetime_str = str(treatment_datetime)
                        parts = str(treatment_datetime).split()
                        if len(parts) >= 2:
                            treatment_date = parts[0]
                            treatment_time = parts[1].split('.')[0][:8]

                fraction = FractionInfo(
                    fraction_number=str(row_dict.get('FractionNumber', '')),
                    fraction_group=str(row_dict.get('FractionGroup', '')),
                    treatment_date=treatment_date,
                    treatment_time=treatment_time,
                    treatment_datetime=treatment_datetime_str,
                    work_ref_id=str(row_dict.get('WorkRefId', '')),
                    site_ref_id=str(row_dict.get('SiteRefId', '')),
                    approval_status=str(row_dict.get('ApprovalStatus', '')),
                    treatment_status=str(row_dict.get('CurrentTreatmentStatus30080200', '')),
                    study_instance_uid=str(row_dict.get('StudyInstanceUid0020000D', ''))
                )

                fractions.append(fraction)

            return fractions

        except Exception as e:
            self.log(f"Error getting fractions in date range: {str(e)}", "ERROR")
            return []

    def get_patient_info_from_work(self, work_ref_id: str) -> Optional[PatientInfo]:
        """Get patient information from WORKS table using WorkRefId"""
        try:
            cursor = self.db.treatment_conn.cursor()
            cursor.execute("SELECT * FROM WORKS WHERE Id = ?", (work_ref_id,))

            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()

            if not row:
                self.log(f"  No work details found for WorkRefId: {work_ref_id}", "WARNING")
                return None

            work = dict(zip(columns, row))

            # Parse patient information
            info = PatientInfo()

            # Basic patient info
            info.patient_name = str(work.get('PatientName00100010', ''))
            info.patient_id = str(work.get('PatientId00100020', ''))
            info.sex = str(work.get('PatientSex00100040', ''))
            info.accession_number = str(work.get('AccessionNumber00080050', ''))
            info.referring_physician = str(work.get('ReferringPhysicianName00080090', ''))

            # Study information
            info.study_instance_uid = str(work.get('StudyInstanceUid0020000D', generate_uid()))
            info.study_id = str(work.get('StudyId00200010', '')).replace('RP', 'RTb')
            info.series_description = str(work.get('SeriesDescription0008103E', ''))
            info.study_description = str(work.get('StudyDescription00081030', ''))
            info.operators_name = str(work.get('OperatorName00081070', ''))
            info.series_number = str(work.get('SeriesNumber00200011', ''))

            # Equipment information
            info.manufacturer = str(work.get('Manufacturer00080070', ''))
            info.manufacturer_model_name = str(work.get('ManufacturerModelName00081090', ''))
            info.device_serial_number = str(work.get('DeviceSerialNumber00181000', ''))

            # Treatment status
            info.verification_status = str(work.get('TreatmentVerificationStatus3008002C', ''))

            # Parse patient birth date
            dob = work.get('PatientBirthDateTime0010003000100032', '')
            if dob:
                if hasattr(dob, 'strftime'):
                    info.birth_date = dob.strftime('%Y%m%d')
                else:
                    info.birth_date = str(dob).split('T')[0].replace('-', '')

            # Parse study date/time
            study_dt = work.get('StudyDateTime0008002000080030', '')
            if study_dt:
                if hasattr(study_dt, 'strftime'):
                    info.study_date = study_dt.strftime('%Y%m%d')
                    info.study_time = study_dt.strftime('%H%M%S')
                else:
                    parts = str(study_dt).split('T')
                    if len(parts) >= 2:
                        info.study_date = parts[0].replace('-', '')
                        info.study_time = parts[1].replace(':', '').split('.')[0][:6]

            # Additional fields
            info.work_ref_id = work_ref_id
            info.site_ref_id = str(work.get('SiteRefId', ''))
            info.phase_no = str(work.get('PhaseNo', ''))

            return info

        except Exception as e:
            self.log(f"Error getting patient info for WorkRefId {work_ref_id}: {str(e)}", "ERROR")
            return None

    def get_control_points_for_fraction(self, work_ref_id: str, table_name: str, fraction_datetime: str) -> Dict[
        str, List[ControlPointInfo]]:
        """
        Get control points grouped by BeamSequence300A00B0 for a specific WorkRefId and fraction datetime
        """
        control_points_by_beam = {}

        try:
            cursor = self.db.treatment_conn.cursor()

            if not fraction_datetime:
                self.log(f"  Warning: No datetime provided for fraction", "WARNING")
                return {}

            # Extract date part only (YYYY-MM-DD)
            date_part = fraction_datetime.split()[0] if ' ' in fraction_datetime else fraction_datetime
            self.log(f"  Looking for control points in {table_name} with date: {date_part}")

            # Also create a version with colons for the secondary table
            date_with_colons = date_part.replace('-', ':')
            self.log(f"  Also trying date with colons: {date_with_colons}")

            # First, check total count for this WorkRefId
            count_query = f"SELECT COUNT(*) FROM {table_name} WHERE WorkRefId = ?"
            cursor.execute(count_query, (work_ref_id,))
            total_count = cursor.fetchone()[0]
            self.log(f"  Total records in {table_name} for WorkRefId {work_ref_id}: {total_count}")

            if total_count == 0:
                self.log(f"  No records found in {table_name} for WorkRefId {work_ref_id}")
                return {}

            # Method 1: Try with hyphens format (for primary table)
            try:
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE WorkRefId = ? 
                    AND CONVERT(date, TreatmentCPDateTime30080024) = CONVERT(date, ?)
                    ORDER BY BeamSequence300A00B0, ControlPointIndex300A0112
                """
                cursor.execute(query, (work_ref_id, fraction_datetime))

                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                self.log(f"  Method 1 (CONVERT with hyphens): Found {len(rows)} control points in {table_name}")

                if len(rows) > 0:
                    return self._process_control_point_rows(rows, columns, control_points_by_beam)
            except Exception as e:
                self.log(f"  Method 1 failed: {str(e)}", "WARNING")

            # Method 2: Try with colons format (for secondary table)
            try:
                # For the secondary table, we need to handle the colon format
                # First, let's try to find records that have this date with colons
                date_pattern = f"{date_with_colons}%"
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE WorkRefId = ? 
                    AND TreatmentCPDateTime30080024 LIKE ?
                    ORDER BY BeamSequence300A00B0, ControlPointIndex300A0112
                """
                cursor.execute(query, (work_ref_id, date_pattern))

                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                self.log(f"  Method 2 (LIKE with colons): Found {len(rows)} control points in {table_name}")

                if len(rows) > 0:
                    return self._process_control_point_rows(rows, columns, control_points_by_beam)
            except Exception as e:
                self.log(f"  Method 2 failed: {str(e)}", "WARNING")

            # Method 3: Try to extract the date part using string functions
            try:
                # For SQL Server, we can use LEFT to get the first 10 characters
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE WorkRefId = ? 
                    AND LEFT(TreatmentCPDateTime30080024, 10) = ?
                    ORDER BY BeamSequence300A00B0, ControlPointIndex300A0112
                """
                # Try both formats
                cursor.execute(query, (work_ref_id, date_part))
                rows = cursor.fetchall()

                if len(rows) == 0:
                    cursor.execute(query, (work_ref_id, date_with_colons))
                    rows = cursor.fetchall()

                columns = [column[0] for column in cursor.description]
                self.log(f"  Method 3 (LEFT): Found {len(rows)} control points in {table_name}")

                if len(rows) > 0:
                    return self._process_control_point_rows(rows, columns, control_points_by_beam)
            except Exception as e:
                self.log(f"  Method 3 failed: {str(e)}", "WARNING")

            # Method 4: Try with REPLACE to convert colons to hyphens
            try:
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE WorkRefId = ? 
                    AND CONVERT(date, REPLACE(TreatmentCPDateTime30080024, ':', '-')) = CONVERT(date, ?)
                    ORDER BY BeamSequence300A00B0, ControlPointIndex300A0112
                """
                cursor.execute(query, (work_ref_id, date_part))

                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                self.log(f"  Method 4 (REPLACE colons): Found {len(rows)} control points in {table_name}")

                if len(rows) > 0:
                    return self._process_control_point_rows(rows, columns, control_points_by_beam)
            except Exception as e:
                self.log(f"  Method 4 failed: {str(e)}", "WARNING")

            self.log(f"  No control points found in {table_name} for date {date_part}")
            return {}

        except Exception as e:
            self.log(f"Error getting control points from {table_name}: {str(e)}", "ERROR")
            self.log(traceback.format_exc(), "ERROR")
            return {}

    def _process_control_point_rows(self, rows, columns, control_points_by_beam):
        """Process control point rows and return grouped control points"""
        for row in rows:
            cp_data = dict(zip(columns, row))
            beam_ref = cp_data.get('BeamSequence300A00B0', '')

            if not beam_ref:
                self.log(f"    Warning: Control point has no BeamSequence300A00B0 reference", "WARNING")
                continue

            cp_info = self._convert_to_control_point_info(cp_data, beam_ref)

            if beam_ref not in control_points_by_beam:
                control_points_by_beam[beam_ref] = []

            control_points_by_beam[beam_ref].append(cp_info)

        # Sort control points for each beam by index
        for beam_ref in control_points_by_beam:
            control_points_by_beam[beam_ref].sort(key=lambda x: x.control_point_index)

        # Log summary
        for beam_ref, cps in control_points_by_beam.items():
            indices = [cp.control_point_index for cp in cps]
            self.log(f"    Beam {beam_ref}: {len(cps)} control points, indices: {indices[:10]}...")

        return control_points_by_beam

    def _convert_to_control_point_info(self, cp_data: Dict, beam_ref: str) -> ControlPointInfo:
        """Convert database row to ControlPointInfo with proper numeric types"""
        cp_info = ControlPointInfo()

        cp_info.beam_sequence_ref = beam_ref

        # Helper function to safely convert to float
        def to_float(val, default=0.0):
            if val is None or val == '' or str(val).lower() in ['none', 'null']:
                return default
            try:
                return float(str(val))
            except (ValueError, TypeError):
                return default

        # Helper function to safely convert to int
        def to_int(val, default=0):
            if val is None or val == '' or str(val).lower() in ['none', 'null']:
                return default
            try:
                return int(float(str(val)))
            except (ValueError, TypeError):
                return default

        # Control point index
        cp_info.control_point_index = to_int(cp_data.get('ControlPointIndex300A0112', 0))

        # Numeric values - convert to float
        cp_info.cumulative_meterset_weight = to_float(cp_data.get('CumulativeMetersetWeight300A0134', 0))
        cp_info.nominal_beam_energy = to_float(cp_data.get('NominalBeamEnergy300A0114', 6.0))
        cp_info.dose_rate_set = to_float(cp_data.get('DoseRateSet300A0115', 0))
        cp_info.gantry_angle = to_float(cp_data.get('GantryAngle300A011E', 0))
        cp_info.beam_limiting_device_angle = to_float(cp_data.get('BeamLimitingDeviceAngle300A0120', 0))
        cp_info.patient_support_angle = to_float(cp_data.get('PatientSupportAngle300A0122', 0))
        cp_info.table_top_eccentric_angle = to_float(cp_data.get('TableTopEccentricAngle300A0125', 0))
        cp_info.table_top_vertical_position = to_float(cp_data.get('TableTopVerticalPosition300A0128', 0))
        cp_info.table_top_longitudinal_position = to_float(cp_data.get('TableTopLongitudinalPosition300A0129', 0))
        cp_info.table_top_lateral_position = to_float(cp_data.get('TableTopLateralPosition300A012A', 0))
        cp_info.table_top_pitch_angle = to_float(cp_data.get('TableTopPitchAngle300A0140', 0))
        cp_info.table_top_roll_angle = to_float(cp_data.get('TableTopRollAngle300A0144', 0))
        cp_info.specified_meterset = to_float(cp_data.get('SpecifiedMeterSet30080042', 0))
        cp_info.delivered_meterset = to_float(cp_data.get('DeliveredMeterset30080044', 0))
        cp_info.dose_rate_delivered = to_float(cp_data.get('DoseRateDelivered300A0075', 0))
        cp_info.source_to_surface_distance = to_float(cp_data.get('SourceToSurfaceDistance300A0130', 0))

        # String values
        cp_info.gantry_rotation_direction = str(cp_data.get('GantryRotationDirection300A011F', 'NONE'))
        cp_info.beam_limiting_device_rotation_direction = str(
            cp_data.get('BeamLimitingDeviceRotationDirection300A0121', 'NONE'))
        cp_info.patient_support_rotation_direction = str(cp_data.get('PatientSupportRotationDirection300A0123', 'NONE'))
        cp_info.table_top_eccentric_rotation_direction = str(
            cp_data.get('TableTopEccentricRotationDirection300A0126', 'NONE'))
        cp_info.table_top_pitch_rotation_direction = str(cp_data.get('TableTopPitchRotationDirection300A0142', 'NONE'))
        cp_info.table_top_roll_rotation_direction = str(cp_data.get('TableTopRollRotationDirection300A0146', 'NONE'))
        cp_info.isocenter_position = str(cp_data.get('IsocenterPosition300A012C', ''))

        # Treatment date/time for matching - handle both hyphen and colon formats
        treatment_dt = cp_data.get('TreatmentCPDateTime30080024', '')
        if treatment_dt and str(treatment_dt).lower() not in ['none', 'null']:
            if hasattr(treatment_dt, 'strftime'):
                # It's a datetime object
                cp_info.treatment_control_point_datetime = treatment_dt.strftime('%Y-%m-%d %H:%M:%S')
                cp_info.treatment_control_point_date = treatment_dt.strftime('%Y%m%d')
                cp_info.treatment_control_point_time = treatment_dt.strftime('%H%M%S')
            else:
                # It's a string - could be with hyphens or colons
                dt_str = str(treatment_dt)
                cp_info.treatment_control_point_datetime = dt_str

                # Replace colons with hyphens for consistent date format
                dt_str_standard = dt_str.replace(':', '-')
                parts = dt_str_standard.split()
                if len(parts) >= 2:
                    cp_info.treatment_control_point_date = parts[0].replace('-', '')
                    cp_info.treatment_control_point_time = parts[1].replace(':', '')[:6]

        # Beam limiting device positions
        cp_info.asymx_positions = self._clean_positions_string(str(cp_data.get('LeafJawPositionsAsymx300A011C', '')))
        cp_info.asymy_positions = self._clean_positions_string(str(cp_data.get('LeafJawPositionsAsymy300A011C', '')))
        cp_info.mlcx_positions = self._clean_positions_string(str(cp_data.get('LeafJawPositionsMlcx300A011C', '')))

        return cp_info

    def _clean_positions_string(self, positions_str: str) -> str:
        """Clean and format positions string for DICOM"""
        if not positions_str or positions_str == 'None' or positions_str == 'null':
            return ""

        # Remove brackets, quotes, and extra spaces
        positions_str = positions_str.replace('[', '').replace(']', '').replace("'", '')
        positions_str = positions_str.replace('"', '')

        # Split and clean each value
        values = []
        for val in positions_str.split(','):
            val = val.strip()
            if val:
                # Try to format as number
                try:
                    f_val = float(val)
                    if abs(f_val - int(f_val)) < 0.000001:
                        val = str(int(f_val))
                    else:
                        val = f"{f_val:.3f}".rstrip('0').rstrip('.')
                except:
                    pass
                values.append(val)

        # Join with backslash
        return '\\'.join(values)


# ==================== DICOM Generator ====================
class RTRecordDICOMGenerator:
    """Generates RT Record DICOM files"""

    def __init__(self, output_dir: str, logger=None):
        self.output_dir = output_dir
        self.logger = logger or print

    def log(self, message, level="INFO"):
        if self.logger:
            self.logger(message, level)

    def generate_rt_record(self, patient_info: PatientInfo, fraction_info: FractionInfo,
                           control_points_by_beam: Dict[str, List[ControlPointInfo]],
                           record_type: str) -> bool:
        """Generate RT Record DICOM file for a specific fraction"""
        try:
            if not control_points_by_beam or not any(control_points_by_beam.values()):
                self.log(f"    ⚠ No control points found for this fraction", "WARNING")
                return False

            # Create file meta
            file_meta = FileMetaDataset()
            file_meta.MediaStorageSOPClassUID = RT_RECORD_STORAGE_UID
            file_meta.MediaStorageSOPInstanceUID = generate_uid()
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            file_meta.ImplementationClassUID = generate_uid()
            file_meta.ImplementationVersionName = "PYTHON_RTRECORD_4.0"

            # Create dataset
            ds = Dataset()
            ds.file_meta = file_meta
            ds.is_little_endian = True
            ds.is_implicit_VR = False

            # SOP Common
            ds.SOPClassUID = RT_RECORD_STORAGE_UID
            ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID

            # Patient Module
            ds.PatientName = patient_info.patient_name or "Unknown^Patient"
            ds.PatientID = patient_info.patient_id or "Unknown"
            ds.PatientBirthDate = patient_info.birth_date or ""
            ds.PatientSex = patient_info.sex or "O"

            # Study Module
            ds.StudyDate = patient_info.study_date or fraction_info.treatment_date.replace('-', '')
            ds.StudyTime = patient_info.study_time or fraction_info.treatment_time.replace(':', '')[:6]
            ds.AccessionNumber = patient_info.accession_number or ""
            ds.ReferringPhysicianName = patient_info.referring_physician or ""
            ds.StudyInstanceUID = patient_info.study_instance_uid or generate_uid()
            ds.StudyID = patient_info.study_id or "1"

            # Series Module
            ds.Modality = "RTRECORD"
            ds.SeriesDescription = f"{patient_info.series_description} - {record_type}" if patient_info.series_description else f"RT Record {record_type}"
            ds.StudyDescription = patient_info.study_description or ""
            ds.OperatorsName = [patient_info.operators_name] if patient_info.operators_name else []
            ds.SeriesInstanceUID = generate_uid()

            # Series number
            series_num = self._extract_int(patient_info.series_number, 1)
            if record_type == "PRIMARY":
                ds.SeriesNumber = series_num
            else:
                ds.SeriesNumber = series_num + 100

            # Equipment Module
            ds.Manufacturer = patient_info.manufacturer or "Unknown"
            ds.ManufacturerModelName = patient_info.manufacturer_model_name or "Unknown"
            ds.DeviceSerialNumber = patient_info.device_serial_number or ""
            ds.SoftwareVersions = ["4.0.0"]

            # Frame of Reference
            ds.FrameOfReferenceUID = generate_uid()
            ds.PositionReferenceIndicator = ""

            # RT Record specific
            ds.NumberOfFractionsPlanned = self._extract_int(fraction_info.fraction_group, 0)
            ds.FirstTreatmentDate = ""
            ds.MostRecentTreatmentDate = fraction_info.treatment_date.replace('-', '')
            ds.CurrentTreatmentStatus = fraction_info.treatment_status or ""
            ds.PrimaryDosimeterUnit = "MU"
            ds.ReferencedFractionGroupNumber = self._extract_int(fraction_info.fraction_group, 1)

            # Referenced RT Plan
            ds.ReferencedRTPlanSequence = []
            plan_item = Dataset()
            plan_item.ReferencedSOPClassUID = RT_PLAN_STORAGE_UID
            plan_item.ReferencedSOPInstanceUID = fraction_info.study_instance_uid or generate_uid()
            ds.ReferencedRTPlanSequence.append(plan_item)

            # Treatment Date/Time
            ds.TreatmentDate = fraction_info.treatment_date.replace('-', '')
            ds.TreatmentTime = fraction_info.treatment_time.replace(':', '')[:6]
            ds.InstanceNumber = fraction_info.fraction_number

            # Treatment Machine Sequence
            ds.TreatmentMachineSequence = []
            machine_item = Dataset()
            machine_item.Manufacturer = patient_info.manufacturer or "Unknown"
            machine_item.ManufacturerModelName = patient_info.manufacturer_model_name or "Unknown"
            machine_item.DeviceSerialNumber = patient_info.device_serial_number or ""
            machine_item.TreatmentMachineName = patient_info.series_description or ""
            machine_item.InstitutionName = ""
            ds.TreatmentMachineSequence.append(machine_item)

            # Treatment Session Beam Sequence
            ds.TreatmentSessionBeamSequence = []

            # Process each beam's control points
            for beam_ref, cp_list in control_points_by_beam.items():
                beam_item = Dataset()

                # Extract beam number from beam_ref
                beam_num = self._extract_int(beam_ref, 1)

                # Beam parameters
                beam_item.CurrentFractionNumber = self._extract_int(fraction_info.fraction_number, 1)
                beam_item.TreatmentVerificationStatus = patient_info.verification_status or ""
                beam_item.TreatmentTerminationStatus = "NORMAL"
                beam_item.BeamType = "STATIC"
                beam_item.TreatmentDeliveryType = "TREATMENT"
                beam_item.RadiationType = "PHOTON"
                beam_item.NumberOfWedges = 0
                beam_item.NumberOfCompensators = 0
                beam_item.NumberOfBoli = 0
                beam_item.NumberOfBlocks = 0
                beam_item.NumberOfControlPoints = len(cp_list)
                beam_item.BeamName = f"Beam {beam_num}"

                # Control Point Delivery Sequence
                if cp_list:
                    beam_item.ControlPointDeliverySequence = []
                    for cp_info in cp_list:
                        cp_item = self._create_control_point_item(cp_info)
                        beam_item.ControlPointDeliverySequence.append(cp_item)

                ds.TreatmentSessionBeamSequence.append(beam_item)

            # Save the file
            filename = self._generate_filename(patient_info.patient_id, fraction_info.treatment_date,
                                               fraction_info.fraction_number, record_type)
            filepath = os.path.join(self.output_dir, filename)

            pydicom.dcmwrite(filepath, ds, write_like_original=False)
            self.log(f"✓ Generated {record_type} record: {filename}")

            return True

        except Exception as e:
            self.log(f"✗ Error generating {record_type} record: {str(e)}", "ERROR")
            self.log(traceback.format_exc(), "ERROR")
            return False

    def _extract_int(self, value: Any, default: int = 0) -> int:
        """Extract integer value from various inputs"""
        if value is None or value == '':
            return default
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            numbers = re.findall(r'-?\d+\.?\d*', str(value))
            if numbers:
                try:
                    return int(float(numbers[0]))
                except:
                    pass
            return default

    def _create_control_point_item(self, cp_info: ControlPointInfo) -> Dataset:
        """Create a control point item with proper DICOM VR types"""
        cp_item = Dataset()

        # String values
        cp_item.NominalBeamEnergyUnit = "MV"
        cp_item.GantryRotationDirection = cp_info.gantry_rotation_direction
        cp_item.BeamLimitingDeviceRotationDirection = cp_info.beam_limiting_device_rotation_direction
        cp_item.PatientSupportRotationDirection = cp_info.patient_support_rotation_direction
        cp_item.TableTopEccentricRotationDirection = cp_info.table_top_eccentric_rotation_direction
        cp_item.TableTopPitchRotationDirection = cp_info.table_top_pitch_rotation_direction
        cp_item.TableTopRollRotationDirection = cp_info.table_top_roll_rotation_direction

        # Floating point values
        cp_item.NominalBeamEnergy = cp_info.nominal_beam_energy
        cp_item.DoseRateSet = cp_info.dose_rate_set
        cp_item.GantryAngle = cp_info.gantry_angle
        cp_item.BeamLimitingDeviceAngle = cp_info.beam_limiting_device_angle
        cp_item.PatientSupportAngle = cp_info.patient_support_angle
        cp_item.TableTopEccentricAngle = cp_info.table_top_eccentric_angle
        cp_item.TableTopVerticalPosition = cp_info.table_top_vertical_position
        cp_item.TableTopLongitudinalPosition = cp_info.table_top_longitudinal_position
        cp_item.TableTopLateralPosition = cp_info.table_top_lateral_position
        cp_item.TableTopPitchAngle = cp_info.table_top_pitch_angle
        cp_item.TableTopRollAngle = cp_info.table_top_roll_angle
        cp_item.SpecifiedMeterset = cp_info.specified_meterset
        cp_item.DeliveredMeterset = cp_info.delivered_meterset
        cp_item.DoseRateDelivered = cp_info.dose_rate_delivered
        cp_item.CumulativeMetersetWeight = cp_info.cumulative_meterset_weight
        cp_item.SourceToSurfaceDistance = cp_info.source_to_surface_distance

        # Isocenter position
        if cp_info.isocenter_position:
            cp_item.IsocenterPosition = cp_info.isocenter_position

        # Treatment control point date/time
        if cp_info.treatment_control_point_date:
            cp_item.TreatmentControlPointDate = cp_info.treatment_control_point_date
        if cp_info.treatment_control_point_time:
            cp_item.TreatmentControlPointTime = cp_info.treatment_control_point_time

        # Beam Limiting Device Position Sequence
        cp_item.BeamLimitingDevicePositionSequence = []

        if cp_info.asymx_positions:
            pos_item = Dataset()
            pos_item.RTBeamLimitingDeviceType = "ASYMX"
            pos_item.LeafJawPositions = cp_info.asymx_positions
            cp_item.BeamLimitingDevicePositionSequence.append(pos_item)

        if cp_info.asymy_positions:
            pos_item = Dataset()
            pos_item.RTBeamLimitingDeviceType = "ASYMY"
            pos_item.LeafJawPositions = cp_info.asymy_positions
            cp_item.BeamLimitingDevicePositionSequence.append(pos_item)

        if cp_info.mlcx_positions:
            pos_item = Dataset()
            pos_item.RTBeamLimitingDeviceType = "MLCX"
            pos_item.LeafJawPositions = cp_info.mlcx_positions
            cp_item.BeamLimitingDevicePositionSequence.append(pos_item)

        return cp_item

    def _generate_filename(self, patient_id: str, treatment_date: str, fraction_number: str, record_type: str) -> str:
        """Generate filename for RT Record"""
        clean_id = re.sub(r'[\\/*?:"<>|]', '_', str(patient_id))
        date_clean = treatment_date.replace('-', '')
        return f"RTRecord_{clean_id}_{date_clean}_F{fraction_number}_{record_type}.dcm"


# ==================== Worker Thread ====================
class RTRecordWorker(QThread):
    progress = pyqtSignal(int, int, str)
    log_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, str)
    fractions_found = pyqtSignal(list)

    def __init__(self, db_config, output_dir, start_date, end_date):
        super().__init__()
        self.db_config = db_config
        self.output_dir = output_dir
        self.start_date = start_date
        self.end_date = end_date
        self.is_running = True
        self.db_manager = None
        self.data_fetcher = None
        self.dicom_generator = None

    def log(self, message, level="INFO"):
        self.log_signal.emit(message, level)

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            self._log_header()

            os.makedirs(self.output_dir, exist_ok=True)

            self.db_manager = DatabaseManager(self.log)
            if not self.db_manager.connect(
                    self.db_config['server_ip'],
                    self.db_config.get('username'),
                    self.db_config.get('password'),
                    self.db_config.get('trusted_connection', False)
            ):
                self.finished_signal.emit(False, "Failed to connect to databases")
                return

            self.data_fetcher = RTRecordDataFetcher(self.db_manager, self.log)
            self.dicom_generator = RTRecordDICOMGenerator(self.output_dir, self.log)

            fractions = self.data_fetcher.get_fractions_in_date_range(self.start_date, self.end_date)

            if not fractions:
                self.log("No fractions found in the specified date range", "WARNING")
                self.finished_signal.emit(True, "No fractions found in the specified date range")
                return

            self.fractions_found.emit(fractions)

            total_fractions = len(fractions)
            files_generated = 0
            fractions_with_control_points = 0

            for idx, fraction in enumerate(fractions):
                if not self.is_running:
                    break

                self.progress.emit(idx + 1, total_fractions,
                                   f"Processing fraction {fraction.fraction_number} for WorkRef {fraction.work_ref_id}")

                files = self._process_fraction(fraction)
                if files > 0:
                    fractions_with_control_points += 1
                files_generated += files

            self._log_footer(files_generated, total_fractions, fractions_with_control_points)
            self.finished_signal.emit(True,
                                      f"Successfully generated {files_generated} RT Record files for {fractions_with_control_points} fractions with control points")

        except Exception as e:
            self.log(f"Error: {str(e)}\n{traceback.format_exc()}", "ERROR")
            self.finished_signal.emit(False, f"Error: {str(e)}")
        finally:
            if self.db_manager:
                self.db_manager.close()

    def _log_header(self):
        self.log("=" * 80)
        self.log("RT RECORD GENERATOR - DUAL RECORD SYSTEM")
        self.log("=" * 80)
        self.log(f"Date Range: {self.start_date} to {self.end_date}")
        self.log(f"Output Directory: {self.output_dir}")
        self.log("=" * 80)

    def _log_footer(self, files_generated: int, total_fractions: int, fractions_with_data: int):
        self.log("=" * 80)
        self.log(f"GENERATION COMPLETE:")
        self.log(f"  Total Fractions in Date Range: {total_fractions}")
        self.log(f"  Fractions with Control Points: {fractions_with_data}")
        self.log(f"  Files Generated: {files_generated} (2 per fraction with data)")
        self.log("=" * 80)

    def _process_fraction(self, fraction: FractionInfo) -> int:
        """Process a single fraction - generates both primary and secondary RT Records"""
        try:
            self.log(f"\n  Processing fraction {fraction.fraction_number} for WorkRef {fraction.work_ref_id}")
            self.log(f"    Treatment Date/Time: {fraction.treatment_datetime}")

            patient_info = self.data_fetcher.get_patient_info_from_work(fraction.work_ref_id)
            if not patient_info:
                self.log(f"    ⚠ No patient info found for WorkRef {fraction.work_ref_id}", "WARNING")
                return 0

            # Get PRIMARY control points
            self.log(f"    Fetching PRIMARY control points...")
            primary_cp = self.data_fetcher.get_control_points_for_fraction(
                fraction.work_ref_id,
                "TreatmentRT_Pri_RecordBeamSequenceControlPointSequence",
                fraction.treatment_datetime
            )

            # Get SECONDARY control points
            self.log(f"    Fetching SECONDARY control points...")
            secondary_cp = self.data_fetcher.get_control_points_for_fraction(
                fraction.work_ref_id,
                "TreatmentRT_Sec_RecordBeamSequenceControlPointSequence",
                fraction.treatment_datetime
            )

            files_generated = 0

            # Generate PRIMARY record
            if primary_cp and any(primary_cp.values()):
                self.log(f"    Generating PRIMARY record with {len(primary_cp)} beams")
                success = self.dicom_generator.generate_rt_record(
                    patient_info, fraction, primary_cp, "PRIMARY"
                )
                if success:
                    files_generated += 1
                    self.log(f"    ✓ PRIMARY record generated successfully")
            else:
                self.log(f"    ⚠ No PRIMARY control points found for this fraction date", "WARNING")

            # Generate SECONDARY record
            if secondary_cp and any(secondary_cp.values()):
                self.log(f"    Generating SECONDARY record with {len(secondary_cp)} beams")
                success = self.dicom_generator.generate_rt_record(
                    patient_info, fraction, secondary_cp, "SECONDARY"
                )
                if success:
                    files_generated += 1
                    self.log(f"    ✓ SECONDARY record generated successfully")
            else:
                self.log(f"    ⚠ No SECONDARY control points found for this fraction date", "WARNING")

            if files_generated > 0:
                self.log(f"    ✓ Generated {files_generated} files for fraction {fraction.fraction_number}")

            return files_generated

        except Exception as e:
            self.log(f"    Error processing fraction: {str(e)}", "ERROR")
            self.log(traceback.format_exc(), "ERROR")
            return 0


# ==================== Main Window ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.fractions = []
        self.init_ui()
        self.setup_logging()

    def init_ui(self):
        self.setWindowTitle("RT Record Generator - Dual Record System")
        self.setGeometry(100, 100, 1300, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("RT Record Generator - PRIMARY & SECONDARY Records")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Check ODBC drivers on startup
        drivers = get_available_odbc_drivers()
        driver_status = QLabel(f"Available ODBC Drivers: {len(drivers)} found")
        if not drivers:
            driver_status.setStyleSheet("color: red; font-weight: bold;")
            driver_status.setText("⚠ No ODBC drivers found! Please install ODBC Driver 17 for SQL Server")
        layout.addWidget(driver_status)

        # Main splitter
        main_splitter = QSplitter(Qt.Vertical)
        layout.addWidget(main_splitter)

        # Top widget for controls
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(10, 10, 10, 10)

        # Connection group
        conn_group = QGroupBox("Database Connection Settings")
        conn_layout = QFormLayout(conn_group)

        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("e.g., 192.168.10.21")
        self.ip_edit.setText("192.168.10.127")
        conn_layout.addRow("SQL Server IP Address:", self.ip_edit)

        self.auth_combo = QComboBox()
        self.auth_combo.addItems(["SQL Server Authentication", "Windows Authentication"])
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)
        conn_layout.addRow("Authentication:", self.auth_combo)

        self.username_edit = QLineEdit()
        self.username_edit.setText("sa")
        conn_layout.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setText("panacea")
        conn_layout.addRow("Password:", self.password_edit)

        top_layout.addWidget(conn_group)

        # Date range and output group
        date_output_layout = QHBoxLayout()

        # Date range group
        date_group = QGroupBox("Date Range Selection")
        date_layout = QFormLayout(date_group)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        date_layout.addRow("Start Date:", self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate().addDays(1))
        self.end_date_edit.setCalendarPopup(True)
        date_layout.addRow("End Date:", self.end_date_edit)

        date_output_layout.addWidget(date_group)

        # Output directory group
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)

        output_path_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setText("D:\\RT_Treatment_Records")
        output_path_layout.addWidget(self.output_edit)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_output)
        output_path_layout.addWidget(browse_btn)
        output_layout.addLayout(output_path_layout)

        date_output_layout.addWidget(output_group)

        top_layout.addLayout(date_output_layout)

        # Button layout
        button_layout = QHBoxLayout()

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        self.test_btn.setMinimumHeight(40)
        button_layout.addWidget(self.test_btn)

        self.preview_btn = QPushButton("Preview Fractions")
        self.preview_btn.clicked.connect(self._preview_fractions)
        self.preview_btn.setMinimumHeight(40)
        self.preview_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        button_layout.addWidget(self.preview_btn)

        self.start_btn = QPushButton("Start Generation")
        self.start_btn.clicked.connect(self._start_generation)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop_generation)
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        button_layout.addWidget(self.stop_btn)

        top_layout.addLayout(button_layout)

        main_splitter.addWidget(top_widget)

        # Bottom widget for preview and logs
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        # Preview table
        preview_group = QGroupBox("Fractions Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(8)
        self.preview_table.setHorizontalHeaderLabels([
            "WorkRef ID", "Fraction No", "Fraction Group",
            "Treatment Date", "Treatment Time", "Approval Status",
            "Treatment Status", "Patient ID"
        ])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        preview_layout.addWidget(self.preview_table)

        bottom_layout.addWidget(preview_group)

        # Log group
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.log_text)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)

        bottom_layout.addWidget(log_group)

        main_splitter.addWidget(bottom_widget)

        main_splitter.setSizes([300, 600])

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)

    def _on_auth_changed(self, text):
        if text == "Windows Authentication":
            self.username_edit.setEnabled(False)
            self.password_edit.setEnabled(False)
        else:
            self.username_edit.setEnabled(True)
            self.password_edit.setEnabled(True)

    def _browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.output_edit.text()
        )
        if directory:
            self.output_edit.setText(directory)

    def setup_logging(self):
        self.log_handler = QTextEditLogger(self.log_text)
        self.log_handler.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO, handlers=[self.log_handler])

    def log(self, message, level="INFO"):
        if level == "ERROR":
            logging.error(message)
        elif level == "WARNING":
            logging.warning(message)
        else:
            logging.info(message)

    def _test_connection(self):
        try:
            ip = self.ip_edit.text().strip()
            if not ip:
                QMessageBox.warning(self, "Warning", "Please enter SQL Server IP address")
                return

            self.log(f"Testing connection to SQL Server at IP: {ip}")

            db_manager = DatabaseManager(self.log)
            success = db_manager.connect(
                ip,
                self.username_edit.text() if self.auth_combo.currentText() == "SQL Server Authentication" else None,
                self.password_edit.text() if self.auth_combo.currentText() == "SQL Server Authentication" else None,
                self.auth_combo.currentText() == "Windows Authentication"
            )

            if success:
                db_manager.close()
                QMessageBox.information(self, "Success", f"Connection to {ip} successful!")
                self.log("✓ Connection test successful")
            else:
                QMessageBox.critical(self, "Connection Failed", "Failed to connect to database")

        except Exception as e:
            self.log(f"✗ Connection failed: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Connection Failed", str(e))

    def _preview_fractions(self):
        ip = self.ip_edit.text().strip()
        if not ip:
            QMessageBox.warning(self, "Warning", "Please enter SQL Server IP address")
            return

        if self.auth_combo.currentText() == "SQL Server Authentication":
            if not self.username_edit.text() or not self.password_edit.text():
                QMessageBox.warning(self, "Warning", "Please enter database credentials")
                return

        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        if start_date > end_date:
            QMessageBox.warning(self, "Warning", "Start date must be before end date")
            return

        self.log(f"\nPreviewing fractions from {start_date} to {end_date}")

        db_manager = DatabaseManager(self.log)
        if not db_manager.connect(
                ip,
                self.username_edit.text() if self.auth_combo.currentText() == "SQL Server Authentication" else None,
                self.password_edit.text() if self.auth_combo.currentText() == "SQL Server Authentication" else None,
                self.auth_combo.currentText() == "Windows Authentication"
        ):
            QMessageBox.critical(self, "Error", "Failed to connect to database")
            return

        try:
            data_fetcher = RTRecordDataFetcher(db_manager, self.log)
            fractions = data_fetcher.get_fractions_in_date_range(start_date, end_date)

            self.preview_table.setRowCount(len(fractions))

            for row, fraction in enumerate(fractions):
                patient_info = data_fetcher.get_patient_info_from_work(fraction.work_ref_id)
                patient_id = patient_info.patient_id if patient_info else "Unknown"

                self.preview_table.setItem(row, 0, QTableWidgetItem(fraction.work_ref_id))
                self.preview_table.setItem(row, 1, QTableWidgetItem(fraction.fraction_number))
                self.preview_table.setItem(row, 2, QTableWidgetItem(fraction.fraction_group))
                self.preview_table.setItem(row, 3, QTableWidgetItem(fraction.treatment_date))
                self.preview_table.setItem(row, 4, QTableWidgetItem(fraction.treatment_time))
                self.preview_table.setItem(row, 5, QTableWidgetItem(fraction.approval_status))
                self.preview_table.setItem(row, 6, QTableWidgetItem(fraction.treatment_status))
                self.preview_table.setItem(row, 7, QTableWidgetItem(patient_id))

                if fraction.approval_status in ['PT', 'T']:
                    self.preview_table.item(row, 5).setBackground(QColor(144, 238, 144))

            self.log(f"Found {len(fractions)} fractions in date range")

        except Exception as e:
            self.log(f"Error previewing fractions: {str(e)}", "ERROR")
            QMessageBox.critical(self, "Error", f"Failed to preview fractions: {str(e)}")
        finally:
            db_manager.close()

    def _start_generation(self):
        ip = self.ip_edit.text().strip()
        if not ip:
            QMessageBox.warning(self, "Warning", "Please enter SQL Server IP address")
            return

        if self.auth_combo.currentText() == "SQL Server Authentication":
            if not self.username_edit.text() or not self.password_edit.text():
                QMessageBox.warning(self, "Warning", "Please enter database credentials")
                return

        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        if start_date > end_date:
            QMessageBox.warning(self, "Warning", "Start date must be before end date")
            return

        reply = QMessageBox.question(
            self, "Confirm Generation",
            f"Generate RT Records for fractions between {start_date} and {end_date}?\n\n"
            f"This will create 2 files per fraction that have control point data.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.preview_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        db_config = {
            'server_ip': ip,
            'username': self.username_edit.text() if self.auth_combo.currentText() == "SQL Server Authentication" else None,
            'password': self.password_edit.text() if self.auth_combo.currentText() == "SQL Server Authentication" else None,
            'trusted_connection': self.auth_combo.currentText() == "Windows Authentication"
        }

        self.worker = RTRecordWorker(
            db_config,
            self.output_edit.text(),
            start_date,
            end_date
        )
        self.worker.progress.connect(self._update_progress)
        self.worker.log_signal.connect(self.log)
        self.worker.fractions_found.connect(self._update_preview)
        self.worker.finished_signal.connect(self._generation_finished)

        self.worker.start()
        self.status_label.setText("Generation in progress...")

    def _update_preview(self, fractions):
        self.preview_table.setRowCount(len(fractions))
        for row, fraction in enumerate(fractions):
            self.preview_table.setItem(row, 0, QTableWidgetItem(fraction.work_ref_id))
            self.preview_table.setItem(row, 1, QTableWidgetItem(fraction.fraction_number))
            self.preview_table.setItem(row, 2, QTableWidgetItem(fraction.fraction_group))
            self.preview_table.setItem(row, 3, QTableWidgetItem(fraction.treatment_date))
            self.preview_table.setItem(row, 4, QTableWidgetItem(fraction.treatment_time))
            self.preview_table.setItem(row, 5, QTableWidgetItem(fraction.approval_status))
            self.preview_table.setItem(row, 6, QTableWidgetItem(fraction.treatment_status))

    def _stop_generation(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Confirm", "Stop generation?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.status_label.setText("Stopping...")

    def _update_progress(self, current, total, task):
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
        self.status_label.setText(task)

    def _generation_finished(self, success, message):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.preview_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.status_label.setText("Generation completed")
            QMessageBox.information(self, "Success", message)
        else:
            self.status_label.setText("Generation failed")
            QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Confirm", "Exit while generation in progress?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.stop()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ==================== Main Entry Point ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())