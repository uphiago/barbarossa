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
