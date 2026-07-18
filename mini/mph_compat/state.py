"""Small mutable server state."""

from __future__ import annotations

from ..utils.config import DEFAULT_BACKEND

_default_backend = DEFAULT_BACKEND if DEFAULT_BACKEND in {"mph", "gui"} else "mph"


def get_default_backend() -> str:
    return _default_backend


def set_default_backend(backend: str) -> dict:
    global _default_backend
    backend = (backend or "").strip().lower()
    if backend not in {"mph", "gui"}:
        return {"success": False, "error": "backend must be 'mph' or 'gui'", "default_backend": _default_backend}
    _default_backend = backend
    return {"success": True, "default_backend": _default_backend}

