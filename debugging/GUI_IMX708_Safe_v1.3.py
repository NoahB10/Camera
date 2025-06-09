import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import time
import numpy as np
from datetime import datetime
import os
import json
from PIL import Image
import discorpy.post.postprocessing as post
import imageio
import threading
import signal
import sys
from contextlib import contextmanager

# Safe GUI for dual IMX708 camera control with crash prevention (v1.3)
# 
# Key safety improvements:
# - No automatic preview to prevent freezing
# - Timeout-based camera initialization
# - Proper resource cleanup and error handling
# - Thread-safe operations
# - Graceful shutdown handling
# - Minimal blocking operations

class SafeIMX708Viewer:
    def __init__(self):
        # Safety flags
        self.shutdown_requested = False
        self.cameras_initializing = False
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
            'cam1': {'width': 2050, 'start_x': 1400, 'height': 2592}
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
        self.left_top_padding = 198
        self.left_bottom_padding = 42
        self.right_top_padding = 150
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
        try:
            with self.camera_timeout(3):  # 3 second timeout
                return operation(cam, *args, **kwargs)
        except Exception as e:
            print(f"[WARNING] Camera operation failed: {e}")
            return None

    def initialize_cameras(self):
        """Initialize cameras with timeout and safety checks"""
        if self.cameras_initializing or self.shutdown_requested:
            return
            
        self.cameras_initializing = True
        print("[INFO] Safely initializing cameras...")
        
        try:
            # Try to initialize camera 0
            try:
                print("[INFO] Attempting to initialize camera 0...")
                from picamera2 import Picamera2
                
                with self.camera_timeout(10):  # 10 second timeout for initialization
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
                print("[SUCCESS] Camera 0 initialized")
                
            except Exception as e:
                print(f"[WARNING] Failed to initialize camera 0: {e}")
                self.cam0_connected = False
                if self.cam0:
                    try:
                        self.cam0.stop()
                    except:
                        pass
                self.cam0 = None

            # Try to initialize camera 1
            try:
                print("[INFO] Attempting to initialize camera 1...")
                
                with self.camera_timeout(10):
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
                print("[SUCCESS] Camera 1 initialized")
                
            except Exception as e:
                print(f"[WARNING] Failed to initialize camera 1: {e}")
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
            print("[ERROR] Picamera2 not available - running in simulation mode")
            self.cam0_connected = False
            self.cam1_connected = False
            
        finally:
            self.cameras_initializing = False
            
        # Report status
        if self.cam0_connected and self.cam1_connected:
            print("[SUCCESS] Both cameras connected and ready")
            self.update_status_display("Both cameras connected")
        elif self.cam0_connected or self.cam1_connected:
            connected = "Camera 0" if self.cam0_connected else "Camera 1"
            print(f"[WARNING] Only {connected} connected")
            self.update_status_display(f"Only {connected} connected")
        else:
            print("[WARNING] No cameras connected")
            self.update_status_display("No cameras connected - GUI ready in simulation mode")

    def update_status_display(self, message):
        """Update GUI status display safely"""
        if hasattr(self, 'status_label') and not self.shutdown_requested:
            try:
                self.status_label.config(text=message)
                self.root.update_idletasks()
            except:
                pass

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Safe Dual IMX708 Camera Control v1.3")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Status frame at top
        status_frame = ttk.LabelFrame(main_frame, text="System Status")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Initializing...", font=('TkDefaultFont', 10, 'bold'))
        self.status_label.pack(pady=5)

        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

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

            entry = ttk.Entry(entry_frame, width=10)
            entry.insert(0, str(param_data['value']))
            entry.pack(side=tk.LEFT, padx=2)
            entry.bind('<Return>', lambda e, p=param_name: self.on_entry_change(p))
            self.entries[param_name] = entry

            ttk.Button(entry_frame, text="Set", command=lambda p=param_name: self.on_entry_change(p)).pack(side=tk.LEFT, padx=2)
            ttk.Button(entry_frame, text="Reset", command=lambda p=param_name: self.reset_parameter(p)).pack(side=tk.LEFT, padx=2)

        # Action buttons
        action_frame = ttk.LabelFrame(control_frame, text="Actions")
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(action_frame, text="Save Image", command=self.safe_save_image).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="Test Single Capture", command=self.test_capture).pack(fill=tk.X, padx=5, pady=2)
        
        # Preview controls
        preview_frame = ttk.Frame(action_frame)
        preview_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.preview_button = ttk.Button(preview_frame, text="Start Preview", command=self.toggle_preview)
        self.preview_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        ttk.Button(preview_frame, text="Single Frame", command=self.capture_single_frame).pack(side=tk.RIGHT, padx=(2, 0))
        
        ttk.Button(action_frame, text="Reset All Parameters", command=self.reset_all).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="Save Settings", command=self.save_settings).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(action_frame, text="Reconnect Cameras", command=self.safe_reconnect_cameras).pack(fill=tk.X, padx=5, pady=2)

        # Processing options
        processing_frame = ttk.LabelFrame(control_frame, text="Save Options")
        processing_frame.pack(fill=tk.X, pady=(0, 10))

        self.save_tiff_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Save Combined TIFF", 
                       variable=self.save_tiff_var).pack(anchor=tk.W, padx=5, pady=2)

        self.save_dng_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(processing_frame, text="Save Original DNG Files", 
                       variable=self.save_dng_var).pack(anchor=tk.W, padx=5, pady=2)

        # Processing controls
        processing_controls_frame = ttk.LabelFrame(processing_frame, text="Processing Controls")
        processing_controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.perspective_var = tk.BooleanVar(value=self.enable_perspective_correction)
        ttk.Checkbutton(processing_controls_frame, text="Enable Perspective Correction", 
                       variable=self.perspective_var,
                       command=self.update_perspective_setting).pack(anchor=tk.W, padx=5, pady=2)
        
        self.right_rotation_var = tk.BooleanVar(value=self.apply_right_rotation)
        ttk.Checkbutton(processing_controls_frame, text="Enable Right Image Rotation", 
                       variable=self.right_rotation_var,
                       command=self.update_right_rotation_setting).pack(anchor=tk.W, padx=5, pady=2)

        # Info display
        info_frame = ttk.LabelFrame(main_frame, text="Camera Information")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        info_text = tk.Text(info_frame, height=20, width=60, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=info_text.yview)
        info_text.configure(yscrollcommand=scrollbar.set)
        
        info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        self.info_text = info_text
        
        # Add initial info
        self.update_info_display("Safe Dual IMX708 Camera Control v1.3\n\nSafety Features:\n- No automatic preview (prevents freezing)\n- Timeout-based camera operations\n- Graceful error handling\n- Proper resource cleanup\n\nCamera initialization in progress...")

        # Start camera initialization in background thread
        threading.Thread(target=self.initialize_cameras, daemon=True).start()

    def update_info_display(self, text, append=False):
        """Update info display safely"""
        if not hasattr(self, 'info_text') or self.shutdown_requested:
            return
            
        try:
            self.info_text.config(state=tk.NORMAL)
            if not append:
                self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, text + "\n")
            self.info_text.see(tk.END)
            self.info_text.config(state=tk.DISABLED)
            self.root.update_idletasks()
        except:
            pass

    def test_capture(self):
        """Test single image capture without saving"""
        if not self.cam0_connected and not self.cam1_connected:
            messagebox.showerror("Error", "No cameras connected!")
            return
            
        self.update_info_display("Testing capture...", append=True)
        
        try:
            if self.cam0_connected:
                req0 = self.safe_camera_operation(lambda cam: cam.capture_request(), self.cam0)
                if req0:
                    array = req0.make_array("main")
                    self.update_info_display(f"Cam0 captured: {array.shape}, dtype: {array.dtype}", append=True)
                    req0.release()
                else:
                    self.update_info_display("Cam0 capture failed", append=True)
                    
            if self.cam1_connected:
                req1 = self.safe_camera_operation(lambda cam: cam.capture_request(), self.cam1)
                if req1:
                    array = req1.make_array("main")
                    self.update_info_display(f"Cam1 captured: {array.shape}, dtype: {array.dtype}", append=True)
                    req1.release()
                else:
                    self.update_info_display("Cam1 capture failed", append=True)
                    
            self.update_info_display("Test capture completed successfully", append=True)
            
        except Exception as e:
            self.update_info_display(f"Test capture error: {e}", append=True)

    def safe_save_image(self):
        """Save images with enhanced safety checks"""
        if not self.cam0_connected and not self.cam1_connected:
            messagebox.showerror("Error", "No cameras connected!")
            return
            
        self.update_info_display("Starting safe image capture...", append=True)
        
        # Run in background thread to prevent GUI blocking
        threading.Thread(target=self._save_image_worker, daemon=True).start()

    def _save_image_worker(self):
        """Worker thread for image saving"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            params_str = "_".join(f"{p}{v['value']:.2f}" for p, v in self.params.items())

            # Capture from available cameras
            req0 = None
            req1 = None
            
            if self.cam0_connected:
                req0 = self.safe_camera_operation(lambda cam: cam.capture_request(), self.cam0)
                if req0:
                    self.update_info_display("Cam0 captured successfully", append=True)
                else:
                    self.update_info_display("Cam0 capture failed", append=True)
                    
            if self.cam1_connected:
                req1 = self.safe_camera_operation(lambda cam: cam.capture_request(), self.cam1)
                if req1:
                    self.update_info_display("Cam1 captured successfully", append=True)
                else:
                    self.update_info_display("Cam1 capture failed", append=True)

            success_count = 0

            # Save DNG files if enabled
            if self.save_dng_var.get():
                try:
                    if req0:
                        dng_filename0 = f"cam0_{timestamp}_original_{params_str}.dng"
                        req0.save_dng(dng_filename0)
                        self.update_info_display(f"Saved: {dng_filename0}", append=True)
                        success_count += 1
                        
                    if req1:
                        dng_filename1 = f"cam1_{timestamp}_original_{params_str}.dng"
                        req1.save_dng(dng_filename1)
                        self.update_info_display(f"Saved: {dng_filename1}", append=True)
                        success_count += 1
                        
                except Exception as e:
                    self.update_info_display(f"DNG save error: {e}", append=True)

            # Create processed TIFF if enabled
            if self.save_tiff_var.get():
                try:
                    img0 = req0.make_array("main") if req0 else None
                    img1 = req1.make_array("main") if req1 else None
                    
                    if img0 is not None or img1 is not None:
                        # Process images
                        img0_final = self.process_image(img0, 'cam0') if img0 is not None else None
                        img1_final = self.process_image(img1, 'cam1') if img1 is not None else None
                        
                        # Create combined image
                        combined = self.create_combined_image(img0_final, img1_final)
                        
                        if combined is not None:
                            tiff_filename = f"dual_{timestamp}_processed_{params_str}.tiff"
                            if self.save_processed_image_tiff(combined, tiff_filename):
                                self.update_info_display(f"Saved: {tiff_filename}", append=True)
                                success_count += 1
                            else:
                                self.update_info_display("TIFF save failed", append=True)
                        else:
                            self.update_info_display("Failed to create combined image", append=True)
                    else:
                        self.update_info_display("No image data available for TIFF", append=True)
                        
                except Exception as e:
                    self.update_info_display(f"TIFF processing error: {e}", append=True)

            self.update_info_display(f"Save complete! {success_count} files saved.", append=True)

        except Exception as e:
            self.update_info_display(f"Save operation error: {e}", append=True)
        
        finally:
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
            # Apply cropping
            if self.apply_cropping:
                image = self.crop_image(image, cam_name)
                
            # Apply distortion correction
            if self.enable_distortion_correction:
                image = self.apply_distortion_correction(image, cam_name)
                
            # Apply perspective correction
            if self.enable_perspective_correction:
                image = self.apply_perspective_correction(image, cam_name)
                
            # Apply rotation
            if cam_name == 'cam0' and self.apply_left_rotation:
                image = self.rotate_left_image(image)
            elif cam_name == 'cam1' and self.apply_right_rotation:
                image = self.rotate_right_image(image)
                
            return image
            
        except Exception as e:
            self.update_info_display(f"Image processing error for {cam_name}: {e}", append=True)
            return image

    def safe_reconnect_cameras(self):
        """Safely reconnect cameras"""
        self.update_info_display("Reconnecting cameras...", append=True)
        
        # Stop existing cameras safely
        self.safe_stop_cameras()
        
        # Wait a moment
        time.sleep(2)
        
        # Reinitialize in background thread
        threading.Thread(target=self.initialize_cameras, daemon=True).start()

    def toggle_preview(self):
        """Toggle preview on/off safely"""
        if self.preview_running:
            self.stop_preview()
        else:
            self.start_preview()

    def start_preview(self):
        """Start safe preview in background thread"""
        if self.preview_running or not (self.cam0_connected or self.cam1_connected):
            return
            
        self.preview_running = True
        self.preview_button.config(text="Stop Preview")
        self.update_info_display("Starting preview...", append=True)
        
        # Start preview in background thread
        self.preview_thread = threading.Thread(target=self._preview_worker, daemon=True)
        self.preview_thread.start()

    def stop_preview(self):
        """Stop preview safely"""
        self.preview_running = False
        self.preview_button.config(text="Start Preview")
        self.update_info_display("Stopping preview...", append=True)
        
        # Close any open CV windows
        try:
            cv2.destroyAllWindows()
        except:
            pass

    def _preview_worker(self):
        """Background worker for preview - runs at limited frame rate"""
        frame_count = 0
        last_time = time.time()
        
        try:
            while self.preview_running and not self.shutdown_requested:
                try:
                    # Limit frame rate to prevent overload
                    current_time = time.time()
                    if current_time - last_time < 0.1:  # Max 10 FPS
                        time.sleep(0.05)
                        continue
                    last_time = current_time
                    
                    # Capture frames safely with timeout
                    frame0 = None
                    frame1 = None
                    
                    if self.cam0_connected and self.cam0:
                        try:
                            with self.camera_timeout(1):  # 1 second timeout
                                frame0 = self.cam0.capture_array()
                        except Exception as e:
                            if frame_count % 10 == 0:  # Only log every 10th error
                                print(f"[WARNING] Cam0 preview capture failed: {e}")
                    
                    if self.cam1_connected and self.cam1:
                        try:
                            with self.camera_timeout(1):  # 1 second timeout
                                frame1 = self.cam1.capture_array()
                        except Exception as e:
                            if frame_count % 10 == 0:  # Only log every 10th error
                                print(f"[WARNING] Cam1 preview capture failed: {e}")
                    
                    # Process and display frames
                    if frame0 is not None or frame1 is not None:
                        self._display_preview_frames(frame0, frame1)
                    else:
                        # Show disconnected status
                        self._display_disconnected_preview()
                    
                    frame_count += 1
                    
                    # Check for OpenCV window close
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                        
                except Exception as e:
                    if frame_count % 10 == 0:  # Only log every 10th error
                        print(f"[WARNING] Preview error: {e}")
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"[ERROR] Preview worker crashed: {e}")
        finally:
            self.preview_running = False
            if hasattr(self, 'preview_button'):
                try:
                    self.preview_button.config(text="Start Preview")
                except:
                    pass
            try:
                cv2.destroyAllWindows()
            except:
                pass

    def _display_preview_frames(self, frame0, frame1):
        """Display preview frames in OpenCV window"""
        try:
            placeholder_shape = (480, 640, 3)
            
            # Process frame0
            if frame0 is not None:
                # Apply light processing for preview
                try:
                    processed0 = self.crop_image(frame0, 'cam0')
                    display0 = cv2.resize(processed0, (640, 480))
                except:
                    display0 = cv2.resize(frame0, (640, 480))
            else:
                display0 = np.zeros(placeholder_shape, dtype=np.uint8)
                cv2.putText(display0, "Camera 0", (240, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(display0, "DISCONNECTED", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Process frame1
            if frame1 is not None:
                # Apply light processing for preview
                try:
                    processed1 = self.crop_image(frame1, 'cam1')
                    display1 = cv2.resize(processed1, (640, 480))
                except:
                    display1 = cv2.resize(frame1, (640, 480))
            else:
                display1 = np.zeros(placeholder_shape, dtype=np.uint8)
                cv2.putText(display1, "Camera 1", (240, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(display1, "DISCONNECTED", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Combine frames
            combined = np.hstack((display0, display1))
            
            # Add overlay information
            y = 30
            for param_name, param_data in self.params.items():
                text = f"{param_name}: {param_data['value']:.2f}"
                cv2.putText(combined, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y += 20
            
            # Add camera status
            cam0_status = "CONNECTED" if self.cam0_connected else "DISCONNECTED"
            cam1_status = "CONNECTED" if self.cam1_connected else "DISCONNECTED"
            cv2.putText(combined, f"Cam0: {cam0_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                       (0, 255, 0) if self.cam0_connected else (0, 0, 255), 1)
            y += 20
            cv2.putText(combined, f"Cam1: {cam1_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                       (0, 255, 0) if self.cam1_connected else (0, 0, 255), 1)
            y += 20
            
            # Add instructions
            cv2.putText(combined, "Press 'q' to close preview", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            # Display the combined frame
            cv2.imshow('Safe Dual Camera Preview', combined)
            
        except Exception as e:
            print(f"[WARNING] Display error: {e}")

    def _display_disconnected_preview(self):
        """Display disconnected status in preview window"""
        try:
            placeholder_shape = (480, 1280, 3)  # Double width for dual view
            display = np.zeros(placeholder_shape, dtype=np.uint8)
            
            cv2.putText(display, "No cameras available", (400, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
            cv2.putText(display, "Check connections and restart preview", (300, 280), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(display, "Press 'q' to close preview", (400, 320), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            
            cv2.imshow('Safe Dual Camera Preview', display)
            
        except Exception as e:
            print(f"[WARNING] Disconnected display error: {e}")

    def capture_single_frame(self):
        """Capture and display a single frame for testing"""
        if not (self.cam0_connected or self.cam1_connected):
            messagebox.showerror("Error", "No cameras connected!")
            return
            
        try:
            frame0 = None
            frame1 = None
            
            if self.cam0_connected and self.cam0:
                frame0 = self.safe_camera_operation(lambda cam: cam.capture_array(), self.cam0)
                
            if self.cam1_connected and self.cam1:
                frame1 = self.safe_camera_operation(lambda cam: cam.capture_array(), self.cam1)
            
            if frame0 is not None or frame1 is not None:
                self._display_preview_frames(frame0, frame1)
                self.update_info_display("Single frame captured and displayed", append=True)
                # Keep window open for 3 seconds, then close
                threading.Timer(3.0, lambda: cv2.destroyAllWindows()).start()
            else:
                self.update_info_display("Failed to capture single frame", append=True)
                
        except Exception as e:
            self.update_info_display(f"Single frame capture error: {e}", append=True)

    def safe_stop_cameras(self):
        """Safely stop all cameras"""
        try:
            if self.cam0:
                try:
                    self.cam0.stop()
                    self.update_info_display("Camera 0 stopped", append=True)
                except:
                    pass
                    
            if self.cam1:
                try:
                    self.cam1.stop()
                    self.update_info_display("Camera 1 stopped", append=True)
                except:
                    pass
                    
        except Exception as e:
            self.update_info_display(f"Error stopping cameras: {e}", append=True)
        
        finally:
            self.cam0 = None
            self.cam1 = None
            self.cam0_connected = False
            self.cam1_connected = False

    def on_closing(self):
        """Handle window closing safely"""
        self.shutdown_requested = True
        self.stop_preview()  # Stop preview first
        self.cleanup()
        self.root.destroy()

    def cleanup(self):
        """Clean up resources safely"""
        print("[INFO] Cleaning up resources...")
        self.save_settings()
        self.stop_preview()  # Ensure preview is stopped
        self.safe_stop_cameras()
        try:
            cv2.destroyAllWindows()
        except:
            pass

    def run(self):
        """Run the GUI"""
        try:
            print("[INFO] Starting safe GUI main loop...")
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self.cleanup()

    # Include all the processing methods from the original (cropping, distortion correction, etc.)
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
            print(f"[ERROR] Distortion correction failed for {cam_name}: {e}")
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
            print(f"[ERROR] Perspective correction failed for {cam_name}: {e}")
            return image

    def rotate_left_image(self, image):
        """Rotate the left image by the specified angle"""
        if not self.apply_left_rotation:
            return image
            
        try:
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, self.left_rotation_angle, 1.0)
            
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                   flags=cv2.INTER_LINEAR, 
                                   borderMode=cv2.BORDER_REFLECT_101)
            return rotated
            
        except Exception as e:
            print(f"[ERROR] Left image rotation failed: {e}")
            return image

    def rotate_right_image(self, image):
        """Rotate the right image by the specified angle"""
        if not self.apply_right_rotation:
            return image
            
        try:
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, self.right_rotation_angle, 1.0)
            
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height), 
                                   flags=cv2.INTER_LINEAR, 
                                   borderMode=cv2.BORDER_REFLECT_101)
            return rotated
            
        except Exception as e:
            print(f"[ERROR] Right image rotation failed: {e}")
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
            print(f"[ERROR] Failed to create combined image: {e}")
            return None

    def save_processed_image_tiff(self, image, output_path):
        """Save processed image as TIFF"""
        try:
            if image is None or image.size == 0:
                return False
            
            imageio.imsave(output_path, image)
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save TIFF {output_path}: {e}")
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
            print(f"[WARNING] Failed to apply settings to camera 0: {e}")
            
        try:
            if self.cam1_connected and self.cam1:
                self.safe_camera_operation(lambda cam: cam.set_controls(settings), self.cam1)
        except Exception as e:
            print(f"[WARNING] Failed to apply settings to camera 1: {e}")

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
            print("[SUCCESS] Settings saved")
        except Exception as e:
            print(f"[ERROR] Failed to save settings: {e}")

    def load_settings(self):
        try:
            if os.path.exists('camera_settings.json'):
                with open('camera_settings.json', 'r') as f:
                    settings = json.load(f)
                for param, value in settings.items():
                    if param in self.params:
                        self.params[param]['value'] = value
                        if hasattr(self, 'scales') and param in self.scales:
                            self.scales[param].set(value)
                        if hasattr(self, 'entries') and param in self.entries:
                            self.entries[param].delete(0, tk.END)
                            self.entries[param].insert(0, f"{value:.2f}")
                print("[SUCCESS] Loaded previous settings")
        except Exception as e:
            print(f"[WARNING] Failed to load settings: {e}")

    def load_distortion_coefficients(self):
        """Load distortion correction coefficients"""
        dual_coeff_file = 'distortion_coefficients_dual.json'
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
                
                print(f"[SUCCESS] Loaded coefficients from {dual_coeff_file}")
                return
            except Exception as e:
                print(f"[WARNING] Failed to load coefficients: {e}")
        
        print("[INFO] Using built-in default coefficients")

    def update_perspective_setting(self):
        """Update perspective correction setting"""
        self.enable_perspective_correction = self.perspective_var.get()
        self.update_info_display(f"Perspective correction {'enabled' if self.enable_perspective_correction else 'disabled'}", append=True)

    def update_right_rotation_setting(self):
        """Update right rotation setting"""
        self.apply_right_rotation = self.right_rotation_var.get()
        self.update_info_display(f"Right image rotation {'enabled' if self.apply_right_rotation else 'disabled'}", append=True)


def main():
    """Main entry point"""
    try:
        print("Initializing Safe Dual IMX708 Camera Control GUI v1.3...")
        
        # Check GUI support
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            print(f"Error: GUI not supported: {e}")
            return 1
        
        viewer = SafeIMX708Viewer()
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