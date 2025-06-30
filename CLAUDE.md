# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a dual IMX708 camera control system for Raspberry Pi with distortion and perspective correction capabilities. The project uses Python with multiple GUI frameworks (Tkinter and PyQt) and modern UV package management.

## Development Commands

### Setup and Dependencies
```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --group dev

# Add new packages
uv add package-name
uv add --group dev dev-package-name
```

### Running the Application
```bash
# Main GUI application
uv run dual-camera-gui
# or
uv run python GUI_IMX708_Dirsotion_Correction_v1.2.py

# Alternative GUIs
uv run python simple_dual_camera_gui.py        # Tkinter version
uv run python simple_dual_camera_gui_pyqt.py   # PyQt version

# Utility scripts
uv run python Find_Camera.py    # Detect connected cameras
uv run python Focus.py          # Camera focusing utility
```

### Code Quality Tools
```bash
# Format code
uv run black .
uv run isort .

# Lint code
uv run flake8

# Run tests (when available)
uv run pytest
```

## Architecture

### Core Components

1. **Camera Control Layer**: Interfaces with Picamera2 library to control dual IMX708 cameras
2. **Image Processing Pipeline**:
   - Automatic cropping
   - Radial distortion correction (using discorpy)
   - Perspective correction
   - Image rotation
3. **GUI Layer**: Multiple implementations (Tkinter and PyQt) providing user interface
4. **Output Management**: Saves processed TIFF files and original DNG files

### Key Files

- `GUI_IMX708_Dirsotion_Correction_v1.2.py`: Latest main GUI application with full feature set
- `image_post_processing_v1.1.py`: Post-processing pipeline implementation
- `img_cvt_utils.py`: Image conversion utilities
- `distortion_coefficients_dual.json`: Stores camera calibration data

### External Dependencies

The project includes ArduCam EVK SDK in `evk_sdk/` directory with C/C++ libraries for camera control.

## Debugging and Troubleshooting

### Diagnostic Tools
```bash
# Run comprehensive system diagnostic
python3 test_raspberry_pi_debug.py

# Test camera detection without hardware
python3 debug_camera_mock.py

# Test GUI components independently
python3 debug_gui_issues.py
```

### Common Issues
1. **Missing libcamera**: Install with `sudo apt install python3-picamera2 libcamera-tools`
2. **Permission denied**: Add user to video group with `sudo usermod -a -G video $USER`
3. **Camera not detected**: Enable camera interface in `raspi-config` and reboot
4. **GUI not appearing**: Use `ssh -X` for X11 forwarding

See `DEBUGGING.md` for comprehensive troubleshooting guide.

## Important Implementation Details

1. **Camera Detection**: The system expects two IMX708 cameras connected. Camera detection is handled through Picamera2 API.

2. **Distortion Correction**: Uses discorpy library with stored coefficients. Falls back to default values if calibration file is missing.

3. **File Naming**: Output files follow pattern: `{user_prefix}_{timestamp}_combined.tiff` for processed images and `{user_prefix}_{timestamp}_camera{N}_original.dng` for raw files.

4. **Threading**: GUI applications use threading to prevent UI blocking during image capture and processing.

5. **Error Handling**: Camera initialization failures and processing errors are handled with user-friendly error dialogs.