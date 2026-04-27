"""OnyxKraken Component System — unified plugin architecture.

Every capability Onyx can use (Blender, Music, YouTube, Video, etc.)
implements the OnyxComponent contract. The brain decides WHAT to do;
components handle HOW.

    from core.components import component_registry

    blender = component_registry.get("blender")
    result = blender.execute("build_scene", {"description": "a robot cat"})
"""

from core.components.base import OnyxComponent, ComponentResult, ComponentStatus
from core.components.registry import component_registry

__all__ = [
    "OnyxComponent",
    "ComponentResult",
    "ComponentStatus",
    "component_registry",
]
