"""Bot Society Markets application package."""

from __future__ import annotations


def __getattr__(name: str):
    if name == "create_app":
        from .main import create_app

        return create_app
    if name == "app":
        from .main import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["app", "create_app"]
