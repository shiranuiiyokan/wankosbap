from __future__ import annotations

import shutil
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class QCResult:
    ok: bool
    action: str
    reasons: list[str]
    metrics: dict

    def to_dict(self):
        return asdict(self)


def disk_guard(path: Path, minimum_free_gb: float = 4.0) -> QCResult:
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024 ** 3)
    ok = free_gb >= minimum_free_gb
    return QCResult(
        ok=ok,
        action="continue" if ok else "wait_retry",
        reasons=[] if ok else [f"runner free disk {free_gb:.2f}GB < {minimum_free_gb:.2f}GB"],
        metrics={"free_disk_gb": round(free_gb, 2)},
    )


def duration_qc(job: dict, seconds: float) -> QCResult:
    q = job["quality"]
    if job["format"] == "long":
        minimum = float(q["long_min_seconds"])
        ok = seconds >= minimum
        return QCResult(
            ok=ok,
            action="continue" if ok else "rebuild_content",
            reasons=[] if ok else [f"long narration {seconds:.1f}s < target {minimum:.1f}s"],
            metrics={"duration_seconds": round(seconds, 1), "minimum_seconds": minimum},
        )

    minimum = float(q["short_min_seconds"])
    maximum = float(q["short_max_seconds"])
    ok = minimum <= seconds <= maximum
    reasons = []
    if seconds < minimum:
        reasons.append(f"short narration {seconds:.1f}s < target {minimum:.1f}s")
    if seconds > maximum:
        reasons.append(f"short narration {seconds:.1f}s > target {maximum:.1f}s")
    return QCResult(
        ok=ok,
        action="continue" if ok else "rebuild_content",
        reasons=reasons,
        metrics={"duration_seconds": round(seconds, 1), "minimum_seconds": minimum, "maximum_seconds": maximum},
    )


def pronunciation_qc(risks: list[str]) -> QCResult:
    unique = sorted(set(risks))
    return QCResult(
        ok=not unique,
        action="continue" if not unique else "needs_pronunciation_map",
        reasons=[] if not unique else [f"unresolved pronunciation risk: {x}" for x in unique],
        metrics={"unresolved_count": len(unique)},
    )
