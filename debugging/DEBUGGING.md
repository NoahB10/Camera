# Debugging Guide for Dual IMX708 Camera Control

This guide helps troubleshoot issues with the dual camera control software on Raspberry Pi.

## Quick Diagnostic

Run this command on your Raspberry Pi to identify the issue:

```bash
python3 test_raspberry_pi_debug.py
```

This will check all aspects of your camera setup and provide specific recommendations.

## Common Issues and Solutions

### 1. "No cameras detected" or "Failed to import picamera2"

**Symptoms:**
- `ImportError: No module named 'libcamera'`
- `No cameras found`
- Camera detection fails

**Solutions:**
```bash
# Enable camera interface
sudo raspi-config
# Navigate to Interface Options → Camera → Enable

# Install required packages
sudo apt update
sudo apt install python3-picamera2 libcamera-apps libcamera-tools

# Reboot after enabling camera
sudo reboot

# Test camera detection
libcamera-hello --list-cameras
```

### 2. "Permission denied" errors

**Symptoms:**
- `Permission denied: '/dev/video0'`
- Camera access blocked

**Solutions:**
```bash
# Add user to video group
sudo usermod -a -G video $USER

# Log out and back in, then verify
groups
# Should show "video" in the list

# Check device permissions
ls -la /dev/video*
```

### 3. "Camera already in use"

**Symptoms:**
- `Device or resource busy`
- One camera works but not both

**Solutions:**
```bash
# Kill conflicting processes
sudo pkill -f camera
sudo pkill -f libcamera

# Check for running camera services
ps aux | grep camera

# Disable conflicting services if needed
sudo systemctl disable camera-service-name
```

### 4. GUI doesn't appear (SSH users)

**Symptoms:**
- GUI fails to start over SSH
- `tkinter` import errors

**Solutions:**
```bash
# Enable X11 forwarding when connecting
ssh -X username@raspberry-pi-ip

# Install GUI packages
sudo apt install python3-tk

# Test GUI support
python3 -c "import tkinter; print('GUI OK')"
```

### 5. Python dependency issues

**Symptoms:**
- Import errors for numpy, opencv, etc.
- `uv sync` fails

**Solutions:**
```bash
# Install system dependencies
sudo apt install python3-dev build-essential libcap-dev

# Use UV for dependency management
uv sync

# Or install manually with pip
pip3 install opencv-python numpy pillow scipy scikit-image
```

## System Requirements Check

### Hardware Requirements
- Raspberry Pi 4 or newer
- Two IMX708 camera modules properly connected
- Sufficient power supply (recommend 3A+)

### Software Requirements
- Raspberry Pi OS (64-bit recommended)
- Python 3.9+
- libcamera system libraries
- Camera interface enabled in raspi-config

## Diagnostic Commands

### Check camera hardware
```bash
# List camera devices
libcamera-hello --list-cameras
v4l2-ctl --list-devices

# Check I2C devices (cameras should appear)
i2cdetect -y 1

# Check kernel messages for camera detection
dmesg | grep -i imx708
dmesg | grep -i camera
```

### Check software environment
```bash
# Python version (should be 3.9+)
python3 --version

# Check installed packages
pip3 list | grep -E 'picamera2|opencv|numpy'

# Test basic imports
python3 -c "from picamera2 import Picamera2; print('picamera2 OK')"
python3 -c "import cv2; print('OpenCV OK')"
```

### Check permissions and services
```bash
# User groups (should include 'video')
groups

# Device permissions
ls -la /dev/video* /dev/vchiq

# Running processes that might conflict
ps aux | grep -E 'camera|libcamera'
```

## Running the Software

### Method 1: Using UV (Recommended)
```bash
# Install dependencies
uv sync

# Run main GUI
uv run dual-camera-gui
# OR
uv run python GUI_IMX708_Dirsotion_Correction_v1.2.py
```

### Method 2: Using pip
```bash
# Install dependencies
pip3 install -r requirements.txt

# Run main GUI
python3 GUI_IMX708_Dirsotion_Correction_v1.2.py
```

## Testing Without Hardware

For testing the GUI logic without camera hardware:

```bash
# Run mock camera test
python3 debug_camera_mock.py

# This will simulate cameras and test the GUI components
```

## Getting Help

If issues persist after following this guide:

1. **Run the full diagnostic**: `python3 test_raspberry_pi_debug.py`
2. **Check system logs**: `sudo journalctl -u camera-related-service`
3. **Verify hardware**: Test cameras individually with `libcamera-hello`
4. **Update system**: `sudo apt update && sudo apt upgrade`

## File Outputs

When working correctly, the software creates:
- `{prefix}_{timestamp}_combined.tiff` - Processed side-by-side images
- `{prefix}_{timestamp}_camera0_original.dng` - Raw camera 0 file
- `{prefix}_{timestamp}_camera1_original.dng` - Raw camera 1 file
- `distortion_coefficients_dual.json` - Calibration data (if available)

## Additional Resources

- [Raspberry Pi Camera Documentation](https://www.raspberrypi.org/documentation/cameras/)
- [libcamera Documentation](https://libcamera.org/)
- [picamera2 Documentation](https://datasheets.raspberrypi.org/camera/picamera2-manual.pdf)