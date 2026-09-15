"""Lanceur zero-configuration de Project Astral Platformer.

A utiliser quand on ne veut rien savoir des environnements virtuels :

    python3 play.py             # installe ce qui manque, puis lance le jeu
    python3 play.py --play      # options transmises a main.py
    python3 play.py --check     # lance le test de demarrage au lieu du jeu

Sur macOS / Linux, `./play.sh` fait la meme chose en trouvant Python tout seul.
Sur Windows, double-clique sur `play.bat`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tools.bootstrap import BootstrapError, ensure_environment, run_script  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    run_tests = "--check" in arguments
    arguments = [argument for argument in arguments if argument != "--check"]

    try:
        python = ensure_environment()
        script = ROOT / "tools" / "smoke_test.py" if run_tests else ROOT / "main.py"
        return run_script(python, script, arguments)
    except BootstrapError as error:
        print(f"\n[erreur] {error}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
