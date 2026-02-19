#!/bin/bash
set -euo pipefail

# Check wget is installed
if ! command -v wget >/dev/null 2>&1; then
    echo "Installing wget..."
    sudo apt update
    sudo apt install -y wget
    echo "wget installed successfully."
    printf "wget version: %s\n" "$(wget --version | head -n 1)"
else
    echo "wget is already installed."
    printf "wget version: %s\n" "$(wget --version | head -n 1)"
fi

# Download and install MediaMTX
echo "Downloading MediaMTX..."
wget -O mediamtx_v1.16.1_linux_amd64.tar.gz \
  https://github.com/bluenviron/mediamtx/releases/download/v1.16.1/mediamtx_v1.16.1_linux_amd64.tar.gz

CURRENT_DIR="$(pwd)"
INSTALL_DIR="$CURRENT_DIR/thirdparty/mediamtx"
mkdir -p "$INSTALL_DIR"

echo "Extracting MediaMTX..."
tar -xzf mediamtx_v1.16.1_linux_amd64.tar.gz -C "$INSTALL_DIR"

echo "MediaMTX installed successfully at $INSTALL_DIR/mediamtx"

# (선택) 버전 확인 - 플래그가 다를 수 있어 fallback 처리
echo -n "MediaMTX version: "
"$INSTALL_DIR/mediamtx" --version 2>/dev/null || "$INSTALL_DIR/mediamtx" -version 2>/dev/null || echo "(unknown)"

echo "Cleaning up..."
rm -f mediamtx_v1.16.1_linux_amd64.tar.gz

# ---- 여기서 config 덮어쓰기 스크립트 호출 (Done 전에) ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/write_mediamtx_config.sh" "$INSTALL_DIR"

echo "Done."
