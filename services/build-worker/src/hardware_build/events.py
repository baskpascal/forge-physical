from __future__ import annotations

from uuid import uuid4

from .models import Build, BuildEvent, BuildStage, BuildStatus
from .security import redact, redact_text
from .settings import get_settings
from .storage import BuildStore


class BuildReporter:
    def __init__(self, store: BuildStore, build: Build):
        self.store = store
        self.build = build

    def emit(
        self,
        event_type: str,
        stage: BuildStage,
        status: str,
        message: str,
        *,
        progress: int | None = None,
        build_status: BuildStatus | None = None,
        metadata: dict | None = None,
    ) -> None:
        settings = get_settings()
        self.build.stage = stage
        if progress is not None:
            self.build.progress = progress
        if build_status is not None:
            self.build.status = build_status
        self.store.save(self.build)
        self.store.add_event(
            self.build.id,
            BuildEvent(
                id=uuid4().hex,
                type=event_type,
                stage=stage,
                status=status,
                message=redact_text(message, settings),
                metadata=redact(metadata or {}, settings),
            ),
        )
