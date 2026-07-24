FROM alpine:3.21

RUN apk add --no-cache \
    bash curl wget ca-certificates openssh-server openssh-client \
    python3 py3-pip py3-requests \
    nmap bind-tools netcat-openbsd tmux tor torsocks && \
    pip3 install --break-system-packages rich httpx && \
    ssh-keygen -A

RUN echo "SOCKSPort 0.0.0.0:9050" > /etc/tor/torrc && \
    echo "DNSPort 5353" >> /etc/tor/torrc && \
    echo "Log notice file /var/log/tor/notices.log" >> /etc/tor/torrc && \
    mkdir -p /var/log/tor /root/.ssh /root/output /root/tools /root/scripts

COPY workers/shared/sshd-shell.sh /usr/local/bin/sshd-shell
COPY workers/shared/worker-entrypoint.sh /entrypoint.sh
COPY workers/papa/tor-entrypoint.sh /tor-entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/sshd-shell /tor-entrypoint.sh

EXPOSE 22 9050
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/tor-entrypoint.sh"]
