"""Configuration loading for the post-fire runoff workflow."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from postfire_runoff.backend.io.paths import project_root as default_project_root, resolve_under_root


@dataclass(frozen=True)
class LoadedConfig:
    path: Path
    root: Path
    data: dict[str, Any]

    def get(self, *keys: str, default: Any = None) -> Any:
        value: Any = self.data
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def resolve(self, value: str | Path) -> Path:
        return resolve_under_root(self.root, value)

    def input_path(self, logical_name: str, required: bool = True) -> Path | None:
        inputs = self.data.get("inputs", {}) or {}
        value = inputs.get(logical_name)
        if value in (None, ""):
            if required:
                raise ConfigError(f"Missing required input mapping: inputs.{logical_name}")
            return None
        return self.resolve(value)


class ConfigError(ValueError):
    """Raised when the project configuration is incomplete or inconsistent."""


def load_config(config_path: str | Path = "config/project.yaml", project_root: str | Path | None = None) -> LoadedConfig:
    path = Path(config_path).expanduser()
    if not path.is_absolute():
        base = default_project_root(project_root)
        path = base / path
    path = path.resolve()
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}

    if project_root is not None:
        root = default_project_root(project_root)
    elif data.get("project_root") not in (None, ""):
        root_value = Path(str(data["project_root"])).expanduser()
        root = root_value.resolve() if root_value.is_absolute() else (path.parent / root_value).resolve()
    elif path.parent.name == "config":
        root = path.parent.parent.resolve()
    else:
        root = default_project_root()
    return LoadedConfig(path=path, root=root, data=data)
