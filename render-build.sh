#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Render uses Ubuntu 22.04+ natively, which drops libssl1.1. We must install it manually for TDLib 1.8.0
echo "Installing libssl1.1 dependency for TDLib..."
wget http://security.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_amd64.deb -O libssl1.1.deb
dpkg -x libssl1.1.deb ./libssl_temp
mkdir -p /usr/lib/x86_64-linux-gnu || true # In case we don't have root
cp -n ./libssl_temp/usr/lib/x86_64-linux-gnu/libssl.so.1.1 . || true
cp -n ./libssl_temp/usr/lib/x86_64-linux-gnu/libcrypto.so.1.1 . || true
rm -rf libssl1.1.deb libssl_temp
export LD_LIBRARY_PATH="$(pwd):$LD_LIBRARY_PATH"
echo "Exporting LD_LIBRARY_PATH to include current directory for libssl"

# Ensure TDLib is present
if [ ! -f "libtdjson.so" ]; then
    echo "Downloading pre-compiled TDLib for Render (Ubuntu x86_64)..."
    curl -L https://github.com/vysheng/tdlib-static/releases/download/v1.8.0/libtdjson.so -o libtdjson.so
fi
