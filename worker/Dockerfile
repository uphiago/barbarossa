FROM alpine:3.21

RUN apk add --no-cache \
    openssh-server \
    bash \
    curl \
    wget \
    jq \
    python3 \
    py3-pip \
    git \
    nmap \
    nmap-nping \
    bind-tools \
    masscan \
    tmux \
    htop \
    unzip \
    tar \
    gcompat \
    build-base \
    openssh-client \
    socat \
    openssl \
    perl \
    whois \
    screen \
    rsync \
    zip

RUN set -eux; \
    mkdir -p /tmp/tools && cd /tmp/tools; \
    \
    curl -sL "https://github.com/projectdiscovery/subfinder/releases/download/v2.14.0/subfinder_2.14.0_linux_amd64.zip" -o subfinder.zip; \
    unzip -o subfinder.zip; \
    mv subfinder /usr/local/bin/; \
    \
    curl -sL "https://github.com/projectdiscovery/httpx/releases/download/v1.9.0/httpx_1.9.0_linux_amd64.zip" -o httpx.zip; \
    unzip -o httpx.zip; \
    mv httpx /usr/local/bin/; \
    \
    curl -sL "https://github.com/projectdiscovery/dnsx/releases/download/v1.2.3/dnsx_1.2.3_linux_amd64.zip" -o dnsx.zip; \
    unzip -o dnsx.zip; \
    mv dnsx /usr/local/bin/; \
    \
    curl -sL "https://github.com/projectdiscovery/nuclei/releases/download/v3.9.0/nuclei_3.9.0_linux_amd64.zip" -o nuclei.zip; \
    unzip -o nuclei.zip; \
    mv nuclei /usr/local/bin/; \
    \
    curl -sL "https://github.com/ffuf/ffuf/releases/download/v2.1.0/ffuf_2.1.0_linux_amd64.tar.gz" -o ffuf.tar.gz; \
    tar xzf ffuf.tar.gz; \
    mv ffuf /usr/local/bin/; \
    \
    rm -rf /tmp/tools; \
    chmod +x /usr/local/bin/subfinder /usr/local/bin/httpx /usr/local/bin/dnsx /usr/local/bin/nuclei /usr/local/bin/ffuf

# Extra tools from GitHub releases
RUN mkdir -p /tmp/extra && cd /tmp/extra && \
    curl -sL "https://github.com/owasp-amass/amass/releases/latest/download/amass_linux_amd64.tar.gz" -o amass.tar.gz && \
    tar xzf amass.tar.gz && mv amass_linux_amd64/amass /usr/local/bin/ && \
    curl -sL "https://github.com/projectdiscovery/naabu/releases/download/v2.6.1/naabu_2.6.1_linux_amd64.zip" -o naabu.zip && \
    unzip -o naabu.zip && mv naabu /usr/local/bin/ && \
    curl -sL "https://github.com/projectdiscovery/katana/releases/download/v1.6.1/katana_1.6.1_linux_amd64.zip" -o katana.zip && \
    unzip -o katana.zip && mv katana /usr/local/bin/ && \
    rm -rf /tmp/extra && \
    chmod +x /usr/local/bin/amass /usr/local/bin/naabu /usr/local/bin/katana

RUN pip install --no-cache-dir --break-system-packages \
    requests \
    httpx \
    aiohttp \
    pyyaml \
    beautifulsoup4 \
    lxml \
    dnspython \
    rich \
    impacket

RUN mkdir -p /root/.ssh /root/output /root/tools && chmod 700 /root/.ssh

# Dummy hermes script — redirect model to use slash commands
RUN printf '#!/bin/sh\necho "hermes is not installed in this worker. Use slash commands: /model, /config, /reset."\n' > /usr/local/bin/hermes && chmod +x /usr/local/bin/hermes

# MOTD banner
RUN printf '\n  \033[1;36m╔══════════════════════════════════╗\n  \033[1;36m║\033[0m     \033[1;32magentiko worker\033[0m              \033[1;36m║\n  \033[1;36m║\033[0m  nmap subfinder nuclei ffuf...  \033[1;36m║\n  \033[1;36m║\033[0m  amass naabu katana httpx dnsx  \033[1;36m║\n  \033[1;36m╚══════════════════════════════════╝\033[0m\n\n' > /etc/motd

# Colored PS1 + ulimit
RUN printf 'export PS1="\\[\\\\033[1;32m\\]\\\\u@\\\\h\\[\\\\033[0m\\]:\\[\\\\033[1;34m\\]\\\\w\\[\\\\033[0m\\]\\\\$ "\nulimit -n 65536 2>/dev/null || true\n' >> /root/.bashrc

COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/sshd-shell.sh /usr/local/bin/sshd-shell
RUN chmod +x /entrypoint.sh /usr/local/bin/sshd-shell

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/sshd", "-D", "-e", "-o", "PermitRootLogin=prohibit-password", "-o", "PasswordAuthentication=no", "-o", "PubkeyAuthentication=yes", "-o", "ForceCommand=/usr/local/bin/sshd-shell"]
