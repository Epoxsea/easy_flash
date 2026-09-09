# Builder image for the Linux standalone build.
#
# The GitHub Actions workflow (publish-builder.yml) publishes this image to
# GHCR (ghcr.io/<owner>/easy-flash-builder) and the Linux build job pulls it
# as its `container:` so the environment is reproducible and cached.
#
# IMPORTANT: PyInstaller does NOT cross-compile. This image can only build the
# Linux binary natively. Windows and macOS builds run on their own native
# GitHub runners — a Linux container cannot produce a Windows .exe or macOS
# .app (and macOS cannot be containerized at all).
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# git            -> actions/checkout runs inside this container
# binutils       -> objdump/ldd used by PyInstaller's binary analysis
# python3-tk     -> tkinter (bundled into the app)
# python-is-python3 -> the `python` shim the build scripts invoke
# libpython3.10  -> libpython3.10.so.1.0 shared lib PyInstaller bundles
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        binutils \
        python3 \
        python3-pip \
        python3-tk \
        python-is-python3 \
        libpython3.10 \
    && rm -rf /var/lib/apt/lists/*

# Single source of truth for the PyInstaller pin.
COPY packaging/requirements-build.txt /tmp/requirements-build.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements-build.txt
