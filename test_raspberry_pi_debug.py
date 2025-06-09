#!/usr/bin/env python3
"""
Diagnostic script to run on Raspberry Pi to identify camera issues.
This script checks various aspects of the camera setup.
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print("STDOUT:")
        print(result.stdout if result.stdout else "(empty)")
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        print(f"\nReturn code: {result.returncode}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def main():
    """Run diagnostic checks."""
    print("Raspberry Pi Camera Diagnostic Tool")
    print("=" * 60)
    
    checks = [
        # System information
        ("uname -a", "System information"),
        ("cat /etc/os-release | head -5", "OS version"),
        
        # Python environment
        ("python3 --version", "Python version"),
        ("pip3 list | grep -E 'picamera2|opencv|numpy|PIL'", "Relevant Python packages"),
        
        # Camera hardware checks
        ("vcgencmd get_camera", "Camera detection (legacy)"),
        ("ls -la /dev/video*", "Video devices"),
        ("v4l2-ctl --list-devices", "V4L2 devices"),
        
        # I2C and camera module checks
        ("i2cdetect -y 1", "I2C devices on bus 1"),
        ("dmesg | grep -i camera | tail -10", "Camera-related kernel messages"),
        ("dmesg | grep -i imx708 | tail -10", "IMX708-specific messages"),
        
        # libcamera checks
        ("libcamera-hello --list-cameras", "libcamera camera list"),
        ("dpkg -l | grep libcamera", "libcamera packages"),
        
        # User permissions
        ("groups", "User groups"),
        ("ls -la /dev/vchiq /dev/video* 2>/dev/null", "Device permissions"),
        
        # Camera module info
        ("cat /proc/device-tree/soc/i2c0mux/i2c@1/imx708@1a/status 2>/dev/null || echo 'Not found'", "Camera 0 status"),
        ("cat /proc/device-tree/soc/i2c0mux/i2c@1/imx708@1b/status 2>/dev/null || echo 'Not found'", "Camera 1 status"),
    ]
    
    passed = 0
    failed = 0
    
    for cmd, desc in checks:
        if run_command(cmd, desc):
            passed += 1
        else:
            failed += 1
    
    # Python module test
    print(f"\n{'='*60}")
    print("Testing Python imports")
    print("-" * 60)
    
    modules = ["picamera2", "cv2", "numpy", "PIL", "tkinter"]
    for module in modules:
        try:
            if module == "tkinter":
                import tkinter
                print(f"✓ {module} imported successfully")
            elif module == "picamera2":
                from picamera2 import Picamera2
                print(f"✓ {module} imported successfully")
                # Try to list cameras
                try:
                    cameras = Picamera2.global_camera_info()
                    print(f"  Found {len(cameras)} cameras")
                    for i, cam in enumerate(cameras):
                        print(f"  Camera {i}: {cam}")
                except Exception as e:
                    print(f"  Error listing cameras: {e}")
            elif module == "cv2":
                import cv2
                print(f"✓ {module} imported successfully (version: {cv2.__version__})")
            elif module == "numpy":
                import numpy
                print(f"✓ {module} imported successfully (version: {numpy.__version__})")
            elif module == "PIL":
                from PIL import Image
                print(f"✓ {module} imported successfully")
        except ImportError as e:
            print(f"✗ {module} import failed: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"System checks: {passed} passed, {failed} failed")
    
    print("\nCommon issues and solutions:")
    print("1. 'No cameras detected':")
    print("   - Check camera cable connections")
    print("   - Enable camera interface: sudo raspi-config")
    print("   - Reboot after enabling")
    
    print("\n2. 'Permission denied':")
    print("   - Add user to video group: sudo usermod -a -G video $USER")
    print("   - Log out and back in")
    
    print("\n3. 'Module not found':")
    print("   - Install picamera2: sudo apt install python3-picamera2")
    print("   - Install dependencies: pip3 install opencv-python numpy pillow")
    
    print("\n4. 'Camera already in use':")
    print("   - Kill other camera processes: sudo pkill -f camera")
    print("   - Check for conflicting services")
    
    print("\nTo run the GUI after fixing issues:")
    print("  python3 GUI_IMX708_Dirsotion_Correction_v1.2.py")

if __name__ == "__main__":
    main()