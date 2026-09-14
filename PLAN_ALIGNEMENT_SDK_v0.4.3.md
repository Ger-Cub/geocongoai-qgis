# Plan d'alignement du plugin QGIS GeoCongo AI sur le SDK GeoCongo AI v0.4.3

Ce document présente le plan d'action détaillé pour refondre et aligner le plugin QGIS **GeoCongo AI** sur les fonctionnalités et l'architecture du nouveau SDK Python **GeoCongo AI (v0.4.3)**.

---

## 1. Objectifs de la mise à niveau

1. **Intégration de l'Orchestrateur Agentique `Mtumishi`** :
   - Le panneau latéral QGIS s'ouvrira par défaut sur l'onglet/vue principale **« Mtumishi »**, agissant comme un chatbot agentique complet et interactif connecté au moteur Mtumishi du SDK v0.4.3.
   - Assistant intelligent capable de comprendre le contexte géospatial actif dans QGIS (BBOX, CRS, couches chargées, province cible, métadonnées).

2. **Refonte des onglets et actions du Panneau Latéral** :
   - **Mtumishi** : Chatbot agentique et assistant conversationnel d'exploration.
   - **Pekua** : Informations et accès rapide au moteur de recherche documentaire et géoscientifique.
   - **Gundua** : Informations et accès rapide au moteur d'analyse Greenfield et télédétection.
   - **Chimbua** : Informations et accès rapide au moteur de calcul de forages, géochimie et modélisation 3D.

3. **Boîtes de dialogue dédiées pour chaque moteur** :
   - Chaque onglet du panneau latéral disposera d'un bouton dédié pour déclencher sa boîte de dialogue interactive respective :
     - **Analyse Greenfield (Gundua Engine)** (`GunduaEngineDialog`)
     - **Recherche Documentaire (Pekua Engine)** (*Nouvelle boîte de dialogue à créer*)
     - **Forages & Géochimie 3D (Chimbua Engine)** (`DrillholeAnalysisDialog`)
     - *Autres actions existantes* (Paramètres, À propos) restant accessibles depuis le menu principal QGIS `&GeoCongo AI`.

---

## 2. Architecture des modifications dans le projet QGIS

### A. Mise à jour de la classe principale [`GeoCongoAI`](file:///home/gerard/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geocongoai_qgis/geocongoai_qgis.py#L21-L150) (`geocongoai_qgis.py`)
- Mettre à jour les menus et actions du plugin pour inclure l'action **Recherche Documentaire (Pekua Engine)**.
- Conserver l'initialisation du Panneau Latéral ouvrant directement **Mtumishi** en premier plan.

### B. Refonte du Panneau Latéral [`GeoCongoAIDockWidget`](file:///home/gerard/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geocongoai_qgis/gui/main_dock.py#L22-L135) (`gui/main_dock.py`)
- Remplacer l'organisation actuelle par 4 onglets principaux :
  1. **Tab 1 : `🤖 Mtumishi`** (Chatbot agentique / assistant conversationnel interactif).
  2. **Tab 2 : `🔍 Pekua Engine`** (Présentation de la base de connaissances géologiques et bouton d'ouverture de la boîte de dialogue de recherche documentaire).
  3. **Tab 3 : `🛰️ Gundua Engine`** (Présentation de l'analyse Greenfield et bouton d'ouverture de la boîte de dialogue Gundua).
  4. **Tab 4 : `⛏️ Chimbua Engine`** (Présentation des forages et modélisation 3D et bouton d'ouverture de la boîte de dialogue Chimbua).

### C. Création des nouvelles interfaces (Dialogues)
- Créer [`gui/pekua_dialog.py`](file:///home/gerard/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geocongoai_qgis/gui/pekua_dialog.py) pour la boîte de dialogue de recherche documentaire Pekua.
- Mettre à jour `gui/main_dock.py` pour connecter les boutons d'ouverture de dialogue de chaque moteur (Pekua, Gundua, Chimbua).

---

## 3. Étapes d'exécution du plan

| Étape | Composant | Description | Fichiers impactés |
| :--- | :--- | :--- | :--- |
| **1** | Métadonnées & SDK | Mettre à jour la version affichée vers `v0.4.3` dans [`geocongoai_qgis.py`](file:///home/gerard/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geocongoai_qgis/geocongoai_qgis.py) et [`metadata.txt`](file:///home/gerard/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geocongoai_qgis/metadata.txt). | `geocongoai_qgis.py`, `metadata.txt` |
| **2** | Boîte de dialogue Pekua | Créer le module de recherche documentaire Pekua Engine. | `gui/pekua_dialog.py` (Nouveau) |
| **3** | Refonte du Dock | Restructurer le panneau latéral avec les onglets Mtumishi, Pekua, Gundua et Chimbua. | `gui/main_dock.py` |
| **4** | Actions & Menus | Ajouter l'action de recherche documentaire Pekua au menu QGIS `&GeoCongo AI`. | `geocongoai_qgis.py` |
| **5** | Validation & Tests | Vérifier le chargement du plugin dans QGIS et l'ouverture correcte des différents panneaux et boîtes de dialogue. | Tous les fichiers modifiés |
