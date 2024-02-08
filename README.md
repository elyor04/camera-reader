# hikvision-ip-camera-reader

* ### works on linux 64-bit and windows 64-bit
* ### may work on linux 32-bit and windows 32-bit


## Install on Linux

### Update your system and install pip
```
sudo apt update && sudo apt -y upgrade && sudo apt -y install python3-pip
```

### To get a better performance install Intel GPU driver and libraries
* WARNING: if you don't have Intel GPU, please skip this part
* NOTE: it's working well with Linux Ubuntu 22.04.3 LTS 64-bit
```
sudo apt -y install intel-opencl-icd opencl-headers ocl-icd-libopencl1 ocl-icd-opencl-dev
```

### Install required library
```
pip install opencv-python
```


## Install on Windows

### Install required library
```
pip install opencv-python
```
