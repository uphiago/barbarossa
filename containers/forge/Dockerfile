FROM node:24-bookworm-slim@sha256:5cbc7caba8c2c0f0bca675d1b61b9f2857e1cf1853c6164ee9dd409501a936e7

ARG CODEX_VERSION=0.160.0
ARG NPM_VERSION=12.2.0
ARG VERCEL_VERSION=62.2.0
ARG SUPABASE_VERSION=2.119.0
ARG UV_VERSION=0.12.23
ARG UV_SHA256=9167d72b3319674b6303c4cbe071854bba13ebdf3d76b1a7cbdc175471fb66d6
# github/spec-kit v1.1.0, resolved to an immutable commit.
ARG SPECIFY_REVISION=f1d3a4f8337ebbd3ae22760a9c12e3352b93a175

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash build-essential ca-certificates cmake curl file gdb gh git jq \
    ltrace openssh-server openssl python3 rsync strace tar unzip xxd \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" -o /tmp/uv.tar.gz \
    && echo "${UV_SHA256}  /tmp/uv.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/uv.tar.gz -C /tmp \
    && install -m 0755 /tmp/uv-x86_64-unknown-linux-gnu/uv /tmp/uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/ \
    && rm -rf /tmp/uv.tar.gz /tmp/uv-x86_64-unknown-linux-gnu

RUN npm install --global "npm@${NPM_VERSION}" \
    && npm install --global "@openai/codex@${CODEX_VERSION}" "vercel@${VERCEL_VERSION}" "supabase@${SUPABASE_VERSION}" \
    && npm cache clean --force

# Install once in the image, outside /home/forge (a persistent volume).
RUN UV_TOOL_DIR=/opt/barbarossa-tools UV_TOOL_BIN_DIR=/usr/local/bin UV_CACHE_DIR=/tmp/uv-cache \
      uv tool install --python /usr/bin/python3 \
        --from "git+https://github.com/github/spec-kit.git@${SPECIFY_REVISION}" specify-cli \
    && rm -rf /tmp/uv-cache

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
