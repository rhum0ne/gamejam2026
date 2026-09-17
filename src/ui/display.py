"""Plein ecran, placement de la fenetre et raccourcis d'affichage.

Raccourcis :
    F11
    Alt+Entree (Windows / Linux)
    Cmd+Entree (macOS, MOD_ACCEL)
"""

from __future__ import annotations

import arcade


def center_on_primary_screen(window: arcade.Window) -> None:
    """Place la fenetre au milieu de l'ecran principal.

    `arcade.Window.center_window` compare la taille de l'ecran (points) a
    `get_framebuffer_size()` (pixels physiques). Sur un ecran Retina le
    rapport 2x donne des coordonnees negatives : la fenetre nait hors cadre,
    a gauche, et il faut la glisser a la main.
    """
    if window.fullscreen:
        return
    screen_width, screen_height = arcade.get_display_size()
    x = max(0, (screen_width - int(window.width)) // 2)
    y = max(0, (screen_height - int(window.height)) // 2)
    window.set_location(x, y)


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
    leaving_fullscreen = window.fullscreen
    window.set_fullscreen(not window.fullscreen)
    if leaving_fullscreen:
        center_on_primary_screen(window)


def handle_display_key(window: arcade.Window, symbol: int, modifiers: int) -> bool:
    """Traite un raccourci d'affichage. Retourne True s'il a ete consomme."""
    if wants_fullscreen_toggle(symbol, modifiers):
        toggle_fullscreen(window)
        return True
    return False


def use_default_camera(window: arcade.Window) -> None:
    """Reactive la camera ecran (menus, HUD, panneau de l'editeur).

    La camera monde de l'editeur active un scissor : il faut le couper ici,
    sinon le panneau et la barre d'etat sont dessines hors de la zone carte
    et n'apparaissent pas.
    """
    camera = getattr(window, "default_camera", None)
    if camera is not None:
        camera.scissor = None
        camera.use()
    window.ctx.scissor = None
    from src.ui.cursor import show as show_cursor

    show_cursor(window)
