from pyAndorSDK3 import AndorSDK3

print("Connecting to camera")

sdk3 = AndorSDK3()
cam = sdk3.GetCamera(0)
print(cam.SerialNumber)

cam.AOIBinning = "1x1"
cam.AOILeft = 1
cam.AOIWidth = 2048
cam.AOIHeight = 2048
cam.AOITop = 1
cam.framerate=86.8

cam.ExposureTime = 0.0016
cam.CycleMode = "Continuous" #"Fixed"
acq = cam.acquire(timeout=20000)

#acq.save(".\image1_SLM.png")
# Ensure you have write permission for the destination location
acq.show()
