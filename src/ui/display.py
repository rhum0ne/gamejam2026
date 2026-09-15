"""Plein ecran et detection des raccourcis d'affichage.

Raccourcis :
    F11
    Alt+Entree (Windows / Linux)
    Cmd+Entree (macOS, MOD_ACCEL)
"""

from __future__ import annotations

import arcade


def wants_fullscreen_toggle(symbol: int, modifiers: int) -> bool:
    """Indique si la combinaison clavier demande un basculement plein ecran."""
    if symbol == arcade.key.F11:
        return True
    enter = symbol in (arcade.key.ENTER, arcade.key.RETURN, arcade.key.NUM_ENTER)
    if not enter:
        return False
    return bool(modifiers & (arcade.key.MOD_ALT | arcade.key.MOD_ACCEL))


def toggle_fullscreen(window: arcade.Window) -> None:
    """Passe de fenetre a plein ecran, et inversement."""
    window.set_fullscreen(not window.fullscreen)


def handle_display_key(window: arcade.Window, symbol: int, modifiers: int) -> bool:
    """Traite un raccourci d'affichage. Retourne True s'il a ete consomme."""
    if wants_fullscreen_toggle(symbol, modifiers):
        toggle_fullscreen(window)
        return True
    return False


def use_default_camera(window: arcade.Window) -> None:
    """Reactive la camera par defaut (menus, apres une vue de jeu)."""
    camera = getattr(window, "default_camera", None)
    if camera is not None:
        camera.use()
