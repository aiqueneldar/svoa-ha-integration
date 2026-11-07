# A clean Debian-based development image with the Python minor version
# required by current Home Assistant Core.
FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

# Build/runtime libraries commonly needed by Home Assistant dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        libffi-dev \
        libjpeg-dev \
        libssl-dev \
        libudev-dev \
        libxml2-dev \
        libxslt1-dev \
        pkg-config \
        zlib1g-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Fail the image build rather than silently using an unsupported interpreter.
RUN python -c "import sys; assert sys.version_info >= (3, 14, 2), sys.version"
