from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class BuildStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    BUILDING = "building"
    TESTING = "testing"
    REPAIRING = "repairing"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    UNSUPPORTED_SCOPE = "unsupported_scope"


class BuildStage(StrEnum):
    IDEA = "idea"
    COMPONENTS = "components"
    ELECTRONICS = "electronics"
    FIRMWARE = "firmware"
    SIMULATION = "simulation"
    ENCLOSURE = "enclosure"
    VERIFICATION = "verification"
    COMPLETE = "complete"


class ProductSpec(BaseModel):
    name: str = "Desk Environmental Monitor"
    intent: str
    description: str
    features: list[str]
    power: Literal["usb", "battery"] = "usb"
    constraints: list[str] = Field(default_factory=list)
    supported: bool = True
    unsupported_reason: str | None = None


class Pin(BaseModel):
    name: str
    functions: list[str]


class ComponentDefinition(BaseModel):
    id: str
    name: str
    type: str
    voltage: float
    interfaces: list[str]
    pins: dict[str, str]
    dimensions_mm: tuple[float, float, float]
    firmware_libraries: list[str]
    wokwi_part_id: str
    constraints: list[str] = Field(default_factory=list)
    i2c_address: str | None = None


class ComponentInstance(BaseModel):
    ref: str
    component_id: str
    label: str


class Endpoint(BaseModel):
    ref: str
    pin: str


class Connection(BaseModel):
    from_: Endpoint = Field(alias="from", serialization_alias="from")
    to: Endpoint
    interface: str
    reason: str

    model_config = {"populate_by_name": True}


class HardwareIR(BaseModel):
    version: str = "1.0"
    board: ComponentInstance
    components: list[ComponentInstance]
    connections: list[Connection]
    power: list[Connection]
    constraints: list[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: str
    severity: Literal["error", "warning"] = "error"


class ValidationResult(BaseModel):
    passed: bool
    checks: dict[str, bool]
    issues: list[ValidationIssue]


class ToolResult(BaseModel):
    status: Literal["passed", "failed", "unavailable", "not_run"]
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class VerificationReport(BaseModel):
    electrical_compatibility: str = "not_run"
    firmware_compilation: str = "not_run"
    simulation: str = "not_run"
    enclosure_generation: str = "not_run"
    physical_assembly: str = "not_verified"
    emi_emc: str = "not_verified"
    thermals: str = "not_verified"
    scenario_checks: list[str] = Field(default_factory=list)


class BuildEvent(BaseModel):
    id: str
    type: str
    stage: BuildStage
    status: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class Build(BaseModel):
    id: str
    prompt: str
    status: BuildStatus = BuildStatus.QUEUED
    stage: BuildStage = BuildStage.IDEA
    progress: int = 0
    version: int = 1
    parent_build_id: str | None = None
    queue_position: int | None = None
    dispatch_requested_at: str | None = None
    execution_started_at: str | None = None
    product_spec: ProductSpec | None = None
    hardware: HardwareIR | None = None
    electrical_validation: ValidationResult | None = None
    semantic_alignment: ToolResult | None = None
    firmware: ToolResult | None = None
    simulation: ToolResult | None = None
    enclosure: ToolResult | None = None
    verification: VerificationReport | None = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    fingerprints: dict[str, str] = Field(default_factory=dict)
    reuse_evidence: list[dict[str, Any]] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    agent_mode: str = "pending"
    error: str | None = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class StartBuildRequest(BaseModel):
    prompt: str = Field(min_length=8, max_length=2000)


class UpdateBuildRequest(BaseModel):
    change: str = Field(min_length=3, max_length=1000)


class StartBuildResponse(BaseModel):
    build_id: str
    status: BuildStatus
    build_url: str
    queue_position: int | None = None
