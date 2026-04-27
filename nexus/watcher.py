"""Nexus FolderWatcher — daemon that auto-ingests new files from watched directories.

Runs as a background thread, polling watched directories for new or modified files.
When detected, files are routed through the intake pipeline automatically.

No external dependencies (uses polling, not inotify/FSEvents).
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

_log = logging.getLogger("nexus.watcher")


class FolderWatcher:
    """Watches directories for new files and triggers callbacks.

    Uses simple polling (cross-platform, no watchdog dependency).
    Runs on a daemon thread — dies when the main process exits.
    """

    def __init__(self, watch_dirs: Optional[List[str]] = None,
                 on_new_file: Optional[Callable[[str], None]] = None,
                 poll_interval: float = 5.0,
                 extensions: Optional[Set[str]] = None):
        """
        Args:
            watch_dirs: List of directory paths to watch.
            on_new_file: Callback(file_path) when a new file is detected.
            poll_interval: Seconds between directory scans.
            extensions: Set of file extensions to watch (e.g. {".txt", ".md"}).
                        None = watch all files.
        """
        self._watch_dirs = watch_dirs or []
        self._on_new_file = on_new_file
        self._poll_interval = poll_interval
        self._extensions = extensions

        self._known_files: Dict[str, float] = {}  # path → mtime
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Initialize known files (don't trigger on existing files)
        self._scan_initial()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start watching in a background daemon thread."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="nexus-watcher",
        )
        self._thread.start()
        _log.info("FolderWatcher started: watching %d directories (poll=%.1fs)",
                  len(self._watch_dirs), self._poll_interval)

    def stop(self):
        """Stop watching."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._poll_interval + 1)
        self._thread = None
        _log.info("FolderWatcher stopped")

    def add_directory(self, dir_path: str):
        """Add a directory to the watch list."""
        if dir_path not in self._watch_dirs:
            self._watch_dirs.append(dir_path)
            # Scan to mark existing files as known
            self._scan_dir(dir_path, trigger=False)

    def remove_directory(self, dir_path: str):
        """Remove a directory from the watch list."""
        if dir_path in self._watch_dirs:
            self._watch_dirs.remove(dir_path)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watched_dirs(self) -> List[str]:
        return list(self._watch_dirs)

    @property
    def known_file_count(self) -> int:
        return len(self._known_files)

    # ------------------------------------------------------------------
    # Internal polling
    # ------------------------------------------------------------------

    def _poll_loop(self):
        """Main polling loop — runs on daemon thread."""
        while not self._stop_event.is_set():
            try:
                for dir_path in self._watch_dirs:
                    self._scan_dir(dir_path, trigger=True)
            except Exception as e:
                _log.error("Watcher poll error: %s", e)

            self._stop_event.wait(self._poll_interval)

    def _scan_dir(self, dir_path: str, trigger: bool = True):
        """Scan a directory for new or modified files."""
        if not os.path.isdir(dir_path):
            return

        try:
            for entry in os.scandir(dir_path):
                if not entry.is_file():
                    continue

                # Extension filter
                if self._extensions:
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext not in self._extensions:
                        continue

                # Skip hidden files and manifests
                if entry.name.startswith("."):
                    continue

                file_path = entry.path
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue

                # Check if new or modified
                prev_mtime = self._known_files.get(file_path)
                if prev_mtime is None or mtime > prev_mtime:
                    self._known_files[file_path] = mtime
                    if trigger and self._on_new_file:
                        try:
                            self._on_new_file(file_path)
                        except Exception as e:
                            _log.error("Callback failed for %s: %s", file_path, e)

        except PermissionError:
            _log.debug("Permission denied scanning %s", dir_path)

    def _scan_initial(self):
        """Scan all watched dirs to build the known-files baseline."""
        for dir_path in self._watch_dirs:
            self._scan_dir(dir_path, trigger=False)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
