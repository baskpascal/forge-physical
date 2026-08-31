from hardware_build.events import BuildReporter
from hardware_build.models import Build, BuildStage
from hardware_build.security import REDACTED, redact, redact_text
from hardware_build.settings import Settings
from hardware_build.storage import LocalJsonBuildStore


def test_known_secrets_and_credential_shapes_are_redacted():
    settings = Settings(wokwi_cli_token="super-secret-token")
    value = "token=visible authorization: Bearer abc123 super-secret-token"
    output = redact_text(value, settings)
    assert "super-secret-token" not in output
    assert "abc123" not in output
    assert output.count(REDACTED) >= 2


def test_nested_tool_evidence_is_redacted():
    settings = Settings(internal_worker_token="private-worker-token")
    output = redact({"output": ["private-worker-token", {"api_key": "safe-label"}]}, settings)
    assert "private-worker-token" not in str(output)


def test_reporter_uses_the_orchestrator_settings_for_redaction(tmp_path):
    settings = Settings(internal_worker_token="private-worker-token")
    store = LocalJsonBuildStore(tmp_path)
    build = Build(id="build-1", prompt="Build a desk monitor")
    store.create(build)

    BuildReporter(store, build, settings).emit(
        "worker.test",
        BuildStage.IDEA,
        "running",
        "Using private-worker-token",
        metadata={"authorization": "Bearer private-worker-token"},
    )

    event = store.events(build.id)[0]
    assert "private-worker-token" not in event.message
    assert "private-worker-token" not in str(event.metadata)
