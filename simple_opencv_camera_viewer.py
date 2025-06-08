import cv2
import time
import numpy as np
from datetime import datetime
import os
import json
from picamera2 import Picamera2

class SimpleOpenCVCameraViewer:
    def __init__(self):
        # Camera connection status
        self.cam0_connected = False
        self.cam1_connected = False
        self.cam0 = None
        self.cam1 = None
        
        # Camera configuration
        self.camera_config = None
        
        # Default camera parameters
        self.params = {
            'ExposureTime': 10000,
            'AnalogueGain': 100,  # Scale to 1-2000 for trackbar
            'Brightness': 100,    # Scale to 0-200 for trackbar (0=-1.0, 100=0.0, 200=1.0)
            'Contrast': 100,      # Scale to 0-400 for trackbar (100=1.0)
            'Saturation': 100,    # Scale to 0-400 for trackbar (100=1.0)
            'Sharpness': 100      # Scale to 0-400 for trackbar (100=1.0)
        }
        
        # Parameter ranges for actual camera values
        self.param_ranges = {
            'ExposureTime': {'min': 100, 'max': 100000},
            'AnalogueGain': {'min': 1.0, 'max': 20.0},
            'Brightness': {'min': -1.0, 'max': 1.0},
            'Contrast': {'min': 0.0, 'max': 4.0},
            'Saturation': {'min': 0.0, 'max': 4.0},
            'Sharpness': {'min': 0.0, 'max': 4.0}
        }
        
        # Initialize cameras
        self.initialize_cameras()
        
        # Setup OpenCV windows and trackbars
        self.setup_opencv_interface()
        
        # Load previous settings
        self.load_settings()

    def initialize_cameras(self):
        """Initialize cameras with error handling"""
        print("Attempting to initialize cameras...")
        
        try:
            # Try to initialize camera 0
            try:
                self.cam0 = Picamera2(0)
                
                # Create shared configuration for consistent settings
                self.camera_config = self.cam0.create_still_configuration(
                    raw={"size": (4608, 2592)},
                    controls={
                        "ExposureTime": self.params['ExposureTime'],
                        "AnalogueGain": self.scale_to_actual('AnalogueGain', self.params['AnalogueGain'])
                    }
                )
                
                self.cam0.configure(self.camera_config)
                self.cam0.start()
                self.cam0_connected = True
                print("[SUCCESS] Camera 0 initialized and started")
                
            except Exception as e:
                print(f"[WARNING] Failed to initialize camera 0: {e}")
                self.cam0_connected = False
                self.cam0 = None

            # Try to initialize camera 1
            try:
                if self.camera_config is not None:
                    self.cam1 = Picamera2(1)
                    self.cam1.configure(self.camera_config)
                    self.cam1.start()
                    self.cam1_connected = True
                    print("[SUCCESS] Camera 1 initialized and started")
                else:
                    # Independent initialization
                    self.cam1 = Picamera2(1)
                    backup_config = self.cam1.create_still_configuration(
                        raw={"size": (4608, 2592)},
                        controls={
                            "ExposureTime": self.params['ExposureTime'],
                            "AnalogueGain": self.scale_to_actual('AnalogueGain', self.params['AnalogueGain'])
                        }
                    )
                    self.cam1.configure(backup_config)
                    self.cam1.start()
                    self.cam1_connected = True
                    print("[SUCCESS] Camera 1 initialized independently")
                    
            except Exception as e:
                print(f"[WARNING] Failed to initialize camera 1: {e}")
                self.cam1_connected = False
                self.cam1 = None

            # Wait for cameras to stabilize
            if self.cam0_connected or self.cam1_connected:
                time.sleep(2)
                
        except ImportError:
            print("[ERROR] Picamera2 not available - running in simulation mode")
            self.cam0_connected = False
            self.cam1_connected = False

    def setup_opencv_interface(self):
        """Setup OpenCV windows and trackbars"""
        # Create main camera windows
        cv2.namedWindow('Camera 0', cv2.WINDOW_RESIZABLE)
        cv2.namedWindow('Camera 1', cv2.WINDOW_RESIZABLE)
        cv2.namedWindow('Controls', cv2.WINDOW_NORMAL)
        
        # Position windows
        cv2.moveWindow('Camera 0', 100, 100)
        cv2.moveWindow('Camera 1', 700, 100)
        cv2.moveWindow('Controls', 100, 600)
        
        # Create control window with trackbars
        control_img = np.zeros((400, 600, 3), dtype=np.uint8)
        cv2.imshow('Controls', control_img)
        
        # Create trackbars for camera parameters
        cv2.createTrackbar('Exposure Time (x100)', 'Controls', 
                          self.params['ExposureTime'] // 100, 1000, 
                          lambda val: self.on_trackbar_change('ExposureTime', val * 100))
        
        cv2.createTrackbar('Analogue Gain', 'Controls', 
                          self.params['AnalogueGain'], 2000, 
                          lambda val: self.on_trackbar_change('AnalogueGain', val))
        
        cv2.createTrackbar('Brightness', 'Controls', 
                          self.params['Brightness'], 200, 
                          lambda val: self.on_trackbar_change('Brightness', val))
        
        cv2.createTrackbar('Contrast', 'Controls', 
                          self.params['Contrast'], 400, 
                          lambda val: self.on_trackbar_change('Contrast', val))
        
        cv2.createTrackbar('Saturation', 'Controls', 
                          self.params['Saturation'], 400, 
                          lambda val: self.on_trackbar_change('Saturation', val))
        
        cv2.createTrackbar('Sharpness', 'Controls', 
                          self.params['Sharpness'], 400, 
                          lambda val: self.on_trackbar_change('Sharpness', val))

    def scale_to_actual(self, param_name, scaled_value):
        """Convert trackbar value to actual camera parameter value"""
        if param_name == 'ExposureTime':
            return int(scaled_value)
        elif param_name == 'AnalogueGain':
            # Scale 0-2000 to 1.0-20.0
            return 1.0 + (scaled_value / 2000.0) * 19.0
        elif param_name == 'Brightness':
            # Scale 0-200 to -1.0-1.0
            return (scaled_value - 100) / 100.0
        elif param_name in ['Contrast', 'Saturation', 'Sharpness']:
            # Scale 0-400 to 0.0-4.0
            return scaled_value / 100.0
        return scaled_value

    def on_trackbar_change(self, param_name, value):
        """Handle trackbar changes"""
        self.params[param_name] = value
        self.apply_camera_settings()

    def apply_camera_settings(self):
        """Apply current parameter values to cameras"""
        settings = {
            "ExposureTime": int(self.params['ExposureTime']),
            "AnalogueGain": self.scale_to_actual('AnalogueGain', self.params['AnalogueGain']),
            "Brightness": self.scale_to_actual('Brightness', self.params['Brightness']),
            "Contrast": self.scale_to_actual('Contrast', self.params['Contrast']),
            "Saturation": self.scale_to_actual('Saturation', self.params['Saturation']),
            "Sharpness": self.scale_to_actual('Sharpness', self.params['Sharpness'])
        }
        
        try:
            if self.cam0_connected and self.cam0 is not None:
                self.cam0.set_controls(settings)
        except Exception as e:
            print(f"[WARNING] Failed to apply settings to camera 0: {e}")
            
        try:
            if self.cam1_connected and self.cam1 is not None:
                self.cam1.set_controls(settings)
        except Exception as e:
            print(f"[WARNING] Failed to apply settings to camera 1: {e}")

    def add_overlay_text(self, image, camera_name, connected):
        """Add parameter overlay to camera image"""
        if image is None:
            return image
            
        overlay = image.copy()
        
        # Connection status
        status_color = (0, 255, 0) if connected else (0, 0, 255)
        status_text = "CONNECTED" if connected else "DISCONNECTED"
        cv2.putText(overlay, f"{camera_name}: {status_text}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        if connected:
            # Add parameter values
            y_offset = 60
            params_display = [
                f"Exposure: {self.params['ExposureTime']}",
                f"Gain: {self.scale_to_actual('AnalogueGain', self.params['AnalogueGain']):.2f}",
                f"Brightness: {self.scale_to_actual('Brightness', self.params['Brightness']):.2f}",
                f"Contrast: {self.scale_to_actual('Contrast', self.params['Contrast']):.2f}",
                f"Saturation: {self.scale_to_actual('Saturation', self.params['Saturation']):.2f}",
                f"Sharpness: {self.scale_to_actual('Sharpness', self.params['Sharpness']):.2f}"
            ]
            
            for param_text in params_display:
                cv2.putText(overlay, param_text, (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 25
        
        # Add instructions
        instructions = [
            "Press 'S' to save images",
            "Press 'R' to reset parameters", 
            "Press 'Q' to quit",
            "Use trackbars to adjust settings"
        ]
        
        y_start = overlay.shape[0] - len(instructions) * 25 - 10
        for i, instruction in enumerate(instructions):
            cv2.putText(overlay, instruction, (10, y_start + i * 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        return overlay

    def update_control_window(self):
        """Update the control window with current status"""
        control_img = np.zeros((400, 600, 3), dtype=np.uint8)
        
        # Title
        cv2.putText(control_img, "Simple Dual Camera Control", (20, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Connection status
        cam0_status = "Connected" if self.cam0_connected else "Disconnected"
        cam1_status = "Connected" if self.cam1_connected else "Disconnected"
        
        cam0_color = (0, 255, 0) if self.cam0_connected else (0, 0, 255)
        cam1_color = (0, 255, 0) if self.cam1_connected else (0, 0, 255)
        
        cv2.putText(control_img, f"Camera 0: {cam0_status}", (20, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, cam0_color, 2)
        cv2.putText(control_img, f"Camera 1: {cam1_status}", (20, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, cam1_color, 2)
        
        # Current parameter values
        y_offset = 140
        cv2.putText(control_img, "Current Parameters:", (20, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        y_offset += 30
        
        param_texts = [
            f"Exposure Time: {self.params['ExposureTime']}",
            f"Analogue Gain: {self.scale_to_actual('AnalogueGain', self.params['AnalogueGain']):.2f}",
            f"Brightness: {self.scale_to_actual('Brightness', self.params['Brightness']):.2f}",
            f"Contrast: {self.scale_to_actual('Contrast', self.params['Contrast']):.2f}",
            f"Saturation: {self.scale_to_actual('Saturation', self.params['Saturation']):.2f}",
            f"Sharpness: {self.scale_to_actual('Sharpness', self.params['Sharpness']):.2f}"
        ]
        
        for param_text in param_texts:
            cv2.putText(control_img, param_text, (20, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset += 25
        
        cv2.imshow('Controls', control_img)

    def save_images(self):
        """Save images from both cameras"""
        if not self.cam0_connected and not self.cam1_connected:
            print("[ERROR] No cameras connected! Cannot save images.")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            success_count = 0
            
            # Capture and save from camera 0
            if self.cam0_connected and self.cam0 is not None:
                try:
                    req0 = self.cam0.capture_request()
                    
                    # Save DNG
                    dng_filename0 = f"cam0_{timestamp}_raw.dng"
                    req0.save_dng(dng_filename0)
                    print(f"[SUCCESS] Saved cam0 DNG: {dng_filename0}")
                    
                    # Save TIFF
                    img0 = req0.make_array("main")
                    tiff_filename0 = f"cam0_{timestamp}_raw.tiff"
                    cv2.imwrite(tiff_filename0, cv2.cvtColor(img0, cv2.COLOR_RGB2BGR))
                    print(f"[SUCCESS] Saved cam0 TIFF: {tiff_filename0}")
                    
                    req0.release()
                    success_count += 2
                    
                except Exception as e:
                    print(f"[ERROR] Failed to save from camera 0: {e}")
            
            # Capture and save from camera 1
            if self.cam1_connected and self.cam1 is not None:
                try:
                    req1 = self.cam1.capture_request()
                    
                    # Save DNG
                    dng_filename1 = f"cam1_{timestamp}_raw.dng"
                    req1.save_dng(dng_filename1)
                    print(f"[SUCCESS] Saved cam1 DNG: {dng_filename1}")
                    
                    # Save TIFF
                    img1 = req1.make_array("main")
                    tiff_filename1 = f"cam1_{timestamp}_raw.tiff"
                    cv2.imwrite(tiff_filename1, cv2.cvtColor(img1, cv2.COLOR_RGB2BGR))
                    print(f"[SUCCESS] Saved cam1 TIFF: {tiff_filename1}")
                    
                    req1.release()
                    success_count += 2
                    
                except Exception as e:
                    print(f"[ERROR] Failed to save from camera 1: {e}")
            
            print(f"\n[SUCCESS] Save operation complete! {success_count} files saved.")
            
        except Exception as e:
            print(f"[ERROR] Save operation failed: {e}")

    def reset_parameters(self):
        """Reset all parameters to defaults"""
        defaults = {
            'ExposureTime': 10000,
            'AnalogueGain': 100,
            'Brightness': 100,
            'Contrast': 100,
            'Saturation': 100,
            'Sharpness': 100
        }
        
        self.params.update(defaults)
        
        # Update trackbars
        cv2.setTrackbarPos('Exposure Time (x100)', 'Controls', defaults['ExposureTime'] // 100)
        cv2.setTrackbarPos('Analogue Gain', 'Controls', defaults['AnalogueGain'])
        cv2.setTrackbarPos('Brightness', 'Controls', defaults['Brightness'])
        cv2.setTrackbarPos('Contrast', 'Controls', defaults['Contrast'])
        cv2.setTrackbarPos('Saturation', 'Controls', defaults['Saturation'])
        cv2.setTrackbarPos('Sharpness', 'Controls', defaults['Sharpness'])
        
        self.apply_camera_settings()
        print("[INFO] Parameters reset to defaults")

    def save_settings(self):
        """Save current settings to file"""
        try:
            with open('opencv_camera_settings.json', 'w') as f:
                json.dump(self.params, f, indent=4)
            print("[SUCCESS] Settings saved")
        except Exception as e:
            print(f"[ERROR] Failed to save settings: {e}")

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists('opencv_camera_settings.json'):
                with open('opencv_camera_settings.json', 'r') as f:
                    saved_params = json.load(f)
                    
                self.params.update(saved_params)
                
                # Update trackbars
                cv2.setTrackbarPos('Exposure Time (x100)', 'Controls', self.params['ExposureTime'] // 100)
                cv2.setTrackbarPos('Analogue Gain', 'Controls', self.params['AnalogueGain'])
                cv2.setTrackbarPos('Brightness', 'Controls', self.params['Brightness'])
                cv2.setTrackbarPos('Contrast', 'Controls', self.params['Contrast'])
                cv2.setTrackbarPos('Saturation', 'Controls', self.params['Saturation'])
                cv2.setTrackbarPos('Sharpness', 'Controls', self.params['Sharpness'])
                
                self.apply_camera_settings()
                print("[SUCCESS] Loaded previous settings")
                
        except Exception as e:
            print(f"[WARNING] Failed to load settings: {e}")

    def run(self):
        """Main loop for camera display"""
        print("\n" + "="*60)
        print("Simple OpenCV Dual Camera Viewer")
        print("="*60)
        print("Controls:")
        print("  S - Save images (DNG + TIFF)")
        print("  R - Reset parameters to defaults")
        print("  Q - Quit application")
        print("  Use trackbars in Controls window to adjust camera settings")
        print("="*60 + "\n")
        
        while True:
            # Update control window
            self.update_control_window()
            
            # Capture and display camera 0
            if self.cam0_connected and self.cam0 is not None:
                try:
                    frame0 = self.cam0.capture_array()
                    frame0_resized = cv2.resize(frame0, (800, 600))
                    frame0_with_overlay = self.add_overlay_text(frame0_resized, "Camera 0", True)
                    cv2.imshow('Camera 0', frame0_with_overlay)
                except Exception as e:
                    print(f"[WARNING] Camera 0 capture failed: {e}")
                    self.cam0_connected = False
            else:
                # Show disconnected placeholder
                placeholder0 = np.zeros((600, 800, 3), dtype=np.uint8)
                placeholder0 = self.add_overlay_text(placeholder0, "Camera 0", False)
                cv2.imshow('Camera 0', placeholder0)
            
            # Capture and display camera 1
            if self.cam1_connected and self.cam1 is not None:
                try:
                    frame1 = self.cam1.capture_array()
                    frame1_resized = cv2.resize(frame1, (800, 600))
                    frame1_with_overlay = self.add_overlay_text(frame1_resized, "Camera 1", True)
                    cv2.imshow('Camera 1', frame1_with_overlay)
                except Exception as e:
                    print(f"[WARNING] Camera 1 capture failed: {e}")
                    self.cam1_connected = False
            else:
                # Show disconnected placeholder
                placeholder1 = np.zeros((600, 800, 3), dtype=np.uint8)
                placeholder1 = self.add_overlay_text(placeholder1, "Camera 1", False)
                cv2.imshow('Camera 1', placeholder1)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == ord('Q'):
                print("\nQuitting application...")
                break
            elif key == ord('s') or key == ord('S'):
                print("\nSaving images...")
                self.save_images()
            elif key == ord('r') or key == ord('R'):
                print("\nResetting parameters...")
                self.reset_parameters()
        
        # Cleanup
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up...")
        
        # Save settings
        self.save_settings()
        
        # Stop cameras
        try:
            if self.cam0 is not None and self.cam0_connected:
                self.cam0.stop()
        except Exception as e:
            print(f"[WARNING] Error stopping camera 0: {e}")
            
        try:
            if self.cam1 is not None and self.cam1_connected:
                self.cam1.stop()
        except Exception as e:
            print(f"[WARNING] Error stopping camera 1: {e}")
        
        # Close OpenCV windows
        cv2.destroyAllWindows()
        print("Cleanup complete!")


def main():
    """Main entry point"""
    try:
        print("Initializing Simple OpenCV Dual Camera Viewer...")
        viewer = SimpleOpenCVCameraViewer()
        viewer.run()
        return 0
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())