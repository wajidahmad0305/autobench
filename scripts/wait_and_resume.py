"""Multi-day auto-resume driver for the AutoBench thesis pilot.

Groq's free-tier tokens-per-day (TPD) cap resets at 00:00 UTC. This script:

1. sleeps until just after the next 00:00 UTC reset (+5 min buffer),
2. runs ``scripts/run_pilot.py`` as a subprocess - it resumes from the
   per-trajectory trace checkpoint and, thanks to ``_DailyQuotaExhausted``,
   exits with code 2 the moment it hits the TPD cap again,
3. checks the trace count; if < 120 it loops back to step 1.

Safety-capped at 5 loops. Emits a heartbeat line every 30 minutes while waiting.
Survives the parent shell closing when launched via ``Start-Process``.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = REPO_ROOT / "experiments" / "thesis_pilot"
TRACES_DIR = PILOT_DIR / "traces"
RUN_LOG = PILOT_DIR / "run_log.txt"
RUN_PILOT = REPO_ROOT / "scripts" / "run_pilot.py"

TOTAL_TRAJECTORIES = 120
MAX_LOOPS = 5
POST_RESET_BUFFER_S = 5 * 60
HEARTBEAT_S = 30 * 60
# If the script starts within this window past a midnight, the quota has just
# reset - resume immediately instead of waiting ~24h.
RECENT_RESET_GRACE_S = 60 * 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(event: str, **fields: object) -> None:
    ts = _now().isoformat(timespec="seconds")
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"[{ts}] {event} {extra}".rstrip(), flush=True)


def _trace_count() -> int:
    return len(list(TRACES_DIR.glob("*.json"))) if TRACES_DIR.is_dir() else 0


def _next_resume_at(now: datetime, *, allow_grace: bool) -> datetime:
    midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if allow_grace and (now - midnight_today).total_seconds() < RECENT_RESET_GRACE_S:
        return now
    next_midnight = midnight_today + timedelta(days=1)
    return next_midnight + timedelta(seconds=POST_RESET_BUFFER_S)


def _wait_until(resume_at: datetime) -> None:
    while True:
        now = _now()
        remaining = (resume_at - now).total_seconds()
        if remaining <= 0:
            return
        print(
            f"[HEARTBEAT] {now.isoformat(timespec='seconds')} - waiting for "
            f"{int(remaining)} more seconds until next quota reset. "
            f"Traces so far: {_trace_count()}/{TOTAL_TRAJECTORIES}",
            flush=True,
        )
        time.sleep(min(HEARTBEAT_S, remaining))


def _run_pilot_once() -> int:
    _log("resume_start", traces_before=_trace_count())
    with RUN_LOG.open("a", encoding="utf-8") as logf:
        logf.write(f"\n\n===== RESUME {_now().isoformat()} =====\n")
        logf.flush()
        proc = subprocess.Popen(
            [sys.executable, str(RUN_PILOT)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if proc.stdout is not None:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                logf.write(line)
                logf.flush()
        proc.wait()
    rc = int(proc.returncode or 0)
    _log("resume_exit", returncode=rc, traces_after=_trace_count())
    return rc


def main() -> int:
    _log("startup", traces=f"{_trace_count()}/{TOTAL_TRAJECTORIES}", max_loops=MAX_LOOPS)
    ran_pilot = False

    for loop in range(1, MAX_LOOPS + 1):
        if _trace_count() >= TOTAL_TRAJECTORIES:
            _log("all_done", traces=f"{_trace_count()}/{TOTAL_TRAJECTORIES}")
            return 0

        now = _now()
        resume_at = _next_resume_at(now, allow_grace=not ran_pilot)
        _log(
            "loop",
            n=loop,
            now_utc=now.isoformat(timespec="seconds"),
            resume_at_utc=resume_at.isoformat(timespec="seconds"),
            wait_seconds=max(0, int((resume_at - now).total_seconds())),
        )
        _wait_until(resume_at)

        rc = _run_pilot_once()
        ran_pilot = True

        done = _trace_count()
        if done >= TOTAL_TRAJECTORIES:
            _log("all_done", traces=f"{done}/{TOTAL_TRAJECTORIES}", loops_used=loop)
            return 0
        _log(
            "loop_incomplete",
            n=loop,
            returncode=rc,
            traces=f"{done}/{TOTAL_TRAJECTORIES}",
            reason="daily quota re-hit" if rc == 2 else "run_pilot exited (non-quota)",
        )

    _log("max_loops_reached", traces=f"{_trace_count()}/{TOTAL_TRAJECTORIES}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

