"""Job source plugins.

Importing a community plugin is a two-step flow: ``/plugins/preview`` shows the
prompts, a list of warnings and the file's SHA-256; ``/plugins/import`` installs
it only if the hash the user approved still matches. A community plugin whose
file changes later is disabled until it is reviewed again.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from engine import prompts
from models import PluginImportRequest, PluginPreviewRequest, PluginToggleRequest

from .common import api_error, plugin_registry

router = APIRouter()


def _plugin_dict(p) -> dict:
    return {
        "name": p.name, "display_name": p.display_name, "version": p.version, "author": p.author,
        "description": p.description, "countries": p.countries, "website": p.website,
        "requires_login": p.requires_login, "login_url": p.login_url, "is_builtin": p.is_builtin,
        "enabled": p.enabled, "sha256": p.sha256, "tampered": p.tampered,
        "filters": [
            {"key": f.key, "label": f.label, "type": f.type, "options": f.options,
             "url_param": f.url_param, "default": f.default}
            for f in p.filters
        ],
    }


@router.get("/plugins")
async def get_plugins(country: Optional[str] = Query(None)):
    registry = plugin_registry()
    plugins = registry.get_for_country(country) if country else registry.get_all()
    return {"success": True, "plugins": [_plugin_dict(p) for p in plugins]}


@router.post("/plugins/preview")
async def preview_plugin(body: PluginPreviewRequest):
    try:
        return {"success": True, "plugin": plugin_registry().preview_plugin(body.file_path)}
    except (FileNotFoundError, ValueError) as e:
        return api_error("preview_failed", str(e), 400)


@router.post("/plugins/import")
async def import_plugin(body: PluginImportRequest):
    registry = plugin_registry()
    if not body.approved_sha256:
        # Old clients: return the preview so the UI can ask the user to review it
        try:
            preview = registry.preview_plugin(body.file_path)
        except (FileNotFoundError, ValueError) as e:
            return api_error("import_failed", str(e), 400)
        return {"success": False, "needs_review": True, "plugin": preview}
    try:
        plugin = registry.import_plugin(body.file_path, approved_sha256=body.approved_sha256)
        return {"success": True, "plugin": {"name": plugin.name, "display_name": plugin.display_name}}
    except (FileNotFoundError, ValueError) as e:
        return api_error("import_failed", str(e), 400)


@router.put("/plugins/{name}/toggle")
async def toggle_plugin(name: str, body: PluginToggleRequest):
    registry = plugin_registry()
    plugin = registry.get_by_name(name)
    if plugin is not None and plugin.tampered and body.enabled:
        return api_error("needs_review", "This plugin's file changed since you approved it. Import it again to review.", 409)
    if not registry.set_enabled(name, body.enabled):
        return api_error("not_found", f"Plugin '{name}' not found", 404)
    return {"success": True, "name": name, "enabled": body.enabled}


@router.delete("/plugins/{name}")
async def remove_plugin(name: str):
    try:
        if not plugin_registry().remove_plugin(name):
            return api_error("not_found", f"Plugin '{name}' not found", 404)
        return {"success": True}
    except ValueError as e:
        return api_error("remove_failed", str(e), 400)


@router.post("/plugins/reload")
async def reload_plugins():
    prompts.reset_registry()
    registry = plugin_registry()
    return {"success": True, "count": len(registry.get_all())}
