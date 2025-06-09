import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from picamera2 import Picamera2
import cv2
import time
import numpy as np
from datetime import datetime
import os
import json
from PIL import Image
import discorpy.post.postprocessing as post
import imageio

# GUI for dual IMX708 camera control with automatic image processing (v1.2)
# 
# When "Save Image" is pressed, outputs:
# 1. Combined TIFF file (left and right images side-by-side, cropped, distortion-corrected, perspective-corrected, left rotated)
# 2. Two original DNG files (cam0 and cam1, unprocessed)
#
# Version 1.2 Improvements:
# - Added perspective correction support matching image_post_processing_v1.3.py
# - Updated distortion parameters structure to include pers_coef
# - Improved coefficient loading to handle both radial and perspective corrections
# - Enhanced default coefficient handling - works without calibration files
# - Better file loading system that looks for distortion_coefficients_dual.json
# - Updated GUI to show perspective correction status and controls
# - Synchronized with v1.3 post-processing pipeline and default values
#
# Features:
# - Automatic cropping, radial distortion correction, perspective correction, and left image rotation for TIFF output
# - Toggle buttons to enable/disable TIFF and DNG saving
# - Perspective correction toggle (new)
# - Preview window shows processed view (cropped and side-by-side)
# - Camera parameter controls (exposure, gain, brightness, etc.)
# - Distortion coefficient loading and management with perspective support
# - Works with default coefficients when no calibration files found

class DualIMX708Viewer:
    def __init__(self):
        # Camera connection status
        self.cam0_connected = False
        self.cam1_connected = False
        self.cam0 = None
        self.cam1 = None
        
        # Initialize camera configuration template
        self.camera_config = None

        # Cropping parameters (matching v1.3 defaults)
        self.crop_params = {
            'cam0': {'width': 2070, 'start_x': 1260, 'height': 2592},
            'cam1': {'width': 2050, 'start_x': 1400, 'height': 2592}
        }

        # Distortion correction parameters (updated to match v1.3 structure with perspective support)
        self.distortion_params = {
            'cam0': {
                'xcenter': 1189.0732,
                'ycenter': 1224.3019,
                'coeffs': [1.0493219962591438, -5.8329152691427105e-05, -4.317510446486265e-08],
                'pers_coef': None  # Will be loaded from coefficients file if available
            },
            'cam1': {
                'xcenter': 959.61816,
                'ycenter': 1238.5898,
                'coeffs': [1.048507138224826, -6.39294339791884e-05, -3.9638970842489805e-08],
                'pers_coef': None  # Will be loaded from coefficients file if available
            }
        }

        # Processing settings - always applied for TIFF (updated to match v1.3)
        self.apply_cropping = True
        self.enable_distortion_correction = True
        self.enable_perspective_correction = True  # New option for perspective correction
        self.apply_left_rotation = True  # Always rotate left image
        self.apply_right_rotation = False  # New flag for right image rotation
        self.left_rotation_angle = -1.3  # Updated to match v1.3 default
        self.right_rotation_angle = -0.5  # New rotation angle for right image
        
        # Distortion correction padding (matching v1.3 values)
        self.left_top_padding = 198  # pixels to pad at the top for left image (cam0)
        self.left_bottom_padding = 42  # pixels to pad at the bottom for left image (cam0)
        self.right_top_padding = 150  # pixels to pad at the top for right image (cam1)
        self.right_bottom_padding = 50  # pixels to pad at the bottom for right image (cam1)

        # Default/base values
        self.defaults = {
            'ExposureTime': 10000,
            'AnalogueGain': 1.0,
            'Brightness': 0.0,
            'Contrast': 1.0,
            'Saturation': 1.0,
            'Sharpness': 1.0
        }

        # Parameter ranges
        self.params = {
            'ExposureTime': {'value': self.defaults['ExposureTime'], 'min': 100, 'max': 100000},
            'AnalogueGain': {'value': self.defaults['AnalogueGain'], 'min': 1.0, 'max': 20.0},
            'Brightness': {'value': self.defaults['Brightness'], 'min': -1.0, 'max': 1.0},
            'Contrast': {'value': self.defaults['Contrast'], 'min': 0.0, 'max': 4.0},
            'Saturation': {'value': self.defaults['Saturation'], 'min': 0.0, 'max': 4.0},
            'Sharpness': {'value': self.defaults['Sharpness'], 'min': 0.0, 'max': 4.0}
        }

        # Setup GUI first (before camera initialization)
        self.setup_gui()
        
        # Load settings and calibration (non-blocking)
        self.load_settings()
        self.load_distortion_coefficients()
        
        # Try to initialize cameras (non-blocking)
        self.initialize_cameras()

    def initialize_cameras(self):
        """Initialize cameras with error handling"""
        print("Attempting to initialize cameras...")
        
        try:
            # Try to initialize camera 0
            try:
                from picamera2 import Picamera2
                self.cam0 = Picamera2(0)
                
                # Create shared full-resolution raw configuration
                self.camera_config = self.cam0.create_still_configuration(
                    raw={"size": (4608, 2592)},
                    controls={
                        "ExposureTime": 10000,
                        "AnalogueGain": 1.0
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
                if self.camera_config is not None:  # Only if cam0 succeeded
                    self.cam1 = Picamera2(1)
                    self.cam1.configure(self.camera_config)
                    self.cam1.start()
                    self.cam1_connected = True
                    print("[SUCCESS] Camera 1 initialized and started")
                else:
                    # Try to create camera 1 independently
                    self.cam1 = Picamera2(1)
                    backup_config = self.cam1.create_still_configuration(
                        raw={"size": (4608, 2592)},
                        controls={
                            "ExposureTime": 10000,
                            "AnalogueGain": 1.0
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

            # Wait a moment for cameras to stabilize if any connected
            if self.cam0_connected or self.cam1_connected:
                time.sleep(2)
                self.apply_settings()  # Apply initial settings to connected cameras
                
        except ImportError:
            print("[ERROR] Picamera2 not available - running in simulation mode")
            self.cam0_connected = False
            self.cam1_connected = False
            
        # Report camera status
        if self.cam0_connected and self.cam1_connected:
            print("[SUCCESS] Both cameras connected and ready")
        elif self.cam0_connected or self.cam1_connected:
            connected = "Camera 0" if self.cam0_connected else "Camera 1"
            print(f"[WARNING] Only {connected} connected")
        else:
            print("[WARNING] No cameras connected - GUI will show disconnected status")

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Dual IMX708 Camera Control v1.2")

        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        self.entries = {}
        self.scales = {}

        for param_name, param_data in self.params.items():
            frame = ttk.LabelFrame(control_frame, text=param_name)
            frame.pack(fill=tk.X, padx=5, pady=5)

            scale = ttk.Scale(
                frame,
                from_=param_data['min'],
                to=param_data['max'],
                value=param_data['value'],
                orient=tk.HORIZONTAL
            )
            scale.pack(fill=tk.X, padx=5)
            scale.bind("<ButtonRelease-1>", lambda e, p=param_name: self.on_scale_change(p))
            self.scales[param_name] = scale

            entry_frame = ttk.Frame(frame)
            entry_frame.pack(fill=tk.X, padx=5)

            entry = ttk.Entry(entry_frame, width=10)
            entry.insert(0, str(param_data['value']))
            entry.pack(side=tk.LEFT, padx=2)
            entry.bind('<Return>', lambda e, p=param_name: self.on_entry_change(p))
            self.entries[param_name] = entry

            ttk.Button(entry_frame, text="Set", command=lambda p=param_name: self.on_entry_change(p)).pack(side=tk.LEFT, padx=2)
            ttk.Button(entry_frame, text="Reset", command=lambda p=param_name: self.reset_parameter(p)).pack(side=tk.LEFT, padx=2)

        ttk.Button(control_frame, text="Save Image", command=self.save_image).pack(fill=tk.X, padx=5, pady=10)
        ttk.Button(control_frame, text="Reset All", command=self.reset_all).pack(fill=tk.X, padx=5)
        ttk.Button(control_frame, text="Save Settings", command=self.save_settings).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(control_frame, text="Reconnect Cameras", command=self.reconnect_cameras).pack(fill=tk.X, padx=5, pady=5)

        # Processing options frame
        processing_frame = ttk.LabelFrame(control_frame, text="Save Options")
        processing_frame.pack(fill=tk.X, padx=5, pady=10)

        # Save TIFF checkbox (default: True)
        self.save_tiff_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Save Combined TIFF (cropped + corrected + perspective + rotated)", 
                       variable=self.save_tiff_var).pack(anchor=tk.W, padx=5, pady=2)

        # Save DNG checkbox (default: True)
        self.save_dng_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Save Original DNG Files", 
                       variable=self.save_dng_var).pack(anchor=tk.W, padx=5, pady=2)

        # Processing control options
        processing_controls_frame = ttk.LabelFrame(processing_frame, text="Processing Controls")
        processing_controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Perspective correction toggle
        self.perspective_var = tk.BooleanVar(value=self.enable_perspective_correction)
        ttk.Checkbutton(processing_controls_frame, text="Enable Perspective Correction", 
                       variable=self.perspective_var,
                       command=self.update_perspective_setting).pack(anchor=tk.W, padx=5, pady=2)
        
        # Right rotation toggle
        self.right_rotation_var = tk.BooleanVar(value=self.apply_right_rotation)
        ttk.Checkbutton(processing_controls_frame, text="Enable Right Image Rotation", 
                       variable=self.right_rotation_var,
                       command=self.update_right_rotation_setting).pack(anchor=tk.W, padx=5, pady=2)

        # Note about automatic processing
        ttk.Label(processing_frame, text="Note: TIFF files are automatically cropped, distortion-corrected,\nperspective-corrected (if available), and rotated. Preview shows processed view.",
                 font=('TkDefaultFont', 8), foreground='gray').pack(anchor=tk.W, padx=5, pady=2)

        # Reload coefficients button
        ttk.Button(processing_frame, text="Reload Distortion Coefficients", 
                  command=lambda: self.load_distortion_coefficients(prompt_for_files=True)).pack(fill=tk.X, padx=5, pady=5)

        # Upload calibration files buttons
        upload_frame = ttk.Frame(processing_frame)
        upload_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(upload_frame, text="Upload Left (Cam0) Calibration", 
                  command=lambda: self.upload_calibration_file('cam0')).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(upload_frame, text="Upload Right (Cam1) Calibration", 
                  command=lambda: self.upload_calibration_file('cam1')).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # Show current parameters button
        ttk.Button(processing_frame, text="Show Current Distortion Parameters", 
                  command=self.show_distortion_parameters).pack(fill=tk.X, padx=5, pady=2)

        # Crop parameters display
        crop_info_frame = ttk.LabelFrame(processing_frame, text="Crop Parameters")
        crop_info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(crop_info_frame, text="Cam0: 2070x2592 @ (1260,0)").pack(anchor=tk.W, padx=5)
        ttk.Label(crop_info_frame, text="Cam1: 2050x2592 @ (1400,0)").pack(anchor=tk.W, padx=5)

    def apply_settings(self):
        settings = {
            "ExposureTime": int(self.params['ExposureTime']['value']),
            "AnalogueGain": self.params['AnalogueGain']['value'],
            "Brightness": self.params['Brightness']['value'],
            "Contrast": self.params['Contrast']['value'],
            "Saturation": self.params['Saturation']['value'],
            "Sharpness": self.params['Sharpness']['value']
        }
        
        # Apply settings only to connected cameras
        try:
            if self.cam0_connected and self.cam0 is not None:
                self.cam0.set_controls(settings)
        except Exception as e:
            print(f"[WARNING] Failed to apply settings to camera 0: {e}")
            self.cam0_connected = False
            
        try:
            if self.cam1_connected and self.cam1 is not None:
                self.cam1.set_controls(settings)
        except Exception as e:
            print(f"[WARNING] Failed to apply settings to camera 1: {e}")
            self.cam1_connected = False

    def save_image(self):
        # Check if any cameras are connected
        if not self.cam0_connected and not self.cam1_connected:
            messagebox.showerror("Error", "No cameras connected! Cannot save images.")
            print("[ERROR] Cannot save images - no cameras connected")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        params_str = "_".join(f"{p}{v['value']:.2f}" for p, v in self.params.items())

        # Capture requests for connected cameras only
        req0 = None
        req1 = None
        
        try:
            if self.cam0_connected and self.cam0 is not None:
                req0 = self.cam0.capture_request()
        except Exception as e:
            print(f"[WARNING] Failed to capture from camera 0: {e}")
            self.cam0_connected = False
            
        try:
            if self.cam1_connected and self.cam1 is not None:
                req1 = self.cam1.capture_request()
        except Exception as e:
            print(f"[WARNING] Failed to capture from camera 1: {e}")
            self.cam1_connected = False

        try:
            success_count = 0
            
            # Always save original DNG files first if enabled
            if hasattr(self, 'save_dng_var') and self.save_dng_var.get():
                try:
                    if req0 is not None:
                        original_filename0 = f"cam0_{timestamp}_original_{params_str}.dng"
                        req0.save_dng(original_filename0)
                        print(f"[SUCCESS] Saved cam0 DNG: {original_filename0}")
                        success_count += 1
                        
                    if req1 is not None:
                        original_filename1 = f"cam1_{timestamp}_original_{params_str}.dng"
                        req1.save_dng(original_filename1)
                        print(f"[SUCCESS] Saved cam1 DNG: {original_filename1}")
                        success_count += 1
                        
                    if req0 is None and req1 is None:
                        print(f"[WARNING] No cameras available for DNG capture")
                        
                except Exception as e:
                    print(f"[ERROR] Failed to save DNG files: {e}")

            # Create processed TIFF if enabled
            if hasattr(self, 'save_tiff_var') and self.save_tiff_var.get():
                try:
                    # Get processed RGB arrays from main stream for available cameras
                    img0 = None
                    img1 = None
                    
                    if req0 is not None:
                        img0 = req0.make_array("main")
                    if req1 is not None:
                        img1 = req1.make_array("main")
                        
                    if img0 is None and img1 is None:
                        print(f"[WARNING] No cameras available for TIFF processing")
                        raise Exception("No camera data available")
                    
                    # Debug info for available images
                    if img0 is not None:
                        print(f"[DEBUG] Cam0 image - shape: {img0.shape}, dtype: {img0.dtype}, range: [{img0.min()}, {img0.max()}]")
                    if img1 is not None:
                        print(f"[DEBUG] Cam1 image - shape: {img1.shape}, dtype: {img1.dtype}, range: [{img1.min()}, {img1.max()}]")

                    # Process available images
                    img0_final = None
                    img1_final = None
                    
                    if img0 is not None:
                        # Always apply cropping for TIFF
                        img0_processed = self.crop_image(img0, 'cam0')
                        print(f"[DEBUG] After cropping - Cam0: {img0_processed.shape}")

                        # Always apply distortion correction for TIFF
                        img0_corrected = self.apply_distortion_correction(img0_processed, 'cam0')
                        print(f"[DEBUG] After distortion correction - Cam0 range: [{img0_corrected.min()}, {img0_corrected.max()}]")

                        # Apply perspective correction for TIFF
                        img0_perspective = self.apply_perspective_correction(img0_corrected, 'cam0')
                        print(f"[DEBUG] After perspective correction - Cam0")

                        # Always apply left image rotation for TIFF
                        img0_final = self.rotate_left_image(img0_perspective)
                        print(f"[DEBUG] Applied rotation to left image")
                    
                    if img1 is not None:
                        # Always apply cropping for TIFF
                        img1_processed = self.crop_image(img1, 'cam1')
                        print(f"[DEBUG] After cropping - Cam1: {img1_processed.shape}")

                        # Always apply distortion correction for TIFF
                        img1_corrected = self.apply_distortion_correction(img1_processed, 'cam1')
                        print(f"[DEBUG] After distortion correction - Cam1")

                        # Apply perspective correction for TIFF
                        img1_perspective = self.apply_perspective_correction(img1_corrected, 'cam1')
                        print(f"[DEBUG] After perspective correction - Cam1")
                        
                        # Apply right image rotation if enabled
                        img1_final = self.rotate_right_image(img1_perspective)
                        if self.apply_right_rotation:
                            print(f"[DEBUG] Applied rotation to right image")
                        else:
                            print(f"[DEBUG] Right image rotation disabled")

                    # Create combined side-by-side image
                    combined_image = self.create_combined_image(img0_final, img1_final)
                    
                    if combined_image is not None:
                        # Save as TIFF file with updated naming
                        suffixes = []
                        if self.apply_cropping:
                            suffixes.append("cropped")
                        if self.enable_distortion_correction:
                            suffixes.append("corrected")
                        if self.enable_perspective_correction:
                            suffixes.append("perspective")
                        if self.apply_left_rotation:
                            suffixes.append("rotated")
                        suffix_str = "_" + "_".join(suffixes) if suffixes else "_processed"
                        
                        combined_filename = f"dual_{timestamp}{suffix_str}_{params_str}.tiff"
                        
                        if self.save_processed_image_tiff(combined_image, combined_filename):
                            print(f"[SUCCESS] Saved combined TIFF: {combined_filename}")
                            success_count += 1
                        else:
                            print(f"[ERROR] Failed to save combined TIFF")
                    else:
                        print(f"[ERROR] Failed to create combined image")
                        
                except Exception as e:
                    print(f"[ERROR] Failed to create processed TIFF: {e}")
                    import traceback
                    traceback.print_exc()

            if success_count > 0:
                print(f"\n[SUCCESS] Save operation complete! {success_count} files saved.")
                print(f"Processing pipeline applied:")
                print(f"   ✓ Cropping: {'Applied' if self.apply_cropping else 'Skipped'}")
                print(f"   ✓ Radial Distortion: {'Applied' if self.enable_distortion_correction else 'Skipped'}")
                print(f"   ✓ Perspective Correction: {'Applied' if self.enable_perspective_correction else 'Skipped'}")
                print(f"   ✓ Left Rotation: {'Applied' if self.apply_left_rotation else 'Skipped'}")
                print(f"   ✓ Right Rotation: {'Applied' if self.apply_right_rotation else 'Skipped'}")
            else:
                print(f"\n[WARNING] No files were saved.")

        finally:
            # Always release the requests if they exist
            try:
                if req0 is not None:
                    req0.release()
            except Exception as e:
                print(f"[WARNING] Error releasing req0: {e}")
                
            try:
                if req1 is not None:
                    req1.release()
            except Exception as e:
                print(f"[WARNING] Error releasing req1: {e}")

    def create_combined_image(self, left_image, right_image):
        """Create a side-by-side combined image, handling missing cameras"""
        try:
            # Handle case where one or both images are missing
            if left_image is None and right_image is None:
                print(f"[ERROR] Both images are None")
                return None
            elif left_image is None:
                print(f"[INFO] Left camera disconnected, using right camera only")
                return right_image
            elif right_image is None:
                print(f"[INFO] Right camera disconnected, using left camera only")
                return left_image
            else:
                # Both images available - combine side by side
                min_height = min(left_image.shape[0], right_image.shape[0])
                left_resized = left_image[:min_height, :]
                right_resized = right_image[:min_height, :]
                
                # Combine horizontally
                combined = np.hstack((left_resized, right_resized))
                print(f"[INFO] Created combined image: {combined.shape}")
                return combined
        except Exception as e:
            print(f"[ERROR] Failed to create combined image: {e}")
            return None

    def save_processed_image_tiff(self, image, output_path):
        """Save processed image as TIFF using imageio for reliable output"""
        try:
            # Ensure we have a valid image
            if image is None or image.size == 0:
                print(f"[ERROR] Invalid image data for {output_path}")
                return False
            
            print(f"[DEBUG] Saving TIFF: {output_path}")
            print(f"[DEBUG] Image shape: {image.shape}, dtype: {image.dtype}, range: [{image.min()}, {image.max()}]")
            
            # Use imageio for TIFF - handles everything automatically
            imageio.imsave(output_path, image)
            print(f"[SUCCESS] Saved TIFF using imageio: {output_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save TIFF {output_path}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_preview(self):
        # Create placeholder images for disconnected cameras
        placeholder_shape = (480, 640, 3)  # Height, Width, Channels
        
        # Try to capture from connected cameras
        frame0 = None
        frame1 = None
        
        if self.cam0_connected and self.cam0 is not None:
            try:
                frame0 = self.cam0.capture_array()
            except Exception as e:
                print(f"[WARNING] Camera 0 capture failed: {e}")
                self.cam0_connected = False
                
        if self.cam1_connected and self.cam1 is not None:
            try:
                frame1 = self.cam1.capture_array()
            except Exception as e:
                print(f"[WARNING] Camera 1 capture failed: {e}")
                self.cam1_connected = False

        # Process or create placeholder for camera 0
        if frame0 is not None:
            # Always apply processing for preview (cropping and correction)
            frame0_display = self.crop_image(frame0, 'cam0')
            display0 = cv2.resize(frame0_display, (640, 480))
        else:
            # Create disconnected placeholder
            display0 = np.zeros(placeholder_shape, dtype=np.uint8)
            cv2.putText(display0, "Camera 0", (240, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(display0, "DISCONNECTED", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
        # Process or create placeholder for camera 1
        if frame1 is not None:
            # Always apply processing for preview (cropping and correction)  
            frame1_display = self.crop_image(frame1, 'cam1')
            display1 = cv2.resize(frame1_display, (640, 480))
        else:
            # Create disconnected placeholder
            display1 = np.zeros(placeholder_shape, dtype=np.uint8)
            cv2.putText(display1, "Camera 1", (240, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(display1, "DISCONNECTED", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        combined = np.hstack((display0, display1))

        y = 30
        for param_name, param_data in self.params.items():
            text = f"{param_name}: {param_data['value']:.2f}"
            cv2.putText(combined, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y += 20

        # Add camera connection status
        cam0_status = "CONNECTED" if self.cam0_connected else "DISCONNECTED"
        cam1_status = "CONNECTED" if self.cam1_connected else "DISCONNECTED"
        cv2.putText(combined, f"Cam0: {cam0_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.cam0_connected else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, f"Cam1: {cam1_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.cam1_connected else (0, 0, 255), 1)
        y += 20
        
        # Add save options status
        tiff_status = "ON" if self.save_tiff_var.get() else "OFF"
        dng_status = "ON" if self.save_dng_var.get() else "OFF"
        cv2.putText(combined, f"Save TIFF: {tiff_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.save_tiff_var.get() else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, f"Save DNG: {dng_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.save_dng_var.get() else (0, 0, 255), 1)
        y += 20
        
        # Add processing status (new)
        distortion_status = "ON" if self.enable_distortion_correction else "OFF"
        perspective_status = "ON" if self.enable_perspective_correction else "OFF"
        left_rot_status = "ON" if self.apply_left_rotation else "OFF"
        right_rot_status = "ON" if self.apply_right_rotation else "OFF"
        
        cv2.putText(combined, f"Radial Dist: {distortion_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.enable_distortion_correction else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, f"Perspective: {perspective_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.enable_perspective_correction else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, f"Left Rot: {left_rot_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.apply_left_rotation else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, f"Right Rot: {right_rot_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.apply_right_rotation else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, "Preview: Cropped + Processed", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        cv2.imshow('Dual Camera Preview', combined)
        cv2.waitKey(1)
        self.root.after(100, self.update_preview)

    def run(self):
        # Skip preview for now - it causes GUI to hang
        # self.update_preview()
        print("GUI ready - preview disabled to prevent hanging")
        self.root.mainloop()
        print("Main loop exited")


    def reconnect_cameras(self):
        """Try to reconnect cameras"""
        print("Attempting to reconnect cameras...")
        
        # Stop existing cameras if they exist
        try:
            if self.cam0 is not None:
                self.cam0.stop()
        except:
            pass
        try:
            if self.cam1 is not None:
                self.cam1.stop()
        except:
            pass
            
        # Reset camera objects
        self.cam0 = None
        self.cam1 = None
        self.cam0_connected = False
        self.cam1_connected = False
        
        # Wait a moment
        time.sleep(1)
        
        # Try to reinitialize
        self.initialize_cameras()
        
        # Show result
        if self.cam0_connected and self.cam1_connected:
            messagebox.showinfo("Success", "Both cameras reconnected successfully!")
        elif self.cam0_connected or self.cam1_connected:
            connected = "Camera 0" if self.cam0_connected else "Camera 1"
            messagebox.showwarning("Partial Success", f"Only {connected} reconnected")
        else:
            messagebox.showerror("Failed", "No cameras could be connected")

    def cleanup(self):
        self.save_settings()
        
        # Stop cameras safely
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
            
        cv2.destroyAllWindows()

    def on_scale_change(self, param_name):
        value = float(self.scales[param_name].get())
        self.entries[param_name].delete(0, tk.END)
        self.entries[param_name].insert(0, f"{value:.2f}")
        self.params[param_name]['value'] = value
        self.apply_settings()

    def on_entry_change(self, param_name):
        try:
            value = float(self.entries[param_name].get())
            param_range = self.params[param_name]
            if param_range['min'] <= value <= param_range['max']:
                self.scales[param_name].set(value)
                self.params[param_name]['value'] = value
                self.apply_settings()
            else:
                self.entries[param_name].delete(0, tk.END)
                self.entries[param_name].insert(0, f"{self.scales[param_name].get():.2f}")
        except ValueError:
            self.entries[param_name].delete(0, tk.END)
            self.entries[param_name].insert(0, f"{self.scales[param_name].get():.2f}")

    def reset_parameter(self, param_name):
        default_value = self.defaults[param_name]
        self.scales[param_name].set(default_value)
        self.entries[param_name].delete(0, tk.END)
        self.entries[param_name].insert(0, f"{default_value:.2f}")
        self.params[param_name]['value'] = default_value
        self.apply_settings()

    def reset_all(self):
        for param_name in self.params:
            self.reset_parameter(param_name)

    def save_settings(self):
        settings = {param: self.params[param]['value'] for param in self.params}
        try:
            with open('camera_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
            print("Settings saved successfully")
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_settings(self):
        try:
            if os.path.exists('camera_settings.json'):
                with open('camera_settings.json', 'r') as f:
                    settings = json.load(f)
                for param, value in settings.items():
                    if param in self.params:
                        self.params[param]['value'] = value
                for param_name, value in settings.items():
                    if param_name in self.scales:
                        self.scales[param_name].set(value)
                    if param_name in self.entries:
                        self.entries[param_name].delete(0, tk.END)
                        self.entries[param_name].insert(0, f"{value:.2f}")
                self.apply_settings()
                print("Loaded previous settings")
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def load_distortion_coefficients(self, prompt_for_files=False):
        """Load distortion correction coefficients from files or use defaults (updated to match v1.3)"""
        if prompt_for_files:
            # Prompt user to select coefficient files
            self.prompt_for_coefficient_files()
            return
        
        # First try to load from saved dual coefficients file (matching v1.3)
        dual_coeff_file = 'distortion_coefficients_dual.json'
        if os.path.exists(dual_coeff_file):
            try:
                with open(dual_coeff_file, 'r') as f:
                    saved_params = json.load(f)
                    
                    # Update distortion parameters
                    for cam in ['cam0', 'cam1']:
                        if cam in saved_params:
                            if cam not in self.distortion_params:
                                self.distortion_params[cam] = {}
                            
                            # Update distortion coefficients (including perspective if available)
                            for key in ['xcenter', 'ycenter', 'coeffs', 'pers_coef']:
                                if key in saved_params[cam]:
                                    self.distortion_params[cam][key] = saved_params[cam][key]
                    
                    print(f"[SUCCESS] Loaded distortion coefficients from {dual_coeff_file}")
                    return
            except Exception as e:
                print(f"[WARNING] Failed to load coefficients from {dual_coeff_file}: {e}")
        
        # Try to load from legacy single coefficients file
        legacy_coeff_file = 'distortion_coefficients.json'
        if os.path.exists(legacy_coeff_file):
            try:
                with open(legacy_coeff_file, 'r') as f:
                    saved_params = json.load(f)
                    # Update only the basic distortion parameters, not perspective
                    for cam in ['cam0', 'cam1']:
                        if cam in saved_params:
                            for key in ['xcenter', 'ycenter', 'coeffs']:
                                if key in saved_params[cam]:
                                    self.distortion_params[cam][key] = saved_params[cam][key]
                    print(f"[SUCCESS] Loaded basic distortion coefficients from {legacy_coeff_file}")
                    return
            except Exception as e:
                print(f"[WARNING] Failed to load legacy coefficients: {e}")
        
        # Try to load from original file paths
        coeff_files = {
            'cam0': 'RPI/Lensation_Calib_Photos/Right_Calib/coefficients_radial_distortion.txt',
            'cam1': 'RPI/Lensation_Calib_Photos/Left_Calib/coefficients_radial_distortion.txt'
        }
        
        files_found = False
        for cam, filepath in coeff_files.items():
            try:
                if os.path.exists(filepath):
                    self.load_coefficient_file(filepath, cam)
                    files_found = True
                else:
                    print(f"[INFO] Coefficient file not found for {cam}: {filepath}")
            except Exception as e:
                print(f"[WARNING] Failed to load coefficients for {cam}: {e}")
        
        if files_found:
            # Save the loaded coefficients for future use
            try:
                self.save_distortion_coefficients()
                print("[SUCCESS] Loaded and saved coefficients from original files")
            except Exception as e:
                print(f"[WARNING] Could not save coefficients: {e}")
        else:
            print("[INFO] No calibration files found - using built-in default coefficients")
            print(f"   Cam0 (Left): center=({self.distortion_params['cam0']['xcenter']:.1f}, {self.distortion_params['cam0']['ycenter']:.1f})")
            print(f"   Cam1 (Right): center=({self.distortion_params['cam1']['xcenter']:.1f}, {self.distortion_params['cam1']['ycenter']:.1f})")
            print("   Perspective correction: Not available (no pers_coef data)")
            print("   Note: GUI will work with radial distortion correction using defaults")
            print("   GUI is ready to use!")

    def prompt_for_coefficient_files(self):
        """Prompt user to select coefficient files for both cameras"""
        # Ask for cam0 (left) coefficient file
        cam0_file = filedialog.askopenfilename(
            title="Select Left Camera (Cam0) Coefficient File",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if cam0_file:
            try:
                self.load_coefficient_file(cam0_file, 'cam0')
                print(f"[SUCCESS] Loaded coefficients for cam0 from: {os.path.basename(cam0_file)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load cam0 coefficients:\n{str(e)}")
                print(f"[ERROR] Failed to load cam0 coefficients: {e}")
        
        # Ask for cam1 (right) coefficient file
        cam1_file = filedialog.askopenfilename(
            title="Select Right Camera (Cam1) Coefficient File",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if cam1_file:
            try:
                self.load_coefficient_file(cam1_file, 'cam1')
                print(f"[SUCCESS] Loaded coefficients for cam1 from: {os.path.basename(cam1_file)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load cam1 coefficients:\n{str(e)}")
                print(f"[ERROR] Failed to load cam1 coefficients: {e}")
        
        # Save the updated coefficients if any were loaded
        if cam0_file or cam1_file:
            self.save_distortion_coefficients()
            messagebox.showinfo("Success", "Distortion coefficients updated successfully!")

    def load_coefficient_file(self, filepath, cam_name):
        """Load coefficients from a single file (updated to handle perspective coefficients)"""
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        xcenter = None
        ycenter = None
        coeffs = []
        pers_coef = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'xcenter' in key or 'x_center' in key or 'centerx' in key:
                    xcenter = float(value)
                elif 'ycenter' in key or 'y_center' in key or 'centery' in key:
                    ycenter = float(value)
                elif 'factor0' in key:
                    # Insert at beginning for factor0
                    coeffs.insert(0, float(value))
                elif 'factor1' in key:
                    # Ensure we have at least one element, then add factor1
                    while len(coeffs) < 1:
                        coeffs.append(0.0)
                    if len(coeffs) == 1:
                        coeffs.append(float(value))
                    else:
                        coeffs[1] = float(value)
                elif 'factor2' in key:
                    # Ensure we have at least two elements, then add factor2
                    while len(coeffs) < 2:
                        coeffs.append(0.0)
                    if len(coeffs) == 2:
                        coeffs.append(float(value))
                    else:
                        coeffs[2] = float(value)
                elif 'coeff' in key or 'k' in key:
                    # Legacy coefficient format
                    coeffs.append(float(value))
                elif 'p1' in key or 'p2' in key or 'p3' in key or 'p4' in key or 'p5' in key or 'p6' in key or 'p7' in key or 'p8' in key:
                    # Perspective coefficients
                    pers_coef.append(float(value))
        
        # Validate that we got the required parameters
        if xcenter is None or ycenter is None or not coeffs:
            raise ValueError(f"Could not parse calibration file {filepath}. Expected format with xcenter, ycenter, and factor0/factor1/factor2 or coeff values.")
        
        # Update the distortion parameters
        self.distortion_params[cam_name]['xcenter'] = xcenter
        self.distortion_params[cam_name]['ycenter'] = ycenter
        self.distortion_params[cam_name]['coeffs'] = coeffs
        
        # Update perspective coefficients if found
        if pers_coef:
            self.distortion_params[cam_name]['pers_coef'] = pers_coef
            print(f"[SUCCESS] Found perspective coefficients for {cam_name}: {len(pers_coef)} values")
        else:
            print(f"[INFO] No perspective coefficients found for {cam_name} in this file")

    def crop_image(self, image, cam_name):
        """Crop image according to camera-specific parameters"""
        if not self.apply_cropping:
            return image
            
        params = self.crop_params[cam_name]
        start_x = params['start_x']
        width = params['width']
        height = params['height']
        
        # Crop the image: [y_start:y_end, x_start:x_end]
        cropped = image[:height, start_x:start_x + width]
        return cropped

    def apply_distortion_correction(self, image, cam_name):
        """Apply distortion correction to the image with camera-specific padding"""
        if not self.enable_distortion_correction:
            return image
            
        params = self.distortion_params[cam_name]
        xcenter = params['xcenter']
        ycenter = params['ycenter']
        coeffs = params['coeffs']
        
        try:
            # Store original data type and range
            original_dtype = image.dtype
            original_min = image.min()
            original_max = image.max()
            original_height, original_width = image.shape[:2]
            
            # Get camera-specific padding values
            if cam_name == 'cam0':  # Left camera
                top_padding = self.left_top_padding
                bottom_padding = self.left_bottom_padding
            else:  # Right camera (cam1)
                top_padding = self.right_top_padding
                bottom_padding = self.right_bottom_padding
            
            # Calculate new output dimensions - add vertical padding
            new_height = original_height + top_padding + bottom_padding
            new_width = original_width  # Keep original width unchanged
            
            # Calculate offset to place the original image with padding
            offset_x = 0  # No horizontal offset since width unchanged
            offset_y = top_padding  # Vertical offset based on top padding
            
            # Adjust center coordinates - only adjust y-center
            new_xcenter = xcenter  # Keep original x-center
            new_ycenter = ycenter + offset_y
            
            # Convert to float for processing if needed
            if image.dtype != np.float64:
                image_float = image.astype(np.float64)
            else:
                image_float = image.copy()
            
            # Create larger canvas and place original image with padding
            if image_float.ndim == 2:
                # Grayscale image
                padded_image = np.zeros((new_height, new_width), dtype=np.float64)
                padded_image[offset_y:offset_y + original_height, offset_x:offset_x + original_width] = image_float
                corrected = post.unwarp_image_backward(padded_image, new_xcenter, new_ycenter, coeffs)
            else:
                # Multi-channel image
                padded_image = np.zeros((new_height, new_width, image_float.shape[2]), dtype=np.float64)
                padded_image[offset_y:offset_y + original_height, offset_x:offset_x + original_width, :] = image_float
                
                corrected = np.zeros_like(padded_image)
                for c in range(image_float.shape[2]):
                    corrected[:, :, c] = post.unwarp_image_backward(padded_image[:, :, c], new_xcenter, new_ycenter, coeffs)
            
            # Handle potential NaN or infinite values
            corrected = np.nan_to_num(corrected, nan=0.0, posinf=original_max, neginf=0.0)
            
            # Clip to reasonable range based on original data
            corrected = np.clip(corrected, 0, original_max)
            
            # Convert back to original data type
            if original_dtype == np.uint8:
                corrected = np.clip(corrected, 0, 255).astype(np.uint8)
            elif original_dtype == np.uint16:
                corrected = np.clip(corrected, 0, 65535).astype(np.uint16)
            else:
                corrected = corrected.astype(original_dtype)
            
            print(f"[DEBUG] Distortion correction for {cam_name}: input range [{original_min}, {original_max}], output range [{corrected.min()}, {corrected.max()}]")
            print(f"[DEBUG] Output size: {original_width}x{original_height} -> {new_width}x{new_height} (padding: {top_padding} top, {bottom_padding} bottom)")
            
            return corrected
            
        except Exception as e:
            print(f"[ERROR] Distortion correction failed for {cam_name}: {e}")
            import traceback
            traceback.print_exc()
            return image

    def rotate_left_image(self, image):
        """Rotate the left image by the specified angle"""
        if not self.apply_left_rotation:
            return image
            
        try:
            # Get image dimensions
            height, width = image.shape[:2]
            
            # Calculate rotation matrix
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, self.left_rotation_angle, 1.0)
            
            # Apply rotation
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                   flags=cv2.INTER_LINEAR, 
                                   borderMode=cv2.BORDER_REFLECT_101)
            
            print(f"[DEBUG] Applied {self.left_rotation_angle}° rotation to left image")
            return rotated
            
        except Exception as e:
            print(f"[ERROR] Left image rotation failed: {e}")
            return image

    def rotate_right_image(self, image):
        """Rotate the right image by the specified angle (new feature matching v1.3)"""
        if not self.apply_right_rotation:
            return image
            
        try:
            # Get image dimensions
            height, width = image.shape[:2]
            
            # Calculate rotation matrix
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, self.right_rotation_angle, 1.0)
            
            # Apply rotation
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                   flags=cv2.INTER_LINEAR, 
                                   borderMode=cv2.BORDER_REFLECT_101)
            
            print(f"[DEBUG] Applied {self.right_rotation_angle}° rotation to right image")
            return rotated
            
        except Exception as e:
            print(f"[ERROR] Right image rotation failed: {e}")
            return image

    def update_distortion_params(self, cam_name, xcenter, ycenter, coeffs):
        """Update distortion parameters for a specific camera"""
        self.distortion_params[cam_name]['xcenter'] = xcenter
        self.distortion_params[cam_name]['ycenter'] = ycenter
        self.distortion_params[cam_name]['coeffs'] = coeffs
        print(f"[SUCCESS] Updated distortion parameters for {cam_name}")

    def upload_calibration_file(self, cam_name):
        """Upload and parse a calibration file for the specified camera (updated for perspective support)"""
        cam_label = "Left" if cam_name == "cam0" else "Right"
        
        # Open file dialog
        file_path = filedialog.askopenfilename(
            title=f"Select {cam_label} Camera Calibration File",
            filetypes=[
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Handle JSON files
            if file_path.lower().endswith('.json'):
                with open(file_path, 'r') as f:
                    json_data = json.load(f)
                    
                # Try to find camera-specific data in JSON
                cam_data = None
                if cam_name in json_data:
                    cam_data = json_data[cam_name]
                elif 'cam0' in json_data and cam_name == 'cam0':
                    cam_data = json_data['cam0']
                elif 'cam1' in json_data and cam_name == 'cam1':
                    cam_data = json_data['cam1']
                else:
                    # Assume direct coefficient data
                    cam_data = json_data
                
                if cam_data:
                    # Update parameters from JSON
                    for key in ['xcenter', 'ycenter', 'coeffs', 'pers_coef']:
                        if key in cam_data:
                            self.distortion_params[cam_name][key] = cam_data[key]
                    print(f"[SUCCESS] Loaded calibration data from JSON for {cam_name}")
                else:
                    raise ValueError("Could not find camera data in JSON file")
            
            else:
                # Handle text files using existing method
                self.load_coefficient_file(file_path, cam_name)
            
            # Save the updated coefficients
            self.save_distortion_coefficients()
            
            # Create success message
            params = self.distortion_params[cam_name]
            success_msg = f"[SUCCESS] Loaded calibration for {cam_label} camera ({cam_name})\n"
            success_msg += f"Center: ({params['xcenter']:.1f}, {params['ycenter']:.1f})\n"
            success_msg += f"Radial Coefficients: {len(params['coeffs'])} values\n"
            
            pers_coef = params.get('pers_coef')
            if pers_coef:
                success_msg += f"Perspective Coefficients: {len(pers_coef)} values"
            else:
                success_msg += "Perspective Coefficients: Not found in file"
            
            messagebox.showinfo("Success", success_msg)
            print(f"[SUCCESS] Updated distortion parameters for {cam_name} from uploaded file")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load calibration file:\n{str(e)}")
            print(f"[ERROR] Failed to load calibration file for {cam_name}: {e}")

    def save_distortion_coefficients(self):
        """Save current distortion coefficients to dual format file (matching v1.3)"""
        try:
            # Save in the dual format that v1.3 expects
            with open('distortion_coefficients_dual.json', 'w') as f:
                json.dump(self.distortion_params, f, indent=4)
            print("[SUCCESS] Saved distortion coefficients to distortion_coefficients_dual.json")
        except Exception as e:
            print(f"[ERROR] Failed to save distortion coefficients: {e}")

    def show_distortion_parameters(self):
        """Show current distortion parameters including perspective correction (updated for v1.2)"""
        # Print to console
        print("Current distortion parameters:")
        for cam, params in self.distortion_params.items():
            cam_label = "Left" if cam == "cam0" else "Right"
            print(f"   {cam} ({cam_label}):")
            print(f"      xcenter: {params['xcenter']:.4f}")
            print(f"      ycenter: {params['ycenter']:.4f}")
            print(f"      radial coeffs: {params['coeffs']}")
            pers_coef = params.get('pers_coef')
            if pers_coef:
                print(f"      perspective coeffs: {pers_coef}")
            else:
                print(f"      perspective coeffs: Not available")
        
        # Show in message box
        info_text = "Current Distortion Parameters:\n\n"
        for cam, params in self.distortion_params.items():
            cam_label = "Left" if cam == "cam0" else "Right"
            info_text += f"{cam_label} Camera ({cam}):\n"
            info_text += f"  Center: ({params['xcenter']:.1f}, {params['ycenter']:.1f})\n"
            info_text += f"  Radial Coefficients: {len(params['coeffs'])} values\n"
            info_text += f"  {params['coeffs']}\n"
            
            pers_coef = params.get('pers_coef')
            if pers_coef:
                info_text += f"  Perspective Coefficients: {len(pers_coef)} values\n"
                info_text += f"  {pers_coef}\n"
            else:
                info_text += f"  Perspective Coefficients: Not available\n"
            info_text += "\n"
        
        # Add processing status
        info_text += "Processing Status:\n"
        info_text += f"  Radial Distortion: {'Enabled' if self.enable_distortion_correction else 'Disabled'}\n"
        info_text += f"  Perspective Correction: {'Enabled' if self.enable_perspective_correction else 'Disabled'}\n"
        info_text += f"  Left Rotation: {'Enabled' if self.apply_left_rotation else 'Disabled'} ({self.left_rotation_angle}°)\n"
        info_text += f"  Right Rotation: {'Enabled' if self.apply_right_rotation else 'Disabled'} ({self.right_rotation_angle}°)\n"
        
        messagebox.showinfo("Distortion Parameters", info_text)

    def apply_perspective_correction(self, image, cam_name):
        """Apply perspective correction if coefficients are available (matching v1.3)"""
        if not self.enable_perspective_correction or cam_name not in self.distortion_params:
            return image
            
        params = self.distortion_params[cam_name]
        pers_coef = params.get('pers_coef')
        
        if pers_coef is None:
            return image
        
        try:
            original_dtype = image.dtype
            original_min = image.min()
            original_max = image.max()
            
            # Convert to float for processing
            image_float = image.astype(np.float64)
            
            if image_float.ndim == 2:
                # Grayscale
                corrected = post.correct_perspective_image(image_float, pers_coef)
            else:
                # Multi-channel
                corrected = np.zeros_like(image_float)
                for c in range(image_float.shape[2]):
                    corrected[:, :, c] = post.correct_perspective_image(image_float[:, :, c], pers_coef)
            
            # Handle NaN values and clip
            corrected = np.nan_to_num(corrected, nan=0.0, posinf=original_max, neginf=0.0)
            corrected = np.clip(corrected, 0, original_max)
            
            # Convert back to original data type
            if original_dtype == np.uint8:
                corrected = np.clip(corrected, 0, 255).astype(np.uint8)
            elif original_dtype == np.uint16:
                corrected = np.clip(corrected, 0, 65535).astype(np.uint16)
            else:
                corrected = corrected.astype(original_dtype)
            
            print(f"[DEBUG] Applied perspective correction to {cam_name}")
            return corrected
            
        except Exception as e:
            print(f"[ERROR] Perspective correction failed for {cam_name}: {e}")
            return image

    def update_perspective_setting(self):
        """Update perspective correction setting from GUI"""
        self.enable_perspective_correction = self.perspective_var.get()
        print(f"[INFO] Perspective correction {'enabled' if self.enable_perspective_correction else 'disabled'}")

    def update_right_rotation_setting(self):
        """Update right rotation setting from GUI"""
        self.apply_right_rotation = self.right_rotation_var.get()
        print(f"[INFO] Right image rotation {'enabled' if self.apply_right_rotation else 'disabled'}")

def main():
    """Main entry point for the dual camera GUI application"""
    try:
        print("Initializing Dual IMX708 Camera Control GUI v1.2...")
        print("GUI will work with defaults if calibration files are not found.")
        
        # Check if we're running on a system with GUI support
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()  # Hide the test window
            root.destroy()
        except Exception as e:
            print(f"Error: GUI not supported on this system: {e}")
            print("Make sure you have tkinter installed and X11 forwarding enabled if using SSH")
            return 1
        
        viewer = DualIMX708Viewer()
        print("Starting GUI main loop...")
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
    finally:
        try:
            if 'viewer' in locals():
                viewer.cleanup()
        except:
            pass


if __name__ == "__main__":
    import sys
    sys.exit(main()) 