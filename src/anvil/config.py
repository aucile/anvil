# AUTHOR: IAN SAVINO
# DATE: 2026

import os
import stat
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

CONFIG_DIR = Path.home() / ".config" / "anvil"
CONFIG_PATH = CONFIG_DIR / "config.toml"


def config_exists() -> bool:
    return CONFIG_PATH.exists()


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _render_value(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(f'"{_escape(str(v))}"' for v in value) + "]"
    return f'"{_escape(str(value))}"'


def _render_toml(data: dict) -> str:
    lines = ["[general]"]
    for key, value in data.get("general", {}).items():
        lines.append(f"{key} = {_render_value(value)}")
    lines.append("")
    lines.append("[keys]")
    for key, value in data.get("keys", {}).items():
        lines.append(f"{key} = {_render_value(value)}")
    return "\n".join(lines) + "\n"


def save_config(data: dict):
    """Write config.toml with owner-only permissions (600) — it holds API keys."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(_render_toml(data), encoding="utf-8")
    os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)


def get_api_key(key_name: str | None) -> str | None:
    """Resolve an API key: environment variable first, then config.toml."""
    if not key_name:
        return None
    env_value = os.environ.get(key_name)
    if env_value:
        return env_value
    return load_config().get("keys", {}).get(key_name)


def get_preferred_model() -> str | None:
    return get_planner_model()


def get_planner_model() -> str | None:
    return load_config().get("general", {}).get("planner_model")


def get_worker_model() -> str | None:
    return load_config().get("general", {}).get("worker_model")


def get_enabled_models() -> list[str]:
    """Legacy support: model names selected by older versions of `anvil init`."""
    return load_config().get("general", {}).get("enabled_models", [])


def save_model_selection(planner: str, worker: str, keys: dict[str, str] | None = None):
    config = load_config()
    config.setdefault("general", {})
    config["general"]["planner_model"] = planner
    config["general"]["worker_model"] = worker
    if keys is not None:
        config["keys"] = keys
    save_config(config)
