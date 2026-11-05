"""NEG cosmetic control: importable names, no behavior."""

from __future__ import annotations


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise NotImplementedError(f"cosmetic stub: {name}")
