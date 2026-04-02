from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app_runtime import GatewayRuntime


@dataclass(slots=True)
class LauncherContext:
    project_root: Path
    config_path: Path
    launcher_config_path: Path
    models_store_path: Path
    runtime: GatewayRuntime
    dashboard_token: str
    dashboard_session_cookie: str
    dashboard_token_generated: bool
    chat_ws_token: str
    chat_runtime: Any

    @property
    def frontend_dist_candidates(self) -> list[Path]:
        return [
            self.project_root / "web" / "backend" / "dist",
            self.project_root / "web" / "frontend" / "dist",
            self.project_root / "web" / "backend" / "dist",
        ]
