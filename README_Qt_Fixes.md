# Qt Platform Plugin Fixes for Raspberry Pi Camera GUI

## Problem
The camera GUI was failing on Raspberry Pi with Qt platform plugin errors:
- `xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin`
- `Could not load the Qt platform plugin "xcb"`
- `This application failed to start because no Qt platform plugin could be initialized`

## Solution
The `GUI_IMX708_Qt_Complete.py` has been updated with comprehensive fixes:

### 1. Environment Setup
- Automatic Qt platform detection and configuration
- OpenCV Qt plugin conflict resolution
- Support for multiple Qt platforms (xcb, wayland, offscreen)

### 2. Graceful Fallbacks
- PyQt5 fallback if PySide6 fails
- Camera operation without Qt preview if QtGlPreview unavailable
- Command-line mode if Qt completely fails
- Clear error messages and installation instructions

### 3. Platform-Specific Handling
- Raspberry Pi optimizations (software rendering, disabled OpenGL)
- SSH/VNC environment detection
- Headless operation support

## Quick Setup

### On Raspberry Pi:
```bash
# Make setup script executable and run it
chmod +x setup_qt_rpi.sh
./setup_qt_rpi.sh

# Or manually install dependencies
sudo apt update
sudo apt install -y libxcb-cursor0 libxcb-cursor-dev qt6-base-dev qt6-wayland
pip install PySide6 PyQt5
```

### Environment Variables:
```bash
# For normal desktop use
export QT_QPA_PLATFORM=xcb

# For VNC
export QT_QPA_PLATFORM=xcb
export DISPLAY=:0

# For headless/SSH without display
export QT_QPA_PLATFORM=offscreen

# For Wayland
export QT_QPA_PLATFORM=wayland
```

## Running the GUI

### Normal Mode (with GUI):
```bash
python GUI_IMX708_Qt_Complete.py
```

### If Qt fails, the application will:
1. Show detailed error information
2. Provide installation instructions
3. Offer to run in command-line mode for basic camera testing

### Manual CLI Mode:
```bash
# Set environment to disable GUI and test cameras
export QT_QPA_PLATFORM=offscreen
python GUI_IMX708_Qt_Complete.py
# Then choose 'y' for CLI mode
```

## Features Still Available Without Qt Preview

Even if QtGlPreview fails, the GUI will still provide:
- ✅ Camera parameter controls (exposure, gain, focus, etc.)
- ✅ Image capture and saving (DNG + processed TIFF)
- ✅ Settings persistence
- ✅ Focus control (if supported by cameras)
- ✅ Processing pipeline (distortion correction, cropping, etc.)
- ⚠️ No live preview (placeholder shown instead)

## SSH Usage

### With X11 forwarding:
```bash
ssh -X user@raspberry-pi-ip
cd /path/to/camera/project
python GUI_IMX708_Qt_Complete.py
```

### Headless operation:
```bash
ssh user@raspberry-pi-ip
export QT_QPA_PLATFORM=offscreen
cd /path/to/camera/project
python GUI_IMX708_Qt_Complete.py
```

## Troubleshooting

### If you still get Qt errors:
1. Run `setup_qt_rpi.sh` to install all dependencies
2. Try different platforms: `export QT_QPA_PLATFORM=wayland` or `=offscreen`
3. Use CLI mode for basic camera functionality
4. Check if `DISPLAY` environment variable is set correctly for VNC

### If cameras don't work:
- The GUI will still start and show simulation mode
- Use the CLI mode to test basic camera connectivity
- Check if cameras are properly connected and recognized by the system

## Files Added/Modified
- `GUI_IMX708_Qt_Complete.py` - Updated with comprehensive Qt fixes
- `setup_qt_rpi.sh` - Automated dependency installation script (Linux)
- `setup_qt_rpi.bat` - Setup instructions for Windows users
- `README_Qt_Fixes.md` - This documentation

The application is now much more robust and should work across different Raspberry Pi configurations, SSH connections, VNC setups, and even when Qt components are partially missing. 