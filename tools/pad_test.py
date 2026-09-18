"""Ecran de test manette : voir si Windows et le jeu voient le pad SNES.

Usage :
    python play.py --pad
    python tools/pad_test.py

Appuie sur la croix et les boutons : les indices et les actions doivent bouger.
Echap pour quitter.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import arcade
except ModuleNotFoundError:
    from tools.bootstrap import bootstrap_and_relaunch

    raise SystemExit(bootstrap_and_relaunch(__file__, sys.argv[1:]))

import settings
from src.ui.display import handle_display_key, use_default_camera
from src.ui.labels import Line
from src.ui.pad import get_pad


class PadTestView(arcade.View):
    """Affiche le nom du peripherique, les axes et les boutons enfonces."""

    def __init__(self) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        font = settings.EDITOR_UI_FONT
        self._title = Line(
            22, settings.COLOR_MENU_TITLE, anchor_x="center", font_name=font
        )
        self._hint = Line(
            14, settings.COLOR_MENU_HINT, anchor_x="center", font_name=font
        )
        self._lines = [
            Line(16, settings.COLOR_HUD_TEXT, font_name=font) for _ in range(12)
        ]
        self._log_timer = 0.0

    def on_show_view(self) -> None:
        use_default_camera(self.window)
        get_pad().calm()

    def on_update(self, delta_time: float) -> None:
        pad = get_pad()
        pad.poll(self.window, delta_time)
        self._log_timer += delta_time
        if self._log_timer >= 1.0:
            self._log_timer = 0.0
            print(" | ".join(pad.debug_lines()))

    def on_draw(self) -> None:
        self.clear()
        width, height = self.window.width, self.window.height
        self._title.draw("Test manette", width / 2, height - 48)
        self._hint.draw(
            "Croix et boutons : les numeros doivent changer.  Echap pour quitter.",
            width / 2,
            height - 78,
            max_width=width - 48,
            overflow="clip",
        )
        pad = get_pad()
        rows = [
            "Switch / PowerA : B=saut  A=attaque  Y/ZL=dash  X=fantome  Plus=pause",
            *pad.debug_lines(),
        ]
        top = height - 120
        for index, line in enumerate(self._lines):
            text = rows[index] if index < len(rows) else ""
            line.draw(text, 48, top - index * 28, max_width=width - 96, overflow="clip")

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if handle_display_key(self.window, symbol, modifiers):
            return
        if symbol == arcade.key.ESCAPE:
            self.window.close()


def main() -> int:
    window = arcade.Window(
        width=settings.SCREEN_WIDTH,
        height=settings.SCREEN_HEIGHT,
        title="Test manette",
        fullscreen=False,
        resizable=True,
        update_rate=settings.FRAME_TIME,
        draw_rate=settings.FRAME_TIME,
        vsync=True,
    )
    window.show_view(PadTestView())
    arcade.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
