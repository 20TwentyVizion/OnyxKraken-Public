"""Hand base class and data structures.

Every Hand extends this base class and implements execute().
The scheduler calls execute() on the Hand's configured schedule.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

_log = logging.getLogger("core.hands")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class HandStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class HandManifest:
    """Configuration manifest for a Hand (equivalent to HAND.toml)."""
    id: str
    name: str
    description: str
    schedule_minutes: int = 60       # Run every N minutes (0 = manual only)
    enabled: bool = True
    max_runtime_seconds: int = 300   # Kill if exceeds this
    retry_on_failure: bool = True
    max_retries: int = 2
    required_services: list[str] = field(default_factory=list)  # e.g. ["Ollama", "ACE-Step"]
    min_disk_gb: float = 1.0
    min_ram_gb: float = 1.0
    tags: list[str] = field(default_factory=list)
    settings: dict = field(default_factory=dict)  # Hand-specific config


@dataclass
class HandResult:
    """Result of a single Hand execution."""
    success: bool
    message: str = ""
    data: dict = field(default_factory=dict)
    duration: float = 0.0
    error: str = ""
    items_processed: int = 0       # e.g. posts created, files cleaned


@dataclass
class HandMetrics:
    """Running metrics for a Hand."""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_items_processed: int = 0
    total_runtime: float = 0.0
    last_run_time: float = 0.0
    last_result: str = ""
    last_error: str = ""
    streak: int = 0  # consecutive successes (negative = consecutive failures)

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100

    @property
    def avg_runtime(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.total_runtime / self.total_runs

    def record(self, result: HandResult):
        self.total_runs += 1
        self.total_runtime += result.duration
        self.last_run_time = time.time()
        self.total_items_processed += result.items_processed
        if result.success:
            self.successful_runs += 1
            self.last_result = result.message
            self.last_error = ""
            self.streak = max(1, self.streak + 1)
        else:
            self.failed_runs += 1
            self.last_result = ""
            self.last_error = result.error
            self.streak = min(-1, self.streak - 1)


# ---------------------------------------------------------------------------
# Hand base class
# ---------------------------------------------------------------------------

class Hand(ABC):
    """Abstract base class for all Hands.

    Subclasses must implement:
      - manifest property (return a HandManifest)
      - execute() method (do the actual work)

    Optionally override:
      - preflight() for pre-execution checks
      - on_activate() / on_deactivate() for lifecycle hooks
    """

    def __init__(self):
        self._status = HandStatus.IDLE
        self._metrics = HandMetrics()
        self._activated_at: float = 0.0

    @property
    @abstractmethod
    def manifest(self) -> HandManifest:
        """Return this Hand's manifest configuration."""
        ...

    @abstractmethod
    def execute(self) -> HandResult:
        """Execute the Hand's primary task. Called by the scheduler."""
        ...

    # -- Lifecycle --

    def on_activate(self):
        """Called when the Hand is activated (enabled and scheduled)."""
        self._activated_at = time.time()
        _log.info("Hand '%s' activated", self.manifest.id)

    def on_deactivate(self):
        """Called when the Hand is deactivated."""
        _log.info("Hand '%s' deactivated", self.manifest.id)

    # -- Pre-flight --

    def preflight(self) -> tuple[bool, str]:
        """Check if conditions are met to run. Returns (ok, reason).

        Default implementation checks resources (disk, RAM) via SystemHealth,
        then ensures required services are running via service_launcher
        (auto-starts any that are missing).
        """
        # Resource checks (passive — cannot auto-fix low disk/RAM)
        try:
            from core.system_health import health

            if self.manifest.min_disk_gb > 0:
                disk = health.check_disk()
                if disk.free_gb < self.manifest.min_disk_gb:
                    return False, f"Need {self.manifest.min_disk_gb}GB disk, have {disk.free_gb:.1f}GB"

            if self.manifest.min_ram_gb > 0:
                ram = health.check_ram()
                if ram.available_gb < self.manifest.min_ram_gb:
                    return False, f"Need {self.manifest.min_ram_gb}GB RAM, have {ram.available_gb:.1f}GB"
        except ImportError:
            _log.debug("SystemHealth not available for resource preflight")

        # Service checks (active — auto-start missing services)
        if self.manifest.required_services:
            try:
                from core.service_launcher import ensure_services
                all_ok, failures = ensure_services(self.manifest.required_services)
                if not all_ok:
                    return False, "; ".join(failures)
            except ImportError:
                # Fallback: passive check only
                try:
                    from core.system_health import health
                    for svc_name in self.manifest.required_services:
                        svc_lower = svc_name.lower()
                        if svc_lower == "ollama":
                            svc = health.check_ollama()
                        elif svc_lower in ("acestep", "ace-step"):
                            svc = health.check_acestep()
                        elif svc_lower == "justedit":
                            svc = health.check_justedit()
                        elif svc_lower == "ffmpeg":
                            svc = health.check_ffmpeg()
                        else:
                            continue
                        if not svc.running:
                            return False, f"Required service '{svc_name}' is not running"
                except ImportError:
                    pass

        return True, ""

    # -- Status / Metrics --

    @property
    def status(self) -> HandStatus:
        return self._status

    @property
    def metrics(self) -> HandMetrics:
        return self._metrics

    def get_dashboard_info(self) -> dict:
        """Return dashboard-friendly status info."""
        m = self.manifest
        met = self._metrics
        return {
            "id": m.id,
            "name": m.name,
            "status": self._status,
            "enabled": m.enabled,
            "schedule_minutes": m.schedule_minutes,
            "total_runs": met.total_runs,
            "success_rate": f"{met.success_rate:.0f}%",
            "avg_runtime": f"{met.avg_runtime:.1f}s",
            "last_run": time.strftime(
                "%H:%M:%S", time.localtime(met.last_run_time)
            ) if met.last_run_time else "never",
            "last_result": met.last_result or met.last_error or "—",
            "items_processed": met.total_items_processed,
            "streak": met.streak,
        }

    def get_summary(self) -> str:
        """Human-readable summary."""
        m = self.manifest
        met = self._metrics
        status = self._status.upper()
        schedule = f"every {m.schedule_minutes}min" if m.schedule_minutes else "manual"
        return (
            f"{m.name} [{status}] ({schedule})\n"
            f"  {m.description}\n"
            f"  Runs: {met.total_runs} | "
            f"Success: {met.success_rate:.0f}% | "
            f"Avg: {met.avg_runtime:.1f}s | "
            f"Items: {met.total_items_processed}"
        )
