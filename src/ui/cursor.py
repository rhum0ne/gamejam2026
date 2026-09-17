"""Curseur : visible dans les menus, cache en jeu apres un delai d'inactivite."""

from __future__ import annotations

import arcade

import settings


def show(window: arcade.Window | None) -> None:
    """Affiche le curseur et remet le compteur d'inactivite a zero."""
    if window is None:
        return
    if not getattr(window, "_pointer_visible", True):
        window.set_mouse_visible(True)
        window._pointer_visible = True
    window._pointer_idle = 0.0


def note(window: arcade.Window | None) -> None:
    """Un mouvement ou un clic : le curseur reapparait."""
    show(window)


def tick(window: arcade.Window | None, delta_time: float, *, hide: bool) -> None:
    """En jeu, cache le curseur apres `MOUSE_HIDE_DELAY` sans activite."""
    if window is None:
        return
    if not hide:
        show(window)
        return
    idle = getattr(window, "_pointer_idle", 0.0) + max(0.0, delta_time)
    window._pointer_idle = idle
    if idle >= settings.MOUSE_HIDE_DELAY and getattr(window, "_pointer_visible", True):
        window.set_mouse_visible(False)
        window._pointer_visible = False
