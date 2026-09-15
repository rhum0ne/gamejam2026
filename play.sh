#!/bin/sh
# Lanceur macOS / Linux : trouve un Python utilisable et delegue a play.py,
# qui se charge de creer .venv et d'installer les dependances si besoin.
# Aucun "source .venv/bin/activate" n'est necessaire.

cd "$(dirname "$0")" || exit 1

# Un environnement deja pret est toujours prioritaire.
if [ -x ".venv/bin/python" ]; then
    exec ".venv/bin/python" play.py "$@"
fi

for candidate in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" > /dev/null 2>&1; then
        exec "$candidate" play.py "$@"
    fi
done

echo "Aucun Python trouve sur cette machine."
echo "Installe Python 3.10 ou plus recent : https://www.python.org/downloads/"
exit 1
