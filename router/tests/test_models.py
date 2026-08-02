import pytest
from pydantic import ValidationError

from barbarossa_router.models import JobRequest, JobStatus


def test_codex_request_uses_codex_lane() -> None:
    request = JobRequest(capability="code.delegate", prompt="Review this repo")

    assert request.worker == "forge"
    assert request.lane == "codex"
    assert request.route == "direct"
    assert request.timeout_seconds == 2700


def test_codex_request_accepts_an_approved_profile() -> None:
    request = JobRequest(
        capability="code.delegate",
        prompt="Review this repo",
        codex_profile="deep",
    )

    assert request.codex_profile == "deep"


def test_codex_profile_is_rejected_for_non_codex_work() -> None:
    with pytest.raises(ValidationError, match="Codex profiles"):
        JobRequest(
            capability="runtime.execute",
            command="printf ok",
            codex_profile="fast",
        )


def test_tor_is_valid_only_for_network_tor() -> None:
    with pytest.raises(ValidationError, match="Tor route requires network.tor"):
        JobRequest(
            capability="runtime.execute",
            command="printf ok",
            route="tor",
        )


def test_network_tor_forces_tor_route() -> None:
    request = JobRequest(
        capability="network.tor",
        command="curl https://example.com",
    )

    assert request.worker == "recon"
    assert request.lane == "recon"
    assert request.route == "tor"


def test_network_fetch_requires_url() -> None:
    with pytest.raises(ValidationError, match="url is required"):
        JobRequest(capability="network.fetch")


@pytest.mark.parametrize(
    "capability",
    ["media.file.inspect", "media.image.inspect", "media.image.edit"],
)
def test_file_capabilities_require_one_input(capability: str) -> None:
    kwargs = {"prompt": "Inspect it"} if capability.startswith("media.image") else {}
    with pytest.raises(ValidationError, match="exactly one input"):
        JobRequest(capability=capability, **kwargs)


def test_image_generation_rejects_input_file() -> None:
    with pytest.raises(ValidationError, match="does not accept an input"):
        JobRequest(
            capability="media.image.generate",
            prompt="Generate a diagram",
            input_paths=["/transfer/reference.png"],
        )


def test_job_status_has_stable_machine_fields() -> None:
    status = JobStatus(
        job_id="job_runtime_01J00000000000000000000000",
        capability="runtime.execute",
        worker="forge",
        lane="runtime",
        route="direct",
        status="queued",
    )

    assert status.model_dump()["exit_code"] is None


def test_job_status_rejects_invalid_job_id() -> None:
    with pytest.raises(ValidationError, match="job_id"):
        JobStatus(
            job_id="../../root",
            capability="runtime.execute",
            worker="forge",
            lane="runtime",
            route="direct",
            status="queued",
        )
