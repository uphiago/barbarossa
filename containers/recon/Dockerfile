FROM alpine:3.22@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce

ARG SUBFINDER_SHA256=1b7f9c608e9a5bd59e609a5e09710d63c5485e92d3d49dc2c16eb4fdbe10cb60
ARG HTTPX_SHA256=9d8439e8b6c9aa7d1e2314817a392e00d5178da3af5652f7475f88868f418f76
ARG DNSX_SHA256=438b964653056dd51dcfe614b1a16f8bced3cc48a1d27bc07cc6fdf2ef2a9533
ARG NUCLEI_SHA256=ea63d4ae232808cd7c6bc00d0142428e231fab59dae01042246097d195835ab6
ARG FFUF_SHA256=b2a3c725fcb9da175159682f54d6e9149f2905b00d84d155e7efc5d599975ceb
ARG AMASS_SHA256=5e22b5f0239e7eb79439d60d43d3cd20dca2478588bc2242e91ab0c4f8fa40dd
ARG NAABU_SHA256=018c4c9884dea971eda860435ede3021d1150732f34cfd245498c6726d8cab90
ARG KATANA_SHA256=fe1142d92f418549338ea46d67a472124878482e225d279e9a42700c75d76a4d
ARG TLSX_SHA256=05628cec246e292e2f9afc6e7bc5de95aaa0fbe78fd556d5ad220b9f4702d364

RUN apk add --no-cache \
    bash bind-tools build-base ca-certificates coreutils curl gcompat git \
    jq masscan netcat-openbsd nmap nmap-nping openssh-client openssh-server \
    openssl py3-aiohttp py3-beautifulsoup4 py3-dnspython py3-httpx py3-lxml \
    py3-pip py3-requests py3-yaml python3 rsync socat tar tmux tor torsocks \
    unzip wget whois zip

RUN set -eux; \
    mkdir -p /tmp/tools; \
    cd /tmp/tools; \
    curl -fsSL \
      "https://github.com/projectdiscovery/subfinder/releases/download/v2.16.0/subfinder_2.16.0_linux_amd64.zip" \
      -o subfinder.zip; \
    echo "$SUBFINDER_SHA256  subfinder.zip" | sha256sum -c -; \
    unzip -oq subfinder.zip; \
    mv subfinder /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/projectdiscovery/httpx/releases/download/v1.12.0/httpx_1.12.0_linux_amd64.zip" \
      -o httpx.zip; \
    echo "$HTTPX_SHA256  httpx.zip" | sha256sum -c -; \
    unzip -oq httpx.zip; \
    mv httpx /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/projectdiscovery/dnsx/releases/download/v1.3.1/dnsx_1.3.1_linux_amd64.zip" \
      -o dnsx.zip; \
    echo "$DNSX_SHA256  dnsx.zip" | sha256sum -c -; \
    unzip -oq dnsx.zip; \
    mv dnsx /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/projectdiscovery/nuclei/releases/download/v3.11.1/nuclei_3.11.1_linux_amd64.zip" \
      -o nuclei.zip; \
    echo "$NUCLEI_SHA256  nuclei.zip" | sha256sum -c -; \
    unzip -oq nuclei.zip; \
    mv nuclei /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/ffuf/ffuf/releases/download/v2.3.0/ffuf_2.3.0_linux_amd64.tar.gz" \
      -o ffuf.tar.gz; \
    echo "$FFUF_SHA256  ffuf.tar.gz" | sha256sum -c -; \
    tar xzf ffuf.tar.gz; \
    mv ffuf /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/owasp-amass/amass/releases/download/v5.1.1/amass_linux_amd64.tar.gz" \
      -o amass.tar.gz; \
    echo "$AMASS_SHA256  amass.tar.gz" | sha256sum -c -; \
    tar xzf amass.tar.gz; \
    mv amass_linux_amd64/amass /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/projectdiscovery/naabu/releases/download/v2.6.1/naabu_2.6.1_linux_amd64.zip" \
      -o naabu.zip; \
    echo "$NAABU_SHA256  naabu.zip" | sha256sum -c -; \
    unzip -oq naabu.zip; \
    mv naabu /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/projectdiscovery/katana/releases/download/v1.7.0/katana_1.7.0_linux_amd64.zip" \
      -o katana.zip; \
    echo "$KATANA_SHA256  katana.zip" | sha256sum -c -; \
    unzip -oq katana.zip; \
    mv katana /usr/local/bin/; \
    curl -fsSL \
      "https://github.com/projectdiscovery/tlsx/releases/download/v1.4.0/tlsx_1.4.0_linux_amd64.zip" \
      -o tlsx.zip; \
    echo "$TLSX_SHA256  tlsx.zip" | sha256sum -c -; \
    unzip -oq tlsx.zip; \
    mv tlsx /usr/local/bin/; \
    chmod 0755 /usr/local/bin/subfinder /usr/local/bin/httpx \
      /usr/local/bin/dnsx /usr/local/bin/nuclei /usr/local/bin/ffuf \
      /usr/local/bin/amass /usr/local/bin/naabu /usr/local/bin/katana \
      /usr/local/bin/tlsx; \
    rm -rf /tmp/tools

RUN apk add --no-cache libcap-getcap libcap-setcap \
    && setcap cap_net_admin,cap_net_raw+eip /usr/bin/masscan \
    && setcap cap_net_admin,cap_net_raw+eip /usr/bin/nmap \
    && setcap cap_net_admin,cap_net_raw+eip /usr/local/bin/naabu

RUN adduser -D -u 10002 -s /bin/bash recon \
    && echo "recon:$(openssl rand -hex 32)" | chpasswd \
    && install -d -o recon -g recon \
      /workspace/jobs /workspace/.locks \
      /home/recon/.config/subfinder /home/recon/.config/katana \
      /home/recon/.config/tlsx \
    && install -o recon -g recon -m 0600 /dev/null \
      /home/recon/.config/subfinder/config.yaml \
    && printf '{}\n' > /home/recon/.config/subfinder/provider-config.yaml \
    && chown recon:recon /home/recon/.config/subfinder/provider-config.yaml \
    && chmod 0600 /home/recon/.config/subfinder/provider-config.yaml \
    && su -s /bin/sh recon -c 'HOME=/home/recon tlsx -version >/dev/null' \
    && install -d /run/sshd /ssh-host-keys \
    && install -d -o tor -g tor /var/lib/tor \
    && printf '%s\n' \
      'SocksPort 127.0.0.1:9050' \
      'SocksPolicy accept 127.0.0.1/32' \
      'SocksPolicy reject *' \
      'DataDirectory /var/lib/tor' \
      'User tor' \
      'Log notice stdout' \
      > /etc/tor/torrc

COPY containers/shared/worker-rpc.py /usr/local/bin/barbarossa-worker
COPY containers/shared/worker-ssh-dispatch.sh /usr/local/bin/worker-ssh-dispatch
COPY containers/shared/worker-entrypoint.sh /usr/local/bin/worker-entrypoint
COPY containers/recon/tor-entrypoint.sh /usr/local/bin/tor-entrypoint

RUN chmod 0755 \
      /usr/local/bin/barbarossa-worker \
      /usr/local/bin/worker-ssh-dispatch \
      /usr/local/bin/worker-entrypoint \
      /usr/local/bin/tor-entrypoint \
    && rm -f /etc/ssh/ssh_host_* \
    && ln -s /ssh-host-keys/ssh_host_ed25519_key \
      /etc/ssh/ssh_host_ed25519_key \
    && ln -s /ssh-host-keys/ssh_host_ed25519_key.pub \
      /etc/ssh/ssh_host_ed25519_key.pub

ENV WORKER_USER=recon \
    WORKER_KIND=recon \
    WORKER_HOME=/home/recon \
    WORKSPACE_ROOT=/workspace \
    TZ=UTC

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/worker-entrypoint"]
CMD ["/usr/local/bin/tor-entrypoint", \
     "/usr/sbin/sshd", "-D", "-e", \
     "-o", "PermitRootLogin=no", \
     "-o", "PasswordAuthentication=no", \
     "-o", "KbdInteractiveAuthentication=no", \
     "-o", "PubkeyAuthentication=yes", \
     "-o", "AllowUsers=recon", \
     "-o", "AllowAgentForwarding=no", \
     "-o", "AllowTcpForwarding=no", \
     "-o", "GatewayPorts=no", \
     "-o", "PermitTunnel=no", \
     "-o", "PermitTTY=no", \
     "-o", "X11Forwarding=no", \
     "-o", "ForceCommand=/usr/local/bin/worker-ssh-dispatch"]
