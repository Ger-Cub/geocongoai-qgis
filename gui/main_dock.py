"""
Main DockWidget for GeoCongo AI QGIS Plugin.
Serves as the primary control panel docked inside QGIS workspace.
Includes Mtumishi Agentic Chatbot powered by live LLM (Gemini) and tabs for Pekua, Gundua, and Chimbua engines.
"""

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QPushButton, QLabel, QTextEdit, QLineEdit, QMessageBox
)
from qgis.PyQt.QtCore import Qt

from .gundua_dialog import GunduaEngineDialog
from .drillhole_dialog import DrillholeAnalysisDialog
from .pekua_dialog import PekuaEngineDialog
from .settings_dialog import SettingsDialog
from ..utils.crs_utils import get_canvas_extent_wgs84, validate_wgs84_bbox
from ..utils.mtumishi_orchestrator import MtumishiOrchestrator


class GeoCongoAIDockWidget(QDockWidget):
    """
    Main Dock Widget for GeoCongo AI plugin in QGIS.
    Features Mtumishi Agentic Chatbot as default tab and dedicated tabs for SDK v0.4.3 engines.
    """

    def __init__(self, iface, parent=None):
        super().__init__("GeoCongo AI", parent or iface.mainWindow())
        self.iface = iface
        self.setObjectName("GeoCongoAIDockWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.orchestrator = MtumishiOrchestrator()
        self._init_ui()

    def _init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Title / Brand Header
        header_layout = QHBoxLayout()
        
        import os
        from qgis.PyQt.QtGui import QIcon, QPixmap
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(logo_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(lbl_logo)

        lbl_title = QLabel("<b>GeoCongo AI</b>")
        lbl_title.setStyleSheet("font-size: 14px; color: #1b5e20;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        btn_settings = QPushButton("⚙️ Paramètres")
        btn_settings.setToolTip("Configurer les clés API et serveurs")
        btn_settings.clicked.connect(self.open_settings)
        header_layout.addWidget(btn_settings)

        layout.addLayout(header_layout)

        # Tab Widget for Modules (Default tab: Mtumishi Agentic Assistant)
        self.tabs = QTabWidget()

        # Tab 1: 🤖 Mtumishi Agentic Chatbot
        tab_mtumishi = QWidget()
        layout_mtumishi = QVBoxLayout(tab_mtumishi)

        box_mtumishi_desc = QGroupBox("🤖 Mtumishi - Assistant Agentic QGIS (LLM Gemini Connecté)")
        box_mtumishi_desc_layout = QVBoxLayout(box_mtumishi_desc)
        lbl_mtu_desc = QLabel(
            "Orchestrateur agentique intelligent connectant vos requêtes textuelles "
            "aux moteurs Pekua (RAG), Gundua (Télédétection) et Chimbua (3D) via Google Gemini."
        )
        lbl_mtu_desc.setWordWrap(True)
        box_mtumishi_desc_layout.addWidget(lbl_mtu_desc)
        layout_mtumishi.addWidget(box_mtumishi_desc)

        # Chat history area
        self.txt_chat_history = QTextEdit()
        self.txt_chat_history.setReadOnly(True)
        self.txt_chat_history.setText(
            "🤖 Bonjour ! Je suis Mtumishi AI. Je peux vous aider à analyser les données géologiques, geospatiales et de forages.\n"
            "Je peux interroger les moteurs Pekua, Gundua et Chimbua de GeoCongo AI pour vous fournir des analyses complexes en télédection, géologie et et modélisation 3D.\n\n"
            "Je peux également piloter ce logiciel (QGIS) en exécutant des commandes QGIS via des scripts Python (PyQGIS).\n\n"
            "Dès que vos clés API sont configurées dans les Paramètres, je peux raisonner intelligemment et prendre le controle de ce logiciel.\n"
            "Posez-moi vos questions géologiques ou demandez-moi d'analyser l'emprise QGIS courante.\n\n"
        )
        layout_mtumishi.addWidget(self.txt_chat_history)

        # Chat input area
        chat_input_layout = QHBoxLayout()
        self.txt_chat_input = QLineEdit()
        self.txt_chat_input.setPlaceholderText("Posez une question à Mtumishi (ex: Analyse l'emprise pour le cuivre en RDC)...")
        self.txt_chat_input.returnPressed.connect(self.send_mtumishi_message)
        chat_input_layout.addWidget(self.txt_chat_input)

        btn_send = QPushButton("Envoyer")
        btn_send.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white;")
        btn_send.clicked.connect(self.send_mtumishi_message)
        chat_input_layout.addWidget(btn_send)

        layout_mtumishi.addLayout(chat_input_layout)
        self.tabs.addTab(tab_mtumishi, "🤖 Mtumishi")

        # Tab 2: 🔍 Pekua Engine (Recherche Documentaire)
        tab_pekua = QWidget()
        layout_pekua = QVBoxLayout(tab_pekua)

        box_pekua = QGroupBox("🔍 Pekua Engine (Knowledge Base RAG)")
        box_pekua_layout = QVBoxLayout(box_pekua)
        lbl_pekua_desc = QLabel("Recherche documentaire et sémantique dans les rapports d'exploration et thèses géologiques.")
        lbl_pekua_desc.setWordWrap(True)
        box_pekua_layout.addWidget(lbl_pekua_desc)

        btn_open_pekua = QPushButton("Ouvrir la Boîte de Dialogue Pekua RAG")
        btn_open_pekua.setStyleSheet("font-weight: bold; background-color: #1976d2; color: white; padding: 8px;")
        btn_open_pekua.clicked.connect(self.open_pekua_dialog)
        box_pekua_layout.addWidget(btn_open_pekua)
        layout_pekua.addWidget(box_pekua)
        layout_pekua.addStretch()
        self.tabs.addTab(tab_pekua, "🔍 Pekua")

        # Tab 3: 🛰️ Gundua Engine & Greenfield
        tab_gundua = QWidget()
        layout_gundua = QVBoxLayout(tab_gundua)

        box_gundua = QGroupBox("🛰️ Gundua Engine API")
        box_gundua_layout = QVBoxLayout(box_gundua)
        lbl_gundua_desc = QLabel("Télédétection et prédiction des anomalies géologiques via l'API Gundua.")
        lbl_gundua_desc.setWordWrap(True)
        box_gundua_layout.addWidget(lbl_gundua_desc)

        btn_open_gundua = QPushButton("Lancer l'analyse Greenfield (BBOX Dynamique)")
        btn_open_gundua.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white; padding: 8px;")
        btn_open_gundua.clicked.connect(self.open_gundua_dialog)
        box_gundua_layout.addWidget(btn_open_gundua)
        layout_gundua.addWidget(box_gundua)

        # BBOX Dynamic Status Preview Box
        box_bbox = QGroupBox("📍 Emprise Carte Courante (WGS84)")
        box_bbox_layout = QVBoxLayout(box_bbox)
        self.lbl_bbox_preview = QLabel("Calcul de l'emprise...")
        self.lbl_bbox_preview.setStyleSheet("font-family: monospace; color: #333;")
        box_bbox_layout.addWidget(self.lbl_bbox_preview)

        btn_refresh_bbox = QPushButton("🔄 Actualiser Emprise")
        btn_refresh_bbox.clicked.connect(self.update_bbox_preview)
        box_bbox_layout.addWidget(btn_refresh_bbox)
        layout_gundua.addWidget(box_bbox)
        layout_gundua.addStretch()
        self.tabs.addTab(tab_gundua, "🛰️ Gundua")

        # Tab 4: ⛏️ Chimbua Engine (Forages & 3D)
        tab_drill = QWidget()
        layout_drill = QVBoxLayout(tab_drill)

        box_drill = QGroupBox("⛏️ Chimbua Engine (Forages & Géochimie 3D)")
        box_drill_layout = QVBoxLayout(box_drill)
        lbl_drill_desc = QLabel("Clustering spatial DBSCAN et filtrage par seuil de teneur sur données de forages 3D.")
        lbl_drill_desc.setWordWrap(True)
        box_drill_layout.addWidget(lbl_drill_desc)

        btn_open_drill = QPushButton("Ouvrir l'analyseur Chimbua 3D")
        btn_open_drill.setStyleSheet("font-weight: bold; background-color: #f57c00; color: white; padding: 8px;")
        btn_open_drill.clicked.connect(self.open_drillhole_dialog)
        box_drill_layout.addWidget(btn_open_drill)
        layout_drill.addWidget(box_drill)
        layout_drill.addStretch()
        self.tabs.addTab(tab_drill, "⛏️ Chimbua")

        layout.addWidget(self.tabs)
        self.setWidget(main_widget)

        # Update initial bbox preview
        self.update_bbox_preview()

        # Connect canvas navigation signals
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().extentsChanged.connect(self.update_bbox_preview)

    def update_bbox_preview(self):
        try:
            bbox = get_canvas_extent_wgs84(self.iface)
            is_valid, msg = validate_wgs84_bbox(bbox)
            text = (
                f"XMin (Lon): {bbox[0]}\n"
                f"YMin (Lat): {bbox[1]}\n"
                f"XMax (Lon): {bbox[2]}\n"
                f"YMax (Lat): {bbox[3]}"
            )
            if not is_valid:
                text += f"\n\n⚠️ Coordonnées non-WGS84 (métriques)\nOuvrez une boîte de dialogue pour spécifier le CRS source."
            self.lbl_bbox_preview.setText(text)
        except Exception as e:
            self.lbl_bbox_preview.setText(f"Erreur d'emprise: {e}")

    def send_mtumishi_message(self):
        msg = self.txt_chat_input.text().strip()
        if not msg:
            return

        self.txt_chat_history.append(f"👤 **Vous** : {msg}")
        self.txt_chat_input.clear()

        # Gather geospatial context
        bbox = get_canvas_extent_wgs84(self.iface)
        context_dict = {
            "bbox": bbox,
            "crs": "EPSG:4326",
            "province": "Katanga / Lualaba / RDC",
            "active_layer": "Carte active QGIS"
        }

        # Invoke Mtumishi Orchestrator (live LLM reasoning if Gemini key is set)
        response_text = self.orchestrator.reason(msg, context_dict)
        self.txt_chat_history.append(f"🤖 **Mtumishi (Orchestrateur)** :\n{response_text}\n")

    def log(self, message: str):
        self.txt_chat_history.append(f"[LOG] {message}")

    def open_pekua_dialog(self):
        dlg = PekuaEngineDialog(self.iface, self)
        dlg.exec_()

    def open_gundua_dialog(self):
        dlg = GunduaEngineDialog(self.iface, self)
        dlg.exec_()

    def open_drillhole_dialog(self):
        dlg = DrillholeAnalysisDialog(self.iface, self)
        dlg.exec_()

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()
        # Reload orchestrator keys after settings change
        if hasattr(self, "orchestrator"):
            self.orchestrator.reload_keys()
            if self.orchestrator.is_gemini_active():
                self.txt_chat_history.append("✅ **Système** : Clé API Google Gemini détectée et activée ! Mtumishi raisonne désormais en temps réel avec le LLM Gemini.\n")
            else:
                self.txt_chat_history.append("ℹ️ **Système** : Aucune clé Gemini valide détectée. Mtumishi fonctionne en mode heuristique local.\n")
