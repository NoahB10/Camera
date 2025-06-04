import numpy as np
import matplotlib.pyplot as plt
import discorpy.losa.loadersaver as losa
import discorpy.prep.preprocessing as prep
import discorpy.prep.linepattern as lprep
import discorpy.proc.processing as proc
import discorpy.post.postprocessing as post
from matplotlib.path import Path
import rawpy
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2

# Dual Camera Fisheye Distortion Correction Script V3
# Processes DNG files from both cameras (left and right)
# Uses FISHEYE LINE PATTERN analysis following discorpy workflow
# Based on: https://discorpy.readthedocs.io/en/latest/technical_notes/fisheye_correction.html
# Applies cropping parameters from GUI and runs fisheye distortion analysis

class DualCameraFisheyeDistortionCorrection:
    def __init__(self):
        # Cropping parameters (from GUI_IMX708_Dirsotion_Correction_v1.1.py)
        self.crop_params = {
            'cam0': {'width': 2070, 'start_x': 1260, 'height': 2592},  # Left camera
            'cam1': {'width': 2050, 'start_x': 1400, 'height': 2592}   # Right camera
        }
        
        # Processing parameters for FISHEYE LINE PATTERN analysis
        self.num_coef = 5  # Number of polynomial coefficients for fisheye (typically 5)
        self.sigma_normalization = 10  # FFT normalization parameter (smaller for line patterns)
        
        # Line pattern detection parameters
        self.line_detection_params = {
            'cam0': {
                'bgr': 'bright',  # 'bright' for dark lines on bright background
                'chessboard': False,  # False for line patterns, True for chessboard
                'radius': 9,  # Radius for cross point detection
                'sensitive': 0.1,  # Sensitivity for peak detection
                'select_peaks': False  # Whether to select peaks manually
            },
            'cam1': {
                'bgr': 'bright',
                'chessboard': False,
                'radius': 9,
                'sensitive': 0.1,
                'select_peaks': False
            }
        }
        
        # Line grouping parameters (separate for each camera)
        self.grouping_params = {
            'cam0': {  # Left camera parameters
                'ratio': 0.1,                      # Grouping tolerance ratio for line patterns
                'num_dot_miss': 3,                 # Number of missing dots allowed
                'accepted_ratio': 0.65,            # Acceptance ratio for grouping (higher for lines)
                'order': 2,                        # Polynomial order for line fitting
                'residual_threshold': 3.0          # Residual threshold for line fitting
            },
            'cam1': {  # Right camera parameters  
                'ratio': 0.1,
                'num_dot_miss': 3,
                'accepted_ratio': 0.65,
                'order': 2,
                'residual_threshold': 3.0
            }
        }
        
        # Perspective correction parameters
        self.perspective_params = {
            'equal_dist': True,        # Use equal distance assumption
            'scale': 'mean',          # Scale method: 'mean', 'median', or specific value
            'optimizing': False,      # Whether to optimize perspective parameters
            'iteration': 2            # Number of iterations for center finding
        }
        
        # Masking parameters for removing edge points
        self.mask_params = {
            'cam0': {
                'hor_curviness': 0.4,    # Horizontal curvature for parabola mask
                'ver_curviness': 0.3,    # Vertical curvature for parabola mask  
                'hor_margin': (400, 300), # Horizontal margins (left, right)
                'ver_margin': (150, 200)  # Vertical margins (top, bottom)
            },
            'cam1': {
                'hor_curviness': 0.4,
                'ver_curviness': 0.3,
                'hor_margin': (400, 300),
                'ver_margin': (150, 200)
            }
        }
        
        # Toggle options
        self.apply_masking = 1  # Set to 1 to enable edge point masking, 0 to disable
        self.test_images = 0  # Set to 1 to test images, 0 to disable
        self.debug_plots = 1  # Set to 1 to enable debug plots, 0 to disable
        self.save_intermediate = 1  # Set to 1 to save intermediate images
        self.apply_perspective_correction = 1  # Set to 1 to apply perspective correction
        
        # Additional attributes for compatibility
        self.exclude_edge_lines = 0  # Not used in fisheye line pattern analysis
        self.snr_threshold = 0.5  # Not used in fisheye, kept for compatibility
        self.interactive_mask_drawing = 0  # Not used in fisheye, kept for compatibility
        self.auto_mask_from_points = 0  # Not used in fisheye, kept for compatibility
        self.mask_expansion_factor = 1.2  # Not used in fisheye, kept for compatibility
        self.masks = {'cam0': None, 'cam1': None}  # Not used in fisheye, kept for compatibility
        
        # Results storage
        self.results = {
            'cam0': {'xcenter': None, 'ycenter': None, 'coeffs': None, 'pers_coef': None},
            'cam1': {'xcenter': None, 'ycenter': None, 'coeffs': None, 'pers_coef': None}
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

    def process_both_cameras_parallel(self, left_image, right_image, output_base):
        """Process both cameras using fisheye line pattern analysis following discorpy workflow"""
        print(f"\n=== Processing Both Cameras (Fisheye Line Pattern Analysis) ===")
        
        # Create output directories
        cam0_output_dir = f"{output_base}_cam0"
        cam1_output_dir = f"{output_base}_cam1"
        os.makedirs(cam0_output_dir, exist_ok=True)
        os.makedirs(cam1_output_dir, exist_ok=True)
        
        # Save input images
        self.save_jpeg_from_array(left_image, f"{cam0_output_dir}/00_input_cropped.jpg")
        self.save_jpeg_from_array(right_image, f"{cam1_output_dir}/00_input_cropped.jpg")
        
        # Step 1: Background normalization for both cameras (following discorpy workflow)
        print("\n--- Step 1: Background Normalization ---")
        print("Normalizing background using FFT for both cameras...")
        
        left_normalized = prep.normalization_fft(left_image, sigma=self.sigma_normalization)
        right_normalized = prep.normalization_fft(right_image, sigma=self.sigma_normalization)
        
        if self.save_intermediate:
            losa.save_image(f"{cam0_output_dir}/01_normalized.jpg", left_normalized)
            losa.save_image(f"{cam1_output_dir}/01_normalized.jpg", right_normalized)
        
        # Step 2: Calculate slope and distance between lines for both cameras
        print("\n--- Step 2: Line Pattern Analysis ---")
        print("Calculating slopes and distances between lines...")
        
        # Left camera line analysis
        left_slope_hor, left_dist_hor = lprep.calc_slope_distance_hor_lines(
            left_normalized, chessboard=self.line_detection_params['cam0']['chessboard'])
        left_slope_ver, left_dist_ver = lprep.calc_slope_distance_ver_lines(
            left_normalized, chessboard=self.line_detection_params['cam0']['chessboard'])
        
        # Right camera line analysis  
        right_slope_hor, right_dist_hor = lprep.calc_slope_distance_hor_lines(
            right_normalized, chessboard=self.line_detection_params['cam1']['chessboard'])
        right_slope_ver, right_dist_ver = lprep.calc_slope_distance_ver_lines(
            right_normalized, chessboard=self.line_detection_params['cam1']['chessboard'])
        
        print(f"   Left - Horizontal: slope={left_slope_hor:.4f}, distance={left_dist_hor:.1f}")
        print(f"   Left - Vertical: slope={left_slope_ver:.4f}, distance={left_dist_ver:.1f}")
        print(f"   Right - Horizontal: slope={right_slope_hor:.4f}, distance={right_dist_hor:.1f}")
        print(f"   Right - Vertical: slope={right_slope_ver:.4f}, distance={right_dist_ver:.1f}")
        
        # Step 3: Extract reference points from lines
        print("\n--- Step 3: Extract Reference Points ---")
        print("Detecting cross points on lines...")
        
        # Left camera point extraction
        left_params = self.line_detection_params['cam0']
        left_points_hor_lines = lprep.get_cross_points_hor_lines(
            left_normalized, left_slope_ver, left_dist_ver,
            bgr=left_params['bgr'], chessboard=left_params['chessboard'],
            radius=left_params['radius'], sensitive=left_params['sensitive'],
            select_peaks=left_params['select_peaks'])
        left_points_ver_lines = lprep.get_cross_points_ver_lines(
            left_normalized, left_slope_hor, left_dist_hor,
            bgr=left_params['bgr'], chessboard=left_params['chessboard'],
            radius=left_params['radius'], sensitive=left_params['sensitive'],
            select_peaks=left_params['select_peaks'])
        
        # Right camera point extraction
        right_params = self.line_detection_params['cam1']
        right_points_hor_lines = lprep.get_cross_points_hor_lines(
            right_normalized, right_slope_ver, right_dist_ver,
            bgr=right_params['bgr'], chessboard=right_params['chessboard'],
            radius=right_params['radius'], sensitive=right_params['sensitive'],
            select_peaks=right_params['select_peaks'])
        right_points_ver_lines = lprep.get_cross_points_ver_lines(
            right_normalized, right_slope_hor, right_dist_hor,
            bgr=right_params['bgr'], chessboard=right_params['chessboard'],
            radius=right_params['radius'], sensitive=right_params['sensitive'],
            select_peaks=right_params['select_peaks'])
        
        print(f"   Left: {len(left_points_hor_lines)} horizontal points, {len(left_points_ver_lines)} vertical points")
        print(f"   Right: {len(right_points_hor_lines)} horizontal points, {len(right_points_ver_lines)} vertical points")
        
        # Step 4: Optional masking to remove edge points (following discorpy workflow)
        if self.apply_masking:
            print("\n--- Step 4: Remove Edge Points with Parabola Mask ---")
            height_left, width_left = left_image.shape
            height_right, width_right = right_image.shape
            
            # Left camera masking
            left_mask_params = self.mask_params['cam0']
            left_points_hor_lines = prep.remove_points_using_parabola_mask(
                left_points_hor_lines, height_left, width_left,
                hor_curviness=left_mask_params['hor_curviness'],
                ver_curviness=left_mask_params['ver_curviness'],
                hor_margin=left_mask_params['hor_margin'],
                ver_margin=left_mask_params['ver_margin'])
            left_points_ver_lines = prep.remove_points_using_parabola_mask(
                left_points_ver_lines, height_left, width_left,
                hor_curviness=left_mask_params['hor_curviness'],
                ver_curviness=left_mask_params['ver_curviness'],
                hor_margin=left_mask_params['hor_margin'],
                ver_margin=left_mask_params['ver_margin'])
            
            # Right camera masking
            right_mask_params = self.mask_params['cam1']
            right_points_hor_lines = prep.remove_points_using_parabola_mask(
                right_points_hor_lines, height_right, width_right,
                hor_curviness=right_mask_params['hor_curviness'],
                ver_curviness=right_mask_params['ver_curviness'],
                hor_margin=right_mask_params['hor_margin'],
                ver_margin=right_mask_params['ver_margin'])
            right_points_ver_lines = prep.remove_points_using_parabola_mask(
                right_points_ver_lines, height_right, width_right,
                hor_curviness=right_mask_params['hor_curviness'],
                ver_curviness=right_mask_params['ver_curviness'],
                hor_margin=right_mask_params['hor_margin'],
                ver_margin=right_mask_params['ver_margin'])
            
            print(f"   After masking - Left: {len(left_points_hor_lines)} horizontal, {len(left_points_ver_lines)} vertical")
            print(f"   After masking - Right: {len(right_points_hor_lines)} horizontal, {len(right_points_ver_lines)} vertical")
        
        # Step 5: Group points into lines (following discorpy workflow)
        print("\n--- Step 5: Group Points into Lines ---")
        print("Grouping points into horizontal and vertical lines using polynomial fitting...")
        
        # Left camera line grouping
        left_group_params = self.grouping_params['cam0']
        left_hor_lines = prep.group_dots_hor_lines_based_polyfit(
            left_points_hor_lines, left_slope_hor, left_dist_hor,
            ratio=left_group_params['ratio'],
            num_dot_miss=left_group_params['num_dot_miss'],
            accepted_ratio=left_group_params['accepted_ratio'],
            order=left_group_params['order'])
        left_ver_lines = prep.group_dots_ver_lines_based_polyfit(
            left_points_ver_lines, left_slope_ver, left_dist_ver,
            ratio=left_group_params['ratio'],
            num_dot_miss=left_group_params['num_dot_miss'],
            accepted_ratio=left_group_params['accepted_ratio'],
            order=left_group_params['order'])
        
        # Right camera line grouping
        right_group_params = self.grouping_params['cam1']
        right_hor_lines = prep.group_dots_hor_lines_based_polyfit(
            right_points_hor_lines, right_slope_hor, right_dist_hor,
            ratio=right_group_params['ratio'],
            num_dot_miss=right_group_params['num_dot_miss'],
            accepted_ratio=right_group_params['accepted_ratio'],
            order=right_group_params['order'])
        right_ver_lines = prep.group_dots_ver_lines_based_polyfit(
            right_points_ver_lines, right_slope_ver, right_dist_ver,
            ratio=right_group_params['ratio'],
            num_dot_miss=right_group_params['num_dot_miss'],
            accepted_ratio=right_group_params['accepted_ratio'],
            order=right_group_params['order'])
        
        print(f"   Left: {len(left_hor_lines)} horizontal lines, {len(left_ver_lines)} vertical lines")
        print(f"   Right: {len(right_hor_lines)} horizontal lines, {len(right_ver_lines)} vertical lines")
        
        # Step 6: Remove residual dots (following discorpy workflow)
        print("\n--- Step 6: Remove Residual Points ---")
        
        left_hor_lines = prep.remove_residual_dots_hor(left_hor_lines, left_slope_hor, 
                                                       left_group_params['residual_threshold'])
        left_ver_lines = prep.remove_residual_dots_ver(left_ver_lines, left_slope_ver, 
                                                       left_group_params['residual_threshold'])
        
        right_hor_lines = prep.remove_residual_dots_hor(right_hor_lines, right_slope_hor, 
                                                        right_group_params['residual_threshold'])
        right_ver_lines = prep.remove_residual_dots_ver(right_ver_lines, right_slope_ver, 
                                                        right_group_params['residual_threshold'])
        
        print(f"   After residual removal:")
        print(f"   Left: {len(left_hor_lines)} horizontal lines, {len(left_ver_lines)} vertical lines")
        print(f"   Right: {len(right_hor_lines)} horizontal lines, {len(right_ver_lines)} vertical lines")
        
        # Debug plot: Show detected points and grouped lines
        if self.debug_plots:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # Left camera points
            ax1.imshow(left_normalized, cmap='gray')
            ax1.plot(left_points_hor_lines[:, 1], left_points_hor_lines[:, 0], ".", color="red", markersize=1)
            ax1.plot(left_points_ver_lines[:, 1], left_points_ver_lines[:, 0], ".", color="blue", markersize=1)
            ax1.set_title(f"Left Camera - Detected Points\nH: {len(left_points_hor_lines)}, V: {len(left_points_ver_lines)}")
            ax1.axis('off')
            
            # Left camera lines
            ax2.imshow(left_normalized, cmap='gray')
            for i, line in enumerate(left_hor_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax2.plot(arr[:, 1], arr[:, 0], 'r-', linewidth=1)
            for i, line in enumerate(left_ver_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax2.plot(arr[:, 1], arr[:, 0], 'b-', linewidth=1)
            ax2.set_title(f"Left Camera - Grouped Lines\nH: {len(left_hor_lines)}, V: {len(left_ver_lines)}")
            ax2.axis('off')
            
            # Right camera points
            ax3.imshow(right_normalized, cmap='gray')
            ax3.plot(right_points_hor_lines[:, 1], right_points_hor_lines[:, 0], ".", color="red", markersize=1)
            ax3.plot(right_points_ver_lines[:, 1], right_points_ver_lines[:, 0], ".", color="blue", markersize=1)
            ax3.set_title(f"Right Camera - Detected Points\nH: {len(right_points_hor_lines)}, V: {len(right_points_ver_lines)}")
            ax3.axis('off')
            
            # Right camera lines
            ax4.imshow(right_normalized, cmap='gray')
            for i, line in enumerate(right_hor_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax4.plot(arr[:, 1], arr[:, 0], 'r-', linewidth=1)
            for i, line in enumerate(right_ver_lines):
                if len(line) > 0:
                    arr = np.array(line)
                    ax4.plot(arr[:, 1], arr[:, 0], 'b-', linewidth=1)
            ax4.set_title(f"Right Camera - Grouped Lines\nH: {len(right_hor_lines)}, V: {len(right_ver_lines)}")
            ax4.axis('off')
            
            plt.tight_layout()
            plt.savefig(f"{output_base}/debug_fisheye_line_detection.png", dpi=150, bbox_inches='tight')
            plt.show()
        
        # Save intermediate line plots
        if self.save_intermediate:
            height_left, width_left = left_image.shape
            height_right, width_right = right_image.shape
            
            losa.save_plot_image(f"{cam0_output_dir}/03_horizontal_lines.png", left_hor_lines, height_left, width_left)
            losa.save_plot_image(f"{cam0_output_dir}/03_vertical_lines.png", left_ver_lines, height_left, width_left)
            losa.save_plot_image(f"{cam1_output_dir}/03_horizontal_lines.png", right_hor_lines, height_right, width_right)
            losa.save_plot_image(f"{cam1_output_dir}/03_vertical_lines.png", right_ver_lines, height_right, width_right)
        
        # Step 7: Process each camera's fisheye distortion parameters
        print("\n--- Step 7: Calculate Fisheye Distortion Parameters ---")
        
        # Store data for individual processing
        self.processed_data['cam0'] = {
            'image': left_image, 'hor_lines': left_hor_lines, 'ver_lines': left_ver_lines,
            'output_dir': cam0_output_dir
        }
        self.processed_data['cam1'] = {
            'image': right_image, 'hor_lines': right_hor_lines, 'ver_lines': right_ver_lines,
            'output_dir': cam1_output_dir
        }
        
        # Process fisheye distortion correction for both cameras
        results = {}
        for cam_name in ['cam0', 'cam1']:
            cam_label = "Left" if cam_name == "cam0" else "Right"
            print(f"\n   Processing {cam_label} camera ({cam_name})...")
            
            data = self.processed_data[cam_name]
            xcenter, ycenter, coeffs = self.calculate_fisheye_distortion_parameters(
                data['hor_lines'], data['ver_lines'], data['image'], 
                cam_name, data['output_dir']
            )
            
            results[cam_name] = {
                'xcenter': float(xcenter),
                'ycenter': float(ycenter),
                'coeffs': [float(c) for c in coeffs],
                'pers_coef': [float(c) for c in self.results[cam_name]['pers_coef']] if self.results[cam_name].get('pers_coef') is not None else None,
                'crop_params': self.crop_params[cam_name]
            }
            
            self.results[cam_name]['xcenter'] = xcenter
            self.results[cam_name]['ycenter'] = ycenter
            self.results[cam_name]['coeffs'] = coeffs
        
        return results
    
    def calculate_fisheye_distortion_parameters(self, hor_lines, ver_lines, image, cam_name, output_dir):
        """Calculate fisheye distortion parameters following discorpy workflow"""
        
        print(f"      Starting fisheye calibration for {cam_name}...")
        
        # Step 1: Find center of distortion using vanishing points (discorpy fisheye workflow)
        print(f"      Finding center of distortion based on vanishing points for {cam_name}...")
        try:
            xcenter, ycenter = proc.find_center_based_vanishing_points_iteration(
                hor_lines, ver_lines, iteration=self.perspective_params['iteration'])
            print(f"      {cam_name} - Center of distortion: ({xcenter:.4f}, {ycenter:.4f})")
        except Exception as e:
            print(f"      Warning: Vanishing point method failed for {cam_name}, using coarse method: {e}")
            # Fallback to coarse method
            xcenter, ycenter = proc.find_cod_coarse(hor_lines, ver_lines)
            print(f"      {cam_name} - Center of distortion (coarse): ({xcenter:.4f}, {ycenter:.4f})")
        
        # Step 2: Correct perspective distortion (discorpy fisheye workflow)
        print(f"      Correcting perspective effect for {cam_name}...")
        try:
            corr_hor_lines, corr_ver_lines = proc.correct_perspective_effect(
                hor_lines, ver_lines, xcenter, ycenter)
            print(f"      {cam_name} - Perspective correction applied to lines")
        except Exception as e:
            print(f"      Warning: Perspective correction failed for {cam_name}, using original lines: {e}")
            corr_hor_lines, corr_ver_lines = hor_lines, ver_lines
        
        # Step 3: Calculate polynomial coefficients for radial distortion (discorpy fisheye workflow)
        print(f"      Calculating radial distortion coefficients for {cam_name}...")
        try:
            coeffs = proc.calc_coef_backward(corr_hor_lines, corr_ver_lines, xcenter, ycenter, self.num_coef)
            print(f"      {cam_name} - Radial distortion coefficients: {coeffs}")
        except Exception as e:
            print(f"      Error: Failed to calculate coefficients for {cam_name}: {e}")
            # Create default coefficients if calculation fails
            coeffs = [1.0] + [0.0] * (self.num_coef - 1)
            print(f"      {cam_name} - Using default coefficients: {coeffs}")
        
        # Save coefficients and metadata
        losa.save_metadata_txt(f"{output_dir}/coefficients_radial_distortion.txt", xcenter, ycenter, coeffs)
        
        # Also save in discorpy JSON format for compatibility
        try:
            losa.save_metadata_json(f"{output_dir}/distortion_parameters.json", xcenter, ycenter, coeffs)
        except Exception as e:
            print(f"      Warning: Could not save JSON metadata for {cam_name}: {e}")
        
        # Check correction results and apply perspective correction if enabled
        if self.save_intermediate:
            print(f"      Checking and saving correction results for {cam_name}...")
            
            try:
                # Test radial correction on lines
                list_uhor_lines = post.unwarp_line_backward(corr_hor_lines, xcenter, ycenter, coeffs)
                list_uver_lines = post.unwarp_line_backward(corr_ver_lines, xcenter, ycenter, coeffs)
                
                height, width = image.shape
                list_hor_data = post.calc_residual_hor(list_uhor_lines, xcenter, ycenter)
                list_ver_data = post.calc_residual_ver(list_uver_lines, xcenter, ycenter)
                
                # Save line analysis results
                losa.save_plot_image(f"{output_dir}/04_unwarpped_horizontal_lines.png", list_uhor_lines, height, width)
                losa.save_plot_image(f"{output_dir}/04_unwarpped_vertical_lines.png", list_uver_lines, height, width)
                losa.save_residual_plot(f"{output_dir}/05_hor_residual_after_correction.png", list_hor_data, height, width)
                losa.save_residual_plot(f"{output_dir}/05_ver_residual_after_correction.png", list_ver_data, height, width)
                
                # Apply radial correction to the image
                print(f"      Applying radial correction to image for {cam_name}...")
                corrected_image = post.unwarp_image_backward(image, xcenter, ycenter, coeffs)
                losa.save_image(f"{output_dir}/06_corrected_image_radial.jpg", corrected_image)
                
                # Calculate and save difference image
                try:
                    diff_image = corrected_image.astype(np.float32) - image.astype(np.float32)
                    diff_image = np.clip(diff_image + 128, 0, 255).astype(np.uint8)  # Normalize difference
                    losa.save_image(f"{output_dir}/06_difference_radial.jpg", diff_image)
                except Exception as e:
                    print(f"      Warning: Could not save difference image for {cam_name}: {e}")
                
                # Apply perspective correction if enabled (discorpy fisheye workflow)
                if self.apply_perspective_correction:
                    print(f"      Applying perspective correction for {cam_name}...")
                    try:
                        # Generate source and target points for perspective correction
                        source_points, target_points = proc.generate_source_target_perspective_points(
                            list_uhor_lines, list_uver_lines, 
                            equal_dist=self.perspective_params['equal_dist'],
                            scale=self.perspective_params['scale'],
                            optimizing=self.perspective_params['optimizing'])
                        
                        # Calculate perspective coefficients
                        pers_coef = proc.calc_perspective_coefficients(source_points, target_points, mapping="backward")
                        
                        # Apply perspective correction to the radially corrected image
                        image_pers_corr = post.correct_perspective_image(corrected_image, pers_coef)
                        
                        # Save perspective correction results
                        np.savetxt(f"{output_dir}/perspective_coefficients.txt", pers_coef.reshape(-1, 1))
                        losa.save_image(f"{output_dir}/07_corrected_image_perspective.jpg", image_pers_corr)
                        
                        # Calculate and save perspective difference
                        try:
                            pers_diff = image_pers_corr.astype(np.float32) - corrected_image.astype(np.float32)
                            pers_diff = np.clip(pers_diff + 128, 0, 255).astype(np.uint8)
                            losa.save_image(f"{output_dir}/07_difference_perspective.jpg", pers_diff)
                        except Exception as e:
                            print(f"      Warning: Could not save perspective difference for {cam_name}: {e}")
                        
                        # Store perspective coefficients in results
                        self.results[cam_name]['pers_coef'] = pers_coef
                        print(f"      {cam_name} - Perspective correction applied and saved")
                        
                    except Exception as e:
                        print(f"      Warning: Perspective correction failed for {cam_name}: {e}")
                        self.results[cam_name]['pers_coef'] = None
                else:
                    print(f"      {cam_name} - Perspective correction disabled")
                    self.results[cam_name]['pers_coef'] = None
                    
            except Exception as e:
                print(f"      Warning: Could not complete correction analysis for {cam_name}: {e}")
                import traceback
                traceback.print_exc()
        
        return xcenter, ycenter, coeffs

    def process_dual_cameras(self, left_dng_path, right_dng_path, output_base):
        """Process both camera DNG files using fisheye line pattern analysis"""
        print("=== Dual Camera Fisheye Distortion Correction V3 (Line Pattern Analysis) ===")
        print(f"Left DNG: {os.path.basename(left_dng_path)}")
        print(f"Right DNG: {os.path.basename(right_dng_path)}")
        print(f"Output base: {output_base}")
        print("Following discorpy fisheye calibration workflow")
        
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
                f.write("=== Dual Camera Fisheye Distortion Correction Results (Line Pattern Analysis) ===\n\n")
                f.write(f"Left Camera (cam0):\n")
                f.write(f"  Center: ({results['cam0']['xcenter']:.4f}, {results['cam0']['ycenter']:.4f})\n")
                f.write(f"  Radial Coefficients: {results['cam0']['coeffs']}\n")
                if results['cam0']['pers_coef'] is not None:
                    f.write(f"  Perspective: Available\n")
                else:
                    f.write(f"  Perspective: Failed/Skipped\n")
                f.write(f"  Crop: {self.crop_params['cam0']}\n\n")
                f.write(f"Right Camera (cam1):\n")
                f.write(f"  Center: ({results['cam1']['xcenter']:.4f}, {results['cam1']['ycenter']:.4f})\n")
                f.write(f"  Radial Coefficients: {results['cam1']['coeffs']}\n")
                if results['cam1']['pers_coef'] is not None:
                    f.write(f"  Perspective: Available\n")
                else:
                    f.write(f"  Perspective: Failed/Skipped\n")
                f.write(f"  Crop: {self.crop_params['cam1']}\n\n")
                
                f.write(f"Processing parameters:\n")
                f.write(f"  Number of coefficients: {self.num_coef}\n")
                f.write(f"  Analysis method: Fisheye line pattern calibration\n")
                f.write(f"  Corrections applied: Radial + Perspective\n")
                f.write(f"  Based on discorpy fisheye workflow\n")
                
                # Write line pattern parameters for each camera
                for cam_name in ['cam0', 'cam1']:
                    cam_label = "Left" if cam_name == "cam0" else "Right"
                    line_config = self.line_detection_params[cam_name]
                    group_config = self.grouping_params[cam_name]
                    mask_config = self.mask_params[cam_name]
                    
                    f.write(f"\n{cam_label} Camera ({cam_name}) parameters:\n")
                    f.write(f"  Line pattern background: {line_config['bgr']}\n")
                    f.write(f"  Chessboard: {line_config['chessboard']}\n")
                    f.write(f"  Detection radius: {line_config['radius']}\n")
                    f.write(f"  Sensitivity: {line_config['sensitive']}\n")
                    f.write(f"  Select peaks manually: {line_config['select_peaks']}\n")
                    f.write(f"  Grouping ratio: {group_config['ratio']}\n")
                    f.write(f"  Polynomial order: {group_config['order']}\n")
                    f.write(f"  Accepted ratio: {group_config['accepted_ratio']}\n")
                    f.write(f"  Residual threshold: {group_config['residual_threshold']}\n")
                    f.write(f"  Mask horizontal curviness: {mask_config['hor_curviness']}\n")
                    f.write(f"  Mask vertical curviness: {mask_config['ver_curviness']}\n")
                    f.write(f"  Mask margins: hor{mask_config['hor_margin']}, ver{mask_config['ver_margin']}\n")
                
                f.write(f"\nGeneral settings:\n")
                f.write(f"  Debug plots: {self.debug_plots}\n")
                f.write(f"  FFT normalization sigma: {self.sigma_normalization}\n")
                f.write(f"  Parabola masking: {self.apply_masking}\n")
                f.write(f"  Perspective correction: {self.apply_perspective_correction}\n")
                
                # Perspective correction parameters
                persp_config = self.perspective_params
                f.write(f"\nPerspective correction settings:\n")
                f.write(f"  Equal distance: {persp_config['equal_dist']}\n")
                f.write(f"  Scale method: {persp_config['scale']}\n")
                f.write(f"  Optimizing: {persp_config['optimizing']}\n")
                f.write(f"  Vanishing point iterations: {persp_config['iteration']}\n")
            
            print("\n=== PROCESSING COMPLETE ===")
            print(f"Left Camera (cam0):  Center: ({results['cam0']['xcenter']:.4f}, {results['cam0']['ycenter']:.4f})")
            print(f"                     Radial Coeffs: {results['cam0']['coeffs']}")
            if results['cam0']['pers_coef'] is not None:
                print(f"                     Perspective: Available")
            else:
                print(f"                     Perspective: Failed/Skipped")
            print(f"Right Camera (cam1): Center: ({results['cam1']['xcenter']:.4f}, {results['cam1']['ycenter']:.4f})")
            print(f"                     Radial Coeffs: {results['cam1']['coeffs']}")
            if results['cam1']['pers_coef'] is not None:
                print(f"                     Perspective: Available")
            else:
                print(f"                     Perspective: Failed/Skipped")
            print(f"Results saved to: {output_base}")
            print(f"\nFinal Parameters Used:")
            print(f"  Analysis method: Fisheye line pattern calibration")
            print(f"  Number of coefficients: {self.num_coef}")
            print(f"  FFT normalization sigma: {self.sigma_normalization}")
            print(f"  Parabola masking: {'Enabled' if self.apply_masking else 'Disabled'}")
            print(f"  Perspective correction: {'Enabled' if self.apply_perspective_correction else 'Disabled'}")
            print(f"  Corrections: Radial + Perspective (discorpy fisheye workflow)")
            
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
            pers_coef_l = self.results['cam0'].get('pers_coef')
            if xcenter_l is None:
                print("No correction parameters for left camera")
                return
            left_corrected = np.copy(left_cropped)
            for i in range(left_corrected.shape[-1]):
                # Apply radial correction
                left_corrected[:, :, i] = post.unwarp_image_backward(left_corrected[:, :, i], xcenter_l, ycenter_l, coeffs_l)
                # Apply perspective correction if available
                if pers_coef_l is not None:
                    left_corrected[:, :, i] = post.correct_perspective_image(left_corrected[:, :, i], pers_coef_l)
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
            pers_coef_r = self.results['cam1'].get('pers_coef')
            if xcenter_r is None:
                print("No correction parameters for right camera")
                return
            right_corrected = np.copy(right_cropped)
            for i in range(right_corrected.shape[-1]):
                # Apply radial correction
                right_corrected[:, :, i] = post.unwarp_image_backward(right_corrected[:, :, i], xcenter_r, ycenter_r, coeffs_r)
                # Apply perspective correction if available
                if pers_coef_r is not None:
                    right_corrected[:, :, i] = post.correct_perspective_image(right_corrected[:, :, i], pers_coef_r)
            
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
            pers_coef = self.results[cam_name].get('pers_coef')
            
            if xcenter is None:
                print(f"No correction parameters available for {cam_name}")
                continue
            
            test_corrected = np.copy(test_cropped)
            if len(test_corrected.shape) == 3:
                # Color image - correct each channel
                for i in range(test_corrected.shape[-1]):
                    # Apply radial correction
                    test_corrected[:, :, i] = post.unwarp_image_backward(test_corrected[:, :, i], 
                                                                       xcenter, ycenter, coeffs)
                    # Apply perspective correction if available
                    if pers_coef is not None:
                        test_corrected[:, :, i] = post.correct_perspective_image(test_corrected[:, :, i], pers_coef)
            else:
                # Grayscale
                test_corrected = post.unwarp_image_backward(test_corrected, xcenter, ycenter, coeffs)
                if pers_coef is not None:
                    test_corrected = post.correct_perspective_image(test_corrected, pers_coef)
            
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

    def draw_interactive_mask(self, image, cam_name, output_dir):
        """Draw an interactive mask for the image using matplotlib"""
        print(f"   Drawing interactive mask for {cam_name}...")
        
        class MaskDrawer:
            def __init__(self, image, title):
                self.image = image
                self.mask_points = []
                self.is_drawing = False
                self.fig, self.ax = plt.subplots(figsize=(12, 8))
                self.ax.imshow(image, cmap='gray')
                self.ax.set_title(f'{title}\nLeft click to draw polygon, Right click to finish, "r" to reset')
                self.ax.axis('on')
                
                # Connect events
                self.fig.canvas.mpl_connect('button_press_event', self.on_click)
                self.fig.canvas.mpl_connect('key_press_event', self.on_key)
                
                self.line, = self.ax.plot([], [], 'r-o', linewidth=2, markersize=4)
                self.mask = None
                
            def on_click(self, event):
                if event.inaxes != self.ax:
                    return
                    
                if event.button == 1:  # Left click
                    self.mask_points.append([event.xdata, event.ydata])
                    self.update_plot()
                elif event.button == 3:  # Right click
                    if len(self.mask_points) >= 3:
                        self.finish_mask()
                    
            def on_key(self, event):
                if event.key == 'r':  # Reset
                    self.mask_points = []
                    self.line.set_data([], [])
                    self.ax.set_title(f'{self.ax.get_title().split("\\n")[0]}\\nLeft click to draw polygon, Right click to finish, "r" to reset')
                    self.fig.canvas.draw()
                    
            def update_plot(self):
                if self.mask_points:
                    x_coords = [p[0] for p in self.mask_points]
                    y_coords = [p[1] for p in self.mask_points]
                    self.line.set_data(x_coords, y_coords)
                    self.fig.canvas.draw()
                    
            def finish_mask(self):
                if len(self.mask_points) >= 3:
                    # Create mask from polygon
                    height, width = self.image.shape
                    x, y = np.meshgrid(np.arange(width), np.arange(height))
                    points = np.column_stack((x.ravel(), y.ravel()))
                    
                    path = Path(self.mask_points)
                    self.mask = path.contains_points(points).reshape(height, width)
                    
                    # Close the polygon
                    x_coords = [p[0] for p in self.mask_points] + [self.mask_points[0][0]]
                    y_coords = [p[1] for p in self.mask_points] + [self.mask_points[0][1]]
                    self.line.set_data(x_coords, y_coords)
                    
                    self.ax.set_title(f'{self.ax.get_title().split("\\n")[0]}\\nMask created! Close window to continue.')
                    self.fig.canvas.draw()
                    
        # Create the mask drawer
        drawer = MaskDrawer(image, f"Draw Mask for {cam_name}")
        plt.show()
        
        if drawer.mask is not None:
            # Save mask
            mask_path = os.path.join(output_dir, f"mask_{cam_name}.png")
            mask_visual_path = os.path.join(output_dir, f"mask_{cam_name}_visual.png")
            
            # Save binary mask
            mask_uint8 = (drawer.mask * 255).astype(np.uint8)
            losa.save_image(mask_path, mask_uint8)
            
            # Save visual overlay
            masked_image = image.copy().astype(np.float32)
            masked_image[~drawer.mask] *= 0.3  # Darken non-masked areas
            losa.save_image(mask_visual_path, masked_image.astype(np.uint8))
            
            print(f"   Mask saved: {mask_path}")
            print(f"   Mask points: {len(drawer.mask_points)}")
            return drawer.mask
        else:
            print(f"   No mask created for {cam_name}")
            return None

    def generate_automatic_mask(self, segmented_image, cam_name, output_dir):
        """Generate automatic mask from detected dots with expansion"""
        print(f"   Generating automatic mask for {cam_name}...")
        
        try:
            # Find all dot locations
            dot_coords = np.column_stack(np.where(segmented_image > 0))
            
            if len(dot_coords) == 0:
                print(f"   Warning: No dots found for automatic mask generation in {cam_name}")
                return None
            
            # Find bounding box of all dots
            min_y, min_x = np.min(dot_coords, axis=0)
            max_y, max_x = np.max(dot_coords, axis=0)
            
            # Calculate center and expansion
            center_y = (min_y + max_y) // 2
            center_x = (min_x + max_x) // 2
            
            # Expand the bounding box
            height_half = int((max_y - min_y) * self.mask_expansion_factor / 2)
            width_half = int((max_x - min_x) * self.mask_expansion_factor / 2)
            
            # Create expanded bounds
            new_min_y = max(0, center_y - height_half)
            new_max_y = min(segmented_image.shape[0], center_y + height_half)
            new_min_x = max(0, center_x - width_half)
            new_max_x = min(segmented_image.shape[1], center_x + width_half)
            
            # Create mask
            mask = np.zeros(segmented_image.shape, dtype=bool)
            mask[new_min_y:new_max_y, new_min_x:new_max_x] = True
            
            # Save mask
            mask_path = os.path.join(output_dir, f"mask_{cam_name}_auto.png")
            mask_visual_path = os.path.join(output_dir, f"mask_{cam_name}_auto_visual.png")
            
            # Save binary mask
            mask_uint8 = (mask * 255).astype(np.uint8)
            losa.save_image(mask_path, mask_uint8)
            
            # Save visual overlay
            original_image = segmented_image.copy().astype(np.float32)
            original_image[~mask] *= 0.3  # Darken non-masked areas
            losa.save_image(mask_visual_path, original_image.astype(np.uint8))
            
            print(f"   Auto mask saved: {mask_path}")
            print(f"   Mask bounds: ({new_min_x}, {new_min_y}) to ({new_max_x}, {new_max_y})")
            print(f"   Expansion factor: {self.mask_expansion_factor}")
            
            return mask
            
        except Exception as e:
            print(f"   Error generating automatic mask for {cam_name}: {e}")
            return None

    def load_mask(self, mask_path):
        """Load a saved mask from file"""
        try:
            if os.path.exists(mask_path):
                mask_image = losa.load_image(mask_path, average=True)
                mask = mask_image > 128  # Convert to boolean
                print(f"   Loaded mask: {mask_path}")
                return mask
            else:
                print(f"   Mask file not found: {mask_path}")
                return None
        except Exception as e:
            print(f"   Error loading mask {mask_path}: {e}")
            return None

    def save_mask(self, mask, mask_path):
        """Save a mask to file"""
        try:
            mask_uint8 = (mask * 255).astype(np.uint8)
            losa.save_image(mask_path, mask_uint8)
            print(f"   Saved mask: {mask_path}")
            return True
        except Exception as e:
            print(f"   Error saving mask {mask_path}: {e}")
            return False

    def apply_mask_to_segmented(self, segmented_image, mask, cam_name):
        """Apply mask to segmented image (only keep dots within mask)"""
        if mask is None:
            print(f"   No mask to apply for {cam_name}")
            return segmented_image
            
        try:
            # Apply mask - keep only dots within the mask
            masked_segmented = segmented_image.copy()
            masked_segmented[~mask] = 0  # Set pixels outside mask to 0
            
            # Count dots before and after masking
            dots_before = np.sum(segmented_image > 0)
            dots_after = np.sum(masked_segmented > 0)
            
            print(f"   Applied mask to {cam_name}: {dots_before} -> {dots_after} dot pixels ({dots_after/dots_before*100:.1f}% retained)")
            
            return masked_segmented
            
        except Exception as e:
            print(f"   Error applying mask to {cam_name}: {e}")
            return segmented_image

    def create_or_load_masks(self, left_segmented, right_segmented, output_base):
        """Create or load masks for both cameras"""
        if not self.apply_masking:
            print("   Masking disabled - skipping mask creation")
            return None, None
            
        print("\n--- Mask Creation/Loading ---")
        
        left_mask = None
        right_mask = None
        
        # Check for existing masks first
        left_mask_path = os.path.join(output_base, "mask_cam0.png")
        right_mask_path = os.path.join(output_base, "mask_cam1.png")
        
        # Try to load existing masks
        if os.path.exists(left_mask_path):
            left_mask = self.load_mask(left_mask_path)
            print(f"   Loaded existing mask for cam0")
        
        if os.path.exists(right_mask_path):
            right_mask = self.load_mask(right_mask_path)
            print(f"   Loaded existing mask for cam1")
        
        # Create masks if they don't exist
        if left_mask is None:
            if self.interactive_mask_drawing:
                print("   Creating interactive mask for left camera (cam0)...")
                left_mask = self.draw_interactive_mask(left_segmented, "cam0", output_base)
            elif self.auto_mask_from_points:
                left_mask = self.generate_automatic_mask(left_segmented, "cam0", output_base)
        
        if right_mask is None:
            if self.interactive_mask_drawing:
                print("   Creating interactive mask for right camera (cam1)...")
                right_mask = self.draw_interactive_mask(right_segmented, "cam1", output_base)
            elif self.auto_mask_from_points:
                right_mask = self.generate_automatic_mask(right_segmented, "cam1", output_base)
        
        # Store masks for later use
        self.masks['cam0'] = left_mask
        self.masks['cam1'] = right_mask
        
        return left_mask, right_mask

# Main execution function
def main():
    # Create a simple tkinter root window for file dialogs
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    print("=== Dual Camera Fisheye Distortion Correction V3 (Line Pattern Analysis) ===")
    print("Based on discorpy fisheye calibration workflow")
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
    
    # Ask about masking options
    masking_response = messagebox.askyesnocancel(
        "Masking Options",
        "Do you want to use masking to limit dot detection?\n\n"
        "YES = Enable interactive mask drawing\n"
        "NO = Enable automatic mask from detected points\n"
        "CANCEL = Disable masking entirely"
    )
    
    # Configure masking
    if masking_response is None:  # Cancel - disable masking
        masking_enabled = False
        interactive_masking = False
        auto_masking = False
    elif masking_response:  # Yes - interactive masking
        masking_enabled = True
        interactive_masking = True
        auto_masking = False
    else:  # No - automatic masking
        masking_enabled = True
        interactive_masking = False
        auto_masking = True
    
    # Create processor
    processor = DualCameraFisheyeDistortionCorrection()
    
    # Configure processing options based on user choice
    processor.debug_plots = 1 if debug_enabled else 0
    processor.save_intermediate = 1 if debug_enabled else 0
    processor.apply_masking = 1 if masking_enabled else 0
    processor.interactive_mask_drawing = 1 if interactive_masking else 0
    processor.auto_mask_from_points = 1 if auto_masking else 0
    processor.test_images = 0  # Can be enabled separately if needed
    processor.exclude_edge_lines = 0  # Disable by default for line pattern analysis
    processor.num_coef = 5  # Use 5 coefficients like demo_05.py
    
    print(f"\nProcessing configuration:")
    print(f"  Analysis type: LINE-based (not dot-based)")
    print(f"  Debug plots: {'Enabled' if processor.debug_plots else 'Disabled'}")
    print(f"  Save intermediate: {'Enabled' if processor.save_intermediate else 'Disabled'}")
    print(f"  Masking: {'Enabled' if processor.apply_masking else 'Disabled'}")
    if processor.apply_masking:
        if processor.interactive_mask_drawing:
            print(f"  Mask mode: Interactive drawing")
        elif processor.auto_mask_from_points:
            print(f"  Mask mode: Automatic from detected points (expansion: {processor.mask_expansion_factor}x)")
    print(f"  Exclude edge lines: {'Disabled' if processor.exclude_edge_lines else 'Enabled'}")
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
                f"Analysis type: LINE-based (not dot-based)")
            
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