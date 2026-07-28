import os
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_packaged_server_lists_expected_tools(
    tmp_path: Path,
) -> None:
    executable = os.environ.get("BARBAROSSA_ROUTER_PEX")
    if executable is None:
        pytest.skip("BARBAROSSA_ROUTER_PEX is not set")
    python = os.environ["BARBAROSSA_ROUTER_PYTHON"]
    key = tmp_path / "worker_key"
    known_hosts = tmp_path / "known_hosts"
    input_root = tmp_path / "transfer"
    result_root = tmp_path / "results"
    key.touch(mode=0o600)
    known_hosts.touch(mode=0o600)
    input_root.mkdir()
    result_root.mkdir()
    parameters = StdioServerParameters(
        command=python,
        args=[executable, "serve"],
        env={
            "BARBAROSSA_SSH_KEY": str(key),
            "BARBAROSSA_KNOWN_HOSTS": str(known_hosts),
            "BARBAROSSA_STATE_DB": str(tmp_path / "jobs.sqlite3"),
            "BARBAROSSA_INPUT_ROOT": str(input_root),
            "BARBAROSSA_RESULT_ROOT": str(result_root),
            "BARBAROSSA_FORGE_HOST": "forge",
            "BARBAROSSA_RECON_HOST": "recon",
            "OTEL_SDK_DISABLED": "true",
        },
    )
    async with Client(
        stdio_client(parameters),
        raise_exceptions=True,
    ) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert {
        "runtime_execute",
        "code_delegate",
        "media_image_generate",
        "network_tor",
    } <= names
