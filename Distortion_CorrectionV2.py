import numpy as np
import matplotlib.pyplot as plt
import discorpy.losa.loadersaver as losa
import discorpy.prep.preprocessing as prep
import discorpy.proc.processing as proc
import discorpy.post.postprocessing as post
from matplotlib.path import Path
import rawpy
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2

# Dual Camera Distortion Correction Script V2
# Processes DNG files from both cameras (left and right)
# Uses DOT-based analysis instead of chessboard analysis
# Applies cropping parameters from GUI and runs distortion analysis

class DualCameraDistortionCorrection:
    def __init__(self):
        # Cropping parameters (from GUI_IMX708_Dirsotion_Correction_v1.1.py)
        self.crop_params = {
            'cam0': {'width': 2200, 'start_x': 1230, 'height': 2592},  # Left camera
            'cam1': {'width': 2155, 'start_x': 1336, 'height': 2592}   # Right camera
        }
        
        # Processing parameters for DOT analysis
        self.num_coef = 3  # Number of polynomial coefficients (matching demo_05.py)
        self.sigma_normalization = 20  # FFT normalization parameter
        self.snr_threshold = 0.5  # Signal-to-noise ratio for threshold calculation
        
        # Dot parameters (set to None to use calc_size_distance, or specify values)
        # Example of configured values:
        # self.dot_parameters = {
        #     'cam0': {'dot_size': 70, 'dot_dist': 160},  # Use specific values for left camera
        #     'cam1': {'dot_size': 75, 'dot_dist': 165}   # Use different values for right camera  
        # }
        self.dot_parameters = {
            'cam0': {
                'dot_size': 30,  # Set to specific value or None to auto-calculate
                'dot_dist': None   # Set to specific value or None to auto-calculate
            },
            'cam1': {
                'dot_size': 30, # Set to specific value or None to auto-calculate  
                'dot_dist': None   # Set to specific value or None to auto-calculate
            }
        }
        
        # Grouping parameters for dots (separate for each camera)
        # You can adjust these parameters independently for each camera
        # to account for different dot patterns or image quality
        self.grouping_params = {
            'cam0': {  # Left camera parameters
                'ratio': 0.4,                      # Grouping tolerance ratio
                'num_dot_miss': 3,                 # Number of missing dots allowed
                'accepted_ratio': 0.5,             # Acceptance ratio for grouping
                'residual_threshold_hor': 20,     # Horizontal residual threshold
                'residual_threshold_ver': 20.0     # Vertical residual threshold
            },
            'cam1': {  # Right camera parameters  
                'ratio': 0.4,                      # Can be different from cam0
                'num_dot_miss': 3,                 # Can be different from cam0
                'accepted_ratio': 0.5,             # Can be different from cam0
                'residual_threshold_hor': 20.0,    # Can be different from cam0
                'residual_threshold_ver': 20.0     # Can be different from cam0
            }
        }
        
        # Toggle options
        self.apply_masking = 0  # Set to 1 to enable masking, 0 to disable
        self.test_images = 0  # Set to 1 to test images, 0 to disable
        self.debug_plots = 1  # Set to 1 to enable debug plots, 0 to disable
        self.exclude_edge_lines = 1  # Set to 1 to exclude edge lines (enabled by default for dots)
        self.save_intermediate = 1  # Set to 1 to save intermediate images
        
        # Results storage
        self.results = {
            'cam0': {'xcenter': None, 'ycenter': None, 'coeffs': None},
            'cam1': {'xcenter': None, 'ycenter': None, 'coeffs': None}
        }
        
        # Store processed data for comparison
        self.processed_data = {
            'cam0': {},
            'cam1': {}
        }
        
    def load_dng_image(self, filepath, to_grayscale=True):
        """Load DNG image using rawpy"""
        try:
            print(f"Loading DNG file: {os.path.basename(filepath)}")
            raw = rawpy.imread(filepath)
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=False,
                no_auto_bright=False,
                output_bps=16,
                output_color=rawpy.ColorSpace.sRGB,
            )
            
            if to_grayscale:
                # Convert to grayscale for distortion analysis
                gray = np.mean(rgb, axis=2).astype(np.uint16)
                print(f"   Converted to grayscale: {gray.shape}, range: [{gray.min()}, {gray.max()}]")
                return gray, rgb
            else:
                print(f"   Loaded RGB: {rgb.shape}, range: [{rgb.min()}, {rgb.max()}]")
                return rgb, rgb
            
        except Exception as e:
            print(f"[ERROR] Failed to load DNG file {filepath}: {e}")
            return None, None
    
    def crop_image(self, image, cam_name):
        """Crop image according to camera-specific parameters"""
        params = self.crop_params[cam_name]
        start_x = params['start_x']
        width = params['width']
        height = params['height']
        
        # Crop the image: [y_start:y_end, x_start:x_end]
        cropped = image[:height, start_x:start_x + width]
        print(f"   Cropped {cam_name}: {image.shape} -> {cropped.shape}")
        return cropped
    
    def save_jpeg_from_array(self, image_array, output_path, quality=95):
        """Save numpy array as JPEG"""
        try:
            # Normalize to 8-bit if needed
            if image_array.dtype == np.uint16:
                image_8bit = (image_array / 256).astype(np.uint8)
            elif image_array.dtype == np.float32 or image_array.dtype == np.float64:
                if image_array.max() <= 1.0:
                    image_8bit = (image_array * 255).astype(np.uint8)
                else:
                    image_8bit = np.clip(image_array / image_array.max() * 255, 0, 255).astype(np.uint8)
            else:
                image_8bit = np.clip(image_array, 0, 255).astype(np.uint8)
            
            losa.save_image(output_path, image_8bit)
            print(f"   Saved JPEG: {output_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save JPEG {output_path}: {e}")
            return False

    def get_dot_parameters(self, segmented_image, cam_name):
        """Get dot size and distance for a camera - use configured values or auto-calculate"""
        config = self.dot_parameters[cam_name]
        
        # Try to get configured values first
        dot_size = config.get('dot_size')
        dot_dist = config.get('dot_dist')
        
        # If either is None, calculate them
        if dot_size is None or dot_dist is None:
            try:
                calc_dot_size, calc_dot_dist = prep.calc_size_distance(segmented_image)
                if dot_size is None:
                    dot_size = calc_dot_size
                if dot_dist is None:
                    dot_dist = calc_dot_dist
                print(f"   {cam_name}: Calculated dot_size={calc_dot_size:.1f}, dot_dist={calc_dot_dist:.1f}")
            except Exception as e:
                print(f"   {cam_name}: Failed to calculate dot parameters, using defaults: {e}")
                if dot_size is None:
                    dot_size = 70  # Default from demo_05.py
                if dot_dist is None:
                    dot_dist = 162  # Default from demo_05.py
        
        # Use configured values
        if config.get('dot_size') is not None:
            print(f"   {cam_name}: Using configured dot_size={dot_size:.1f}")
        if config.get('dot_dist') is not None:
            print(f"   {cam_name}: Using configured dot_dist={dot_dist:.1f}")
            
        # Store final values for summary
        if cam_name == 'cam0':
            self._final_left_dot_size = dot_size
            self._final_left_dot_dist = dot_dist
        else:
            self._final_right_dot_size = dot_size
            self._final_right_dot_dist = dot_dist
            
        return dot_size, dot_dist

    def process_both_cameras_parallel(self, left_image, right_image, output_base):
        """Process both cameras in parallel steps for comparison"""
        print(f"\n=== Processing Both Cameras (Dot Analysis) ===")
        
        # Create output directories
        cam0_output_dir = f"{output_base}_cam0"
        cam1_output_dir = f"{output_base}_cam1"
        os.makedirs(cam0_output_dir, exist_ok=True)
        os.makedirs(cam1_output_dir, exist_ok=True)
        
        # Save input images
        self.save_jpeg_from_array(left_image, f"{cam0_output_dir}/00_input_cropped.jpg")
        self.save_jpeg_from_array(right_image, f"{cam1_output_dir}/00_input_cropped.jpg")
        
        # Step 1: Background normalization for both cameras
        print("\n--- Step 1: Background Normalization ---")
        print("Normalizing background using FFT for both cameras...")
        
        left_normalized = prep.normalization_fft(left_image, sigma=self.sigma_normalization)
        right_normalized = prep.normalization_fft(right_image, sigma=self.sigma_normalization)
        
        if self.save_intermediate:
            losa.save_image(f"{cam0_output_dir}/01_normalized.jpg", left_normalized)
            losa.save_image(f"{cam1_output_dir}/01_normalized.jpg", right_normalized)
        
        # Step 2: Dot segmentation for both cameras  
        print("\n--- Step 2: Dot Segmentation ---")
        print("Calculating thresholds and segmenting dots...")
        
        threshold_left = prep.calculate_threshold(left_normalized, bgr="bright", snr=self.snr_threshold)
        threshold_right = prep.calculate_threshold(right_normalized, bgr="bright", snr=self.snr_threshold)
        
        left_segmented = prep.binarization(left_normalized, thres=threshold_left)
        right_segmented = prep.binarization(right_normalized, thres=threshold_right)
        
        print(f"   Left threshold: {threshold_left:.3f}, Right threshold: {threshold_right:.3f}")
        
        if self.save_intermediate:
            losa.save_image(f"{cam0_output_dir}/02_segmented_dots.jpg", left_segmented)
            losa.save_image(f"{cam1_output_dir}/02_segmented_dots.jpg", right_segmented)
        
        # Step 3: Calculate dot parameters
        print("\n--- Step 3: Dot Analysis ---")
        print("Calculating dot sizes and distances...")
        
        # Get dot parameters for each camera (configured or calculated)
        left_dot_size, left_dot_dist = self.get_dot_parameters(left_segmented, 'cam0')
        right_dot_size, right_dot_dist = self.get_dot_parameters(right_segmented, 'cam1')
        
        print(f"   Final parameters:")
        print(f"   Left: dot_size={left_dot_size:.1f}, dot_dist={left_dot_dist:.1f}")
        print(f"   Right: dot_size={right_dot_size:.1f}, dot_dist={right_dot_dist:.1f}")
        
        # Step 4: Calculate slopes for both cameras
        print("\n--- Step 4: Slope Calculation ---") 
        print("Calculating horizontal and vertical slopes...")
        
        left_hor_slope = prep.calc_hor_slope(left_segmented)
        left_ver_slope = prep.calc_ver_slope(left_segmented)
        right_hor_slope = prep.calc_hor_slope(right_segmented)
        right_ver_slope = prep.calc_ver_slope(right_segmented)
        
        print(f"   Left - Horizontal: {left_hor_slope:.4f}, Vertical: {left_ver_slope:.4f}")
        print(f"   Right - Horizontal: {right_hor_slope:.4f}, Vertical: {right_ver_slope:.4f}")
        
        # Debug plot: Show segmented dots and slopes side by side
        if self.debug_plots:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            
            # Left camera
            ax1.imshow(left_segmented, cmap='gray')
            ax1.set_title(f"Left Camera (cam0) - Segmented Dots\nHor slope: {left_hor_slope:.4f}, Ver slope: {left_ver_slope:.4f}\nDot size: {left_dot_size:.1f}, Dot dist: {left_dot_dist:.1f}")
            ax1.axis('off')
            
            # Right camera  
            ax2.imshow(right_segmented, cmap='gray')
            ax2.set_title(f"Right Camera (cam1) - Segmented Dots\nHor slope: {right_hor_slope:.4f}, Ver slope: {right_ver_slope:.4f}\nDot size: {right_dot_size:.1f}, Dot dist: {right_dot_dist:.1f}")
            ax2.axis('off')
            
            plt.tight_layout()
            plt.savefig(f"{output_base}/debug_01_segmented_dots_comparison.png", dpi=150, bbox_inches='tight')
            plt.show()
        
        # Step 5: Group dots into lines for both cameras
        print("\n--- Step 5: Grouping Dots into Lines ---")
        print("Grouping dots into horizontal and vertical lines...")
        
        # Left camera grouping (using cam0 parameters)
        left_params = self.grouping_params['cam0']
        left_hor_lines = prep.group_dots_hor_lines(left_segmented, left_hor_slope, left_dot_dist,
                                                   ratio=left_params['ratio'], 
                                                   num_dot_miss=left_params['num_dot_miss'],
                                                   accepted_ratio=left_params['accepted_ratio'])
        left_ver_lines = prep.group_dots_ver_lines(left_segmented, left_ver_slope, left_dot_dist,
                                                   ratio=left_params['ratio'], 
                                                   num_dot_miss=left_params['num_dot_miss'],
                                                   accepted_ratio=left_params['accepted_ratio'])
        
        # Right camera grouping (using cam1 parameters)
        right_params = self.grouping_params['cam1']
        right_hor_lines = prep.group_dots_hor_lines(right_segmented, right_hor_slope, right_dot_dist,
                                                    ratio=right_params['ratio'], 
                                                    num_dot_miss=right_params['num_dot_miss'],
                                                    accepted_ratio=right_params['accepted_ratio'])
        right_ver_lines = prep.group_dots_ver_lines(right_segmented, right_ver_slope, right_dot_dist,
                                                    ratio=right_params['ratio'], 
                                                    num_dot_miss=right_params['num_dot_miss'],
                                                    accepted_ratio=right_params['accepted_ratio'])
        
        print(f"   Left: {len(left_hor_lines)} horizontal lines, {len(left_ver_lines)} vertical lines")
        print(f"   Right: {len(right_hor_lines)} horizontal lines, {len(right_ver_lines)} vertical lines")
        
        # Exclude edge lines if enabled
        if self.exclude_edge_lines:
            if len(left_ver_lines) > 2:
                left_ver_lines = left_ver_lines[1:-1]
                print(f"   Left: Excluded edge lines, now {len(left_ver_lines)} vertical lines")
            if len(right_ver_lines) > 2:
                right_ver_lines = right_ver_lines[1:-1] 
                print(f"   Right: Excluded edge lines, now {len(right_ver_lines)} vertical lines")
        
        # Step 6: Remove residual dots for both cameras
        print("\n--- Step 6: Removing Residual Dots ---")
        
        left_hor_lines = prep.remove_residual_dots_hor(left_hor_lines, left_hor_slope, 
                                                       left_params['residual_threshold_hor'])
        left_ver_lines = prep.remove_residual_dots_ver(left_ver_lines, left_ver_slope, 
                                                       left_params['residual_threshold_ver'])
        
        right_hor_lines = prep.remove_residual_dots_hor(right_hor_lines, right_hor_slope, 
                                                        right_params['residual_threshold_hor'])
        right_ver_lines = prep.remove_residual_dots_ver(right_ver_lines, right_ver_slope, 
                                                        right_params['residual_threshold_ver'])
        
        print(f"   After residual removal:")
        print(f"   Left: {len(left_hor_lines)} horizontal lines, {len(left_ver_lines)} vertical lines")
        print(f"   Right: {len(right_hor_lines)} horizontal lines, {len(right_ver_lines)} vertical lines")
        
        # Debug plot: Show grouped lines side by side (FIXED COORDINATE ROTATION)
        if self.debug_plots:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # Left horizontal lines (FIXED: switched coordinates)
            ax1.imshow(left_segmented, cmap='gray')
            for i, line in enumerate(left_hor_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax1.plot(arr[:, 1], arr[:, 0], 'r-o', markersize=2, linewidth=1, 
                            label=f'Line {i}' if i < 3 else "")
            ax1.set_title(f"Left Camera - Horizontal Lines ({len(left_hor_lines)})")
            ax1.axis('off')
            
            # Left vertical lines (FIXED: switched coordinates)
            ax2.imshow(left_segmented, cmap='gray')
            for i, line in enumerate(left_ver_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax2.plot(arr[:, 1], arr[:, 0], 'b-o', markersize=2, linewidth=1,
                            label=f'Line {i}' if i < 3 else "")
            ax2.set_title(f"Left Camera - Vertical Lines ({len(left_ver_lines)})")
            ax2.axis('off')
            
            # Right horizontal lines (FIXED: switched coordinates)
            ax3.imshow(right_segmented, cmap='gray')
            for i, line in enumerate(right_hor_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax3.plot(arr[:, 1], arr[:, 0], 'r-o', markersize=2, linewidth=1,
                            label=f'Line {i}' if i < 3 else "")
            ax3.set_title(f"Right Camera - Horizontal Lines ({len(right_hor_lines)})")
            ax3.axis('off')
            
            # Right vertical lines (FIXED: switched coordinates)
            ax4.imshow(right_segmented, cmap='gray')
            for i, line in enumerate(right_ver_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax4.plot(arr[:, 1], arr[:, 0], 'b-o', markersize=2, linewidth=1,
                            label=f'Line {i}' if i < 3 else "")
            ax4.set_title(f"Right Camera - Vertical Lines ({len(right_ver_lines)})")
            ax4.axis('off')
            
            plt.tight_layout()
            plt.savefig(f"{output_base}/debug_02_grouped_lines_comparison.png", dpi=150, bbox_inches='tight')
            plt.show()
        
        # Save intermediate line plots
        if self.save_intermediate:
            height_left, width_left = left_image.shape
            height_right, width_right = right_image.shape
            
            losa.save_plot_image(f"{cam0_output_dir}/03_horizontal_lines.png", left_hor_lines, height_left, width_left)
            losa.save_plot_image(f"{cam0_output_dir}/03_vertical_lines.png", left_ver_lines, height_left, width_left)
            losa.save_plot_image(f"{cam1_output_dir}/03_horizontal_lines.png", right_hor_lines, height_right, width_right)
            losa.save_plot_image(f"{cam1_output_dir}/03_vertical_lines.png", right_ver_lines, height_right, width_right)
        
        # Step 7: Process each camera's distortion parameters
        print("\n--- Step 7: Calculating Distortion Parameters ---")
        
        # Store data for individual processing
        self.processed_data['cam0'] = {
            'image': left_image, 'hor_lines': left_hor_lines, 'ver_lines': left_ver_lines,
            'output_dir': cam0_output_dir
        }
        self.processed_data['cam1'] = {
            'image': right_image, 'hor_lines': right_hor_lines, 'ver_lines': right_ver_lines,
            'output_dir': cam1_output_dir
        }
        
        # Process distortion correction for both cameras
        results = {}
        for cam_name in ['cam0', 'cam1']:
            cam_label = "Left" if cam_name == "cam0" else "Right"
            print(f"\n   Processing {cam_label} camera ({cam_name})...")
            
            data = self.processed_data[cam_name]
            xcenter, ycenter, coeffs = self.calculate_distortion_parameters(
                data['hor_lines'], data['ver_lines'], data['image'], 
                cam_name, data['output_dir']
            )
            
            results[cam_name] = {
                'xcenter': float(xcenter),
                'ycenter': float(ycenter),
                'coeffs': [float(c) for c in coeffs],
                'crop_params': self.crop_params[cam_name]
            }
            
            self.results[cam_name]['xcenter'] = xcenter
            self.results[cam_name]['ycenter'] = ycenter
            self.results[cam_name]['coeffs'] = coeffs
        
        return results
    
    def calculate_distortion_parameters(self, hor_lines, ver_lines, image, cam_name, output_dir):
        """Calculate distortion parameters for a single camera"""
        
        # Regenerate grid points after correcting the perspective effect
        print(f"      Regenerating grid points for {cam_name}...")
        hor_lines, ver_lines = proc.regenerate_grid_points_parabola(hor_lines, ver_lines, perspective=True)
        
        # Calculate parameters of the radial correction model
        print(f"      Finding center of distortion for {cam_name}...")
        (xcenter, ycenter) = proc.find_cod_coarse(hor_lines, ver_lines)
        
        print(f"      Calculating coefficients for {cam_name}...")
        coeffs = proc.calc_coef_backward(hor_lines, ver_lines, xcenter, ycenter, self.num_coef)
        
        # Save coefficients
        losa.save_metadata_txt(f"{output_dir}/coefficients_radial_distortion.txt", xcenter, ycenter, coeffs)
        
        print(f"      {cam_name} - X-center: {xcenter:.4f}, Y-center: {ycenter:.4f}")
        print(f"      {cam_name} - Coefficients: {coeffs}")
        
        # Check correction results
        if self.save_intermediate:
            print(f"      Checking correction results for {cam_name}...")
            
            list_uhor_lines = post.unwarp_line_backward(hor_lines, xcenter, ycenter, coeffs)
            list_uver_lines = post.unwarp_line_backward(ver_lines, xcenter, ycenter, coeffs)
            
            height, width = image.shape
            list_hor_data = post.calc_residual_hor(list_uhor_lines, xcenter, ycenter)
            list_ver_data = post.calc_residual_ver(list_uver_lines, xcenter, ycenter)
            
            losa.save_plot_image(f"{output_dir}/04_unwarpped_horizontal_lines.png", list_uhor_lines, height, width)
            losa.save_plot_image(f"{output_dir}/04_unwarpped_vertical_lines.png", list_uver_lines, height, width)
            losa.save_residual_plot(f"{output_dir}/05_hor_residual_after_correction.png", list_hor_data, height, width)
            losa.save_residual_plot(f"{output_dir}/05_ver_residual_after_correction.png", list_ver_data, height, width)
            
            # Apply correction to the image
            corrected_image = post.unwarp_image_backward(image, xcenter, ycenter, coeffs)
            losa.save_image(f"{output_dir}/06_corrected_image.jpg", corrected_image)
            losa.save_image(f"{output_dir}/06_difference.jpg", corrected_image - image)
        
        return xcenter, ycenter, coeffs

    def process_dual_cameras(self, left_dng_path, right_dng_path, output_base):
        """Process both camera DNG files using dot analysis"""
        print("=== Dual Camera Distortion Correction V2 (Dot Analysis) ===")
        print(f"Left DNG: {os.path.basename(left_dng_path)}")
        print(f"Right DNG: {os.path.basename(right_dng_path)}")
        print(f"Output base: {output_base}")
        
        # Create main output directory
        os.makedirs(output_base, exist_ok=True)
        
        # Load and process left camera (cam0)
        print("\n--- Loading Left Camera (cam0) ---")
        left_gray, left_rgb = self.load_dng_image(left_dng_path, to_grayscale=True)
        if left_gray is None:
            raise ValueError("Failed to load left camera DNG file")
        
        # Crop left image
        left_cropped = self.crop_image(left_gray, 'cam0')
        
        # Save cropped RGB version as JPEG
        left_rgb_cropped = self.crop_image(left_rgb, 'cam0')
        self.save_jpeg_from_array(left_rgb_cropped, f"{output_base}/left_cam0_cropped.jpg")
        
        # Load and process right camera (cam1)  
        print("\n--- Loading Right Camera (cam1) ---")
        right_gray, right_rgb = self.load_dng_image(right_dng_path, to_grayscale=True)
        if right_gray is None:
            raise ValueError("Failed to load right camera DNG file")
        
        # Crop right image
        right_cropped = self.crop_image(right_gray, 'cam1')
        
        # Save cropped RGB version as JPEG
        right_rgb_cropped = self.crop_image(right_rgb, 'cam1')
        self.save_jpeg_from_array(right_rgb_cropped, f"{output_base}/right_cam1_cropped.jpg")
        
        # Process both cameras in parallel for comparison
        try:
            results = self.process_both_cameras_parallel(left_cropped, right_cropped, output_base)
            
            # Save combined results
            with open(f"{output_base}/distortion_coefficients_dual.json", 'w') as f:
                json.dump(results, f, indent=4)
            
            # Save summary
            with open(f"{output_base}/summary.txt", 'w') as f:
                f.write("=== Dual Camera Distortion Correction Results (Dot Analysis) ===\n\n")
                f.write(f"Left Camera (cam0):\n")
                f.write(f"  Center: ({results['cam0']['xcenter']:.4f}, {results['cam0']['ycenter']:.4f})\n")
                f.write(f"  Coefficients: {results['cam0']['coeffs']}\n")
                f.write(f"  Crop: {self.crop_params['cam0']}\n\n")
                f.write(f"Right Camera (cam1):\n")
                f.write(f"  Center: ({results['cam1']['xcenter']:.4f}, {results['cam1']['ycenter']:.4f})\n")
                f.write(f"  Coefficients: {results['cam1']['coeffs']}\n")
                f.write(f"  Crop: {self.crop_params['cam1']}\n\n")
                
                f.write(f"Processing parameters:\n")
                f.write(f"  Number of coefficients: {self.num_coef}\n")
                
                # Write dot parameters for each camera
                for cam_name in ['cam0', 'cam1']:
                    cam_label = "Left" if cam_name == "cam0" else "Right"
                    dot_config = self.dot_parameters[cam_name]
                    group_config = self.grouping_params[cam_name]
                    
                    f.write(f"\n{cam_label} Camera ({cam_name}) parameters:\n")
                    if dot_config['dot_size'] is not None:
                        f.write(f"  Dot size: {dot_config['dot_size']:.1f} (configured)\n")
                    else:
                        f.write(f"  Dot size: auto-calculated\n")
                    if dot_config['dot_dist'] is not None:
                        f.write(f"  Dot distance: {dot_config['dot_dist']:.1f} (configured)\n")
                    else:
                        f.write(f"  Dot distance: auto-calculated\n")
                    f.write(f"  Grouping ratio: {group_config['ratio']}\n")
                    f.write(f"  Num dot miss: {group_config['num_dot_miss']}\n")
                    f.write(f"  Accepted ratio: {group_config['accepted_ratio']}\n")
                    f.write(f"  Residual threshold hor: {group_config['residual_threshold_hor']}\n")
                    f.write(f"  Residual threshold ver: {group_config['residual_threshold_ver']}\n")
                
                f.write(f"\nGeneral settings:\n")
                f.write(f"  Debug plots: {self.debug_plots}\n")
                f.write(f"  Exclude edge lines: {self.exclude_edge_lines}\n")
                f.write(f"  FFT normalization sigma: {self.sigma_normalization}\n")
                f.write(f"  SNR threshold: {self.snr_threshold}\n")
            
            print("\n=== PROCESSING COMPLETE ===")
            print(f"Left Camera (cam0):  Center: ({results['cam0']['xcenter']:.4f}, {results['cam0']['ycenter']:.4f})")
            print(f"                     Coeffs: {results['cam0']['coeffs']}")
            print(f"Right Camera (cam1): Center: ({results['cam1']['xcenter']:.4f}, {results['cam1']['ycenter']:.4f})")
            print(f"                     Coeffs: {results['cam1']['coeffs']}")
            print(f"Results saved to: {output_base}")
            print(f"\nFinal Parameters Used:")
            print(f"  Left dot params: size={getattr(self, '_final_left_dot_size', 'N/A'):.1f}, dist={getattr(self, '_final_left_dot_dist', 'N/A'):.1f}")
            print(f"  Right dot params: size={getattr(self, '_final_right_dot_size', 'N/A'):.1f}, dist={getattr(self, '_final_right_dot_dist', 'N/A'):.1f}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Processing failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_correction_on_images(self, test_image_left, test_image_right, output_base):
        """Test the correction on additional images. If both left and right are provided, merge and save only the combined image."""
        if not self.test_images:
            return
        
        print("\n=== Testing correction on additional images ===")
        
        # If both images are provided, process and merge
        if test_image_left and os.path.exists(test_image_left) and test_image_right and os.path.exists(test_image_right):
            print("Processing and merging both left and right test images...")
            # Load left
            if test_image_left.lower().endswith('.dng'):
                left_gray, left_rgb = self.load_dng_image(test_image_left, to_grayscale=False)
            else:
                left_rgb = losa.load_image(test_image_left, average=False)
            if left_rgb is None:
                print("Failed to load left test image")
                return
            left_cropped = self.crop_image(left_rgb, 'cam0')
            xcenter_l = self.results['cam0']['xcenter']
            ycenter_l = self.results['cam0']['ycenter']
            coeffs_l = self.results['cam0']['coeffs']
            if xcenter_l is None:
                print("No correction parameters for left camera")
                return
            left_corrected = np.copy(left_cropped)
            for i in range(left_corrected.shape[-1]):
                left_corrected[:, :, i] = post.unwarp_image_backward(left_corrected[:, :, i], xcenter_l, ycenter_l, coeffs_l)
            left_corrected = self.rotate_left_image(left_corrected)
            
            # Load right
            if test_image_right.lower().endswith('.dng'):
                right_gray, right_rgb = self.load_dng_image(test_image_right, to_grayscale=False)
            else:
                right_rgb = losa.load_image(test_image_right, average=False)
            if right_rgb is None:
                print("Failed to load right test image")
                return
            right_cropped = self.crop_image(right_rgb, 'cam1')
            xcenter_r = self.results['cam1']['xcenter']
            ycenter_r = self.results['cam1']['ycenter']
            coeffs_r = self.results['cam1']['coeffs']
            if xcenter_r is None:
                print("No correction parameters for right camera")
                return
            right_corrected = np.copy(right_cropped)
            for i in range(right_corrected.shape[-1]):
                right_corrected[:, :, i] = post.unwarp_image_backward(right_corrected[:, :, i], xcenter_r, ycenter_r, coeffs_r)
            
            # Merge
            min_height = min(left_corrected.shape[0], right_corrected.shape[0])
            left_resized = left_corrected[:min_height, :]
            right_resized = right_corrected[:min_height, :]
            combined = np.hstack((left_resized, right_resized))
            out_path = os.path.join(output_base, "test_images_undistorted_merged.jpg")
            self.save_jpeg_from_array(combined, out_path)
            print(f"   Merged undistorted test image saved: {out_path}")
            return
        
        # Otherwise, process individually as before
        for cam_name, test_path in [('cam0', test_image_left), ('cam1', test_image_right)]:
            if not test_path or not os.path.exists(test_path):
                print(f"Skipping {cam_name} test - file not found: {test_path}")
                continue
                
            print(f"Testing {cam_name}...")
            
            # Load test image
            if test_path.lower().endswith('.dng'):
                test_gray, test_rgb = self.load_dng_image(test_path, to_grayscale=False)
            else:
                test_rgb = losa.load_image(test_path, average=False)
                test_gray = np.mean(test_rgb, axis=2).astype(np.uint16)
            
            if test_rgb is None:
                print(f"Failed to load test image for {cam_name}")
                continue
            
            # Crop test image
            test_cropped = self.crop_image(test_rgb, cam_name)
            
            # Apply correction using stored results
            xcenter = self.results[cam_name]['xcenter']
            ycenter = self.results[cam_name]['ycenter'] 
            coeffs = self.results[cam_name]['coeffs']
            
            if xcenter is None:
                print(f"No correction parameters available for {cam_name}")
                continue
            
            test_corrected = np.copy(test_cropped)
            if len(test_corrected.shape) == 3:
                # Color image - correct each channel
                for i in range(test_corrected.shape[-1]):
                    test_corrected[:, :, i] = post.unwarp_image_backward(test_corrected[:, :, i], 
                                                                       xcenter, ycenter, coeffs)
            else:
                # Grayscale
                test_corrected = post.unwarp_image_backward(test_corrected, xcenter, ycenter, coeffs)
            
            # Save result
            test_output_dir = f"{output_base}_{cam_name}"
            self.save_jpeg_from_array(test_cropped, f"{test_output_dir}/test_image_original.jpg")
            self.save_jpeg_from_array(test_corrected, f"{test_output_dir}/test_image_corrected.jpg")
            print(f"   {cam_name} test correction saved")

    def rotate_left_image(self, image, angle=None):
        """Rotate the left image by the specified angle (default -2 degrees)."""
        if angle is None:
            angle = -2
        try:
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height),
                                     flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REFLECT_101)
            print(f"[DEBUG] Applied {angle}° rotation to left image")
            return rotated
        except Exception as e:
            print(f"[ERROR] Left image rotation failed: {e}")
            return image

# Main execution function
def main():
    # Create a simple tkinter root window for file dialogs
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    print("=== Dual Camera Distortion Correction V2 (Dot Analysis) ===")
    print("Please select the calibration files...")
    
    # Select left camera DNG file
    left_dng_path = filedialog.askopenfilename(
        title="Select LEFT Camera (cam0) DNG Calibration File",
        filetypes=[
            ("DNG files", "*.dng"),
            ("All files", "*.*")
        ],
        initialdir=r"C:\Users\NoahB\Documents\HebrewU Bioengineering\Equipment\Camera"
    )
    
    if not left_dng_path:
        print("No left DNG file selected. Exiting...")
        return
    
    # Select right camera DNG file
    right_dng_path = filedialog.askopenfilename(
        title="Select RIGHT Camera (cam1) DNG Calibration File",
        filetypes=[
            ("DNG files", "*.dng"),
            ("All files", "*.*")
        ],
        initialdir=os.path.dirname(left_dng_path)  # Start in same directory as left file
    )
    
    if not right_dng_path:
        print("No right DNG file selected. Exiting...")
        return
    
    # Select output directory
    output_base = filedialog.askdirectory(
        title="Select Output Directory for Results",
        initialdir=os.path.dirname(left_dng_path)  # Start in same directory as input files
    )
    
    if not output_base:
        # If no directory selected, use the same directory as the input files
        output_base = os.path.join(os.path.dirname(left_dng_path), "Dual_Distortion_Results")
        print(f"No output directory selected. Using: {output_base}")
    
    # Optional test images (can be selected later if needed)
    test_left = ""
    test_right = ""
    
    # Display selected files
    print(f"\nSelected files:")
    print(f"Left DNG:  {os.path.basename(left_dng_path)}")
    print(f"Right DNG: {os.path.basename(right_dng_path)}")
    print(f"Output:    {output_base}")
    
    # Ask user for processing options
    response = messagebox.askyesno(
        "Processing Options", 
        "Enable debug plots and detailed visualization?\n\n"
        "YES = Show debug plots and save intermediate images\n"
        "NO = Quick processing with minimal output"
    )
    
    debug_enabled = response
    
    # Create processor
    processor = DualCameraDistortionCorrection()
    
    # Configure processing options based on user choice
    processor.debug_plots = 1 if debug_enabled else 0
    processor.save_intermediate = 1 if debug_enabled else 0
    processor.test_images = 0  # Can be enabled separately if needed
    processor.exclude_edge_lines = 1  # Enable by default for dot analysis
    processor.num_coef = 4  # Use 4 coefficients like demo_05.py
    
    print(f"\nProcessing configuration:")
    print(f"  Analysis type: DOT-based (not chessboard)")
    print(f"  Debug plots: {'Enabled' if processor.debug_plots else 'Disabled'}")
    print(f"  Save intermediate: {'Enabled' if processor.save_intermediate else 'Disabled'}")
    print(f"  Exclude edge lines: {'Enabled' if processor.exclude_edge_lines else 'Disabled'}")
    print(f"  Number of coefficients: {processor.num_coef}")
    
    # Verify files exist
    if not os.path.exists(left_dng_path):
        messagebox.showerror("Error", f"Left DNG file not found:\n{left_dng_path}")
        return
    
    if not os.path.exists(right_dng_path):
        messagebox.showerror("Error", f"Right DNG file not found:\n{right_dng_path}")
        return
    
    try:
        # Process both cameras
        print(f"\nStarting processing...")
        success = processor.process_dual_cameras(left_dng_path, right_dng_path, output_base)
        
        if success:
            # Ask if user wants to test on additional images
            if messagebox.askyesno("Testing", "Processing complete!\n\nDo you want to test the correction on additional images?"):
                # Select test images
                test_left = filedialog.askopenfilename(
                    title="Select LEFT test image (optional - can cancel)",
                    filetypes=[
                        ("DNG files", "*.dng"),
                        ("Image files", "*.jpg;*.jpeg;*.png;*.tiff"),
                        ("All files", "*.*")
                    ],
                    initialdir=os.path.dirname(left_dng_path)
                )
                
                test_right = filedialog.askopenfilename(
                    title="Select RIGHT test image (optional - can cancel)",
                    filetypes=[
                        ("DNG files", "*.dng"),
                        ("Image files", "*.jpg;*.jpeg;*.png;*.tiff"),
                        ("All files", "*.*")
                    ],
                    initialdir=os.path.dirname(right_dng_path)
                )
                
                if test_left or test_right:
                    processor.test_images = 1  # Enable testing
                    processor.test_correction_on_images(test_left, test_right, output_base)
            
            print("\n=== All processing complete! ===")
            messagebox.showinfo("Success", 
                f"Processing completed successfully!\n\n"
                f"Results saved to:\n{output_base}\n\n"
                f"Key files:\n"
                f"• distortion_coefficients_dual.json\n"
                f"• summary.txt\n"
                f"• Individual camera results in subdirectories\n\n"
                f"Analysis type: DOT-based (not chessboard)")
            
        else:
            print("\n=== Processing failed! ===")
            messagebox.showerror("Error", "Processing failed! Check console for details.")
            
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Unexpected error occurred:\n\n{str(e)}\n\nCheck console for details.")
    
    finally:
        root.destroy()  # Clean up the tkinter root window

if __name__ == "__main__":
    main() 