#!/bin/sh
set -eu
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
hermes_image="${BARBAROSSA_HERMES_TEST_IMAGE:?set BARBAROSSA_HERMES_TEST_IMAGE}"
docker run --rm --entrypoint /opt/hermes/.venv/bin/python \
  -v "$root/config/hermes:/opt/barbarossa:ro" "$hermes_image" -c '
import runpy
import sys
import types

gateway = runpy.run_path("/opt/barbarossa/gateway_entrypoint.py")
from hermes_cli import model_normalize
cli = types.ModuleType("hermes_cli.main")
cli.main = lambda: 0
sys.modules["hermes_cli.main"] = cli
assert gateway["main"]() == 0
assert model_normalize.normalize_model_for_provider("deepseek-flash", "deepseek") == "deepseek-flash"
from gateway.run import GatewayRunner
assert GatewayRunner._enrich_message_with_vision is gateway["enrich_message_with_codex"]
print("Hermes image: native Flash normalization and image routing verified")
'

# configure.py must import and write with the image venv interpreter (catches
# dependency drift such as PyYAML being dropped for ruamel.yaml in 0.21.6).
docker run --rm \
  -e HERMES_MODEL_PROVIDER=deepseek -e HERMES_MODEL_NAME=deepseek-flash \
  -v "$root/config/hermes:/opt/barbarossa:ro" \
  --entrypoint /opt/hermes/.venv/bin/python "$hermes_image" -c '
import pathlib
import runpy
import tempfile

module = runpy.run_path("/opt/barbarossa/configure.py")
target = pathlib.Path(tempfile.mkdtemp()) / "config.yaml"
module["configure"](target)
text = target.read_text(encoding="utf-8")
assert "deepseek-flash" in text
print("Hermes image: configure.py writes config with the image interpreter")
'
