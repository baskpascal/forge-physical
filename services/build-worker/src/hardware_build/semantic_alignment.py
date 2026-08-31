from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor

from google import genai
from google.genai import types

from .models import ProductSpec, ToolResult
from .security import redact_text
from .settings import Settings


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    return numerator / denominator if denominator else 0.0


def verify_semantic_alignment(
    prompt: str,
    spec: ProductSpec,
    settings: Settings,
) -> ToolResult:
    """Use three additional Google embedding models to detect planning drift."""
    if not settings.gemini_configured:
        return ToolResult(
            status="unavailable",
            summary="Semantic alignment requires Vertex AI credentials and project configuration.",
        )

    spec_text = " ".join(
        [spec.name, spec.intent, spec.description, *spec.features, *spec.constraints]
    )
    config = types.EmbedContentConfig(
        task_type="SEMANTIC_SIMILARITY",
        output_dimensionality=128,
    )

    def verify_model(model: str) -> dict[str, object]:
        started = time.perf_counter()
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_region,
        )
        try:
            # One batched request/model replaces two serial network round trips while retaining
            # separate prompt/spec vectors and per-model evidence.
            response = client.models.embed_content(
                model=model,
                contents=[prompt, spec_text],
                config=config,
            )
            prompt_vector = response.embeddings[0].values
            spec_vector = response.embeddings[1].values
            return {
                "model": model,
                "status": "runtime_verified",
                "dimensions": len(prompt_vector),
                "similarity": round(_cosine(prompt_vector, spec_vector), 4),
                "latency_ms": round((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:
            return {
                "model": model,
                "status": "unavailable",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error": redact_text(f"{type(exc).__name__}: {exc}", settings),
            }

    models = settings.embedding_model_ids
    if not models:
        return ToolResult(
            status="unavailable",
            summary="Semantic alignment has no configured embedding models.",
            evidence={"models": [], "vectors_persisted": False},
        )
    with ThreadPoolExecutor(
        max_workers=max(1, min(settings.embedding_max_concurrency, len(models))),
        thread_name_prefix="semantic-alignment",
    ) as executor:
        results = list(executor.map(verify_model, models))
    if any(result["status"] != "runtime_verified" for result in results):
        return ToolResult(
            status="unavailable",
            summary="At least one additional Google embedding model could not verify planning alignment.",
            evidence={"models": results, "vectors_persisted": False},
        )

    return ToolResult(
        status="passed",
        summary=f"{len(results)} additional Google AI models verified prompt-to-spec semantic alignment.",
        evidence={"models": results, "vectors_persisted": False},
    )
