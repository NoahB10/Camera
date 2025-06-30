# Dual IMX708 Camera Control with UV

This project provides a GUI for controlling dual IMX708 cameras with distortion and perspective correction. It uses UV for modern Python package management.

## Prerequisites

1. **Install UV** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **System Requirements** (Raspberry Pi):
   ```bash
   sudo apt-get update
   sudo apt-get install python3-tk python3-dev build-essential
   ```

## Quick Start with UV

### 1. Initialize the project
```bash
# Clone or navigate to your project directory
cd /path/to/your/camera/project

# Install dependencies using UV
uv sync
```

### 2. Run the GUI application
```bash
# Option 1: Using the script entry point
uv run dual-camera-gui

# Option 2: Run the module directly
uv run python GUI_IMX708_Dirsotion_Correction_v1.2.py

# Option 3: Run in the UV environment
uv run python -m GUI_IMX708_Dirsotion_Correction_v1_2
```

### 3. Development workflow
```bash
# Install development dependencies
uv sync --group dev

# Add new dependencies
uv add opencv-python
uv add --group dev pytest

# Run with specific Python version
uv run --python 3.11 python GUI_IMX708_Dirsotion_Correction_v1.2.py

# Format code (if dev dependencies installed)
uv run black .
uv run isort .
```

## Raspberry Pi Specific Setup

### For Raspberry Pi with limited resources:
```bash
# Use piwheels for faster ARM package installation
export UV_INDEX_URL="https://www.piwheels.org/simple"
uv sync

# Or configure in .uv.toml (already done in this project)
```

### Enable X11 forwarding for SSH (if running remotely):
```bash
ssh -X username@raspberry-pi-ip
# Then run the GUI commands above
```

## Available Commands

After setting up with UV, you can use these commands:

### Run the GUI
```bash
uv run dual-camera-gui
```

### Run with debugging
```bash
uv run python GUI_IMX708_Dirsotion_Correction_v1.2.py
```

### Install additional packages
```bash
uv add package-name
```

### Show dependency tree
```bash
uv tree
```

### Create a requirements.txt (if needed for compatibility)
```bash
uv export --format requirements-txt --output-file requirements.txt
```

## Project Structure

```
.
├── GUI_IMX708_Dirsotion_Correction_v1.2.py  # Main GUI application
├── pyproject.toml                            # Project configuration & dependencies
├── .uv.toml                                  # UV-specific configuration
├── distortion_coefficients_dual.json         # Camera calibration data
├── README_UV.md                              # This file
└── ...other project files
```

## Features

- **Dual Camera Control**: Control two IMX708 cameras simultaneously
- **Real-time Preview**: Live view of both cameras side-by-side
- **Image Processing Pipeline**:
  - Automatic cropping
  - Radial distortion correction
  - Perspective correction (if coefficients available)
  - Image rotation
- **File Output**: 
  - Combined TIFF files (processed)
  - Original DNG files (unprocessed)
- **Calibration Support**: Load custom distortion coefficients
- **Default Fallback**: Works with built-in defaults if no calibration files found

## Troubleshooting

### GUI doesn't appear
1. **Check X11 forwarding**: `echo $DISPLAY`
2. **Install tkinter**: `sudo apt-get install python3-tk`
3. **Check UV environment**: `uv run python -c "import tkinter; print('tkinter OK')"`

### Camera not found
1. **Check cameras**: `v4l2-ctl --list-devices`
2. **Permissions**: Add user to video group: `sudo usermod -a -G video $USER`
3. **Restart**: Log out and back in for group changes

### Package installation issues
1. **Update UV**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Clear cache**: `uv cache clean`
3. **Use piwheels**: Set `UV_INDEX_URL="https://www.piwheels.org/simple"`

### Memory issues on Raspberry Pi
1. **Increase swap**: 
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=1024
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

## Configuration

The project uses two configuration files:

### pyproject.toml
- Project metadata and dependencies
- Script entry points
- Tool configurations (black, isort)

### .uv.toml
- UV-specific settings
- Python version preferences
- Index URLs for package sources
- Build configurations

## Contributing

1. Install development dependencies: `uv sync --group dev`
2. Format code: `uv run black . && uv run isort .`
3. Run tests: `uv run pytest` (if tests are added)
4. Update dependencies: `uv add package-name` or `uv add --group dev dev-package`

## License

MIT License - see project files for details. 