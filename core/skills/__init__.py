"""OnyxKraken Skills — high-level capability modules.

Skills are higher-level than app modules. A skill combines multiple
modules, APIs, and LLM calls into a coherent capability:

  - content_creation: Research → Write → Publish → Analyze
  - coding: Plan → Generate → Test → Deploy
  - 3d_creation: Concept → Model → Animate → Render

Each skill registers itself and tracks confidence/usage metrics.
"""

from core.skills.base_skill import Skill, SkillRegistry, get_skill_registry

__all__ = ["Skill", "SkillRegistry", "get_skill_registry"]
