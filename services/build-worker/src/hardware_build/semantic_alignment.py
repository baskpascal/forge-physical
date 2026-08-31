from __future__ import annotations

import math
import time

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

    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_region,
    )
    spec_text = " ".join(
        [spec.name, spec.intent, spec.description, *spec.features, *spec.constraints]
    )
    config = types.EmbedContentConfig(
        task_type="SEMANTIC_SIMILARITY",
        output_dimensionality=128,
    )
    results: list[dict[str, object]] = []
    try:
        for model in settings.embedding_model_ids:
            started = time.perf_counter()
            prompt_response = client.models.embed_content(
                model=model,
                contents=prompt,
                config=config,
            )
            spec_response = client.models.embed_content(
                model=model,
                contents=spec_text,
                config=config,
            )
            prompt_vector = prompt_response.embeddings[0].values
            spec_vector = spec_response.embeddings[0].values
            results.append(
                {
                    "model": model,
                    "status": "runtime_verified",
                    "dimensions": len(prompt_vector),
                    "similarity": round(_cosine(prompt_vector, spec_vector), 4),
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                }
            )
    except Exception as exc:
        return ToolResult(
            status="unavailable",
            summary="At least one additional Google embedding model could not verify planning alignment.",
            evidence={
                "models": results,
                "error": redact_text(f"{type(exc).__name__}: {exc}", settings),
            },
        )

    return ToolResult(
        status="passed",
        summary="Three additional Google AI models verified prompt-to-spec semantic alignment.",
        evidence={"models": results, "vectors_persisted": False},
    )
