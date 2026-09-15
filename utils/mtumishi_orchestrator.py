"""
Mtumishi orchestrator backed by the official GeoCongo AI SDK.
"""

import contextlib
import io
import importlib.metadata as importlib_metadata
import os
import queue
import re
import subprocess
import sys
import threading

from qgis.PyQt.QtCore import QCoreApplication, QObject, QSettings, Qt, QThread, pyqtSignal, pyqtSlot


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

    DEFAULT_SERVER_URL = "http://137.184.96.142:8000"
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
        loaded_gemini_key = settings.value("api_keys/gemini", "")
        loaded_geocongo_key = settings.value("api_keys/geocongo", "")
        loaded_server_url = settings.value("server/url", self.DEFAULT_SERVER_URL)
        loaded_preferred_model = settings.value("llm/gemini_model", "")

        self.gemini_key = (loaded_gemini_key if gemini_key is None else gemini_key or "").strip()
        self.geocongo_key = (loaded_geocongo_key if geocongo_key is None else geocongo_key or "").strip()
        self.server_url = (loaded_server_url if server_url is None else server_url or self.DEFAULT_SERVER_URL).strip()
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

    def _extract_layer_name_from_prompt(self, prompt: str):
        patterns = [
            r"couche raster\s+([^\n,.]+)",
            r"couche\s*:\s*([^\n,]+)",
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

    def _detect_local_action(self, prompt: str):
        text = prompt.lower()

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

    def _run_local_action(self, prompt: str):
        action = self._detect_local_action(prompt)
        if not action:
            return None

        tool_name = action["tool"]
        args = action["args"]
        summary_builder = action["summary_builder"]

        if tool_name == "qgis_apply_raster_symbology":
            result = self._apply_raster_symbology(**args)
        elif tool_name == "qgis_remove_layer":
            result = self._remove_layer(**args)
        elif tool_name == "qgis_execute_python_script":
            result = self._execute_qgis_python_script(**args)
        else:
            raise ValueError(f"Outil local non pris en charge: {tool_name}")

        summary = summary_builder(result, args)
        return {
            "tool": tool_name,
            "args": args,
            "result": result,
            "summary": summary,
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
            yield {
                "kind": "tool_call",
                "content": f"Lancement de l'outil local {local_action['tool']}",
                "metadata": {"tool": local_action["tool"], "args": local_action["args"]},
            }
            yield {
                "kind": "tool_result",
                "content": str(local_action["result"]),
                "metadata": {
                    "tool": local_action["tool"],
                    "status": "success" if local_action["result"].get("success", True) else "error",
                    "result": local_action["result"],
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
