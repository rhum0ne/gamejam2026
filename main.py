"""Point d'entree de Project Astral Platformer.

Usage :
    python main.py               # demarre sur l'ecran titre
    python main.py --play        # saute le menu et lance directement le niveau
    python main.py --level 0     # choisit le niveau de depart (index dans LEVEL_SEQUENCE)
    python main.py --fullscreen  # demarre en plein ecran

Si Arcade manque dans l'interpreteur utilise, ce fichier prepare
l'environnement et se relance tout seul (voir `tools/bootstrap.py`) : aucune
activation manuelle de `.venv` n'est necessaire.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Sous WSL/WSLg, ALSA n'a pas de vraie carte son et openal-soft spamme la
# console d'erreurs "ALSA lib ... cannot find card '0'" au demarrage. Un
# serveur PulseAudio est fourni par WSLg (PULSE_SERVER) : on le priorise pour
# eviter la sonde ALSA foireuse. Ne s'applique pas quand le systeme n'expose
# pas PULSE_SERVER (Linux "nature", macOS), pour ne rien changer ailleurs.
if os.environ.get("PULSE_SERVER") and not os.environ.get("ALSOFT_DRIVERS"):
    os.environ["ALSOFT_DRIVERS"] = "pulse"

try:
    import arcade
except ModuleNotFoundError:
    from tools.bootstrap import bootstrap_and_relaunch

    raise SystemExit(bootstrap_and_relaunch(__file__, sys.argv[1:]))

import settings  # noqa: E402
from src.systems.game_state import GameSession, PlayView  # noqa: E402
from src.ui.display import center_on_primary_screen  # noqa: E402
from src.ui.menus import TitleView  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=settings.SCREEN_TITLE)
    parser.add_argument(
        "--play",
        action="store_true",
        help="demarre directement la partie sans passer par l'ecran titre",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=0,
        help="index du niveau de depart dans settings.LEVEL_SEQUENCE",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="demarre en plein ecran (F11 pour basculer ensuite)",
    )
    return parser.parse_args(argv)


def create_window(*, fullscreen: bool = False) -> arcade.Window:
    """Cree la fenetre de jeu, redimensionnable, cadencee a 60 FPS avec vsync."""
    window = arcade.Window(
        width=settings.SCREEN_WIDTH,
        height=settings.SCREEN_HEIGHT,
        title=settings.SCREEN_TITLE,
        fullscreen=fullscreen,
        resizable=True,
        update_rate=settings.FRAME_TIME,
        draw_rate=settings.FRAME_TIME,
        vsync=True,
        center_window=False,
    )
    window.set_minimum_size(settings.SCREEN_MIN_WIDTH, settings.SCREEN_MIN_HEIGHT)
    if not fullscreen:
        center_on_primary_screen(window)
    arcade.enable_timings()
    return window


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not 0 <= args.level < len(settings.LEVEL_SEQUENCE):
        raise SystemExit(
            f"--level doit etre entre 0 et {len(settings.LEVEL_SEQUENCE) - 1} "
            f"(niveaux disponibles : {', '.join(settings.LEVEL_SEQUENCE)})"
        )

    session = GameSession(level_index=args.level)
    window = create_window(fullscreen=args.fullscreen)
    window.show_view(PlayView(session) if args.play else TitleView(session))
    arcade.run()


if __name__ == "__main__":
    main()
