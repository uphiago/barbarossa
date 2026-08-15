FROM node:24-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d

ARG CODEX_VERSION=0.145.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash build-essential ca-certificates cmake curl file gdb gh git jq \
    ltrace openssh-server openssl python3 rsync strace tar unzip xxd \
    && rm -rf /var/lib/apt/lists/*

# uv — package manager for the Specify CLI (spec-kit / spec-driven development)
RUN curl -LsSf https://astral.sh/uv/install.sh \
      | env UV_INSTALL_DIR=/usr/local/bin sh \
    && uv --version \
    && rm -rf /root/.cache/uv

RUN npm install --global "@openai/codex@${CODEX_VERSION}" \
    && npm install --global vercel \
    && npm install --global supabase \
    && npm cache clean --force

RUN useradd --create-home --uid 10001 --shell /bin/bash forge \
    && usermod --password \
      "$(openssl passwd -6 "$(head -c 32 /dev/urandom | base64)")" forge \
    && install -d -o forge -g forge \
      /workspace/jobs /workspace/.locks /home/forge/.codex \
      /home/forge/.codex/skills/barbarossa-artifacts \
    && install -d /run/sshd /ssh-host-keys \
      /usr/local/share/barbarossa/codex

COPY containers/shared/worker-rpc.py /usr/local/bin/barbarossa-worker
COPY containers/shared/worker-ssh-dispatch.sh /usr/local/bin/worker-ssh-dispatch
COPY containers/shared/worker-entrypoint.sh /usr/local/bin/worker-entrypoint
COPY containers/forge/forge-entrypoint.sh /usr/local/bin/forge-entrypoint
COPY --chown=forge:forge config/codex/config.toml /home/forge/.codex/config.toml
COPY --chown=forge:forge skills/codex/barbarossa-artifacts/SKILL.md \
  /home/forge/.codex/skills/barbarossa-artifacts/SKILL.md
COPY config/codex/config.toml \
  /usr/local/share/barbarossa/codex/config.toml
COPY skills/codex/barbarossa-artifacts/SKILL.md \
  /usr/local/share/barbarossa/codex/SKILL.md

RUN chmod 0755 \
      /usr/local/bin/barbarossa-worker \
      /usr/local/bin/worker-ssh-dispatch \
      /usr/local/bin/worker-entrypoint \
      /usr/local/bin/forge-entrypoint \
    && chmod 0644 \
      /usr/local/share/barbarossa/codex/config.toml \
      /usr/local/share/barbarossa/codex/SKILL.md \
    && rm -f /etc/ssh/ssh_host_* \
    && ln -s /ssh-host-keys/ssh_host_ed25519_key \
      /etc/ssh/ssh_host_ed25519_key \
    && ln -s /ssh-host-keys/ssh_host_ed25519_key.pub \
      /etc/ssh/ssh_host_ed25519_key.pub

ENV WORKER_USER=forge \
    WORKER_KIND=forge \
    WORKER_HOME=/home/forge \
    WORKSPACE_ROOT=/workspace \
    CODEX_HOME=/home/forge/.codex \
    TZ=UTC

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/forge-entrypoint"]
CMD ["/usr/sbin/sshd", "-D", "-e", \
     "-o", "PermitRootLogin=no", \
     "-o", "PasswordAuthentication=no", \
     "-o", "KbdInteractiveAuthentication=no", \
     "-o", "PubkeyAuthentication=yes", \
     "-o", "AllowUsers=forge", \
     "-o", "AllowAgentForwarding=no", \
     "-o", "AllowTcpForwarding=no", \
     "-o", "GatewayPorts=no", \
     "-o", "PermitTunnel=no", \
     "-o", "PermitTTY=no", \
     "-o", "X11Forwarding=no", \
     "-o", "ForceCommand=/usr/local/bin/worker-ssh-dispatch"]
