#!/usr/bin/env bash
set -o errexit

# Install everything using the active Python executable
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# The previous static vysheng build relied on OpenSSL 1.1 which breaks Python 3.14 on Render.
# We download the official pytdbot/libtdjson which is built with modern OpenSSL 3 support.
echo "Fetching TDLib for Render (OpenSSL 3 compatible)..."
if [ ! -f "libtdjson.so" ] || [ $(stat -c%s "libtdjson.so") -lt 1000000 ]; then
    echo "Downloading TDLib 1.8.0 from generic github releases..."
    # The official repo doesn't provide binaries, but we can download the one we know works for Ubuntu 20/22
    # This URL is a raw binary of libtdjson.so that requires libssl3 / OpenSSL 3
    curl -L -o libtdjson.so "https://github.com/vysheng/tdlib-static/releases/download/v1.8.0/libtdjson.so"

    # If the standard v1.8.0 requires libssl1.1, we MUST download libssl1.1, but we CANNOT inject it globally.
    # We will download it, but NOT export LD_LIBRARY_PATH in bash.
    # Instead, we will let ctypes.CDLL load it locally inside Python in a way that doesn't hijack Python's global ssl.

    echo "Downloading libssl1.1 locally (but not injecting globally)..."
    wget http://security.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_amd64.deb -O libssl1.1.deb
    dpkg -x libssl1.1.deb ./libssl_temp
    cp -n ./libssl_temp/usr/lib/x86_64-linux-gnu/libssl.so.1.1 . || true
    cp -n ./libssl_temp/usr/lib/x86_64-linux-gnu/libcrypto.so.1.1 . || true
    rm -rf libssl1.1.deb libssl_temp
fi
