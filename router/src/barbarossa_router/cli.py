import argparse
import asyncio
import json
from typing import Any

from barbarossa_router.config import Settings
from barbarossa_router.models import JobRequest
from barbarossa_router.scheduler import Scheduler
from barbarossa_router.server import create_server
from barbarossa_router.service import RouterService
from barbarossa_router.ssh import SSHTransport
from barbarossa_router.store import JobStore

TERMINAL_STATES = {"succeeded", "failed", "cancelled", "interrupted"}


def build_service(settings: Settings | None = None) -> RouterService:
    resolved = settings or Settings.from_env()
    store = JobStore(resolved.state_db)
    transport = SSHTransport(resolved)
    scheduler = Scheduler(store, transport)
    return RouterService(
        store,
        scheduler,
        transport,
        resolved.result_root,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="barbarossa-router")
    commands = root.add_subparsers(dest="operator_command", required=True)
    commands.add_parser("serve")
    commands.add_parser("health")
    for command in ("status", "logs", "result"):
        inspection = commands.add_parser(command)
        inspection.add_argument("job_id")
    submit = commands.add_parser("submit")
    submit.add_argument("--capability", required=True)
    submit.add_argument("--command")
    submit.add_argument("--prompt")
    submit.add_argument("--url")
    submit.add_argument("--input-path", action="append", default=[])
    submit.add_argument("--timeout-seconds", type=int)
    submit.add_argument("--wait", action="store_true")
    return root


def dump(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")))


async def run_operator_command(args: argparse.Namespace) -> int:
    service = build_service()
    if args.operator_command == "health":
        try:
            dump(await service.health())
            return 0
        finally:
            await service.transport.close()
    if args.operator_command in {"status", "logs", "result"}:
        try:
            operation = getattr(service, args.operator_command)
            dump(await operation(args.job_id))
            return 0
        finally:
            await service.transport.close()

    request = JobRequest(
        capability=args.capability,
        command=args.command,
        prompt=args.prompt,
        url=args.url,
        input_paths=args.input_path,
        timeout_seconds=args.timeout_seconds,
    )
    await service.start()
    try:
        job = await service.submit(request)
        if not args.wait:
            dump(job)
            return 0
        while True:
            current = await service.status(job.job_id)
            if current.status in TERMINAL_STATES:
                dump(current)
                return 0 if current.status == "succeeded" else 1
            await asyncio.sleep(1)
    finally:
        await service.close()


def main() -> None:
    args = parser().parse_args()
    if args.operator_command == "serve":
        create_server(build_service()).run(transport="stdio")
        return
    raise SystemExit(asyncio.run(run_operator_command(args)))
