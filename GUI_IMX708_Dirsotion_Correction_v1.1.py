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

# GUI for dual IMX708 camera control with automatic image processing (v1.1)
# 
# When "Save Image" is pressed, outputs:
# 1. Combined TIFF file (left and right images side-by-side, cropped, distortion-corrected, left rotated)
# 2. Two original DNG files (cam0 and cam1, unprocessed)
#
# Version 1.1 Improvements:
# - Automatic processing: cropping, distortion correction, and left image rotation always applied to TIFF
# - Simplified UI: removed individual processing toggles, added save option toggles
# - Fixed TIFF saving using imageio for reliable output
# - Preview always shows processed view (cropped and side-by-side)
# - Better error handling and status reporting
#
# Features:
# - Automatic cropping, distortion correction, and left image rotation for TIFF output
# - Toggle buttons to enable/disable TIFF and DNG saving
# - Preview window shows processed view (cropped and side-by-side)
# - Camera parameter controls (exposure, gain, brightness, etc.)
# - Distortion coefficient loading and management

class DualIMX708Viewer:
    def __init__(self):
        # Initialize both cameras
        self.cam0 = Picamera2(0)
        self.cam1 = Picamera2(1)

        # Shared full-resolution raw configuration
        self.camera_config = self.cam0.create_still_configuration(
            raw={"size": (4608, 2592)},
            controls={
                "ExposureTime": 10000,
                "AnalogueGain": 1.0
            }
        )

        self.cam0.configure(self.camera_config)
        self.cam1.configure(self.camera_config)

        # Cropping parameters
        self.crop_params = {
            'cam0': {'width': 2200, 'start_x': 1230, 'height': 2592},
            'cam1': {'width': 2155, 'start_x': 1336, 'height': 2592}
        }

        # Distortion correction parameters (default values - will be loaded from files)
        self.distortion_params = {
            'cam0': {
                'xcenter': 1189.0732,
                'ycenter': 1224.3019,
                'coeffs': [1.0493219962591438, -5.8329152691427105e-05, -4.317510446486265e-08]
            },
            'cam1': {
                'xcenter': 959.61816,
                'ycenter': 1238.5898,
                'coeffs': [1.048507138224826, -6.39294339791884e-05, -3.9638970842489805e-08]
            }
        }

        # Processing settings - always applied for TIFF
        self.apply_cropping = True
        self.enable_distortion_correction = True
        self.apply_left_rotation = True  # Always rotate left image
        self.left_rotation_angle = -2  # Rotation angle in degrees

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

        self.setup_gui()
        self.cam0.start()
        self.cam1.start()
        time.sleep(2)
        self.load_settings()
        self.load_distortion_coefficients()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Dual IMX708 Camera Control v1.1")

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

        # Processing options frame
        processing_frame = ttk.LabelFrame(control_frame, text="Save Options")
        processing_frame.pack(fill=tk.X, padx=5, pady=10)

        # Save TIFF checkbox (default: True)
        self.save_tiff_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Save Combined TIFF (cropped + corrected + rotated)", 
                       variable=self.save_tiff_var).pack(anchor=tk.W, padx=5, pady=2)

        # Save DNG checkbox (default: True)
        self.save_dng_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Save Original DNG Files", 
                       variable=self.save_dng_var).pack(anchor=tk.W, padx=5, pady=2)

        # Note about automatic processing
        ttk.Label(processing_frame, text="Note: TIFF files are automatically cropped, distortion-corrected,\nand left image rotated. Preview shows processed view.",
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
        
        ttk.Label(crop_info_frame, text="Cam0: 2161x2592 @ (1284,0)").pack(anchor=tk.W, padx=5)
        ttk.Label(crop_info_frame, text="Cam1: 2088x2592 @ (1336,0)").pack(anchor=tk.W, padx=5)

    def apply_settings(self):
        settings = {
            "ExposureTime": int(self.params['ExposureTime']['value']),
            "AnalogueGain": self.params['AnalogueGain']['value'],
            "Brightness": self.params['Brightness']['value'],
            "Contrast": self.params['Contrast']['value'],
            "Saturation": self.params['Saturation']['value'],
            "Sharpness": self.params['Sharpness']['value']
        }
        self.cam0.set_controls(settings)
        self.cam1.set_controls(settings)

    def save_image(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        params_str = "_".join(f"{p}{v['value']:.2f}" for p, v in self.params.items())

        # Capture requests for both cameras
        req0 = self.cam0.capture_request()
        req1 = self.cam1.capture_request()

        try:
            success_count = 0
            
            # Always save original DNG files first if enabled
            if hasattr(self, 'save_dng_var') and self.save_dng_var.get():
                original_filename0 = f"cam0_{timestamp}_original_{params_str}.dng"
                original_filename1 = f"cam1_{timestamp}_original_{params_str}.dng"
                
                try:
                    req0.save_dng(original_filename0)
                    req1.save_dng(original_filename1)
                    print(f"[SUCCESS] Saved original DNG files:")
                    print(f"   {original_filename0}")
                    print(f"   {original_filename1}")
                    success_count += 2
                except Exception as e:
                    print(f"[ERROR] Failed to save original DNG files: {e}")

            # Create processed TIFF if enabled
            if hasattr(self, 'save_tiff_var') and self.save_tiff_var.get():
                try:
                    # Get processed RGB arrays from main stream
                    img0 = req0.make_array("main")
                    img1 = req1.make_array("main")
                    
                    print(f"[DEBUG] Original image shapes - Cam0: {img0.shape}, Cam1: {img1.shape}")
                    print(f"[DEBUG] Original image dtypes - Cam0: {img0.dtype}, Cam1: {img1.dtype}")
                    print(f"[DEBUG] Original image ranges - Cam0: [{img0.min()}, {img0.max()}], Cam1: [{img1.min()}, {img1.max()}]")

                    # Always apply cropping for TIFF
                    img0_processed = self.crop_image(img0, 'cam0')
                    img1_processed = self.crop_image(img1, 'cam1')
                    print(f"[DEBUG] After cropping - Cam0: {img0_processed.shape}, Cam1: {img1_processed.shape}")

                    # Always apply distortion correction for TIFF
                    img0_corrected = self.apply_distortion_correction(img0_processed, 'cam0')
                    img1_corrected = self.apply_distortion_correction(img1_processed, 'cam1')
                    print(f"[DEBUG] After distortion correction - Cam0 range: [{img0_corrected.min()}, {img0_corrected.max()}]")

                    # Always apply left image rotation for TIFF
                    img0_final = self.rotate_left_image(img0_corrected)
                    img1_final = img1_corrected
                    print(f"[DEBUG] Applied rotation to left image")

                    # Create combined side-by-side image
                    combined_image = self.create_combined_image(img0_final, img1_final)
                    
                    if combined_image is not None:
                        # Save as TIFF file
                        combined_filename = f"dual_{timestamp}_cropped_corrected_rotated_{params_str}.tiff"
                        
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
            else:
                print(f"\n[WARNING] No files were saved.")

        finally:
            # Always release the requests
            req0.release()
            req1.release()

    def create_combined_image(self, left_image, right_image):
        """Create a side-by-side combined image"""
        try:
            # Ensure both images have the same height
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
        frame0 = self.cam0.capture_array()
        frame1 = self.cam1.capture_array()

        # Always apply processing for preview (cropping and correction)
        frame0_display = self.crop_image(frame0, 'cam0')
        frame1_display = self.crop_image(frame1, 'cam1')

        display0 = cv2.resize(frame0_display, (640, 480))
        display1 = cv2.resize(frame1_display, (640, 480))
        combined = np.hstack((display0, display1))

        y = 30
        for param_name, param_data in self.params.items():
            text = f"{param_name}: {param_data['value']:.2f}"
            cv2.putText(combined, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y += 20

        # Add save options status
        tiff_status = "ON" if self.save_tiff_var.get() else "OFF"
        dng_status = "ON" if self.save_dng_var.get() else "OFF"
        cv2.putText(combined, f"Save TIFF: {tiff_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.save_tiff_var.get() else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, f"Save DNG: {dng_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.save_dng_var.get() else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, "Preview: Cropped + Processed", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        cv2.imshow('Dual Camera Preview', combined)
        cv2.waitKey(1)
        self.root.after(100, self.update_preview)

    def run(self):
        self.update_preview()
        self.root.mainloop()

    def cleanup(self):
        self.save_settings()
        self.cam0.stop()
        self.cam1.stop()
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
        """Load distortion correction coefficients from files or use defaults"""
        if prompt_for_files:
            # Prompt user to select coefficient files
            self.prompt_for_coefficient_files()
            return
            
        # First try to load from saved local files
        local_coeff_file = 'distortion_coefficients.json'
        if os.path.exists(local_coeff_file):
            try:
                with open(local_coeff_file, 'r') as f:
                    saved_params = json.load(f)
                    self.distortion_params.update(saved_params)
                    print("[SUCCESS] Loaded distortion coefficients from saved file")
                    return
            except Exception as e:
                print(f"[WARNING] Failed to load saved coefficients: {e}")
        
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
                    print(f"[WARNING] Coefficient file not found for {cam}: {filepath}")
            except Exception as e:
                print(f"[ERROR] Failed to load coefficients for {cam}: {e}")
        
        if files_found:
            # Save the loaded coefficients for future use
            self.save_distortion_coefficients()
        else:
            print("[INFO] Using default distortion coefficients (no calibration files found)")
            print(f"   Cam0 (Left): center=({self.distortion_params['cam0']['xcenter']:.1f}, {self.distortion_params['cam0']['ycenter']:.1f})")
            print(f"   Cam1 (Right): center=({self.distortion_params['cam1']['xcenter']:.1f}, {self.distortion_params['cam1']['ycenter']:.1f})")

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
        """Load coefficients from a single file"""
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        xcenter = None
        ycenter = None
        coeffs = []
        
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
        
        # Validate that we got the required parameters
        if xcenter is None or ycenter is None or not coeffs:
            raise ValueError(f"Could not parse calibration file {filepath}. Expected format with xcenter, ycenter, and factor0/factor1/factor2 or coeff values.")
        
        # Update the distortion parameters
        self.distortion_params[cam_name]['xcenter'] = xcenter
        self.distortion_params[cam_name]['ycenter'] = ycenter
        self.distortion_params[cam_name]['coeffs'] = coeffs

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
        """Apply distortion correction to the image"""
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
            
            # Convert to float for processing if needed
            if image.dtype != np.float64:
                image_float = image.astype(np.float64)
            else:
                image_float = image.copy()
            
            if image_float.ndim == 2:
                # Grayscale image
                corrected = post.unwarp_image_backward(image_float, xcenter, ycenter, coeffs)
            else:
                # Multi-channel image
                corrected = np.zeros_like(image_float)
                for c in range(image_float.shape[2]):
                    corrected[:, :, c] = post.unwarp_image_backward(image_float[:, :, c], xcenter, ycenter, coeffs)
            
            # Handle potential NaN or infinite values
            corrected = np.nan_to_num(corrected, nan=0.0, posinf=original_max, neginf=0.0)
            
            # Clip to reasonable range based on original data
            corrected = np.clip(corrected, 0, original_max * 1.1)  # Allow slight overflow
            
            # Convert back to original data type
            if original_dtype == np.uint8:
                corrected = np.clip(corrected, 0, 255).astype(np.uint8)
            elif original_dtype == np.uint16:
                corrected = np.clip(corrected, 0, 65535).astype(np.uint16)
            else:
                corrected = corrected.astype(original_dtype)
            
            print(f"[DEBUG] Distortion correction for {cam_name}: input range [{original_min}, {original_max}], output range [{corrected.min()}, {corrected.max()}]")
            
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

    def update_distortion_params(self, cam_name, xcenter, ycenter, coeffs):
        """Update distortion parameters for a specific camera"""
        self.distortion_params[cam_name]['xcenter'] = xcenter
        self.distortion_params[cam_name]['ycenter'] = ycenter
        self.distortion_params[cam_name]['coeffs'] = coeffs
        print(f"[SUCCESS] Updated distortion parameters for {cam_name}")

    def upload_calibration_file(self, cam_name):
        """Upload and parse a calibration file for the specified camera"""
        cam_label = "Left" if cam_name == "cam0" else "Right"
        
        # Open file dialog
        file_path = filedialog.askopenfilename(
            title=f"Select {cam_label} Camera Calibration File",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Parse the calibration file
            with open(file_path, 'r') as f:
                lines = f.readlines()
                
            # Extract parameters (assuming format: parameter=value)
            xcenter = None
            ycenter = None
            coeffs = []
            
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
                    elif 'coeff' in key or 'k' in key:
                        coeffs.append(float(value))
            
            # Validate that we got the required parameters
            if xcenter is None or ycenter is None or not coeffs:
                messagebox.showerror("Error", 
                    "Could not parse calibration file. Expected format:\n"
                    "xcenter=value\n"
                    "ycenter=value\n"
                    "coeff1=value\n"
                    "coeff2=value\n"
                    "...")
                return
            
            # Update the distortion parameters
            self.distortion_params[cam_name]['xcenter'] = xcenter
            self.distortion_params[cam_name]['ycenter'] = ycenter
            self.distortion_params[cam_name]['coeffs'] = coeffs
            
            # Save the updated coefficients
            self.save_distortion_coefficients()
            
            messagebox.showinfo("Success", 
                f"[SUCCESS] Loaded calibration for {cam_label} camera ({cam_name})\n"
                f"Center: ({xcenter:.1f}, {ycenter:.1f})\n"
                f"Coefficients: {len(coeffs)} values")
            
            print(f"[SUCCESS] Updated distortion parameters for {cam_name} from uploaded file")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load calibration file:\n{str(e)}")
            print(f"[ERROR] Failed to load calibration file for {cam_name}: {e}")

    def save_distortion_coefficients(self):
        """Save current distortion coefficients to a local file"""
        try:
            with open('distortion_coefficients.json', 'w') as f:
                json.dump(self.distortion_params, f, indent=4)
            print("[SUCCESS] Saved distortion coefficients to local file")
        except Exception as e:
            print(f"[ERROR] Failed to save distortion coefficients: {e}")

    def show_distortion_parameters(self):
        """Show current distortion parameters"""
        # Print to console
        print("Current distortion parameters:")
        for cam, params in self.distortion_params.items():
            cam_label = "Left" if cam == "cam0" else "Right"
            print(f"   {cam} ({cam_label}):")
            print(f"      xcenter: {params['xcenter']:.4f}")
            print(f"      ycenter: {params['ycenter']:.4f}")
            print(f"      coeffs: {params['coeffs']}")
        
        # Show in message box
        info_text = "Current Distortion Parameters:\n\n"
        for cam, params in self.distortion_params.items():
            cam_label = "Left" if cam == "cam0" else "Right"
            info_text += f"{cam_label} Camera ({cam}):\n"
            info_text += f"  Center: ({params['xcenter']:.1f}, {params['ycenter']:.1f})\n"
            info_text += f"  Coefficients: {len(params['coeffs'])} values\n"
            info_text += f"  {params['coeffs']}\n\n"
        
        messagebox.showinfo("Distortion Parameters", info_text)

if __name__ == "__main__":
    viewer = DualIMX708Viewer()
    try:
        viewer.run()
    finally:
        viewer.cleanup() 