import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time
import numpy as np
from datetime import datetime
import os
import json
from PIL import Image, ImageTk
import discorpy.post.postprocessing as post
import imageio
import threading
import signal
import sys
from contextlib import contextmanager

# Ultra-Safe GUI for dual IMX708 camera control - NO PREVIEW VERSION (v1.4)
# 
# This version completely removes any preview functionality that could cause freezing
# Focus is on stable image capture and processing only
# 
# Key safety improvements:
# - NO OpenCV preview (main cause of freezing)
# - NO continuous capture loops  
# - Minimal camera operations
# - Text-only status updates
# - Emergency stop mechanisms

class UltraSafeIMX708Viewer:
    def __init__(self):
        # Safety flags
        self.shutdown_requested = False
        self.cameras_initializing = False
        self.operation_in_progress = False
        self.preview_running = False
        self.preview_thread = None
        
        # Camera connection status
        self.cam0_connected = False
        self.cam1_connected = False
        self.cam0 = None
        self.cam1 = None
        
        # Initialize camera configuration template
        self.camera_config = None

        # Cropping parameters
        self.crop_params = {
            'cam0': {'width': 2070, 'start_x': 1260, 'height': 2592},
            'cam1': {'width': 2020, 'start_x': 1400, 'height': 2592}
        }

        # Distortion correction parameters
        self.distortion_params = {
            'cam0': {
                'xcenter': 1189.0732,
                'ycenter': 1224.3019,
                'coeffs': [1.0493219962591438, -5.8329152691427105e-05, -4.317510446486265e-08],
                'pers_coef': None
            },
            'cam1': {
                'xcenter': 959.61816,
                'ycenter': 1238.5898,
                'coeffs': [1.048507138224826, -6.39294339791884e-05, -3.9638970842489805e-08],
                'pers_coef': None
            }
        }

        # Processing settings
        self.apply_cropping = True
        self.enable_distortion_correction = True
        self.enable_perspective_correction = True
        self.apply_left_rotation = True
        self.apply_right_rotation = False
        self.left_rotation_angle = -1.3
        self.right_rotation_angle = -0.5
        
        # Distortion correction padding
        self.left_top_padding = 170
        self.left_bottom_padding = 35
        self.right_top_padding = 200
        self.right_bottom_padding = 50

        # Default/base values
        self.defaults = {
            'ExposureTime': 10000,
            'AnalogueGain': 1.0,
            'Brightness': 0.0,
            'Contrast': 1.0,
            'Saturation': 1.0,
            'Sharpness': 1.0
        }

        # Processing defaults for reset functionality
        self.processing_defaults = {
            'apply_cropping': True,
            'enable_distortion_correction': True,
            'enable_perspective_correction': True,
            'apply_left_rotation': True,
            'apply_right_rotation': False,
            'left_rotation_angle': -1.3,
            'right_rotation_angle': -0.5,
            'left_top_padding': 170,
            'left_bottom_padding': 35,
            'right_top_padding': 200,
            'right_bottom_padding': 50
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

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Setup GUI first
        self.setup_gui()
        
        # Load settings (non-blocking)
        self.load_settings()
        self.load_distortion_coefficients()

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n[INFO] Received signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True
        if hasattr(self, 'root'):
            self.root.quit()

    @contextmanager
    def camera_timeout(self, timeout_seconds=5):
        """Context manager for camera operations with timeout"""
        import threading
        import time
        
        class TimeoutException(Exception):
            pass
        
        def timeout_handler():
            time.sleep(timeout_seconds)
            if not getattr(threading.current_thread(), 'completed', False):
                raise TimeoutException(f"Operation timed out after {timeout_seconds} seconds")
        
        timer_thread = threading.Thread(target=timeout_handler, daemon=True)
        timer_thread.start()
        
        try:
            yield
            timer_thread.completed = True
        except Exception as e:
            timer_thread.completed = True
            raise e

    def safe_camera_operation(self, operation, cam, *args, **kwargs):
        """Safely execute camera operations with error handling"""
        if self.operation_in_progress:
            self.log_message("Another operation in progress, please wait...")
            return None
            
        try:
            self.operation_in_progress = True
            with self.camera_timeout(3):  # 3 second timeout
                result = operation(cam, *args, **kwargs)
                return result
        except Exception as e:
            self.log_message(f"Camera operation failed: {e}")
            return None
        finally:
            self.operation_in_progress = False

    def initialize_cameras(self):
        """Initialize cameras with maximum safety"""
        if self.cameras_initializing or self.shutdown_requested:
            return
            
        self.cameras_initializing = True
        self.log_message("Safely initializing cameras...")
        self.log_message("WARNING: This may take 10-15 seconds, please wait...")
        
        try:
            # Try to initialize camera 0
            try:
                self.log_message("Attempting to initialize camera 0...")
                from picamera2 import Picamera2
                
                with self.camera_timeout(15):  # 15 second timeout for initialization
                    self.cam0 = Picamera2(0)
                    
                    self.camera_config = self.cam0.create_still_configuration(
                        raw={"size": (4608, 2592)},
                        controls={
                            "ExposureTime": 10000,
                            "AnalogueGain": 1.0
                        }
                    )
                    
                    self.cam0.configure(self.camera_config)
                    self.cam0.start()
                    time.sleep(1)  # Brief stabilization
                    
                self.cam0_connected = True
                self.log_message("✓ Camera 0 initialized successfully")
                
            except Exception as e:
                self.log_message(f"✗ Camera 0 failed: {e}")
                self.cam0_connected = False
                if self.cam0:
                    try:
                        self.cam0.stop()
                    except:
                        pass
                self.cam0 = None

            # Try to initialize camera 1
            try:
                self.log_message("Attempting to initialize camera 1...")
                
                with self.camera_timeout(15):
                    if self.camera_config is not None:
                        self.cam1 = Picamera2(1)
                        self.cam1.configure(self.camera_config)
                        self.cam1.start()
                        time.sleep(1)
                    else:
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
                        time.sleep(1)
                        
                self.cam1_connected = True
                self.log_message("✓ Camera 1 initialized successfully")
                
            except Exception as e:
                self.log_message(f"✗ Camera 1 failed: {e}")
                self.cam1_connected = False
                if self.cam1:
                    try:
                        self.cam1.stop()
                    except:
                        pass
                self.cam1 = None

            # Apply initial settings to connected cameras
            if self.cam0_connected or self.cam1_connected:
                self.apply_settings()
                
        except ImportError:
            self.log_message("ERROR: Picamera2 not available - running in simulation mode")
            self.cam0_connected = False
            self.cam1_connected = False
            
        finally:
            self.cameras_initializing = False
            
        # Report final status
        if self.cam0_connected and self.cam1_connected:
            self.log_message("🎉 SUCCESS: Both cameras ready for use!")
            self.update_status_display("Both cameras connected - Ready!")
        elif self.cam0_connected or self.cam1_connected:
            connected = "Camera 0" if self.cam0_connected else "Camera 1"
            self.log_message(f"⚠️  PARTIAL: Only {connected} connected")
            self.update_status_display(f"Only {connected} connected")
        else:
            self.log_message("❌ No cameras connected - GUI ready in simulation mode")
            self.update_status_display("No cameras - Simulation mode")

    def update_status_display(self, message):
        """Update GUI status display safely"""
        if hasattr(self, 'status_label') and not self.shutdown_requested:
            try:
                self.status_label.config(text=message)
                self.root.update_idletasks()
            except:
                pass

    def log_message(self, message):
        """Add message to log display"""
        if not hasattr(self, 'log_text') or self.shutdown_requested:
            print(message)  # Fallback to console
            return
            
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            full_message = f"[{timestamp}] {message}"
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, full_message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.root.update_idletasks()
            
            print(full_message)  # Also print to console
        except:
            print(message)  # Fallback

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Safe Dual IMX708 Camera Control with Preview")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.geometry("1400x900")  # Increased height from 800 to 900

        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Status frame at top
        status_frame = ttk.LabelFrame(main_frame, text="System Status")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Initializing...", font=('TkDefaultFont', 12, 'bold'))
        self.status_label.pack(pady=5)

        # Create three-column horizontal layout
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left control frame (camera parameters and basic actions)
        control_frame = ttk.Frame(content_frame)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        control_frame.config(width=280)

        # Middle processing frame (actions and processing controls tabs)
        processing_main_frame = ttk.Frame(content_frame)
        processing_main_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        processing_main_frame.config(width=350)

        # Right frame (preview and log)
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # === CAMERA PARAMETERS SECTION ===
        self.entries = {}
        self.scales = {}

        # Camera parameter controls
        params_frame = ttk.LabelFrame(control_frame, text="Camera Parameters")
        params_frame.pack(fill=tk.X, pady=(0, 10))

        for param_name, param_data in self.params.items():
            frame = ttk.LabelFrame(params_frame, text=param_name)
            frame.pack(fill=tk.X, padx=5, pady=2)

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

            entry = ttk.Entry(entry_frame, width=8)
            entry.insert(0, str(param_data['value']))
            entry.pack(side=tk.LEFT, padx=2)
            entry.bind('<Return>', lambda e, p=param_name: self.on_entry_change(p))
            self.entries[param_name] = entry

            ttk.Button(entry_frame, text="Set", command=lambda p=param_name: self.on_entry_change(p)).pack(side=tk.LEFT, padx=2)
            ttk.Button(entry_frame, text="Reset", command=lambda p=param_name: self.reset_parameter(p)).pack(side=tk.LEFT, padx=2)

        # Processing options - Save Options
        save_frame = ttk.LabelFrame(control_frame, text="Save Options")
        save_frame.pack(fill=tk.X, pady=(0, 10))

        self.save_tiff_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(save_frame, text="Save Combined TIFF", 
                       variable=self.save_tiff_var).pack(anchor=tk.W, padx=5, pady=2)

        self.save_dng_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(save_frame, text="Save Original DNG Files", 
                       variable=self.save_dng_var).pack(anchor=tk.W, padx=5, pady=2)

        # === MIDDLE PROCESSING FRAME - Actions First, Then Processing Controls ===
        
        # Action buttons (moved above processing controls)
        action_frame = ttk.LabelFrame(processing_main_frame, text="Actions")
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(action_frame, text="💾 Save Images", command=self.safe_save_image).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="🧪 Test Single Capture", command=self.test_capture).pack(fill=tk.X, padx=5, pady=2)
        
        # Preview controls
        preview_controls_frame = ttk.LabelFrame(action_frame, text="Preview Controls")
        preview_controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.preview_button = ttk.Button(preview_controls_frame, text="▶️ Start Preview", command=self.toggle_preview)
        self.preview_button.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(preview_controls_frame, text="📷 Single Frame", command=self.capture_single_frame).pack(fill=tk.X, padx=5, pady=2)
        
        # Frame rate control
        rate_frame = ttk.Frame(preview_controls_frame)
        rate_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(rate_frame, text="FPS:").pack(side=tk.LEFT)
        
        self.fps_var = tk.StringVar(value="2")
        fps_combo = ttk.Combobox(rate_frame, textvariable=self.fps_var, width=8, values=["0.5", "1", "2", "3", "5"])
        fps_combo.pack(side=tk.RIGHT)
        fps_combo.bind("<<ComboboxSelected>>", self.on_fps_change)
        
        ttk.Button(action_frame, text="🔄 Reset All Parameters", command=self.reset_all).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="💾 Save Settings", command=self.save_settings).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="📁 Load Distortion Coefficients", command=self.load_coefficients_dialog).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="📊 Show Processing Info", command=self.show_processing_info).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="🔌 Reconnect Cameras", command=self.safe_reconnect_cameras).pack(fill=tk.X, padx=5, pady=2)
        
        # Emergency stop button
        ttk.Button(action_frame, text="🛑 EMERGENCY STOP", command=self.emergency_stop).pack(fill=tk.X, padx=5, pady=5)

        # Processing Controls (moved below actions)
        processing_frame = ttk.LabelFrame(processing_main_frame, text="Processing Controls")
        processing_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create a notebook for organized tabs
        processing_notebook = ttk.Notebook(processing_frame)
        processing_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Basic Processing Options
        basic_tab = ttk.Frame(processing_notebook)
        processing_notebook.add(basic_tab, text="Basic")
        
        # Basic processing checkboxes
        self.cropping_var = tk.BooleanVar(value=self.apply_cropping)
        ttk.Checkbutton(basic_tab, text="Apply Cropping", 
                       variable=self.cropping_var,
                       command=self.update_cropping_setting).pack(anchor=tk.W, padx=5, pady=2)
        
        self.distortion_var = tk.BooleanVar(value=self.enable_distortion_correction)
        ttk.Checkbutton(basic_tab, text="Apply Radial Distortion Correction", 
                       variable=self.distortion_var,
                       command=self.update_distortion_setting).pack(anchor=tk.W, padx=5, pady=2)
        
        self.perspective_var = tk.BooleanVar(value=self.enable_perspective_correction)
        ttk.Checkbutton(basic_tab, text="Enable Perspective Correction", 
                       variable=self.perspective_var,
                       command=self.update_perspective_setting).pack(anchor=tk.W, padx=5, pady=2)
        
        # Left rotation controls
        left_rot_frame = ttk.Frame(basic_tab)
        left_rot_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.left_rotation_var = tk.BooleanVar(value=self.apply_left_rotation)
        ttk.Checkbutton(left_rot_frame, text="Left Image Rotation:", 
                       variable=self.left_rotation_var,
                       command=self.update_left_rotation_setting).pack(side=tk.LEFT)
        
        self.left_angle_var = tk.DoubleVar(value=self.left_rotation_angle)
        left_angle_entry = ttk.Entry(left_rot_frame, textvariable=self.left_angle_var, width=8)
        left_angle_entry.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(left_rot_frame, text="°").pack(side=tk.LEFT)
        
        # Right rotation controls
        right_rot_frame = ttk.Frame(basic_tab)
        right_rot_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.right_rotation_var = tk.BooleanVar(value=self.apply_right_rotation)
        ttk.Checkbutton(right_rot_frame, text="Right Image Rotation:", 
                       variable=self.right_rotation_var,
                       command=self.update_right_rotation_setting).pack(side=tk.LEFT)
        
        self.right_angle_var = tk.DoubleVar(value=self.right_rotation_angle)
        right_angle_entry = ttk.Entry(right_rot_frame, textvariable=self.right_angle_var, width=8)
        right_angle_entry.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(right_rot_frame, text="°").pack(side=tk.LEFT)
        
        # Tab 2: Distortion Padding
        padding_tab = ttk.Frame(processing_notebook)
        processing_notebook.add(padding_tab, text="Padding")
        
        ttk.Label(padding_tab, text="Distortion Correction Padding (pixels):").pack(anchor=tk.W, padx=5, pady=(5, 2))
        ttk.Label(padding_tab, text="Higher values preserve more content but may add artifacts").pack(anchor=tk.W, padx=5, pady=(0, 5))
        
        # Left camera padding
        left_pad_frame = ttk.LabelFrame(padding_tab, text="Left Camera (cam0)")
        left_pad_frame.pack(fill=tk.X, padx=5, pady=5)
        
        left_pad_row1 = ttk.Frame(left_pad_frame)
        left_pad_row1.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(left_pad_row1, text="Top:").pack(side=tk.LEFT)
        self.left_top_padding_var = tk.IntVar(value=self.left_top_padding)
        left_top_entry = ttk.Entry(left_pad_row1, textvariable=self.left_top_padding_var, width=8)
        left_top_entry.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(left_pad_row1, text="Bottom:").pack(side=tk.LEFT)
        self.left_bottom_padding_var = tk.IntVar(value=self.left_bottom_padding)
        left_bottom_entry = ttk.Entry(left_pad_row1, textvariable=self.left_bottom_padding_var, width=8)
        left_bottom_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Right camera padding
        right_pad_frame = ttk.LabelFrame(padding_tab, text="Right Camera (cam1)")
        right_pad_frame.pack(fill=tk.X, padx=5, pady=5)
        
        right_pad_row1 = ttk.Frame(right_pad_frame)
        right_pad_row1.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(right_pad_row1, text="Top:").pack(side=tk.LEFT)
        self.right_top_padding_var = tk.IntVar(value=self.right_top_padding)
        right_top_entry = ttk.Entry(right_pad_row1, textvariable=self.right_top_padding_var, width=8)
        right_top_entry.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(right_pad_row1, text="Bottom:").pack(side=tk.LEFT)
        self.right_bottom_padding_var = tk.IntVar(value=self.right_bottom_padding)
        right_bottom_entry = ttk.Entry(right_pad_row1, textvariable=self.right_bottom_padding_var, width=8)
        right_bottom_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Tab 3: Crop Parameters
        crop_tab = ttk.Frame(processing_notebook)
        processing_notebook.add(crop_tab, text="Crop")
        
        ttk.Label(crop_tab, text="Cropping Parameters:").pack(anchor=tk.W, padx=5, pady=(5, 2))
        
        # Left camera crop
        left_crop_frame = ttk.LabelFrame(crop_tab, text="Left Camera (cam0)")
        left_crop_frame.pack(fill=tk.X, padx=5, pady=5)
        
        left_crop_row1 = ttk.Frame(left_crop_frame)
        left_crop_row1.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(left_crop_row1, text="Width:").pack(side=tk.LEFT)
        self.left_width_var = tk.IntVar(value=self.crop_params['cam0']['width'])
        ttk.Entry(left_crop_row1, textvariable=self.left_width_var, width=8).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(left_crop_row1, text="Start X:").pack(side=tk.LEFT)
        self.left_start_x_var = tk.IntVar(value=self.crop_params['cam0']['start_x'])
        ttk.Entry(left_crop_row1, textvariable=self.left_start_x_var, width=8).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(left_crop_row1, text="Height:").pack(side=tk.LEFT)
        self.left_height_var = tk.IntVar(value=self.crop_params['cam0']['height'])
        ttk.Entry(left_crop_row1, textvariable=self.left_height_var, width=8).pack(side=tk.LEFT, padx=(5, 0))
        
        # Right camera crop
        right_crop_frame = ttk.LabelFrame(crop_tab, text="Right Camera (cam1)")
        right_crop_frame.pack(fill=tk.X, padx=5, pady=5)
        
        right_crop_row1 = ttk.Frame(right_crop_frame)
        right_crop_row1.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(right_crop_row1, text="Width:").pack(side=tk.LEFT)
        self.right_width_var = tk.IntVar(value=self.crop_params['cam1']['width'])
        ttk.Entry(right_crop_row1, textvariable=self.right_width_var, width=8).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(right_crop_row1, text="Start X:").pack(side=tk.LEFT)
        self.right_start_x_var = tk.IntVar(value=self.crop_params['cam1']['start_x'])
        ttk.Entry(right_crop_row1, textvariable=self.right_start_x_var, width=8).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(right_crop_row1, text="Height:").pack(side=tk.LEFT)
        self.right_height_var = tk.IntVar(value=self.crop_params['cam1']['height'])
        ttk.Entry(right_crop_row1, textvariable=self.right_height_var, width=8).pack(side=tk.LEFT, padx=(5, 0))

<<<<<<< HEAD
        # Preview display (top right) - Made 2x larger with proper aspect ratio
        preview_frame = ttk.LabelFrame(right_frame, text="Camera Preview")
        preview_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Calculate proper preview dimensions based on cropped image aspect ratio
        # Combined cropped width: cam0_width + cam1_width = 2070 + 2020 = 4090
        # Cropped height: 2592 (same for both cameras)
        # Aspect ratio: 4090:2592 ≈ 1.58:1
        
        preview_width = 800   # Increased width to better show cropped content
        preview_height = int(preview_width * 2592 / 4090)  # Maintain proper aspect ratio ≈ 507
        
        self.preview_canvas = tk.Canvas(preview_frame, width=preview_width, height=preview_height, bg='black')
=======
        # Preview display (top right) - Made 2x larger
        preview_frame = ttk.LabelFrame(right_frame, text="Camera Preview")
        preview_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Preview canvas (2x larger: 960x360 instead of 480x180)
        self.preview_canvas = tk.Canvas(preview_frame, width=960, height=360, bg='black')
>>>>>>> 3ce32e7292c4137fc36611774305c6d1f5710292
        self.preview_canvas.pack(padx=5, pady=5)
        
        # Preview status
        self.preview_status = ttk.Label(preview_frame, text="Preview stopped", font=('TkDefaultFont', 9))
        self.preview_status.pack(pady=2)
        
        # Log display (bottom right) - Reduced height by half
        log_frame = ttk.LabelFrame(right_frame, text="Activity Log")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create text widget with scrollbar
        log_inner_frame = ttk.Frame(log_frame)
        log_inner_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Reduced height from 15 to 8 (approximately half)
        self.log_text = tk.Text(log_inner_frame, wrap=tk.WORD, state=tk.DISABLED, 
                               font=('Consolas', 9), bg='black', fg='lime', height=8)
        scrollbar = ttk.Scrollbar(log_inner_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add initial log messages
        self.log_message("Safe Dual IMX708 Camera Control with Preview")
        self.log_message("Stable Tkinter-based preview system")
        self.log_message("Safety Features:")
        self.log_message("  ✓ Safe Tkinter-based preview (no freezing)")
        self.log_message("  ✓ Timeout protection on all operations")
        self.log_message("  ✓ Emergency stop functionality")
        self.log_message("  ✓ Graceful error handling")
        self.log_message("  ✓ Adjustable frame rate control")
        self.log_message("")
        self.log_message("Camera initialization starting...")

        # Start camera initialization in background
        threading.Thread(target=self.initialize_cameras, daemon=True).start()

    def emergency_stop(self):
        """Emergency stop all operations"""
        self.log_message("🛑 EMERGENCY STOP ACTIVATED")
        self.operation_in_progress = False
        self.shutdown_requested = True
        
        # Stop cameras immediately
        try:
            if self.cam0:
                self.cam0.stop()
            if self.cam1:
                self.cam1.stop()
        except:
            pass
            
        self.cam0_connected = False
        self.cam1_connected = False
        self.log_message("All operations stopped")
        self.update_status_display("Emergency stopped")

    def toggle_preview(self):
        """Toggle preview on/off safely"""
        if self.preview_running:
            self.stop_preview()
        else:
            self.start_preview()

    def start_preview(self):
        """Start safe Tkinter-based preview"""
        if self.preview_running or not (self.cam0_connected or self.cam1_connected):
            if not (self.cam0_connected or self.cam1_connected):
                self.log_message("❌ Cannot start preview - no cameras connected")
            return
            
        self.preview_running = True
        self.preview_button.config(text="⏹️ Stop Preview")
        self.preview_status.config(text="Preview running...")
        self.log_message("▶️ Starting safe Tkinter preview...")
        
        # Start preview in background thread
        self.preview_thread = threading.Thread(target=self._preview_worker, daemon=True)
        self.preview_thread.start()

    def stop_preview(self):
        """Stop preview safely"""
        if not self.preview_running:
            return
            
        self.preview_running = False
        self.preview_button.config(text="▶️ Start Preview")
        self.preview_status.config(text="Preview stopped")
        self.log_message("⏹️ Stopping preview...")
        
        # Clear preview canvas
        try:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(480, 180, text="Preview Stopped", fill="white", font=('Arial', 14))
        except:
            pass

    def _preview_worker(self):
        """Background worker for safe Tkinter preview"""
        frame_count = 0
        last_time = time.time()
        
        try:
            # Get frame rate from GUI
            fps = float(self.fps_var.get())
            frame_delay = 1.0 / fps
            
            while self.preview_running and not self.shutdown_requested:
                try:
                    # Respect frame rate
                    current_time = time.time()
                    if current_time - last_time < frame_delay:
                        time.sleep(0.05)
                        continue
                    last_time = current_time
                    
                    # Capture frames safely
                    frame0 = None
                    frame1 = None
                    
                    if self.cam0_connected and self.cam0:
                        try:
                            with self.camera_timeout(2):  # 2 second timeout
                                frame0 = self.cam0.capture_array()
                        except Exception as e:
                            if frame_count % 20 == 0:  # Log every 20th error only
                                self.log_message(f"⚠️  Cam0 preview capture failed: {e}")
                    
                    if self.cam1_connected and self.cam1:
                        try:
                            with self.camera_timeout(2):  # 2 second timeout
                                frame1 = self.cam1.capture_array()
                        except Exception as e:
                            if frame_count % 20 == 0:  # Log every 20th error only
                                self.log_message(f"⚠️  Cam1 preview capture failed: {e}")
                    
                    # Update preview display using Tkinter-safe method
                    if frame0 is not None or frame1 is not None:
                        self.root.after(0, self._update_preview_display, frame0, frame1)
                    else:
                        self.root.after(0, self._update_preview_disconnected)
                    
                    frame_count += 1
                    
                    # Update status periodically
                    if frame_count % 10 == 0:
                        fps_actual = 10.0 / (time.time() - last_time) if frame_count > 0 else 0
                        status_text = f"Preview running - {fps_actual:.1f} FPS (target: {fps})"
                        self.root.after(0, lambda: self.preview_status.config(text=status_text))
                        
                except Exception as e:
                    if frame_count % 20 == 0:  # Only log every 20th error
                        self.log_message(f"⚠️  Preview error: {e}")
                    time.sleep(0.1)
                    
        except Exception as e:
            self.log_message(f"❌ Preview worker crashed: {e}")
        finally:
            self.preview_running = False
            self.root.after(0, lambda: self.preview_button.config(text="▶️ Start Preview"))
            self.root.after(0, lambda: self.preview_status.config(text="Preview stopped"))

    def _update_preview_display(self, frame0, frame1):
        """Update preview display safely in Tkinter main thread"""
        try:
            # Clear canvas
            self.preview_canvas.delete("all")
            
<<<<<<< HEAD
            # Get current canvas dimensions
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            # Use canvas dimensions if available, otherwise fall back to configured size
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width = 800
                canvas_height = int(800 * 2592 / 4090)
=======
            # Process frames for preview (light processing) - Updated for 2x larger preview
            display_width = 640  # Increased from 320
            display_height = 480  # Increased from 240
>>>>>>> 3ce32e7292c4137fc36611774305c6d1f5710292
            
            combined_image = None
            
            if frame0 is not None or frame1 is not None:
                # Create side-by-side preview matching output TIFF dimensions
                if frame0 is not None and frame1 is not None:
                    # Both cameras - process and combine like the output TIFF
                    try:
                        # Apply cropping to match output dimensions
                        crop0 = self.crop_image(frame0, 'cam0') if self.apply_cropping else frame0
                        crop1 = self.crop_image(frame1, 'cam1') if self.apply_cropping else frame1
                        
                        # Get cropped dimensions
                        h0, w0 = crop0.shape[:2]
                        h1, w1 = crop1.shape[:2]
                        
                        # Match heights for side-by-side combination
                        min_height = min(h0, h1)
                        crop0_resized = crop0[:min_height, :]
                        crop1_resized = crop1[:min_height, :]
                        
                        # Combine horizontally (like the output TIFF)
                        combined_raw = np.hstack((crop0_resized, crop1_resized))
                        
                        # Scale to fit canvas while maintaining aspect ratio
                        orig_height, orig_width = combined_raw.shape[:2]
                        
                        # Calculate scaling factor to fit within canvas
                        scale_x = canvas_width / orig_width
                        scale_y = canvas_height / orig_height
                        scale = min(scale_x, scale_y)
                        
                        new_width = int(orig_width * scale)
                        new_height = int(orig_height * scale)
                        
                        import cv2
                        combined_image = cv2.resize(combined_raw, (new_width, new_height), interpolation=cv2.INTER_AREA)
                        
                    except Exception as e:
                        self.log_message(f"Preview processing error: {e}")
                        return
                        
                elif frame0 is not None:
                    # Only camera 0
                    try:
                        crop0 = self.crop_image(frame0, 'cam0') if self.apply_cropping else frame0
                        orig_height, orig_width = crop0.shape[:2]
                        
                        # Scale to fit canvas
                        scale_x = canvas_width / orig_width
                        scale_y = canvas_height / orig_height
                        scale = min(scale_x, scale_y)
                        
                        new_width = int(orig_width * scale)
                        new_height = int(orig_height * scale)
                        
                        import cv2
                        combined_image = cv2.resize(crop0, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    except:
                        return
                        
                elif frame1 is not None:
                    # Only camera 1
                    try:
                        crop1 = self.crop_image(frame1, 'cam1') if self.apply_cropping else frame1
                        orig_height, orig_width = crop1.shape[:2]
                        
                        # Scale to fit canvas
                        scale_x = canvas_width / orig_width
                        scale_y = canvas_height / orig_width
                        scale = min(scale_x, scale_y)
                        
                        new_width = int(orig_width * scale)
                        new_height = int(orig_height * scale)
                        
                        import cv2
                        combined_image = cv2.resize(crop1, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    except:
                        return
                
                # Convert to PIL Image and display
                if combined_image is not None:
                    # Convert BGR to RGB
                    if len(combined_image.shape) == 3:
                        import cv2
                        combined_image = cv2.cvtColor(combined_image, cv2.COLOR_BGR2RGB)
                    
                    # Convert to PIL Image
                    from PIL import Image, ImageTk
                    pil_image = Image.fromarray(combined_image)
                    
                    # Convert to PhotoImage
                    self.preview_photo = ImageTk.PhotoImage(pil_image)
                    
<<<<<<< HEAD
                    # Center the image on canvas
                    canvas_center_x = canvas_width // 2
                    canvas_center_y = canvas_height // 2
                    self.preview_canvas.create_image(canvas_center_x, canvas_center_y, image=self.preview_photo)
=======
                    # Display on canvas (updated center position for larger canvas)
                    self.preview_canvas.create_image(480, 180, image=self.preview_photo)
>>>>>>> 3ce32e7292c4137fc36611774305c6d1f5710292
                    
                    # Add overlay text at top
                    cam0_status = "✓" if self.cam0_connected else "✗"
                    cam1_status = "✓" if self.cam1_connected else "✗"
                    overlay_text = f"Cam0: {cam0_status}  Cam1: {cam1_status}"
<<<<<<< HEAD
                    self.preview_canvas.create_text(canvas_center_x, 15, text=overlay_text, fill="yellow", font=('Arial', 12, 'bold'))
                    
                    # Add dimension info at bottom
                    img_height, img_width = combined_image.shape[:2]
                    dim_text = f"Preview: {img_width}×{img_height} (Scaled from cropped)"
                    self.preview_canvas.create_text(canvas_center_x, canvas_height - 15, text=dim_text, fill="cyan", font=('Arial', 10))
=======
                    self.preview_canvas.create_text(480, 15, text=overlay_text, fill="yellow", font=('Arial', 12, 'bold'))
>>>>>>> 3ce32e7292c4137fc36611774305c6d1f5710292
                    
        except Exception as e:
            self.log_message(f"❌ Preview display error: {e}")
            self._update_preview_error()

    def _update_preview_disconnected(self):
        """Show disconnected status in preview"""
        try:
            self.preview_canvas.delete("all")
<<<<<<< HEAD
            canvas_width = self.preview_canvas.winfo_width() or 800
            canvas_height = self.preview_canvas.winfo_height() or int(800 * 2592 / 4090)
            center_x = canvas_width // 2
            center_y = canvas_height // 2
            
            self.preview_canvas.create_text(center_x, center_y, text="No Camera Data", fill="red", font=('Arial', 16))
            self.preview_canvas.create_text(center_x, center_y + 20, text="Check camera connections", fill="white", font=('Arial', 12))
=======
            self.preview_canvas.create_text(480, 180, text="No Camera Data", fill="red", font=('Arial', 16))
            self.preview_canvas.create_text(480, 200, text="Check camera connections", fill="white", font=('Arial', 12))
>>>>>>> 3ce32e7292c4137fc36611774305c6d1f5710292
        except:
            pass

    def _update_preview_error(self):
        """Show error status in preview"""
        try:
            self.preview_canvas.delete("all")
<<<<<<< HEAD
            canvas_width = self.preview_canvas.winfo_width() or 800
            canvas_height = self.preview_canvas.winfo_height() or int(800 * 2592 / 4090)
            center_x = canvas_width // 2
            center_y = canvas_height // 2
            
            self.preview_canvas.create_text(center_x, center_y, text="Preview Error", fill="red", font=('Arial', 16))
            self.preview_canvas.create_text(center_x, center_y + 20, text="Check log for details", fill="white", font=('Arial', 12))
=======
            self.preview_canvas.create_text(480, 180, text="Preview Error", fill="red", font=('Arial', 16))
            self.preview_canvas.create_text(480, 200, text="Check log for details", fill="white", font=('Arial', 12))
>>>>>>> 3ce32e7292c4137fc36611774305c6d1f5710292
        except:
            pass

    def capture_single_frame(self):
        """Capture and display a single frame in preview"""
        if not (self.cam0_connected or self.cam1_connected):
            self.log_message("❌ No cameras connected!")
            return
            
        self.log_message("📷 Capturing single frame for preview...")
        
        try:
            frame0 = None
            frame1 = None
            
            if self.cam0_connected and self.cam0:
                frame0 = self.safe_camera_operation(lambda cam: cam.capture_array(), self.cam0)
                
            if self.cam1_connected and self.cam1:
                frame1 = self.safe_camera_operation(lambda cam: cam.capture_array(), self.cam1)
            
            if frame0 is not None or frame1 is not None:
                self._update_preview_display(frame0, frame1)
                self.log_message("✓ Single frame displayed in preview")
            else:
                self.log_message("❌ Failed to capture single frame")
                self._update_preview_error()
                
        except Exception as e:
            self.log_message(f"❌ Single frame capture error: {e}")

    def on_fps_change(self, event=None):
        """Handle FPS change"""
        try:
            fps = float(self.fps_var.get())
            self.log_message(f"Preview FPS changed to {fps}")
        except:
            self.fps_var.set("2")  # Reset to default

    def test_capture(self):
        """Test single image capture without saving"""
        if not self.cam0_connected and not self.cam1_connected:
            self.log_message("❌ No cameras connected!")
            return
            
        self.log_message("🧪 Testing capture...")
        
        try:
            if self.cam0_connected:
                req0 = self.safe_camera_operation(lambda cam: cam.capture_request(), self.cam0)
                if req0:
                    array = req0.make_array("main")
                    self.log_message(f"✓ Cam0: {array.shape}, dtype: {array.dtype}, range: [{array.min()}-{array.max()}]")
                    req0.release()
                else:
                    self.log_message("✗ Cam0 capture failed")
                    
            if self.cam1_connected:
                req1 = self.safe_camera_operation(lambda cam: cam.capture_request(), self.cam1)
                if req1:
                    array = req1.make_array("main")
                    self.log_message(f"✓ Cam1: {array.shape}, dtype: {array.dtype}, range: [{array.min()}-{array.max()}]")
                    req1.release()
                else:
                    self.log_message("✗ Cam1 capture failed")
                    
            self.log_message("🧪 Test capture completed")
            
        except Exception as e:
            self.log_message(f"❌ Test capture error: {e}")

    def safe_save_image(self):
        """Save images with maximum safety"""
        if not self.cam0_connected and not self.cam1_connected:
            self.log_message("❌ No cameras connected!")
            messagebox.showerror("Error", "No cameras connected!")
            return
            
        if self.operation_in_progress:
            self.log_message("⚠️  Another operation in progress, please wait...")
            return
            
        self.log_message("💾 Starting safe image capture and save...")
        
        # Run in background thread to prevent GUI blocking
        threading.Thread(target=self._save_image_worker, daemon=True).start()

    def _save_image_worker(self):
        """Worker thread for image saving"""
        try:
            self.operation_in_progress = True
            
            # Update processing settings from GUI before saving
            self.get_current_processing_settings()
            
            # Create folder structure
            base_folder = "RPI_Captures"
            date_folder = datetime.now().strftime("%Y-%m-%d")
            save_folder = os.path.join(base_folder, date_folder)
            
            # Ensure folders exist
            if not os.path.exists(save_folder):
                os.makedirs(save_folder, exist_ok=True)
                self.log_message(f"📁 Created folder: {save_folder}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            params_str = "_".join(f"{p}{v['value']:.2f}" for p, v in self.params.items())

            # Capture from available cameras
            req0 = None
            req1 = None
            
            if self.cam0_connected:
                self.log_message("📸 Capturing from Camera 0...")
                req0 = self.cam0.capture_request()
                if req0:
                    self.log_message("✓ Camera 0 captured successfully")
                else:
                    self.log_message("✗ Camera 0 capture failed")
                    
            if self.cam1_connected:
                self.log_message("📸 Capturing from Camera 1...")
                req1 = self.cam1.capture_request()
                if req1:
                    self.log_message("✓ Camera 1 captured successfully")
                else:
                    self.log_message("✗ Camera 1 capture failed")

            success_count = 0

            # Save DNG files if enabled
            if self.save_dng_var.get():
                self.log_message("💾 Saving DNG files...")
                try:
                    if req0:
                        dng_filename0 = f"cam0_{timestamp}_original_{params_str}.dng"
                        dng_path0 = os.path.join(save_folder, dng_filename0)
                        req0.save_dng(dng_path0)
                        self.log_message(f"✓ Saved: {dng_path0}")
                        success_count += 1
                        
                    if req1:
                        dng_filename1 = f"cam1_{timestamp}_original_{params_str}.dng"
                        dng_path1 = os.path.join(save_folder, dng_filename1)
                        req1.save_dng(dng_path1)
                        self.log_message(f"✓ Saved: {dng_path1}")
                        success_count += 1
                        
                except Exception as e:
                    self.log_message(f"❌ DNG save error: {e}")

            # Create processed TIFF if enabled
            if self.save_tiff_var.get():
                self.log_message("🔄 Processing images for TIFF...")
                try:
                    img0 = req0.make_array("main") if req0 else None
                    img1 = req1.make_array("main") if req1 else None
                    
                    if img0 is not None or img1 is not None:
                        # Process images
                        self.log_message("🔄 Applying image processing pipeline...")
                        img0_final = self.process_image(img0, 'cam0') if img0 is not None else None
                        img1_final = self.process_image(img1, 'cam1') if img1 is not None else None
                        
                        # Create combined image
                        self.log_message("🔄 Creating combined image...")
                        combined = self.create_combined_image(img0_final, img1_final)
                        
                        if combined is not None:
                            tiff_filename = f"dual_{timestamp}_processed_{params_str}.tiff"
                            tiff_path = os.path.join(save_folder, tiff_filename)
                            if self.save_processed_image_tiff(combined, tiff_path):
                                self.log_message(f"✓ Saved: {tiff_path}")
                                success_count += 1
                            else:
                                self.log_message("❌ TIFF save failed")
                        else:
                            self.log_message("❌ Failed to create combined image")
                    else:
                        self.log_message("❌ No image data available for TIFF")
                        
                except Exception as e:
                    self.log_message(f"❌ TIFF processing error: {e}")
                    import traceback
                    self.log_message(f"Full error: {traceback.format_exc()}")

            self.log_message(f"🎉 Save operation complete! {success_count} files saved.")
            if success_count > 0:
                self.log_message(f"Files saved in: {save_folder}")

        except Exception as e:
            self.log_message(f"❌ Save operation error: {e}")
            import traceback
            self.log_message(f"Full error: {traceback.format_exc()}")
        
        finally:
            self.operation_in_progress = False
            # Always release requests
            try:
                if req0:
                    req0.release()
                if req1:
                    req1.release()
            except:
                pass

    def process_image(self, image, cam_name):
        """Process a single image through the pipeline"""
        if image is None:
            return None
            
        try:
            original_shape = image.shape
            self.log_message(f"🔄 Processing {cam_name}: {original_shape}")
            
            # Apply cropping
            if self.apply_cropping:
                image = self.crop_image(image, cam_name)
                self.log_message(f"  ✓ Cropped: {original_shape} -> {image.shape}")
                
            # Apply distortion correction
            if self.enable_distortion_correction:
                image = self.apply_distortion_correction(image, cam_name)
                self.log_message(f"  ✓ Distortion corrected")
                
            # Apply perspective correction
            if self.enable_perspective_correction:
                image = self.apply_perspective_correction(image, cam_name)
                self.log_message(f"  ✓ Perspective corrected")
                
            # Apply rotation
            if cam_name == 'cam0' and self.apply_left_rotation:
                image = self.rotate_left_image(image)
                self.log_message(f"  ✓ Left rotation applied")
            elif cam_name == 'cam1' and self.apply_right_rotation:
                image = self.rotate_right_image(image)
                self.log_message(f"  ✓ Right rotation applied")
                
            return image
            
        except Exception as e:
            self.log_message(f"❌ Processing error for {cam_name}: {e}")
            return image

    def safe_reconnect_cameras(self):
        """Safely reconnect cameras"""
        self.log_message("🔌 Reconnecting cameras...")
        
        # Stop existing cameras safely
        self.safe_stop_cameras()
        
        # Wait a moment
        time.sleep(2)
        
        # Reinitialize in background thread
        threading.Thread(target=self.initialize_cameras, daemon=True).start()

    def safe_stop_cameras(self):
        """Safely stop all cameras"""
        try:
            if self.cam0:
                try:
                    self.cam0.stop()
                    self.log_message("Camera 0 stopped")
                except:
                    pass
                    
            if self.cam1:
                try:
                    self.cam1.stop()
                    self.log_message("Camera 1 stopped")
                except:
                    pass
                    
        except Exception as e:
            self.log_message(f"Error stopping cameras: {e}")
        
        finally:
            self.cam0 = None
            self.cam1 = None
            self.cam0_connected = False
            self.cam1_connected = False

    def on_closing(self):
        """Handle window closing safely"""
        self.shutdown_requested = True
        self.stop_preview()  # Stop preview first
        self.log_message("Shutting down safely...")
        self.cleanup()
        self.root.destroy()

    def cleanup(self):
        """Clean up resources safely"""
        self.log_message("Cleaning up resources...")
        self.stop_preview()  # Ensure preview is stopped
        self.save_settings()
        self.safe_stop_cameras()

    def run(self):
        """Run the GUI"""
        try:
            self.log_message("Starting ultra-safe GUI main loop...")
            self.root.mainloop()
        except KeyboardInterrupt:
            self.log_message("Interrupted by user")
        finally:
            self.cleanup()

    # Include all the processing methods from the original
    def crop_image(self, image, cam_name):
        """Crop image according to camera-specific parameters"""
        if not self.apply_cropping:
            return image
            
        params = self.crop_params[cam_name]
        start_x = params['start_x']
        width = params['width']
        height = params['height']
        
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
            original_dtype = image.dtype
            original_height, original_width = image.shape[:2]
            
            if cam_name == 'cam0':
                top_padding = self.left_top_padding
                bottom_padding = self.left_bottom_padding
            else:
                top_padding = self.right_top_padding
                bottom_padding = self.right_bottom_padding
            
            new_height = original_height + top_padding + bottom_padding
            new_width = original_width
            
            offset_y = top_padding
            new_xcenter = xcenter
            new_ycenter = ycenter + offset_y
            
            image_float = image.astype(np.float64)
            
            if image_float.ndim == 2:
                padded_image = np.zeros((new_height, new_width), dtype=np.float64)
                padded_image[offset_y:offset_y + original_height, :] = image_float
                corrected = post.unwarp_image_backward(padded_image, new_xcenter, new_ycenter, coeffs)
            else:
                padded_image = np.zeros((new_height, new_width, image_float.shape[2]), dtype=np.float64)
                padded_image[offset_y:offset_y + original_height, :, :] = image_float
                
                corrected = np.zeros_like(padded_image)
                for c in range(image_float.shape[2]):
                    corrected[:, :, c] = post.unwarp_image_backward(padded_image[:, :, c], new_xcenter, new_ycenter, coeffs)
            
            corrected = np.nan_to_num(corrected, nan=0.0)
            corrected = np.clip(corrected, 0, image.max())
            
            if original_dtype == np.uint8:
                corrected = np.clip(corrected, 0, 255).astype(np.uint8)
            elif original_dtype == np.uint16:
                corrected = np.clip(corrected, 0, 65535).astype(np.uint16)
            else:
                corrected = corrected.astype(original_dtype)
            
            return corrected
            
        except Exception as e:
            self.log_message(f"Distortion correction failed for {cam_name}: {e}")
            return image

    def apply_perspective_correction(self, image, cam_name):
        """Apply perspective correction if coefficients are available"""
        if not self.enable_perspective_correction or cam_name not in self.distortion_params:
            return image
            
        params = self.distortion_params[cam_name]
        pers_coef = params.get('pers_coef')
        
        if pers_coef is None:
            return image
        
        try:
            original_dtype = image.dtype
            image_float = image.astype(np.float64)
            
            if image_float.ndim == 2:
                corrected = post.correct_perspective_image(image_float, pers_coef)
            else:
                corrected = np.zeros_like(image_float)
                for c in range(image_float.shape[2]):
                    corrected[:, :, c] = post.correct_perspective_image(image_float[:, :, c], pers_coef)
            
            corrected = np.nan_to_num(corrected, nan=0.0)
            corrected = np.clip(corrected, 0, image.max())
            
            if original_dtype == np.uint8:
                corrected = np.clip(corrected, 0, 255).astype(np.uint8)
            elif original_dtype == np.uint16:
                corrected = np.clip(corrected, 0, 65535).astype(np.uint16)
            else:
                corrected = corrected.astype(original_dtype)
            
            return corrected
            
        except Exception as e:
            self.log_message(f"Perspective correction failed for {cam_name}: {e}")
            return image

    def rotate_left_image(self, image):
        """Rotate the left image by the specified angle"""
        if not self.apply_left_rotation:
            return image
            
        try:
            import cv2
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, self.left_rotation_angle, 1.0)
            
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                   flags=cv2.INTER_LINEAR, 
                                   borderMode=cv2.BORDER_REFLECT_101)
            return rotated
            
        except Exception as e:
            self.log_message(f"Left image rotation failed: {e}")
            return image

    def rotate_right_image(self, image):
        """Rotate the right image by the specified angle"""
        if not self.apply_right_rotation:
            return image
            
        try:
            import cv2
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, self.right_rotation_angle, 1.0)
            
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                   flags=cv2.INTER_LINEAR, 
                                   borderMode=cv2.BORDER_REFLECT_101)
            return rotated
            
        except Exception as e:
            self.log_message(f"Right image rotation failed: {e}")
            return image

    def create_combined_image(self, left_image, right_image):
        """Create a side-by-side combined image"""
        try:
            if left_image is None and right_image is None:
                return None
            elif left_image is None:
                return right_image
            elif right_image is None:
                return left_image
            else:
                min_height = min(left_image.shape[0], right_image.shape[0])
                left_resized = left_image[:min_height, :]
                right_resized = right_image[:min_height, :]
                
                combined = np.hstack((left_resized, right_resized))
                return combined
        except Exception as e:
            self.log_message(f"Failed to create combined image: {e}")
            return None

    def save_processed_image_tiff(self, image, output_path):
        """Save processed image as TIFF"""
        try:
            if image is None or image.size == 0:
                return False
            
            imageio.imsave(output_path, image)
            return True
            
        except Exception as e:
            self.log_message(f"Failed to save TIFF {output_path}: {e}")
            return False

    def apply_settings(self):
        """Apply camera settings safely"""
        settings = {
            "ExposureTime": int(self.params['ExposureTime']['value']),
            "AnalogueGain": self.params['AnalogueGain']['value'],
            "Brightness": self.params['Brightness']['value'],
            "Contrast": self.params['Contrast']['value'],
            "Saturation": self.params['Saturation']['value'],
            "Sharpness": self.params['Sharpness']['value']
        }
        
        try:
            if self.cam0_connected and self.cam0:
                self.safe_camera_operation(lambda cam: cam.set_controls(settings), self.cam0)
        except Exception as e:
            self.log_message(f"Failed to apply settings to camera 0: {e}")
            
        try:
            if self.cam1_connected and self.cam1:
                self.safe_camera_operation(lambda cam: cam.set_controls(settings), self.cam1)
        except Exception as e:
            self.log_message(f"Failed to apply settings to camera 1: {e}")

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
        """Save both camera parameters and processing settings"""
        # Camera parameters
        camera_settings = {param: self.params[param]['value'] for param in self.params}
        
        # Get current processing settings from GUI
        self.get_current_processing_settings()
        
        # Processing settings
        processing_settings = {
            'apply_cropping': self.apply_cropping,
            'enable_distortion_correction': self.enable_distortion_correction,
            'enable_perspective_correction': self.enable_perspective_correction,
            'apply_left_rotation': self.apply_left_rotation,
            'apply_right_rotation': self.apply_right_rotation,
            'left_rotation_angle': self.left_rotation_angle,
            'right_rotation_angle': self.right_rotation_angle,
            'left_top_padding': self.left_top_padding,
            'left_bottom_padding': self.left_bottom_padding,
            'right_top_padding': self.right_top_padding,
            'right_bottom_padding': self.right_bottom_padding,
            'crop_params': self.crop_params
        }
        
        # Combined settings
        all_settings = {
            'camera_parameters': camera_settings,
            'processing_settings': processing_settings
        }
        
        try:
            with open('camera_settings.json', 'w') as f:
                json.dump(all_settings, f, indent=4)
            self.log_message("Camera parameters and processing settings saved successfully")
        except Exception as e:
            self.log_message(f"Failed to save settings: {e}")

    def load_settings(self):
        """Load both camera parameters and processing settings"""
        try:
            if os.path.exists('camera_settings.json'):
                with open('camera_settings.json', 'r') as f:
                    all_settings = json.load(f)
                
                # Load camera parameters (backward compatibility)
                if 'camera_parameters' in all_settings:
                    settings = all_settings['camera_parameters']
                else:
                    # Old format - direct parameters
                    settings = all_settings
                
                for param, value in settings.items():
                    if param in self.params:
                        self.params[param]['value'] = value
                        if hasattr(self, 'scales') and param in self.scales:
                            self.scales[param].set(value)
                        if hasattr(self, 'entries') and param in self.entries:
                            self.entries[param].delete(0, tk.END)
                            self.entries[param].insert(0, f"{value:.2f}")
                
                # Load processing settings
                if 'processing_settings' in all_settings:
                    proc_settings = all_settings['processing_settings']
                    
                    self.apply_cropping = proc_settings.get('apply_cropping', self.processing_defaults['apply_cropping'])
                    self.enable_distortion_correction = proc_settings.get('enable_distortion_correction', self.processing_defaults['enable_distortion_correction'])
                    self.enable_perspective_correction = proc_settings.get('enable_perspective_correction', self.processing_defaults['enable_perspective_correction'])
                    self.apply_left_rotation = proc_settings.get('apply_left_rotation', self.processing_defaults['apply_left_rotation'])
                    self.apply_right_rotation = proc_settings.get('apply_right_rotation', self.processing_defaults['apply_right_rotation'])
                    self.left_rotation_angle = proc_settings.get('left_rotation_angle', self.processing_defaults['left_rotation_angle'])
                    self.right_rotation_angle = proc_settings.get('right_rotation_angle', self.processing_defaults['right_rotation_angle'])
                    self.left_top_padding = proc_settings.get('left_top_padding', self.processing_defaults['left_top_padding'])
                    self.left_bottom_padding = proc_settings.get('left_bottom_padding', self.processing_defaults['left_bottom_padding'])
                    self.right_top_padding = proc_settings.get('right_top_padding', self.processing_defaults['right_top_padding'])
                    self.right_bottom_padding = proc_settings.get('right_bottom_padding', self.processing_defaults['right_bottom_padding'])
                    
                    # Load crop parameters
                    if 'crop_params' in proc_settings:
                        self.crop_params = proc_settings['crop_params']
                    
                    # Update GUI elements if they exist
                    if hasattr(self, 'cropping_var'):
                        self.cropping_var.set(self.apply_cropping)
                    if hasattr(self, 'distortion_var'):
                        self.distortion_var.set(self.enable_distortion_correction)
                    if hasattr(self, 'perspective_var'):
                        self.perspective_var.set(self.enable_perspective_correction)
                    if hasattr(self, 'left_rotation_var'):
                        self.left_rotation_var.set(self.apply_left_rotation)
                    if hasattr(self, 'right_rotation_var'):
                        self.right_rotation_var.set(self.apply_right_rotation)
                    if hasattr(self, 'left_angle_var'):
                        self.left_angle_var.set(self.left_rotation_angle)
                    if hasattr(self, 'right_angle_var'):
                        self.right_angle_var.set(self.right_rotation_angle)
                    if hasattr(self, 'left_top_padding_var'):
                        self.left_top_padding_var.set(self.left_top_padding)
                    if hasattr(self, 'left_bottom_padding_var'):
                        self.left_bottom_padding_var.set(self.left_bottom_padding)
                    if hasattr(self, 'right_top_padding_var'):
                        self.right_top_padding_var.set(self.right_top_padding)
                    if hasattr(self, 'right_bottom_padding_var'):
                        self.right_bottom_padding_var.set(self.right_bottom_padding)
                    
                    # Update crop parameter GUI elements
                    if hasattr(self, 'left_width_var'):
                        self.left_width_var.set(self.crop_params['cam0']['width'])
                        self.left_start_x_var.set(self.crop_params['cam0']['start_x'])
                        self.left_height_var.set(self.crop_params['cam0']['height'])
                        self.right_width_var.set(self.crop_params['cam1']['width'])
                        self.right_start_x_var.set(self.crop_params['cam1']['start_x'])
                        self.right_height_var.set(self.crop_params['cam1']['height'])
                
                self.log_message("Loaded previous camera parameters and processing settings")
        except Exception as e:
            self.log_message(f"Failed to load settings: {e}")

    def load_distortion_coefficients(self, filepath=None):
        """Load distortion correction coefficients"""
        if filepath is None:
            dual_coeff_file = 'distortion_coefficients_dual.json'
        else:
            dual_coeff_file = filepath
            
        if os.path.exists(dual_coeff_file):
            try:
                with open(dual_coeff_file, 'r') as f:
                    saved_params = json.load(f)
                    
                for cam in ['cam0', 'cam1']:
                    if cam in saved_params:
                        if cam not in self.distortion_params:
                            self.distortion_params[cam] = {}
                        
                        for key in ['xcenter', 'ycenter', 'coeffs', 'pers_coef']:
                            if key in saved_params[cam]:
                                self.distortion_params[cam][key] = saved_params[cam][key]
                
                self.log_message(f"Loaded coefficients from {os.path.basename(dual_coeff_file)}")
                return True
            except Exception as e:
                self.log_message(f"Failed to load coefficients: {e}")
                return False
        else:
            if filepath is None:
                self.log_message("Using built-in default coefficients")
            else:
                self.log_message(f"Coefficients file not found: {dual_coeff_file}")
            return False

    def load_coefficients_dialog(self):
        """Load distortion coefficients from file dialog"""
        from tkinter import filedialog
        
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
            self.log_message(f"✓ Loaded coefficients from {os.path.basename(coeff_file)}")
            messagebox.showinfo("Success", f"Distortion coefficients loaded successfully from:\n{os.path.basename(coeff_file)}")
        else:
            self.log_message(f"✗ Failed to load coefficients from {os.path.basename(coeff_file)}")
            messagebox.showerror("Error", f"Failed to load coefficients from:\n{os.path.basename(coeff_file)}\n\nCheck log for details.")

    def show_processing_info(self):
        """Show detailed processing information in a dialog"""
        # Update current settings from GUI
        self.get_current_processing_settings()
        
        # Create info window
        info_window = tk.Toplevel(self.root)
        info_window.title("Processing Information & Coefficients")
        info_window.geometry("800x600")
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(info_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        info_text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 9))
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=info_text.yview)
        info_text.configure(yscrollcommand=scrollbar.set)
        
        info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Generate processing info
        info_content = self.generate_processing_info()
        info_text.insert(tk.END, info_content)
        info_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(info_window, text="Close", command=info_window.destroy).pack(pady=10)

    def generate_processing_info(self):
        """Generate detailed processing information text"""
        info = []
        
        info.append("=== PROCESSING PIPELINE STATUS ===\n")
        info.append(f"✓ Cropping: {'Enabled' if self.apply_cropping else 'Disabled'}\n")
        info.append(f"✓ Radial Distortion Correction: {'Enabled' if self.enable_distortion_correction else 'Disabled'}\n")
        info.append(f"✓ Perspective Correction: {'Enabled' if self.enable_perspective_correction else 'Disabled'}\n")
        info.append(f"✓ Left Image Rotation: {'Enabled' if self.apply_left_rotation else 'Disabled'}\n")
        info.append(f"✓ Right Image Rotation: {'Enabled' if self.apply_right_rotation else 'Disabled'}\n")
        info.append("\n")
        
        info.append("=== ROTATION PARAMETERS ===\n")
        info.append(f"Left Image (cam0): {self.left_rotation_angle}°\n")
        info.append(f"Right Image (cam1): {self.right_rotation_angle}°\n")
        info.append("\n")
        
        info.append("=== DISTORTION PADDING ===\n")
        info.append(f"Left Camera (cam0): {self.left_top_padding} top, {self.left_bottom_padding} bottom\n")
        info.append(f"Right Camera (cam1): {self.right_top_padding} top, {self.right_bottom_padding} bottom\n")
        info.append("(Higher values preserve more content but may add artifacts)\n")
        info.append("\n")
        
        info.append("=== CROP PARAMETERS ===\n")
        for cam, params in self.crop_params.items():
            cam_label = "Left" if cam == "cam0" else "Right"
            info.append(f"{cam} ({cam_label}):\n")
            info.append(f"  Width: {params['width']} pixels\n")
            info.append(f"  Start X: {params['start_x']} pixels\n")
            info.append(f"  Height: {params['height']} pixels\n")
            info.append(f"  Region: {params['width']}x{params['height']} @ ({params['start_x']},0)\n")
            info.append("\n")
        
        info.append("=== RADIAL DISTORTION PARAMETERS ===\n")
        for cam, params in self.distortion_params.items():
            cam_label = "Left" if cam == "cam0" else "Right"
            info.append(f"{cam} ({cam_label}):\n")
            info.append(f"  Center: ({params['xcenter']:.3f}, {params['ycenter']:.3f})\n")
            info.append(f"  Radial Coefficients:\n")
            for i, coeff in enumerate(params['coeffs']):
                info.append(f"    k{i+1}: {coeff:.8e}\n")
            info.append("\n")
        
        info.append("=== PERSPECTIVE CORRECTION PARAMETERS ===\n")
        for cam, params in self.distortion_params.items():
            cam_label = "Left" if cam == "cam0" else "Right"
            pers_coef = params.get('pers_coef')
            info.append(f"{cam} ({cam_label}):\n")
            
            if pers_coef is not None:
                info.append(f"  Status: Available\n")
                info.append(f"  Perspective Coefficients:\n")
                labels = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8']
                for i, coeff in enumerate(pers_coef):
                    if i < len(labels):
                        info.append(f"    {labels[i]}: {coeff:.8e}\n")
            else:
                info.append(f"  Status: Not available\n")
                info.append(f"  Note: Load coefficients file with perspective data\n")
            info.append("\n")
        
        info.append("=== PROCESSING PIPELINE ===\n")
        pipeline_steps = []
        if self.apply_cropping:
            pipeline_steps.append("1. Crop image to specified region")
        if self.enable_distortion_correction:
            pipeline_steps.append("2. Apply radial distortion correction with padding")
        if self.enable_perspective_correction:
            pipeline_steps.append("3. Apply perspective correction")
        if self.apply_left_rotation or self.apply_right_rotation:
            pipeline_steps.append("4. Apply rotation (if enabled for camera)")
        
        if pipeline_steps:
            for step in pipeline_steps:
                info.append(f"{step}\n")
        else:
            info.append("No processing steps enabled\n")
        
        return "".join(info)

    def update_cropping_setting(self):
        """Update cropping setting"""
        self.apply_cropping = self.cropping_var.get()
        self.log_message(f"Cropping {'enabled' if self.apply_cropping else 'disabled'}")

    def update_distortion_setting(self):
        """Update distortion correction setting"""
        self.enable_distortion_correction = self.distortion_var.get()
        self.log_message(f"Distortion correction {'enabled' if self.enable_distortion_correction else 'disabled'}")

    def update_perspective_setting(self):
        """Update perspective correction setting"""
        self.enable_perspective_correction = self.perspective_var.get()
        self.log_message(f"Perspective correction {'enabled' if self.enable_perspective_correction else 'disabled'}")

    def update_left_rotation_setting(self):
        """Update left rotation setting"""
        self.apply_left_rotation = self.left_rotation_var.get()
        self.log_message(f"Left image rotation {'enabled' if self.apply_left_rotation else 'disabled'}")

    def update_right_rotation_setting(self):
        """Update right rotation setting"""
        self.apply_right_rotation = self.right_rotation_var.get()
        self.log_message(f"Right image rotation {'enabled' if self.apply_right_rotation else 'disabled'}")

    def get_current_processing_settings(self):
        """Get current processing settings from GUI"""
        # Update rotation angles from GUI
        if hasattr(self, 'left_angle_var'):
            self.left_rotation_angle = self.left_angle_var.get()
        if hasattr(self, 'right_angle_var'):
            self.right_rotation_angle = self.right_angle_var.get()
        
        # Update padding from GUI
        if hasattr(self, 'left_top_padding_var'):
            self.left_top_padding = self.left_top_padding_var.get()
        if hasattr(self, 'left_bottom_padding_var'):
            self.left_bottom_padding = self.left_bottom_padding_var.get()
        if hasattr(self, 'right_top_padding_var'):
            self.right_top_padding = self.right_top_padding_var.get()
        if hasattr(self, 'right_bottom_padding_var'):
            self.right_bottom_padding = self.right_bottom_padding_var.get()
        
        # Update crop parameters from GUI
        if hasattr(self, 'left_width_var'):
            self.crop_params['cam0']['width'] = self.left_width_var.get()
            self.crop_params['cam0']['start_x'] = self.left_start_x_var.get()
            self.crop_params['cam0']['height'] = self.left_height_var.get()
            self.crop_params['cam1']['width'] = self.right_width_var.get()
            self.crop_params['cam1']['start_x'] = self.right_start_x_var.get()
            self.crop_params['cam1']['height'] = self.right_height_var.get()


def main():
    """Main entry point"""
    try:
        print("Initializing Safe Dual IMX708 Camera Control with Preview...")
        
        # Check GUI support
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            print(f"Error: GUI not supported: {e}")
            return 1
        
        viewer = UltraSafeIMX708Viewer()
        viewer.run()
        return 0
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())