from __future__ import annotations

import json
import re
from dataclasses import dataclass

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

from .catalog import public_catalog
from .models import ProductSpec
from .planning import deterministic_product_spec
from .settings import Settings


def get_supported_component_catalog() -> dict:
    """Return the complete verified component catalog. Only these parts may be selected."""
    return {"components": public_catalog()}


def low_voltage_scope_policy() -> dict:
    """Return the non-negotiable prototype safety boundary."""
    return {
        "supported": "low-voltage, non-medical, non-safety-critical electronic prototypes",
        "rejected": ["mains electricity", "high voltage", "medical", "weapons", "safety-critical", "high-power"],
    }


PLANNER_INSTRUCTION = """You are ProductPlanner for Forge Physical.
Convert the request into a concise ProductSpec for a low-voltage ESP32-S3 prototype.
You MUST call get_supported_component_catalog before selecting parts and respect low_voltage_scope_policy.
For the base desk environmental monitor select ESP32-S3, SSD1306, DHT22, and KY-040.
For a temperature alarm request, select the supported ESP32-S3, DHT22, and LED, include the
"temperature alarm" feature, and keep the threshold behavior testable in Wokwi.
When the request adds motion sensing, include the "motion sensing" feature so the verified planner
can add the catalog MPU6050 on the existing I2C bus.
Never invent a part, a verification result, or a simulation outcome.
Return only JSON with: name, intent, description, features, power, constraints, supported, unsupported_reason.
"""

REPAIR_INSTRUCTION = """You are EngineeringAgent. Analyze one real PlatformIO compiler failure.
Return only a JSON object with keys find, replace, explanation. The find value must be an exact,
small substring of the supplied source. Make one minimal change. Never claim compilation passed.
"""


def make_planner_agent(settings: Settings) -> Agent:
    return Agent(
        name="product_planner",
        model=settings.gemini_model,
        description="Turns product intent into a supported low-voltage ProductSpec.",
        instruction=PLANNER_INSTRUCTION,
        tools=[get_supported_component_catalog, low_voltage_scope_policy],
        generate_content_config=types.GenerateContentConfig(temperature=0.1),
    )


def make_engineering_agent(settings: Settings) -> Agent:
    return Agent(
        name="engineering_agent",
        model=settings.gemini_model,
        description="Produces constrained repairs from real compiler evidence.",
        instruction=REPAIR_INSTRUCTION,
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
    )


def _final_text(events: list) -> str:
    for event in reversed(events):
        if event.content and event.content.parts:
            text = "".join(part.text or "" for part in event.content.parts)
            if text.strip():
                return text.strip()
    raise RuntimeError("ADK agent returned no text response")


def _json_object(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    return json.loads(candidate)


def _normalize_product_spec_payload(payload: dict) -> dict:
    """Accept Gemini's descriptive power object while preserving the public ProductSpec contract."""
    power = payload.get("power")
    if isinstance(power, dict):
        description = " ".join(str(value) for value in power.values()).lower()
        payload = {**payload, "power": "battery" if "battery" in description else "usb"}
    return payload


@dataclass
class PlanOutcome:
    spec: ProductSpec
    mode: str
    note: str | None = None


async def plan_product(prompt: str, settings: Settings) -> PlanOutcome:
    if not settings.gemini_configured:
        return PlanOutcome(
            spec=deterministic_product_spec(prompt),
            mode="deterministic-fallback",
            note="Google Cloud credentials/project are not configured; used the verified demo planner.",
        )
    try:
        runner = InMemoryRunner(agent=make_planner_agent(settings), app_name="forge_physical")
        events = await runner.run_debug(prompt, user_id="build-worker", session_id="product-plan", quiet=True)
        spec = ProductSpec.model_validate(_normalize_product_spec_payload(_json_object(_final_text(events))))
        return PlanOutcome(spec=spec, mode=f"google-adk/{settings.gemini_model}")
    except Exception as exc:
        return PlanOutcome(
            spec=deterministic_product_spec(prompt),
            mode="deterministic-fallback",
            note=f"ADK planning failed and the verified planner took over: {type(exc).__name__}: {exc}",
        )


async def propose_repair(source: str, compiler_output: str, settings: Settings) -> dict | None:
    if not settings.gemini_configured:
        return None
    prompt = json.dumps({"source": source, "compiler_output": compiler_output[-10000:]})
    runner = InMemoryRunner(agent=make_engineering_agent(settings), app_name="forge_physical")
    events = await runner.run_debug(prompt, user_id="build-worker", session_id="firmware-repair", quiet=True)
    proposal = _json_object(_final_text(events))
    if not all(isinstance(proposal.get(key), str) for key in ("find", "replace", "explanation")):
        return None
    if not proposal["find"] or len(proposal["find"]) > 500 or len(proposal["replace"]) > 1000:
        return None
    return proposal


# Standard ADK discovery export; runtime workers create per-build agents above.
root_agent = Agent(
    name="build_orchestrator",
    model="gemini-3.5-flash",
    description="Coordinates supported physical-product planning with real engineering tools.",
    instruction=PLANNER_INSTRUCTION,
    tools=[get_supported_component_catalog, low_voltage_scope_policy],
)
