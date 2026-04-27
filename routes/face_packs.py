"""Face Pack API routes — browse, install, activate, and manage face packs.

Endpoints:
    GET  /face-packs              — List all discovered packs
    GET  /face-packs/active       — Get the currently active pack
    POST /face-packs/activate     — Activate a pack by ID
    POST /face-packs/deactivate   — Deactivate (revert to default)
    POST /face-packs/install      — Install a pack from uploaded .zip
    POST /face-packs/install-dir  — Install a pack from a local directory
    DELETE /face-packs/{pack_id}  — Uninstall a user-installed pack
    GET  /face-packs/{pack_id}    — Get details for a specific pack
"""

import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

_log = logging.getLogger("routes.face_packs")

router = APIRouter(prefix="/face-packs", tags=["face-packs"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ActivateRequest(BaseModel):
    pack_id: str


class InstallDirRequest(BaseModel):
    path: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_manager():
    from core.face_packs import pack_manager
    if not pack_manager._packs:
        pack_manager.init()
    return pack_manager


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def list_packs(tag: Optional[str] = Query(None), free_only: bool = Query(False)):
    """List all discovered face packs."""
    mgr = _get_manager()
    packs = mgr.list_packs(tag=tag, free_only=free_only)
    return {
        "packs": [p.to_dict() for p in packs],
        "active": mgr._active_pack_id,
        "count": len(packs),
    }


@router.get("/active")
def get_active():
    """Get the currently active face pack."""
    mgr = _get_manager()
    pack = mgr.get_active_pack()
    if pack:
        return {"active": True, "pack": pack.to_dict()}
    return {"active": False, "pack": None, "message": "Using default face."}


@router.post("/activate")
def activate_pack(req: ActivateRequest):
    """Activate a face pack by ID."""
    mgr = _get_manager()
    pack = mgr.get_pack(req.pack_id)
    if not pack:
        raise HTTPException(404, f"Pack '{req.pack_id}' not found.")
    if not pack.is_licensed:
        raise HTTPException(403, f"Pack '{req.pack_id}' requires a license. Purchase at {_gumroad_url()}")
    ok = mgr.activate_pack(req.pack_id)
    if ok:
        return {"message": f"Activated face pack: {pack.name}", "pack": pack.to_dict()}
    raise HTTPException(500, "Failed to activate pack.")


@router.post("/deactivate")
def deactivate_pack():
    """Deactivate the current face pack (revert to default)."""
    mgr = _get_manager()
    mgr.activate_pack(None)
    return {"message": "Reverted to default face."}


@router.post("/install")
async def install_from_zip(file: UploadFile = File(...)):
    """Install a face pack from an uploaded .zip file."""
    if not file.filename.endswith(".zip"):
        raise HTTPException(400, "File must be a .zip archive.")

    mgr = _get_manager()

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        pack = mgr.install_from_zip(tmp_path)
        if pack:
            return {"message": f"Installed face pack: {pack.name}", "pack": pack.to_dict()}
        raise HTTPException(400, "Failed to install pack. Check the zip contains a valid manifest.json.")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/install-dir")
def install_from_dir(req: InstallDirRequest):
    """Install a face pack from a local directory path."""
    if not os.path.isdir(req.path):
        raise HTTPException(400, f"Directory not found: {req.path}")

    mgr = _get_manager()
    pack = mgr.install_from_directory(req.path)
    if pack:
        return {"message": f"Installed face pack: {pack.name}", "pack": pack.to_dict()}
    raise HTTPException(400, "Failed to install. Directory must contain manifest.json.")


@router.delete("/{pack_id}")
def uninstall_pack(pack_id: str):
    """Uninstall a user-installed face pack."""
    mgr = _get_manager()
    pack = mgr.get_pack(pack_id)
    if not pack:
        raise HTTPException(404, f"Pack '{pack_id}' not found.")
    if pack.builtin:
        raise HTTPException(400, f"Cannot uninstall built-in pack '{pack_id}'.")

    ok = mgr.uninstall(pack_id)
    if ok:
        return {"message": f"Uninstalled face pack: {pack.name}"}
    raise HTTPException(500, "Failed to uninstall pack.")


@router.get("/{pack_id}")
def get_pack_detail(pack_id: str):
    """Get detailed info for a specific face pack."""
    mgr = _get_manager()
    pack = mgr.get_pack(pack_id)
    if not pack:
        raise HTTPException(404, f"Pack '{pack_id}' not found.")
    return {
        "pack": pack.to_dict(),
        "is_active": mgr._active_pack_id == pack_id,
        "spec_overrides_keys": list(pack.spec_overrides.keys()) if pack.spec_overrides else [],
    }


def _gumroad_url() -> str:
    try:
        from core.pricing import GUMROAD_URL
        return GUMROAD_URL
    except ImportError:
        return "https://markvizion.gumroad.com/l/onyxkraken"
