import pydicom
import numpy as np

ds = pydicom.dcmread("D:/RDose/shubam/RD1.2.752.243.1.1.20250219133115855.6300.48141.dcm")
dose = ds.pixel_array * ds.DoseGridScaling  # dose in Gy

total_dose_gy = np.sum(dose)*(300/1174)
print(f"Total Dose = {total_dose_gy:.2f} Gy")