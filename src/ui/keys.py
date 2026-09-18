"""Icones de touches PNG (feuilles Kenney) avec etat relache / enfonce.

Les deux atlas (`Keyboard Letters and Symbols.png`, `Keyboard Extras.png`)
sont decoupees une fois, mises a l'echelle en nearest-neighbor, puis cachees.
La rangee du bas de chaque feuille est l'etat enfonce (glyphes bleus).
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

import arcade
from arcade.types import XYWH
from PIL import Image

import settings
from src.ui.fonts import PIXEL_FONT
from src.ui.pad import get_pad

_CELL = settings.UI_KEY_CELL
_LETTERS_PRESSED_ROW = 7
_EXTRAS_PRESSED_ROW = 4

# (colonne, ligne) dans la feuille lettres, etat relache.
_LETTERS: dict[str, tuple[int, int]] = {
    "up": (0, 0),
    "down": (1, 0),
    "left": (2, 0),
    "right": (3, 0),
    "f1": (4, 0),
    "f2": (5, 0),
    "f3": (6, 0),
    "f4": (7, 0),
    "f5": (0, 1),
    "f6": (1, 1),
    "f7": (2, 1),
    "f8": (3, 1),
    "f9": (4, 1),
    "f10": (5, 1),
    "f11": (6, 1),
    "f12": (7, 1),
    "a": (0, 2),
    "b": (1, 2),
    "c": (2, 2),
    "d": (3, 2),
    "e": (4, 2),
    "f": (5, 2),
    "g": (6, 2),
    "h": (7, 2),
    "i": (0, 3),
    "j": (1, 3),
    "k": (2, 3),
    "l": (3, 3),
    "m": (4, 3),
    "n": (5, 3),
    "o": (6, 3),
    "p": (7, 3),
    "q": (0, 4),
    "r": (1, 4),
    "s": (2, 4),
    "t": (3, 4),
    "u": (4, 4),
    "v": (5, 4),
    "w": (6, 4),
    "x": (7, 4),
    "y": (0, 5),
    "z": (1, 5),
}

# (index 0-3 dans la rangee, ligne) : chaque extra fait 2 cellules de large.
_EXTRAS: dict[str, tuple[int, int]] = {
    "tab": (0, 0),
    "esc": (1, 0),
    "print": (2, 0),
    "back": (3, 0),
    "shift": (0, 1),
    "pgup": (1, 1),
    "pgdn": (2, 1),
    "enter": (3, 1),
    "ctrl": (0, 2),
    "alt": (1, 2),
    "space": (2, 2),
    "ins": (3, 2),
    "del": (0, 3),
    "end": (1, 3),
    "home": (2, 3),
    "pause": (3, 3),
}

_ARCADE_GROUPS: dict[str, frozenset[int]] = {}

_SHEETS: dict[str, Image.Image] = {}
_TEXTURES: dict[tuple[str, bool, int], arcade.Texture] = {}
_PAD_FACE: dict[str, tuple[str, tuple[int, int, int]]] = {
    "btn_b": ("B", settings.COLOR_PAD_B),
    "btn_a": ("A", settings.COLOR_PAD_A),
    "btn_y": ("Y", settings.COLOR_PAD_Y),
    "btn_x": ("X", settings.COLOR_PAD_X),
}
_PAD_ACTIONS: dict[str, str] = {
    "btn_b": "jump",
    "btn_a": "attack",
    "btn_y": "dash",
    "btn_x": "project",
    "btn_minus": "back",
    "btn_plus": "start",
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
    "stick": "stick",
}
_PAD_GLYPHS = frozenset(_PAD_FACE) | {"btn_minus", "btn_plus", "stick"}
_PAD_LETTERS: dict[tuple[str, float, tuple[int, int, int]], arcade.Text] = {}
_LABELS: dict[tuple, arcade.Text] = {}


def _arcade_groups() -> dict[str, frozenset[int]]:
    if _ARCADE_GROUPS:
        return _ARCADE_GROUPS
    _ARCADE_GROUPS.update(
        {
            "left": frozenset({arcade.key.LEFT, arcade.key.Q}),
            "right": frozenset({arcade.key.RIGHT, arcade.key.D}),
            "up": frozenset({arcade.key.UP, arcade.key.W, arcade.key.Z}),
            "down": frozenset({arcade.key.DOWN, arcade.key.S}),
            "q": frozenset({arcade.key.Q, arcade.key.LEFT}),
            "z": frozenset({arcade.key.Z, arcade.key.W, arcade.key.UP}),
            "s": frozenset({arcade.key.S, arcade.key.DOWN}),
            "d": frozenset({arcade.key.D, arcade.key.RIGHT}),
            "a": frozenset({arcade.key.A}),
            "e": frozenset({arcade.key.E}),
            "space": frozenset({arcade.key.SPACE}),
            "shift": frozenset({arcade.key.LSHIFT, arcade.key.RSHIFT}),
            "f": frozenset({arcade.key.F}),
            "r": frozenset({arcade.key.R}),
            "t": frozenset({arcade.key.T}),
            "tab": frozenset({arcade.key.TAB}),
            "enter": frozenset(
                {
                    arcade.key.ENTER,
                    arcade.key.RETURN,
                    getattr(arcade.key, "NUM_ENTER", arcade.key.ENTER),
                }
            ),
            "esc": frozenset({arcade.key.ESCAPE}),
            "f11": frozenset({arcade.key.F11}),
        }
    )
    for index in range(1, 10):
        _ARCADE_GROUPS[str(index)] = frozenset({getattr(arcade.key, f"KEY_{index}")})
    return _ARCADE_GROUPS


def is_pressed(name: str, held: Collection[int]) -> bool:
    """True si une touche physique correspondant a `name` est enfoncee."""
    if get_pad().using_pad:
        action = _PAD_ACTIONS.get(name)
        if action == "stick":
            pad = get_pad()
            return bool(pad.axis_x or pad.axis_y or pad.held & {"left", "right", "up", "down"})
        if action:
            if action == "attack":
                return bool(get_pad().held & {"attack", "confirm"})
            return action in get_pad().held
    group = _arcade_groups().get(name)
    if not group or not held:
        return False
    return not group.isdisjoint(held)


def key_size(name: str, height: int = settings.UI_KEY_ICON_HEIGHT) -> tuple[float, float]:
    """Largeur et hauteur a l'ecran de l'icone `name`."""
    scale = height / _CELL
    if name in _PAD_GLYPHS:
        if name in ("btn_minus", "btn_plus"):
            return height * 0.85, height * 0.55
        return float(height), float(height)
    if name in _EXTRAS:
        return _CELL * 2 * scale, height
    return _CELL * scale, height


def draw_key(
    name: str,
    center_x: float,
    center_y: float,
    *,
    pressed: bool = False,
    height: int = settings.UI_KEY_ICON_HEIGHT,
) -> tuple[float, float]:
    """Dessine une touche. Retourne (largeur, hauteur) dessinees."""
    if name in _PAD_GLYPHS:
        return _draw_pad_glyph(name, center_x, center_y, pressed=pressed, height=height)
    texture = _texture(name, pressed, height)
    width, size_h = key_size(name, height)
    arcade.draw_texture_rect(
        texture,
        XYWH(center_x, center_y, width, size_h),
        pixelated=True,
    )
    return width, size_h


def draw_prompt(
    center_x: float,
    center_y: float,
    names: Sequence[str],
    label: str,
    held: Collection[int],
    *,
    height: int = settings.UI_KEY_ICON_HEIGHT,
    caption_size: float | None = None,
    caption_color: tuple[int, int, int] = settings.COLOR_MENU_HINT,
) -> float:
    """Rangee d'icones + libelle, centree sur (`center_x`, `center_y`). Retourne la largeur."""
    size = caption_size if caption_size is not None else settings.UI_KEY_CAPTION_SIZE
    widths = [key_size(name, height)[0] for name in names]
    caption = _caption(label, size, caption_color) if label else None
    total = _prompt_width(names, caption, height)
    cursor = center_x - total / 2
    gap = 4
    for name, width in zip(names, widths, strict=True):
        draw_key(
            name,
            cursor + width / 2,
            center_y,
            pressed=is_pressed(name, held),
            height=height,
        )
        cursor += width + gap
    if caption is not None:
        caption.x = cursor + 4
        caption.y = center_y
        caption.draw()
    return total


def draw_prompt_row(
    center_x: float,
    center_y: float,
    groups: Sequence[tuple[Sequence[str], str]],
    held: Collection[int],
    *,
    height: int = settings.UI_KEY_ICON_HEIGHT,
    spacing: float = 26.0,
    caption_size: float | None = None,
    caption_color: tuple[int, int, int] = settings.COLOR_MENU_HINT,
) -> None:
    """Aligne plusieurs prompts (icone(s) + texte) sur une ligne."""
    size = caption_size if caption_size is not None else settings.UI_KEY_CAPTION_SIZE
    widths = [
        _prompt_width(
            names,
            _caption(label, size, caption_color) if label else None,
            height,
        )
        for names, label in groups
    ]
    total = sum(widths) + spacing * max(0, len(groups) - 1)
    cursor = center_x - total / 2
    for (names, label), width in zip(groups, widths, strict=True):
        draw_prompt(
            cursor + width / 2,
            center_y,
            names,
            label,
            held,
            height=height,
            caption_size=size,
            caption_color=caption_color,
        )
        cursor += width + spacing


def _draw_pad_glyph(
    name: str,
    center_x: float,
    center_y: float,
    *,
    pressed: bool,
    height: int,
) -> tuple[float, float]:
    """Boutons Switch (ronds colores) et stick, sans atlas clavier."""
    width, size_h = key_size(name, height)
    if name == "stick":
        radius = size_h * 0.42
        ring = settings.COLOR_PAD_STICK
        arcade.draw_circle_filled(center_x, center_y, radius, (28, 32, 40, 220))
        arcade.draw_circle_outline(center_x, center_y, radius, ring, 2)
        pad = get_pad()
        nub_x = center_x + pad.axis_x * radius * 0.45
        nub_y = center_y + pad.axis_y * radius * 0.45
        nub_color = (255, 255, 255) if pressed else ring
        arcade.draw_circle_filled(nub_x, nub_y, radius * 0.32, nub_color)
        return width, size_h
    if name in ("btn_minus", "btn_plus"):
        left, right = center_x - width / 2, center_x + width / 2
        bottom, top = center_y - size_h / 2, center_y + size_h / 2
        fill = (70, 74, 84) if pressed else (40, 44, 52)
        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, fill)
        arcade.draw_lrbt_rectangle_outline(
            left, right, bottom, top, settings.COLOR_PAD_PLUS, 2
        )
        glyph = "+" if name == "btn_plus" else "-"
        label = _pad_letter(glyph, height * 0.42, settings.COLOR_PAD_PLUS)
        label.x = center_x
        label.y = center_y
        label.draw()
        return width, size_h
    letter, color = _PAD_FACE[name]
    radius = min(width, size_h) * 0.46
    fill = tuple(min(255, channel + 40) for channel in color) if pressed else color
    arcade.draw_circle_filled(center_x, center_y, radius, fill)
    arcade.draw_circle_outline(center_x, center_y, radius, (20, 22, 28), 2)
    ink = (20, 22, 28) if not pressed else (255, 255, 255)
    label = _pad_letter(letter, height * 0.38, ink)
    label.x = center_x
    label.y = center_y + 1
    label.draw()
    return width, size_h


def _pad_letter(
    text: str, size: float, color: tuple[int, int, int]
) -> arcade.Text:
    key = (text, size, color)
    cached = _PAD_LETTERS.get(key)
    if cached is None:
        cached = arcade.Text(
            text,
            0,
            0,
            color,
            font_size=size,
            anchor_x="center",
            anchor_y="center",
            font_name=settings.EDITOR_UI_FONT,
        )
        _PAD_LETTERS[key] = cached
    return cached


def _prompt_width(
    names: Sequence[str],
    caption: arcade.Text | None,
    height: int,
) -> float:
    gap = 4
    widths = [key_size(name, height)[0] for name in names]
    extra = 8 + caption.content_width if caption is not None else 0.0
    return sum(widths) + gap * max(0, len(names) - 1) + extra


def _caption(text: str, size: float, color: tuple[int, int, int]) -> arcade.Text:
    key = (text, size, color)
    cached = _LABELS.get(key)
    if cached is None:
        if len(_LABELS) >= 64:
            _LABELS.clear()
        cached = arcade.Text(
            text,
            0,
            0,
            color,
            font_size=size,
            anchor_x="left",
            anchor_y="center",
            font_name=PIXEL_FONT,
        )
        _LABELS[key] = cached
    return cached


def _texture(name: str, pressed: bool, height: int) -> arcade.Texture:
    cache_key = (name, pressed, height)
    cached = _TEXTURES.get(cache_key)
    if cached is not None:
        return cached
    image = _crop(name, pressed)
    scale = height / image.height
    new_size = (max(1, round(image.width * scale)), height)
    if image.size != new_size:
        image = image.resize(new_size, Image.Resampling.NEAREST)
    texture = arcade.Texture(image, hash=f"key:{name}:{int(pressed)}:{height}")
    _TEXTURES[cache_key] = texture
    return texture


def _crop(name: str, pressed: bool) -> Image.Image:
    if name in _LETTERS:
        column, row = _LETTERS[name]
        if pressed:
            row += _LETTERS_PRESSED_ROW
        sheet = _sheet(settings.UI_KEYBOARD_LETTERS)
        left, top = column * _CELL, row * _CELL
        return sheet.crop((left, top, left + _CELL, top + _CELL)).copy()
    if name in _EXTRAS:
        index, row = _EXTRAS[name]
        if pressed:
            row += _EXTRAS_PRESSED_ROW
        sheet = _sheet(settings.UI_KEYBOARD_EXTRAS)
        left, top = index * _CELL * 2, row * _CELL
        return sheet.crop((left, top, left + _CELL * 2, top + _CELL)).copy()
    raise KeyError(f"icone clavier inconnue : {name}")


def _sheet(filename: str) -> Image.Image:
    cached = _SHEETS.get(filename)
    if cached is not None:
        return cached
    path = settings.UI_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"feuille clavier introuvable : {path}")
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    _SHEETS[filename] = image
    return image


PLAYING_PROMPTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("z", "q", "s", "d"), "bouger"),
    (("space",), "sauter"),
    (("a", "e"), "attaquer"),
    (("shift",), "dash"),
)

ESPRIT_PROMPT: tuple[tuple[str, ...], str] = (("f",), "esprit")

GHOST_PROMPTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("z", "q", "s", "d"), "voler"),
    (("r",), "retour"),
)

PAD_PLAYING_PROMPTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("stick",), "bouger"),
    (("btn_b",), "sauter"),
    (("btn_a",), "attaquer"),
    (("btn_y",), "dash"),
)

PAD_ESPRIT_PROMPT: tuple[tuple[str, ...], str] = (("btn_x",), "esprit")

PAD_GHOST_PROMPTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("stick",), "voler"),
    (("btn_minus",), "retour"),
)

TITLE_PROMPTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("z", "q", "s", "d"), "bouger"),
    (("space",), "sauter"),
    (("shift",), "dash"),
)

PAD_TITLE_PROMPTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("stick",), "bouger"),
    (("btn_b",), "sauter"),
    (("btn_y",), "dash"),
)


def playing_prompts(*, show_esprit: bool) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Commandes du corps : F / X n'apparait qu'apres la premiere projection."""
    if get_pad().using_pad:
        if not show_esprit:
            return PAD_PLAYING_PROMPTS
        return PAD_PLAYING_PROMPTS + (PAD_ESPRIT_PROMPT,)
    if not show_esprit:
        return PLAYING_PROMPTS
    return PLAYING_PROMPTS + (ESPRIT_PROMPT,)


def ghost_prompts() -> tuple[tuple[tuple[str, ...], str], ...]:
    if get_pad().using_pad:
        return PAD_GHOST_PROMPTS
    return GHOST_PROMPTS


def title_prompts() -> tuple[tuple[tuple[str, ...], str], ...]:
    if get_pad().using_pad:
        return PAD_TITLE_PROMPTS
    return TITLE_PROMPTS


def confirm_prompt() -> tuple[str, ...]:
    """B / saut valident aussi les menus (`jump` ou `confirm`)."""
    return ("btn_b",) if get_pad().using_pad else ("enter",)


def back_prompt() -> tuple[str, ...]:
    return ("btn_minus",) if get_pad().using_pad else ("esc",)


def spectral_prompt() -> tuple[tuple[str, ...], str]:
    if get_pad().using_pad:
        return (("btn_x",), settings.SPECTRAL_BUTTON_PROMPT_PAD)
    return (("f",), settings.SPECTRAL_BUTTON_PROMPT)
