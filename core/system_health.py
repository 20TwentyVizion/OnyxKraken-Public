"""System Health Monitor — Onyx's interoception (awareness of its own resource state).

Provides real-time insight into CPU, RAM, VRAM, disk, and running services
so Onyx can make smarter decisions about what it can attempt.

Usage:
    from core.system_health import health

    summary = health.get_summary()       # LLM-friendly text report
    report  = health.get_report()        # structured dict
    ok      = health.can_generate_music() # pre-flight checks

CLI:
    python -m core.system_health
"""

import logging
import os
import shutil
import sys
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_log = logging.getLogger("core.system_health")

_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CpuInfo:
    usage_percent: float = 0.0
    core_count: int = 0
    freq_mhz: float = 0.0


@dataclass
class RamInfo:
    total_gb: float = 0.0
    used_gb: float = 0.0
    available_gb: float = 0.0
    percent: float = 0.0


@dataclass
class VramInfo:
    available: bool = False
    gpu_name: str = ""
    total_gb: float = 0.0
    used_gb: float = 0.0
    free_gb: float = 0.0
    percent: float = 0.0
    driver_version: str = ""


@dataclass
class DiskInfo:
    total_gb: float = 0.0
    used_gb: float = 0.0
    free_gb: float = 0.0
    percent: float = 0.0
    path: str = ""


@dataclass
class ServiceStatus:
    name: str
    running: bool = False
    pid: int = 0
    url: str = ""
    details: str = ""


@dataclass
class HealthReport:
    """Complete system health snapshot."""
    timestamp: float = 0.0
    cpu: CpuInfo = field(default_factory=CpuInfo)
    ram: RamInfo = field(default_factory=RamInfo)
    vram: VramInfo = field(default_factory=VramInfo)
    disk: DiskInfo = field(default_factory=DiskInfo)
    services: list[ServiceStatus] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    os_info: str = ""


# ---------------------------------------------------------------------------
# System Health Monitor
# ---------------------------------------------------------------------------

class SystemHealth:
    """Onyx's awareness of its own system resource state.

    All methods are safe to call at any time — they catch exceptions
    and return sensible defaults on failure.
    """

    def __init__(self):
        self._last_report: Optional[HealthReport] = None
        self._cache_ttl = 5.0  # seconds
        self._last_check = 0.0

    # -- CPU --

    def check_cpu(self) -> CpuInfo:
        """Get CPU usage, core count, and frequency."""
        info = CpuInfo()
        try:
            import psutil
            info.usage_percent = psutil.cpu_percent(interval=0.5)
            info.core_count = psutil.cpu_count(logical=True) or 0
            freq = psutil.cpu_freq()
            if freq:
                info.freq_mhz = freq.current
        except ImportError:
            # Fallback: os.cpu_count
            info.core_count = os.cpu_count() or 0
            info.usage_percent = -1  # unknown
        except Exception as exc:
            _log.debug("CPU check failed: %s", exc)
        return info

    # -- RAM --

    def check_ram(self) -> RamInfo:
        """Get RAM usage."""
        info = RamInfo()
        try:
            import psutil
            mem = psutil.virtual_memory()
            info.total_gb = mem.total / (1024 ** 3)
            info.used_gb = mem.used / (1024 ** 3)
            info.available_gb = mem.available / (1024 ** 3)
            info.percent = mem.percent
        except ImportError:
            _log.debug("psutil not available for RAM check")
        except Exception as exc:
            _log.debug("RAM check failed: %s", exc)
        return info

    # -- VRAM (NVIDIA GPU via nvidia-smi) --

    def check_vram(self) -> VramInfo:
        """Get GPU VRAM usage via nvidia-smi."""
        info = VramInfo()
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ]
            result = subprocess.run(
                cmd, capture_output=True, timeout=10, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 5:
                    info.available = True
                    info.gpu_name = parts[0].strip()
                    info.total_gb = float(parts[1].strip()) / 1024
                    info.used_gb = float(parts[2].strip()) / 1024
                    info.free_gb = float(parts[3].strip()) / 1024
                    info.driver_version = parts[4].strip()
                    if info.total_gb > 0:
                        info.percent = (info.used_gb / info.total_gb) * 100
        except FileNotFoundError:
            _log.debug("nvidia-smi not found — no NVIDIA GPU or driver not installed")
        except Exception as exc:
            _log.debug("VRAM check failed: %s", exc)
        return info

    # -- Disk --

    def check_disk(self, path: str = "") -> DiskInfo:
        """Get disk usage for the drive containing the project."""
        if not path:
            path = str(_ROOT)
        info = DiskInfo(path=path)
        try:
            usage = shutil.disk_usage(path)
            info.total_gb = usage.total / (1024 ** 3)
            info.used_gb = usage.used / (1024 ** 3)
            info.free_gb = usage.free / (1024 ** 3)
            if info.total_gb > 0:
                info.percent = (info.used_gb / info.total_gb) * 100
        except Exception as exc:
            _log.debug("Disk check failed: %s", exc)
        return info

    # -- Service detection --

    def check_ollama(self) -> ServiceStatus:
        """Check if Ollama is running and responsive."""
        svc = ServiceStatus(name="Ollama", url="http://localhost:11434")
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://localhost:11434/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    import json
                    data = json.loads(resp.read())
                    models = [m.get("name", "") for m in data.get("models", [])]
                    svc.running = True
                    svc.details = f"{len(models)} model(s) available"
        except Exception:
            svc.running = False
            svc.details = "Not responding"
        return svc

    def check_ollama_loaded_models(self) -> list[str]:
        """Get list of currently loaded Ollama models (in VRAM)."""
        try:
            import urllib.request, json
            req = urllib.request.Request(
                "http://localhost:11434/api/ps",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def check_acestep(self) -> ServiceStatus:
        """Check if ACE-Step music generation server is running.

        ACE-Step may run on port 7860 (Gradio default) or 8001 (EVERA adapter).
        """
        svc = ServiceStatus(name="ACE-Step")
        # Check both possible ports
        for port in (8001, 7860):
            try:
                import urllib.request
                url = f"http://localhost:{port}/"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        svc.running = True
                        svc.url = url
                        svc.details = f"Responding on port {port}"
                        return svc
            except Exception:
                pass
            # Also try /api/predict for Gradio
            if port == 7860:
                try:
                    req = urllib.request.Request(
                        f"http://localhost:{port}/api/predict", method="GET")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        svc.running = True
                        svc.url = f"http://localhost:{port}"
                        svc.details = f"Gradio API on port {port}"
                        return svc
                except Exception:
                    pass

        svc.running = False
        svc.details = "Not responding (checked ports 8001, 7860)"
        return svc

    def check_justedit(self) -> ServiceStatus:
        """Check if JustEdit dev server is running."""
        svc = ServiceStatus(name="JustEdit", url="http://localhost:5173")
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://localhost:5173/",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    svc.running = True
                    svc.details = "Vite dev server responding"
        except Exception:
            svc.running = False
            svc.details = "Not responding"
        return svc

    def check_blender(self) -> ServiceStatus:
        """Check if Blender is currently running."""
        svc = ServiceStatus(name="Blender")
        try:
            import psutil
            for proc in psutil.process_iter(["name", "pid"]):
                if proc.info["name"] and "blender" in proc.info["name"].lower():
                    svc.running = True
                    svc.pid = proc.info["pid"]
                    svc.details = f"PID {proc.info['pid']}"
                    break
        except ImportError:
            # Fallback: check via tasklist on Windows
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq blender.exe", "/FO", "CSV", "/NH"],
                    capture_output=True, timeout=5, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if "blender" in result.stdout.lower():
                    svc.running = True
                    svc.details = "Found via tasklist"
            except Exception:
                pass
        except Exception as exc:
            _log.debug("Blender check failed: %s", exc)
        return svc

    def check_ffmpeg(self) -> ServiceStatus:
        """Check if ffmpeg is available on PATH."""
        svc = ServiceStatus(name="ffmpeg")
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True, timeout=5, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                svc.running = True
                # Extract version from first line
                first_line = result.stdout.split("\n")[0] if result.stdout else ""
                svc.details = first_line[:60]
        except FileNotFoundError:
            svc.details = "Not found on PATH"
        except Exception:
            svc.details = "Check failed"
        return svc

    # -- Composite checks (pre-flight) --

    def check_all_services(self) -> list[ServiceStatus]:
        """Check all known services."""
        return [
            self.check_ollama(),
            self.check_acestep(),
            self.check_justedit(),
            self.check_blender(),
            self.check_ffmpeg(),
        ]

    def ensure_service(self, name: str) -> tuple[bool, str]:
        """Auto-start a service if it's not running. Returns (ok, message).

        Uses core.service_launcher for the actual start logic.
        """
        try:
            from core.service_launcher import ensure_service
            return ensure_service(name)
        except ImportError:
            _log.debug("service_launcher not available — cannot auto-start")
            return False, f"Auto-start unavailable for {name}"

    def ensure_services(self, names: list[str]) -> tuple[bool, list[str]]:
        """Auto-start multiple services. Returns (all_ok, failure_messages)."""
        try:
            from core.service_launcher import ensure_services
            return ensure_services(names)
        except ImportError:
            failures = []
            for name in names:
                ok, msg = self.ensure_service(name)
                if not ok:
                    failures.append(msg)
            return len(failures) == 0, failures

    def can_generate_music(self, auto_start: bool = False) -> bool:
        """Pre-flight: enough VRAM and ACE-Step running?

        If auto_start=True, will attempt to start ACE-Step automatically.
        """
        vram = self.check_vram()
        if vram.available and vram.free_gb < 4.0:
            return False

        acestep = self.check_acestep()
        if acestep.running:
            return True

        if auto_start:
            ok, _ = self.ensure_service("ACE-Step")
            return ok
        return False

    def can_run_vision(self, auto_start: bool = False) -> bool:
        """Pre-flight: Ollama running with vision model loaded?"""
        ollama = self.check_ollama()
        if not ollama.running:
            if auto_start:
                ok, _ = self.ensure_service("Ollama")
                if not ok:
                    return False
            else:
                return False
        loaded = self.check_ollama_loaded_models()
        return any("vision" in m or "llava" in m for m in loaded)

    def can_record_screen(self) -> bool:
        """Pre-flight: enough disk space for screen recording?"""
        disk = self.check_disk()
        return disk.free_gb >= 2.0

    def can_run_chain_workflow(self, workflow_id: str = "",
                               auto_start: bool = True) -> tuple[bool, list[str]]:
        """Pre-flight check for chain workflows. Returns (ok, issues).

        When auto_start=True (default), missing services are started
        automatically before reporting failure.
        """
        issues = []
        disk = self.check_disk()
        if disk.free_gb < 5.0:
            issues.append(f"Low disk space: {disk.free_gb:.1f} GB free (need 5+)")

        ram = self.check_ram()
        if ram.available_gb < 2.0:
            issues.append(f"Low RAM: {ram.available_gb:.1f} GB available")

        vram = self.check_vram()
        if vram.available and vram.free_gb < 3.0:
            issues.append(f"Low VRAM: {vram.free_gb:.1f} GB free")

        # Determine which services this workflow needs
        needed = ["ffmpeg", "Ollama"]
        if workflow_id in ("full_production", "music_video", "highlight_reel", "3d_showcase"):
            needed.append("ACE-Step")
        if workflow_id in ("full_production", "music_video", "highlight_reel"):
            needed.append("JustEdit")
        if workflow_id in ("3d_showcase",):
            needed.append("Blender")

        # Auto-start or passive check
        if auto_start:
            all_ok, svc_failures = self.ensure_services(needed)
            issues.extend(svc_failures)
        else:
            for svc_name in needed:
                svc_lower = svc_name.lower()
                if svc_lower == "ollama":
                    svc = self.check_ollama()
                elif svc_lower in ("acestep", "ace-step"):
                    svc = self.check_acestep()
                elif svc_lower == "justedit":
                    svc = self.check_justedit()
                elif svc_lower == "ffmpeg":
                    svc = self.check_ffmpeg()
                elif svc_lower == "blender":
                    svc = self.check_blender()
                else:
                    continue
                if not svc.running:
                    issues.append(f"{svc_name} not running")

        return (len(issues) == 0, issues)

    # -- Full report --

    def get_report(self, force: bool = False) -> HealthReport:
        """Get a full system health report. Cached for 5 seconds."""
        now = time.time()
        if not force and self._last_report and (now - self._last_check) < self._cache_ttl:
            return self._last_report

        report = HealthReport(
            timestamp=now,
            cpu=self.check_cpu(),
            ram=self.check_ram(),
            vram=self.check_vram(),
            disk=self.check_disk(),
            services=self.check_all_services(),
            os_info=f"{sys.platform} (runtime)",
        )

        # Generate warnings
        if report.ram.percent > 85:
            report.warnings.append(f"High RAM usage: {report.ram.percent:.0f}%")
        if report.vram.available and report.vram.percent > 85:
            report.warnings.append(f"High VRAM usage: {report.vram.percent:.0f}%")
        if report.disk.free_gb < 5:
            report.warnings.append(f"Low disk space: {report.disk.free_gb:.1f} GB free")
        if report.cpu.usage_percent > 90:
            report.warnings.append(f"High CPU usage: {report.cpu.usage_percent:.0f}%")

        self._last_report = report
        self._last_check = now
        return report

    def get_summary(self, force: bool = False) -> str:
        """Get an LLM-friendly text summary of system health."""
        r = self.get_report(force=force)
        lines = [
            f"System Health ({time.strftime('%H:%M:%S', time.localtime(r.timestamp))})",
            f"  OS: {r.os_info}",
            f"  CPU: {r.cpu.usage_percent:.0f}% usage, {r.cpu.core_count} cores",
            f"  RAM: {r.ram.used_gb:.1f}/{r.ram.total_gb:.1f} GB ({r.ram.percent:.0f}%)",
        ]

        if r.vram.available:
            lines.append(
                f"  GPU: {r.vram.gpu_name} — "
                f"{r.vram.used_gb:.1f}/{r.vram.total_gb:.1f} GB VRAM "
                f"({r.vram.free_gb:.1f} GB free)"
            )
        else:
            lines.append("  GPU: No NVIDIA GPU detected")

        lines.append(
            f"  Disk: {r.disk.free_gb:.1f}/{r.disk.total_gb:.1f} GB free"
        )

        lines.append("  Services:")
        for svc in r.services:
            status = "RUNNING" if svc.running else "STOPPED"
            detail = f" — {svc.details}" if svc.details else ""
            lines.append(f"    {svc.name}: {status}{detail}")

        if r.warnings:
            lines.append("  Warnings:")
            for w in r.warnings:
                lines.append(f"    ! {w}")

        return "\n".join(lines)

    def get_context_prompt(self) -> str:
        """Return a compact health string suitable for LLM system prompts."""
        r = self.get_report()
        parts = [f"RAM:{r.ram.available_gb:.0f}GB free"]
        if r.vram.available:
            parts.append(f"VRAM:{r.vram.free_gb:.1f}GB free({r.vram.gpu_name})")
        parts.append(f"Disk:{r.disk.free_gb:.0f}GB free")

        running = [s.name for s in r.services if s.running]
        stopped = [s.name for s in r.services if not s.running]
        if running:
            parts.append(f"Running:{','.join(running)}")
        if stopped:
            parts.append(f"Stopped:{','.join(stopped)}")
        if r.warnings:
            parts.append(f"WARNINGS:{'; '.join(r.warnings)}")

        return " | ".join(parts)


# Module-level singleton
health = SystemHealth()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    print(health.get_summary(force=True))
    print()

    # Pre-flight checks
    print("Pre-flight checks:")
    print(f"  Can generate music: {health.can_generate_music()}")
    print(f"  Can run vision: {health.can_run_vision()}")
    print(f"  Can record screen: {health.can_record_screen()}")

    ok, issues = health.can_run_chain_workflow("full_production")
    print(f"  Full production workflow: {'OK' if ok else 'ISSUES'}")
    for issue in issues:
        print(f"    - {issue}")

    print()
    print("LLM context prompt:")
    print(f"  {health.get_context_prompt()}")
