"""Background scene facade for the command interface."""

from __future__ import annotations

from ui.renderer import CinematicRenderer


class BackgroundField(CinematicRenderer):
    """Named layer used by the main surface.

    Keeping this facade separate makes the file structure explicit while the
    heavy rendering work lives in renderer.py.
    """

    pass
