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
    indices = numpy.linspace(0, 29, num=30)
    ax1.plot(slm_array[:,0,0], intensity, '.-')
    #ax1.plot(indices, intensity, '.-')
    ax1.set_ylabel('intensity')
    ax1.set_xlabel('grayscale value')

    # plot phase vs. pixel value
    phase = numpy.arccos(2*intensity - 1)/(numpy.pi)
    ax2.plot(slm_array[:,0,0], phase, '.-')
    #ax2.plot(indices, phase, '.-')
    ax2.set_ylabel('phase')
    ax2.set_xlabel('grayscale value')
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
    cam.CycleMode = cycle_mode

def temperature_stabilisation(cam):
    # Cooling the camera sensor
    cam.SensorCooling = True
    # waiting for temperature to stabilise
    while(cam.TemperatureStatus != "Stabilised"):
        time.sleep(5)
        print("Temperature: {:.5f}C".format(cam.SensorTemperature), end="  ")
        print("Status: '{}'".format(cam.TemperatureStatus))
        if cam.TemperatureStatus == "Fault":
            err_str = "Camera faulted when cooling to target temperature"
            raise RuntimeError(err_str)

    print("Sensor Temperature now Stabilised and Camera is ready to use")

# Query DPI Awareness (Windows 10 and 8)
import ctypes
awareness = ctypes.c_int()
errorCode = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
print(awareness.value)

# Set DPI Awareness  (Windows 10 and 8)
errorCode = ctypes.windll.shcore.SetProcessDpiAwareness(2)

# Set DPI Awareness  (Windows 7 and Vista)
success = ctypes.windll.user32.SetProcessDPIAware()

# Load DLL for SLM functionalities
cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\Blink_C_wrapper")
slm_lib = CDLL("Blink_C_wrapper") # slm_lib.function() can now be uesd like the functions in C but in python

# Load DLL for image generation
cdll.LoadLibrary("C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\SDK\\ImageGen")
image_lib = CDLL("ImageGen")


# Call the constructor for the SLM
slm_lib.Create_SDK(1)

# load LUT
file_path = "C:\\Program Files\\Meadowlark Optics\\Blink 1920 HDMI\\LUT Files\\custom_linear_LUT.LUT"
file_path_c = ctypes.c_char_p(file_path.encode('utf-8'))
slm_lib.Load_lut(file_path_c)

# indicate that our images are black and white -> don't really see why this is necessary?
RGB = c_uint(0)
is_eight_bit_image = c_uint(1)

# SLM dimensions
height = c_uint(slm_lib.Get_Height())
width = c_uint(slm_lib.Get_Width())
depth = c_uint(slm_lib.Get_Depth())
bytesPerPixel = 1 #for not RGBA? #4; #RGBA
center_x = c_uint(width.value//2)
center_y = c_uint(height.value//2)
print("height: ", height.value, "width: ", width.value, "depth: ", depth.value)


# generate the 256 patterns
sample_num=256
pattern = numpy.ones((height.value, width.value), dtype=numpy.uint8) 
slm_array = numpy.empty([sample_num, height.value, width.value], dtype=numpy.uint8)
for i in range(sample_num):
    slm_array[i] = pattern * i
    print(f'pattern: {slm_array[i]}')


# loop for measurements no cam!
pbar = tqdm(range(sample_num))
for k in pbar:
    slm_array_ptr = slm_array[k].flatten().ctypes.data_as(POINTER(c_ubyte))
    # define WFC as zero (what alfonso did)
    wfc = pattern * 0
    wfc_ptr = wfc.flatten().ctypes.data_as(POINTER(c_ubyte))
    # generate the images for the SLM
    image_lib.Generate_Solid(slm_array_ptr, wfc_ptr, width.value, height.value, depth.value, is_eight_bit_image, RGB)
    # write the image on the slm
    slm_lib.Write_image(slm_array_ptr, is_eight_bit_image)
    if k == 0:
        time.sleep(1) # Alfonso did this for the first image because the SLM needs a bit longer for the intial big jump
    time.sleep(0.1)


time.sleep(100)

# Always call Delete_SDK before exiting
slm_lib.Delete_SDK()