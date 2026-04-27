"""Pytest configuration — ensure project root is on sys.path."""

import os
import sys

# Add project root to path so tests can import top-level modules (config, log, etc.)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
