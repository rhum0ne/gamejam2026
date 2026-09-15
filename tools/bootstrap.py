"""Preparation automatique de l'environnement Python.

Objectif : que le jeu se lance quel que soit l'etat de la machine, sans avoir a
activer quoi que ce soit a la main. Le module repond a trois questions :

1. l'interpreteur courant a-t-il deja Arcade ? -> on joue directement ;
2. sinon, `.venv/` existe-t-il avec Arcade dedans ? -> on relance le jeu avec
   ce Python-la ;
3. sinon, on cree `.venv/` et on installe `requirements.txt`, puis on relance.

Contrainte importante : ce fichier doit fonctionner avec un Python nu, avant
toute installation. Il n'utilise donc **que** la bibliotheque standard, et
aucun import du projet.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"

MIN_PYTHON = (3, 10)
# Empeche une boucle de relances si l'installation echoue sans le dire.
GUARD_ENV = "ASTRAL_BOOTSTRAP_DONE"


class BootstrapError(RuntimeError):
    """L'environnement n'a pas pu etre prepare : le message explique quoi faire."""


# --------------------------------------------------------------------------- #
# Inspection
# --------------------------------------------------------------------------- #


def venv_python(venv: Path = VENV_DIR) -> Path:
    """Chemin de l'interpreteur d'un environnement virtuel, selon l'OS."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _current_has_arcade() -> bool:
    try:
        return importlib.util.find_spec("arcade") is not None
    except (ImportError, ValueError):
        return False


def _has_arcade(python: Path) -> bool:
    if not python.exists():
        return False
    return _run([str(python), "-c", "import arcade"]) == 0


def _version_of(python: str) -> tuple[int, int]:
    """Version majeure/mineure d'un interpreteur, (0, 0) s'il est inutilisable."""
    try:
        completed = subprocess.run(
            [python, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return (0, 0)
    if completed.returncode != 0:
        return (0, 0)
    try:
        major, minor = completed.stdout.split()
        return (int(major), int(minor))
    except ValueError:
        return (0, 0)


def _find_base_python() -> str:
    """Trouve un interpreteur assez recent pour creer l'environnement virtuel."""
    if sys.version_info[:2] >= MIN_PYTHON:
        return sys.executable
    for name in ("python3.13", "python3.12", "python3.11", "python3.10", "python3", "python"):
        path = shutil.which(name)
        if path and _version_of(path) >= MIN_PYTHON:
            return path
    required = ".".join(str(part) for part in MIN_PYTHON)
    raise BootstrapError(
        f"Python {required} ou plus recent est introuvable sur cette machine "
        f"(l'interpreteur courant est {sys.version.split()[0]}).\n"
        "Installe-le depuis https://www.python.org/downloads/ puis relance ./play.sh"
    )


# --------------------------------------------------------------------------- #
# Installation
# --------------------------------------------------------------------------- #


def _run(command: list[str]) -> int:
    try:
        return subprocess.call(command, cwd=ROOT)
    except OSError as error:
        raise BootstrapError(f"impossible d'executer {command[0]} : {error}") from error


def _say(message: str) -> None:
    """Affiche une etape d'installation immediatement (sans attendre le buffer)."""
    print(f"[setup] {message}", flush=True)


def _create_venv(verbose: bool) -> None:
    base_python = _find_base_python()
    if verbose:
        _say(f"creation de l'environnement virtuel .venv (avec {base_python})")
    if _run([base_python, "-m", "venv", str(VENV_DIR)]) != 0:
        shutil.rmtree(VENV_DIR, ignore_errors=True)
        raise BootstrapError(
            "la creation de .venv a echoue.\n"
            f"Essaie a la main : {base_python} -m venv .venv"
        )


def _install_requirements(python: Path, verbose: bool) -> None:
    if not REQUIREMENTS.exists():
        raise BootstrapError(f"fichier introuvable : {REQUIREMENTS}")
    if verbose:
        _say("installation des dependances (arcade) - cela peut prendre une minute")
    _run([str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    if _run([str(python), "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS)]) != 0:
        raise BootstrapError(
            "l'installation des dependances a echoue (connexion internet ?).\n"
            f"Essaie a la main : {python} -m pip install -r requirements.txt"
        )


# --------------------------------------------------------------------------- #
# API publique
# --------------------------------------------------------------------------- #


def ensure_environment(verbose: bool = True) -> str:
    """Retourne le chemin d'un interpreteur pret a lancer le jeu.

    Installe ce qui manque si necessaire. Leve `BootstrapError` avec un message
    actionnable si l'environnement ne peut pas etre prepare.
    """
    if _current_has_arcade():
        return sys.executable

    python = venv_python()
    if _has_arcade(python):
        if verbose:
            _say(f"utilisation de l'environnement existant : {python}")
        return str(python)

    if os.environ.get(GUARD_ENV):
        raise BootstrapError(
            "Arcade reste introuvable apres installation.\n"
            f"Verifie l'environnement : {python} -m pip install -r requirements.txt"
        )

    if not python.exists():
        _create_venv(verbose)
    _install_requirements(python, verbose)

    if not _has_arcade(python):
        raise BootstrapError(
            "Arcade n'est pas importable malgre une installation reussie.\n"
            "Supprime .venv et relance ./play.sh"
        )
    if verbose:
        _say("environnement pret")
    return str(python)


def run_script(python: str, script: Path, argv: list[str] | None = None) -> int:
    """Lance un script du projet avec l'interpreteur donne et retourne son code de sortie."""
    environment = {**os.environ, GUARD_ENV: "1"}
    command = [python, str(script), *(argv or [])]
    try:
        return subprocess.call(command, cwd=ROOT, env=environment)
    except OSError as error:
        raise BootstrapError(f"impossible de lancer {script.name} : {error}") from error
    except KeyboardInterrupt:
        return 130


def bootstrap_and_relaunch(script: str | Path, argv: list[str] | None = None) -> int:
    """Prepare l'environnement puis relance `script` avec le bon interpreteur.

    Utilise par `main.py` quand Arcade manque : `python main.py` finit donc par
    fonctionner meme avec un interpreteur qui n'a pas les dependances.
    """
    try:
        python = ensure_environment()
    except BootstrapError as error:
        print(f"\n[erreur] {error}\n", file=sys.stderr)
        return 1
    return run_script(python, Path(script).resolve(), argv)
