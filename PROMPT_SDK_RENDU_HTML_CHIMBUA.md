## Prompt de développement SDK GeoCongo AI

Tu es l'agent chargé du développement du SDK `geocongoai`. Ta mission est d'implémenter, côté SDK, un générateur HTML autonome pour les résultats **Chimbua 3D** afin de reproduire fidèlement le rendu actuellement apprécié dans le plugin QGIS GeoCongo AI.

Le résultat attendu est une visualisation HTML interactive, lisible, fluide et directement exploitable par un géologue, un ingénieur minier ou un utilisateur QGIS, sans dépendre du code UI du plugin.

### Objectif principal

Créer dans le SDK une fonction de rendu HTML 3D pour Chimbua qui produit :

- une **scène 3D interactive de forages**,
- une **barre latérale de contrôle** moderne et compacte,
- des **indicateurs de synthèse** visibles en haut,
- une **double logique de coloration** :
  - par **teneur / grade** (`CU`, `AU`, etc.),
  - par **`cluster_id`**,
- un **filtre de clusters**,
- une option pour **masquer les trous non concernés**,
- une capacité de **zoom automatique sur un cluster sélectionné**,
- une option pour **afficher ou masquer les volumes 3D**,
- un rendu sombre, professionnel, propre et stable dans un navigateur moderne.

### Intention UX à reproduire

Le rendu doit donner l'impression d'un outil géoscientifique premium :

- thème sombre élégant,
- lisibilité immédiate,
- focus sur la donnée géologique,
- commandes simples à comprendre,
- interaction rapide même sur plusieurs milliers d'intervalles,
- hiérarchie visuelle nette entre :
  - la scène 3D,
  - les contrôles d'affichage,
  - les statistiques de synthèse,
  - les explications métier.

### Structure visuelle souhaitée

Reproduire une page avec :

1. un **header horizontal sombre**
   - titre du type `GeoCongo AI - Visualisation 3D`
   - badges statistiques à droite :
     - `Intervalles`
     - `Clusters 3D`
     - `Max grade`

2. une **sidebar gauche**
   - bloc `Affichage`
   - bloc `Lecture géologique`
   - bloc `Performance`
   - bloc `Résumé`
   - tous les champs, labels, selects, inputs et boutons doivent rester visuellement contenus dans la sidebar, sans débordement horizontal
   - le fond du panneau latéral doit être **semi-transparent**, avec un rendu discret de type verre sombre ou overlay élégant
   - la transparence doit laisser respirer la scène sans nuire à la lisibilité du contenu
   - éviter un séparateur visuel dur entre la sidebar et la scène 3D si cela alourdit le rendu
   - la zone de scroll doit faire partie intégrante de la largeur du panneau latéral, et non rogner visuellement son contenu

3. une **grande zone centrale 3D**
   - fond sombre
   - grille visible mais discrète
   - axes lisibles
   - navigation Plotly ou équivalent

4. une **légende verticale à droite**
   - si mode teneur : colorbar continue
   - si mode cluster : légende catégorielle ou indication claire du mode actif

### Contrôles obligatoires

Dans la sidebar, prévoir au minimum :

- un select `Coloration des intervalles`
  - `Par teneur`
  - `Par cluster_id`

- un select `Échelle des teneurs`
  - `Robuste`
  - `Complète`
  - `Manuelle`

- deux champs numériques
  - `Min affichage`
  - `Max affichage`

- un bouton `Appliquer la plage`

- un select `Filtrer un cluster`
  - `Tous les clusters`
  - liste des clusters disponibles

- une case à cocher `Masquer les autres trous`
- une case à cocher `Afficher les volumes 3D`
- un bouton `Réinitialiser la vue`

La sidebar doit rester propre et robuste sur différentes largeurs :

- aucun champ ne doit sortir de son conteneur,
- les paires de champs comme `Min affichage` / `Max affichage` doivent pouvoir passer proprement sur une ou deux colonnes selon la largeur disponible,
- les contrôles doivent rester lisibles sur écran portable et dans une fenêtre navigateur réduite,
- la mise en page doit être responsive sans casser l'expérience principale.
- la scrollbar doit rester très discrète et idéalement n'apparaître visuellement qu'au survol du panneau,
- si possible, la scrollbar peut être positionnée à gauche du panneau pour préserver l'alignement du contenu principal,
- le style du scroll doit rester léger, fin et cohérent avec une interface géoscientifique premium.

### Comportement attendu

#### Mode 1 : coloration par teneur

- les points / intervalles sont colorés selon la valeur du champ de teneur
- utiliser une palette continue lisible sur fond sombre
- afficher une colorbar verticale
- les valeurs élevées doivent ressortir immédiatement
- les fortes teneurs doivent culminer visuellement en **rouge**
- éviter une palette où les valeurs maximales resteraient en vert ou en jaune si cela nuit à l'intuition métier
- ne pas laisser quelques valeurs aberrantes ou fausses écraser toute l'échelle de couleurs

#### Gestion des valeurs aberrantes et de la plage d'affichage

Le rendu doit explicitement prendre en compte le fait que, dans des données de forage réelles, quelques teneurs extrêmes ou erronées peuvent aplatir visuellement tout le nuage de points.

Le SDK doit donc intégrer :

- un mode d'échelle **robuste** par défaut, par exemple basé sur les percentiles `P2-P98` ou une logique équivalente,
- un mode d'échelle **complet** basé sur `min-max`,
- un mode d'échelle **manuel** où l'utilisateur peut imposer une plage visuelle, par exemple `0` à `1.3`,
- un comportement de clipping visuel des couleurs sans supprimer les données sources,
- une indication claire dans l'interface sur le fait qu'une plage manuelle ou robuste permet de mieux faire ressortir les zones à potentiel quand une ou deux valeurs extrêmes déforment la palette.

Exemple métier à couvrir :

- si 95 % des teneurs sont comprises entre `0` et `1.3`,
- mais qu'un point erroné vaut `20`,
- la visualisation ne doit pas afficher presque tous les points avec la même couleur.

L'objectif est que les zones à fort potentiel géologique restent visibles et lisibles même en présence de valeurs aberrantes.

#### Mode 2 : coloration par cluster_id

- chaque cluster reçoit une couleur distincte et stable
- les intervalles sans cluster peuvent être grisés ou peu visibles
- la légende ou le panneau doit permettre de comprendre quel cluster est actif

#### Filtre cluster

- quand un cluster est sélectionné :
  - mettre en évidence ses intervalles
  - permettre de masquer les autres trous
  - recentrer automatiquement la caméra sur son emprise si possible

#### Volumes 3D

- les volumes 3D doivent être optionnels
- ils doivent être désactivés par défaut si cela améliore les performances
- lorsqu'activés, ils doivent rester semi-transparents et ne pas masquer totalement les intervalles

### Lecture géologique à préserver

Le HTML ne doit pas être seulement "joli". Il doit aider l'utilisateur à interpréter :

- la continuité spatiale des minéralisations,
- la distribution verticale des teneurs,
- les regroupements DBSCAN,
- la densité de forages,
- les zones potentiellement plus riches.

Prévoir un bloc texte de lecture métier expliquant simplement :

- ce que montre le mode teneur,
- ce que montre le mode cluster,
- pourquoi une échelle robuste est souvent préférable à un simple `min-max`,
- dans quels cas fixer manuellement une plage comme `0 à 1.3`,
- quand utiliser le masquage des autres trous,
- comment interpréter les volumes.

### Contraintes de performance

Le HTML doit rester utilisable sur des jeux de données de plusieurs milliers à dizaines de milliers d'intervalles.

Prévoir explicitement :

- limitation du nombre de traces Plotly si possible,
- regroupement intelligent par trou ou cluster,
- activation différée des volumes 3D,
- réduction des recalculs côté navigateur,
- évitement des boucles JS coûteuses à chaque interaction,
- calcul efficace des percentiles ou bornes robustes sans surcoût excessif,
- CSS et structure HTML robustes pour éviter les débordements de formulaires dans la sidebar,
- effets visuels légers seulement, afin qu'une sidebar transparente ou avec blur ne pénalise pas la fluidité,
- stratégie pour éviter qu'une page locale `.html` devienne non responsive.

Le SDK doit viser la robustesse sur :

- Chrome
- Firefox
- affichage local via fichier HTML

### Données d'entrée attendues

Le générateur HTML côté SDK doit pouvoir consommer une structure normalisée contenant au minimum :

- `intervals`
  - `hole_id`
  - `x`
  - `y`
  - `z`
  - `grade`
  - `cluster_id`
  - éventuellement `from`
  - éventuellement `to`

- `collars`
  - `hole_id`
  - coordonnées de collar

- `cluster_meshes` ou équivalent
  - géométries triangulées ou enveloppes 3D exportables

- `metadata`
  - `grade_field`
  - `cutoff`
  - `eps`
  - `min_samples`
  - nombre d'intervalles
  - nombre de clusters
  - maximum de teneur
  - CRS si disponible

### Exigence importante sur les trajectoires de forage

Le SDK ne doit pas simplifier à l'excès la reconstruction des trajectoires si une table `survey` est disponible.

En particulier :

- une table `survey` peut contenir plusieurs stations de déviation par forage,
- chaque station peut porter une profondeur de mesure du type `AT`, `AT_M`, `DEPTH`, `MD` ou équivalent,
- l'orientation d'un intervalle ne doit pas être dérivée d'une seule ligne arbitraire du forage,
- l'algorithme doit au minimum sélectionner la station de déviation cohérente avec la profondeur de l'intervalle,
- idéalement, il doit interpoler proprement entre stations successives si le pipeline le permet.

Le piège à éviter absolument :

- utiliser une seule valeur `azimuth/dip` par trou,
- ou utiliser la dernière ligne rencontrée dans la table `survey`,
- ce qui peut produire des trajectoires instables ou différentes d'un rendu à l'autre avec pourtant les mêmes tables source.

Le comportement attendu est :

- trajectoires déterministes,
- reproductibles à données identiques,
- cohérentes avec les profondeurs des intervalles,
- et aussi proches que possible d'un workflow de désurveying géologiquement crédible.

### API SDK attendue

Concevoir une API réutilisable du type :

```python
export_chimbua_interactive_html(
    output_html_path,
    intervals,
    collars=None,
    cluster_meshes=None,
    metadata=None,
    default_color_mode="grade",
    default_show_volumes=False,
    auto_open=False,
)
```

Ou une API équivalente, mais :

- purement côté SDK,
- indépendante de QGIS,
- documentée,
- testable.

### Exigences techniques

- produire un HTML autonome ou quasi autonome
- éviter les dépendances front inutiles
- privilégier Plotly si cela reste le meilleur compromis
- générer un JS clair et maintenable
- isoler la logique de préparation des données de la logique d'affichage
- rendre stable la correspondance `cluster_id -> couleur`
- garantir un traitement déterministe des trajectoires `survey` et de leur ordre de lecture
- prévoir un comportement propre si :
  - aucun cluster n'existe,
  - aucun volume 3D n'est disponible,
  - le champ de teneur est absent,
  - le dataset est trop volumineux

### Critères d'acceptation

Le travail sera considéré réussi si :

- le SDK peut générer ce rendu HTML sans passer par le plugin,
- le rendu reproduit l'esthétique sombre et professionnelle observée,
- l'utilisateur peut basculer entre coloration par teneur et par cluster,
- l'utilisateur peut choisir une échelle robuste, complète ou manuelle pour la teneur,
- l'utilisateur peut saisir une plage visuelle personnalisée comme `0 - 1.3`,
- les contrôles de la sidebar restent correctement contenus et lisibles, même sur une largeur réduite,
- le panneau latéral conserve une transparence élégante sans gêner la lecture,
- la scrollbar du panneau reste discrète et ne devient visible qu'au survol ou à l'interaction,
- la largeur utile de la sidebar reste constante, scrollbar comprise,
- les trajectoires de forage restent stables et reproductibles avec les mêmes tables `assay`, `collar` et `survey`,
- l'utilisateur peut filtrer un cluster et isoler les trous associés,
- le zoom sur cluster fonctionne,
- la page reste responsive sur des volumes de données réalistes,
- le code est suffisamment générique pour être réutilisé par :
  - le plugin QGIS,
  - un script Python,
  - une future interface web GeoCongo AI.

### Livrables demandés

Produis :

- le code Python SDK du générateur HTML,
- les helpers de sérialisation des données,
- le template HTML/CSS/JS si séparé,
- la documentation d'usage,
- au moins un exemple exécutable,
- des tests minimaux sur la génération et la structure du rendu.

### Priorité fonctionnelle

Priorité 1 :

- scène 3D stable
- coloration par teneur
- coloration par cluster_id
- filtre cluster
- masquage des autres trous

Priorité 2 :

- volumes 3D activables
- zoom automatique sur cluster
- résumé statistique enrichi

Priorité 3 :

- optimisation poussée pour très gros jeux de données
- variantes de thème ou d'export

### Consigne finale

Ne fais pas une visualisation générique. Reproduis un rendu géoscientifique haut de gamme, sombre, clair, interactif et orienté interprétation, très proche de l'expérience actuelle validée dans le plugin QGIS GeoCongo AI, mais implémenté proprement et nativement dans le SDK `geocongoai`.
