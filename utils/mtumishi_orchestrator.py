"""
Mtumishi orchestrator backed by the official GeoCongo AI SDK.
"""

import contextlib
import io
import importlib.metadata as importlib_metadata
import json
import os
import queue
import re
import subprocess
import sys
import threading
from datetime import datetime

from qgis.PyQt.QtCore import QCoreApplication, QObject, QSettings, Qt, QThread, QVariant, pyqtSignal, pyqtSlot

from .chimbua_visualization import apply_cluster_symbology, apply_grade_symbology, export_interactive_chimbua_html, make_qgis_symbol
from .drillhole_adapter import build_resource_sample_points, prepare_drillhole_dataset, validate_resource_estimation_inputs


class _MainThreadInvoker(QObject):
    """
    Execute des appels Python synchrones dans le thread principal Qt/QGIS.
    """

    executionRequested = pyqtSignal(object, object, object, object)

    def __init__(self):
        super().__init__()
        self.executionRequested.connect(self._execute, Qt.QueuedConnection)

    def invoke(self, func, args=None, kwargs=None):
        app = QCoreApplication.instance()
        args = tuple(args or ())
        kwargs = dict(kwargs or {})

        if app is None or QThread.currentThread() == app.thread():
            return func(*args, **kwargs)

        completion = {"event": threading.Event(), "result": None, "error": None}
        self.executionRequested.emit(func, args, kwargs, completion)
        completion["event"].wait()

        if completion["error"] is not None:
            raise completion["error"]
        return completion["result"]

    @pyqtSlot(object, object, object, object)
    def _execute(self, func, args, kwargs, completion):
        try:
            completion["result"] = func(*(args or ()), **(kwargs or {}))
        except Exception as exc:
            completion["error"] = exc
        finally:
            completion["event"].set()


class MtumishiOrchestrator:
    """
    Wrapper autour du vrai `geocongoai.Mtumishi` avec outils QGIS locaux.
    """

    DEFAULT_SERVER_URL = ""
    LEGACY_SERVER_URLS = {
        "http://137.184.96.142:8000",
        "https://137.184.96.142:8000",
    }
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, iface=None):
        self.iface = iface
        self._main_thread_invoker = _MainThreadInvoker()

        self.gemini_key = ""
        self.geocongo_key = ""
        self.server_url = self.DEFAULT_SERVER_URL
        self.preferred_model = ""

        self.mtumishi = None
        self.client = None
        self.runtime_name = None
        self.active_model_name = None
        self.status_message = "Mode heuristique local."
        self.last_init_error = ""
        self.last_run_result = None
        self.last_events = []
        self.last_drillhole_preparation = None
        self.last_chimbua_result = None
        self.last_chimbua_output_path = None
        self.last_resource_estimate = None
        self.last_resource_report_paths = None
        self.antigravity_diagnostic = None
        self._settings_signature = None

        self.reload_keys(force=True)

    def reload_keys(
        self,
        force: bool = False,
        gemini_key: str = None,
        geocongo_key: str = None,
        server_url: str = None,
        preferred_model: str = None,
    ):
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        self.migrate_legacy_server_url(settings)
        loaded_gemini_key = settings.value("api_keys/gemini", "")
        loaded_geocongo_key = settings.value("api_keys/geocongo", "")
        loaded_server_url = settings.value("server/url", self.DEFAULT_SERVER_URL)
        loaded_preferred_model = settings.value("llm/gemini_model", "")

        self.gemini_key = (loaded_gemini_key if gemini_key is None else gemini_key or "").strip()
        self.geocongo_key = (loaded_geocongo_key if geocongo_key is None else geocongo_key or "").strip()
        resolved_server_url = loaded_server_url if server_url is None else server_url or self.DEFAULT_SERVER_URL
        self.server_url = self.normalize_server_url(resolved_server_url)
        self.preferred_model = (loaded_preferred_model if preferred_model is None else preferred_model or "").strip()

        new_signature = (
            self.gemini_key,
            self.geocongo_key,
            self.server_url,
            self.preferred_model,
        )
        if not force and new_signature == self._settings_signature:
            return

        self._settings_signature = new_signature
        self.clear_conversation()
        self._initialize_mtumishi_sdk()

    def _initialize_mtumishi_sdk(self):
        self.mtumishi = None
        self.client = None
        self.runtime_name = None
        self.active_model_name = None
        self.last_run_result = None
        self.last_events = []
        self.last_drillhole_preparation = None
        self.last_chimbua_result = None
        self.last_chimbua_output_path = None
        self.last_resource_estimate = None
        self.last_resource_report_paths = None
        self.antigravity_diagnostic = self._probe_antigravity_environment()
        self.last_init_error = ""

        try:
            from geocongoai import Mtumishi
            from geocongoai.client import GeoCongoClient
        except Exception as exc:
            self.status_message = "Service GeoCongo AI indisponible."
            self.last_init_error = str(exc)
            return

        client_kwargs = {}
        if self.geocongo_key:
            client_kwargs["api_key"] = self.geocongo_key
            if self._looks_like_geocongo_base_url(self.server_url):
                client_kwargs["base_url"] = self.server_url

        if client_kwargs:
            try:
                self.client = GeoCongoClient(**client_kwargs)
            except Exception as exc:
                self.client = None
                self.last_init_error = f"Client GeoCongo AI non initialise: {exc}"

        runtime_type = "antigravity" if self.gemini_key else "native"
        runtime_kwargs = {
            "workspaces": [os.getcwd()],
            "model_name": self.preferred_model or self.DEFAULT_MODEL,
        }
        if self.gemini_key:
            runtime_kwargs["api_key"] = self.gemini_key

        try:
            self.mtumishi = Mtumishi(
                api_key=self.geocongo_key or None,
                client=self.client,
                runtime_type=runtime_type,
                runtime_kwargs=runtime_kwargs,
            )
            self.runtime_name = runtime_type
            self.active_model_name = runtime_kwargs["model_name"] if runtime_type == "antigravity" else "geocongo-native-v2"
            if runtime_type == "antigravity":
                self.status_message = f"Mtumishi est prêt via le moteur conversationnel avancé ({self.active_model_name})."
            else:
                self.status_message = "Mtumishi est actif via le moteur natif."
            self._register_qgis_tools()
        except Exception as exc:
            self.mtumishi = None
            self.status_message = "Initialisation de Mtumishi impossible."
            self.last_init_error = str(exc)

    def _looks_like_geocongo_base_url(self, url: str) -> bool:
        if not url:
            return False
        lowered = url.lower()
        return "supabase" in lowered or "/functions/v1" in lowered

    @classmethod
    def normalize_server_url(cls, url: str) -> str:
        normalized = (url or "").strip().rstrip("/")
        if normalized in cls.LEGACY_SERVER_URLS:
            return ""
        return normalized

    @classmethod
    def migrate_legacy_server_url(cls, settings: QSettings = None) -> bool:
        settings = settings or QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        current_value = settings.value("server/url", cls.DEFAULT_SERVER_URL)
        normalized = cls.normalize_server_url(current_value)
        if normalized == (current_value or "").strip():
            return False
        settings.setValue("server/url", normalized)
        return True

    def _sanitize_user_visible_text(self, text: str) -> str:
        if not text:
            return text

        replacements = (
            ("Mtumishi SDK", "Mtumishi"),
            ("SDK Mtumishi", "Mtumishi"),
            ("SDK GeoCongo AI", "service GeoCongo AI"),
            ("google-antigravity", "moteur conversationnel avancé"),
            ("Google Antigravity SDK", "moteur conversationnel avancé"),
            ("runtime Antigravity", "moteur conversationnel avancé"),
            ("Runtime Antigravity", "moteur conversationnel avancé"),
            ("runtime agentique Antigravity", "moteur conversationnel avancé"),
            ("Runtime agentique Antigravity", "moteur conversationnel avancé"),
            ("runtime antigravity", "moteur conversationnel avancé"),
            ("Runtime antigravity", "moteur conversationnel avancé"),
            ("antigravity", "moteur conversationnel avancé"),
            ("Antigravity", "moteur conversationnel avancé"),
        )

        sanitized = text
        for source, target in replacements:
            sanitized = sanitized.replace(source, target)
        return sanitized

    def _run_in_qgis_main_thread(self, func, *args, **kwargs):
        return self._main_thread_invoker.invoke(func, args=args, kwargs=kwargs)

    def _probe_antigravity_environment(self):
        diagnostic = {
            "available": False,
            "error": None,
            "protobuf_version": None,
            "antigravity_version": None,
        }

        try:
            diagnostic["protobuf_version"] = importlib_metadata.version("protobuf")
        except Exception:
            pass

        try:
            diagnostic["antigravity_version"] = importlib_metadata.version("google-antigravity")
        except Exception:
            pass

        try:
            import google.antigravity  # noqa: F401
            diagnostic["available"] = True
        except Exception as exc:
            diagnostic["error"] = str(exc)

        return diagnostic

    def get_antigravity_resolution_hint(self) -> str:
        diag = self.antigravity_diagnostic or {}
        error = diag.get("error")
        protobuf_version = diag.get("protobuf_version") or "inconnue"
        antigravity_version = diag.get("antigravity_version") or "inconnue"

        if error and "runtime_version" in error and "google.protobuf" in error:
            return (
                "Le moteur conversationnel avancé est installé, mais il ne peut pas se charger car "
                f"`protobuf` est trop ancien dans le Python de QGIS (`{protobuf_version}`). "
                f"La version détectée du moteur est `{antigravity_version}` et elle attend `protobuf>=7.35`."
            )

        if error:
            return f"Chargement du moteur conversationnel avancé impossible : {self._sanitize_user_visible_text(error)}"

        if diag.get("available"):
            return "Le moteur conversationnel avancé est disponible dans cet environnement."

        return "Diagnostic du moteur conversationnel indisponible."

    def get_dependency_diagnostics(self) -> dict:
        diag = self.antigravity_diagnostic or {}
        return {
            "python_executable": sys.executable,
            "gemini_key_present": bool(self.gemini_key),
            "geocongo_key_present": bool(self.geocongo_key),
            "antigravity_available": bool(diag.get("available")),
            "antigravity_error": self._sanitize_user_visible_text(diag.get("error")),
            "antigravity_version": diag.get("antigravity_version"),
            "protobuf_version": diag.get("protobuf_version"),
            "resolution_hint": self.get_antigravity_resolution_hint(),
            "recommended_packages": [
                "protobuf>=7.35",
                "composant conversationnel avancé",
                "google-genai>=1.0",
            ],
        }

    def repair_antigravity_dependencies(self) -> dict:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "--upgrade",
            "protobuf>=7.35",
            "google-antigravity>=0.1.16",
            "google-genai>=1.0",
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        self.reload_keys(force=True)
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": command,
            "diagnostics": self.get_dependency_diagnostics(),
        }

    def _register_qgis_tools(self):
        if not self.mtumishi:
            return

        from geocongoai.mtumishi.tools import GeoTool

        self.mtumishi.register_tool(GeoTool(
            name="qgis_get_layers",
            description=(
                "Liste les couches actuellement ouvertes dans QGIS Desktop avec leur nom, "
                "identifiant et type."
            ),
            parameters={"type": "object", "properties": {}},
            handler=self._get_layers,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_zoom_extent",
            description=(
                "Centre la vue de QGIS Desktop sur une emprise [xmin, ymin, xmax, ymax]."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "bbox": {
                        "type": "array",
                        "description": "[xmin, ymin, xmax, ymax]",
                        "items": {"type": "number"},
                    }
                },
                "required": ["bbox"],
            },
            handler=self._zoom_extent,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_add_layer",
            description=(
                "Charge une couche raster ou vecteur dans le projet QGIS Desktop."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier SIG."},
                    "name": {"type": "string", "description": "Nom d'affichage dans QGIS."},
                },
                "required": ["path"],
            },
            handler=self._add_layer,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_execute_python_script",
            description=(
                "Execute un script Python directement dans la session QGIS Desktop courante "
                "via PyQGIS. Utiliser cet outil quand l'utilisateur demande explicitement "
                "d'executer un script Python dans QGIS, d'automatiser une action de couche, "
                "de modifier une symbologie ou de manipuler le projet SIG."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code Python/PyQGIS a executer dans la session QGIS en cours."
                    }
                },
                "required": ["code"]
            },
            handler=self._execute_qgis_python_script,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_apply_raster_symbology",
            description=(
                "Applique une symbologie raster coloree dans QGIS Desktop. "
                "Utiliser cet outil pour symboliser une couche raster greenfield, "
                "faire ressortir les classes, appliquer une pseudocouleur ou recolorer "
                "une couche raster existante."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Nom de la couche raster cible. Si vide, utilise la couche active raster."
                    },
                    "classes": {
                        "type": "integer",
                        "description": "Nombre de classes de couleur a afficher.",
                        "default": 5
                    },
                    "color_ramp_name": {
                        "type": "string",
                        "description": "Nom de la rampe de couleurs QGIS (ex: Viridis, Spectral).",
                        "default": "Viridis"
                    }
                }
            },
            handler=self._apply_raster_symbology,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_remove_layer",
            description=(
                "Supprime une couche du projet QGIS Desktop par son nom ou son identifiant. "
                "Utiliser cet outil quand l'utilisateur demande de supprimer, retirer, "
                "enlever ou fermer une couche dans QGIS."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Nom exact de la couche a supprimer."
                    },
                    "layer_id": {
                        "type": "string",
                        "description": "Identifiant QGIS interne de la couche a supprimer."
                    }
                }
            },
            handler=self._remove_layer,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_prepare_drillhole_dataset",
            description=(
                "Prépare un jeu de données de forage depuis les couches QGIS Desktop pour une "
                "analyse Chimbua ou une visualisation 3D. Détecte les couches assay, collar et "
                "survey, les champs de teneur et les profondeurs, puis résume les données prêtes "
                "pour le moteur de forages."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "assay_layer_name": {
                        "type": "string",
                        "description": "Nom de la couche assay / intervalles / forages à analyser."
                    },
                    "collar_layer_name": {
                        "type": "string",
                        "description": "Nom de la couche de colliers si connue."
                    },
                    "survey_layer_name": {
                        "type": "string",
                        "description": "Nom de la couche survey / déviation si connue."
                    },
                    "grade_field": {
                        "type": "string",
                        "description": "Champ de teneur à analyser, par exemple Cu, Au ou cu_pct."
                    },
                    "cutoff": {
                        "type": "number",
                        "description": "Seuil minimum de teneur à retenir.",
                        "default": 0.0
                    }
                }
            },
            handler=self._prepare_drillhole_dataset,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_run_chimbua_pipeline",
            description=(
                "Lance un pipeline Chimbua 3D réel à partir des couches de forage QGIS, "
                "génère la visualisation HTML 3D, puis recharge les résultats utiles dans QGIS."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "assay_layer_name": {"type": "string"},
                    "collar_layer_name": {"type": "string"},
                    "survey_layer_name": {"type": "string"},
                    "grade_field": {"type": "string"},
                    "cutoff": {"type": "number", "default": 0.0},
                    "eps": {"type": "number", "default": 25.0},
                    "min_samples": {"type": "integer", "default": 3},
                    "output_html_path": {"type": "string"},
                    "open_after_export": {"type": "boolean", "default": True},
                }
            },
            handler=self._run_chimbua_pipeline,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_open_3d_result",
            description=(
                "Ouvre la dernière visualisation 3D Chimbua générée, ou un chemin HTML 3D fourni."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "html_path": {
                        "type": "string",
                        "description": "Chemin HTML à ouvrir. Si absent, utilise le dernier résultat Chimbua."
                    }
                }
            },
            handler=self._open_3d_result,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_style_chimbua_results",
            description=(
                "Applique une symbologie sur une couche de resultats Chimbua dans QGIS, "
                "soit par cluster_id, soit par teneur/grade."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "layer_name": {"type": "string"},
                    "mode": {"type": "string", "default": "cluster"},
                    "grade_field": {"type": "string", "default": "grade"},
                }
            },
            handler=self._style_chimbua_results,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_estimate_resources",
            description=(
                "Estime des ressources à partir des couches de forage QGIS en construisant un "
                "modèle de blocs 3D, en interpolant les teneurs, puis en classifiant les blocs "
                "par catégorie de ressources avec cutoff économique."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "assay_layer_name": {"type": "string"},
                    "collar_layer_name": {"type": "string"},
                    "survey_layer_name": {"type": "string"},
                    "grade_field": {"type": "string"},
                    "cutoff": {"type": "number", "default": 0.5},
                    "density": {"type": "number", "default": 2.7},
                    "method": {"type": "string", "default": "idw"},
                    "block_size_x": {"type": "number", "default": 25.0},
                    "block_size_y": {"type": "number", "default": 25.0},
                    "block_size_z": {"type": "number", "default": 10.0},
                    "search_range": {"type": "number", "default": 100.0},
                    "min_samples": {"type": "integer", "default": 3},
                    "max_samples": {"type": "integer", "default": 12},
                }
            },
            handler=self._estimate_resources,
        ))

        self.mtumishi.register_tool(GeoTool(
            name="qgis_export_resource_report",
            description=(
                "Exporte le dernier rapport d'estimation de ressources en HTML et JSON."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "base_path": {
                        "type": "string",
                        "description": "Chemin de base sans extension pour les fichiers de rapport."
                    }
                }
            },
            handler=self._export_resource_report,
        ))

    def _resolve_layer(self, layer_name: str = None, raster_only: bool = False):
        if not self.iface:
            raise ValueError("Interface QGIS indisponible.")

        from qgis.core import QgsMapLayerType, QgsProject

        active_layer = self.iface.activeLayer() if hasattr(self.iface, "activeLayer") else None
        all_layers = list(QgsProject.instance().mapLayers().values())
        if layer_name:
            project_layers = self.iface.mapCanvas().mapSettings().layers() if hasattr(self.iface, "mapCanvas") else []
            for layer in project_layers:
                if layer.name() == layer_name:
                    active_layer = layer
                    break
            if not active_layer or active_layer.name() != layer_name:
                for layer in all_layers:
                    if layer.name() == layer_name:
                        active_layer = layer
                        break

        if raster_only and (not active_layer or getattr(active_layer, "type", lambda: None)() != QgsMapLayerType.RasterLayer):
            preferred_keywords = ("greenfield", "gundua", "anomal", "potential", "favorability")
            for layer in all_layers:
                if getattr(layer, "type", lambda: None)() == QgsMapLayerType.RasterLayer:
                    lname = layer.name().lower()
                    if any(keyword in lname for keyword in preferred_keywords):
                        active_layer = layer
                        break

        if raster_only and (not active_layer or getattr(active_layer, "type", lambda: None)() != QgsMapLayerType.RasterLayer):
            for layer in all_layers:
                if getattr(layer, "type", lambda: None)() == QgsMapLayerType.RasterLayer:
                    active_layer = layer
                    break

        if not active_layer:
            raise ValueError("Aucune couche active disponible.")

        if raster_only and getattr(active_layer, "type", lambda: None)() != QgsMapLayerType.RasterLayer:
            raise ValueError(f"La couche '{active_layer.name()}' n'est pas un raster.")

        return active_layer

    def _get_layers(self):
        return self._run_in_qgis_main_thread(self._get_layers_impl)

    def _get_layers_impl(self):
        if not self.iface:
            raise ValueError("Interface QGIS indisponible.")

        from qgis.core import QgsMapLayerType, QgsProject

        type_map = {
            QgsMapLayerType.VectorLayer: "VectorLayer",
            QgsMapLayerType.RasterLayer: "RasterLayer",
            QgsMapLayerType.MeshLayer: "MeshLayer",
        }
        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            layer_type = type_map.get(layer.type(), str(layer.type()))
            layers.append({
                "id": layer.id(),
                "name": layer.name(),
                "type": layer_type,
            })
        return {
            "success": True,
            "data": {"layers": layers},
            "message": f"{len(layers)} couches trouvées",
        }

    def _zoom_extent(self, bbox):
        return self._run_in_qgis_main_thread(self._zoom_extent_impl, bbox)

    def _zoom_extent_impl(self, bbox):
        if not self.iface or not hasattr(self.iface, "mapCanvas"):
            raise ValueError("Canvas QGIS indisponible.")

        from qgis.core import QgsRectangle

        if not bbox or len(bbox) != 4:
            raise ValueError("BBox invalide.")

        rect = QgsRectangle(bbox[0], bbox[1], bbox[2], bbox[3])
        self.iface.mapCanvas().setExtent(rect)
        self.iface.mapCanvas().refresh()
        return {
            "success": True,
            "message": "Zoom appliqué sur l'emprise demandée.",
            "bbox": list(bbox),
        }

    def _add_layer(self, path: str, name: str = "Couche GeoCongo AI"):
        return self._run_in_qgis_main_thread(self._add_layer_impl, path, name)

    def _add_layer_impl(self, path: str, name: str = "Couche GeoCongo AI"):
        if not self.iface:
            raise ValueError("Interface QGIS indisponible.")

        from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

        layer = QgsVectorLayer(path, name, "ogr")
        if not layer.isValid():
            layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            return {
                "success": False,
                "message": f"Impossible de charger la couche : {path}",
                "name": name,
                "path": path,
            }

        QgsProject.instance().addMapLayer(layer)
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().refresh()
        return {
            "success": True,
            "message": f"Couche '{name}' ajoutée à QGIS",
            "name": name,
            "path": path,
            "layer_id": layer.id(),
        }

    def _remove_layer(self, layer_name: str = None, layer_id: str = None):
        return self._run_in_qgis_main_thread(self._remove_layer_impl, layer_name, layer_id)

    def _remove_layer_impl(self, layer_name: str = None, layer_id: str = None):
        if not self.iface:
            raise ValueError("Interface QGIS indisponible pour supprimer une couche.")

        from qgis.core import QgsProject

        project = QgsProject.instance()
        target_layer = None

        if layer_id:
            target_layer = project.mapLayer(layer_id)

        if target_layer is None and layer_name:
            for layer in project.mapLayers().values():
                if layer.name() == layer_name:
                    target_layer = layer
                    break

        if target_layer is None:
            return {
                "success": False,
                "message": f"Couche introuvable: {layer_name or layer_id}",
                "layer_name": layer_name,
                "layer_id": layer_id,
            }

        removed_name = target_layer.name()
        removed_id = target_layer.id()
        project.removeMapLayer(removed_id)

        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().refresh()

        return {
            "success": True,
            "message": f"Couche supprimée: {removed_name}",
            "layer_name": removed_name,
            "layer_id": removed_id,
        }

    def _resolve_drillhole_layer_name(self, layer_name: str = None, preferred_keywords=None, allow_fallback: bool = True):
        if not self.iface:
            raise ValueError("Interface QGIS indisponible.")

        from qgis.core import QgsMapLayerType, QgsProject

        preferred_keywords = tuple(keyword.lower() for keyword in (preferred_keywords or ()))
        layers = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if layer.type() == QgsMapLayerType.VectorLayer
        ]

        if layer_name:
            requested = layer_name.strip().lower()
            for layer in layers:
                if layer.name().strip().lower() == requested:
                    return layer
            for layer in layers:
                if requested in layer.name().strip().lower():
                    return layer

        if preferred_keywords:
            for layer in layers:
                lowered = layer.name().lower()
                if any(keyword in lowered for keyword in preferred_keywords):
                    return layer

        if not allow_fallback:
            return None

        active_layer = self.iface.activeLayer() if hasattr(self.iface, "activeLayer") else None
        if active_layer and active_layer in layers:
            return active_layer

        return layers[0] if layers else None

    def _prepare_drillhole_dataset(
        self,
        assay_layer_name: str = None,
        collar_layer_name: str = None,
        survey_layer_name: str = None,
        grade_field: str = None,
        cutoff: float = 0.0,
    ):
        return self._run_in_qgis_main_thread(
            self._prepare_drillhole_dataset_impl,
            assay_layer_name,
            collar_layer_name,
            survey_layer_name,
            grade_field,
            cutoff,
        )

    def _prepare_drillhole_dataset_impl(
        self,
        assay_layer_name: str = None,
        collar_layer_name: str = None,
        survey_layer_name: str = None,
        grade_field: str = None,
        cutoff: float = 0.0,
    ):
        assay_layer = self._resolve_drillhole_layer_name(
            assay_layer_name,
            preferred_keywords=("assay", "interval", "forage", "drill", "sample"),
            allow_fallback=True,
        )
        collar_layer = self._resolve_drillhole_layer_name(
            collar_layer_name,
            preferred_keywords=("collar", "head"),
            allow_fallback=False,
        )
        survey_layer = self._resolve_drillhole_layer_name(
            survey_layer_name,
            preferred_keywords=("survey", "deviation", "devia"),
            allow_fallback=False,
        )

        if assay_layer is None:
            raise ValueError("Aucune couche assay/forage exploitable n'a été trouvée dans QGIS.")

        prepared = prepare_drillhole_dataset(
            assay_layer=assay_layer,
            grade_field=grade_field or "",
            cutoff=float(cutoff or 0.0),
            collar_layer=collar_layer,
            survey_layer=survey_layer,
            project_or_layers=None,
        )

        schema = dict(prepared.get("schema") or {})
        preview_records = []
        for record in prepared.get("records", [])[:5]:
            preview_records.append({
                "hole_id": record.get("hole_id"),
                "grade_value": record.get("grade_value"),
                "mid_depth": record.get("mid_depth"),
                "x": record["point"].x() if record.get("point") else None,
                "y": record["point"].y() if record.get("point") else None,
                "z": record.get("z_value"),
            })

        result = {
            "success": True,
            "message": "Jeu de données de forage préparé pour Chimbua.",
            "layers": {
                "assay": assay_layer.name(),
                "collar": collar_layer.name() if collar_layer else None,
                "survey": survey_layer.name() if survey_layer else None,
            },
            "schema": schema,
            "stats": dict(prepared.get("stats") or {}),
            "grade_field": prepared.get("grade_field"),
            "cutoff": float(cutoff or 0.0),
            "records_prepared": len(prepared.get("records", [])),
            "preview": preview_records,
        }
        self.last_drillhole_preparation = result
        return result

    def _default_chimbua_output_path(self, assay_layer_name: str = None, grade_field: str = None):
        safe_assay = re.sub(r"[^A-Za-z0-9_-]+", "_", (assay_layer_name or "forages")).strip("_") or "forages"
        safe_grade = re.sub(r"[^A-Za-z0-9_-]+", "_", (grade_field or "grade")).strip("_") or "grade"
        downloads_dir = os.path.expanduser("~/Downloads")
        base_dir = downloads_dir if os.path.isdir(downloads_dir) else "/tmp"
        return os.path.join(base_dir, f"geocongoai_chimbua_{safe_assay}_{safe_grade}.html")

    def _default_resource_report_base_path(self, assay_layer_name: str = None, grade_field: str = None):
        safe_assay = re.sub(r"[^A-Za-z0-9_-]+", "_", (assay_layer_name or "forages")).strip("_") or "forages"
        safe_grade = re.sub(r"[^A-Za-z0-9_-]+", "_", (grade_field or "grade")).strip("_") or "grade"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        downloads_dir = os.path.expanduser("~/Downloads")
        base_dir = downloads_dir if os.path.isdir(downloads_dir) else "/tmp"
        return os.path.join(base_dir, f"geocongoai_resources_{safe_assay}_{safe_grade}_{timestamp}")

    def _run_chimbua_pipeline(
        self,
        assay_layer_name: str = None,
        collar_layer_name: str = None,
        survey_layer_name: str = None,
        grade_field: str = None,
        cutoff: float = 0.0,
        eps: float = 25.0,
        min_samples: int = 3,
        output_html_path: str = None,
        open_after_export: bool = True,
    ):
        prep_result = self._prepare_drillhole_dataset(
            assay_layer_name=assay_layer_name,
            collar_layer_name=collar_layer_name,
            survey_layer_name=survey_layer_name,
            grade_field=grade_field,
            cutoff=cutoff,
        )
        return self._run_chimbua_pipeline_from_preparation(
            prep_result=prep_result,
            eps=eps,
            min_samples=min_samples,
            output_html_path=output_html_path,
            open_after_export=open_after_export,
        )

    def _run_chimbua_pipeline_from_preparation(
        self,
        prep_result: dict,
        eps: float = 25.0,
        min_samples: int = 3,
        output_html_path: str = None,
        open_after_export: bool = True,
    ):
        from geocongoai.datasets import DrillholeDataset

        if not prep_result or not prep_result.get("success"):
            raise ValueError("Aucune préparation de forage valide n'est disponible pour Chimbua.")

        assay_layer_name = (prep_result.get("layers") or {}).get("assay")
        grade_field = prep_result.get("grade_field")
        output_html_path = output_html_path or self._default_chimbua_output_path(assay_layer_name, grade_field)

        prepared = prepare_drillhole_dataset(
            assay_layer=self._resolve_drillhole_layer_name(assay_layer_name, allow_fallback=True),
            grade_field=grade_field,
            cutoff=float(prep_result.get("cutoff") or 0.0),
            collar_layer=self._resolve_drillhole_layer_name((prep_result.get("layers") or {}).get("collar"), preferred_keywords=("collar", "head"), allow_fallback=False),
            survey_layer=self._resolve_drillhole_layer_name((prep_result.get("layers") or {}).get("survey"), preferred_keywords=("survey", "deviation", "devia"), allow_fallback=False),
            project_or_layers=None,
        )

        sdk_inputs = prepared.get("sdk_inputs") or {}
        collars = sdk_inputs.get("collars") or []
        assays = sdk_inputs.get("assays") or []
        survey = sdk_inputs.get("survey") or []
        if not collars:
            raise ValueError("Chimbua requiert au moins une couche de colliers ou des colliers dérivables.")
        if not assays:
            raise ValueError("Aucune analyse géochimique exploitable n'a été transmise à Chimbua.")

        assay_layer = prepared.get("assay_layer")
        crs_authid = assay_layer.crs().authid() if assay_layer and assay_layer.crs().isValid() else "EPSG:4326"
        title = f"GeoCongo AI — Chimbua 3D ({assay_layer_name or 'forages'})"

        dataset = DrillholeDataset(collars=collars, assays=assays, survey=survey or None)
        geo_result = dataset.analyze(
            method="dbscan",
            element=grade_field,
            grade_threshold=float(prep_result.get("cutoff") or 0.0),
            eps=float(eps),
            min_samples=int(min_samples),
            title=title,
            crs=crs_authid,
        )

        html_code = None
        try:
            html_code = export_interactive_chimbua_html(geo_result, output_path=output_html_path)
        except Exception:
            output_html_path = None

        load_result = self._load_chimbua_results(
            geo_result=geo_result,
            assay_layer=assay_layer,
            grade_field=grade_field,
        )

        open_result = None
        if open_after_export and output_html_path:
            open_result = self._open_3d_result(output_html_path)

        result = {
            "success": True,
            "status": "success",
            "message": "Pipeline Chimbua exécuté avec succès.",
            "layers": prep_result.get("layers") or {},
            "grade_field": grade_field,
            "cutoff": float(prep_result.get("cutoff") or 0.0),
            "eps": float(eps),
            "min_samples": int(min_samples),
            "total_intervals": len(getattr(geo_result, "points", []) or []),
            "clustering_summary": dict(getattr(geo_result, "metadata", {}) or {}),
            "statistics": dict(getattr(geo_result, "statistics", {}) or {}),
            "hulls_count": len(getattr(geo_result, "geometries", []) or []),
            "output_html_path": output_html_path,
            "html_generated": bool(html_code and output_html_path),
            "loaded_layers": load_result,
            "open_result": open_result,
        }
        self.last_chimbua_result = result
        self.last_chimbua_output_path = output_html_path
        return result

    def _load_chimbua_results(self, geo_result, assay_layer=None, grade_field: str = None):
        return self._run_in_qgis_main_thread(
            self._load_chimbua_results_impl,
            geo_result,
            assay_layer,
            grade_field,
        )

    def _load_chimbua_results_impl(self, geo_result, assay_layer=None, grade_field: str = None):
        from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPoint, QgsProject, QgsVectorLayer

        crs_authid = assay_layer.crs().authid() if assay_layer and assay_layer.crs().isValid() else "EPSG:4326"
        point_layer = QgsVectorLayer(f"PointZ?crs={crs_authid}", f"GeoCongo AI - Chimbua 3D ({grade_field or 'grade'})", "memory")
        point_provider = point_layer.dataProvider()
        point_fields = [
            QgsField("hole_id", QVariant.String),
            QgsField("from_m", QVariant.Double),
            QgsField("to_m", QVariant.Double),
            QgsField("grade", QVariant.Double),
            QgsField("cluster_id", QVariant.Int),
            QgsField("z_elev", QVariant.Double),
        ]
        if grade_field and grade_field.lower() != "grade":
            point_fields.append(QgsField(grade_field, QVariant.Double))
        point_provider.addAttributes(point_fields)
        point_layer.updateFields()

        point_features = []
        for point in getattr(geo_result, "points", []) or []:
            feature = QgsFeature(point_layer.fields())
            feature.setGeometry(QgsGeometry(QgsPoint(float(point["x"]), float(point["y"]), float(point["z"]))))
            grade_value = float(point.get(grade_field, point.get("value", 0.0)) or 0.0)
            attributes = [
                str(point.get("hole_id", "")),
                float(point.get("from_m", 0.0) or 0.0),
                float(point.get("to_m", 0.0) or 0.0),
                grade_value,
                int(point.get("cluster", -1) or -1),
                float(point.get("z", 0.0) or 0.0),
            ]
            if grade_field and grade_field.lower() != "grade":
                attributes.append(grade_value)
            feature.setAttributes([
                *attributes
            ])
            point_features.append(feature)
        point_provider.addFeatures(point_features)
        point_layer.updateExtents()
        apply_cluster_symbology(point_layer, cluster_field="cluster_id")
        QgsProject.instance().addMapLayer(point_layer)
        if hasattr(self.iface, "setActiveLayer"):
            self.iface.setActiveLayer(point_layer)

        collars_layer_name = None
        collar_features = []
        collars = getattr(geo_result, "collars", []) or []
        if collars:
            collars_layer = QgsVectorLayer(f"PointZ?crs={crs_authid}", "GeoCongo AI - Chimbua Collars", "memory")
            collars_provider = collars_layer.dataProvider()
            collars_provider.addAttributes([
                QgsField("hole_id", QVariant.String),
                QgsField("z", QVariant.Double),
                QgsField("dip", QVariant.Double),
                QgsField("azimuth", QVariant.Double),
            ])
            collars_layer.updateFields()
            for collar in collars:
                feature = QgsFeature(collars_layer.fields())
                feature.setGeometry(QgsGeometry(QgsPoint(float(collar["x"]), float(collar["y"]), float(collar["z"]))))
                feature.setAttributes([
                    str(collar.get("hole_id", "")),
                    float(collar.get("z", 0.0) or 0.0),
                    float(collar.get("dip", -90.0) or -90.0),
                    float(collar.get("azimuth", 0.0) or 0.0),
                ])
                collar_features.append(feature)
            collars_provider.addFeatures(collar_features)
            collars_layer.updateExtents()
            QgsProject.instance().addMapLayer(collars_layer)
            collars_layer_name = collars_layer.name()

        hull_vertices_layer_name = None
        hull_vertex_features = []
        hulls = getattr(geo_result, "geometries", []) or []
        if hulls:
            hull_vertices_layer = QgsVectorLayer(f"PointZ?crs={crs_authid}", "GeoCongo AI - Chimbua Hull Vertices", "memory")
            hull_vertices_provider = hull_vertices_layer.dataProvider()
            hull_vertices_provider.addAttributes([
                QgsField("cluster_id", QVariant.Int),
                QgsField("vertex_id", QVariant.Int),
                QgsField("volume_m3", QVariant.Double),
                QgsField("area_m2", QVariant.Double),
            ])
            hull_vertices_layer.updateFields()
            for hull in hulls:
                vertices = hull.get("vertices") or {}
                x_values = vertices.get("x") or []
                y_values = vertices.get("y") or []
                z_values = vertices.get("z") or []
                cluster_id = int(hull.get("cluster_id", -1) or -1)
                volume_m3 = float(hull.get("volume_m3", 0.0) or 0.0)
                area_m2 = float(hull.get("area_m2", 0.0) or 0.0)
                for vertex_id, (x_value, y_value, z_value) in enumerate(zip(x_values, y_values, z_values), start=1):
                    feature = QgsFeature(hull_vertices_layer.fields())
                    feature.setGeometry(QgsGeometry(QgsPoint(float(x_value), float(y_value), float(z_value))))
                    feature.setAttributes([
                        cluster_id,
                        vertex_id,
                        volume_m3,
                        area_m2,
                    ])
                    hull_vertex_features.append(feature)
            if hull_vertex_features:
                hull_vertices_provider.addFeatures(hull_vertex_features)
                hull_vertices_layer.updateExtents()
                QgsProject.instance().addMapLayer(hull_vertices_layer)
                hull_vertices_layer_name = hull_vertices_layer.name()

        if hasattr(self.iface, "mapCanvas") and point_features:
            self.iface.mapCanvas().setExtent(point_layer.extent())
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().refresh()

        return {
            "point_layer": point_layer.name(),
            "point_count": len(point_features),
            "collar_layer": collars_layer_name,
            "collar_count": len(collar_features),
            "hull_vertices_layer": hull_vertices_layer_name,
            "hull_vertex_count": len(hull_vertex_features),
        }

    def _open_3d_result(self, html_path: str = None):
        return self._run_in_qgis_main_thread(self._open_3d_result_impl, html_path)

    def _open_3d_result_impl(self, html_path: str = None):
        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtGui import QDesktopServices

        target_path = html_path or self.last_chimbua_output_path
        if not target_path:
            return {
                "success": False,
                "message": "Aucune visualisation 3D Chimbua n'est encore disponible.",
                "html_path": None,
            }

        if not os.path.exists(target_path):
            return {
                "success": False,
                "message": f"Le fichier 3D est introuvable : {target_path}",
                "html_path": target_path,
            }

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(target_path))
        return {
            "success": bool(opened),
            "message": "Visualisation 3D ouverte." if opened else "Impossible d'ouvrir automatiquement la visualisation 3D.",
            "html_path": target_path,
        }

    def _style_chimbua_results(
        self,
        layer_name: str = None,
        mode: str = "cluster",
        grade_field: str = "grade",
    ):
        return self._run_in_qgis_main_thread(self._style_chimbua_results_impl, layer_name, mode, grade_field)

    def _style_chimbua_results_impl(
        self,
        layer_name: str = None,
        mode: str = "cluster",
        grade_field: str = "grade",
    ):
        layer = self._resolve_drillhole_layer_name(
            layer_name,
            preferred_keywords=("chimbua 3d", "cluster", "dbscan", "chimbua"),
            allow_fallback=True,
        )
        if layer is None:
            raise ValueError("Aucune couche de resultats Chimbua n'a ete trouvee.")

        selected_mode = (mode or "cluster").strip().lower()
        if selected_mode == "grade":
            available_field_names = [field.name().lower() for field in layer.fields()]
            target_grade_field = grade_field if grade_field and grade_field.lower() in available_field_names else "grade"
            apply_grade_symbology(layer, grade_field=target_grade_field)
            message = f"Symbologie appliquee par teneur ({target_grade_field})."
        else:
            apply_cluster_symbology(layer, cluster_field="cluster_id")
            message = "Symbologie appliquee par cluster_id."

        if hasattr(self.iface, "layerTreeView"):
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().refresh()

        return {
            "success": True,
            "message": message,
            "layer_name": layer.name(),
            "mode": selected_mode,
            "grade_field": target_grade_field if selected_mode == "grade" else grade_field,
        }

    def _estimate_resources(
        self,
        assay_layer_name: str = None,
        collar_layer_name: str = None,
        survey_layer_name: str = None,
        grade_field: str = None,
        cutoff: float = 0.5,
        density: float = 2.7,
        method: str = "idw",
        block_size_x: float = 25.0,
        block_size_y: float = 25.0,
        block_size_z: float = 10.0,
        search_range: float = 100.0,
        min_samples: int = 3,
        max_samples: int = 12,
    ):
        prep_result = self._prepare_drillhole_dataset(
            assay_layer_name=assay_layer_name,
            collar_layer_name=collar_layer_name,
            survey_layer_name=survey_layer_name,
            grade_field=grade_field,
            cutoff=0.0,
        )
        return self._estimate_resources_from_preparation(
            prep_result=prep_result,
            cutoff=cutoff,
            density=density,
            method=method,
            block_size=(block_size_x, block_size_y, block_size_z),
            search_range=search_range,
            min_samples=min_samples,
            max_samples=max_samples,
        )

    def _estimate_resources_from_preparation(
        self,
        prep_result: dict,
        cutoff: float = 0.5,
        density: float = 2.7,
        method: str = "idw",
        block_size=(25.0, 25.0, 10.0),
        search_range: float = 100.0,
        min_samples: int = 3,
        max_samples: int = 12,
    ):
        from math import ceil

        from geocongoai.chimbua_engine.blockmodel import BlockModel3D
        from geocongoai.chimbua_engine.estimation import IDWEstimator, OrdinaryKriging
        from geocongoai.chimbua_engine.resources import ResourceEstimator

        if not prep_result or not prep_result.get("success"):
            raise ValueError("Aucune préparation de forage valide n'est disponible pour l'estimation de ressources.")

        layers = prep_result.get("layers") or {}
        grade_field = prep_result.get("grade_field")
        assay_layer = self._resolve_drillhole_layer_name(layers.get("assay"), allow_fallback=True)
        collar_layer = self._resolve_drillhole_layer_name(
            layers.get("collar"),
            preferred_keywords=("collar", "head"),
            allow_fallback=False,
        )
        survey_layer = self._resolve_drillhole_layer_name(
            layers.get("survey"),
            preferred_keywords=("survey", "deviation", "devia"),
            allow_fallback=False,
        )

        prepared = prepare_drillhole_dataset(
            assay_layer=assay_layer,
            grade_field=grade_field,
            cutoff=0.0,
            collar_layer=collar_layer,
            survey_layer=survey_layer,
            project_or_layers=None,
        )

        validation = validate_resource_estimation_inputs(
            prepared,
            cutoff_grade=float(cutoff),
            density=float(density),
            block_size=tuple(float(v) for v in block_size),
            search_range=float(search_range),
            min_samples=int(min_samples),
            method=method,
        )
        if not validation.get("ok"):
            raise ValueError(" ".join(validation.get("errors") or ["Validation métier de ressources échouée."]))

        sample_points = validation.get("sample_points") or build_resource_sample_points(prepared)
        extent = validation.get("extent") or {}
        dx, dy, dz = [float(v) for v in block_size]
        width_x = max(dx, float(extent.get("xmax", 0.0)) - float(extent.get("xmin", 0.0)))
        width_y = max(dy, float(extent.get("ymax", 0.0)) - float(extent.get("ymin", 0.0)))
        width_z = max(dz, float(extent.get("zmax", 0.0)) - float(extent.get("zmin", 0.0)))
        nx = max(1, int(ceil(width_x / dx)))
        ny = max(1, int(ceil(width_y / dy)))
        nz = max(1, int(ceil(width_z / dz)))

        block_model = BlockModel3D(
            origin=(float(extent["xmin"]), float(extent["ymin"]), float(extent["zmin"])),
            block_size=(dx, dy, dz),
            count=(nx, ny, nz),
        )
        blocks = block_model.build_grid()
        selected_method = (method or "idw").strip().lower()
        kriging = OrdinaryKriging() if selected_method == "ordinary_kriging" else None

        for block in blocks:
            target_pt = {"x": block["x"], "y": block["y"], "z": block["z"]}
            if selected_method == "ordinary_kriging":
                grade_value, variance = kriging.estimate(
                    sample_points,
                    target_pt,
                    max_range=float(search_range),
                    max_samples=max(1, int(max_samples)),
                )
            else:
                grade_value, variance = IDWEstimator.estimate(
                    sample_points,
                    target_pt,
                    power=2.0,
                    max_range=float(search_range),
                    min_samples=max(1, int(min_samples)),
                )
            block["estimated_grade"] = float(grade_value or 0.0)
            block["variance"] = float(variance or 0.0)

        report = ResourceEstimator.classify_and_report(
            blocks,
            density=float(density),
            cutoff_grade=float(cutoff),
        )
        for block in blocks:
            block["density"] = float(density)
        crs_authid = assay_layer.crs().authid() if assay_layer and assay_layer.crs().isValid() else "EPSG:4326"
        layer_result = self._load_resource_blocks(blocks, crs_authid, grade_field)
        report_export = self._export_resource_report_from_payload(
            payload={
                "layers": layers,
                "grade_field": grade_field,
                "method": selected_method,
                "cutoff": float(cutoff),
                "density": float(density),
                "block_size": {"x": dx, "y": dy, "z": dz},
                "search_range": float(search_range),
                "min_samples": int(min_samples),
                "max_samples": int(max_samples),
                "block_count": len(blocks),
                "sample_count": validation.get("sample_count", len(sample_points)),
                "unique_hole_count": validation.get("unique_hole_count", 0),
                "warnings": validation.get("warnings") or [],
                "report": report,
                "loaded_layers": layer_result,
            }
        )

        result = {
            "success": True,
            "message": "Estimation de ressources exécutée avec succès.",
            "layers": layers,
            "grade_field": grade_field,
            "method": selected_method,
            "cutoff": float(cutoff),
            "density": float(density),
            "block_size": {"x": dx, "y": dy, "z": dz},
            "search_range": float(search_range),
            "min_samples": int(min_samples),
            "max_samples": int(max_samples),
            "block_count": len(blocks),
            "sample_count": validation.get("sample_count", len(sample_points)),
            "unique_hole_count": validation.get("unique_hole_count", 0),
            "warnings": validation.get("warnings") or [],
            "report": report,
            "loaded_layers": layer_result,
            "report_export": report_export,
        }
        self.last_resource_estimate = result
        self.last_resource_report_paths = report_export
        return result

    def _load_resource_blocks(self, blocks, crs_authid: str, grade_field: str = None):
        return self._run_in_qgis_main_thread(self._load_resource_blocks_impl, blocks, crs_authid, grade_field)

    def _load_resource_blocks_impl(self, blocks, crs_authid: str, grade_field: str = None):
        from qgis.PyQt.QtGui import QColor
        from qgis.core import (
            QgsCategorizedSymbolRenderer,
            QgsFeature,
            QgsField,
            QgsGeometry,
            QgsPoint,
            QgsProject,
            QgsRendererCategory,
            QgsVectorLayer,
        )

        layer_name = f"GeoCongo AI - Ressources ({grade_field or 'grade'})"
        layer = QgsVectorLayer(f"PointZ?crs={crs_authid}", layer_name, "memory")
        provider = layer.dataProvider()
        provider.addAttributes([
            QgsField("ix", QVariant.Int),
            QgsField("iy", QVariant.Int),
            QgsField("iz", QVariant.Int),
            QgsField("grade_est", QVariant.Double),
            QgsField("variance", QVariant.Double),
            QgsField("category", QVariant.String),
            QgsField("volume_m3", QVariant.Double),
            QgsField("tonnage_t", QVariant.Double),
        ])
        layer.updateFields()

        features = []
        for block in blocks:
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry(QgsPoint(float(block["x"]), float(block["y"]), float(block["z"]))))
            volume = float(block.get("volume") or 0.0)
            density = float(block.get("density") or 0.0)
            feature.setAttributes([
                int(block.get("ix", 0)),
                int(block.get("iy", 0)),
                int(block.get("iz", 0)),
                float(block.get("estimated_grade") or 0.0),
                float(block.get("variance") or 0.0),
                str(block.get("category") or "Unclassified"),
                volume,
                volume * density if density > 0.0 else 0.0,
            ])
            features.append(feature)

        provider.addFeatures(features)
        layer.updateExtents()

        category_colors = {
            "Mesuré": "#0B8F3A",
            "Indiqué": "#E2A400",
            "Inféré": "#D95F02",
            "Non Économique": "#7A7A7A",
            "Unclassified": "#4C78A8",
        }
        categories = []
        for category_name, color_code in category_colors.items():
            symbol = make_qgis_symbol(layer)
            symbol.setColor(QColor(color_code))
            symbol.setOpacity(0.9)
            if hasattr(symbol, "setSize"):
                symbol.setSize(3.2)
            categories.append(QgsRendererCategory(category_name, symbol, category_name))
        renderer = QgsCategorizedSymbolRenderer("category", categories)
        layer.setRenderer(renderer)

        QgsProject.instance().addMapLayer(layer)
        if hasattr(self.iface, "setActiveLayer"):
            self.iface.setActiveLayer(layer)
        if hasattr(self.iface, "layerTreeView"):
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        if hasattr(self.iface, "mapCanvas") and features:
            self.iface.mapCanvas().setExtent(layer.extent())
            self.iface.mapCanvas().refresh()

        return {
            "resource_layer": layer.name(),
            "block_count": len(features),
        }

    def _export_resource_report(self, base_path: str = None):
        payload = self.last_resource_estimate
        if not payload:
            return {
                "success": False,
                "message": "Aucun résultat de ressources n'est disponible pour export.",
                "html_path": None,
                "json_path": None,
            }
        return self._export_resource_report_from_payload(payload, base_path=base_path)

    def _export_resource_report_from_payload(self, payload: dict, base_path: str = None):
        layers = payload.get("layers") or {}
        grade_field = payload.get("grade_field")
        assay_layer_name = layers.get("assay")
        base_path = (base_path or self._default_resource_report_base_path(assay_layer_name, grade_field)).strip()
        if base_path.lower().endswith(".json") or base_path.lower().endswith(".html"):
            base_path = os.path.splitext(base_path)[0]

        output_dir = os.path.dirname(base_path) or "."
        os.makedirs(output_dir, exist_ok=True)
        json_path = f"{base_path}.json"
        html_path = f"{base_path}.html"

        report_payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": {
                "assay_layer": assay_layer_name,
                "collar_layer": layers.get("collar"),
                "survey_layer": layers.get("survey"),
                "grade_field": grade_field,
                "method": payload.get("method"),
                "cutoff": payload.get("cutoff"),
                "density": payload.get("density"),
                "block_size": payload.get("block_size"),
                "search_range": payload.get("search_range"),
                "min_samples": payload.get("min_samples"),
                "max_samples": payload.get("max_samples"),
                "block_count": payload.get("block_count"),
                "sample_count": payload.get("sample_count"),
                "unique_hole_count": payload.get("unique_hole_count"),
            },
            "report": payload.get("report") or {},
            "warnings": payload.get("warnings") or [],
            "loaded_layers": payload.get("loaded_layers") or {},
        }

        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(report_payload, handle, ensure_ascii=False, indent=2)

        total = (report_payload["report"].get("total") or {})
        category_rows = []
        for row in report_payload["report"].get("by_category") or []:
            category_rows.append(
                "<tr>"
                f"<td>{row.get('category')}</td>"
                f"<td>{row.get('block_count', 0)}</td>"
                f"<td>{row.get('tonnage_t', 0)}</td>"
                f"<td>{row.get('mean_grade_pct', 0)}</td>"
                f"<td>{row.get('metal_contained_t', 0)}</td>"
                "</tr>"
            )
        warnings_html = "".join(f"<li>{warning}</li>" for warning in (report_payload.get("warnings") or [])) or "<li>Aucun avertissement.</li>"
        category_rows_html = "".join(category_rows) or '<tr><td colspan="5">Aucune catégorie calculée.</td></tr>'
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>GeoCongo AI - Rapport Ressources</title>"
            "<style>"
            "body{font-family:Arial,sans-serif;background:#f5f1e8;color:#1f2933;padding:24px;line-height:1.45;}"
            ".card{background:#fff;border-radius:14px;padding:20px;box-shadow:0 12px 35px rgba(0,0,0,0.08);margin-bottom:18px;}"
            "h1,h2{margin:0 0 12px 0;color:#0f4c5c;} table{width:100%;border-collapse:collapse;}"
            "th,td{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left;} th{background:#eef6f7;}"
            ".kpis{display:flex;gap:12px;flex-wrap:wrap}.kpi{background:#eef6f7;border-radius:10px;padding:12px 14px;min-width:180px}"
            ".muted{color:#5b6470}"
            "</style></head><body>"
            "<div class='card'>"
            "<h1>Rapport d'estimation de ressources</h1>"
            f"<p class='muted'>Généré le {report_payload['generated_at']}</p>"
            f"<p><strong>Couche assay :</strong> {assay_layer_name or 'n/a'}<br>"
            f"<strong>Champ analysé :</strong> {grade_field or 'n/a'}<br>"
            f"<strong>Méthode :</strong> {payload.get('method')}<br>"
            f"<strong>Cutoff :</strong> {payload.get('cutoff')}<br>"
            f"<strong>Densité :</strong> {payload.get('density')} t/m3</p>"
            "</div>"
            "<div class='card'><h2>Indicateurs globaux</h2>"
            "<div class='kpis'>"
            f"<div class='kpi'><strong>Tonnage total</strong><br>{total.get('total_tonnage_t', 0)} t</div>"
            f"<div class='kpi'><strong>Teneur moyenne</strong><br>{total.get('global_mean_grade_pct', 0)} %</div>"
            f"<div class='kpi'><strong>Métal contenu</strong><br>{total.get('total_metal_t', 0)} t</div>"
            f"<div class='kpi'><strong>Blocs générés</strong><br>{payload.get('block_count', 0)}</div>"
            "</div></div>"
            "<div class='card'><h2>Catégories de ressources</h2>"
            "<table><thead><tr><th>Catégorie</th><th>Blocs</th><th>Tonnage (t)</th><th>Teneur (%)</th><th>Métal contenu (t)</th></tr></thead>"
            f"<tbody>{category_rows_html}</tbody></table>"
            "</div>"
            f"<div class='card'><h2>Points de vigilance</h2><ul>{warnings_html}</ul></div>"
            "</body></html>"
        )

        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(html)

        export_result = {
            "success": True,
            "message": "Rapport de ressources exporté.",
            "json_path": json_path,
            "html_path": html_path,
        }
        self.last_resource_report_paths = export_result
        return export_result

    def _extract_layer_name_from_prompt(self, prompt: str):
        matched_layers = self._find_project_layer_names_in_prompt(prompt)
        if matched_layers:
            return matched_layers[0]

        patterns = [
            r"couche raster\s+([^\n,.]+)",
            r"couche\s*:\s*([^\n,]+)",
            r"sur\s+([A-Za-z0-9_()\- ]+)",
            r"couche\s+([^\n,.]+)",
            r"layer\s+([^\n,.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).strip(" :\"'")
                if candidate:
                    return candidate
        return None

    def _find_project_layer_names_in_prompt(self, prompt: str):
        if not self.iface:
            return []

        try:
            from qgis.core import QgsProject

            lowered_prompt = prompt.lower()
            matches = []
            for layer in QgsProject.instance().mapLayers().values():
                layer_name = layer.name() if layer else None
                if not layer_name:
                    continue
                start_index = lowered_prompt.find(layer_name.lower())
                if start_index != -1:
                    matches.append((start_index, -len(layer_name), layer_name))
            matches.sort()
            return [layer_name for _, _, layer_name in matches]
        except Exception:
            return []

    def _extract_drillhole_layers_from_prompt(self, prompt: str):
        mentioned_layers = self._find_project_layer_names_in_prompt(prompt)
        layer_map = {
            "assay_layer_name": None,
            "collar_layer_name": None,
            "survey_layer_name": None,
        }

        for layer_name in mentioned_layers:
            lowered = layer_name.lower()
            if layer_map["assay_layer_name"] is None and any(token in lowered for token in ("assay", "sample", "interval")):
                layer_map["assay_layer_name"] = layer_name
                continue
            if layer_map["collar_layer_name"] is None and any(token in lowered for token in ("collar", "head")):
                layer_map["collar_layer_name"] = layer_name
                continue
            if layer_map["survey_layer_name"] is None and any(token in lowered for token in ("survey", "deviation", "devia")):
                layer_map["survey_layer_name"] = layer_name

        text = prompt.lower()
        if "babbitt" in text:
            layer_map["assay_layer_name"] = layer_map["assay_layer_name"] or "assay_BABBITT"
            layer_map["collar_layer_name"] = layer_map["collar_layer_name"] or "collar_BABBITT"
            layer_map["survey_layer_name"] = layer_map["survey_layer_name"] or "survey_BABBITT"

        if layer_map["assay_layer_name"] is None and mentioned_layers:
            layer_map["assay_layer_name"] = mentioned_layers[0]

        return layer_map

    def _extract_grade_field_from_prompt(self, prompt: str):
        patterns = [
            r"champ\s+([A-Za-z0-9_]+)",
            r"teneur\s+(?:en|de)?\s*([A-Za-z0-9_]+)",
            r"grade\s+(?:field|champ)?\s*([A-Za-z0-9_]+)",
            r"\b(cu_pct|au_ppm|zn_pct|pb_pct|fe_pct|cu|au|zn|pb|fe)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_cutoff_from_prompt(self, prompt: str):
        match = re.search(r"(?:seuil|cutoff)\s*(?:>=|>|=|de)?\s*(-?\d+(?:[.,]\d+)?)", prompt, flags=re.IGNORECASE)
        if not match:
            return 0.0
        return float(match.group(1).replace(",", "."))

    def _has_cutoff_in_prompt(self, prompt: str):
        return bool(re.search(r"(?:seuil|cutoff)\s*(?:>=|>|=|de)?\s*(-?\d+(?:[.,]\d+)?)", prompt, flags=re.IGNORECASE))

    def _extract_eps_from_prompt(self, prompt: str):
        match = re.search(r"\beps\s*(?:=|de)?\s*(\d+(?:[.,]\d+)?)", prompt, flags=re.IGNORECASE)
        if not match:
            return 25.0
        return float(match.group(1).replace(",", "."))

    def _extract_min_samples_from_prompt(self, prompt: str):
        match = re.search(r"(?:min[_ ]?samples?|minimum d[’']?échantillons)\s*(?:=|de)?\s*(\d+)", prompt, flags=re.IGNORECASE)
        if not match:
            return 3
        return int(match.group(1))

    def _extract_density_from_prompt(self, prompt: str):
        match = re.search(r"(?:densite|densité|density)\s*(?:=|de)?\s*(\d+(?:[.,]\d+)?)", prompt, flags=re.IGNORECASE)
        if not match:
            return 2.7
        return float(match.group(1).replace(",", "."))

    def _extract_search_range_from_prompt(self, prompt: str):
        match = re.search(r"(?:search[_ ]?range|portee|portée|rayon)\s*(?:=|de)?\s*(\d+(?:[.,]\d+)?)", prompt, flags=re.IGNORECASE)
        if not match:
            return 100.0
        return float(match.group(1).replace(",", "."))

    def _extract_block_size_from_prompt(self, prompt: str):
        match = re.search(
            r"(?:taille de bloc|taille bloc|bloc(?:s)?|block size)\s*(?:=|de)?\s*(\d+(?:[.,]\d+)?)\s*[xX*,/ ]\s*(\d+(?:[.,]\d+)?)\s*[xX*,/ ]\s*(\d+(?:[.,]\d+)?)",
            prompt,
            flags=re.IGNORECASE,
        )
        if not match:
            return 25.0, 25.0, 10.0
        return tuple(float(match.group(i).replace(",", ".")) for i in range(1, 4))

    def _extract_resource_method_from_prompt(self, prompt: str):
        text = prompt.lower()
        if "krige" in text or "kriging" in text:
            return "ordinary_kriging"
        return "idw"

    def _extract_style_mode_from_prompt(self, prompt: str):
        text = prompt.lower()
        if "cluster" in text or "cluster_id" in text:
            return "cluster"
        if any(token in text for token in ("teneur", "grade", "cu", "au", "zn", "pb", "fe")):
            return "grade"
        return "cluster"

    def _detect_local_action(self, prompt: str):
        text = prompt.lower()
        drillhole_layers = self._extract_drillhole_layers_from_prompt(prompt)

        if (
            any(keyword in text for keyword in ("symbolog", "styl", "color", "couleur", "affich"))
            and "chimbua" in text
            and any(keyword in text for keyword in ("cluster", "cluster_id", "teneur", "grade", "cu", "au"))
        ):
            return {
                "tool": "qgis_style_chimbua_results",
                "args": {
                    "layer_name": self._extract_layer_name_from_prompt(prompt),
                    "mode": self._extract_style_mode_from_prompt(prompt),
                    "grade_field": self._extract_grade_field_from_prompt(prompt) or "grade",
                },
                "summary_builder": self._build_style_chimbua_summary,
            }

        if (
            any(keyword in text for keyword in ("exporte", "exporter", "sauvegarde", "génère", "genere"))
            and any(keyword in text for keyword in ("rapport", "report"))
            and any(keyword in text for keyword in ("ressource", "resource"))
        ):
            return {
                "tool": "qgis_export_resource_report",
                "args": {},
                "summary_builder": self._build_resource_report_export_summary,
            }

        if (
            any(keyword in text for keyword in ("ressource", "resource", "tonnage", "bloc", "block model", "krige", "kriging", "idw"))
            and any(keyword in text for keyword in ("estime", "estimer", "estimation", "calcule", "calculer", "modele", "modèle", "interpole"))
        ):
            block_size_x, block_size_y, block_size_z = self._extract_block_size_from_prompt(prompt)
            cutoff = self._extract_cutoff_from_prompt(prompt) if self._has_cutoff_in_prompt(prompt) else 0.5
            return {
                "tool": "qgis_estimate_resources",
                "args": {
                    "assay_layer_name": drillhole_layers["assay_layer_name"],
                    "collar_layer_name": drillhole_layers["collar_layer_name"],
                    "survey_layer_name": drillhole_layers["survey_layer_name"],
                    "grade_field": self._extract_grade_field_from_prompt(prompt),
                    "cutoff": cutoff,
                    "density": self._extract_density_from_prompt(prompt),
                    "method": self._extract_resource_method_from_prompt(prompt),
                    "block_size_x": block_size_x,
                    "block_size_y": block_size_y,
                    "block_size_z": block_size_z,
                    "search_range": self._extract_search_range_from_prompt(prompt),
                    "min_samples": self._extract_min_samples_from_prompt(prompt),
                    "max_samples": 12,
                },
                "summary_builder": self._build_resource_estimate_summary,
            }

        if (
            any(keyword in text for keyword in ("chimbua", "forage", "forages", "drill", "assay", "collar", "survey"))
            and any(keyword in text for keyword in ("lance", "lancer", "execute", "exécute", "run", "pipeline", "cluster", "dbscan", "visualisation 3d", "modélisation 3d", "modele 3d", "modelise"))
        ):
            return {
                "tool": "qgis_run_chimbua_pipeline",
                "args": {
                    "assay_layer_name": drillhole_layers["assay_layer_name"],
                    "collar_layer_name": drillhole_layers["collar_layer_name"],
                    "survey_layer_name": drillhole_layers["survey_layer_name"],
                    "grade_field": self._extract_grade_field_from_prompt(prompt),
                    "cutoff": self._extract_cutoff_from_prompt(prompt),
                    "eps": self._extract_eps_from_prompt(prompt),
                    "min_samples": self._extract_min_samples_from_prompt(prompt),
                    "open_after_export": True,
                },
                "summary_builder": self._build_chimbua_pipeline_summary,
            }

        if (
            any(keyword in text for keyword in ("ouvre", "ouvrir", "affiche", "visualise", "visualisation"))
            and "3d" in text
            and any(keyword in text for keyword in ("chimbua", "forage", "forages", "html", "resultat", "résultat"))
        ):
            return {
                "tool": "qgis_open_3d_result",
                "args": {},
                "summary_builder": self._build_open_3d_result_summary,
            }

        if (
            any(keyword in text for keyword in ("forage", "forages", "drill", "assay", "collar", "survey", "3d", "ressource", "resource"))
            and any(keyword in text for keyword in ("prepare", "prépare", "prepare-moi", "analyse", "analyse-moi", "comprend", "comprendre", "modele", "modél"))
        ):
            return {
                "tool": "qgis_prepare_drillhole_dataset",
                "args": {
                    "assay_layer_name": drillhole_layers["assay_layer_name"],
                    "collar_layer_name": drillhole_layers["collar_layer_name"],
                    "survey_layer_name": drillhole_layers["survey_layer_name"],
                    "grade_field": self._extract_grade_field_from_prompt(prompt),
                    "cutoff": self._extract_cutoff_from_prompt(prompt),
                },
                "summary_builder": self._build_drillhole_preparation_summary,
            }

        if any(keyword in text for keyword in ("supprime", "supprimer", "retire", "retirer", "enleve", "enlever")) and "couche" in text:
            return {
                "tool": "qgis_remove_layer",
                "args": {
                    "layer_name": self._extract_layer_name_from_prompt(prompt),
                },
                "summary_builder": self._build_remove_layer_summary,
            }

        if (
            ("symbolog" in text or "symbolis" in text or "pseudocouleur" in text or "couleur" in text)
            and ("raster" in text or "greenfield" in text)
        ):
            classes_match = re.search(r"(\d+)\s*classes?", text)
            classes = int(classes_match.group(1)) if classes_match else 5
            ramp = "Viridis"
            for candidate in ("Viridis", "Spectral", "Magma", "Inferno", "Turbo", "Plasma"):
                if candidate.lower() in text:
                    ramp = candidate
                    break
            return {
                "tool": "qgis_apply_raster_symbology",
                "args": {
                    "layer_name": self._extract_layer_name_from_prompt(prompt),
                    "classes": classes,
                    "color_ramp_name": ramp,
                },
                "summary_builder": self._build_raster_symbology_summary,
            }

        if ("script python" in text or "script pyqgis" in text or "exécute un script" in text or "execute un script" in text):
            code_match = re.search(r"```(?:python)?\s*(.*?)```", prompt, flags=re.IGNORECASE | re.DOTALL)
            if code_match:
                return {
                    "tool": "qgis_execute_python_script",
                    "args": {"code": code_match.group(1).strip()},
                    "summary_builder": self._build_python_execution_summary,
                }

        return None

    def _detect_local_actions(self, prompt: str):
        segments = [segment.strip() for segment in re.split(r"[\n\r]+", prompt) if segment.strip()]
        if len(segments) <= 1:
            split_segments = []
            for part in re.split(r"\b(?:puis|ensuite|and then)\b", prompt, flags=re.IGNORECASE):
                cleaned = part.strip(" ,;")
                if cleaned:
                    split_segments.append(cleaned)
            segments = split_segments or [prompt]

        actions = []
        seen = set()
        for segment in segments:
            action = self._detect_local_action(segment)
            if not action:
                continue
            signature = (
                action["tool"],
                json.dumps(action.get("args") or {}, sort_keys=True, ensure_ascii=False, default=str),
            )
            if signature in seen:
                continue
            seen.add(signature)
            actions.append(action)

        if actions:
            return actions

        fallback_action = self._detect_local_action(prompt)
        return [fallback_action] if fallback_action else []

    def _build_raster_symbology_summary(self, result: dict, args: dict) -> str:
        if not isinstance(result, dict) or not result.get("success"):
            return "⚠️ La symbologie raster n'a pas pu être appliquée."
        return (
            "### 🎨 Symbologie Raster Appliquée\n\n"
            f"La couche **{result.get('layer_name', 'raster')}** a été stylée avec "
            f"**{result.get('classes', args.get('classes', 5))} classes** et la rampe "
            f"**{result.get('color_ramp_name', args.get('color_ramp_name', 'Viridis'))}**.\n\n"
            f"Plage de valeurs : `{result.get('minimum')}` à `{result.get('maximum')}`."
        )

    def _build_python_execution_summary(self, result: dict, _args: dict) -> str:
        if not isinstance(result, dict):
            return "⚠️ Le script PyQGIS n'a pas renvoyé de résultat exploitable."
        if not result.get("success"):
            return (
                "### 🐍 Exécution PyQGIS\n\n"
                f"Le script a échoué : `{result.get('error', 'erreur inconnue')}`"
            )
        stdout = (result.get("stdout") or "").strip()
        return (
            "### 🐍 Exécution PyQGIS\n\n"
            "Le script Python a été exécuté dans QGIS avec succès.\n\n"
            f"Sortie standard :\n```\n{stdout or 'Aucune sortie'}\n```"
        )

    def _build_remove_layer_summary(self, result: dict, args: dict) -> str:
        target_name = args.get("layer_name") or args.get("layer_id") or "la couche demandee"
        if not isinstance(result, dict) or not result.get("success"):
            return (
                "### 🗑️ Suppression de couche\n\n"
                f"Je n'ai pas pu supprimer **{target_name}**.\n\n"
                f"Détail : `{(result or {}).get('message', 'erreur inconnue')}`"
            )
        return (
            "### 🗑️ Suppression de couche\n\n"
            f"La couche **{result.get('layer_name', target_name)}** a été supprimée avec succès."
        )

    def _build_drillhole_preparation_summary(self, result: dict, _args: dict) -> str:
        if not isinstance(result, dict) or not result.get("success"):
            message = (result or {}).get("message", "préparation impossible")
            return (
                "### ⛏️ Préparation Forages\n\n"
                f"La préparation des couches de forage a échoué : `{message}`"
            )

        layers = result.get("layers") or {}
        schema = result.get("schema") or {}
        stats = result.get("stats") or {}
        preview = result.get("preview") or []
        lines = [
            "### ⛏️ Préparation Forages",
            "",
            "Les couches QGIS sont maintenant prêtes pour un futur pipeline Chimbua.",
            "",
            f"- **Assay** : {layers.get('assay') or 'non détectée'}",
            f"- **Collar** : {layers.get('collar') or 'non détectée'}",
            f"- **Survey** : {layers.get('survey') or 'non détectée'}",
            f"- **Champ de teneur** : {result.get('grade_field') or 'non détecté'}",
            f"- **Champ trou** : {schema.get('assay_hole_id_field') or 'non détecté'}",
            f"- **From / To** : {schema.get('from_field') or 'n/a'} / {schema.get('to_field') or 'n/a'}",
            f"- **Enregistrements préparés** : {result.get('records_prepared', 0)}",
            f"- **Échantillons source** : {stats.get('source_feature_count', 0)}",
        ]
        if preview:
            first = preview[0]
            lines.extend([
                "",
                "**Aperçu du premier intervalle prêt**",
                f"- Trou : `{first.get('hole_id')}`",
                f"- Teneur : `{first.get('grade_value')}`",
                f"- Profondeur médiane : `{first.get('mid_depth')}`",
                f"- Position 3D : `({first.get('x')}, {first.get('y')}, {first.get('z')})`",
            ])
        return "\n".join(lines)

    def _build_chimbua_pipeline_summary(self, result: dict, _args: dict) -> str:
        if not isinstance(result, dict) or not result.get("success"):
            message = (result or {}).get("message", "pipeline Chimbua impossible")
            return (
                "### ⛏️ Chimbua 3D\n\n"
                f"Le pipeline Chimbua a échoué : `{message}`"
            )

        layers = result.get("layers") or {}
        loaded = result.get("loaded_layers") or {}
        stats = result.get("statistics") or {}
        open_result = result.get("open_result") or {}
        return "\n".join([
            "### ⛏️ Chimbua 3D",
            "",
            "Le pipeline de forages Chimbua a été exécuté avec succès.",
            "",
            f"- **Assay** : {layers.get('assay') or 'non détectée'}",
            f"- **Collar** : {layers.get('collar') or 'non détectée'}",
            f"- **Survey** : {layers.get('survey') or 'non détectée'}",
            f"- **Champ analysé** : {result.get('grade_field') or 'non détecté'}",
            f"- **Intervalles traités** : {result.get('total_intervals', 0)}",
            f"- **Clusters 3D** : {(result.get('clustering_summary') or {}).get('cluster_count', 0)}",
            f"- **Couche QGIS créée** : {loaded.get('point_layer') or 'aucune'}",
            f"- **Collars rechargés** : {loaded.get('collar_count', 0)}",
            f"- **Sommets des volumes** : {loaded.get('hull_vertex_count', 0)}",
            f"- **HTML 3D** : {result.get('output_html_path') or 'non généré'}",
            f"- **Ouverture automatique** : {'oui' if open_result.get('success') else 'non'}",
            f"- **Valeur max** : {stats.get('max', 'n/a')}",
        ])

    def _build_open_3d_result_summary(self, result: dict, _args: dict) -> str:
        if not isinstance(result, dict) or not result.get("success"):
            message = (result or {}).get("message") or "Impossible d'ouvrir la visualisation 3D."
            return (
                "### 🌐 Visualisation 3D\n\n"
                f"{message}"
            )
        return (
            "### 🌐 Visualisation 3D\n\n"
            f"La visualisation 3D a été ouverte depuis `{result.get('html_path')}`."
        )

    def _build_resource_estimate_summary(self, result: dict, _args: dict) -> str:
        if not isinstance(result, dict) or not result.get("success"):
            message = (result or {}).get("message", "estimation de ressources impossible")
            return (
                "### 📦 Estimation de Ressources\n\n"
                f"L'estimation de ressources a échoué : `{message}`"
            )

        report = result.get("report") or {}
        total = report.get("total") or {}
        categories = report.get("by_category") or []
        exported = result.get("report_export") or {}
        lines = [
            "### 📦 Estimation de Ressources",
            "",
            "Le modèle de blocs Chimbua a été généré et classifié.",
            "",
            f"- **Méthode** : {result.get('method')}",
            f"- **Champ analysé** : {result.get('grade_field') or 'non détecté'}",
            f"- **Cutoff économique** : {result.get('cutoff')}",
            f"- **Densité** : {result.get('density')} t/m3",
            f"- **Trous utilisés** : {result.get('unique_hole_count', 0)}",
            f"- **Points interpolés** : {result.get('sample_count', 0)}",
            f"- **Blocs générés** : {result.get('block_count', 0)}",
            f"- **Couche QGIS** : {(result.get('loaded_layers') or {}).get('resource_layer') or 'aucune'}",
            f"- **Tonnage total** : {total.get('total_tonnage_t', 0)} t",
            f"- **Teneur moyenne globale** : {total.get('global_mean_grade_pct', 0)} %",
            f"- **Métal contenu** : {total.get('total_metal_t', 0)} t",
            f"- **Rapport JSON** : {exported.get('json_path') or 'non exporté'}",
            f"- **Rapport HTML** : {exported.get('html_path') or 'non exporté'}",
        ]
        if categories:
            lines.extend(["", "**Catégories de ressources**"])
            for item in categories:
                lines.append(
                    f"- **{item.get('category')}** : {item.get('block_count', 0)} blocs, "
                    f"{item.get('tonnage_t', 0)} t à {item.get('mean_grade_pct', 0)} %"
                )
        warnings = result.get("warnings") or []
        if warnings:
            lines.extend(["", "**Points de vigilance**"])
            for warning in warnings:
                lines.append(f"- {warning}")
        return "\n".join(lines)

    def _build_resource_report_export_summary(self, result: dict, _args: dict) -> str:
        if not isinstance(result, dict) or not result.get("success"):
            message = (result or {}).get("message") or "Impossible d'exporter le rapport de ressources."
            return (
                "### 📄 Rapport Ressources\n\n"
                f"{message}"
            )
        return "\n".join([
            "### 📄 Rapport Ressources",
            "",
            "Le rapport de ressources a été exporté avec succès.",
            "",
            f"- **JSON** : {result.get('json_path')}",
            f"- **HTML** : {result.get('html_path')}",
        ])

    def _build_style_chimbua_summary(self, result: dict, _args: dict) -> str:
        if not isinstance(result, dict) or not result.get("success"):
            message = (result or {}).get("message") or "Impossible d'appliquer la symbologie Chimbua."
            return (
                "### 🎨 Symbologie Chimbua\n\n"
                f"{message}"
            )
        mode_label = "par cluster_id" if result.get("mode") == "cluster" else f"par teneur ({result.get('grade_field')})"
        return (
            "### 🎨 Symbologie Chimbua\n\n"
            f"La couche **{result.get('layer_name')}** est maintenant stylée {mode_label}."
        )

    def _run_local_action(self, prompt: str):
        actions = self._detect_local_actions(prompt)
        if not actions:
            return None

        executed_actions = []
        for action in actions:
            tool_name = action["tool"]
            args = action["args"]
            summary_builder = action["summary_builder"]

            if tool_name == "qgis_apply_raster_symbology":
                result = self._apply_raster_symbology(**args)
            elif tool_name == "qgis_remove_layer":
                result = self._remove_layer(**args)
            elif tool_name == "qgis_execute_python_script":
                result = self._execute_qgis_python_script(**args)
            elif tool_name == "qgis_prepare_drillhole_dataset":
                result = self._prepare_drillhole_dataset(**args)
            elif tool_name == "qgis_run_chimbua_pipeline":
                result = self._run_chimbua_pipeline(**args)
            elif tool_name == "qgis_open_3d_result":
                result = self._open_3d_result(**args)
            elif tool_name == "qgis_style_chimbua_results":
                result = self._style_chimbua_results(**args)
            elif tool_name == "qgis_estimate_resources":
                result = self._estimate_resources(**args)
            elif tool_name == "qgis_export_resource_report":
                result = self._export_resource_report(**args)
            else:
                raise ValueError(f"Outil local non pris en charge: {tool_name}")

            executed_actions.append({
                "tool": tool_name,
                "args": args,
                "result": result,
                "summary": summary_builder(result, args),
            })

        if len(executed_actions) == 1:
            return executed_actions[0]

        return {
            "multi": True,
            "actions": executed_actions,
            "tool": executed_actions[-1]["tool"],
            "args": executed_actions[-1]["args"],
            "result": executed_actions[-1]["result"],
            "summary": "\n\n".join(action["summary"] for action in executed_actions if action.get("summary")),
        }

    def _execute_qgis_python_script(self, code: str):
        return self._run_in_qgis_main_thread(self._execute_qgis_python_script_impl, code)

    def _execute_qgis_python_script_impl(self, code: str):
        if not self.iface:
            raise ValueError("Interface QGIS indisponible pour l'execution PyQGIS.")

        from qgis.core import QgsProject
        from qgis.utils import iface as qgis_iface

        scope = {
            "__name__": "__mtumishi_qgis__",
            "iface": self.iface or qgis_iface,
            "qgis_iface": self.iface or qgis_iface,
            "QgsProject": QgsProject,
            "project": QgsProject.instance(),
            "result": None,
        }

        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, scope, scope)
            return {
                "success": True,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "result": scope.get("result"),
            }
        except Exception as exc:
            return {
                "success": False,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "error": str(exc),
            }

    def _apply_raster_symbology(
        self,
        layer_name: str = None,
        classes: int = 5,
        color_ramp_name: str = "Viridis",
    ):
        return self._run_in_qgis_main_thread(
            self._apply_raster_symbology_impl,
            layer_name,
            classes,
            color_ramp_name,
        )

    def _apply_raster_symbology_impl(
        self,
        layer_name: str = None,
        classes: int = 5,
        color_ramp_name: str = "Viridis",
    ):
        if not self.iface:
            raise ValueError("Interface QGIS indisponible pour la symbologie raster.")

        from qgis.PyQt.QtGui import QColor
        from qgis.core import (
            QgsColorRampShader,
            QgsGradientColorRamp,
            QgsRasterBandStats,
            QgsRasterShader,
            QgsSingleBandPseudoColorRenderer,
            QgsStyle,
        )

        layer = self._resolve_layer(layer_name=layer_name, raster_only=True)
        classes = max(2, int(classes))

        provider = layer.dataProvider()
        stats = provider.bandStatistics(1, QgsRasterBandStats.All)
        min_val = stats.minimumValue
        max_val = stats.maximumValue
        if min_val == max_val:
            max_val = min_val + 1.0

        ramp = QgsStyle.defaultStyle().colorRamp(color_ramp_name)
        if ramp is None:
            ramp = QgsGradientColorRamp(QColor("#440154"), QColor("#FDE725"))

        items = []
        step_count = max(classes - 1, 1)
        for idx in range(classes):
            ratio = idx / step_count
            value = min_val + ((max_val - min_val) * ratio)
            items.append(
                QgsColorRampShader.ColorRampItem(
                    value,
                    ramp.color(ratio),
                    f"Classe {idx + 1}",
                )
            )

        shader_function = QgsColorRampShader()
        shader_function.setColorRampType(QgsColorRampShader.Discrete)
        shader_function.setColorRampItemList(items)

        shader = QgsRasterShader()
        shader.setRasterShaderFunction(shader_function)

        renderer = QgsSingleBandPseudoColorRenderer(provider, 1, shader)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        if hasattr(self.iface, "layerTreeView"):
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().refresh()

        return {
            "success": True,
            "layer_name": layer.name(),
            "classes": classes,
            "color_ramp_name": color_ramp_name,
            "minimum": min_val,
            "maximum": max_val,
        }

    def clear_conversation(self):
        if self.mtumishi:
            try:
                self.mtumishi.reset_memory()
            except Exception:
                pass

    def get_status_message(self) -> str:
        if self.antigravity_diagnostic and self.gemini_key and not self.antigravity_diagnostic.get("available"):
            diag_hint = self.get_antigravity_resolution_hint()
            if self.last_init_error:
                return self._sanitize_user_visible_text(
                    f"{self.status_message} Détail: {self.last_init_error} | Moteur conversationnel: {diag_hint}"
                )
            return self._sanitize_user_visible_text(
                f"{self.status_message} Moteur conversationnel: {diag_hint}"
            )
        if self.last_init_error:
            return self._sanitize_user_visible_text(f"{self.status_message} Détail: {self.last_init_error}")
        return self._sanitize_user_visible_text(self.status_message)

    def is_gemini_active(self) -> bool:
        return bool(self.gemini_key and self.mtumishi and self.runtime_name == "antigravity")

    def _build_context(self, context_dict: dict = None):
        from geocongoai import GeoSpatialContext

        context_dict = context_dict or {}
        bbox = context_dict.get("bbox")
        bbox_tuple = tuple(bbox) if bbox and len(bbox) == 4 else None
        metadata = dict(context_dict.get("metadata") or {})
        return GeoSpatialContext(
            bbox=bbox_tuple,
            crs=context_dict.get("crs") or "EPSG:4326",
            province=context_dict.get("province"),
            target_commodity=context_dict.get("target_commodity"),
            active_layer=context_dict.get("active_layer"),
            metadata=metadata,
        )

    def _update_runtime_status_from_events(self, events):
        self.last_events = [ev.to_dict() if hasattr(ev, "to_dict") else ev for ev in events]

        fallback_event = None
        model_name = self.active_model_name
        for ev in events:
            metadata = getattr(ev, "metadata", {}) or {}
            if metadata.get("fallback"):
                fallback_event = ev
            if metadata.get("model"):
                model_name = metadata["model"]

        if fallback_event:
            self.runtime_name = "native-fallback"
            self.active_model_name = model_name
            diag_hint = self.get_antigravity_resolution_hint()
            fallback_content = self._sanitize_user_visible_text(getattr(fallback_event, "content", "") or "")
            self.status_message = (
                f"Mtumishi bascule sur le moteur natif. {fallback_content} {diag_hint}"
            ).strip()
            return

        if self.gemini_key:
            self.runtime_name = "antigravity"
            self.active_model_name = model_name or self.preferred_model or self.DEFAULT_MODEL
            self.status_message = f"Mtumishi est actif via le moteur conversationnel avancé ({self.active_model_name})."
        else:
            self.runtime_name = "native"
            self.active_model_name = "geocongo-native-v2"
            self.status_message = "Mtumishi est actif via le moteur natif."

    def validate_gemini_connection(
        self,
        probe_prompt: str = "Reponds uniquement par OK.",
        force_reload: bool = False,
    ) -> tuple[bool, str]:
        if force_reload:
            self.reload_keys(force=True)
        if not self.is_gemini_active():
            return False, self.get_status_message()
        if not self.mtumishi:
            return False, "Mtumishi n'est pas initialisé."

        events = []
        try:
            result = self.mtumishi.run_with_stream(
                probe_prompt,
                on_event=events.append,
                context_override=self._build_context(),
            )
            self._update_runtime_status_from_events(events)
            self.clear_conversation()

            if self.runtime_name == "native-fallback":
                return False, self.get_status_message()

            summary = (result.summary or "").strip() if result else ""
            return True, summary or "OK"
        except Exception as exc:
            self.last_init_error = str(exc)
            return False, str(exc)

    def reason(self, prompt: str, context_dict: dict = None) -> str:
        self.reload_keys()
        if not self.mtumishi:
            return (
                "⚠️ Mtumishi n'est pas disponible.\n\n"
                f"Statut actuel : {self.get_status_message()}"
            )

        try:
            result = self.mtumishi.run(prompt, context_override=self._build_context(context_dict))
            self.last_run_result = result
            if getattr(result, "summary", None):
                return result.summary
            return str(result)
        except Exception as exc:
            return (
                f"⚠️ Erreur lors de l'appel à Mtumishi : {exc}\n\n"
                f"Statut actuel : {self.get_status_message()}"
            )

    def stream_reason(self, prompt: str, context_dict: dict = None):
        for item in self.stream_reason_events(prompt, context_dict):
            if item.get("kind") == "text":
                yield item.get("content", "")
            elif item.get("kind") == "error":
                yield item.get("content", "")

    def stream_reason_events(self, prompt: str, context_dict: dict = None):
        self.reload_keys()
        if not self.mtumishi:
            yield {
                "kind": "error",
                "content": (
                    "⚠️ Mtumishi n'est pas disponible.\n\n"
                    f"Statut actuel : {self.get_status_message()}"
                ),
            }
            return

        try:
            local_action = self._run_local_action(prompt)
        except Exception as exc:
            yield {
                "kind": "status",
                "content": "Routage local des commandes QGIS...",
                "metadata": {"runtime": "local-router"},
            }
            yield {
                "kind": "tool_call",
                "content": "Lancement outil QGIS local",
                "metadata": {"tool": "local_router", "args": {"prompt": prompt}},
            }
            yield {
                "kind": "tool_result",
                "content": str(exc),
                "metadata": {"tool": "local_router", "status": "error", "result": str(exc)},
            }
            yield {
                "kind": "error",
                "content": f"⚠️ Erreur lors de l'exécution locale QGIS : {exc}",
            }
            return

        if local_action is not None:
            yield {
                "kind": "status",
                "content": "Commande QGIS reconnue localement. Exécution directe sans délégation au runtime SDK.",
                "metadata": {"runtime": "local-router"},
            }
            actions_to_emit = local_action.get("actions") if isinstance(local_action, dict) and local_action.get("multi") else [local_action]
            for action_item in actions_to_emit:
                yield {
                    "kind": "tool_call",
                    "content": f"Lancement de l'outil local {action_item['tool']}",
                    "metadata": {"tool": action_item["tool"], "args": action_item["args"]},
                }
                yield {
                    "kind": "tool_result",
                    "content": str(action_item["result"]),
                    "metadata": {
                        "tool": action_item["tool"],
                        "status": "success" if action_item["result"].get("success", True) else "error",
                        "result": action_item["result"],
                    },
                }
            self.last_run_result = None
            yield {
                "kind": "text",
                "content": local_action["summary"],
                "metadata": {"source": "local-router"},
            }
            return

        sdk_context = self._build_context(context_dict)
        event_queue = queue.Queue()
        sentinel = object()
        state = {"error": None, "result": None}
        streamed_text = []
        captured_events = []

        def on_event(event):
            captured_events.append(event)
            event_queue.put(event)

        def runner():
            try:
                state["result"] = self.mtumishi.run_with_stream(
                    prompt,
                    on_event=on_event,
                    context_override=sdk_context,
                )
            except Exception as exc:
                state["error"] = exc
            finally:
                event_queue.put(sentinel)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()

        while True:
            event = event_queue.get()
            if event is sentinel:
                break

            event_type = getattr(event.type, "value", str(event.type))
            payload = {
                "kind": event_type,
                "content": self._sanitize_user_visible_text(getattr(event, "content", "") or ""),
                "metadata": getattr(event, "metadata", {}) or {},
            }
            yield payload
            if event_type == "text":
                if payload["content"]:
                    streamed_text.append(payload["content"])

        thread.join()
        self._update_runtime_status_from_events(captured_events)
        self.last_run_result = state["result"]

        if state["error"] is not None:
            yield {
                "kind": "error",
                "content": (
                    f"⚠️ Erreur lors du streaming de Mtumishi : {state['error']}\n\n"
                    f"Statut actuel : {self.get_status_message()}"
                ),
            }
            return

        if not streamed_text and self.last_run_result and getattr(self.last_run_result, "summary", None):
            yield {
                "kind": "text",
                "content": self.last_run_result.summary,
                "metadata": {"source": "final_summary"},
            }
