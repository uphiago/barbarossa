# Infra consolidation and hardening

## Scope

Consolidate the Barbarossa worker infrastructure around the `barbarossa`
repository, which is the source used by GitHub Actions and the OVH deployment.
The separate `infra/images` and `infra/compose` copies will be removed.

`infra/agent-image-bench` is explicitly out of scope and must remain unchanged.
No production SSH key is rotated until the replacement GitHub secret is
configured.

## Canonical layout

- `barbarossa/docker-compose.yml` defines Hermes and the three workers.
- `barbarossa/workers/charlie` owns the recon image.
- `barbarossa/workers/oscar` owns the heavy/reverse-engineering image.
- `barbarossa/workers/papa` owns the Tor image and Tor lifecycle.
- `barbarossa/workers/shared` owns common SSH startup and audit behavior.
- `barbarossa/setup.sh` is only a local-development bootstrap. It generates or
  selects local SSH key material outside Git and installs only the public
  authorized key under the ignored runtime directory.
- `.github/workflows/build-deploy.yml` is the production bootstrap. It receives
  the worker private key through `BARBAROSSA_WORKER_SSH_KEY_B64`, derives its
  public key on the OVH host, and stores both outside the Git clone.

The obsolete `infra/images` and `infra/compose` trees are deleted after their
unique behavior has either been rejected as stale or incorporated into the
canonical repository.

## Runtime behavior

Dashboard username, password, and signing secret are required configuration.
The example environment file contains no working default credentials, and
setup fails before starting containers when required values are absent.

Production deploys fail before changing containers when the worker key secret
is absent or invalid. The decoded private key is written with mode `0600` under
`~/.config/barbarossa`, its public key is derived with `ssh-keygen`, and the
non-secret authorized-keys path is persisted in the production `.env`. After
containers are recreated, the workflow installs the private key into the
Hermes data volume with restrictive ownership and permissions.

Each worker receives an SSH healthcheck. Hermes waits for healthy workers
instead of only waiting for container creation.

Papa starts Tor and SSH as supervised child processes. It waits for the local
SOCKS listener before reporting readiness and terminates the container if
either Tor or SSH exits. Its healthcheck verifies both SSH and SOCKS ports.
The Tor validation checks DNS resolution and confirms that the reported egress
is a Tor exit.

Worker SSH host keys live in dedicated Docker volumes so routine container
recreation does not invalidate Hermes's `known_hosts`. The first deployment
with persistent host-key volumes removes stale worker-name entries once before
performing the SSH health check.

## Build hardening

Worker tool versions remain explicit. Remote release archives are downloaded
with failure-aware curl flags and verified with SHA-256 before extraction.
The Amass download is changed from a mutable `latest` URL to an explicit
release. Python dependency installation must not silently succeed after a
failure.

Container registry `latest` remains the deployment channel because the
existing GitHub Actions workflow builds workers independently. Changing this
to a single immutable tag would make partial worker builds inconsistent and is
outside this focused correction.

## Documentation

`infra/AGENTS.md`, the Barbarossa README, and worker routing documentation will
describe only the canonical COP names and actual tools. Stored dashboard
credentials and obsolete alternate-compose paths will be removed. Host SSH
examples will use the loopback port mapping.

## Verification

Shell regression tests will cover required dashboard configuration, key
handling, Tor supervision, healthchecks, and the absence of obsolete defaults.
Verification also includes:

- `bash -n` for shell scripts
- `docker compose config` with non-secret test values
- Dockerfile/tool download assertions
- focused worker image builds when network access permits
- remote container logs, Hermes-to-worker SSH, and Tor egress checks on OVH
- a final Git diff and secret-pattern scan
