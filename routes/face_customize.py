"""Face Customization API routes — read/write face customization settings.

Endpoints:
    GET  /face/customize            — Get current face customization config
    POST /face/customize            — Apply face customization changes
    GET  /face/customize/presets    — List saved face presets
    POST /face/customize/presets    — Save a new face preset
    DELETE /face/customize/presets/{name} — Delete a saved preset
    GET  /face/customize/spec       — Get the full face spec (themes, styles, etc.)
    POST /face/customize/reset      — Reset customization to defaults
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_log = logging.getLogger("routes.face_customize")

router = APIRouter(prefix="/face/customize", tags=["face-customize"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CustomizeRequest(BaseModel):
    face_theme: Optional[str] = None
    eye_style: Optional[str] = None
    face_shape: Optional[str] = None
    accessory: Optional[str] = None
    scan_lines: Optional[bool] = None
    custom_accent_color: Optional[str] = None
    geometry: Optional[dict] = None
    animation: Optional[dict] = None


class PresetSaveRequest(BaseModel):
    name: str
    config: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def get_customization():
    """Get the current face customization settings."""
    from face.settings import load_settings
    s = load_settings()
    return {
        "face_theme": s.get("face_theme", "cyan"),
        "eye_style": s.get("eye_style", "default"),
        "face_shape": s.get("face_shape", "default"),
        "accessory": s.get("accessory", "none"),
        "scan_lines": s.get("scan_lines", True),
        "custom_accent_color": s.get("custom_accent_color", ""),
        "geometry": s.get("geometry", {}),
        "animation": s.get("animation", {}),
    }


@router.post("")
async def set_customization(req: CustomizeRequest):
    """Apply face customization changes and persist them."""
    from face.settings import load_settings, save_settings
    s = load_settings()

    if req.face_theme is not None:
        s["face_theme"] = req.face_theme
    if req.eye_style is not None:
        s["eye_style"] = req.eye_style
    if req.face_shape is not None:
        s["face_shape"] = req.face_shape
    if req.accessory is not None:
        s["accessory"] = req.accessory
    if req.scan_lines is not None:
        s["scan_lines"] = req.scan_lines
    if req.custom_accent_color is not None:
        s["custom_accent_color"] = req.custom_accent_color
    if req.geometry is not None:
        existing_geo = s.get("geometry", {})
        existing_geo.update(req.geometry)
        s["geometry"] = existing_geo
    if req.animation is not None:
        existing_anim = s.get("animation", {})
        existing_anim.update(req.animation)
        s["animation"] = existing_anim

    save_settings(s)
    _log.info("Face customization updated")
    return {"status": "ok", "settings": s}


@router.get("/presets")
async def list_presets():
    """List all saved face presets."""
    from face.settings import load_settings
    s = load_settings()
    presets = s.get("face_presets", {})
    return {"presets": presets}


@router.post("/presets")
async def save_preset(req: PresetSaveRequest):
    """Save a named face preset."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Preset name cannot be empty")

    from face.settings import load_settings, save_settings
    s = load_settings()
    presets = s.get("face_presets", {})
    presets[req.name.strip()] = req.config
    s["face_presets"] = presets
    save_settings(s)
    return {"status": "ok", "name": req.name.strip()}


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    """Delete a saved face preset by name."""
    from face.settings import load_settings, save_settings
    s = load_settings()
    presets = s.get("face_presets", {})
    if name not in presets:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    del presets[name]
    s["face_presets"] = presets
    save_settings(s)
    return {"status": "ok", "deleted": name}


@router.get("/spec")
async def get_face_spec():
    """Get the full face spec (themes, eye styles, face shapes, accessories)."""
    from face.face_gui import _THEMES, _EYE_STYLES, _FACE_SHAPES, _ACCESSORIES, _SPEC
    return {
        "themes": _THEMES,
        "eye_styles": _EYE_STYLES,
        "face_shapes": _FACE_SHAPES,
        "accessories": _ACCESSORIES,
        "geometry_defaults": _SPEC.get("geometry", {}),
        "animation_defaults": _SPEC.get("animation", {}),
        "emotion_presets": list(_SPEC.get("emotion_presets", {}).keys()),
    }


@router.post("/reset")
async def reset_customization():
    """Reset face customization to defaults."""
    from face.settings import load_settings, save_settings, DEFAULTS
    s = load_settings()
    for key in ("face_theme", "eye_style", "face_shape", "accessory",
                "scan_lines", "custom_accent_color", "geometry", "animation"):
        s[key] = DEFAULTS.get(key, "")
    save_settings(s)
    return {"status": "ok", "message": "Face customization reset to defaults"}
