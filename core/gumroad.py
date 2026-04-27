"""Public stub of core.gumroad -- payment integration is private build only."""
from __future__ import annotations


def is_component_licensed(_component: str) -> bool:
    """Public build treats every component as licensed."""
    return True
