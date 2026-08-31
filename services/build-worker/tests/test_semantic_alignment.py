import threading
import time
from types import SimpleNamespace

from hardware_build.models import ProductSpec
from hardware_build.semantic_alignment import verify_semantic_alignment
from hardware_build.settings import Settings


def test_three_google_models_verify_prompt_to_spec_alignment(monkeypatch):
    calls: list[str] = []

    class FakeModels:
        def embed_content(self, *, model, contents, config):
            calls.append(model)
            assert len(contents) == 2
            vectors = [
                [1.0, 0.5, 0.25] if "alarm" in content.lower() else [0.9, 0.5, 0.2]
                for content in contents
            ]
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=vector) for vector in vectors]
            )

    monkeypatch.setattr(
        "hardware_build.semantic_alignment.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )
    spec = ProductSpec(
        name="ESP32 Temperature Alarm",
        intent="temperature alarm",
        description="Turn an LED on above 30 degrees Celsius.",
        features=["temperature alarm"],
    )
    settings = Settings(
        google_cloud_project="test-project",
        google_genai_use_vertexai=True,
    )

    result = verify_semantic_alignment("Create an ESP32 temperature alarm", spec, settings)

    assert result.status == "passed"
    assert calls == [
        "gemini-embedding-001",
        "text-embedding-005",
        "text-multilingual-embedding-002",
    ]
    assert [entry["status"] for entry in result.evidence["models"]] == [
        "runtime_verified",
        "runtime_verified",
        "runtime_verified",
    ]
    assert result.evidence["vectors_persisted"] is False


def test_embedding_models_execute_concurrently_and_keep_individual_evidence(monkeypatch):
    lock = threading.Lock()
    active = 0
    maximum = 0

    class FakeModels:
        def embed_content(self, *, model, contents, config):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.03)
            with lock:
                active -= 1
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[1.0, 0.5]) for _ in contents]
            )

    monkeypatch.setattr(
        "hardware_build.semantic_alignment.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )
    result = verify_semantic_alignment(
        "temperature alarm",
        ProductSpec(intent="temperature alarm", description="alarm", features=["alarm"]),
        Settings(google_cloud_project="test-project"),
    )

    assert result.status == "passed"
    assert maximum > 1
    assert [entry["model"] for entry in result.evidence["models"]] == list(
        Settings().embedding_model_ids
    )
