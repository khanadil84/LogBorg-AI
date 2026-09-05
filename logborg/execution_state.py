"""Live LogBorg execution state — the single source of truth for the dashboard SVG."""

from __future__ import annotations

import copy
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable


PHASES = ("INGEST", "DIAGNOSE", "SAFETY", "REPAIR", "VERIFY", "RECOVERED")

# Node visual states driven only by real orchestrator transitions.
NODE_PENDING = "pending"
NODE_ACTIVE = "active"
NODE_SUCCESS = "success"
NODE_FAILED = "failed"
NODE_SKIPPED = "skipped"

# Edge visual states: idle until the upstream phase completes and flow continues.
EDGE_IDLE = "idle"
EDGE_FLOWING = "flowing"
EDGE_COMPLETE = "complete"
EDGE_FAILED = "failed"


class ExecutionState:
    """Thread-safe live state for one recovery run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._state = self._empty()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "run_id": None,
            "running": False,
            "started_at": None,
            "updated_at": None,
            "finished_at": None,
            "source": None,
            "overall_status": "IDLE",
            "active_phase": None,
            "message": "Awaiting recovery run.",
            "phases": {
                phase: {
                    "name": phase,
                    "state": NODE_PENDING,
                    "started_at": None,
                    "finished_at": None,
                    "detail": None,
                }
                for phase in PHASES
            },
            "edges": {
                f"{a}->{b}": {"from": a, "to": b, "state": EDGE_IDLE}
                for a, b in zip(PHASES, PHASES[1:])
            },
            "evidence": None,
            "events": [],
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def subscribe(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def _emit(self) -> None:
        snapshot = copy.deepcopy(self._state)
        for listener in list(self._listeners):
            try:
                listener(snapshot)
            except Exception:
                pass

    def reset(self, *, source: str, run_id: str) -> None:
        with self._lock:
            self._state = self._empty()
            now = _utcnow()
            self._state["run_id"] = run_id
            self._state["running"] = True
            self._state["started_at"] = now
            self._state["updated_at"] = now
            self._state["source"] = source
            self._state["overall_status"] = "RUNNING"
            self._state["message"] = "Recovery pipeline started."
            self._append_event_locked("PIPELINE", "started", "Recovery pipeline started.")
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def begin_phase(self, phase: str, detail: str | None = None) -> None:
        with self._lock:
            now = _utcnow()
            self._state["updated_at"] = now
            self._state["active_phase"] = phase
            self._state["message"] = detail or f"{phase} in progress."

            node = self._state["phases"][phase]
            node["state"] = NODE_ACTIVE
            node["started_at"] = now
            node["finished_at"] = None
            node["detail"] = detail

            # Upstream edge flows while this phase is active.
            idx = PHASES.index(phase)
            if idx > 0:
                edge_key = f"{PHASES[idx - 1]}->{phase}"
                self._state["edges"][edge_key]["state"] = EDGE_FLOWING

            self._append_event_locked(phase, NODE_ACTIVE, detail or f"{phase} started.")
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def complete_phase(self, phase: str, detail: str | None = None) -> None:
        with self._lock:
            now = _utcnow()
            self._state["updated_at"] = now
            node = self._state["phases"][phase]
            node["state"] = NODE_SUCCESS
            node["finished_at"] = now
            if detail:
                node["detail"] = detail

            idx = PHASES.index(phase)
            if idx > 0:
                edge_key = f"{PHASES[idx - 1]}->{phase}"
                self._state["edges"][edge_key]["state"] = EDGE_COMPLETE

            self._append_event_locked(phase, NODE_SUCCESS, detail or f"{phase} completed.")
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def fail_phase(self, phase: str, status: str, detail: str | None = None) -> None:
        with self._lock:
            now = _utcnow()
            self._state["updated_at"] = now
            self._state["finished_at"] = now
            self._state["running"] = False
            self._state["active_phase"] = phase
            self._state["overall_status"] = status
            self._state["message"] = detail or f"{phase} failed ({status})."

            node = self._state["phases"][phase]
            node["state"] = NODE_FAILED
            node["finished_at"] = now
            node["detail"] = detail

            idx = PHASES.index(phase)
            if idx > 0:
                edge_key = f"{PHASES[idx - 1]}->{phase}"
                self._state["edges"][edge_key]["state"] = EDGE_FAILED

            for later in PHASES[idx + 1 :]:
                self._state["phases"][later]["state"] = NODE_SKIPPED
                self._state["phases"][later]["detail"] = "Skipped after upstream failure."

            self._append_event_locked(phase, NODE_FAILED, detail or status)
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def finish_success(self, status: str = "RECOVERED", detail: str | None = None) -> None:
        with self._lock:
            now = _utcnow()
            self._state["updated_at"] = now
            self._state["finished_at"] = now
            self._state["running"] = False
            self._state["active_phase"] = "RECOVERED"
            self._state["overall_status"] = status
            self._state["message"] = detail or "Workload recovered and verified."

            recovered = self._state["phases"]["RECOVERED"]
            recovered["state"] = NODE_SUCCESS
            recovered["started_at"] = recovered["started_at"] or now
            recovered["finished_at"] = now
            recovered["detail"] = detail or "Recovery verified."

            self._state["edges"]["VERIFY->RECOVERED"]["state"] = EDGE_COMPLETE
            self._append_event_locked("RECOVERED", NODE_SUCCESS, detail or status)
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def mark_healthy(self, detail: str | None = None) -> None:
        """Workload was already healthy after ingest — no repair path taken."""
        with self._lock:
            now = _utcnow()
            self._state["updated_at"] = now
            self._state["finished_at"] = now
            self._state["running"] = False
            self._state["active_phase"] = None
            self._state["overall_status"] = "HEALTHY"
            self._state["message"] = detail or "Runtime already healthy; no remediation required."

            for phase in ("DIAGNOSE", "REPAIR", "VERIFY", "RECOVERED"):
                self._state["phases"][phase]["state"] = NODE_SKIPPED
                self._state["phases"][phase]["detail"] = "Not required — runtime healthy."

            for edge in self._state["edges"].values():
                edge["state"] = EDGE_IDLE

            self._append_event_locked("PIPELINE", "healthy", detail or "HEALTHY")
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def publish_runtime_event(
        self,
        stream: str,
        message: str,
    ) -> None:
        """Publish one real stdout/stderr runtime event to live state."""
        with self._lock:
            now = _utcnow()
            self._state["updated_at"] = now
            self._append_event_locked(
                "INGEST",
                stream.upper(),
                message,
            )
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def set_evidence(self, evidence: dict[str, Any]) -> None:
        with self._lock:
            self._state["evidence"] = copy.deepcopy(evidence)
            self._state["updated_at"] = _utcnow()
            snapshot = copy.deepcopy(self._state)
        self._notify(snapshot)

    def _append_event_locked(self, phase: str, kind: str, message: str) -> None:
        self._state["events"].append(
            {
                "ts": _utcnow(),
                "phase": phase,
                "kind": kind,
                "message": message,
            }
        )
        # Keep the event tail bounded for the live UI.
        self._state["events"] = self._state["events"][-80:]

    def _notify(self, snapshot: dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(snapshot)
            except Exception:
                pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# Process-wide live state used by the orchestrator and dashboard server.
LIVE = ExecutionState()


def new_run_id() -> str:
    return f"run-{int(time.time() * 1000)}"
