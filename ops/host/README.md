# OVH host setup notes

Host-side files for the Barbarossa deployment. Install paths:

| File | Install as |
| --- | --- |
| `48-barbarossa-forwarding.conf` | `/etc/ssh/sshd_config.d/48-barbarossa-forwarding.conf` |
| `barbarossa-container-firewall` | `/usr/local/sbin/barbarossa-container-firewall` |
| `barbarossa-container-firewall.service` | `/etc/systemd/system/barbarossa-container-firewall.service` |
| `fail2ban-sshd.local` | `/etc/fail2ban/jail.d/sshd.local` |

## Dashboard tunnel and the `Match User ubuntu` override

The drop-in above allows local forwarding to the Hermes dashboard
(`127.0.0.1:9119`), but a `Match User ubuntu` block in the main
`/etc/ssh/sshd_config` takes precedence for that user and only allowed
`*:80` and `*:443`. Symptom:

```text
channel 2: open failed: administratively prohibited: open failed
```

Keep the dashboard target in the per-user block as well:

```text
Match User ubuntu
    AllowTcpForwarding local
    PermitOpen *:80 *:443 127.0.0.1:9119 localhost:9119
    ...
```

Verify the effective policy for the user (not just `sshd -T`):

```bash
sudo sshd -T -C user=ubuntu,host=localhost,addr=127.0.0.1 \
  | grep -iE '^(permitopen|allowtcpforwarding)'
```

Then reload (`sudo systemctl reload ssh`) and reconnect the tunnel;
existing SSH sessions keep the policy loaded when they were opened.
