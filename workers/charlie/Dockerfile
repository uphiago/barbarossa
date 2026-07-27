FROM alpine:3.21

ARG SUBFINDER_SHA256=6529294788f56a20ed96a9b70e71f8f3c247f1d6104ba1e2c2e9e58d8a32c6cb
ARG HTTPX_SHA256=54c6c91d61d3b82ba79f93633df04bb547f0c954d9d9b0fb8bcedf158f85ff2f
ARG DNSX_SHA256=f58d93f511c1e1f653eac2ae1d44be8ea1ee8eba0d95825ab54ca2be6b9d703d
ARG NUCLEI_SHA256=05357e07886d9670e9c54325ec8afd362d03610c87e2aa1455886ad3f7b58519
ARG FFUF_SHA256=fc2c82736c14dcbea4daf3d3cf3878c1c4773008ba45c2bc0fceba7d17b40bb5
ARG AMASS_SHA256=5e22b5f0239e7eb79439d60d43d3cd20dca2478588bc2242e91ab0c4f8fa40dd
ARG NAABU_SHA256=018c4c9884dea971eda860435ede3021d1150732f34cfd245498c6726d8cab90
ARG KATANA_SHA256=503754f1bd370c3ef287df6998e317baed2dd75bdd13ea64034f09b80ca393f3

RUN apk add --no-cache \
    openssh-server bash curl wget jq python3 py3-pip git \
    nmap nmap-nping bind-tools masscan tmux htop unzip tar \
    gcompat build-base openssh-client socat openssl perl whois screen rsync zip

RUN set -eux; mkdir -p /tmp/tools && cd /tmp/tools; \
    curl -fsSL "https://github.com/projectdiscovery/subfinder/releases/download/v2.14.0/subfinder_2.14.0_linux_amd64.zip" -o subfinder.zip; echo "$SUBFINDER_SHA256  subfinder.zip" | sha256sum -c -; unzip -o subfinder.zip && mv subfinder /usr/local/bin/; \
    curl -fsSL "https://github.com/projectdiscovery/httpx/releases/download/v1.9.0/httpx_1.9.0_linux_amd64.zip" -o httpx.zip; echo "$HTTPX_SHA256  httpx.zip" | sha256sum -c -; unzip -o httpx.zip && mv httpx /usr/local/bin/; \
    curl -fsSL "https://github.com/projectdiscovery/dnsx/releases/download/v1.2.3/dnsx_1.2.3_linux_amd64.zip" -o dnsx.zip; echo "$DNSX_SHA256  dnsx.zip" | sha256sum -c -; unzip -o dnsx.zip && mv dnsx /usr/local/bin/; \
    curl -fsSL "https://github.com/projectdiscovery/nuclei/releases/download/v3.9.0/nuclei_3.9.0_linux_amd64.zip" -o nuclei.zip; echo "$NUCLEI_SHA256  nuclei.zip" | sha256sum -c -; unzip -o nuclei.zip && mv nuclei /usr/local/bin/; \
    curl -fsSL "https://github.com/ffuf/ffuf/releases/download/v2.1.0/ffuf_2.1.0_linux_amd64.tar.gz" -o ffuf.tar.gz; echo "$FFUF_SHA256  ffuf.tar.gz" | sha256sum -c -; tar xzf ffuf.tar.gz && mv ffuf /usr/local/bin/; \
    rm -rf /tmp/tools; chmod +x /usr/local/bin/subfinder /usr/local/bin/httpx /usr/local/bin/dnsx /usr/local/bin/nuclei /usr/local/bin/ffuf

RUN mkdir -p /tmp/extra && cd /tmp/extra && \
    curl -fsSL "https://github.com/owasp-amass/amass/releases/download/v5.1.1/amass_linux_amd64.tar.gz" -o amass.tar.gz && echo "$AMASS_SHA256  amass.tar.gz" | sha256sum -c - && tar xzf amass.tar.gz && mv amass_linux_amd64/amass /usr/local/bin/ && \
    curl -fsSL "https://github.com/projectdiscovery/naabu/releases/download/v2.6.1/naabu_2.6.1_linux_amd64.zip" -o naabu.zip && echo "$NAABU_SHA256  naabu.zip" | sha256sum -c - && unzip -o naabu.zip && mv naabu /usr/local/bin/ && \
    curl -fsSL "https://github.com/projectdiscovery/katana/releases/download/v1.6.1/katana_1.6.1_linux_amd64.zip" -o katana.zip && echo "$KATANA_SHA256  katana.zip" | sha256sum -c - && unzip -o katana.zip && mv katana /usr/local/bin/ && \
    rm -rf /tmp/extra && chmod +x /usr/local/bin/amass /usr/local/bin/naabu /usr/local/bin/katana

RUN pip install --no-cache-dir --break-system-packages requests httpx aiohttp pyyaml beautifulsoup4 lxml dnspython rich impacket

RUN rm -f /etc/ssh/ssh_host_* && \
    mkdir -p /run/sshd /root/.ssh /root/output /root/tools /root/scripts && \
    chmod 700 /root/.ssh

RUN printf '#!/bin/sh\necho "hermes is not installed in this worker. Use slash commands."\n' > /usr/local/bin/hermes && chmod +x /usr/local/bin/hermes

COPY workers/shared/sshd-shell.sh /usr/local/bin/sshd-shell
COPY workers/shared/worker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/sshd-shell

EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/sshd", "-D", "-e", "-o", "PermitRootLogin=prohibit-password", "-o", "PasswordAuthentication=no", "-o", "PubkeyAuthentication=yes", "-o", "ForceCommand=/usr/local/bin/sshd-shell"]
