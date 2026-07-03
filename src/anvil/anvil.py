# AUTHOR: IAN SAVINO
# DATE: 2026

import argparse
import os
from pathlib import Path
import sys

import questionary

from anvil import config, storage

PRESETS = [
    {
        "tag": "openai",
        "label": "OpenAI — gpt-4o-mini",
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "key_name": "OPENAI_API_KEY",
        "specialty": "general assistant",
    },
    {
        "tag": "anthropic",
        "label": "Anthropic — claude-sonnet-4-6",
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-6",
        "base_url": None,
        "key_name": "ANTHROPIC_API_KEY",
        "specialty": "general assistant",
    },
    {
        "tag": "grok",
        "label": "Grok — grok-4",
        "provider": "openai-compatible",
        "model_id": "grok-4",
        "base_url": "https://api.x.ai/v1",
        "key_name": "XAI_API_KEY",
        "specialty": "general assistant",
    },
    {
        "tag": "deepseek",
        "label": "Deepseek — deepseek-chat",
        "provider": "openai-compatible",
        "model_id": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "key_name": "DEEPSEEK_API_KEY",
        "specialty": "general assistant",
    },
    {
        "tag": "qwen",
        "label": "Qwen — local Ollama model (RECOMMENDED WORKER; FURTHER CONFIG REQUIRED)",
        "provider": "ollama",
        "model_id": None,
        "base_url": None,
        "key_name": None,
        "specialty": "worker"
    }
]


def read_storage(limit: int = 10):
    """Print recent request history straight from storage — no API key needed."""
    for request in storage.get_history(limit):
        print(f"\n{'='*60}")
        print(f"Request #{request['id']}  ({request['created_at']})")
        print(f"Request: {request['request_text']}")
        print(f"Subtasks:")
        for sub in request["subtasks"]:
            print(f"  [{sub['subtask_index']}] {sub['subtask_text']}")
            print(f"      {sub['model']}: {str(sub['result'])[:200]}")
        print(f"Final answer: {(request['final_answer'] or '(none)')[:300]}...")


def _asked(answer):
    """Unwrap a questionary answer; None means the user hit Ctrl-C."""
    if answer is None:
        raise SystemExit("Setup cancelled.")
    return answer


KNOWN_PROVIDERS = ("anthropic", "openai-compatible", "openai", "ollama")

CUSTOM_CHOICE = "__custom__"


def _validate_provider(value: str):
    if value.strip() in KNOWN_PROVIDERS:
        return True
    return (
        f"Error: unknown provider '{value.strip()}' — "
        "must be anthropic, openai-compatible, or ollama"
    )


def _custom_model(tier: str) -> dict:
    """Prompt for a custom model's specs and register it for the given role."""
    name = _asked(questionary.text(
        "Model name (tag used to reference it):",
        validate=lambda v: bool(v.strip()) or "name is required",
    ).ask()).strip()

    model = storage.get_model(name) or {
        "name": name,
        "model_id": "",
        "provider": "",
        "specialty": None,
        "tier": tier,
        "base_url": None,
        "key_name": None,
    }

    model["model_id"] = _asked(questionary.text(
        "model_id (the provider's model identifier):",
        default=model["model_id"] or "",
        validate=lambda v: bool(v.strip()) or "model_id is required",
    ).ask()).strip()
    model["provider"] = _asked(questionary.text(
        "provider (anthropic/openai-compatible/ollama):",
        default=model["provider"] or "",
        validate=_validate_provider,
    ).ask()).strip()
    model["specialty"] = _asked(questionary.text(
        "specialty (free text, blank to skip):",
        default=model["specialty"] or "",
    ).ask()).strip() or None
    model["base_url"] = _asked(questionary.text(
        "base_url (blank for Anthropic and Ollama):",
        default=model["base_url"] or "",
    ).ask()).strip() or None
    model["key_name"] = _asked(questionary.text(
        "key_name (env var for the API key, blank for Ollama):",
        default=model["key_name"] or "",
    ).ask()).strip() or None
    model["tier"] = tier

    storage.upsert_model(model)
    return model


def _select_model(role: str) -> dict:
    """Pick a preset for the given role, or define a custom model via 'Other'."""
    choices = [questionary.Choice(title=p["label"], value=p) for p in PRESETS]
    choices.append(questionary.Choice(
        title="Other — add your own model (custom specs)", value=CUSTOM_CHOICE,
    ))
    preset = _asked(questionary.select(
        f"Select your {role} model preset:", choices=choices,
    ).ask())
    if preset == CUSTOM_CHOICE:
        return _custom_model(role)

    model = storage.get_model(preset["tag"]) or {
        "name": preset["tag"],
        "model_id": preset["model_id"],
        "provider": preset["provider"],
        "specialty": preset["specialty"],
        "tier": role,
        "base_url": preset["base_url"],
        "key_name": preset["key_name"],
    }
    model["model_id"] = _asked(questionary.text(
        f"Model id for '{model['name']}':",
        default=model["model_id"] or "",
        validate=lambda v: bool(v.strip()) or "model_id is required",
    ).ask()).strip()
    model["provider"] = preset["provider"]
    model["specialty"] = preset["specialty"]
    model["tier"] = role
    model["base_url"] = preset["base_url"]
    model["key_name"] = preset["key_name"]
    storage.upsert_model(model)
    return model


def run_init():
    """Interactive setup: choose planner and worker models and store any needed API keys."""
    storage.init_db()
    existing = config.load_config()

    planner = _select_model("planner")
    worker = _select_model("worker")

    # Ask only for the keys the selected models actually reference
    keys = dict(existing.get("keys", {}))
    for key_name in sorted({m["key_name"] for m in (planner, worker) if m["key_name"]}):
        hints = []
        if os.environ.get(key_name):
            hints.append("set in env — env wins")
        if keys.get(key_name):
            hints.append("saved")
        hint = f" ({', '.join(hints)})" if hints else ""
        value = _asked(questionary.password(
            f"{key_name}{hint} — blank to keep/skip:",
        ).ask()).strip()
        if value:
            keys[key_name] = value

    config.save_model_selection(planner["name"], worker["name"], keys)
    print(f"Config saved to {config.CONFIG_PATH} (permissions set to 600).")


def ensure_config():
    """Trigger the interactive setup the first time it's needed."""
    if not config.config_exists():
        print("No anvil configuration found — let's set one up.")
        run_init()


def view_config():
    """Print the current model config: planner/worker selection, models, key status."""
    cfg = config.load_config()
    general = cfg.get("general", {})
    planner = general.get("planner_model")
    worker = general.get("worker_model")

    location = str(config.CONFIG_PATH)
    if not config.config_exists():
        location += " (not created — run `anvil init`)"
    print("Model configuration")
    print(f"  config file: {location}")
    print(f"  planner:     {planner or '(unset)'}")
    print(f"  worker:      {worker or '(unset)'}")

    models = storage.get_models()
    print(f"\nRegistered models ({len(models)}):")
    for m in models:
        roles = [r for r, name in (("planner", planner), ("worker", worker)) if m["name"] == name]
        tag = f"  <- {', '.join(roles)}" if roles else ""
        print(f"  {m['name']:12} {m['model_id']:24} {m['provider']:18} tier={m['tier']}{tag}")

    key_names = sorted({m["key_name"] for m in models if m["key_name"]})
    if key_names:
        saved = cfg.get("keys", {})
        print("\nAPI keys:")
        for key_name in key_names:
            if os.environ.get(key_name):
                status = "set in environment"
            elif saved.get(key_name):
                status = "saved in config"
            else:
                status = "MISSING — run `anvil init`"
            print(f"  {key_name}: {status}")

    print("\nEdit: `anvil init` to change planner/worker, `anvil -c <name>` to edit a model.")


def reset_config():
    """Delete the saved config file (planner/worker selection + saved API keys)."""
    if not config.config_exists():
        print("No config to reset.")
        return
    confirm = input(
        f"Delete {config.CONFIG_PATH} (selection + saved API keys)? [y/N] "
    ).strip().lower()
    if confirm != "y":
        print("Reset cancelled.")
        return
    config.CONFIG_PATH.unlink()
    print("Config reset. Run `anvil init` to set up again.")


def configure_model(name: str):
    """Interactively edit (or register) the model with the given tag."""
    existing = storage.get_model(name) or {
        "name": name,
        "model_id": "",
        "provider": "",
        "specialty": None,
        "tier": "worker",
        "base_url": None,
        "key_name": None,
    }

    if storage.get_model(name):
        print(f"Editing model '{name}' — press Enter to keep the current value.")
    else:
        print(f"Registering new model '{name}'.")

    def ask(field: str, current, required: bool = False):
        shown = current if current is not None else ""
        while True:
            value = input(f"  {field} [{shown}]: ").strip()
            if value:
                return value
            if current not in (None, ""):
                return current
            if not required:
                return None
            print(f"    {field} is required.")

    existing["model_id"] = ask("model_id", existing["model_id"], required=True)
    while True:
        provider = ask("provider (anthropic/openai-compatible/ollama)", existing["provider"], required=True)
        if provider in ("anthropic", "openai-compatible", "openai", "ollama"):
            existing["provider"] = provider
            break
        print("    provider must be 'anthropic', 'openai-compatible', or 'ollama'.")
    existing["specialty"] = ask("specialty", existing["specialty"])
    while True:
        tier = ask("tier (planner/worker)", existing["tier"], required=True)
        if tier in ("planner", "worker"):
            existing["tier"] = tier
            break
        print("    tier must be 'planner' or 'worker'.")
    existing["base_url"] = ask("base_url", existing["base_url"])
    existing["key_name"] = ask("key_name (env var for API key)", existing["key_name"])

    storage.upsert_model(existing)
    print(f"Model '{name}' saved.")


def main():
    parser = argparse.ArgumentParser(description="construct simple instructions with a high-functioning model and pass them to a lower one")
    
    parser.add_argument("request", nargs="?", default=None, type=str, help="the request to be processed")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-o", "--orchestrate", action="store_true", help="used with request details to activate the model")
    group.add_argument("-f", "--forget", action="store_true", help="erases storage memory")
    group.add_argument("-s", "--storage", action="store_true", help="access memory of requests")
    group.add_argument("-c", "--config", metavar="MODEL", type=str, help="edit or register the model with the given tag")
    group.add_argument("-v", "--view", action="store_true", help="view the current model config (selection, models, key status)")
    group.add_argument("--reset", action="store_true", help="reset the saved model config (planner/worker selection + saved keys)")

    args = parser.parse_args()

    # `anvil init` (bare) runs setup; with any flag set, "init" is just request text
    if args.request == "init" and not (args.orchestrate or args.forget or args.storage or args.config or args.view or args.reset):
        run_init()
        sys.exit(0)

    # Handle --forget before init_db(), which would recreate the file just to delete it
    if args.forget:
        db_path = Path(storage.DB_PATH)
        if db_path.exists():
            db_path.unlink()
            print("Storage has been erased.")
        else:
            print("No storage database found.")
        sys.exit(0)

    storage.init_db()

    if args.config:
        configure_model(args.config)
        sys.exit(0)

    if args.view:
        view_config()
        sys.exit(0)

    if args.reset:
        reset_config()
        sys.exit(0)

    if args.storage:
        read_storage()
        sys.exit(0)

    if (args.orchestrate and args.request):
        ensure_config()
        from anvil import orchestrator
        print(orchestrator.orchestrate(args.request))
    elif (args.request):
        raise SystemExit("Error: Did you mean to run the anvil with -o?")
    elif (args.orchestrate):
        ensure_config()
        from anvil import orchestrator
        print("What is your request?")
        err_request = input("Enter it here: ")
        print(orchestrator.orchestrate(err_request))
    else:
        parser.print_help()

if __name__ == "__main__": main()