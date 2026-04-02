from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.utils.config_store import load_raw_config, save_raw_config

router = APIRouter()

TOOL_CATALOG = [
    {
        "name": "read_file",
        "description": "Read file content from the workspace.",
        "category": "filesystem",
        "config_key": "read_file",
    },
    {
        "name": "write_file",
        "description": "Create or overwrite files in the workspace.",
        "category": "filesystem",
        "config_key": "write_file",
    },
    {
        "name": "edit_file",
        "description": "Apply targeted edits to existing files.",
        "category": "filesystem",
        "config_key": "edit_file",
    },
    {
        "name": "list_dir",
        "description": "Inspect directories available to the agent.",
        "category": "filesystem",
        "config_key": "list_dir",
    },
    {
        "name": "exec",
        "description": "Run shell commands inside the configured workspace.",
        "category": "filesystem",
        "config_key": "exec",
    },
    {
        "name": "web_search",
        "description": "Search the web using the configured provider.",
        "category": "web",
        "config_key": "web_search",
    },
    {
        "name": "web_fetch",
        "description": "Fetch and summarize a webpage.",
        "category": "web",
        "config_key": "web_fetch",
    },
    {
        "name": "message",
        "description": "Send a follow-up message to the active channel.",
        "category": "communication",
        "config_key": "message",
    },
    {
        "name": "spawn",
        "description": "Launch a delegated sub-agent task.",
        "category": "agents",
        "config_key": "spawn",
    },
    {
        "name": "cron",
        "description": "Schedule reminders and recurring jobs.",
        "category": "automation",
        "config_key": "cron",
    },
]


@router.get("/api/tools")
async def tools(request: Request):
    context = request.app.state.launcher_context
    raw = load_raw_config(context.config_path)
    exec_cfg = ((raw.get("tools") or {}).get("exec") or {})
    exec_enabled = bool(exec_cfg.get("enable", True))

    items = []
    for entry in TOOL_CATALOG:
        status = "enabled"
        if entry["name"] == "exec":
            status = "enabled" if exec_enabled else "disabled"
        items.append({**entry, "status": status})
    return {"tools": items}


@router.put("/api/tools/{name}/state")
async def update_tool_state(name: str, request: Request):
    if name != "exec":
        return JSONResponse(
            {"error": "only the exec tool can be toggled in this launcher"},
            status_code=400,
        )

    context = request.app.state.launcher_context
    payload = await request.json()
    enabled = bool(payload.get("enabled"))

    raw = load_raw_config(context.config_path)
    tools = raw.setdefault("tools", {})
    exec_cfg = tools.get("exec")
    if not isinstance(exec_cfg, dict):
        exec_cfg = {}
    exec_cfg["enable"] = enabled
    tools["exec"] = exec_cfg
    save_raw_config(context.config_path, raw)
    return {"status": "ok"}
