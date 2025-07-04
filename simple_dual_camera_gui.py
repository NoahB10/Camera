import tkinter as tk
from tkinter import ttk, messagebox
from picamera2 import Picamera2
import cv2
import time
import numpy as np
from datetime import datetime
import os
import json

class SimpleDualCameraGUI:
    def __init__(self):
        # Camera connection status
        self.cam0_connected = False
        self.cam1_connected = False
        self.cam0 = None
        self.cam1 = None
        
        # Initialize camera configuration template
        self.camera_config = None

        # Default/base values for camera parameters
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
        
        # Load settings
        self.load_settings()
        
        # Try to initialize cameras
        self.initialize_cameras()

    def initialize_cameras(self):
        """Initialize cameras with error handling"""
        print("Attempting to initialize cameras...")
        
        try:
            # Try to initialize camera 0
            try:
                from picamera2 import Picamera2
                self.cam0 = Picamera2(0)
                
                # Create shared full-resolution configuration
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
        self.root.title("Simple Dual Camera Control")

        # Main control frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        self.entries = {}
        self.scales = {}

        # Camera parameter controls
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

        # Main action buttons
        ttk.Button(control_frame, text="Save Images", command=self.save_images).pack(fill=tk.X, padx=5, pady=10)
        ttk.Button(control_frame, text="Reset All", command=self.reset_all).pack(fill=tk.X, padx=5)
        ttk.Button(control_frame, text="Save Settings", command=self.save_settings).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(control_frame, text="Reconnect Cameras", command=self.reconnect_cameras).pack(fill=tk.X, padx=5, pady=5)

        # Save options frame
        save_frame = ttk.LabelFrame(control_frame, text="Save Options")
        save_frame.pack(fill=tk.X, padx=5, pady=10)

        # Save DNG checkbox (default: True)
        self.save_dng_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(save_frame, text="Save Original DNG Files", 
                       variable=self.save_dng_var).pack(anchor=tk.W, padx=5, pady=2)

        # Save TIFF checkbox (default: False since it's just for raw viewing)
        self.save_tiff_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(save_frame, text="Save Raw TIFF Files", 
                       variable=self.save_tiff_var).pack(anchor=tk.W, padx=5, pady=2)

        # Info label
        ttk.Label(save_frame, text="Note: Images are saved without any processing\n(no cropping, correction, or rotation)",
                 font=('TkDefaultFont', 8), foreground='gray').pack(anchor=tk.W, padx=5, pady=2)

    def apply_settings(self):
        """Apply camera settings to connected cameras"""
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

    def save_images(self):
        """Save images from connected cameras without any processing"""
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
            
            # Save original DNG files if enabled
            if self.save_dng_var.get():
                try:
                    if req0 is not None:
                        original_filename0 = f"cam0_{timestamp}_raw_{params_str}.dng"
                        req0.save_dng(original_filename0)
                        print(f"[SUCCESS] Saved cam0 DNG: {original_filename0}")
                        success_count += 1
                        
                    if req1 is not None:
                        original_filename1 = f"cam1_{timestamp}_raw_{params_str}.dng"
                        req1.save_dng(original_filename1)
                        print(f"[SUCCESS] Saved cam1 DNG: {original_filename1}")
                        success_count += 1
                        
                except Exception as e:
                    print(f"[ERROR] Failed to save DNG files: {e}")

            # Save raw TIFF files if enabled
            if self.save_tiff_var.get():
                try:
                    if req0 is not None:
                        img0 = req0.make_array("main")
                        tiff_filename0 = f"cam0_{timestamp}_raw_{params_str}.tiff"
                        cv2.imwrite(tiff_filename0, cv2.cvtColor(img0, cv2.COLOR_RGB2BGR))
                        print(f"[SUCCESS] Saved cam0 TIFF: {tiff_filename0}")
                        success_count += 1
                        
                    if req1 is not None:
                        img1 = req1.make_array("main")
                        tiff_filename1 = f"cam1_{timestamp}_raw_{params_str}.tiff"
                        cv2.imwrite(tiff_filename1, cv2.cvtColor(img1, cv2.COLOR_RGB2BGR))
                        print(f"[SUCCESS] Saved cam1 TIFF: {tiff_filename1}")
                        success_count += 1
                        
                except Exception as e:
                    print(f"[ERROR] Failed to save TIFF files: {e}")

            if success_count > 0:
                print(f"\n[SUCCESS] Save operation complete! {success_count} files saved.")
                messagebox.showinfo("Success", f"Successfully saved {success_count} image files!")
            else:
                print(f"\n[WARNING] No files were saved.")
                messagebox.showwarning("Warning", "No files were saved. Check save options and camera connections.")

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

    def update_preview(self):
        """Update the camera preview window"""
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
            display0 = cv2.resize(frame0, (640, 480))
        else:
            # Create disconnected placeholder
            display0 = np.zeros(placeholder_shape, dtype=np.uint8)
            cv2.putText(display0, "Camera 0", (240, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(display0, "DISCONNECTED", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
        # Process or create placeholder for camera 1
        if frame1 is not None:
            display1 = cv2.resize(frame1, (640, 480))
        else:
            # Create disconnected placeholder
            display1 = np.zeros(placeholder_shape, dtype=np.uint8)
            cv2.putText(display1, "Camera 1", (240, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(display1, "DISCONNECTED", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Combine displays side by side
        combined = np.hstack((display0, display1))

        # Add parameter display
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
        
        cv2.putText(combined, "Preview: Raw images (no processing)", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        cv2.imshow('Simple Dual Camera Preview', combined)
        cv2.waitKey(1)
        self.root.after(100, self.update_preview)

    def run(self):
        """Start the GUI main loop"""
        self.update_preview()
        self.root.mainloop()

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
        """Clean up resources"""
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
        """Handle scale value changes"""
        value = float(self.scales[param_name].get())
        self.entries[param_name].delete(0, tk.END)
        self.entries[param_name].insert(0, f"{value:.2f}")
        self.params[param_name]['value'] = value
        self.apply_settings()

    def on_entry_change(self, param_name):
        """Handle entry field changes"""
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
        """Reset a single parameter to default"""
        default_value = self.defaults[param_name]
        self.scales[param_name].set(default_value)
        self.entries[param_name].delete(0, tk.END)
        self.entries[param_name].insert(0, f"{default_value:.2f}")
        self.params[param_name]['value'] = default_value
        self.apply_settings()

    def reset_all(self):
        """Reset all parameters to defaults"""
        for param_name in self.params:
            self.reset_parameter(param_name)

    def save_settings(self):
        """Save current settings to file"""
        settings = {param: self.params[param]['value'] for param in self.params}
        try:
            with open('simple_camera_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
            print("Settings saved successfully")
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists('simple_camera_settings.json'):
                with open('simple_camera_settings.json', 'r') as f:
                    settings = json.load(f)
                for param, value in settings.items():
                    if param in self.params:
                        self.params[param]['value'] = value
                        
                # Update GUI elements
                for param_name, value in settings.items():
                    if param_name in self.scales:
                        self.scales[param_name].set(value)
                    if param_name in self.entries:
                        self.entries[param_name].delete(0, tk.END)
                        self.entries[param_name].insert(0, f"{value:.2f}")
                        
                print("Loaded previous settings")
        except Exception as e:
            print(f"Failed to load settings: {e}")


def main():
    """Main entry point"""
    try:
        print("Initializing Simple Dual Camera Control GUI...")
        
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
        
        gui = SimpleDualCameraGUI()
        print("Starting GUI main loop...")
        gui.run()
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
            if 'gui' in locals():
                gui.cleanup()
        except:
            pass


if __name__ == "__main__":
    import sys
    sys.exit(main())
