"""BaseJsonStore — shared JSON persistence base class.

Eliminates the duplicated _load/_save pattern across:
  - memory/store.py (MemoryStore)
  - core/knowledge.py (KnowledgeStore)
  - core/self_improvement.py (_Store)

Concurrency safety:
  - Per-path ``threading.Lock`` guards in-process concurrent access
    (FastAPI threads, autonomy daemon, orchestrator all share one process).
  - Atomic writes via write-to-temp + ``os.replace`` to prevent partial-write
    corruption if the process is killed mid-save.
"""

import json
import logging
import os
import threading

_log = logging.getLogger("store")

# Global registry of per-path locks so every store instance sharing a file
# serialises access even if multiple BaseJsonStore objects exist.
_path_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    """Return (or create) the threading.Lock for *path*."""
    norm = os.path.normpath(os.path.abspath(path))
    with _registry_lock:
        if norm not in _path_locks:
            _path_locks[norm] = threading.Lock()
        return _path_locks[norm]


class BaseJsonStore:
    """JSON-backed persistent store with safe load/save and schema enforcement."""

    def __init__(self, path: str, default: dict):
        self.path = path
        self._default = default
        self._lock = _lock_for(path)
        self._data = self._load()

    def _load(self) -> dict:
        with self._lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for key, default_val in self._default.items():
                        if key not in data:
                            data[key] = type(default_val)() if isinstance(default_val, (list, dict)) else default_val
                    return data
                except (json.JSONDecodeError, IOError) as e:
                    _log.warning(f"Failed to load {self.path}: {e}")
            return json.loads(json.dumps(self._default))

    def _save(self):
        with self._lock:
            dir_name = os.path.dirname(self.path) or "."
            os.makedirs(dir_name, exist_ok=True)
            tmp_path = self.path + ".tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, default=str)
                os.replace(tmp_path, self.path)  # atomic on same filesystem
            except OSError as e:
                _log.warning(f"Failed to save {self.path}: {e}")
                # Clean up temp file on failure
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass  # temp cleanup is best-effort

    @property
    def data(self) -> dict:
        return self._data
