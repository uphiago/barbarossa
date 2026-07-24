#!/bin/sh
tor -f /etc/tor/torrc &
sleep 3
echo "Tor SOCKS5: :9050"
exec /usr/sbin/sshd -D -e -o PermitRootLogin=prohibit-password -o PasswordAuthentication=no -o PubkeyAuthentication=yes -o ForceCommand=/usr/local/bin/sshd-shell
