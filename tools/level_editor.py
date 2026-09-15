"""Point d'entree de l'editeur de niveaux.

Usage :
    python tools/level_editor.py
    python tools/level_editor.py level_1_tuto.json
    ./play.sh --edit
    ./play.sh --edit level_1_tuto.json

Si Arcade manque, le fichier se relance tout seul via `tools/bootstrap.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import arcade
except ModuleNotFoundError:
    from tools.bootstrap import bootstrap_and_relaunch

    raise SystemExit(bootstrap_and_relaunch(__file__, sys.argv[1:]))

import settings  # noqa: E402
from src.editor.browser import BrowserView  # noqa: E402
from src.editor.document import DocumentError, EditorDocument  # noqa: E402
from src.editor.edit_view import EditView  # noqa: E402
import src.ui.fonts  # noqa: E402  # charge la police pixel avant le premier Text


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=settings.EDITOR_TITLE)
    parser.add_argument(
        "map",
        nargs="?",
        default="",
        help="carte JSON a ouvrir (dans assets/maps/, ou chemin)",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="demarre en plein ecran (F11 pour basculer ensuite)",
    )
    return parser.parse_args(argv)


def create_window(*, fullscreen: bool = False) -> arcade.Window:
    window = arcade.Window(
        width=settings.EDITOR_WINDOW_WIDTH,
        height=settings.EDITOR_WINDOW_HEIGHT,
        title=settings.EDITOR_TITLE,
        fullscreen=fullscreen,
        resizable=True,
        update_rate=settings.FRAME_TIME,
        draw_rate=settings.FRAME_TIME,
        vsync=True,
        center_window=not fullscreen,
    )
    window.set_minimum_size(settings.SCREEN_MIN_WIDTH, settings.SCREEN_MIN_HEIGHT)
    return window


def opening_view(map_name: str) -> arcade.View:
    """Navigateur, ou directement l'edition si une carte est passee en argument."""
    if not map_name:
        return BrowserView()
    try:
        document = EditorDocument.from_file(map_name)
    except DocumentError as error:
        raise SystemExit(f"impossible d'ouvrir {map_name} : {error}") from error
    return EditView(document)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    window = create_window(fullscreen=args.fullscreen)
    window.show_view(opening_view(args.map))
    arcade.run()


if __name__ == "__main__":
    main()
