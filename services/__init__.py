from __future__ import annotations

from importlib import import_module


_ROUTER_MODULES = {
    "form_router": "services.form.main",
    "bot_router": "services.bot.main",
    "llm_router": "services.llm.main",
    "parser_router": "services.parser.main",
    "scoring_router": "services.scoring.main",
    "dashboard_router": "services.dashboard.main",
}

__all__ = list(_ROUTER_MODULES)


def __getattr__(name: str):
    module_name = _ROUTER_MODULES.get(name)
    if not module_name:
        raise AttributeError(f"module 'services' has no attribute '{name}'")
    module = import_module(module_name)
    return getattr(module, "router")
