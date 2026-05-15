"""Compatibility module for older imports.

The active cinematic window is defined in main.py so the requested file
structure stays compact. Import CommandWindow from main when launching.
"""

from __future__ import annotations


def Dashboard(*args, **kwargs):  # noqa: N802
    from main import CommandWindow

    return CommandWindow(*args, **kwargs)
