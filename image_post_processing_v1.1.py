#!/usr/bin/env python3
"""
Image Post-Processing Script for IMX708 Dual Camera System (v1.1)

This script processes DNG files captured by the dual camera system:
- Loads DNG files from both cameras (left and right)
- Applies camera-specific cropping (optional)
- Applies camera-specific distortion correction (optional)
- Saves as JPEG, TIFF, or PNG with quality settings

Version 1.1 Improvements:
- Fixed TIFF saving issues by using imageio for reliable TIFF output
- Improved DNG loading with better color space handling
- Enhanced distortion correction with better error handling
- Added support for batch processing of image pairs
- Improved GUI with better parameter display
- Added support for combined side-by-side image output
- Better handling of image data types and ranges
- More robust error handling and logging
- Improved file naming with processing status indicators

Usage:
    python image_post_processing.py [left_image] [right_image] [options]
    
Or run interactively to select files via GUI.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
import os
import json
import argparse
from PIL import Image
import rawpy
import discorpy.post.postprocessing as post
from datetime import datetime
import imageio

class DualImagePostProcessor:
    def __init__(self):
        # Default cropping parameters (same as main GUI)
        self.crop_params = {
            'cam0': {'width': 2161, 'start_x': 1284, 'height': 2592},
            'cam1': {'width': 2088, 'start_x': 1336, 'height': 2592}
        }

        # Default distortion correction parameters
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

        # Processing options
        self.apply_cropping = True
        self.enable_distortion_correction = True
        self.apply_left_rotation = True  # New flag for left image rotation
        self.apply_right_rotation = False  # New flag for right image rotation
        self.left_rotation_angle = -1.5  # Rotation angle in degrees
        self.right_rotation_angle = 0.0  # Rotation angle in degrees
        self.jpeg_quality = 95
        self.output_format = 'JPEG'  # 'JPEG', 'TIFF', 'PNG'
        self.save_combined = True  # Save side-by-side combined image
        self.save_individual = True  # Save individual processed images

        # Load saved coefficients if available
        self.load_distortion_coefficients()

    def load_distortion_coefficients(self, filepath=None):
        """Load distortion correction coefficients from saved file"""
        if filepath is None:
            coeff_file = 'distortion_coefficients.json'
        else:
            coeff_file = filepath
            
        if os.path.exists(coeff_file):
            try:
                with open(coeff_file, 'r') as f:
                    saved_params = json.load(f)
                    
                    # Update distortion parameters
                    for cam in ['cam0', 'cam1']:
                        if cam in saved_params:
                            if cam not in self.distortion_params:
                                self.distortion_params[cam] = {}
                            
                            # Update distortion coefficients
                            for key in ['xcenter', 'ycenter', 'coeffs']:
                                if key in saved_params[cam]:
                                    self.distortion_params[cam][key] = saved_params[cam][key]
                            
                            # Update crop parameters if present
                            if 'crop_params' in saved_params[cam]:
                                if cam not in self.crop_params:
                                    self.crop_params[cam] = {}
                                self.crop_params[cam].update(saved_params[cam]['crop_params'])
                    
                    print(f"[SUCCESS] Loaded distortion coefficients from {coeff_file}")
                    return True
            except Exception as e:
                print(f"[WARNING] Failed to load coefficients from {coeff_file}: {e}")
                print("[INFO] Using default distortion coefficients")
                return False
        else:
            if filepath is None:
                print("[INFO] No default coefficients file found, using built-in defaults")
            else:
                print(f"[WARNING] Coefficients file not found: {coeff_file}")
            return False

    def load_dng_image(self, filepath):
        """Load DNG image using rawpy with improved approach"""
        try:
            # Load and process DNG using the improved approach
            raw = rawpy.imread(filepath)
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=False,
                no_auto_bright=False,  # Allow some auto-brightness
                output_bps=16,
                output_color=rawpy.ColorSpace.ProPhoto,  # Wide color gamut
            )
            
            print(f"[SUCCESS] Loaded DNG: {os.path.basename(filepath)}")
            print(f"   Shape: {rgb.shape}, dtype: {rgb.dtype}")
            print(f"   Range: [{rgb.min()}, {rgb.max()}]")
            return rgb
        except Exception as e:
            print(f"[ERROR] Failed to load DNG file {filepath}: {e}")
            return None

    def crop_image(self, image, cam_name):
        """Crop image according to camera-specific parameters"""
        if not self.apply_cropping or cam_name not in self.crop_params:
            return image
            
        params = self.crop_params[cam_name]
        start_x = params['start_x']
        width = params['width']
        height = params['height']
        
        # Ensure we don't exceed image boundaries
        img_height, img_width = image.shape[:2]
        end_x = min(start_x + width, img_width)
        end_y = min(height, img_height)
        
        # Crop the image: [y_start:y_end, x_start:x_end]
        cropped = image[:end_y, start_x:end_x]
        print(f"[INFO] Cropped {cam_name}: {image.shape} -> {cropped.shape}")
        return cropped

    def apply_distortion_correction(self, image, cam_name):
        """Apply distortion correction to the image"""
        if not self.enable_distortion_correction or cam_name not in self.distortion_params:
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
            
            # Convert to float for processing
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
            
            # Clip to reasonable range
            corrected = np.clip(corrected, 0, original_max)
            
            # Convert back to original data type
            if original_dtype == np.uint8:
                corrected = np.clip(corrected, 0, 255).astype(np.uint8)
            elif original_dtype == np.uint16:
                corrected = np.clip(corrected, 0, 65535).astype(np.uint16)
            else:
                corrected = corrected.astype(original_dtype)
            
            print(f"[INFO] Applied distortion correction to {cam_name}")
            print(f"   Center: ({xcenter:.1f}, {ycenter:.1f})")
            print(f"   Input range: [{original_min}, {original_max}], Output range: [{corrected.min()}, {corrected.max()}]")
            
            return corrected
            
        except Exception as e:
            print(f"[ERROR] Distortion correction failed for {cam_name}: {e}")
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
            
            print(f"[INFO] Applied {self.left_rotation_angle}° rotation to left image")
            return rotated
            
        except Exception as e:
            print(f"[ERROR] Left image rotation failed: {e}")
            return image

    def rotate_right_image(self, image):
        """Rotate the right image by the specified angle"""
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
            
            print(f"[INFO] Applied {self.right_rotation_angle}° rotation to right image")
            return rotated
            
        except Exception as e:
            print(f"[ERROR] Right image rotation failed: {e}")
            return image

    def save_processed_image(self, image, output_path, format_type=None):
        """Save processed image in specified format with improved TIFF handling"""
        if format_type is None:
            format_type = self.output_format
            
        try:
            # Ensure we have a valid image
            if image is None or image.size == 0:
                print(f"[ERROR] Invalid image data for {output_path}")
                return False
            
            print(f"[DEBUG] Saving image: {output_path}")
            print(f"[DEBUG] Original image shape: {image.shape}, dtype: {image.dtype}, range: [{image.min()}, {image.max()}]")
            
            # For TIFF, use imageio directly - simple and clean
            if format_type.upper() == 'TIFF':
                # Use imageio for TIFF - handles everything automatically
                imageio.imsave(output_path, image)
                print(f"[SUCCESS] Saved TIFF using imageio: {output_path}")
                return True
                    
            else:
                # For JPEG/PNG, convert to 8-bit and use PIL
                if image.dtype == np.uint16:
                    # Convert 16-bit to 8-bit
                    image_save = (image / 256).astype(np.uint8)
                elif image.dtype == np.float32 or image.dtype == np.float64:
                    # Normalize float to 8-bit
                    if image.max() <= 1.0:
                        image_save = (image * 255).astype(np.uint8)
                    else:
                        image_save = np.clip(image / image.max() * 255, 0, 255).astype(np.uint8)
                else:
                    image_save = np.clip(image, 0, 255).astype(np.uint8)
                
                # Handle BGR to RGB conversion for PIL if needed
                if len(image_save.shape) == 3 and image_save.shape[2] == 3:
                    # Convert BGR to RGB for PIL
                    image_rgb = image_save[:,:,[2,1,0]]
                else:
                    # Grayscale or already in correct format
                    image_rgb = image_save
                
                # Create PIL Image
                if len(image_rgb.shape) == 2:
                    # Grayscale
                    pil_image = Image.fromarray(image_rgb, mode='L')
                elif image_rgb.shape[2] == 3:
                    # RGB
                    pil_image = Image.fromarray(image_rgb, mode='RGB')
                else:
                    print(f"[ERROR] Unsupported image format: {image_rgb.shape}")
                    return False
                
                # Save with format-specific options
                if format_type.upper() == 'JPEG':
                    pil_image.save(output_path, 'JPEG', quality=self.jpeg_quality, optimize=True)
                elif format_type.upper() == 'PNG':
                    pil_image.save(output_path, 'PNG', optimize=True)
                else:
                    pil_image.save(output_path)
                
                print(f"[SUCCESS] Saved processed image: {output_path}")
                return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save image {output_path}: {e}")
            import traceback
            traceback.print_exc()
            return False

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

    def process_dual_images(self, left_path, right_path, output_dir=None, base_name=None):
        """Process both left and right images"""
        print(f"\n[INFO] Processing dual images:")
        print(f"   Left (cam0): {os.path.basename(left_path)}")
        print(f"   Right (cam1): {os.path.basename(right_path)}")
        
        # Load both images
        left_image = self.load_dng_image(left_path)
        right_image = self.load_dng_image(right_path)
        
        if left_image is None or right_image is None:
            print("[ERROR] Failed to load one or both images")
            return False
        
        # Process left image (cam0)
        print("\n[INFO] Processing left image (cam0)...")
        left_processed = left_image
        if self.apply_cropping:
            left_processed = self.crop_image(left_processed, 'cam0')
        if self.enable_distortion_correction:
            left_processed = self.apply_distortion_correction(left_processed, 'cam0')
        if self.apply_left_rotation:
            left_processed = self.rotate_left_image(left_processed)
        
        # Process right image (cam1)
        print("\n[INFO] Processing right image (cam1)...")
        right_processed = right_image
        if self.apply_cropping:
            right_processed = self.crop_image(right_processed, 'cam1')
        if self.enable_distortion_correction:
            right_processed = self.apply_distortion_correction(right_processed, 'cam1')
        if self.apply_right_rotation:
            right_processed = self.rotate_right_image(right_processed)
        
        # Generate base filename if not provided
        if base_name is None:
            left_base = os.path.splitext(os.path.basename(left_path))[0]
            right_base = os.path.splitext(os.path.basename(right_path))[0]
            # Try to find common timestamp or use both names
            if any(part in right_base for part in left_base.split('_')):
                # Find common parts
                left_parts = left_base.split('_')
                right_parts = right_base.split('_')
                common_parts = []
                for part in left_parts:
                    if part in right_parts and part not in ['cam0', 'cam1', 'left', 'right']:
                        common_parts.append(part)
                base_name = '_'.join(common_parts) if common_parts else 'dual_image'
            else:
                base_name = f"{left_base}_and_{right_base}"
        
        # Set output directory
        if output_dir is None:
            output_dir = os.path.dirname(left_path)
        
        # Generate suffixes
        suffixes = []
        if self.apply_cropping:
            suffixes.append("cropped")
        if self.enable_distortion_correction:
            suffixes.append("corrected")
        if self.apply_left_rotation:
            suffixes.append("rotated")
        suffix_str = "_" + "_".join(suffixes) if suffixes else "_processed"
        
        # File extension
        ext_map = {'JPEG': '.jpg', 'TIFF': '.tiff', 'PNG': '.png'}
        ext = ext_map.get(self.output_format.upper(), '.jpg')
        
        success_count = 0
        
        # Save individual images if requested
        if self.save_individual:
            left_output = os.path.join(output_dir, f"{base_name}_left{suffix_str}{ext}")
            right_output = os.path.join(output_dir, f"{base_name}_right{suffix_str}{ext}")
            
            if self.save_processed_image(left_processed, left_output):
                success_count += 1
            if self.save_processed_image(right_processed, right_output):
                success_count += 1
        
        # Save combined image if requested
        if self.save_combined:
            combined_image = self.create_combined_image(left_processed, right_processed)
            if combined_image is not None:
                combined_output = os.path.join(output_dir, f"{base_name}_combined{suffix_str}{ext}")
                if self.save_processed_image(combined_image, combined_output):
                    success_count += 1
        
        print(f"\n[SUCCESS] Dual image processing complete!")
        print(f"   Left: {left_image.shape} -> {left_processed.shape}")
        print(f"   Right: {right_image.shape} -> {right_processed.shape}")
        print(f"   Files saved: {success_count}")
        
        return success_count > 0

    def process_batch_pairs(self, input_directory, output_directory=None):
        """Process pairs of DNG files in a directory"""
        if output_directory is None:
            output_directory = input_directory
        
        # Create output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)
        
        # Find all DNG files
        dng_files = []
        for file in os.listdir(input_directory):
            if file.lower().endswith('.dng'):
                dng_files.append(file)
        
        if not dng_files:
            print(f"[WARNING] No DNG files found in {input_directory}")
            return
        
        # Group files by timestamp or common identifier
        pairs = []
        left_files = [f for f in dng_files if 'cam0' in f.lower() or 'left' in f.lower()]
        right_files = [f for f in dng_files if 'cam1' in f.lower() or 'right' in f.lower()]
        
        print(f"[INFO] Found {len(left_files)} left images and {len(right_files)} right images")
        
        # Try to match pairs by timestamp or similar naming
        for left_file in left_files:
            left_base = left_file.replace('cam0', '').replace('left', '').replace('_', '')
            best_match = None
            best_score = 0
            
            for right_file in right_files:
                right_base = right_file.replace('cam1', '').replace('right', '').replace('_', '')
                # Simple similarity score
                common_chars = sum(1 for a, b in zip(left_base, right_base) if a == b)
                score = common_chars / max(len(left_base), len(right_base))
                
                if score > best_score and score > 0.7:  # 70% similarity threshold
                    best_match = right_file
                    best_score = score
            
            if best_match:
                pairs.append((left_file, best_match))
                right_files.remove(best_match)  # Remove to avoid duplicate pairing
        
        if not pairs:
            print("[WARNING] Could not find matching pairs. Processing files individually...")
            # Fall back to processing available files
            for i, left_file in enumerate(left_files):
                if i < len(right_files):
                    pairs.append((left_file, right_files[i]))
        
        print(f"[INFO] Found {len(pairs)} image pairs to process")
        
        # Process each pair
        successful = 0
        for i, (left_file, right_file) in enumerate(pairs, 1):
            print(f"\n[INFO] Processing pair {i}/{len(pairs)}")
            
            left_path = os.path.join(input_directory, left_file)
            right_path = os.path.join(input_directory, right_file)
            
            if self.process_dual_images(left_path, right_path, output_directory):
                successful += 1
        
        print(f"\n[SUCCESS] Batch processing complete: {successful}/{len(pairs)} pairs processed successfully")

    def create_gui(self):
        """Create a GUI for dual image processing"""
        root = tk.Tk()
        root.title("Dual Camera DNG Post-Processor")
        root.geometry("700x600")
        
        # Main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Processing options
        options_frame = ttk.LabelFrame(main_frame, text="Processing Options", padding="10")
        options_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Cropping checkbox
        self.crop_var = tk.BooleanVar(value=self.apply_cropping)
        ttk.Checkbutton(options_frame, text="Apply Cropping", 
                       variable=self.crop_var).grid(row=0, column=0, sticky=tk.W)
        
        # Distortion correction checkbox
        self.distortion_var = tk.BooleanVar(value=self.enable_distortion_correction)
        ttk.Checkbutton(options_frame, text="Apply Distortion Correction", 
                       variable=self.distortion_var).grid(row=1, column=0, sticky=tk.W)
        
        # Left rotation checkbox
        self.left_rotation_var = tk.BooleanVar(value=self.apply_left_rotation)
        ttk.Checkbutton(options_frame, text="Apply Left Image Rotation", 
                       variable=self.left_rotation_var).grid(row=2, column=0, sticky=tk.W)
        
        # Right rotation checkbox
        self.right_rotation_var = tk.BooleanVar(value=self.apply_right_rotation)
        ttk.Checkbutton(options_frame, text="Apply Right Image Rotation", 
                       variable=self.right_rotation_var).grid(row=3, column=0, sticky=tk.W)
        
        # Output options
        self.individual_var = tk.BooleanVar(value=self.save_individual)
        ttk.Checkbutton(options_frame, text="Save Individual Images", 
                       variable=self.individual_var).grid(row=4, column=0, sticky=tk.W)
        
        self.combined_var = tk.BooleanVar(value=self.save_combined)
        ttk.Checkbutton(options_frame, text="Save Combined Side-by-Side Image", 
                       variable=self.combined_var).grid(row=5, column=0, sticky=tk.W)
        
        # Output format
        ttk.Label(options_frame, text="Output Format:").grid(row=6, column=0, sticky=tk.W, pady=(10, 0))
        self.format_var = tk.StringVar(value=self.output_format)
        format_combo = ttk.Combobox(options_frame, textvariable=self.format_var, 
                                   values=['JPEG', 'TIFF', 'PNG'], state='readonly', width=10)
        format_combo.grid(row=6, column=1, sticky=tk.W, padx=(10, 0), pady=(10, 0))
        
        # JPEG quality
        ttk.Label(options_frame, text="JPEG Quality:").grid(row=7, column=0, sticky=tk.W, pady=(5, 0))
        self.quality_var = tk.IntVar(value=self.jpeg_quality)
        quality_scale = ttk.Scale(options_frame, from_=50, to=100, variable=self.quality_var, 
                                 orient=tk.HORIZONTAL, length=200)
        quality_scale.grid(row=7, column=1, sticky=tk.W, padx=(10, 0), pady=(5, 0))
        
        # Quality label
        self.quality_label = ttk.Label(options_frame, text=f"{self.jpeg_quality}%")
        self.quality_label.grid(row=7, column=2, sticky=tk.W, padx=(5, 0), pady=(5, 0))
        
        def update_quality_label(*args):
            self.quality_label.config(text=f"{self.quality_var.get()}%")
        quality_scale.config(command=update_quality_label)
        
        # Rotation angles frame
        rotation_frame = ttk.LabelFrame(main_frame, text="Rotation Angles (degrees)", padding="10")
        rotation_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Left rotation angle
        ttk.Label(rotation_frame, text="Left Image Angle:").grid(row=0, column=0, sticky=tk.W)
        self.left_angle_var = tk.DoubleVar(value=self.left_rotation_angle)
        left_angle_entry = ttk.Entry(rotation_frame, textvariable=self.left_angle_var, width=10)
        left_angle_entry.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Right rotation angle
        ttk.Label(rotation_frame, text="Right Image Angle:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0))
        self.right_angle_var = tk.DoubleVar(value=self.right_rotation_angle)
        right_angle_entry = ttk.Entry(rotation_frame, textvariable=self.right_angle_var, width=10)
        right_angle_entry.grid(row=0, column=3, sticky=tk.W, padx=(10, 0))
        
        # Cropping parameters frame
        crop_frame = ttk.LabelFrame(main_frame, text="Cropping Parameters", padding="10")
        crop_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Left camera crop parameters
        ttk.Label(crop_frame, text="Left Camera (cam0):").grid(row=0, column=0, sticky=tk.W, columnspan=4)
        
        ttk.Label(crop_frame, text="Width:").grid(row=1, column=0, sticky=tk.W, padx=(20, 0))
        self.left_width_var = tk.IntVar(value=self.crop_params['cam0']['width'])
        ttk.Entry(crop_frame, textvariable=self.left_width_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(crop_frame, text="Start X:").grid(row=1, column=2, sticky=tk.W, padx=(15, 0))
        self.left_start_x_var = tk.IntVar(value=self.crop_params['cam0']['start_x'])
        ttk.Entry(crop_frame, textvariable=self.left_start_x_var, width=8).grid(row=1, column=3, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(crop_frame, text="Height:").grid(row=1, column=4, sticky=tk.W, padx=(15, 0))
        self.left_height_var = tk.IntVar(value=self.crop_params['cam0']['height'])
        ttk.Entry(crop_frame, textvariable=self.left_height_var, width=8).grid(row=1, column=5, sticky=tk.W, padx=(5, 0))
        
        # Right camera crop parameters
        ttk.Label(crop_frame, text="Right Camera (cam1):").grid(row=2, column=0, sticky=tk.W, columnspan=4, pady=(10, 0))
        
        ttk.Label(crop_frame, text="Width:").grid(row=3, column=0, sticky=tk.W, padx=(20, 0))
        self.right_width_var = tk.IntVar(value=self.crop_params['cam1']['width'])
        ttk.Entry(crop_frame, textvariable=self.right_width_var, width=8).grid(row=3, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(crop_frame, text="Start X:").grid(row=3, column=2, sticky=tk.W, padx=(15, 0))
        self.right_start_x_var = tk.IntVar(value=self.crop_params['cam1']['start_x'])
        ttk.Entry(crop_frame, textvariable=self.right_start_x_var, width=8).grid(row=3, column=3, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(crop_frame, text="Height:").grid(row=3, column=4, sticky=tk.W, padx=(15, 0))
        self.right_height_var = tk.IntVar(value=self.crop_params['cam1']['height'])
        ttk.Entry(crop_frame, textvariable=self.right_height_var, width=8).grid(row=3, column=5, sticky=tk.W, padx=(5, 0))
        
        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        file_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Dual image processing
        ttk.Button(file_frame, text="Process Left + Right DNG Pair", 
                  command=self.gui_process_dual).grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Batch processing
        ttk.Button(file_frame, text="Process Directory (Batch Pairs)", 
                  command=self.gui_process_batch).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Single image processing (legacy)
        ttk.Button(file_frame, text="Process Single DNG File", 
                  command=self.gui_process_single).grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Current parameters display
        params_frame = ttk.LabelFrame(main_frame, text="Current Parameters", padding="10")
        params_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Create text widget for parameters
        self.params_text = tk.Text(params_frame, height=10, width=70)
        self.params_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Scrollbar for text widget
        scrollbar = ttk.Scrollbar(params_frame, orient=tk.VERTICAL, command=self.params_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.params_text.config(yscrollcommand=scrollbar.set)
        
        # Update parameters display
        self.update_params_display()
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(buttons_frame, text="Reload Distortion Coefficients", 
                  command=self.reload_coefficients).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(buttons_frame, text="Exit", 
                  command=root.quit).pack(side=tk.RIGHT)
        
        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        file_frame.columnconfigure(0, weight=1)
        params_frame.columnconfigure(0, weight=1)
        
        return root
    
    def update_params_display(self):
        """Update the parameters display in the GUI"""
        if hasattr(self, 'params_text'):
            self.params_text.delete(1.0, tk.END)
            
            # Crop parameters
            self.params_text.insert(tk.END, "Crop Parameters:\n")
            for cam, params in self.crop_params.items():
                cam_label = "Left" if cam == "cam0" else "Right"
                self.params_text.insert(tk.END, f"  {cam} ({cam_label}): {params['width']}x{params['height']} @ ({params['start_x']},0)\n")
            
            # Rotation parameters
            self.params_text.insert(tk.END, "\nRotation Parameters:\n")
            self.params_text.insert(tk.END, f"  Left Image (cam0): {self.left_rotation_angle}°\n")
            self.params_text.insert(tk.END, f"  Right Image (cam1): {self.right_rotation_angle}°\n")
            
            self.params_text.insert(tk.END, "\nDistortion Parameters:\n")
            for cam, params in self.distortion_params.items():
                cam_label = "Left" if cam == "cam0" else "Right"
                self.params_text.insert(tk.END, f"  {cam} ({cam_label}):\n")
                self.params_text.insert(tk.END, f"    Center: ({params['xcenter']:.1f}, {params['ycenter']:.1f})\n")
                self.params_text.insert(tk.END, f"    Coefficients: {params['coeffs']}\n")
    
    def gui_process_dual(self):
        """GUI handler for dual image processing"""
        # Update settings from GUI
        self.apply_cropping = self.crop_var.get()
        self.enable_distortion_correction = self.distortion_var.get()
        self.apply_left_rotation = self.left_rotation_var.get()
        self.apply_right_rotation = self.right_rotation_var.get()
        self.save_individual = self.individual_var.get()
        self.save_combined = self.combined_var.get()
        self.output_format = self.format_var.get()
        self.jpeg_quality = self.quality_var.get()
        
        # Update rotation angles
        self.left_rotation_angle = self.left_angle_var.get()
        self.right_rotation_angle = self.right_angle_var.get()
        
        # Update crop parameters
        self.crop_params['cam0']['width'] = self.left_width_var.get()
        self.crop_params['cam0']['start_x'] = self.left_start_x_var.get()
        self.crop_params['cam0']['height'] = self.left_height_var.get()
        self.crop_params['cam1']['width'] = self.right_width_var.get()
        self.crop_params['cam1']['start_x'] = self.right_start_x_var.get()
        self.crop_params['cam1']['height'] = self.right_height_var.get()
        
        if not self.save_individual and not self.save_combined:
            messagebox.showerror("Error", "Please select at least one output option (Individual or Combined)")
            return
        
        # Select left image
        left_file = filedialog.askopenfilename(
            title="Select LEFT camera DNG file (cam0)",
            filetypes=[("DNG files", "*.dng"), ("All files", "*.*")]
        )
        
        if not left_file:
            return
        
        # Select right image
        right_file = filedialog.askopenfilename(
            title="Select RIGHT camera DNG file (cam1)",
            filetypes=[("DNG files", "*.dng"), ("All files", "*.*")]
        )
        
        if not right_file:
            return
        
        # Select output directory
        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            output_dir = os.path.dirname(left_file)
        
        # Process the files
        success = self.process_dual_images(left_file, right_file, output_dir)
        
        if success:
            messagebox.showinfo("Success", "Dual images processed successfully!\nCheck the output directory for results.")
        else:
            messagebox.showerror("Error", "Failed to process images. Check console for details.")
    
    def gui_process_single(self):
        """GUI handler for single file processing (legacy support)"""
        # Update settings from GUI
        self.apply_cropping = self.crop_var.get()
        self.enable_distortion_correction = self.distortion_var.get()
        self.apply_left_rotation = self.left_rotation_var.get()
        self.apply_right_rotation = self.right_rotation_var.get()
        self.output_format = self.format_var.get()
        self.jpeg_quality = self.quality_var.get()
        
        # Update rotation angles
        self.left_rotation_angle = self.left_angle_var.get()
        self.right_rotation_angle = self.right_angle_var.get()
        
        # Update crop parameters
        self.crop_params['cam0']['width'] = self.left_width_var.get()
        self.crop_params['cam0']['start_x'] = self.left_start_x_var.get()
        self.crop_params['cam0']['height'] = self.left_height_var.get()
        self.crop_params['cam1']['width'] = self.right_width_var.get()
        self.crop_params['cam1']['start_x'] = self.right_start_x_var.get()
        self.crop_params['cam1']['height'] = self.right_height_var.get()
        
        # Select input file
        input_file = filedialog.askopenfilename(
            title="Select DNG file to process",
            filetypes=[("DNG files", "*.dng"), ("All files", "*.*")]
        )
        
        if not input_file:
            return
        
        # Detect camera type
        cam_name = 'cam0'  # Default
        basename = os.path.basename(input_file).lower()
        if 'cam1' in basename or 'right' in basename:
            cam_name = 'cam1'
        
        # Select output file
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        suffixes = []
        if self.apply_cropping:
            suffixes.append("cropped")
        if self.enable_distortion_correction:
            suffixes.append("corrected")
        if self.apply_left_rotation and cam_name == 'cam0':
            suffixes.append("rotated")
        if self.apply_right_rotation and cam_name == 'cam1':
            suffixes.append("rotated")
        
        suffix_str = "_" + "_".join(suffixes) if suffixes else "_processed"
        ext_map = {'JPEG': '.jpg', 'TIFF': '.tiff', 'PNG': '.png'}
        ext = ext_map.get(self.output_format.upper(), '.jpg')
        
        default_output = f"{base_name}{suffix_str}{ext}"
        
        output_file = filedialog.asksaveasfilename(
            title="Save processed image as",
            defaultextension=ext,
            initialfile=default_output,
            filetypes=[(f"{self.output_format} files", f"*{ext}"), ("All files", "*.*")]
        )
        
        if not output_file:
            return
        
        # Process the file
        success = self.process_single_image(input_file, output_file, cam_name)
        
        if success:
            messagebox.showinfo("Success", f"Image processed successfully!\nSaved as: {os.path.basename(output_file)}")
        else:
            messagebox.showerror("Error", "Failed to process image. Check console for details.")
    
    def process_single_image(self, input_path, output_path, cam_name):
        """Process a single DNG image (legacy method)"""
        print(f"\n[INFO] Processing single image: {os.path.basename(input_path)} as {cam_name}")
        
        # Load the DNG image
        image = self.load_dng_image(input_path)
        if image is None:
            return False
        
        # Apply processing steps
        processed_image = image
        
        # Apply cropping
        if self.apply_cropping:
            processed_image = self.crop_image(processed_image, cam_name)
        
        # Apply distortion correction
        if self.enable_distortion_correction:
            processed_image = self.apply_distortion_correction(processed_image, cam_name)
        
        # Apply left image rotation if this is cam0
        if self.apply_left_rotation and cam_name == 'cam0':
            processed_image = self.rotate_left_image(processed_image)
        
        # Apply right image rotation if this is cam1
        if self.apply_right_rotation and cam_name == 'cam1':
            processed_image = self.rotate_right_image(processed_image)
        
        # Save the processed image
        success = self.save_processed_image(processed_image, output_path)
        
        if success:
            print(f"[SUCCESS] Completed processing: {os.path.basename(output_path)}")
            print(f"   Original: {image.shape} -> Processed: {processed_image.shape}")
        
        return success
    
    def gui_process_batch(self):
        """GUI handler for batch processing"""
        # Update settings from GUI
        self.apply_cropping = self.crop_var.get()
        self.enable_distortion_correction = self.distortion_var.get()
        self.apply_left_rotation = self.left_rotation_var.get()
        self.apply_right_rotation = self.right_rotation_var.get()
        self.save_individual = self.individual_var.get()
        self.save_combined = self.combined_var.get()
        self.output_format = self.format_var.get()
        self.jpeg_quality = self.quality_var.get()
        
        # Update rotation angles
        self.left_rotation_angle = self.left_angle_var.get()
        self.right_rotation_angle = self.right_angle_var.get()
        
        # Update crop parameters
        self.crop_params['cam0']['width'] = self.left_width_var.get()
        self.crop_params['cam0']['start_x'] = self.left_start_x_var.get()
        self.crop_params['cam0']['height'] = self.left_height_var.get()
        self.crop_params['cam1']['width'] = self.right_width_var.get()
        self.crop_params['cam1']['start_x'] = self.right_start_x_var.get()
        self.crop_params['cam1']['height'] = self.right_height_var.get()
        
        if not self.save_individual and not self.save_combined:
            messagebox.showerror("Error", "Please select at least one output option (Individual or Combined)")
            return
        
        # Select input directory
        input_dir = filedialog.askdirectory(title="Select directory containing DNG file pairs")
        if not input_dir:
            return
        
        # Ask for output directory
        output_dir = filedialog.askdirectory(title="Select output directory (or cancel to use input directory)")
        if not output_dir:
            output_dir = input_dir
        
        # Process batch
        self.process_batch_pairs(input_dir, output_dir)
        messagebox.showinfo("Batch Processing Complete", "Check console for detailed results.")
    
    def reload_coefficients(self):
        """Reload distortion coefficients and update display"""
        # Open file dialog to select coefficients file
        coeff_file = filedialog.askopenfilename(
            title="Select Distortion Coefficients JSON File",
            filetypes=[
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if not coeff_file:
            return
        
        # Try to load the coefficients
        success = self.load_distortion_coefficients(coeff_file)
        
        if success:
            # Update GUI values with loaded parameters
            if hasattr(self, 'left_width_var'):
                self.left_width_var.set(self.crop_params['cam0']['width'])
                self.left_start_x_var.set(self.crop_params['cam0']['start_x'])
                self.left_height_var.set(self.crop_params['cam0']['height'])
                self.right_width_var.set(self.crop_params['cam1']['width'])
                self.right_start_x_var.set(self.crop_params['cam1']['start_x'])
                self.right_height_var.set(self.crop_params['cam1']['height'])
            
            # Update parameters display
            self.update_params_display()
            messagebox.showinfo("Success", f"Distortion coefficients and crop parameters loaded successfully from:\n{os.path.basename(coeff_file)}")
        else:
            messagebox.showerror("Error", f"Failed to load coefficients from:\n{os.path.basename(coeff_file)}\n\nCheck console for details.")

def main():
    parser = argparse.ArgumentParser(description="Post-process DNG image pairs from IMX708 dual camera system")
    parser.add_argument("left", nargs="?", help="Left camera DNG file")
    parser.add_argument("right", nargs="?", help="Right camera DNG file")
    parser.add_argument("-o", "--output", help="Output directory")
    parser.add_argument("--no-crop", action="store_true", help="Disable cropping")
    parser.add_argument("--no-distortion", action="store_true", help="Disable distortion correction")
    parser.add_argument("--no-rotation", action="store_true", help="Disable left image rotation")
    parser.add_argument("--format", choices=['JPEG', 'TIFF', 'PNG'], default='JPEG', help="Output format")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality (50-100)")
    parser.add_argument("--no-individual", action="store_true", help="Don't save individual images")
    parser.add_argument("--no-combined", action="store_true", help="Don't save combined image")
    parser.add_argument("--batch", action="store_true", help="Process all DNG file pairs in directory")
    parser.add_argument("--gui", action="store_true", help="Launch GUI interface")
    
    args = parser.parse_args()
    
    # Create processor
    processor = DualImagePostProcessor()
    
    # Update settings from command line
    if args.no_crop:
        processor.apply_cropping = False
    if args.no_distortion:
        processor.enable_distortion_correction = False
    if args.no_rotation:
        processor.apply_left_rotation = False
        processor.apply_right_rotation = False
    if args.no_individual:
        processor.save_individual = False
    if args.no_combined:
        processor.save_combined = False
    processor.output_format = args.format
    processor.jpeg_quality = args.quality
    
    # Launch GUI if requested or no input provided
    if args.gui or (args.left is None and args.right is None):
        root = processor.create_gui()
        root.mainloop()
        return
    
    # Command line processing
    if args.batch:
        # Batch processing - use left argument as directory
        input_dir = args.left if args.left else "."
        processor.process_batch_pairs(input_dir, args.output)
    elif args.left and args.right:
        # Dual image processing
        processor.process_dual_images(args.left, args.right, args.output)
    else:
        print("Error: Please provide both left and right image files, or use --gui or --batch")
        parser.print_help()

if __name__ == "__main__":
    main() 