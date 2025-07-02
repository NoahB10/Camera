#!/bin/bash
# Qt5 Setup Script for Raspberry Pi - Dual IMX708 Camera GUI
# Optimized for PyQt5 + Picamera2 compatibility

set -e  # Exit on any error

echo "🍓 Qt5 Setup for Raspberry Pi - Dual IMX708 Camera GUI"
echo "======================================================"
echo "This script will install Qt5 dependencies for optimal Picamera2 compatibility"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    print_warning "This script is optimized for Raspberry Pi but will continue anyway"
fi

# Update system packages
print_header "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Qt5 system packages
print_header "🔧 Installing Qt5 system packages..."

# Core Qt5 packages
sudo apt install -y \
    qt5-default \
    qtbase5-dev \
    qtbase5-dev-tools \
    libqt5widgets5 \
    libqt5gui5 \
    libqt5core5a \
    libqt5opengl5 \
    libqt5opengl5-dev

# Qt5 platform plugins and dependencies
sudo apt install -y \
    libxcb1 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxcb-cursor-dev \
    libxcb-keysyms1 \
    libxcb-image0 \
    libxcb-shm0 \
    libxcb-icccm4 \
    libxcb-sync1 \
    libxcb-render-util0 \
    libxcb-xfixes0 \
    libxcb-shape0 \
    libxcb-randr0

# X11 and graphics libraries
sudo apt install -y \
    libx11-xcb1 \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libegl1-mesa-dev \
    libgles2-mesa-dev

# Font packages (Qt5 needs fonts)
sudo apt install -y \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
    fontconfig

# Additional development tools
sudo apt install -y \
    build-essential \
    cmake \
    pkg-config \
    python3-dev \
    python3-pip

print_status "Qt5 system packages installed successfully"

# Install Python packages
print_header "🐍 Installing Python Qt5 packages..."

# Upgrade pip first
python3 -m pip install --upgrade pip

# Install PyQt5 and related packages
python3 -m pip install \
    PyQt5==5.15.10 \
    PyQt5-Qt5==5.15.2 \
    PyQt5-sip==12.13.0 \
    PyQt5-tools

print_status "PyQt5 Python packages installed successfully"

# Install Picamera2 and dependencies
print_header "📸 Installing Picamera2 and camera dependencies..."

# Install libcamera and picamera2
sudo apt install -y \
    libcamera-dev \
    libcamera-apps \
    python3-libcamera \
    python3-picamera2

# Install additional Python camera packages
python3 -m pip install \
    picamera2 \
    opencv-python-headless \
    numpy \
    Pillow

print_status "Camera packages installed successfully"

# Install additional dependencies for the GUI
print_header "🎨 Installing additional GUI dependencies..."

python3 -m pip install \
    imageio \
    scipy \
    matplotlib

print_status "Additional dependencies installed successfully"

# Configure Qt5 environment
print_header "⚙️ Configuring Qt5 environment..."

# Create Qt5 environment configuration
QT_ENV_FILE="$HOME/.qt5_camera_env"
cat > "$QT_ENV_FILE" << 'EOF'
# Qt5 Camera GUI Environment Configuration
export QT_QPA_PLATFORM_PLUGIN_PATH=""
export QT_QPA_PLATFORM="xcb"
export QT_XCB_GL_INTEGRATION="none"
export QT_QUICK_BACKEND="software"
export QT_AUTO_SCREEN_SCALE_FACTOR="0"
export QT_SCALE_FACTOR="1"
export QT_LOGGING_RULES="*.debug=false;qt.qpa.plugin.debug=false"
export QT_THREAD_POOL_MAX_THREADS="4"

# OpenCV conflict prevention
export OPENCV_VIDEOIO_PRIORITY_MSMF="0"
export OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS="0"
export OPENCV_THREADING="0"
export OPENCV_NUM_THREADS="1"

# Font configuration
export QT_QPA_FONTDIR="/usr/share/fonts"

# For VNC/SSH usage
# export DISPLAY=:0
# export QT_QPA_PLATFORM="offscreen"  # Uncomment for headless
EOF

print_status "Qt5 environment configuration created at $QT_ENV_FILE"

# Add to bashrc if not already present
if ! grep -q "qt5_camera_env" "$HOME/.bashrc"; then
    echo "" >> "$HOME/.bashrc"
    echo "# Qt5 Camera GUI Environment" >> "$HOME/.bashrc"
    echo "source $QT_ENV_FILE" >> "$HOME/.bashrc"
    print_status "Added Qt5 environment to .bashrc"
fi

# Create desktop launcher
print_header "🖥️ Creating desktop launcher..."

DESKTOP_FILE="$HOME/Desktop/IMX708_Camera_GUI.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=IMX708 Camera GUI
Comment=Dual IMX708 Camera Control with Qt5
Exec=bash -c 'source $QT_ENV_FILE && cd "$HOME/Documents/Camera_GIT/Camera" && python3 GUI_IMX708_Qt_Complete.py'
Icon=camera-video
Terminal=true
Categories=Graphics;Photography;
Keywords=camera;picamera2;qt5;
EOF

chmod +x "$DESKTOP_FILE"
print_status "Desktop launcher created at $DESKTOP_FILE"

# Create startup script
print_header "🚀 Creating startup script..."

STARTUP_SCRIPT="$HOME/start_camera_gui.sh"
cat > "$STARTUP_SCRIPT" << EOF
#!/bin/bash
# Startup script for IMX708 Camera GUI with Qt5

# Load Qt5 environment
source $QT_ENV_FILE

# Navigate to camera directory (adjust path as needed)
CAMERA_DIR="\$HOME/Documents/Camera_GIT/Camera"
if [ -d "\$CAMERA_DIR" ]; then
    cd "\$CAMERA_DIR"
else
    echo "⚠️ Camera directory not found at \$CAMERA_DIR"
    echo "Please adjust the path in \$0"
    exit 1
fi

# Check if GUI file exists
if [ ! -f "GUI_IMX708_Qt_Complete.py" ]; then
    echo "❌ GUI_IMX708_Qt_Complete.py not found in current directory"
    exit 1
fi

echo "🚀 Starting IMX708 Camera GUI with Qt5..."
echo "📁 Working directory: \$(pwd)"
echo "🔧 Qt Platform: \$QT_QPA_PLATFORM"

# Start the GUI
python3 GUI_IMX708_Qt_Complete.py
EOF

chmod +x "$STARTUP_SCRIPT"
print_status "Startup script created at $STARTUP_SCRIPT"

# Run basic tests
print_header "🧪 Running basic compatibility tests..."

# Test Qt5 installation
print_status "Testing Qt5 installation..."
if python3 -c "from PyQt5.QtWidgets import QApplication; print('✅ PyQt5 import successful')" 2>/dev/null; then
    print_status "PyQt5 installation verified"
else
    print_error "PyQt5 installation test failed"
fi

# Test Picamera2 installation
print_status "Testing Picamera2 installation..."
if python3 -c "from picamera2 import Picamera2; print('✅ Picamera2 import successful')" 2>/dev/null; then
    print_status "Picamera2 installation verified"
else
    print_warning "Picamera2 installation test failed (this is normal if no cameras are connected)"
fi

# Test Picamera2 Qt widgets
print_status "Testing Picamera2 Qt5 widgets..."
if python3 -c "from picamera2.previews.qt import QGlPicamera2, QPicamera2; print('✅ Picamera2 Qt5 widgets import successful')" 2>/dev/null; then
    print_status "Picamera2 Qt5 widgets installation verified"
else
    print_warning "Picamera2 Qt5 widgets test failed"
fi

# Final instructions
print_header "🎉 Installation Complete!"
echo ""
print_status "Qt5 setup completed successfully!"
echo ""
echo "📋 NEXT STEPS:"
echo "1. 🔄 Restart your terminal or run: source ~/.bashrc"
echo "2. 🔌 Connect your IMX708 cameras"
echo "3. 🚀 Start the GUI using one of these methods:"
echo "   • Double-click the desktop launcher"
echo "   • Run: $STARTUP_SCRIPT"
echo "   • Navigate to camera directory and run: python3 GUI_IMX708_Qt_Complete.py"
echo ""
echo "🔧 TROUBLESHOOTING:"
echo "• For VNC/remote desktop: export DISPLAY=:0"
echo "• For SSH/headless: export QT_QPA_PLATFORM=offscreen"
echo "• For display issues: sudo raspi-config → Advanced → GL Driver → Legacy"
echo ""
echo "📁 Important files created:"
echo "• Environment: $QT_ENV_FILE"
echo "• Startup script: $STARTUP_SCRIPT"
echo "• Desktop launcher: $DESKTOP_FILE"
echo ""
print_status "Enjoy your Qt5-powered IMX708 camera GUI! 📸" 