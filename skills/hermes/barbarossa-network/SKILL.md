---
name: barbarossa-network
description: Run authorized direct or explicitly Tor-routed network jobs in Recon.
---

# Barbarossa Network

Operate only on targets within the user's authorized scope.

- Use `network_fetch` for a single HTTP(S) URL without shell interpolation.
- Use `network_inspect` for direct DNS, HTTP, discovery, or scanning commands.
- Use `network_tor` only when Tor is explicitly requested or the plan records
  a clear need for it.
- Never silently retry a failed direct request through Tor.
- Never describe a direct result as Tor-routed.
- Track the job to a terminal state and retrieve its bounded logs/results.

Recon is isolated from Forge. Transfer only reviewed artifacts through Hermes.
