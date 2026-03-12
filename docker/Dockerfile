FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/bin:${PATH}"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential autoconf automake libtool pkg-config \
    libreadline-dev libfftw3-dev libxaw7-dev libx11-dev \
    bison flex gperf \
    wget git curl ca-certificates \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ngspice 45.2 from local tarball (SourceForge blocks downloads in Docker)
COPY ngspice-45.2.tar.gz /tmp/ngspice-45.2.tar.gz
RUN cd /tmp && tar xzf ngspice-45.2.tar.gz \
    && cd ngspice-45.2 \
    && mkdir release && cd release \
    && ../configure \
        --enable-osdi \
        --enable-xspice \
        --enable-cider \
        --with-readline=yes \
        --disable-debug \
        --prefix=/usr/local \
    && make -j$(nproc) \
    && make install \
    && cd /tmp && rm -rf ngspice*

# OpenVAF 23.5.0 — prebuilt Linux amd64 binary (local copy)
COPY openvaf_23_5_0_linux_amd64.tar.gz /tmp/openvaf.tar.gz
RUN cd /tmp && tar xzf openvaf.tar.gz \
    && mv /tmp/openvaf /usr/local/bin/openvaf \
    && chmod +x /usr/local/bin/openvaf \
    && rm -f /tmp/openvaf.tar.gz

# Download pre-compiled HERACLES OSDI as fallback
RUN mkdir -p /workspace/models/fefet/heracles \
    && wget -q "https://github.com/bics-rug/heracles/releases/download/v0.2.1/heracles_v0.2.1__osdi_v0.4.osdi" \
       -O /workspace/models/fefet/heracles/heracles.osdi

# Verify installations
RUN ngspice --version && openvaf --version

WORKDIR /workspace
CMD ["/bin/bash"]
