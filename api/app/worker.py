from __future__ import annotations

import time
from dataclasses import dataclass

from .services import BotSocietyService


@dataclass(slots=True)
class WorkerRunSummary:
    completed_cycles: int
    interval_seconds: int


class PipelineWorker:
    def __init__(self, service: BotSocietyService, interval_seconds: int) -> None:
        self.service = service
        self.interval_seconds = interval_seconds
        self.social_discovery_interval_seconds = max(
            interval_seconds,
            int(getattr(service.settings, "social_discovery_interval_seconds", interval_seconds)),
        )
        self._last_social_discovery_at = 0.0

    def run(self, *, max_cycles: int = 0) -> WorkerRunSummary:
        completed_cycles = 0
        while True:
            completed_cycles += 1
            started_at = time.monotonic()
            worker_controls_social = self._worker_controls_social_discovery()
            result = self.service.run_pipeline_cycle(refresh_social_discovery=not worker_controls_social)
            operation = result.operation
            print(
                f"[{completed_cycles}] cycle={operation.cycle_type if operation else 'n/a'} "
                f"generated={operation.generated_predictions if operation else 0} "
                f"scored={operation.scored_predictions if operation else 0} "
                f"alerts={result.alert_inbox.unread_count}"
            )
            if self._should_run_social_discovery(started_at):
                self._last_social_discovery_at = started_at
                try:
                    social_result = self.service.refresh_social_trader_discovery()
                    warning_suffix = f" warning={social_result.warnings[0]}" if social_result.warnings else ""
                    print(
                        f"[{completed_cycles}] social_discovery provider={social_result.provider} "
                        f"youtube_configured={social_result.youtube_configured} "
                        f"discovered={social_result.discovered} updated={social_result.updated}"
                        f"{warning_suffix}"
                    )
                except Exception as exc:
                    print(f"[{completed_cycles}] social_discovery failed={exc.__class__.__name__}: {exc}")
            if max_cycles and completed_cycles >= max_cycles:
                break
            time.sleep(self.interval_seconds)
        return WorkerRunSummary(completed_cycles=completed_cycles, interval_seconds=self.interval_seconds)

    def _should_run_social_discovery(self, now: float) -> bool:
        if not self._worker_controls_social_discovery():
            return False
        return self._last_social_discovery_at == 0.0 or (
            now - self._last_social_discovery_at >= self.social_discovery_interval_seconds
        )

    def _worker_controls_social_discovery(self) -> bool:
        if self.service.settings.social_discovery_provider != "youtube":
            return False
        if not self.service.settings.youtube_api_key:
            return False
        return True
