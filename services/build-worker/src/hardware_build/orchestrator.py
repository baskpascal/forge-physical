from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .agent import plan_product, propose_repair
from .artifacts import ArtifactWorkspace
from .enclosure import generate_enclosure
from .events import BuildReporter
from .firmware import compile_firmware, deterministic_repair, generate_firmware
from .models import BuildStage, BuildStatus, VerificationReport
from .planning import deterministic_hardware_ir, product_has_temperature_alarm
from .security import redact_text
from .semantic_alignment import verify_semantic_alignment
from .settings import Settings, get_settings
from .simulation import generate_wokwi, run_wokwi
from .storage import BuildStore, get_store
from .validators import validate_hardware

logger = logging.getLogger("forge.build")


class BuildOrchestrator:
    def __init__(self, store: BuildStore | None = None, settings: Settings | None = None):
        self.store = store or get_store()
        self.settings = settings or get_settings()

    def run(self, build_id: str) -> None:
        build = self.store.get(build_id)
        reporter = BuildReporter(self.store, build)
        workspace = ArtifactWorkspace(self.settings, build_id)
        try:
            reporter.emit("plan.started", BuildStage.IDEA, "running", "Translating product intent into an engineering brief…", progress=5, build_status=BuildStatus.PLANNING)
            outcome = asyncio.run(plan_product(build.prompt, self.settings))
            build.product_spec = outcome.spec
            build.agent_mode = outcome.mode
            if product_has_temperature_alarm(outcome.spec, build.prompt) and "temperature alarm" not in outcome.spec.features:
                outcome.spec.features.append("temperature alarm")
            if outcome.note:
                reporter.emit("agent.fallback", BuildStage.IDEA, "unavailable", outcome.note, progress=10, metadata={"mode": outcome.mode})
            if not outcome.spec.supported:
                build.error = f"Unsupported scope: {outcome.spec.unsupported_reason}"
                reporter.emit("build.unsupported", BuildStage.IDEA, "failed", build.error, progress=100, build_status=BuildStatus.UNSUPPORTED_SCOPE)
                return
            reporter.emit("plan.completed", BuildStage.IDEA, "passed", f"Product brief ready: {outcome.spec.name}", progress=15, build_status=BuildStatus.BUILDING, metadata={"agent_mode": outcome.mode})

            build.semantic_alignment = verify_semantic_alignment(
                build.prompt,
                build.product_spec,
                self.settings,
            )
            alignment_path = workspace.write_json(
                "semantic-alignment.json",
                build.semantic_alignment,
            )
            build.artifact_paths["semantic_alignment"] = workspace.relative(alignment_path)
            reporter.emit(
                "plan.semantic_alignment",
                BuildStage.IDEA,
                build.semantic_alignment.status,
                build.semantic_alignment.summary,
                progress=20,
                metadata=build.semantic_alignment.evidence,
            )

            build.hardware = deterministic_hardware_ir(outcome.spec, build.prompt)
            component_ids = [component.component_id for component in build.hardware.components]
            reporter.emit("component.selected", BuildStage.COMPONENTS, "passed", "Selected supported components from the verified catalog.", progress=28, metadata={"component_ids": component_ids})
            reporter.emit("electronics.generated", BuildStage.ELECTRONICS, "running", "Hardware IR generated; checking every rail and signal…", progress=36)
            build.electrical_validation = validate_hardware(build.hardware)
            if not build.electrical_validation.passed:
                build.verification = VerificationReport(electrical_compatibility="failed")
                workspace.write_json("verification.json", build.verification)
                reporter.emit("electronics.verified", BuildStage.ELECTRONICS, "failed", "Deterministic electrical validation found blocking issues.", progress=100, build_status=BuildStatus.NEEDS_REVIEW, metadata={"issues": [issue.model_dump(mode="json") for issue in build.electrical_validation.issues]})
                return
            reporter.emit("electronics.verified", BuildStage.ELECTRONICS, "passed", "Voltage, pin capabilities, GPIO allocation, I²C addresses and required connections passed.", progress=44)
            build.artifact_paths.update(workspace.persist_build_inputs(build))

            firmware_dir = workspace.directory("firmware")
            firmware_files = generate_firmware(build.hardware, firmware_dir)
            build.artifact_paths["firmware_source"] = workspace.relative(firmware_files["source"])
            build.artifact_paths["platformio"] = workspace.relative(firmware_files["platformio"])
            reporter.emit("firmware.generated", BuildStage.FIRMWARE, "passed", "Generated ESP32-S3 firmware from the verified Hardware IR.", progress=52)

            reporter.emit("firmware.compile.started", BuildStage.FIRMWARE, "running", "PlatformIO is compiling the actual firmware…", progress=58, build_status=BuildStatus.TESTING)
            build.firmware = compile_firmware(self.settings, firmware_dir)
            attempts = 0
            while build.firmware.status == "failed" and attempts < self.settings.max_repair_attempts:
                attempts += 1
                reporter.emit("firmware.compile.failed", BuildStage.FIRMWARE, "failed", f"Compiler rejected the firmware. Repair attempt {attempts}/{self.settings.max_repair_attempts} is starting.", progress=60, build_status=BuildStatus.REPAIRING, metadata={"exit_code": build.firmware.evidence.get("exit_code")})
                source_path = firmware_files["source"]
                compiler_output = str(build.firmware.evidence.get("output", ""))
                repaired = False
                try:
                    proposal = asyncio.run(propose_repair(source_path.read_text(encoding="utf-8"), compiler_output, self.settings))
                    if proposal and proposal["find"] in source_path.read_text(encoding="utf-8"):
                        source = source_path.read_text(encoding="utf-8")
                        source_path.write_text(source.replace(proposal["find"], proposal["replace"], 1), encoding="utf-8")
                        repaired = True
                        reporter.emit("agent.repair.started", BuildStage.FIRMWARE, "running", proposal["explanation"], progress=62, metadata={"agent": "EngineeringAgent", "attempt": attempts})
                except Exception as exc:
                    logger.warning("ADK repair proposal failed", extra={"build_id": build_id, "error": redact_text(str(exc), self.settings)})
                if not repaired:
                    repaired = deterministic_repair(source_path, compiler_output)
                    reporter.emit("agent.repair.started", BuildStage.FIRMWARE, "running" if repaired else "failed", "Applied a constrained known-error repair." if repaired else "No safe automatic patch matched the compiler evidence.", progress=62, metadata={"agent": "deterministic-fallback", "attempt": attempts})
                if not repaired:
                    break
                reporter.emit("firmware.compile.started", BuildStage.FIRMWARE, "running", "Recompiling the repaired firmware with PlatformIO…", progress=64, build_status=BuildStatus.TESTING)
                build.firmware = compile_firmware(self.settings, firmware_dir)

            if build.firmware.status == "passed":
                binary = Path(str(build.firmware.evidence.get("firmware_bin")))
                if binary.exists():
                    build.artifact_paths["firmware_bin"] = workspace.relative(binary)
                reporter.emit("firmware.compile.passed", BuildStage.FIRMWARE, "passed", f"PlatformIO compilation passed{f' after {attempts} repair attempt(s)' if attempts else ''}.", progress=70, metadata={"attempts": attempts})
            elif build.firmware.status == "unavailable":
                reporter.emit("firmware.compile.unavailable", BuildStage.FIRMWARE, "unavailable", build.firmware.summary, progress=70, metadata=build.firmware.evidence)
            else:
                reporter.emit("firmware.compile.failed", BuildStage.FIRMWARE, "failed", "Firmware still fails after the bounded repair loop.", progress=70, metadata={"attempts": attempts})

            simulation_dir = workspace.directory("simulation")
            wokwi_files = generate_wokwi(build.hardware, firmware_dir, simulation_dir)
            for key in ("diagram", "config", "scenario"):
                build.artifact_paths[f"wokwi_{key}"] = workspace.relative(wokwi_files[key])
            reporter.emit("simulation.started", BuildStage.SIMULATION, "running", "Prepared a real Wokwi circuit and automated sensor scenario.", progress=76)
            build.simulation = run_wokwi(self.settings, simulation_dir, build.firmware.status == "passed")
            for name, artifact_key in (("serial.log", "wokwi_serial_log"), ("simulation-result.json", "wokwi_result")):
                path = simulation_dir / name
                if path.exists():
                    build.artifact_paths[artifact_key] = workspace.relative(path)
            reporter.emit(f"simulation.{build.simulation.status}", BuildStage.SIMULATION, build.simulation.status, build.simulation.summary, progress=82, metadata=build.simulation.evidence)

            reporter.emit("enclosure.started", BuildStage.ENCLOSURE, "running", "Generating a parametric enclosure around board, display, knob and USB clearances…", progress=86, build_status=BuildStatus.BUILDING)
            enclosure_dir = workspace.directory("enclosure")
            build.enclosure = generate_enclosure(build.hardware, enclosure_dir)
            build.artifact_paths["enclosure_base"] = workspace.relative(enclosure_dir / "base.stl")
            build.artifact_paths["enclosure_lid"] = workspace.relative(enclosure_dir / "lid.stl")
            reporter.emit("enclosure.generated", BuildStage.ENCLOSURE, build.enclosure.status, build.enclosure.summary, progress=92, metadata=build.enclosure.evidence)

            build.verification = VerificationReport(
                electrical_compatibility="passed",
                firmware_compilation=build.firmware.status,
                simulation=build.simulation.status,
                enclosure_generation=build.enclosure.status,
                scenario_checks=list(build.simulation.evidence.get("checks", [])),
            )
            verification_path = workspace.write_json("verification.json", build.verification)
            build.artifact_paths["verification"] = workspace.relative(verification_path)
            reporter.emit("verification.completed", BuildStage.VERIFICATION, "passed", "Verification report issued. Physical assembly, EMI/EMC and thermals remain explicitly unverified.", progress=97, metadata=build.verification.model_dump(mode="json"))
            if self.settings.artifact_bucket:
                uploaded = workspace.publish(self.settings.artifact_bucket)
                reporter.emit(
                    "artifacts.published",
                    BuildStage.VERIFICATION,
                    "passed",
                    f"Published {uploaded} build artifacts to Cloud Storage.",
                    progress=99,
                    metadata={"bucket": self.settings.artifact_bucket, "objects": uploaded},
                )
            digital_evidence_passed = (
                build.firmware.status == "passed"
                and build.enclosure.status == "passed"
                and build.simulation.status == "passed"
            )
            final_status = BuildStatus.COMPLETED if digital_evidence_passed else BuildStatus.NEEDS_REVIEW
            final_event = "build.completed" if final_status == BuildStatus.COMPLETED else "build.needs_review"
            final_message = (
                "Verified digital prototype is ready. Physical assembly is not verified."
                if final_status == BuildStatus.COMPLETED
                else "Digital artifacts are ready, but at least one executed verification step failed or needs review."
            )
            reporter.emit(final_event, BuildStage.COMPLETE, "passed" if final_status == BuildStatus.COMPLETED else "unavailable", final_message, progress=100, build_status=final_status)
        except Exception as exc:
            build.error = redact_text(f"{type(exc).__name__}: {exc}", self.settings)
            # Do not attach the traceback: third-party exceptions can include request credentials.
            logger.error("Build failed", extra={"build_id": build_id, "error": build.error})
            reporter.emit("build.failed", build.stage, "failed", "The worker stopped on real evidence; no success state was fabricated.", progress=100, build_status=BuildStatus.FAILED, metadata={"error": build.error})


def run_build(build_id: str) -> None:
    BuildOrchestrator().run(build_id)
