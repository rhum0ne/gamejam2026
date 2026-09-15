"""Police pixel du jeu, chargee une seule fois quel que soit le point d'entree.

`arcade.load_font` doit etre appele avant la creation du premier `arcade.Text`
qui la reference. Comme plusieurs points d'entree creent des `arcade.Window`
(`main.py`, `tools/smoke_test.py`), le chargement se fait ici, au moment de
l'import, plutot que dans un seul de ces points d'entree.
"""

from __future__ import annotations

import arcade

import settings

arcade.load_font(str(settings.FONT_FILE))

PIXEL_FONT = settings.FONT_PIXEL
