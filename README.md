# Ubuntu Desktop Toolkit

Petits outils graphiques pour rendre le quotidien sous Ubuntu plus pratique.

Version expérimentale pour Ubuntu avec GNOME/Fichiers (Nautilus), Python 3 et GTK 4. Interface en français. Le développement initial a été effectué sur Ubuntu 26.04 ; la compatibilité avec d’autres versions reste à vérifier.

## Installer

Télécharge et décompresse le dépôt, puis exécute :

```sh
python3 install.py --dependencies
```

L’installation des dépendances demande une authentification Ubuntu. Les outils eux-mêmes sont installés pour ton compte, sans lancement permanent en administrateur. La compression RAR et le support d’extensions Nautilus sont installés avec les autres dépendances. Après installation, déconnecte puis reconnecte ta session pour charger la vue Ce PC dans Fichiers.

## Toutes les fonctions incluses

| Fonction | Accès |
| --- | --- |
| Ce PC, jauges bleues et disque Ubuntu en premier | Barre latérale de Fichiers |
| Ce PC toujours en grille, indépendamment des dossiers | Automatique |
| Moniteur système | Ctrl + Maj + Échap |
| Documents texte, Markdown, Python et Bash | Clic droit → Nouveau document |
| Choix des applications au démarrage | Menu → Applications au démarrage |
| Création d’un lanceur avec nom et icône | Sélectionner un programme → clic droit → Scripts → Créer une application… |
| Raccourcis, copie du chemin, envoi vers un dossier, RAR, rangement de la sélection | Clic droit → Scripts |
| Renommage multiple | Sélectionner plusieurs fichiers puis F2 (fonction native) |
| Nettoyeur et désinstalleur | Menu des applications et raccourcis bureau |

Les modèles existants et les préférences d’affichage de tes dossiers sont conservés. Les fichiers remplacés sont sauvegardés. Si le dossier Bureau ou Modèles est désactivé dans ta configuration XDG, l’installateur n’écrit pas ces éléments dans ton dossier personnel à sa place.

## Désinstaller des applications

Recherche « Désinstaller des applications » dans le menu.

- Liste les applications visibles du menu installées via APT, Snap et Flatpak.
- Recherche par nom ou identifiant.
- Pour APT : simulation de la suppression, affichage des paquets retirés, puis nouvelle vérification après authentification.
- Bloque les composants essentiels, les paquets importants et les noyaux identifiés.
- N’exécute ni `autoremove`, ni purge des réglages, ni suppression des données Flatpak.
- Pour les AppImage identifiées par leur lanceur et situées dans le dossier personnel : place le fichier et son lanceur dans la corbeille après affichage de leur chemin.
- Pour les autres lanceurs locaux : retire uniquement l’entrée du menu dans la corbeille. Le fichier exécutable reste en place.

Ce n’est pas un inventaire de tous les paquets : bibliothèques, outils sans entrée de menu et installations manuelles peuvent ne pas apparaître. Les noms affichés reflètent les fichiers `.desktop`, pas une reconnaissance universelle des installateurs. Vérifie les suppressions proposées, en particulier les dépendances APT.

## Nettoyer les caches

Recherche « Nettoyer les caches » dans le menu. Aucune suppression avant sélection et confirmation.

Catégories : miniatures, Chrome, Blender, OptiX, Redshift (cache local standard), shaders NVIDIA/Mesa, téléchargements pip/Winetricks, paquets Ubuntu et cache RAM des fichiers.

Les chemins sont une liste explicite ; pas d’analyse ou d’effacement des projets. Les caches d’un logiciel détecté comme ouvert sont bloqués. La détection des processus est indicative : ferme les logiciels de rendu avant nettoyage. Les emplacements personnalisés de Redshift/OptiX ne sont pas suivis automatiquement. Les caches sont recréés et les prochains lancements/rendus peuvent être plus lents.

L’option RAM utilise `sync`, puis `vm.drop_caches=1` après authentification. Elle ne libère pas la mémoire privée de Maya, Blender ou des autres applications. Linux récupère déjà automatiquement ce cache quand il a besoin de mémoire ; ce bouton n’est pas un accélérateur à utiliser régulièrement.

## Actions de Fichiers

Dans clic droit → Scripts : nouveau dossier avec la sélection, copie du chemin, envoi d’une copie vers un dossier, raccourci bureau, compression RAR et création d’une application. Les fichiers existants ne sont pas volontairement écrasés par les actions de copie.

## Vue « Ce PC »

La vue avec jauges est incluse et installée automatiquement. Elle est basée sur [My Computer for Nautilus](https://github.com/yannmasoch/nautilus-my-computer), sous licence MIT, conservée dans `vendor/ce-pc/LICENSE`.

Les adaptations sont incluses : nom Ce PC, système racine nommé Ubuntu, affichage du système en premier, jauges bleues et grille fixe. Aucun changement de la préférence globale de vue des dossiers. La version incluse est 0.13.2 ; son origine et les changements sont décrits dans `vendor/ce-pc/PROVENANCE.md`.

L’extension utilise les structures internes de Nautilus et peut nécessiter une mise à jour après une mise à jour de GNOME. La configuration de référence est Ubuntu 26.04 / Nautilus 50.2.2 ; les versions plus anciennes ne sont pas garanties.

## Retirer le toolkit

```sh
python3 install.py --uninstall
```

Seuls les fichiers installés et non modifiés sont retirés ; les versions antérieures sauvegardées sont restaurées. Les réglages modifiés par l’installateur sont restaurés lorsqu’ils n’ont pas été changés depuis. Les dépendances système restent installées. Reconnecte ta session après désinstallation pour recharger Fichiers.

## Tests

```sh
/usr/bin/python3 -m unittest discover -s tests -v
```

Les tests utilisent des simulations et des dossiers temporaires. Ils ne désinstallent aucun logiciel et ne vident aucun cache réel.

## Licence

MIT pour le code du toolkit. La licence et les crédits de l’extension Ce PC sont conservés dans `vendor/ce-pc`. Les icônes des lanceurs proviennent du thème installé ; les ressources et traductions de l’extension restent couvertes par sa licence d’origine.
