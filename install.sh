#!/bin/bash
set -e

# === LicMan Installer ===
# Usage: ./install.sh [-port PORT]

PORT="58080"

while [ $# -gt 0 ]; do
    case "$1" in
        -port)
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [-port PORT]"
            echo "  -port  Web port number (default: 58080)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-port PORT]"
            exit 1
            ;;
    esac
done

# Detect install directory
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "========================================="
echo "  LicMan Installer"
echo "  Install path: $INSTALL_DIR"
echo "  Web port:     $PORT"
echo "========================================="

# Verify Python
PYTHON="$INSTALL_DIR/python/bin/python3"
if [ ! -f "$PYTHON" ]; then
    # Try system python
    PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || echo "")
    if [ -z "$PYTHON" ]; then
        echo "ERROR: Python3 not found. Install Python 3.8+ or use the embedded python."
        exit 1
    fi
    echo "Using system Python: $PYTHON"
else
    echo "Using embedded Python: $PYTHON"
fi

# Patch run.py - shebang
if [ -f "$INSTALL_DIR/app/run.py" ]; then
    echo "Patching app/run.py..."
    sed -i "1s|.*|#!$PYTHON|" "$INSTALL_DIR/app/run.py"
    sed -i "s|socketio.run(app, host='0.0.0.0', port=[0-9]*|socketio.run(app, host='0.0.0.0', port=$PORT|" "$INSTALL_DIR/app/run.py"
fi

# Patch bin/licman
if [ -f "$INSTALL_DIR/bin/licman" ]; then
    echo "Patching bin/licman..."
    sed -i "s|^LICMAN_HOME=.*|LICMAN_HOME=\"$INSTALL_DIR\"|" "$INSTALL_DIR/bin/licman"
    sed -i "s|^PYTHON=.*|PYTHON=\"$PYTHON\"|" "$INSTALL_DIR/bin/licman"
    sed -i "s|^PORT=.*|PORT=\"$PORT\"|" "$INSTALL_DIR/bin/licman"
    sed -i "s|^HOST=.*|HOST=\"0.0.0.0\"|" "$INSTALL_DIR/bin/licman"
    chmod +x "$INSTALL_DIR/bin/licman"
fi

# Create directories
mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/logs"

# Install Python dependencies if using embedded Python
if [ -f "$INSTALL_DIR/python/bin/pip3" ]; then
    echo "Installing Python dependencies..."
    "$INSTALL_DIR/python/bin/pip3" install --quiet flask flask-socketio 2>/dev/null || {
        echo "Note: pip install may have failed. If dependencies are present it's OK."
    }
fi

echo ""
echo "Installation complete!"
echo "  Start:  $INSTALL_DIR/bin/licman start"
echo "  Access: http://localhost:$PORT"
echo ""
