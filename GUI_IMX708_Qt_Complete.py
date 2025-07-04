#!/usr/bin/env python3

import sys
import os
import json
import time
import threading
import numpy as np
from datetime import datetime

# Fix Qt platform plugin issues on Raspberry Pi and headless systems
def setup_qt_environment():
    """Setup Qt environment variables to fix OpenCV Qt conflicts and platform issues"""
    
    print("🔧 Setting up Qt environment...")
    
    # CRITICAL: Fix OpenCV Qt plugin conflicts that cause platform plugin errors
    # OpenCV ships with Qt plugins that conflict with system Qt plugins
    
    # 1. Clear any existing OpenCV Qt plugin paths
    current_plugin_path = os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH', '')
    if current_plugin_path:
        # Remove any OpenCV Qt plugin paths
        paths = current_plugin_path.split(os.pathsep)
        filtered_paths = []
        for path in paths:
            if 'cv2' not in path and 'opencv' not in path:
                filtered_paths.append(path)
        if filtered_paths != paths:
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.pathsep.join(filtered_paths)
            print("🔧 Removed OpenCV Qt plugin paths from QT_QPA_PLATFORM_PLUGIN_PATH")
    else:
        # Explicitly set empty to prevent OpenCV interference
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''
        print("🔧 Set empty QT_QPA_PLATFORM_PLUGIN_PATH to prevent OpenCV conflicts")
    
    # 2. Disable OpenCV's Qt backend completely
    os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
    os.environ['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS'] = '0'
    
    # 3. Set Qt platform appropriately
    if 'QT_QPA_PLATFORM' not in os.environ:
        # Detect environment
        display = os.environ.get('DISPLAY', '')
        wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
        
        if wayland_display:
            os.environ['QT_QPA_PLATFORM'] = 'wayland'
            print("🐧 Using Wayland platform")
        elif display:
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
            print("🐧 Using X11/xcb platform")
        else:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
            print("🐧 No display detected, using offscreen platform")
    
    # 4. Raspberry Pi specific optimizations
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
            if 'raspberry pi' in model:
                print("🍓 Raspberry Pi detected - applying optimizations")
                os.environ['QT_QPA_EGLFS_FORCE888'] = '1'
                os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
                os.environ['QT_SCALE_FACTOR'] = '1'
                # Disable problematic features on Pi
                os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
                os.environ['QT_QUICK_BACKEND'] = 'software'
    except:
        # Not on Pi or can't detect
        pass
    
    # 5. General Qt stability settings
    os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.plugin.debug=false'
    
    platform = os.environ.get('QT_QPA_PLATFORM', 'default')
    print(f"Qt Platform: {platform}")
    
    # 6. Prevent threading issues
    os.environ['QT_THREAD_POOL_MAX_THREADS'] = '4'

# Setup Qt environment before importing Qt
setup_qt_environment()

# Qt imports with error handling - PREFER PyQt5 for Picamera2 compatibility
QT_AVAILABLE = True
QT_FRAMEWORK = None

try:
    # Try PyQt5 FIRST for better Picamera2 compatibility
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QTabWidget, QGroupBox, QLabel, QSlider, QLineEdit, QPushButton, QCheckBox,
        QTextEdit, QSplitter, QFrame, QSpinBox, QDoubleSpinBox, QComboBox,
        QMessageBox, QFileDialog, QFormLayout, QScrollArea
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal as Signal, QThread, QObject
    from PyQt5.QtGui import QFont, QTextCursor, QPixmap, QImage
    QT_FRAMEWORK = "PyQt5"
    print("✅ PyQt5 imported successfully (preferred for Picamera2)")
except ImportError as e:
    print(f"⚠️ PyQt5 import failed: {e}")
    print("Trying PySide6 as fallback...")
    try:
        from PySide6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
            QTabWidget, QGroupBox, QLabel, QSlider, QLineEdit, QPushButton, QCheckBox,
            QTextEdit, QSplitter, QFrame, QSpinBox, QDoubleSpinBox, QComboBox,
            QMessageBox, QFileDialog, QFormLayout, QScrollArea
        )
        from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
        from PySide6.QtGui import QFont, QTextCursor, QPixmap, QImage
        QT_FRAMEWORK = "PySide6"
        print("✅ PySide6 imported successfully (fallback)")
    except ImportError:
        print("❌ Both PyQt5 and PySide6 failed to import")
        QT_AVAILABLE = False
        QT_FRAMEWORK = None

# Camera imports
CAMERA_AVAILABLE = True
QGlPicamera2 = None
QPicamera2 = None

try:
    from picamera2 import Picamera2
    print("✅ Picamera2 imported successfully")
    
    # Import proper Qt widgets if Qt is available
    if QT_AVAILABLE and QT_FRAMEWORK:
        try:
            from picamera2.previews.qt import QGlPicamera2, QPicamera2
            print(f"✅ QGlPicamera2 and QPicamera2 imported successfully for {QT_FRAMEWORK}")
            
            # Verify compatibility
            if QT_FRAMEWORK == "PyQt5":
                print("🎯 Using PyQt5 - optimal compatibility for Picamera2 Qt widgets")
            else:
                print("⚠️ Using PySide6 - may have compatibility issues with Picamera2 Qt widgets")
                
        except ImportError as e:
            print(f"❌ Picamera2 Qt widgets import failed: {e}")
            print(f"   This may be due to {QT_FRAMEWORK} compatibility issues")
            print("   Preview will use custom fallback mode")
            QGlPicamera2 = None
            QPicamera2 = None
    else:
        print("⚠️ Qt not available - Picamera2 Qt widgets disabled")
        QGlPicamera2 = None
        QPicamera2 = None
        
except ImportError as e:
    print(f"❌ Picamera2 not available: {e}")
    print("Running in simulation mode")
    CAMERA_AVAILABLE = False

# Image processing imports - CRITICAL: Import cv2 AFTER Qt to avoid threading issues
PROCESSING_AVAILABLE = False
cv2 = None

def initialize_opencv():
    """Initialize OpenCV after Qt is set up to avoid threading conflicts"""
    global cv2, PROCESSING_AVAILABLE
    
    if cv2 is not None:
        return  # Already initialized
    
    try:
        # Set OpenCV threading to single thread to avoid Qt conflicts
        os.environ['OPENCV_THREADING'] = '0'
        os.environ['OPENCV_NUM_THREADS'] = '1'
        
        # Import OpenCV after Qt initialization
        import cv2 as cv2_module
        cv2 = cv2_module
        
        # Disable OpenCV's Qt backend to prevent conflicts
        if hasattr(cv2, 'setUseOptimized'):
            cv2.setUseOptimized(True)
        if hasattr(cv2, 'setNumThreads'):
            cv2.setNumThreads(1)
            
        print("✅ OpenCV initialized after Qt setup")
        
        # Try other processing libraries
        try:
            import discorpy.post.postprocessing as post
            import imageio
            PROCESSING_AVAILABLE = True
            print("✅ Image processing libraries available")
        except ImportError:
            print("⚠️ Some processing libraries not available, but OpenCV is ready")
            PROCESSING_AVAILABLE = False
            
    except ImportError:
        print("❌ OpenCV not available - preview fallback disabled")
        cv2 = None
        PROCESSING_AVAILABLE = False


class LogWidget(QTextEdit):
    """Custom log widget with automatic scrolling and formatting"""
    
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        
        # Set dark theme for log
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 9pt;
                border: 1px solid #333;
            }
        """)
        
    def log_message(self, message):
        """Add timestamped message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        
        self.append(full_message)
        
        # Auto-scroll to bottom
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        
        # Also print to console
        print(full_message)


class ParameterControl(QWidget):
    """Custom widget for camera parameter control with slider and entry"""
    
    value_changed = Signal(str, float)
    
    def __init__(self, param_name, param_data):
        super().__init__()
        self.param_name = param_name
        self.param_data = param_data
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Parameter label
        label = QLabel(self.param_name)
        label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(label)
        
        # Slider
        self.slider = QSlider(Qt.Horizontal)
        
        if self.param_name == 'ExposureTime':
            # Integer values for exposure time
            self.slider.setMinimum(int(self.param_data['min']))
            self.slider.setMaximum(int(self.param_data['max']))
            self.slider.setValue(int(self.param_data['value']))
        else:
            # Scaled values for float parameters
            self.slider.setMinimum(int(self.param_data['min'] * 100))
            self.slider.setMaximum(int(self.param_data['max'] * 100))
            self.slider.setValue(int(self.param_data['value'] * 100))
            
        self.slider.valueChanged.connect(self.on_slider_change)
        layout.addWidget(self.slider)
        
        # Control row with entry and buttons
        control_layout = QHBoxLayout()
        
        self.entry = QLineEdit(str(self.param_data['value']))
        self.entry.setMaximumWidth(80)
        self.entry.returnPressed.connect(self.on_entry_change)
        control_layout.addWidget(self.entry)
        
        set_btn = QPushButton("Set")
        set_btn.setMaximumWidth(40)
        set_btn.clicked.connect(self.on_entry_change)
        control_layout.addWidget(set_btn)
        
        reset_btn = QPushButton("Reset")
        reset_btn.setMaximumWidth(50)
        reset_btn.clicked.connect(self.reset_parameter)
        control_layout.addWidget(reset_btn)
        
        layout.addLayout(control_layout)
        
        # Range label
        range_label = QLabel(f"Range: {self.param_data['min']} - {self.param_data['max']}")
        range_label.setStyleSheet("color: gray; font-size: 8pt;")
        layout.addWidget(range_label)
        
    def on_slider_change(self, value):
        """Handle slider value changes"""
        if self.param_name == 'ExposureTime':
            actual_value = float(value)
        else:
            actual_value = value / 100.0
            
        self.param_data['value'] = actual_value
        self.entry.setText(f"{actual_value:.2f}")
        self.value_changed.emit(self.param_name, actual_value)
        
    def on_entry_change(self):
        """Handle entry field changes"""
        try:
            value = float(self.entry.text())
            param_range = self.param_data
            
            if param_range['min'] <= value <= param_range['max']:
                self.param_data['value'] = value
                
                if self.param_name == 'ExposureTime':
                    self.slider.setValue(int(value))
                else:
                    self.slider.setValue(int(value * 100))
                    
                self.value_changed.emit(self.param_name, value)
            else:
                # Reset to current value if out of range
                current_value = self.param_data['value']
                self.entry.setText(f"{current_value:.2f}")
                QMessageBox.warning(self, "Invalid Value", 
                                  f"Value must be between {param_range['min']} and {param_range['max']}")
                
        except ValueError:
            # Reset to current value if invalid
            current_value = self.param_data['value']
            self.entry.setText(f"{current_value:.2f}")
            QMessageBox.warning(self, "Invalid Value", "Please enter a valid number")
            
    def reset_parameter(self):
        """Reset parameter to default value"""
        if 'default' in self.param_data:
            default_value = self.param_data['default']
            self.param_data['value'] = default_value
            self.entry.setText(f"{default_value:.2f}")
            
            if self.param_name == 'ExposureTime':
                self.slider.setValue(int(default_value))
            else:
                self.slider.setValue(int(default_value * 100))
                
            self.value_changed.emit(self.param_name, default_value)
            
    def get_value(self):
        """Get current parameter value"""
        return self.param_data['value']
        
    def set_value(self, value):
        """Set parameter value programmatically"""
        self.param_data['value'] = value
        self.entry.setText(f"{value:.2f}")
        
        if self.param_name == 'ExposureTime':
            self.slider.setValue(int(value))
        else:
            self.slider.setValue(int(value * 100))


class EfficientDualCameraGUI(QMainWindow):
    """Main Qt-based dual camera GUI with proper QGlPicamera2/QPicamera2 widgets"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize state
        self.cam0 = None
        self.cam1 = None
        self.preview0 = None
        self.preview1 = None
        self.cam0_connected = False
        self.cam1_connected = False
        
        # Camera parameters with defaults
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
            'ExposureTime': {'value': self.defaults['ExposureTime'], 'min': 100, 'max': 100000, 'default': self.defaults['ExposureTime']},
            'AnalogueGain': {'value': self.defaults['AnalogueGain'], 'min': 1.0, 'max': 20.0, 'default': self.defaults['AnalogueGain']},
            'Brightness': {'value': self.defaults['Brightness'], 'min': -1.0, 'max': 1.0, 'default': self.defaults['Brightness']},
            'Contrast': {'value': self.defaults['Contrast'], 'min': 0.0, 'max': 4.0, 'default': self.defaults['Contrast']},
            'Saturation': {'value': self.defaults['Saturation'], 'min': 0.0, 'max': 4.0, 'default': self.defaults['Saturation']},
            'Sharpness': {'value': self.defaults['Sharpness'], 'min': 0.0, 'max': 4.0, 'default': self.defaults['Sharpness']}
        }
        
        # Focus support
        self.focus_supported = {"cam0": False, "cam1": False}
        self.focus_controls = {}
        
        # Processing settings
        self.processing_settings = {
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
            'right_bottom_padding': 50,
            'crop_params': {
                'cam0': {'width': 2070, 'start_x': 1260, 'height': 2592},
                'cam1': {'width': 2020, 'start_x': 1400, 'height': 2592}
            }
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
        
        # GUI setup
        self.setup_ui()
        self.load_settings()
        
        # Initialize OpenCV for fallback preview mode
        initialize_opencv()
        
        # Don't initialize cameras automatically - let user click reconnect
        self.log_message("✅ GUI loaded successfully. Click 'Reconnect Cameras' to initialize cameras.")
        
        # Set up initial preview layout with placeholder
        self.setup_preview_widgets()
        
    def setup_ui(self):
        """Setup the main user interface"""
        title = f"Efficient Dual IMX708 Camera Control ({QT_FRAMEWORK}) with Picamera2 Qt Widgets"
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 1600, 1000)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Controls
        self.setup_left_panel(splitter)
        
        # Middle panel - Preview
        self.setup_preview_panel(splitter)
        
        # Right panel - Actions and Log
        self.setup_right_panel(splitter)
        
        # Set splitter proportions
        splitter.setSizes([400, 800, 400])
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Initializing cameras...")
        
    def setup_left_panel(self, parent):
        """Setup left control panel"""
        left_widget = QWidget()
        left_widget.setMaximumWidth(400)
        left_widget.setMinimumWidth(350)
        
        layout = QVBoxLayout(left_widget)
        
        # Camera parameters
        params_group = QGroupBox("Camera Parameters")
        params_layout = QVBoxLayout(params_group)
        
        self.parameter_controls = {}
        for param_name, param_data in self.params.items():
            control = ParameterControl(param_name, param_data)
            control.value_changed.connect(self.on_parameter_changed)
            self.parameter_controls[param_name] = control
            params_layout.addWidget(control)
            
        layout.addWidget(params_group)
        
        # Focus controls
        self.focus_group = QGroupBox("Focus Control")
        self.focus_layout = QVBoxLayout(self.focus_group)
        
        self.focus_status_label = QLabel("Focus detection pending camera initialization...")
        self.focus_layout.addWidget(self.focus_status_label)
        
        layout.addWidget(self.focus_group)
        
        layout.addStretch()
        parent.addWidget(left_widget)
        
    def setup_processing_controls_right(self, parent_layout):
        """Setup processing controls for right panel"""
        processing_group = QGroupBox("Processing Controls")
        tab_widget = QTabWidget()
        
        # Basic tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        self.cropping_checkbox = QCheckBox("Apply Cropping")
        self.cropping_checkbox.setChecked(self.processing_settings['apply_cropping'])
        basic_layout.addWidget(self.cropping_checkbox)
        
        self.distortion_checkbox = QCheckBox("Apply Radial Distortion Correction")
        self.distortion_checkbox.setChecked(self.processing_settings['enable_distortion_correction'])
        basic_layout.addWidget(self.distortion_checkbox)
        
        self.perspective_checkbox = QCheckBox("Enable Perspective Correction")
        self.perspective_checkbox.setChecked(self.processing_settings['enable_perspective_correction'])
        basic_layout.addWidget(self.perspective_checkbox)
        
        # Rotation controls
        rotation_group = QGroupBox("Image Rotation")
        rotation_layout = QVBoxLayout(rotation_group)
        
        left_rot_layout = QHBoxLayout()
        self.left_rotation_checkbox = QCheckBox("Left Image Rotation:")
        self.left_rotation_checkbox.setChecked(self.processing_settings['apply_left_rotation'])
        left_rot_layout.addWidget(self.left_rotation_checkbox)
        
        self.left_angle_spinbox = QDoubleSpinBox()
        self.left_angle_spinbox.setRange(-180, 180)
        self.left_angle_spinbox.setValue(self.processing_settings['left_rotation_angle'])
        self.left_angle_spinbox.setSuffix("°")
        left_rot_layout.addWidget(self.left_angle_spinbox)
        rotation_layout.addLayout(left_rot_layout)
        
        # Right rotation
        right_rot_layout = QHBoxLayout()
        self.right_rotation_checkbox = QCheckBox("Right Image Rotation:")
        self.right_rotation_checkbox.setChecked(self.processing_settings['apply_right_rotation'])
        right_rot_layout.addWidget(self.right_rotation_checkbox)
        
        self.right_angle_spinbox = QDoubleSpinBox()
        self.right_angle_spinbox.setRange(-180, 180)
        self.right_angle_spinbox.setValue(self.processing_settings['right_rotation_angle'])
        self.right_angle_spinbox.setSuffix("°")
        right_rot_layout.addWidget(self.right_angle_spinbox)
        rotation_layout.addLayout(right_rot_layout)
        
        basic_layout.addWidget(rotation_group)
        basic_layout.addStretch()
        
        tab_widget.addTab(basic_tab, "Basic")
        
        # Padding tab
        padding_tab = QWidget()
        padding_layout = QVBoxLayout(padding_tab)
        
        info_label = QLabel("Distortion Correction Padding (pixels):")
        info_label.setStyleSheet("font-weight: bold;")
        padding_layout.addWidget(info_label)
        
        # Left camera padding
        left_group = QGroupBox("Left Camera (cam0)")
        left_layout = QHBoxLayout(left_group)
        
        left_layout.addWidget(QLabel("Top:"))
        self.left_top_spinbox = QSpinBox()
        self.left_top_spinbox.setRange(0, 500)
        self.left_top_spinbox.setValue(self.processing_settings['left_top_padding'])
        left_layout.addWidget(self.left_top_spinbox)
        
        left_layout.addWidget(QLabel("Bottom:"))
        self.left_bottom_spinbox = QSpinBox()
        self.left_bottom_spinbox.setRange(0, 500)
        self.left_bottom_spinbox.setValue(self.processing_settings['left_bottom_padding'])
        left_layout.addWidget(self.left_bottom_spinbox)
        
        padding_layout.addWidget(left_group)
        
        # Right camera padding
        right_group = QGroupBox("Right Camera (cam1)")
        right_layout = QHBoxLayout(right_group)
        
        right_layout.addWidget(QLabel("Top:"))
        self.right_top_spinbox = QSpinBox()
        self.right_top_spinbox.setRange(0, 500)
        self.right_top_spinbox.setValue(self.processing_settings['right_top_padding'])
        right_layout.addWidget(self.right_top_spinbox)
        
        right_layout.addWidget(QLabel("Bottom:"))
        self.right_bottom_spinbox = QSpinBox()
        self.right_bottom_spinbox.setRange(0, 500)
        self.right_bottom_spinbox.setValue(self.processing_settings['right_bottom_padding'])
        right_layout.addWidget(self.right_bottom_spinbox)
        
        padding_layout.addWidget(right_group)
        padding_layout.addStretch()
        
        tab_widget.addTab(padding_tab, "Padding")
        
        # Crop tab
        crop_tab = QWidget()
        crop_layout = QVBoxLayout(crop_tab)
        
        crop_info_label = QLabel("Cropping Parameters:")
        crop_info_label.setStyleSheet("font-weight: bold;")
        crop_layout.addWidget(crop_info_label)
        
        # Left camera crop
        left_crop_group = QGroupBox("Left Camera (cam0)")
        left_crop_layout = QGridLayout(left_crop_group)
        
        left_crop_layout.addWidget(QLabel("Width:"), 0, 0)
        self.left_width_spinbox = QSpinBox()
        self.left_width_spinbox.setRange(100, 5000)
        self.left_width_spinbox.setValue(self.processing_settings['crop_params']['cam0']['width'])
        left_crop_layout.addWidget(self.left_width_spinbox, 0, 1)
        
        left_crop_layout.addWidget(QLabel("Start X:"), 1, 0)
        self.left_start_x_spinbox = QSpinBox()
        self.left_start_x_spinbox.setRange(0, 5000)
        self.left_start_x_spinbox.setValue(self.processing_settings['crop_params']['cam0']['start_x'])
        left_crop_layout.addWidget(self.left_start_x_spinbox, 1, 1)
        
        left_crop_layout.addWidget(QLabel("Height:"), 2, 0)
        self.left_height_spinbox = QSpinBox()
        self.left_height_spinbox.setRange(100, 5000)
        self.left_height_spinbox.setValue(self.processing_settings['crop_params']['cam0']['height'])
        left_crop_layout.addWidget(self.left_height_spinbox, 2, 1)
        
        crop_layout.addWidget(left_crop_group)
        
        # Right camera crop
        right_crop_group = QGroupBox("Right Camera (cam1)")
        right_crop_layout = QGridLayout(right_crop_group)
        
        right_crop_layout.addWidget(QLabel("Width:"), 0, 0)
        self.right_width_spinbox = QSpinBox()
        self.right_width_spinbox.setRange(100, 5000)
        self.right_width_spinbox.setValue(self.processing_settings['crop_params']['cam1']['width'])
        right_crop_layout.addWidget(self.right_width_spinbox, 0, 1)
        
        right_crop_layout.addWidget(QLabel("Start X:"), 1, 0)
        self.right_start_x_spinbox = QSpinBox()
        self.right_start_x_spinbox.setRange(0, 5000)
        self.right_start_x_spinbox.setValue(self.processing_settings['crop_params']['cam1']['start_x'])
        right_crop_layout.addWidget(self.right_start_x_spinbox, 1, 1)
        
        right_crop_layout.addWidget(QLabel("Height:"), 2, 0)
        self.right_height_spinbox = QSpinBox()
        self.right_height_spinbox.setRange(100, 5000)
        self.right_height_spinbox.setValue(self.processing_settings['crop_params']['cam1']['height'])
        right_crop_layout.addWidget(self.right_height_spinbox, 2, 1)
        
        crop_layout.addWidget(right_crop_group)
        crop_layout.addStretch()
        
        tab_widget.addTab(crop_tab, "Crop")
        
        processing_layout = QVBoxLayout(processing_group)
        processing_layout.addWidget(tab_widget)
        parent_layout.addWidget(processing_group)
        
    def setup_preview_panel(self, parent):
        """Setup center preview panel"""
        preview_widget = QWidget()
        layout = QVBoxLayout(preview_widget)
        
        # Preview area
        self.preview_container = QWidget()
        self.preview_container.setMinimumSize(800, 400)
        self.preview_container.setStyleSheet("background-color: #2a2a2a; border: 2px solid #555;")
        layout.addWidget(self.preview_container)
        
        # Preview controls
        controls_layout = QHBoxLayout()
        
        self.fps_label = QLabel("FPS:")
        controls_layout.addWidget(self.fps_label)
        
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["0.5", "1", "2", "5", "10", "15", "30"])
        self.fps_combo.setCurrentText("5")
        self.fps_combo.currentTextChanged.connect(self.on_fps_changed)
        self.fps_combo.setToolTip("Preview refresh rate (only for fallback previews)")
        controls_layout.addWidget(self.fps_combo)
        
        # Preview toggle button (will be enabled only for fallback previews)
        self.preview_toggle_btn = QPushButton("⏸️ Pause")
        self.preview_toggle_btn.setMaximumWidth(80)
        self.preview_toggle_btn.clicked.connect(self.toggle_preview)
        self.preview_toggle_btn.setEnabled(False)  # Initially disabled
        controls_layout.addWidget(self.preview_toggle_btn)
        
        controls_layout.addStretch()
        
        self.preview_status = QLabel("Cameras initializing...")
        controls_layout.addWidget(self.preview_status)
        
        layout.addLayout(controls_layout)
        
        # Activity Log (moved from right panel)
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_widget = LogWidget()
        self.log_widget.setMaximumHeight(250)  # Slightly larger than before
        log_layout.addWidget(self.log_widget)
        
        layout.addWidget(log_group)
        
        parent.addWidget(preview_widget)
        
    def setup_right_panel(self, parent):
        """Setup right action panel"""
        right_widget = QWidget()
        right_widget.setMaximumWidth(350)
        right_widget.setMinimumWidth(300)
        
        layout = QVBoxLayout(right_widget)
        
        # Action buttons
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        self.save_btn = QPushButton("💾 Save Images")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        self.save_btn.clicked.connect(self.save_images)
        actions_layout.addWidget(self.save_btn)
        
        self.test_btn = QPushButton("🧪 Test Capture")
        self.test_btn.clicked.connect(self.test_capture)
        actions_layout.addWidget(self.test_btn)
        
        self.reset_btn = QPushButton("🔄 Reset Parameters")
        self.reset_btn.clicked.connect(self.reset_all_parameters)
        actions_layout.addWidget(self.reset_btn)
        
        self.save_settings_btn = QPushButton("💾 Save Settings")
        self.save_settings_btn.clicked.connect(self.save_settings)
        actions_layout.addWidget(self.save_settings_btn)
        
        self.reconnect_btn = QPushButton("🔌 Connect Cameras")
        self.reconnect_btn.clicked.connect(self.reconnect_cameras)
        self.reconnect_btn.setToolTip("Initialize and connect to available IMX708 cameras")
        actions_layout.addWidget(self.reconnect_btn)
        
        self.test_btn = QPushButton("🧪 Test Cameras & Capture")
        self.test_btn.clicked.connect(self.test_capture)
        self.test_btn.setToolTip("Test camera connectivity and capture sample photos")
        actions_layout.addWidget(self.test_btn)
        
        self.emergency_btn = QPushButton("🚨 EMERGENCY STOP")
        self.emergency_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        self.emergency_btn.clicked.connect(self.emergency_stop)
        self.emergency_btn.setToolTip("Stop all camera operations immediately")
        actions_layout.addWidget(self.emergency_btn)
        
        layout.addWidget(actions_group)
        
        # Save options
        save_options_group = QGroupBox("Save Options")
        save_options_layout = QVBoxLayout(save_options_group)
        
        self.save_tiff_checkbox = QCheckBox("Save Combined TIFF")
        self.save_tiff_checkbox.setChecked(True)
        save_options_layout.addWidget(self.save_tiff_checkbox)
        
        self.save_dng_checkbox = QCheckBox("Save Original DNG Files")
        self.save_dng_checkbox.setChecked(True)
        save_options_layout.addWidget(self.save_dng_checkbox)
        
        layout.addWidget(save_options_group)
        
        # Processing controls (moved from left panel to below save options)
        self.setup_processing_controls_right(layout)
        
        layout.addStretch()
        
        parent.addWidget(right_widget)
        
    def log_message(self, message):
        """Log message using the log widget"""
        self.log_widget.log_message(message)
        
    def initialize_cameras(self):
        """Initialize cameras with proper QGlPicamera2/QPicamera2 widgets or fallback"""
        if not CAMERA_AVAILABLE:
            self.log_message("❌ Picamera2 not available - running in simulation mode")
            self.preview_status.setText("Simulation mode - No cameras")
            return
            
        if QGlPicamera2 is None and QPicamera2 is None:
            self.log_message("⚠️ Picamera2 Qt widgets not available - will use QLabel fallback")
        else:
            self.log_message("🔄 Initializing cameras with proper Picamera2 Qt widgets...")
        
        try:
            # Initialize Camera 0
            try:
                self.log_message("📷 Initializing Camera 0...")
                self.cam0 = Picamera2(0)
                
                # Configure camera first
                config0 = self.cam0.create_preview_configuration(
                    main={"size": (820, 616)},
                    buffer_count=4
                )
                self.cam0.configure(config0)
                
                # Start camera FIRST (as per Picamera2 docs pattern)
                self.log_message("🔄 Starting Camera 0...")
                self.cam0.start()
                self.cam0_connected = True
                
                # Create proper Qt widget AFTER starting camera
                if QGlPicamera2 is not None:
                    try:
                        self.log_message("🔄 Creating QGlPicamera2 for Camera 0...")
                        # Give camera time to stabilize before creating widget
                        time.sleep(0.1)
                        self.preview0 = QGlPicamera2(self.cam0, width=400, height=300, keep_ar=True)
                        self.log_message("✅ Camera 0: QGlPicamera2 (hardware accelerated) created")
                    except Exception as e:
                        self.log_message(f"⚠️ Camera 0: QGlPicamera2 failed, trying QPicamera2: {e}")
                        if QPicamera2 is not None:
                            try:
                                self.log_message("🔄 Creating QPicamera2 for Camera 0...")
                                self.preview0 = QPicamera2(self.cam0, width=400, height=300, keep_ar=True)
                                self.log_message("✅ Camera 0: QPicamera2 (software) created")
                            except Exception as e2:
                                self.log_message(f"⚠️ Camera 0: QPicamera2 also failed, using QLabel: {e2}")
                                self.preview0 = self.create_fallback_preview("Camera 0")
                        else:
                            self.preview0 = self.create_fallback_preview("Camera 0")
                elif QPicamera2 is not None:
                    try:
                        self.log_message("🔄 Creating QPicamera2 for Camera 0...")
                        self.preview0 = QPicamera2(self.cam0, width=400, height=300, keep_ar=True)
                        self.log_message("✅ Camera 0: QPicamera2 (software) created")
                    except Exception as e:
                        self.log_message(f"⚠️ Camera 0: QPicamera2 failed, using QLabel: {e}")
                        self.preview0 = self.create_fallback_preview("Camera 0")
                else:
                    self.log_message("📺 Camera 0: Using QLabel fallback preview")
                    self.preview0 = self.create_fallback_preview("Camera 0")
                
                # Determine preview type
                if hasattr(self.preview0, 'setPixmap'):
                    preview_msg = "with QLabel fallback"
                elif hasattr(self.preview0, '__class__') and 'QGl' in str(self.preview0.__class__):
                    preview_msg = "with QGlPicamera2 (hardware)"
                else:
                    preview_msg = "with QPicamera2 (software)"
                    
                self.log_message(f"✅ Camera 0 initialized {preview_msg}")
                
            except Exception as e:
                self.log_message(f"❌ Camera 0 failed: {e}")
                self.cam0_connected = False
                self.preview0 = None
                
            # Initialize Camera 1
            try:
                self.log_message("📷 Initializing Camera 1...")
                self.cam1 = Picamera2(1)
                
                # Configure camera first
                config1 = self.cam1.create_preview_configuration(
                    main={"size": (820, 616)},
                    buffer_count=4
                )
                self.cam1.configure(config1)
                
                # Start camera FIRST (as per Picamera2 docs pattern)
                self.log_message("🔄 Starting Camera 1...")
                self.cam1.start()
                self.cam1_connected = True
                
                # Create proper Qt widget AFTER starting camera
                if QGlPicamera2 is not None:
                    try:
                        self.log_message("🔄 Creating QGlPicamera2 for Camera 1...")
                        # Give camera time to stabilize before creating widget
                        time.sleep(0.1)
                        self.preview1 = QGlPicamera2(self.cam1, width=400, height=300, keep_ar=True)
                        self.log_message("✅ Camera 1: QGlPicamera2 (hardware accelerated) created")
                    except Exception as e:
                        self.log_message(f"⚠️ Camera 1: QGlPicamera2 failed, trying QPicamera2: {e}")
                        if QPicamera2 is not None:
                            try:
                                self.log_message("🔄 Creating QPicamera2 for Camera 1...")
                                self.preview1 = QPicamera2(self.cam1, width=400, height=300, keep_ar=True)
                                self.log_message("✅ Camera 1: QPicamera2 (software) created")
                            except Exception as e2:
                                self.log_message(f"⚠️ Camera 1: QPicamera2 also failed, using QLabel: {e2}")
                                self.preview1 = self.create_fallback_preview("Camera 1")
                        else:
                            self.preview1 = self.create_fallback_preview("Camera 1")
                elif QPicamera2 is not None:
                    try:
                        self.log_message("🔄 Creating QPicamera2 for Camera 1...")
                        self.preview1 = QPicamera2(self.cam1, width=400, height=300, keep_ar=True)
                        self.log_message("✅ Camera 1: QPicamera2 (software) created")
                    except Exception as e:
                        self.log_message(f"⚠️ Camera 1: QPicamera2 failed, using QLabel: {e}")
                        self.preview1 = self.create_fallback_preview("Camera 1")
                else:
                    self.log_message("📺 Camera 1: Using QLabel fallback preview")
                    self.preview1 = self.create_fallback_preview("Camera 1")
                
                # Determine preview type
                if hasattr(self.preview1, 'setPixmap'):
                    preview_msg = "with QLabel fallback"
                elif hasattr(self.preview1, '__class__') and 'QGl' in str(self.preview1.__class__):
                    preview_msg = "with QGlPicamera2 (hardware)"
                else:
                    preview_msg = "with QPicamera2 (software)"
                    
                self.log_message(f"✅ Camera 1 initialized {preview_msg}")
                
            except Exception as e:
                self.log_message(f"❌ Camera 1 failed: {e}")
                self.cam1_connected = False
                self.preview1 = None
                
            # Setup preview layout AFTER creating all widgets
            self.log_message("🔄 Setting up preview widget layout...")
            self.setup_preview_widgets()
            
            # Start preview update timer if using fallback previews
            self.start_fallback_preview_timer()
            
            # Apply initial settings
            self.apply_camera_settings()
            
            # Detect focus capabilities
            self.detect_focus_capabilities()
            
            # Update status
            self.update_connection_status()
            
            self.log_message("✅ Camera initialization complete!")
            
        except Exception as e:
            self.log_message(f"❌ Camera initialization error: {e}")
            
    def create_fallback_preview(self, camera_name):
        """Create a QLabel-based preview as fallback"""
        preview_label = QLabel(f"{camera_name}\nPreview Loading...")
        preview_label.setMinimumSize(400, 300)
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setStyleSheet(
            "border: 2px solid #4CAF50; "
            "background-color: black; "
            "color: white; "
            "font-size: 12pt;"
        )
        preview_label.setScaledContents(True)
        return preview_label
        
    def start_fallback_preview_timer(self):
        """Start timer for QLabel-based preview updates (only if needed)"""
        # Check if we have any QLabel fallback previews that need manual updates
        has_fallback = False
        
        if self.preview0 and hasattr(self.preview0, 'setPixmap'):
            has_fallback = True
        if self.preview1 and hasattr(self.preview1, 'setPixmap'):
            has_fallback = True
            
        if has_fallback:
            self.log_message("📺 Starting fallback preview timer for QLabel widgets...")
            self.preview_timer = QTimer()
            self.preview_timer.timeout.connect(self.update_fallback_previews)
            # Start with slower refresh rate for better performance
            fps = float(self.fps_combo.currentText())
            interval = int(1000 / max(fps, 0.5))  # Convert to milliseconds
            self.preview_timer.start(interval)
            
            # Enable FPS controls for fallback previews
            self.fps_combo.setEnabled(True)
            self.preview_toggle_btn.setEnabled(True)
            self.fps_combo.setToolTip("Control refresh rate for QLabel preview")
            self.preview_toggle_btn.setToolTip("Pause/resume QLabel preview updates")
        else:
            self.log_message("✅ Using proper Qt widgets - no manual timer needed")
            
            # Disable FPS controls since Qt widgets handle their own refresh
            self.fps_combo.setEnabled(False)
            self.preview_toggle_btn.setEnabled(False)
            self.fps_combo.setToolTip("FPS control not needed - Qt widgets handle their own refresh")
            self.preview_toggle_btn.setToolTip("Pause/resume not needed - using proper Qt widgets")
            
    def update_fallback_previews(self):
        """Update QLabel-based previews"""
        try:
            # Update Camera 0 preview
            if (self.cam0_connected and self.preview0 and 
                hasattr(self.preview0, 'setPixmap')):
                try:
                    array = self.cam0.capture_array()
                    if array is not None:
                        # Convert to QPixmap and display
                        pixmap = self.array_to_qpixmap(array)
                        if pixmap:
                            self.preview0.setPixmap(pixmap)
                except Exception as e:
                    pass  # Silently ignore capture errors
                    
            # Update Camera 1 preview
            if (self.cam1_connected and self.preview1 and 
                hasattr(self.preview1, 'setPixmap')):
                try:
                    array = self.cam1.capture_array()
                    if array is not None:
                        # Convert to QPixmap and display
                        pixmap = self.array_to_qpixmap(array)
                        if pixmap:
                            self.preview1.setPixmap(pixmap)
                except Exception as e:
                    pass  # Silently ignore capture errors
                    
        except Exception as e:
            pass  # Silently ignore timer errors
            
    def array_to_qpixmap(self, array):
        """Convert numpy array to QPixmap for display"""
        try:
            # Resize for better performance if OpenCV is available
            height, width = array.shape[:2]
            if width > 400 and cv2 is not None:
                scale = 400.0 / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                array = cv2.resize(array, (new_width, new_height))
            elif width > 400:
                # Simple downsampling without OpenCV
                step = width // 400
                array = array[::step, ::step]
            
            # Ensure array is contiguous and the right type
            array = np.ascontiguousarray(array, dtype=np.uint8)
            
            # Handle different array formats
            if len(array.shape) == 3:
                # Color image
                if array.shape[2] == 3:
                    # RGB
                    h, w, ch = array.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(array.data, w, h, bytes_per_line, QImage.Format_RGB888)
                elif array.shape[2] == 4:
                    # RGBA
                    h, w, ch = array.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(array.data, w, h, bytes_per_line, QImage.Format_RGBA8888)
                else:
                    return None
            else:
                # Grayscale
                h, w = array.shape
                bytes_per_line = w
                qt_image = QImage(array.data, w, h, bytes_per_line, QImage.Format_Grayscale8)
            
            return QPixmap.fromImage(qt_image)
            
        except Exception as e:
            return None
            
    def setup_preview_widgets(self):
        """Setup the preview widgets in the container"""
        # Clear existing layout
        layout = self.preview_container.layout()
        if layout:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)
        else:
            layout = QHBoxLayout(self.preview_container)
            
        # Add preview widgets or placeholders
        widgets_added = 0
        
        if self.preview0:
            try:
                layout.addWidget(self.preview0)
                self.preview0.show()
                widgets_added += 1
                self.log_message("✅ Preview 0 widget added to layout")
            except Exception as e:
                self.log_message(f"❌ Failed to add preview0 to layout: {e}")
        elif self.cam0_connected:
            # Camera connected but no preview - show placeholder
            placeholder0 = QLabel("Camera 0\nConnected\n(Preview not available)")
            placeholder0.setAlignment(Qt.AlignCenter)
            placeholder0.setStyleSheet(
                "color: #4CAF50; font-size: 14pt; font-weight: bold; "
                "border: 2px solid #4CAF50; border-radius: 10px; padding: 20px;"
            )
            placeholder0.setMinimumSize(400, 300)
            layout.addWidget(placeholder0)
            widgets_added += 1
            
        if self.preview1:
            try:
                layout.addWidget(self.preview1)
                self.preview1.show()
                widgets_added += 1
                self.log_message("✅ Preview 1 widget added to layout")
            except Exception as e:
                self.log_message(f"❌ Failed to add preview1 to layout: {e}")
        elif self.cam1_connected:
            # Camera connected but no preview - show placeholder
            placeholder1 = QLabel("Camera 1\nConnected\n(Preview not available)")
            placeholder1.setAlignment(Qt.AlignCenter)
            placeholder1.setStyleSheet(
                "color: #4CAF50; font-size: 14pt; font-weight: bold; "
                "border: 2px solid #4CAF50; border-radius: 10px; padding: 20px;"
            )
            placeholder1.setMinimumSize(400, 300)
            layout.addWidget(placeholder1)
            widgets_added += 1
            
        # If no cameras at all
        if not self.cam0_connected and not self.cam1_connected:
            placeholder = QLabel("No Cameras Connected\n\nClick 'Reconnect Cameras' to initialize cameras")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(
                "color: #ff9800; font-size: 16pt; font-weight: bold; "
                "border: 2px solid #ff9800; border-radius: 10px; padding: 30px;"
            )
            layout.addWidget(placeholder)
            widgets_added += 1
            
        # Show preview status
        if not (self.preview0 or self.preview1):
            status_msg = "Cameras connected - Preview disabled"
        else:
            # Check preview types
            hardware_count = 0
            software_count = 0
            fallback_count = 0
            
            for p in [self.preview0, self.preview1]:
                if p is not None:
                    if hasattr(p, 'setPixmap'):
                        fallback_count += 1
                    elif hasattr(p, '__class__') and 'QGl' in str(p.__class__):
                        hardware_count += 1
                    else:
                        software_count += 1
            
            status_parts = []
            if hardware_count > 0:
                status_parts.append(f"{hardware_count} hardware")
            if software_count > 0:
                status_parts.append(f"{software_count} software")
            if fallback_count > 0:
                status_parts.append(f"{fallback_count} fallback")
                
            if len(status_parts) > 1:
                status_msg = f"Mixed preview: {', '.join(status_parts)}"
            elif hardware_count > 0:
                status_msg = f"Hardware-accelerated preview active ({hardware_count} camera(s))"
            elif software_count > 0:
                status_msg = f"Software-rendered preview active ({software_count} camera(s))"
            else:
                status_msg = f"QLabel fallback preview active ({fallback_count} camera(s))"
            
        self.preview_status.setText(status_msg)
        self.log_message(f"📺 Preview status: {status_msg}")
        
        # Log widget count in layout  
        self.log_message(f"📊 Total widgets in preview layout: {widgets_added}")
        
    def on_fps_changed(self, fps_text):
        """Handle FPS combo box changes"""
        try:
            fps = float(fps_text)
            if hasattr(self, 'preview_timer') and self.preview_timer is not None:
                # Update timer interval
                interval = int(1000 / max(fps, 0.5))
                self.preview_timer.setInterval(interval)
                self.log_message(f"📺 Preview FPS changed to {fps} ({interval}ms interval)")
        except ValueError:
            pass
             
    def toggle_preview(self):
        """Toggle preview on/off"""
        if hasattr(self, 'preview_timer') and self.preview_timer is not None:
            if self.preview_timer.isActive():
                self.preview_timer.stop()
                self.preview_toggle_btn.setText("▶️ Resume")
                self.log_message("⏸️ Preview paused")
            else:
                self.preview_timer.start()
                self.preview_toggle_btn.setText("⏸️ Pause")
                self.log_message("▶️ Preview resumed")
            
    def detect_focus_capabilities(self):
        """Detect and setup focus controls for cameras that support it"""
        # Clear existing focus controls
        for i in reversed(range(self.focus_layout.count())):
            child = self.focus_layout.takeAt(i).widget()
            if child:
                child.setParent(None)
                
        focus_cameras = []
        
        # Check camera 0
        if self.cam0_connected and self.cam0:
            try:
                controls = self.cam0.camera_controls
                if "LensPosition" in controls and "AfMode" in controls:
                    self.focus_supported["cam0"] = True
                    focus_cameras.append("cam0")
                    self.log_message("🎯 Camera 0: Focus control supported")
                else:
                    self.log_message("❌ Camera 0: No focus control")
            except Exception as e:
                self.log_message(f"⚠️ Camera 0 focus detection failed: {e}")
                
        # Check camera 1
        if self.cam1_connected and self.cam1:
            try:
                controls = self.cam1.camera_controls
                if "LensPosition" in controls and "AfMode" in controls:
                    self.focus_supported["cam1"] = True
                    focus_cameras.append("cam1")
                    self.log_message("🎯 Camera 1: Focus control supported")
                else:
                    self.log_message("❌ Camera 1: No focus control")
            except Exception as e:
                self.log_message(f"⚠️ Camera 1 focus detection failed: {e}")
                
        # Create focus controls
        if focus_cameras:
            for cam_label in focus_cameras:
                self.create_focus_control(cam_label)
        else:
            no_focus_label = QLabel("No cameras with focus support detected")
            no_focus_label.setStyleSheet("color: #888;")
            self.focus_layout.addWidget(no_focus_label)
            
    def create_focus_control(self, cam_label):
        """Create focus control for a specific camera"""
        cam_obj = getattr(self, cam_label, None)
        if not cam_obj:
            return
            
        # Create group for this camera
        group = QGroupBox(f"Focus - {cam_label.upper()}")
        layout = QVBoxLayout(group)
        
        # Focus slider
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Position:"))
        
        focus_slider = QSlider(Qt.Horizontal)
        focus_slider.setMinimum(0)
        focus_slider.setMaximum(700)  # 0.0 to 7.0 range scaled by 100
        focus_slider.setValue(100)  # Default to 1.0
        focus_slider.valueChanged.connect(lambda val, cam=cam_label: self.set_focus_position(cam, val / 100.0))
        
        slider_layout.addWidget(focus_slider)
        
        position_label = QLabel("1.0")
        focus_slider.valueChanged.connect(lambda val: position_label.setText(f"{val/100.0:.1f}"))
        slider_layout.addWidget(position_label)
        
        layout.addLayout(slider_layout)
        
        # Preset buttons
        preset_layout = QHBoxLayout()
        
        near_btn = QPushButton("Near")
        near_btn.clicked.connect(lambda: self.set_focus_preset(cam_label, "near"))
        preset_layout.addWidget(near_btn)
        
        mid_btn = QPushButton("Mid")
        mid_btn.clicked.connect(lambda: self.set_focus_preset(cam_label, "mid"))
        preset_layout.addWidget(mid_btn)
        
        far_btn = QPushButton("Far")
        far_btn.clicked.connect(lambda: self.set_focus_preset(cam_label, "far"))
        preset_layout.addWidget(far_btn)
        
        layout.addLayout(preset_layout)
        
        # Auto focus button
        af_btn = QPushButton("🎯 Auto Focus")
        af_btn.clicked.connect(lambda: self.trigger_autofocus(cam_label))
        layout.addWidget(af_btn)
        
        self.focus_layout.addWidget(group)
        self.focus_controls[cam_label] = {
            'slider': focus_slider,
            'label': position_label
        }
        
    def set_focus_position(self, cam_label, position):
        """Set focus position for a camera"""
        cam_obj = getattr(self, cam_label, None)
        if not cam_obj or not self.focus_supported.get(cam_label, False):
            return
            
        try:
            cam_obj.set_controls({"AfMode": 0, "LensPosition": position})
            self.log_message(f"🎯 {cam_label}: Focus set to {position:.2f}")
        except Exception as e:
            self.log_message(f"❌ {cam_label}: Focus setting failed: {e}")
            
    def set_focus_preset(self, cam_label, preset):
        """Set focus to preset positions"""
        presets = {
            "near": 5.0,    # Close focus
            "mid": 2.0,     # Medium focus  
            "far": 0.1      # Far focus (closer to infinity)
        }
        
        if preset in presets:
            position = presets[preset]
            self.set_focus_position(cam_label, position)
            
            # Update slider
            if cam_label in self.focus_controls:
                self.focus_controls[cam_label]['slider'].setValue(int(position * 100))
                
    def trigger_autofocus(self, cam_label):
        """Trigger automatic autofocus"""
        cam_obj = getattr(self, cam_label, None)
        if not cam_obj or not self.focus_supported.get(cam_label, False):
            return
            
        try:
            self.log_message(f"🎯 {cam_label}: Triggering autofocus...")
            cam_obj.set_controls({
                "AfMode": 1,        # Auto mode
                "AfTrigger": 0      # Trigger autofocus
            })
            
            # Give it time to focus
            QTimer.singleShot(1000, lambda: self.check_autofocus_result(cam_label))
            
        except Exception as e:
            self.log_message(f"❌ {cam_label}: Autofocus failed: {e}")
            
    def check_autofocus_result(self, cam_label):
        """Check autofocus result and update controls"""
        cam_obj = getattr(self, cam_label, None)
        if not cam_obj:
            return
            
        try:
            metadata = cam_obj.capture_metadata()
            if "LensPosition" in metadata:
                lens_pos = metadata["LensPosition"]
                self.log_message(f"🎯 {cam_label}: Autofocus complete, position: {lens_pos:.2f}")
                
                # Update slider
                if cam_label in self.focus_controls:
                    self.focus_controls[cam_label]['slider'].setValue(int(lens_pos * 100))
                    
        except Exception as e:
            self.log_message(f"⚠️ {cam_label}: Could not read autofocus result: {e}")
            
    def on_parameter_changed(self, param_name, value):
        """Handle camera parameter changes"""
        self.log_message(f"📊 {param_name} changed to {value}")
        self.apply_camera_settings()
        
    def apply_camera_settings(self):
        """Apply current settings to cameras"""
        settings = {
            "ExposureTime": int(self.params['ExposureTime']['value']),
            "AnalogueGain": self.params['AnalogueGain']['value'],
            "Brightness": self.params['Brightness']['value'],
            "Contrast": self.params['Contrast']['value'], 
            "Saturation": self.params['Saturation']['value'],
            "Sharpness": self.params['Sharpness']['value']
        }
        
        if self.cam0_connected and self.cam0:
            try:
                self.cam0.set_controls(settings)
            except Exception as e:
                self.log_message(f"⚠️ Failed to apply settings to camera 0: {e}")
                
        if self.cam1_connected and self.cam1:
            try:
                self.cam1.set_controls(settings)
            except Exception as e:
                self.log_message(f"⚠️ Failed to apply settings to camera 1: {e}")
                
    def test_capture(self):
        """Comprehensive test of camera connection and photo capture capability"""
        self.log_message("🧪 Starting comprehensive camera test...")
        
        if not self.cam0_connected and not self.cam1_connected:
            self.log_message("❌ No cameras connected. Click 'Reconnect Cameras' first.")
            QMessageBox.warning(self, "No Cameras", "No cameras connected. Click 'Reconnect Cameras' first.")
            return
        
        success_count = 0
        total_cameras = 0
        
        try:
            # Test Camera 0
            if self.cam0_connected and self.cam0:
                total_cameras += 1
                self.log_message("🔍 Testing Camera 0...")
                
                try:
                    # Test capture request
                    req0 = self.cam0.capture_request()
                    if req0:
                        array = req0.make_array("main")
                        self.log_message(f"✅ Cam0 Array: {array.shape}, dtype: {array.dtype}, range: [{array.min()}-{array.max()}]")
                        
                        # Test photo capture
                        photo_path = f"test_cam0_{int(time.time())}.jpg"
                        if self.save_test_photo(req0, photo_path, "Camera 0"):
                            success_count += 1
                        
                        req0.release()
                    else:
                        self.log_message("❌ Cam0: Capture request failed")
                        
                    # Test metadata
                    metadata = self.cam0.capture_metadata()
                    if metadata:
                        exposure = metadata.get("ExposureTime", "Unknown")
                        gain = metadata.get("AnalogueGain", "Unknown") 
                        self.log_message(f"✅ Cam0 Metadata: Exposure={exposure}, Gain={gain}")
                    else:
                        self.log_message("⚠️ Cam0: No metadata available")
                        
                except Exception as e:
                    self.log_message(f"❌ Cam0 test failed: {e}")
                    
            # Test Camera 1
            if self.cam1_connected and self.cam1:
                total_cameras += 1
                self.log_message("🔍 Testing Camera 1...")
                
                try:
                    # Test capture request
                    req1 = self.cam1.capture_request()
                    if req1:
                        array = req1.make_array("main")
                        self.log_message(f"✅ Cam1 Array: {array.shape}, dtype: {array.dtype}, range: [{array.min()}-{array.max()}]")
                        
                        # Test photo capture
                        photo_path = f"test_cam1_{int(time.time())}.jpg"
                        if self.save_test_photo(req1, photo_path, "Camera 1"):
                            success_count += 1
                            
                        req1.release()
                    else:
                        self.log_message("❌ Cam1: Capture request failed")
                        
                    # Test metadata
                    metadata = self.cam1.capture_metadata()
                    if metadata:
                        exposure = metadata.get("ExposureTime", "Unknown")
                        gain = metadata.get("AnalogueGain", "Unknown")
                        self.log_message(f"✅ Cam1 Metadata: Exposure={exposure}, Gain={gain}")
                    else:
                        self.log_message("⚠️ Cam1: No metadata available")
                        
                except Exception as e:
                    self.log_message(f"❌ Cam1 test failed: {e}")
                    
            # Summary
            self.log_message(f"🧪 Test completed: {success_count}/{total_cameras} cameras working")
            
            if success_count == total_cameras:
                self.log_message("🎉 All connected cameras are working perfectly!")
                QMessageBox.information(self, "Test Success", 
                                      f"✅ All {total_cameras} cameras tested successfully!\n"
                                      f"Photos captured and saved for verification.")
            elif success_count > 0:
                QMessageBox.warning(self, "Partial Success", 
                                  f"⚠️ {success_count}/{total_cameras} cameras working.\n"
                                  f"Check log for details.")
            else:
                QMessageBox.critical(self, "Test Failed", 
                                   "❌ No cameras working properly.\n"
                                   "Check connections and try reconnecting.")
            
        except Exception as e:
            self.log_message(f"❌ Test capture error: {e}")
            QMessageBox.critical(self, "Test Error", f"Camera test failed:\n{str(e)}")
            
    def save_test_photo(self, request, filename, camera_name):
        """Save a test photo from capture request"""
        try:
            # Save as JPEG for quick verification
            request.save(filename)
            file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            
            if file_size > 1000:  # At least 1KB
                self.log_message(f"✅ {camera_name}: Test photo saved - {filename} ({file_size} bytes)")
                return True
            else:
                self.log_message(f"❌ {camera_name}: Test photo too small or failed - {filename}")
                return False
                
        except Exception as e:
            self.log_message(f"❌ {camera_name}: Failed to save test photo - {e}")
            return False
            
    def save_images(self):
        """Save images with processing"""
        if not self.cam0_connected and not self.cam1_connected:
            QMessageBox.warning(self, "Error", "No cameras connected!")
            return
            
        self.log_message("💾 Starting image capture and save...")
        
        # Run in background thread to prevent GUI blocking
        self.save_thread = threading.Thread(target=self._save_images_worker, daemon=True)
        self.save_thread.start()
        
    def _save_images_worker(self):
        """Worker thread for image saving"""
        try:
            # Create folder structure
            base_folder = "RPI_Captures"
            date_folder = datetime.now().strftime("%Y-%m-%d")
            save_folder = os.path.join(base_folder, date_folder)
            
            if not os.path.exists(save_folder):
                os.makedirs(save_folder, exist_ok=True)
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            params_str = "_".join(f"{p}{self.params[p]['value']:.2f}" for p in self.params)
            
            # Capture from cameras
            req0 = None
            req1 = None
            
            if self.cam0_connected and self.cam0:
                self.log_message("📸 Capturing from Camera 0...")
                req0 = self.cam0.capture_request()
                
            if self.cam1_connected and self.cam1:
                self.log_message("📸 Capturing from Camera 1...")
                req1 = self.cam1.capture_request()
                
            success_count = 0
            
            # Save DNG files if enabled
            if self.save_dng_checkbox.isChecked():
                self.log_message("💾 Saving DNG files...")
                try:
                    if req0:
                        dng_path0 = os.path.join(save_folder, f"cam0_{timestamp}_original_{params_str}.dng")
                        req0.save_dng(dng_path0)
                        self.log_message(f"✅ Saved: {os.path.basename(dng_path0)}")
                        success_count += 1
                        
                    if req1:
                        dng_path1 = os.path.join(save_folder, f"cam1_{timestamp}_original_{params_str}.dng")
                        req1.save_dng(dng_path1)
                        self.log_message(f"✅ Saved: {os.path.basename(dng_path1)}")
                        success_count += 1
                        
                except Exception as e:
                    self.log_message(f"❌ DNG save error: {e}")
                    
            # Save processed TIFF if enabled
            if self.save_tiff_checkbox.isChecked() and PROCESSING_AVAILABLE:
                self.log_message("🔄 Creating processed TIFF...")
                try:
                    img0 = req0.make_array("main") if req0 else None
                    img1 = req1.make_array("main") if req1 else None
                    
                    if img0 is not None or img1 is not None:
                        # Create combined image (simplified for this version)
                        combined = self.create_combined_image(img0, img1)
                        
                        if combined is not None:
                            tiff_path = os.path.join(save_folder, f"dual_{timestamp}_processed_{params_str}.tiff")
                            if self.save_processed_image_tiff(combined, tiff_path):
                                self.log_message(f"✅ Saved: {os.path.basename(tiff_path)}")
                                success_count += 1
                                
                except Exception as e:
                    self.log_message(f"❌ TIFF processing error: {e}")
                    
            self.log_message(f"🎉 Save operation complete! {success_count} files saved in {save_folder}")
            
        except Exception as e:
            self.log_message(f"❌ Save operation error: {e}")
        finally:
            # Always release requests
            try:
                if req0:
                    req0.release()
                if req1:
                    req1.release()
            except:
                pass
                
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
                
            if PROCESSING_AVAILABLE:
                imageio.imsave(output_path, image)
                return True
            else:
                self.log_message("❌ ImageIO not available for TIFF saving")
                return False
                
        except Exception as e:
            self.log_message(f"Failed to save TIFF {output_path}: {e}")
            return False
            
    def reset_all_parameters(self):
        """Reset all camera parameters to defaults"""
        for param_name, control in self.parameter_controls.items():
            control.reset_parameter()
            
    def save_settings(self):
        """Save current settings to file"""
        try:
            # Camera parameters
            camera_settings = {param: self.params[param]['value'] for param in self.params}
            
            # Combined settings
            all_settings = {
                'camera_parameters': camera_settings,
                'processing_settings': self.processing_settings,
                'distortion_params': self.distortion_params
            }
            
            with open('camera_settings_qt.json', 'w') as f:
                json.dump(all_settings, f, indent=4)
                
            self.log_message("💾 Settings saved successfully")
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            
        except Exception as e:
            self.log_message(f"❌ Failed to save settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{str(e)}")
            
    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists('camera_settings_qt.json'):
                with open('camera_settings_qt.json', 'r') as f:
                    all_settings = json.load(f)
                    
                # Load camera parameters
                if 'camera_parameters' in all_settings:
                    settings = all_settings['camera_parameters']
                    for param, value in settings.items():
                        if param in self.params:
                            self.params[param]['value'] = value
                            
                # Load distortion parameters
                if 'distortion_params' in all_settings:
                    self.distortion_params = all_settings['distortion_params']
                    
                self.log_message("📂 Loaded previous settings")
                
        except Exception as e:
            self.log_message(f"⚠️ Failed to load settings: {e}")
            
    def check_camera_connections(self):
        """Check for available IMX708 cameras and return connection info"""
        if not CAMERA_AVAILABLE:
            return []
        
        available_cameras = []
        self.log_message("🔍 Scanning for IMX708 cameras...")
        
        # Check camera indices 0-3 for IMX708 sensors
        for cam_idx in range(4):
            try:
                temp_cam = Picamera2(cam_idx)
                camera_info = temp_cam.camera_properties
                sensor_model = camera_info.get('Model', 'Unknown')
                
                temp_cam.close()
                
                # Check if it's an IMX708
                if 'imx708' in sensor_model.lower():
                    available_cameras.append({
                        'index': cam_idx,
                        'model': sensor_model,
                        'properties': camera_info
                    })
                    self.log_message(f"✅ Found IMX708 camera at index {cam_idx}: {sensor_model}")
                else:
                    self.log_message(f"⚠️ Camera at index {cam_idx} is not IMX708: {sensor_model}")
                    
            except Exception as e:
                # This is expected for non-existent cameras
                continue
                
        if not available_cameras:
            self.log_message("❌ No IMX708 cameras detected")
        else:
            self.log_message(f"🎯 Found {len(available_cameras)} IMX708 camera(s)")
            
        return available_cameras
    
    def reconnect_cameras(self):
        """Reconnect cameras with enhanced detection and PyQt5 compatibility"""
        self.log_message("🔌 Reconnecting cameras...")
        self.log_message(f"🔧 Using Qt Framework: {QT_FRAMEWORK}")
        
        # First check what cameras are available
        available_cameras = self.check_camera_connections()
        
        if not available_cameras:
            self.log_message("❌ No IMX708 cameras found. Check hardware connections.")
            QMessageBox.warning(self, "No Cameras", 
                              "No IMX708 cameras detected.\n"
                              "Please check hardware connections and try again.")
            return
        
        # Stop preview timer
        if hasattr(self, 'preview_timer') and self.preview_timer is not None:
            self.preview_timer.stop()
            self.preview_timer = None
        
        # Stop existing cameras
        if self.cam0:
            try:
                self.cam0.stop()
                self.cam0.close()
                self.log_message("🔄 Camera 0 stopped")
            except Exception as e:
                self.log_message(f"⚠️ Error stopping camera 0: {e}")
                
        if self.cam1:
            try:
                self.cam1.stop()
                self.cam1.close()
                self.log_message("🔄 Camera 1 stopped")
            except Exception as e:
                self.log_message(f"⚠️ Error stopping camera 1: {e}")
                
        # Clear previews
        if self.preview0:
            self.preview0.setParent(None)
        if self.preview1:
            self.preview1.setParent(None)
            
        self.cam0 = None
        self.cam1 = None
        self.preview0 = None
        self.preview1 = None
        self.cam0_connected = False
        self.cam1_connected = False
        
        # Wait for cleanup
        time.sleep(0.5)
        
        # Reinitialize
        QTimer.singleShot(1000, self.initialize_cameras)
        
    def emergency_stop(self):
        """Emergency stop all operations"""
        self.log_message("🛑 EMERGENCY STOP ACTIVATED")
        
        # Stop preview timer
        if hasattr(self, 'preview_timer') and self.preview_timer is not None:
            self.preview_timer.stop()
            
        try:
            if self.cam0:
                self.cam0.stop()
            if self.cam1:
                self.cam1.stop()
        except:
            pass
            
        self.cam0_connected = False
        self.cam1_connected = False
        self.update_connection_status()
        
    def update_connection_status(self):
        """Update GUI status based on camera connections"""
        if self.cam0_connected and self.cam1_connected:
            status = "Both cameras connected - Ready!"
            self.preview_status.setText("Dual camera preview active")
        elif self.cam0_connected or self.cam1_connected:
            connected = "Camera 0" if self.cam0_connected else "Camera 1"
            status = f"Only {connected} connected"
            self.preview_status.setText(f"Single camera preview active")
        else:
            status = "No cameras connected"
            self.preview_status.setText("No cameras detected")
            
        self.status_bar.showMessage(status)
        
    def closeEvent(self, event):
        """Handle application closing"""
        self.log_message("🔄 Shutting down application...")
        
        # Stop preview timer
        if hasattr(self, 'preview_timer') and self.preview_timer is not None:
            self.preview_timer.stop()
        
        # Save settings
        self.save_settings()
        
        # Stop cameras
        try:
            if self.cam0:
                self.cam0.stop()
            if self.cam1:
                self.cam1.stop()
        except:
            pass
            
        event.accept()
        
    def showEvent(self, event):
        """Override showEvent - no automatic camera initialization"""
        super().showEvent(event)
        # Camera initialization is now manual via reconnect button
        pass


def install_qt_dependencies():
    """Provide instructions for installing Qt dependencies"""
    print("\n" + "="*60)
    print("🔧 QT DEPENDENCIES INSTALLATION GUIDE")
    print("="*60)
    print("\nTo fix Qt platform plugin issues on Raspberry Pi:")
    print("\n1. Install required system packages:")
    print("   sudo apt update")
    print("   sudo apt install -y libxcb-cursor0 libxcb-cursor-dev")
    print("   sudo apt install -y qt6-base-dev qt6-wayland")
    print("   sudo apt install -y libqt6widgets6 libqt6gui6 libqt6core6")
    print("\n2. Install Python Qt packages:")
    print("   pip install PySide6")
    print("   # OR alternatively:")
    print("   pip install PyQt5")
    print("\n3. For headless operation (SSH/VNC):")
    print("   export QT_QPA_PLATFORM=offscreen")
    print("   export DISPLAY=:0  # if using VNC")
    print("\n4. For X11 forwarding over SSH:")
    print("   ssh -X user@raspberry-pi-ip")
    print("="*60)

def run_cli_mode():
    """Run a simple command-line interface when Qt is not available"""
    print("\n" + "="*50)
    print("📟 COMMAND LINE MODE")
    print("="*60)
    print("Qt GUI not available. Running basic camera test...")
    
    if not CAMERA_AVAILABLE:
        print("❌ No camera libraries available")
        return False
    
    try:
        # Simple camera test
        print("🔄 Testing camera connection...")
        cam = Picamera2(0)
        config = cam.create_still_configuration()
        cam.configure(config)
        cam.start()
        
        print("✅ Camera 0 connected successfully")
        print("📸 Taking test capture...")
        
        # Capture test image
        import time
        time.sleep(2)  # Let camera stabilize
        array = cam.capture_array()
        print(f"✅ Captured image: {array.shape}, dtype: {array.dtype}")
        
        cam.stop()
        print("🎉 Camera test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Camera test failed: {e}")
        return False

def main():
    """Main entry point with fallback handling"""
    print("🚀 Starting Efficient Dual IMX708 Camera Control...")
    
    # Check if Qt is available
    if not QT_AVAILABLE:
        print("❌ Qt not available for GUI mode")
        install_qt_dependencies()
        
        # Offer CLI mode
        print("\n" + "="*50)
        response = input("Would you like to run camera test in CLI mode? (y/n): ")
        if response.lower() in ['y', 'yes']:
            success = run_cli_mode()
            return 0 if success else 1
        else:
            print("Exiting. Install Qt dependencies and try again.")
            return 1
    
    try:
        # Try to create QApplication
        app = QApplication(sys.argv)
        print("✅ Qt Application created successfully")
        
        # CRITICAL: Initialize OpenCV AFTER Qt Application is created
        initialize_opencv()
        
        # Set application properties
        app.setApplicationName("Efficient Dual IMX708 Camera Control")
        app.setApplicationVersion("2.0.0")
        
        # Try different Qt platforms if the default fails
        platforms_to_try = ['xcb', 'wayland', 'offscreen']
        window = None
        
        for platform in platforms_to_try:
            try:
                if platform != os.environ.get('QT_QPA_PLATFORM', ''):
                    print(f"🔄 Trying Qt platform: {platform}")
                    os.environ['QT_QPA_PLATFORM'] = platform
                
                # Create main window
                window = EfficientDualCameraGUI()
                window.show()
                
                print(f"✅ GUI started successfully with platform: {platform}")
                break
                
            except Exception as e:
                print(f"❌ Platform {platform} failed: {e}")
                if window:
                    window = None
                continue
        
        if window is None:
            print("❌ All Qt platforms failed")
            return 1
        
        # Run the application
        return app.exec_()
        
    except Exception as e:
        print(f"❌ Failed to start GUI: {e}")
        print("\nTrying CLI mode as fallback...")
        success = run_cli_mode()
        return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 