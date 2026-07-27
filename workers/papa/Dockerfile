FROM alpine:3.21

RUN apk add --no-cache \
    bash curl wget ca-certificates openssh-server openssh-client \
    python3 py3-pip py3-requests \
    nmap bind-tools netcat-openbsd tmux tor torsocks && \
    pip3 install --break-system-packages rich httpx

RUN echo "SOCKSPort 0.0.0.0:9050" > /etc/tor/torrc && \
    echo "SocksPolicy accept 127.0.0.1/32" >> /etc/tor/torrc && \
    echo "SocksPolicy accept 172.16.0.0/12" >> /etc/tor/torrc && \
    echo "SocksPolicy reject *" >> /etc/tor/torrc && \
    echo "DNSPort 5353" >> /etc/tor/torrc && \
    echo "DataDirectory /var/lib/tor" >> /etc/tor/torrc && \
    echo "User tor" >> /etc/tor/torrc && \
    echo "Log notice stdout" >> /etc/tor/torrc && \
    rm -f /etc/ssh/ssh_host_* && \
    mkdir -p /run/sshd /root/.ssh /root/output /root/tools /root/scripts && \
    chown -R tor:tor /var/lib/tor

COPY workers/shared/sshd-shell.sh /usr/local/bin/sshd-shell
COPY workers/shared/worker-entrypoint.sh /entrypoint.sh
COPY workers/papa/tor-entrypoint.sh /tor-entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/sshd-shell /tor-entrypoint.sh

EXPOSE 22 9050
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/tor-entrypoint.sh", "/usr/sbin/sshd", "-D", "-e", "-o", "PermitRootLogin=prohibit-password", "-o", "PasswordAuthentication=no", "-o", "PubkeyAuthentication=yes", "-o", "ForceCommand=/usr/local/bin/sshd-shell"]
