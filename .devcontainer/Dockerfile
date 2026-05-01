FROM mcr.microsoft.com/devcontainers/base:ubuntu

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    sshpass \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages \
    ansible \
    ansible-lint \
    molecule \
    molecule-docker \
    "molecule-plugins[docker]" \
    docker \
    yamllint \
    jmespath
