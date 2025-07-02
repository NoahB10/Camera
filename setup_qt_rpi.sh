#!/bin/bash

echo "========================================"
echo "🔧 Qt Setup for Raspberry Pi Camera GUI"
echo "========================================"

# Update system
echo "📦 Updating system packages..."
sudo apt update

# Install Qt6 system dependencies
echo "🔧 Installing Qt6 system packages..."
sudo apt install -y \
    libxcb-cursor0 \
    libxcb-cursor-dev \
    qt6-base-dev \
    qt6-wayland \
    libqt6widgets6 \
    libqt6gui6 \
    libqt6core6 \
    libqt6opengl6 \
    libqt6openglwidgets6

# Install Qt5 as fallback
echo "🔧 Installing Qt5 fallback packages..."
sudo apt install -y \
    python3-pyqt5 \
    python3-pyqt5.qtwidgets \
    qtbase5-dev \
    qt5-qmake

# Install Python packages
echo "🐍 Installing Python Qt packages..."
pip install PySide6 PyQt5

# Set up environment variables
echo "🌍 Setting up environment variables..."
cat >> ~/.bashrc << 'EOF'

# Qt Environment for Camera GUI
export QT_QPA_PLATFORM=xcb
export QT_XCB_GL_INTEGRATION=none
export QT_QUICK_BACKEND=software

# For headless operation (uncomment if needed)
# export QT_QPA_PLATFORM=offscreen

EOF

echo "✅ Setup complete!"
echo ""
echo "📝 Usage notes:"
echo "1. Restart your terminal or run: source ~/.bashrc"
echo "2. For SSH with X11 forwarding: ssh -X user@pi-ip"
echo "3. For VNC: export DISPLAY=:0"
echo "4. For headless: export QT_QPA_PLATFORM=offscreen"
echo ""
echo "🚀 Now try running the camera GUI!" 