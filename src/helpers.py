import numpy as np
import matplotlib.pyplot as plt
from pyAndorSDK3 import AndorSDK3
import time

def plot_intensity(images, slm_array):
    # average the intensity of the cam
    intensity = np.mean(images, axis=(1,2))
    max_intensity = np.max(intensity)
    min_intensity = np.min(intensity)
    uncentered_intensity = intensity/max_intensity
    intensity = (intensity-min_intensity)/(max_intensity-min_intensity)
    print(f'shape: {slm_array[:,0,0].shape}, {slm_array[0,:,0].shape}, {slm_array[0,0,:].shape}')
    # display pixel value of SLM vs. image value cam (-> intensity)
    fig, (ax1, ax2) = plt.subplots(2, 1)
    indices = np.linspace(0, 29, num=30)
    ax1.plot(slm_array[:,0,0], intensity, '.-')
    #ax1.plot(indices, intensity, '.-')
    ax1.set_ylabel('intensity')
    ax1.set_xlabel('grayscale value')

    # plot phase vs. pixel value
    phase = np.arccos(2*intensity - 1)/(np.pi)
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