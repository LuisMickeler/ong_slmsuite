import os
import numpy
from ctypes import *
# from scipy import misc
import time
from pyAndorSDK3 import AndorSDK3
import matplotlib.pyplot as plt
from tqdm import tqdm

def plot_intensity(images, slm_array):
    # average the intensity of the cam
    intensity = numpy.mean(images, axis=(1,2))
    max_intensity = numpy.max(intensity)
    min_intensity = numpy.min(intensity)
    uncentered_intensity = intensity/max_intensity
    intensity = (intensity-min_intensity)/(max_intensity-min_intensity)
    print(f'shape: {slm_array[:,0,0].shape}, {slm_array[0,:,0].shape}, {slm_array[0,0,:].shape}')
    # display pixel value of SLM vs. image value cam (-> intensity)
    fig, (ax1, ax2) = plt.subplots(2, 1)
    ax1.plot(slm_array[:,0,0], intensity, '.-')
    ax1.set_ylabel('intensity')
    ax1.set_xlabel('pixel value')

    # plot phase vs. pixel value
    phase = numpy.arccos(2*uncentered_intensity - 1)/(numpy.pi)
    ax2.plot(slm_array[:,0,0], phase, '.-')
    ax2.set_ylabel('phase')
    ax2.set_xlabel('pixel value')
    plt.savefig(".\calibration_1_curr.png")
    plt.show()
    plt.close()

def AOI_cam(cam, binning='1x1', width=2048, height=2048, left=1, top=1, exp_time=0.001, cycle_mode='Continuous'):
    cam.AOIBinning = binning
    cam.AOIWidth = width
    cam.AOILeft = left
    cam.AOIHeight = height
    cam.AOITop = top
    # cam.framerate=90
    cam.ExposureTime = exp_time
    cam.CycleMode = cycle_mode #"Continuous" (was in example on fixed)

################################ MAKE SURE THE WINDOW SHOWS UP IN THE WRITE PLACE FOR THE DPI SETTINGS#############
# Query DPI Awareness (Windows 10 and 8)
import ctypes
awareness = ctypes.c_int()
errorCode = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
print(awareness.value)

# Set DPI Awareness  (Windows 10 and 8)
errorCode = ctypes.windll.shcore.SetProcessDpiAwareness(2)
# the argument is the awareness level, which can be 0, 1 or 2:
# for 1-to-1 pixel control I seem to need it to be non-zero (I'm using level 2)

# Set DPI Awareness  (Windows 7 and Vista)
success = ctypes.windll.user32.SetProcessDPIAware()
# behaviour on later OSes is undefined, although when I run it on my Windows 10 machine, it seems to work with effects identical to SetProcessDpiAwareness(1)
#######################################################################################################################


# Load the DLL
# Blink_C_wrapper.dll, HdmiDisplay.dll, ImageGen.dll, freeglut.dll and glew64.dll
# should all be located in the same directory as the program referencing the
# library
cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\Blink_C_wrapper")
slm_lib = CDLL("Blink_C_wrapper") # slm_lib.function() can now be uesd like the functions in C but in python

# Call the constructor
slm_lib.Create_SDK()

# file_path = "\\group-data.phys.ethz.ch\\ong-stud\\2025\\4_Seraina_Leuthold\\01_Data\\01_Code\\semesterproject_fully-optical-nn\\src\\LUT\\custom_linear_LUT.LUT"
file_path = "C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\custom_linear_LUT.LUT"
slm_lib.Load_lut(file_path)

if not os.path.exists(file_path):
    print("File does not exist or is not accessible.")
else:
    # Create the string buffer for the path
    print("File exists")
    file_path_cstr = ctypes.c_char_p(file_path.encode('utf-8'))

    # Call Load_lut with the buffer and handle exceptions
    try:
        result = slm_lib.Load_lut(file_path_cstr)
        # slm_lib.Load_lut = file_path
        print("LUT file loaded successfully.")
    except Exception as e:
        print(f"Error loading LUT: {e}")


# TODO:
# generate input voltages -> maybe have to convert to images
# pass voltages to SLM
# measure intensity with camera
# store intensity in a list
# iterate through voltages
# plot intensity vs voltage
# plot phase vs voltage

# connect to camera and set parameters
sdk3 = AndorSDK3()
cam = sdk3.GetCamera(0)


# Cooling the camera sensor
cam.SensorCooling = True

if 0:
    # getting legal available options for TemperatureControl feature
    temps = cam.available_options_TemperatureControl

    print(cam.TemperatureControl)  
    print(cam.TemperatureControl == temps[0])

    if cam.TemperatureControl == temps[0]:
        target_temp = temps[0] 
    else: 
        target_temp = temps[1]
    print("Target temperature = {}C".format(target_temp))
    cam.TemperatureControl = target_temp


# waiting for temperature to stabilise
while(cam.TemperatureStatus != "Stabilised"):
    time.sleep(5)
    print("Temperature: {:.5f}C".format(cam.SensorTemperature), end="  ")
    print("Status: '{}'".format(cam.TemperatureStatus))
    if cam.TemperatureStatus == "Fault":
        err_str = "Camera faulted when cooling to target temperature"
        raise RuntimeError(err_str)

print("Sensor Temperature now Stabilised and Camera is ready to use")

AOI_cam(cam,
        width=300,
        height=300,
        left=843,
        top=872,
)

# indicate that our images are black and white -> don't really see why this is necessary?
RGB = c_uint(0)
is_eight_bit_image = c_uint(1)

height = c_uint(slm_lib.Get_Height())
width = c_uint(slm_lib.Get_Width())
depth = c_uint(slm_lib.Get_Depth())
bytesPerPixel = 1 #for not RGBA? #4; #RGBA

# SLM dimensions
print("height: ", height.value, "width: ", width.value, "depth: ", depth.value)

center_x = c_uint(width.value//2)
center_y = c_uint(height.value//2)

# generate the 256 patterns
sample_num=250
pattern = numpy.ones((height.value, width.value), dtype=numpy.uint8) 
pattern_curr = numpy.zeros((height.value, width.value), dtype=numpy.uint8)
slm_array = numpy.empty([sample_num, height.value, width.value], dtype=numpy.uint8)
for i in range(sample_num):
    slm_array[i] = pattern_curr
    pattern_curr += pattern * 1
    if i%50 == 0:
        print(f'pattern step{i}: {slm_array[i][0]}')
   
# loop for measurements
images = numpy.empty([sample_num, cam.AOIWidth, cam.AOIHeight], numpy.uint8, 'C')
pbar = tqdm(range(sample_num))
for k in pbar:
    # write the image on the slm
    slm_lib.Write_image(slm_array[k].ctypes.data_as(POINTER(c_ubyte)), is_eight_bit_image)
    time.sleep(0.01)
    # measure the intensity
    img = cam.acquire(timeout=50, min_buf=4)
    images[k] = img.image
    if k % 5 == 0:
        #img.save(f'.\cam_img_{k}.png')
        plt.imshow(images[k], cmap='gray', vmin=0, vmax=255)
        plt.savefig(f'.\cam_img_step{k}.png')
    pbar.set_postfix({'Temperature': cam.SensorTemperature})
      
plot_intensity(images=images, slm_array=slm_array)

# Always call Delete_SDK before exiting
slm_lib.Delete_SDK()
