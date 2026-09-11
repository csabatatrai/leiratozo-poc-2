"""MetricsSink port — feldolgozási idő, RTF, hibaarány, job/session id szerinti
korrelációval. Kívánatos (nem kemény megkötés), minimálisan tartva a skeletonban."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsSink(Protocol):
    def observe_processing_time(self, *, correlation_id: str, stage: str, seconds: float) -> None: ...
    def observe_rtf(self, *, correlation_id: str, rtf: float) -> None: ...
    def increment_error(self, *, error_code: str) -> None: ...
