import sys
import cv2
import time
import numpy as np
from datetime import datetime
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLabel, QSlider, 
                             QLineEdit, QPushButton, QCheckBox, QGroupBox,
                             QMessageBox, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont
from picamera2 import Picamera2

class SimpleDualCameraGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
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

        # Storage for GUI elements
        self.sliders = {}
        self.entries = {}
        
        # Setup GUI
        self.setup_gui()
        
        # Load settings
        self.load_settings()
        
        # Try to initialize cameras
        self.initialize_cameras()
        
        # Setup preview timer
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.start(100)  # Update every 100ms

    def setup_gui(self):
        """Setup the PyQt5 GUI"""
        self.setWindowTitle("Simple Dual Camera Control (PyQt5)")
        self.setGeometry(100, 100, 1400, 800)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create preview area (left side)
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(1280, 480)
        self.preview_label.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("Camera Preview Loading...")
        main_layout.addWidget(self.preview_label, 2)  # Give it more space
        
        # Create control panel (right side)
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel, 1)

    def create_control_panel(self):
        """Create the control panel with camera parameters and buttons"""
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_widget.setMaximumWidth(400)
        
        # Camera parameter controls
        params_group = QGroupBox("Camera Parameters")
        params_layout = QVBoxLayout(params_group)
        
        for param_name, param_data in self.params.items():
            param_widget = self.create_parameter_control(param_name, param_data)
            params_layout.addWidget(param_widget)
        
        control_layout.addWidget(params_group)
        
        # Action buttons
        buttons_group = QGroupBox("Actions")
        buttons_layout = QVBoxLayout(buttons_group)
        
        save_btn = QPushButton("Save Images")
        save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        save_btn.clicked.connect(self.save_images)
        buttons_layout.addWidget(save_btn)
        
        reset_all_btn = QPushButton("Reset All Parameters")
        reset_all_btn.clicked.connect(self.reset_all)
        buttons_layout.addWidget(reset_all_btn)
        
        save_settings_btn = QPushButton("Save Settings")
        save_settings_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_settings_btn)
        
        reconnect_btn = QPushButton("Reconnect Cameras")
        reconnect_btn.clicked.connect(self.reconnect_cameras)
        buttons_layout.addWidget(reconnect_btn)
        
        control_layout.addWidget(buttons_group)
        
        # Save options
        save_options_group = QGroupBox("Save Options")
        save_options_layout = QVBoxLayout(save_options_group)
        
        self.save_dng_checkbox = QCheckBox("Save Original DNG Files")
        self.save_dng_checkbox.setChecked(True)
        save_options_layout.addWidget(self.save_dng_checkbox)
        
        self.save_tiff_checkbox = QCheckBox("Save Raw TIFF Files")
        self.save_tiff_checkbox.setChecked(False)
        save_options_layout.addWidget(self.save_tiff_checkbox)
        
        note_label = QLabel("Note: Images are saved without any processing\n(no cropping, correction, or rotation)")
        note_label.setStyleSheet("color: gray; font-size: 9px;")
        note_label.setWordWrap(True)
        save_options_layout.addWidget(note_label)
        
        control_layout.addWidget(save_options_group)
        
        # Status information
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Initializing cameras...")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        
        control_layout.addWidget(status_group)
        
        # Add stretch to push everything to the top
        control_layout.addStretch()
        
        return control_widget

    def create_parameter_control(self, param_name, param_data):
        """Create a parameter control widget with slider and entry"""
        widget = QGroupBox(param_name)
        layout = QVBoxLayout(widget)
        
        # Slider
        slider = QSlider(Qt.Horizontal)
        
        if param_name == 'ExposureTime':
            # Use integer values for exposure time
            slider.setMinimum(int(param_data['min']))
            slider.setMaximum(int(param_data['max']))
            slider.setValue(int(param_data['value']))
        else:
            # Use scaled values for float parameters (multiply by 100)
            slider.setMinimum(int(param_data['min'] * 100))
            slider.setMaximum(int(param_data['max'] * 100))
            slider.setValue(int(param_data['value'] * 100))
        
        slider.valueChanged.connect(lambda value, p=param_name: self.on_slider_change(p, value))
        layout.addWidget(slider)
        self.sliders[param_name] = slider
        
        # Entry and buttons layout
        entry_layout = QHBoxLayout()
        
        entry = QLineEdit(str(param_data['value']))
        entry.setMaximumWidth(80)
        entry.returnPressed.connect(lambda p=param_name: self.on_entry_change(p))
        entry_layout.addWidget(entry)
        self.entries[param_name] = entry
        
        set_btn = QPushButton("Set")
        set_btn.setMaximumWidth(40)
        set_btn.clicked.connect(lambda checked, p=param_name: self.on_entry_change(p))
        entry_layout.addWidget(set_btn)
        
        reset_btn = QPushButton("Reset")
        reset_btn.setMaximumWidth(50)
        reset_btn.clicked.connect(lambda checked, p=param_name: self.reset_parameter(p))
        entry_layout.addWidget(reset_btn)
        
        layout.addLayout(entry_layout)
        
        return widget

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
            
        # Update status
        self.update_status()

    def update_status(self):
        """Update the status label"""
        if self.cam0_connected and self.cam1_connected:
            status = "✓ Both cameras connected and ready"
            print("[SUCCESS] Both cameras connected and ready")
        elif self.cam0_connected or self.cam1_connected:
            connected = "Camera 0" if self.cam0_connected else "Camera 1"
            status = f"⚠ Only {connected} connected"
            print(f"[WARNING] Only {connected} connected")
        else:
            status = "✗ No cameras connected"
            print("[WARNING] No cameras connected - GUI will show disconnected status")
        
        # Add save options status
        save_status = []
        if hasattr(self, 'save_dng_checkbox') and self.save_dng_checkbox.isChecked():
            save_status.append("DNG: ON")
        else:
            save_status.append("DNG: OFF")
            
        if hasattr(self, 'save_tiff_checkbox') and self.save_tiff_checkbox.isChecked():
            save_status.append("TIFF: ON")
        else:
            save_status.append("TIFF: OFF")
        
        full_status = f"{status}\n\nSave Options:\n{', '.join(save_status)}"
        
        if hasattr(self, 'status_label'):
            self.status_label.setText(full_status)

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
        
        self.update_status()

    def save_images(self):
        """Save images from connected cameras without any processing"""
        # Check if any cameras are connected
        if not self.cam0_connected and not self.cam1_connected:
            QMessageBox.critical(self, "Error", "No cameras connected! Cannot save images.")
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
            if self.save_dng_checkbox.isChecked():
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
            if self.save_tiff_checkbox.isChecked():
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
                QMessageBox.information(self, "Success", f"Successfully saved {success_count} image files!")
            else:
                print(f"\n[WARNING] No files were saved.")
                QMessageBox.warning(self, "Warning", "No files were saved. Check save options and camera connections.")

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
        """Update the camera preview"""
        try:
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

            # Add parameter overlay
            y = 30
            for param_name, param_data in self.params.items():
                text = f"{param_name}: {param_data['value']:.2f}"
                cv2.putText(combined, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y += 20

            # Add status overlay
            cam0_status = "CONNECTED" if self.cam0_connected else "DISCONNECTED"
            cam1_status = "CONNECTED" if self.cam1_connected else "DISCONNECTED"
            cv2.putText(combined, f"Cam0: {cam0_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.cam0_connected else (0, 0, 255), 1)
            y += 20
            cv2.putText(combined, f"Cam1: {cam1_status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if self.cam1_connected else (0, 0, 255), 1)
            y += 20
            cv2.putText(combined, "Preview: Raw images (no processing)", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            # Convert to QImage and display
            height, width, channel = combined.shape
            bytes_per_line = 3 * width
            q_image = QImage(combined.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(q_image)
            self.preview_label.setPixmap(pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
        except Exception as e:
            print(f"[ERROR] Preview update failed: {e}")

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
            QMessageBox.information(self, "Success", "Both cameras reconnected successfully!")
        elif self.cam0_connected or self.cam1_connected:
            connected = "Camera 0" if self.cam0_connected else "Camera 1"
            QMessageBox.warning(self, "Partial Success", f"Only {connected} reconnected")
        else:
            QMessageBox.critical(self, "Failed", "No cameras could be connected")

    def on_slider_change(self, param_name, value):
        """Handle slider value changes"""
        if param_name == 'ExposureTime':
            actual_value = value  # Integer value
        else:
            actual_value = value / 100.0  # Convert back from scaled value
        
        self.params[param_name]['value'] = actual_value
        self.entries[param_name].setText(f"{actual_value:.2f}")
        self.apply_settings()

    def on_entry_change(self, param_name):
        """Handle entry field changes"""
        try:
            value = float(self.entries[param_name].text())
            param_range = self.params[param_name]
            
            if param_range['min'] <= value <= param_range['max']:
                self.params[param_name]['value'] = value
                
                if param_name == 'ExposureTime':
                    self.sliders[param_name].setValue(int(value))
                else:
                    self.sliders[param_name].setValue(int(value * 100))
                    
                self.apply_settings()
            else:
                # Reset to current value if out of range
                current_value = self.params[param_name]['value']
                self.entries[param_name].setText(f"{current_value:.2f}")
                QMessageBox.warning(self, "Invalid Value", f"Value must be between {param_range['min']} and {param_range['max']}")
                
        except ValueError:
            # Reset to current value if invalid
            current_value = self.params[param_name]['value']
            self.entries[param_name].setText(f"{current_value:.2f}")
            QMessageBox.warning(self, "Invalid Value", "Please enter a valid number")

    def reset_parameter(self, param_name):
        """Reset a single parameter to default"""
        default_value = self.defaults[param_name]
        self.params[param_name]['value'] = default_value
        
        self.entries[param_name].setText(f"{default_value:.2f}")
        
        if param_name == 'ExposureTime':
            self.sliders[param_name].setValue(int(default_value))
        else:
            self.sliders[param_name].setValue(int(default_value * 100))
            
        self.apply_settings()

    def reset_all(self):
        """Reset all parameters to defaults"""
        for param_name in self.params:
            self.reset_parameter(param_name)

    def save_settings(self):
        """Save current settings to file"""
        settings = {param: self.params[param]['value'] for param in self.params}
        try:
            with open('simple_camera_settings_pyqt.json', 'w') as f:
                json.dump(settings, f, indent=4)
            print("Settings saved successfully")
            QMessageBox.information(self, "Success", "Settings saved successfully!")
        except Exception as e:
            print(f"Failed to save settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{str(e)}")

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists('simple_camera_settings_pyqt.json'):
                with open('simple_camera_settings_pyqt.json', 'r') as f:
                    settings = json.load(f)
                    
                for param, value in settings.items():
                    if param in self.params:
                        self.params[param]['value'] = value
                        
                        # Update GUI elements if they exist
                        if param in self.entries:
                            self.entries[param].setText(f"{value:.2f}")
                            
                        if param in self.sliders:
                            if param == 'ExposureTime':
                                self.sliders[param].setValue(int(value))
                            else:
                                self.sliders[param].setValue(int(value * 100))
                                
                print("Loaded previous settings")
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def closeEvent(self, event):
        """Handle application close event"""
        self.cleanup()
        event.accept()

    def cleanup(self):
        """Clean up resources"""
        self.save_settings()
        
        # Stop preview timer
        if hasattr(self, 'preview_timer'):
            self.preview_timer.stop()
        
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


def main():
    """Main entry point"""
    try:
        print("Initializing Simple Dual Camera Control GUI (PyQt5)...")
        
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Use modern Fusion style
        
        gui = SimpleDualCameraGUI()
        gui.show()
        
        print("Starting PyQt5 GUI...")
        return app.exec_()
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())