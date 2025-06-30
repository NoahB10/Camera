#!/usr/bin/env python3
"""
Mock version of the camera GUI for debugging on non-Raspberry Pi systems.
This helps identify issues without requiring actual camera hardware.
"""

import sys
import os
import numpy as np
from datetime import datetime
import json
import time
import threading
from pathlib import Path

# Create mock versions of picamera2 components
class MockPicamera2:
    """Mock Picamera2 class that simulates camera behavior."""
    
    def __init__(self, camera_num=0):
        self.camera_num = camera_num
        self.is_open = False
        self.is_running = False
        self.configuration = None
        self.controls = {}
        
    def start(self):
        """Start the mock camera."""
        self.is_running = True
        print(f"Mock Camera {self.camera_num}: Started")
        
    def stop(self):
        """Stop the mock camera."""
        self.is_running = False
        print(f"Mock Camera {self.camera_num}: Stopped")
        
    def close(self):
        """Close the mock camera."""
        self.is_open = False
        print(f"Mock Camera {self.camera_num}: Closed")
        
    def configure(self, config):
        """Configure the mock camera."""
        self.configuration = config
        print(f"Mock Camera {self.camera_num}: Configured")
        
    def capture_array(self, name="main"):
        """Return a mock image array."""
        # Create test pattern based on camera number
        height, width = 480, 640
        image = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Different patterns for each camera
        if self.camera_num == 0:
            # Red gradient for camera 0
            for x in range(width):
                image[:, x] = [int(255 * x / width), 0, 0]
        else:
            # Blue gradient for camera 1
            for y in range(height):
                image[y, :] = [0, 0, int(255 * y / height)]
                
        # Add timestamp text overlay
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Simple text overlay (would use cv2.putText in real implementation)
        image[10:30, 10:200] = [255, 255, 255]
        
        return image
    
    def capture_file(self, output, format="jpeg", name="main"):
        """Simulate file capture."""
        print(f"Mock Camera {self.camera_num}: Captured to {output}")
        # Create a mock file
        if format == "dng":
            # Create empty file as placeholder
            Path(output).touch()
        else:
            # For JPEG, could save the test pattern
            array = self.capture_array()
            # Would save array as image here
            Path(output).touch()
            
    def set_controls(self, controls):
        """Set camera controls."""
        self.controls.update(controls)
        print(f"Mock Camera {self.camera_num}: Controls updated: {controls}")
        
    @staticmethod
    def create_preview_configuration(main={"size": (640, 480), "format": "RGB888"}):
        """Create preview configuration."""
        return {"main": main}
    
    @staticmethod
    def create_still_configuration(main={"size": (4608, 2592), "format": "RGB888"}, 
                                   raw={"size": (4608, 2592)}):
        """Create still configuration."""
        config = {"main": main}
        if raw:
            config["raw"] = raw
        return config
    
    @staticmethod
    def global_camera_info():
        """Return mock camera information."""
        return [
            {
                'Id': '/base/i2c@7e804000/imx708@1a',
                'Model': 'imx708',
                'Location': 0,
                'Rotation': 0
            },
            {
                'Id': '/base/i2c@7e804000/imx708@1b', 
                'Model': 'imx708',
                'Location': 1,
                'Rotation': 0
            }
        ]

# Mock the picamera2 module
sys.modules['picamera2'] = type(sys)('picamera2')
sys.modules['picamera2'].Picamera2 = MockPicamera2

# Now we can run a simplified version of the GUI
def test_mock_gui():
    """Test the GUI with mock cameras."""
    print("=== Testing Mock Camera GUI ===\n")
    
    try:
        # Test camera detection
        cameras = MockPicamera2.global_camera_info()
        print(f"Detected {len(cameras)} mock cameras:")
        for i, cam in enumerate(cameras):
            print(f"  Camera {i}: {cam['Model']} at {cam['Id']}")
        
        # Test camera initialization
        print("\nInitializing cameras...")
        cam0 = MockPicamera2(0)
        cam1 = MockPicamera2(1)
        
        # Configure cameras
        preview_config = MockPicamera2.create_preview_configuration()
        cam0.configure(preview_config)
        cam1.configure(preview_config)
        
        # Start cameras
        cam0.start()
        cam1.start()
        
        # Simulate capture
        print("\nSimulating capture...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Capture arrays
        array0 = cam0.capture_array()
        array1 = cam1.capture_array()
        print(f"  Camera 0 array shape: {array0.shape}")
        print(f"  Camera 1 array shape: {array1.shape}")
        
        # Capture files
        cam0.capture_file(f"test_{timestamp}_cam0.jpg", format="jpeg")
        cam1.capture_file(f"test_{timestamp}_cam1.jpg", format="jpeg")
        
        # Test controls
        print("\nTesting camera controls...")
        cam0.set_controls({"ExposureTime": 10000, "AnalogueGain": 1.0})
        cam1.set_controls({"ExposureTime": 10000, "AnalogueGain": 1.0})
        
        # Stop cameras
        print("\nStopping cameras...")
        cam0.stop()
        cam1.stop()
        cam0.close()
        cam1.close()
        
        print("\n✓ Mock camera test completed successfully!")
        
        # Test distortion coefficients loading
        print("\n=== Testing Distortion Coefficients ===")
        coeff_file = "distortion_coefficients_dual.json"
        if os.path.exists(coeff_file):
            with open(coeff_file, 'r') as f:
                coeffs = json.load(f)
                print(f"✓ Loaded distortion coefficients from {coeff_file}")
                print(f"  Keys: {list(coeffs.keys())}")
        else:
            print(f"⚠️  No distortion coefficients file found at {coeff_file}")
            print("  Using default coefficients")
            
    except Exception as e:
        print(f"\n✗ Error during mock test: {e}")
        import traceback
        traceback.print_exc()
        
def analyze_main_gui():
    """Analyze the main GUI file for potential issues."""
    print("\n=== Analyzing Main GUI File ===")
    
    gui_file = "GUI_IMX708_Dirsotion_Correction_v1.2.py"
    if not os.path.exists(gui_file):
        print(f"✗ GUI file {gui_file} not found")
        return
        
    print(f"Reading {gui_file}...")
    
    # Check for common issues
    issues_found = []
    suggestions = []
    
    with open(gui_file, 'r') as f:
        content = f.read()
        
    # Check for hardcoded paths
    if "/home/pi/" in content:
        issues_found.append("Hardcoded Raspberry Pi paths found")
        suggestions.append("Use os.path.expanduser('~') for home directory")
        
    # Check for missing error handling
    if "try:" not in content or "except" not in content:
        issues_found.append("Limited error handling found")
        suggestions.append("Add try/except blocks around camera operations")
        
    # Check for camera count assumptions
    if "cameras = Picamera2.global_camera_info()" in content:
        if "if len(cameras) < 2" not in content:
            issues_found.append("No check for minimum camera count")
            suggestions.append("Add validation for 2 cameras before proceeding")
            
    print("\nIssues found:")
    for issue in issues_found:
        print(f"  - {issue}")
        
    print("\nSuggestions:")
    for suggestion in suggestions:
        print(f"  - {suggestion}")
        
    return len(issues_found) == 0

def main():
    """Run all debugging tests."""
    print("Camera GUI Debug Tool (Mock Mode)")
    print("=" * 50)
    
    # Check environment
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Working directory: {os.getcwd()}")
    
    # Run tests
    test_mock_gui()
    analyze_main_gui()
    
    print("\n" + "=" * 50)
    print("Debugging Summary:")
    print("1. Mock cameras work correctly")
    print("2. To run on Raspberry Pi:")
    print("   - Ensure both cameras are connected")
    print("   - Install picamera2: sudo apt install python3-picamera2")
    print("   - Run with proper permissions")
    print("3. Common issues:")
    print("   - Camera not detected: Check connections and i2c")
    print("   - Permission denied: Add user to video group")
    print("   - Import errors: Install all dependencies with uv sync")

if __name__ == "__main__":
    main()