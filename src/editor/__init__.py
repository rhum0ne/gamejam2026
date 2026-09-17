"""Editeur de niveaux : cartes JSON de `assets/maps/` editees a la souris.

Point d'entree : `tools/level_editor.py` (ou `./play.sh --edit`).

Decoupage du paquet :

    palette.py   catalogue des elements placables (tuiles, gameplay, decor)
    icons.py     vignettes / textures de cellules, generees et mises en cache
    history.py   pile d'annulation (Ctrl+Z / Ctrl+Shift+Z)
    document.py  modele d'une carte en cours d'edition + lecture/ecriture JSON
    selection.py rectangle de selection et bloc de presse-papiers
    canvas.py      camera et rendu de la grille
    panel.py       panneau lateral : onglets, grille, plaques
    overlay.py     barre d'etat, aide, saisie de texte
    activators.py  plaques, boutons spectraux, actions par lien
    edit_view.py vue d'edition : entrees clavier / souris, outils
    browser.py   liste des cartes : creer, dupliquer, renommer, supprimer
    playtest.py  essai du niveau en cours, avec retour a l'editeur
"""
