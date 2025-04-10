import numpy as np

grayscale = np.arange(256)
pixels = np.ones_like(grayscale)

LUT = np.column_stack((grayscale, pixels))
LUT_folder='C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\'
#LUT_folder = '\\group-data.phys.ethz.ch\\ong-stud\\2025\\4_Seraina_Leuthold\\01_Data\\01_Code\\semesterproject_fully-optical-nn\\notebooks\\'
file_name = f"{LUT_folder}test_LUT.LUT"

np.savetxt(file_name, LUT, delimiter=' ', fmt='%d')