#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Ensure TDLib is present
if [ ! -f "libtdjson.so" ]; then
    echo "Downloading pre-compiled TDLib for Render (Ubuntu x86_64)..."
    curl -L https://github.com/vysheng/tdlib-static/releases/download/v1.8.0/libtdjson.so -o libtdjson.so
fi
