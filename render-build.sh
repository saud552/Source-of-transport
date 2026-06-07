#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Download pre-compiled TDLib for Linux (Ubuntu/Debian)
# For Render, we need a .so file compiled for Linux x86_64.
if [ ! -f "libtdjson.so" ]; then
    echo "Downloading pre-compiled TDLib..."
    # Using a reputable binary source for libtdjson.so (Common for bot developers)
    curl -L https://github.com/tdlib/td/releases/download/v1.8.0/libtdjson.so -o libtdjson.so || true
fi
