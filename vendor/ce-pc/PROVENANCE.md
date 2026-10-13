# Ce PC : origine et adaptations

Projet d’origine : https://github.com/yannmasoch/nautilus-my-computer

Version incluse : 0.13.2, récupérée depuis l’installation locale du toolkit.
Licence MIT d’origine conservée dans `LICENSE`. Les traductions proviennent du dépôt d’origine au commit `4c6247e8210239ecc8de66fd7a9c793dc9a7e66f`.

Adaptations dans cette distribution :

- `main.py` : nom « Ce PC » dans la barre latérale.
- `my_computer_view.py` : nom d’affichage « Ubuntu » pour le système racine.
- `my_computer_view.py` : système racine placé en premier dans sa section.
- `my_computer_view.py` : mode `icon-view` propre à Ce PC, sans modifier la préférence globale de vue des dossiers.
- L’installateur configure des jauges bleues et masque les partitions boot/EFI par défaut.

Le code original dépend des structures internes de Nautilus. Les mises à jour de GNOME peuvent nécessiter une adaptation. Installation testée initialement sur Ubuntu 26.04 / Nautilus 50.2.2.
