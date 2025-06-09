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
            'cam0': {'width': 2161, 'start_x': 1284, 'height': 2592},
            'cam1': {'width': 2088, 'start_x': 1336, 'height': 2592}
        }

        # Distortion correction parameters (default values - will be loaded from files)
        self.distortion_params = {
            'cam0': {
                'xcenter': 1189.0732,
                'ycenter': 1224.3019,
                'coeffs': [1.0493219962591438, -5.8329152691427105e-05, -4.317510446486265e-08]
            },
            'cam1': {
                'xcenter': 1189.2568,
                'ycenter': 1223.9213,
                'coeffs': [1.006674855782123, 0.00010232984957050351, -1.3102049770975328e-07]
            }
        }

        # Control flags
        self.apply_cropping = True
        self.enable_distortion_correction = True

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
        self.root.title("Dual IMX708 Camera Control")

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
        processing_frame = ttk.LabelFrame(control_frame, text="Image Processing")
        processing_frame.pack(fill=tk.X, padx=5, pady=10)

        # Cropping checkbox
        self.crop_var = tk.BooleanVar(value=self.apply_cropping)
        ttk.Checkbutton(processing_frame, text="Apply Cropping", 
                       variable=self.crop_var, 
                       command=self.toggle_cropping).pack(anchor=tk.W, padx=5, pady=2)

        # Distortion correction checkbox
        self.distortion_var = tk.BooleanVar(value=self.enable_distortion_correction)
        ttk.Checkbutton(processing_frame, text="Apply Distortion Correction", 
                       variable=self.distortion_var, 
                       command=self.toggle_distortion_correction).pack(anchor=tk.W, padx=5, pady=2)

        # Reload coefficients button
        ttk.Button(processing_frame, text="Reload Distortion Coefficients", 
                  command=self.load_distortion_coefficients).pack(fill=tk.X, padx=5, pady=5)

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
            # Create filenames with processing info
            crop_str = "cropped" if self.apply_cropping else "full"
            distort_str = "corrected" if self.enable_distortion_correction else "raw"
            
            # Always save original DNG files first (these are unprocessed)
            original_filename0 = f"cam0_{timestamp}_original_{params_str}.dng"
            original_filename1 = f"cam1_{timestamp}_original_{params_str}.dng"
            
            try:
                req0.save_dng(original_filename0)
                req1.save_dng(original_filename1)
                print(f"[SUCCESS] Saved original DNG files:")
                print(f"   {original_filename0}")
                print(f"   {original_filename1}")
            except Exception as e:
                print(f"[ERROR] Failed to save original DNG files: {e}")

            # If processing is enabled, save processed versions
            if self.apply_cropping or self.enable_distortion_correction:
                try:
                    # For processed images, we need to work with the main stream (processed RGB data)
                    # NOT the raw stream which is Bayer data
                    
                    # Get processed RGB arrays from main stream
                    img0 = req0.make_array("main")
                    img1 = req1.make_array("main")
                    
                    print(f"[DEBUG] Original image shapes - Cam0: {img0.shape}, Cam1: {img1.shape}")
                    print(f"[DEBUG] Original image dtypes - Cam0: {img0.dtype}, Cam1: {img1.dtype}")
                    print(f"[DEBUG] Original image ranges - Cam0: [{img0.min()}, {img0.max()}], Cam1: [{img1.min()}, {img1.max()}]")

                    # Apply cropping if enabled
                    if self.apply_cropping:
                        img0_processed = self.crop_image(img0, 'cam0')
                        img1_processed = self.crop_image(img1, 'cam1')
                        print(f"[DEBUG] After cropping - Cam0: {img0_processed.shape}, Cam1: {img1_processed.shape}")
                    else:
                        img0_processed = img0
                        img1_processed = img1

                    # Apply distortion correction if enabled
                    if self.enable_distortion_correction:
                        print(f"[DEBUG] Before distortion correction - Cam0 range: [{img0_processed.min()}, {img0_processed.max()}]")
                        img0_corrected = self.apply_distortion_correction(img0_processed, 'cam0')
                        img1_corrected = self.apply_distortion_correction(img1_processed, 'cam1')
                        print(f"[DEBUG] After distortion correction - Cam0 range: [{img0_corrected.min()}, {img0_corrected.max()}]")
                    else:
                        img0_corrected = img0_processed
                        img1_corrected = img1_processed

                    # For processed DNG files, we need to create new requests with the processed data
                    # This is complex, so let's save as TIFF for processed versions
                    processed_filename0 = f"cam0_{timestamp}_{crop_str}_{distort_str}_{params_str}.tiff"
                    processed_filename1 = f"cam1_{timestamp}_{crop_str}_{distort_str}_{params_str}.tiff"

                    # Convert to proper format for saving
                    def prepare_for_save(img):
                        # Handle different input formats
                        if img.dtype == np.uint8:
                            # Already 8-bit, convert to 16-bit for better quality
                            return (img.astype(np.uint16) * 257)
                        elif img.dtype == np.float32 or img.dtype == np.float64:
                            # Float data, normalize to 16-bit
                            img_norm = np.clip(img, 0, None)  # Remove negative values
                            if img_norm.max() <= 1.0:
                                # 0-1 range, scale to 16-bit
                                return (img_norm * 65535).astype(np.uint16)
                            elif img_norm.max() <= 255:
                                # 0-255 range, scale to 16-bit  
                                return (img_norm * 257).astype(np.uint16)
                            else:
                                # Already in larger range, just convert
                                return np.clip(img_norm, 0, 65535).astype(np.uint16)
                        else:
                            # Assume uint16 or similar
                            return np.clip(img, 0, 65535).astype(np.uint16)

                    img0_save = prepare_for_save(img0_corrected)
                    img1_save = prepare_for_save(img1_corrected)

                    print(f"[DEBUG] Final save format - Cam0: {img0_save.shape}, dtype: {img0_save.dtype}, range: [{img0_save.min()}, {img0_save.max()}]")

                    # Save as TIFF files
                    from PIL import Image
                    
                    # Handle different image formats for PIL
                    if len(img0_save.shape) == 3:
                        # Multi-channel image - convert BGR to RGB for PIL
                        if img0_save.shape[2] == 3:
                            img0_pil = Image.fromarray(img0_save[:,:,[2,1,0]])  # BGR to RGB
                            img1_pil = Image.fromarray(img1_save[:,:,[2,1,0]])  # BGR to RGB
                        else:
                            img0_pil = Image.fromarray(img0_save)
                            img1_pil = Image.fromarray(img1_save)
                    else:
                        # Grayscale image
                        img0_pil = Image.fromarray(img0_save)
                        img1_pil = Image.fromarray(img1_save)
                    
                    img0_pil.save(processed_filename0)
                    img1_pil.save(processed_filename1)
                    
                    print(f"[SUCCESS] Saved processed images:")
                    print(f"   {processed_filename0} (shape: {img0_save.shape})")
                    print(f"   {processed_filename1} (shape: {img1_save.shape})")
                    
                    # If you want processed DNG files, we can try to create them using the helpers
                    # But this is experimental and may not work perfectly
                    if True:  # Set to True if you want to try processed DNG files
                        try:
                            processed_dng_filename0 = f"cam0_{timestamp}_{crop_str}_{distort_str}_{params_str}_processed.dng"
                            processed_dng_filename1 = f"cam1_{timestamp}_{crop_str}_{distort_str}_{params_str}_processed.dng"
                            
                            # Get metadata from original request
                            metadata0 = req0.get_metadata()
                            metadata1 = req1.get_metadata()
                            
                            # Try to save processed data as DNG using helpers
                            # Note: This may not work perfectly as DNG expects raw Bayer data
                            # but we're giving it processed RGB data
                            
                            # Convert back to buffer format for save_dng
                            buffer0 = img0_save.tobytes()
                            buffer1 = img1_save.tobytes()
                            
                            # Create a fake config for the processed image
                            fake_config0 = {
                                'format': 'RGB888' if len(img0_save.shape) == 3 else 'R8',
                                'size': (img0_save.shape[1], img0_save.shape[0]),
                                'stride': img0_save.shape[1] * (img0_save.shape[2] if len(img0_save.shape) == 3 else 1) * 2,  # 2 bytes per pixel for uint16
                                'framesize': len(buffer0)
                            }
                            fake_config1 = {
                                'format': 'RGB888' if len(img1_save.shape) == 3 else 'R8', 
                                'size': (img1_save.shape[1], img1_save.shape[0]),
                                'stride': img1_save.shape[1] * (img1_save.shape[2] if len(img1_save.shape) == 3 else 1) * 2,
                                'framesize': len(buffer1)
                            }
                            
                            # This might not work as DNG expects Bayer data, but let's try
                            self.cam0.helpers.save_dng(buffer0, metadata0, fake_config0, processed_dng_filename0)
                            self.cam1.helpers.save_dng(buffer1, metadata1, fake_config1, processed_dng_filename1)
                            
                            print(f"[SUCCESS] Saved processed DNG files (experimental):")
                            print(f"   {processed_dng_filename0}")
                            print(f"   {processed_dng_filename1}")
                            
                        except Exception as e:
                            print(f"[WARNING] Failed to save processed DNG files (this is expected): {e}")
                            print("   Processed DNG saving is experimental and may not work with RGB data")
                        
                except Exception as e:
                    print(f"[ERROR] Failed to save processed images: {e}")
                    import traceback
                    traceback.print_exc()

        finally:
            # Always release the requests
            req0.release()
            req1.release()

    def update_preview(self):
        frame0 = self.cam0.capture_array()
        frame1 = self.cam1.capture_array()

        # Apply cropping to preview if enabled
        if self.apply_cropping:
            frame0_display = self.crop_image(frame0, 'cam0')
            frame1_display = self.crop_image(frame1, 'cam1')
        else:
            frame0_display = frame0
            frame1_display = frame1

        display0 = cv2.resize(frame0_display, (640, 480))
        display1 = cv2.resize(frame1_display, (640, 480))
        combined = np.hstack((display0, display1))

        y = 30
        for param_name, param_data in self.params.items():
            text = f"{param_name}: {param_data['value']:.2f}"
            cv2.putText(combined, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y += 20

        # Add processing status
        crop_status = "ON" if self.apply_cropping else "OFF"
        distort_status = "ON" if self.enable_distortion_correction else "OFF"
        cv2.putText(combined, f"Crop: {crop_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.apply_cropping else (0, 0, 255), 1)
        y += 20
        cv2.putText(combined, f"Distortion: {distort_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.enable_distortion_correction else (0, 0, 255), 1)

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

    def load_distortion_coefficients(self):
        """Load distortion correction coefficients from files or use defaults"""
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
                    with open(filepath, 'r') as f:
                        lines = f.readlines()
                        xcenter = float(lines[0].split('=')[1].strip())
                        ycenter = float(lines[1].split('=')[1].strip())
                        coeffs = []
                        for i in range(2, len(lines)):
                            if lines[i].strip():
                                coeffs.append(float(lines[i].split('=')[1].strip()))
                        
                        self.distortion_params[cam]['xcenter'] = xcenter
                        self.distortion_params[cam]['ycenter'] = ycenter
                        self.distortion_params[cam]['coeffs'] = coeffs
                        print(f"[SUCCESS] Loaded distortion coefficients for {cam} from original file")
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
        
        # Adjust center coordinates for cropped image if cropping is applied
        if self.apply_cropping:
            crop_params = self.crop_params[cam_name]
            xcenter = xcenter - crop_params['start_x']
        
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

    def toggle_cropping(self):
        """Toggle cropping on/off"""
        self.apply_cropping = self.crop_var.get()
        print(f"Cropping: {'ON' if self.apply_cropping else 'OFF'}")

    def toggle_distortion_correction(self):
        """Toggle distortion correction on/off"""
        self.enable_distortion_correction = self.distortion_var.get()
        print(f"Distortion correction: {'ON' if self.enable_distortion_correction else 'OFF'}")

    def update_distortion_params(self, cam_name, xcenter, ycenter, coeffs):
        """Update distortion parameters for a specific camera"""
        self.distortion_params[cam_name]['xcenter'] = xcenter
        self.distortion_params[cam_name]['ycenter'] = ycenter
        self.distortion_params[cam_name]['coeffs'] = coeffs
        print(f"[SUCCESS] Updated distortion parameters for {cam_name}")

    def update_crop_params(self, cam_name, width, start_x, height=2592):
        """Update crop parameters for a specific camera"""
        self.crop_params[cam_name]['width'] = width
        self.crop_params[cam_name]['start_x'] = start_x
        self.crop_params[cam_name]['height'] = height
        print(f"[SUCCESS] Updated crop parameters for {cam_name}: {width}x{height} @ ({start_x},0)")

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