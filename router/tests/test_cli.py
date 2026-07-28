from barbarossa_router.cli import parser


def test_operator_inspection_commands_require_job_id() -> None:
    command_parser = parser()

    for command in ("status", "logs", "result"):
        parsed = command_parser.parse_args([command, "job_runtime_01ARZ3NDEKTSV4RRFFQ69G5FAV"])
        assert parsed.operator_command == command
        assert parsed.job_id == "job_runtime_01ARZ3NDEKTSV4RRFFQ69G5FAV"
