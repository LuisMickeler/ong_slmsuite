import os
from ctypes import *
import numpy as np
import time

# Set up DPI awareness (optional, depending on the system)
import ctypes
awareness = ctypes.c_int()
errorCode = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
print("DPI Awareness:", awareness.value)
errorCode = ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Set DPI awareness level (2 for full control)

# Load the necessary DLLs
blink_lib_path = r"C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\SDK"
cdll.LoadLibrary(os.path.join(blink_lib_path, "Blink_C_wrapper.dll"))
cdll.LoadLibrary(os.path.join(blink_lib_path, "ImageGen.dll"))

# Define the library bindings
slm_lib = CDLL(os.path.join(blink_lib_path, "Blink_C_wrapper.dll"))

# Create the SDK instance
slm_lib.Create_SDK()
print("Blink SDK was successfully constructed")

# Define LUT file path
LUT_filepath = r"C:\Program Files\Meadowlark Optics\Blink 1920 HDMI\LUT Files\slm6543_at785.LUT"

# Load LUT function
def load_lut(lut_filepath):
    slm_lib.Load_lut(c_char_p(lut_filepath.encode('utf-8')))
    print(f"LUT file loaded from: {lut_filepath}")

# Load LUT
load_lut(LUT_filepath)

# Cleanup: Always call Delete_SDK before exiting
slm_lib.Delete_SDK()
print("SDK successfully deleted and cleaned up")
