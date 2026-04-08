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

    def run(self, *, max_cycles: int = 0) -> WorkerRunSummary:
        completed_cycles = 0
        while True:
            completed_cycles += 1
            result = self.service.run_pipeline_cycle()
            operation = result.operation
            print(
                f"[{completed_cycles}] cycle={operation.cycle_type if operation else 'n/a'} "
                f"generated={operation.generated_predictions if operation else 0} "
                f"scored={operation.scored_predictions if operation else 0} "
                f"alerts={result.alert_inbox.unread_count}"
            )
            if max_cycles and completed_cycles >= max_cycles:
                break
            time.sleep(self.interval_seconds)
        return WorkerRunSummary(completed_cycles=completed_cycles, interval_seconds=self.interval_seconds)
