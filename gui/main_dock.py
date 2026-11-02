"""
Main DockWidget for GeoCongo AI QGIS Plugin.
Serves as the primary control panel docked inside QGIS workspace.
Includes Mtumishi Agentic Chatbot powered by live LLM (Gemini) and tabs for Pekua, Gundua, and Chimbua engines.
"""

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QPushButton, QLabel, QTextEdit, QMessageBox
)
from qgis.PyQt.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal

from .gundua_dialog import GunduaEngineDialog
from .drillhole_dialog import DrillholeAnalysisDialog
from .pekua_dialog import PekuaEngineDialog
from .settings_dialog import SettingsDialog
from ..utils.crs_utils import get_canvas_extent_wgs84, validate_wgs84_bbox
from ..utils.mtumishi_orchestrator import MtumishiOrchestrator


class ChatInputTextEdit(QTextEdit):
    """
    Multi-line chat input. Ctrl+Enter submits, Enter inserts a new line.
    """

    sendRequested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
            self.sendRequested.emit()
            return
        super().keyPressEvent(event)


class MtumishiResponseWorker(QObject):
    """
    Background worker for Mtumishi replies to keep the QGIS UI responsive.
    """

    eventReceived = pyqtSignal(dict)
    chunkReceived = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, orchestrator, message, context_dict):
        super().__init__()
        self.orchestrator = orchestrator
        self.message = message
        self.context_dict = context_dict

    def run(self):
        chunks = []
        try:
            for item in self.orchestrator.stream_reason_events(self.message, self.context_dict):
                if not item:
                    continue
                self.eventReceived.emit(item)
                if item.get("kind") == "text" and item.get("content"):
                    chunk = item["content"]
                    chunks.append(chunk)
                    self.chunkReceived.emit(chunk)
                elif item.get("kind") == "error" and item.get("content"):
                    chunks.append(item["content"])
            self.finished.emit("".join(chunks).strip())
        except Exception as exc:
            self.failed.emit(str(exc))


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

        self.orchestrator = MtumishiOrchestrator(self.iface)
        self._chat_blocks = []
        self._pending_assistant_text = ""
        self._pending_trace_lines = []
        self._active_assistant_block_index = None
        self._active_trace_block_index = None
        self._active_thread = None
        self._active_worker = None
        self._spinner_index = 0
        self._spinner_frames = ["|", "/", "-", "\\"]
        self._startup_diagnostic_logged = False
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(140)
        self._spinner_timer.timeout.connect(self._advance_spinner)
        self._init_ui()
        QTimer.singleShot(0, self._run_startup_diagnostic)

    def _apply_modern_ui_theme(self):
        """Applies a cleaner UI theme inspired by AI Agent while keeping QGIS light styling."""
        self.setStyleSheet(
            """
            QDockWidget {
                background: #f3f5f7;
                color: #1f2937;
                border: 1px solid #dfe7ee;
            }
            QWidget {
                background: #f3f5f7;
                color: #1f2937;
            }
            QTabWidget::pane {
                border: 1px solid #dfe7ee;
                border-radius: 10px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #edf2f5;
                color: #475569;
                border: 1px solid #dfe7ee;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 8px 14px;
                margin-right: 5px;
                min-height: 28px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f766e;
                border-color: #cfe4e2;
                font-weight: 600;
            }
            QGroupBox {
                border: 1px solid #dfe7ee;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background: #ffffff;
                color: #1f2937;
            }
            QGroupBox:title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #0f766e;
                font-weight: 600;
            }
            QLabel {
                color: #1f2937;
            }
            QPushButton {
                border: 1px solid #bdd6d3;
                border-radius: 8px;
                background: #eef9f7;
                color: #0f172a;
                padding: 7px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #e4f5f2;
                border-color: #86c0ba;
            }
            QPushButton:pressed {
                background: #d9f0ed;
            }
            QTextEdit, QPlainTextEdit {
                border: 1px solid #dfe7ee;
                border-radius: 12px;
                background: #ffffff;
                color: #1f2937;
                padding: 8px;
            }
            QScrollBar:vertical {
                background: #edf2f7;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #a8b7c7;
                border-radius: 5px;
            }
            """
        )
        self.txt_chat_history.setStyleSheet(
            """
            QTextEdit {
                background: #f9fbfc;
                border: 1px solid #dfe7ee;
                border-radius: 12px;
                padding: 12px;
                color: #1f2937;
            }
            """
        )
        self.txt_chat_input.setStyleSheet(
            """
            QTextEdit {
                background: #ffffff;
                border: 1px solid #cfe1e7;
                border-radius: 12px;
                padding: 10px 12px;
                color: #1f2937;
            }
            """
        )
        self.btn_send.setStyleSheet(
            """
            QPushButton {
                background: #0f766e;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0d6b66;
            }
            QPushButton:pressed {
                background: #0b5e5a;
            }
            """
        )
        self.lbl_streaming_status.setStyleSheet(
            "color: #0f766e; font-style: italic; background: transparent; padding: 4px 0;"
        )
        self.box_runtime_warning.setStyleSheet(
            "QGroupBox {"
            "border: 1px solid #f0b8a8;"
            "border-radius: 8px;"
            "margin-top: 8px;"
            "padding-top: 10px;"
            "background: #fff9f5;"
            "}"
            "QLabel { color: #7f1d1d; }"
        )

    def _init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header / brand bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        import os
        from qgis.PyQt.QtGui import QIcon, QPixmap
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(logo_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(lbl_logo)

        lbl_title = QLabel("<b>GeoCongo AI</b>")
        lbl_title.setStyleSheet("font-size: 14px; color: #0f172a; font-weight: 700;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        btn_settings = QPushButton("⚙️ Paramètres")
        btn_settings.setToolTip("Configurer les clés API et serveurs")
        btn_settings.clicked.connect(self.open_settings)
        header_layout.addWidget(btn_settings)

        layout.addLayout(header_layout)

        # Tabs section
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            """
        )

        tab_mtumishi = QWidget()
        layout_mtumishi = QVBoxLayout(tab_mtumishi)
        layout_mtumishi.setContentsMargins(0, 0, 0, 0)
        layout_mtumishi.setSpacing(8)

        box_mtumishi_desc = QGroupBox("🤖 Mtumishi - Assistant QGIS intelligent")
        box_mtumishi_desc_layout = QVBoxLayout(box_mtumishi_desc)
        lbl_mtu_desc = QLabel(
            "Mtumishi est votre assistant pour interagir avec GeoCongo AI, piloter QGIS "
            "et mobiliser Pekua (RAG), Gundua (télédétection) et Chimbua (3D) selon vos besoins."
        )
        lbl_mtu_desc.setWordWrap(True)
        box_mtumishi_desc_layout.addWidget(lbl_mtu_desc)
        layout_mtumishi.addWidget(box_mtumishi_desc)

        self.box_runtime_warning = QGroupBox("⚠️ Diagnostic runtime Mtumishi")
        self.box_runtime_warning.setVisible(False)
        runtime_warning_layout = QVBoxLayout(self.box_runtime_warning)

        self.lbl_runtime_warning = QLabel("")
        self.lbl_runtime_warning.setWordWrap(True)
        runtime_warning_layout.addWidget(self.lbl_runtime_warning)

        runtime_btn_layout = QHBoxLayout()
        self.btn_runtime_diagnose = QPushButton("Diagnostiquer")
        self.btn_runtime_repair = QPushButton("Réparer")
        self.btn_runtime_open_settings = QPushButton("Paramètres")
        self.btn_runtime_diagnose.clicked.connect(self._show_runtime_diagnostics)
        self.btn_runtime_repair.clicked.connect(self._repair_runtime_dependencies)
        self.btn_runtime_open_settings.clicked.connect(self.open_settings)
        runtime_btn_layout.addWidget(self.btn_runtime_diagnose)
        runtime_btn_layout.addWidget(self.btn_runtime_repair)
        runtime_btn_layout.addWidget(self.btn_runtime_open_settings)
        runtime_btn_layout.addStretch()
        runtime_warning_layout.addLayout(runtime_btn_layout)
        layout_mtumishi.addWidget(self.box_runtime_warning)

        self.txt_chat_history = QTextEdit()
        self.txt_chat_history.setReadOnly(True)
        self.txt_chat_history.setAcceptRichText(True)
        self._chat_blocks = [
            "🤖 Bonjour ! Je suis **Mtumishi**, votre assistant pour interagir avec le plugin **GeoCongo AI** et piloter **QGIS** plus facilement.\n\n"
            "Je peux vous aider pour les analyses géologiques, géospatiales et de forages, interroger les moteurs **Pekua**, **Gundua** et **Chimbua**, puis exécuter des actions utiles dans QGIS pour faciliter la cartographie.\n\n"
            "Dès que vos clés API sont configurées dans les Paramètres, je peux raisonner intelligemment sur vos données et vous assister directement dans ce logiciel.\n"
            "Posez-moi votre question ou demandez-moi une action dans QGIS.\n\n"
        ]
        self._render_chat_history()
        layout_mtumishi.addWidget(self.txt_chat_history)

        self.lbl_streaming_status = QLabel("")
        self.lbl_streaming_status.setVisible(False)
        layout_mtumishi.addWidget(self.lbl_streaming_status)

        chat_input_layout = QHBoxLayout()
        self.txt_chat_input = ChatInputTextEdit()
        self.txt_chat_input.setFixedHeight(72)
        self.txt_chat_input.setPlaceholderText("Posez une question à Mtumishi (ex: Analyse l'emprise pour le cuivre en RDC)...")
        self.txt_chat_input.sendRequested.connect(self.send_mtumishi_message)
        chat_input_layout.addWidget(self.txt_chat_input)

        self.btn_send = QPushButton("Envoyer")
        self.btn_send.clicked.connect(self.send_mtumishi_message)
        chat_input_layout.addWidget(self.btn_send)

        layout_mtumishi.addLayout(chat_input_layout)
        self.tabs.addTab(tab_mtumishi, "🤖 Mtumishi")

        tab_pekua = QWidget()
        layout_pekua = QVBoxLayout(tab_pekua)
        box_pekua = QGroupBox("🔍 Pekua Engine (Knowledge Base RAG)")
        box_pekua_layout = QVBoxLayout(box_pekua)
        lbl_pekua_desc = QLabel("Recherche documentaire et sémantique dans les rapports d'exploration et thèses géologiques.")
        lbl_pekua_desc.setWordWrap(True)
        box_pekua_layout.addWidget(lbl_pekua_desc)
        btn_open_pekua = QPushButton("Ouvrir la Boîte de Dialogue Pekua RAG")
        btn_open_pekua.clicked.connect(self.open_pekua_dialog)
        box_pekua_layout.addWidget(btn_open_pekua)
        layout_pekua.addWidget(box_pekua)
        layout_pekua.addStretch()
        self.tabs.addTab(tab_pekua, "🔍 Pekua")

        tab_gundua = QWidget()
        layout_gundua = QVBoxLayout(tab_gundua)
        box_gundua = QGroupBox("🛰️ Gundua Engine API")
        box_gundua_layout = QVBoxLayout(box_gundua)
        lbl_gundua_desc = QLabel("Télédétection et prédiction des anomalies géologiques via l'API Gundua.")
        lbl_gundua_desc.setWordWrap(True)
        box_gundua_layout.addWidget(lbl_gundua_desc)
        btn_open_gundua = QPushButton("Lancer l'analyse Greenfield (BBOX Dynamique)")
        btn_open_gundua.clicked.connect(self.open_gundua_dialog)
        box_gundua_layout.addWidget(btn_open_gundua)
        layout_gundua.addWidget(box_gundua)

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

        tab_drill = QWidget()
        layout_drill = QVBoxLayout(tab_drill)
        box_drill = QGroupBox("⛏️ Chimbua Engine (Forages & Géochimie 3D)")
        box_drill_layout = QVBoxLayout(box_drill)
        lbl_drill_desc = QLabel("Clustering spatial DBSCAN et filtrage par seuil de teneur sur données de forages 3D.")
        lbl_drill_desc.setWordWrap(True)
        box_drill_layout.addWidget(lbl_drill_desc)
        btn_open_drill = QPushButton("Ouvrir l'analyseur Chimbua 3D")
        btn_open_drill.clicked.connect(self.open_drillhole_dialog)
        box_drill_layout.addWidget(btn_open_drill)
        layout_drill.addWidget(box_drill)
        layout_drill.addStretch()
        self.tabs.addTab(tab_drill, "⛏️ Chimbua")

        layout.addWidget(self.tabs)
        self.setWidget(main_widget)
        self._apply_modern_ui_theme()

        # Update initial bbox preview
        self.update_bbox_preview()

        # Connect canvas navigation signals
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().extentsChanged.connect(self.update_bbox_preview)

    def _format_dependency_diagnostics(self, diagnostics: dict) -> str:
        return (
            f"Python QGIS détecté : {diagnostics.get('python_executable', 'inconnu')}\n"
            f"Moteur conversationnel disponible : {diagnostics.get('antigravity_available')}\n"
            f"Version du moteur conversationnel : {diagnostics.get('antigravity_version', 'inconnue')}\n"
            f"Version protobuf : {diagnostics.get('protobuf_version', 'inconnue')}\n\n"
            f"Diagnostic :\n{diagnostics.get('resolution_hint', 'Aucun diagnostic')}"
        )

    def _refresh_runtime_banner(self, log_to_chat: bool = False):
        diagnostics = self.orchestrator.get_dependency_diagnostics()
        gemini_present = diagnostics.get("gemini_key_present")
        antigravity_ready = diagnostics.get("antigravity_available")

        should_warn = bool(gemini_present and not antigravity_ready)
        self.box_runtime_warning.setVisible(should_warn)

        if should_warn:
            self.lbl_runtime_warning.setText(
                "Mtumishi est configuré avec une clé Gemini, mais le moteur conversationnel "
                "avancé n'est pas prêt dans ce Python QGIS.\n\n"
                f"{diagnostics.get('resolution_hint', '')}"
            )
            if log_to_chat and not self._startup_diagnostic_logged:
                self._append_chat_block(
                    "⚠️ **Diagnostic automatique Mtumishi** : "
                    f"{diagnostics.get('resolution_hint', 'Le moteur conversationnel avancé est indisponible.')}\n"
                    "Utilisez **Réparer** dans l'onglet Mtumishi ou dans les Paramètres."
                )
                self._startup_diagnostic_logged = True
        else:
            self.lbl_runtime_warning.setText("")
            if gemini_present and antigravity_ready and log_to_chat and not self._startup_diagnostic_logged:
                self._append_chat_block(
                    "✅ **Diagnostic automatique Mtumishi** : le moteur conversationnel avancé est prêt dans QGIS."
                )
                self._startup_diagnostic_logged = True

    def _run_startup_diagnostic(self):
        self.orchestrator.reload_keys(force=True)
        self._refresh_runtime_banner(log_to_chat=True)

    def _show_runtime_diagnostics(self):
        diagnostics = self.orchestrator.get_dependency_diagnostics()
        QMessageBox.information(
            self,
            "GeoCongo AI - Diagnostic Mtumishi",
            self._format_dependency_diagnostics(diagnostics),
        )

    def _repair_runtime_dependencies(self):
        answer = QMessageBox.question(
            self,
            "GeoCongo AI - Réparer Mtumishi",
            "Le plugin va installer ou mettre à jour automatiquement les dépendances "
            "Mtumishi dans le Python utilisé par QGIS. Voulez-vous continuer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return

        self.btn_runtime_repair.setEnabled(False)
        self.lbl_streaming_status.setVisible(True)
        self.lbl_streaming_status.setText("Réparation Mtumishi en cours...")
        result = self.orchestrator.repair_antigravity_dependencies()
        self.btn_runtime_repair.setEnabled(True)
        self.lbl_streaming_status.setVisible(False)
        self.lbl_streaming_status.setText("")
        self._refresh_runtime_banner(log_to_chat=False)

        diagnostics = result.get("diagnostics", {})
        if result.get("success"):
            self._append_chat_block(
                "✅ **Réparation Mtumishi** : dépendances mises à jour. "
                "Redémarrez QGIS pour garantir la prise en compte complète des nouveaux paquets."
            )
            QMessageBox.information(
                self,
                "GeoCongo AI - Réparation terminée",
                "Les dépendances Mtumishi ont été installées ou mises à jour avec succès.\n\n"
                f"{self._format_dependency_diagnostics(diagnostics)}\n\n"
                "Redémarrez QGIS pour garantir la prise en compte complète des nouveaux paquets.",
            )
            return

        QMessageBox.critical(
            self,
            "GeoCongo AI - Réparation échouée",
            "La réparation automatique n'a pas abouti.\n\n"
            f"{self._format_dependency_diagnostics(diagnostics)}\n\n"
            f"STDERR :\n{result.get('stderr', '')}\n\n"
            f"STDOUT :\n{result.get('stdout', '')}",
        )

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

    def _render_chat_history(self):
        style = """
        <style>
            body { font-family: sans-serif; background: #f3f5f7; color: #1f2937; }
            .geo-bubble {
                border-radius: 14px;
                padding: 12px 14px;
                margin: 10px 0;
                border: 1px solid #dfe7ee;
                background: #ffffff;
                box-shadow: 0 1px 0 rgba(15, 23, 42, 0.03);
            }
            .geo-bubble.user {
                background: #eaf6f4;
                border-color: #cfe5e2;
                margin-left: 40px;
            }
            .geo-bubble.assistant {
                background: #f7f9fb;
                border-color: #e2e8f0;
                margin-right: 40px;
            }
            .geo-bubble.trace {
                background: #f3f8ff;
                border-color: #d9e7f7;
                margin-right: 40px;
            }
            .geo-title {
                font-size: 12px;
                font-weight: 700;
                color: #0f766e;
                margin-bottom: 8px;
            }
            .geo-body {
                font-size: 13px;
                line-height: 1.5;
                color: #1f2937;
            }
            b { color: #0f172a; }
            i { color: #475569; }
        </style>
        """

        html_blocks = []
        for block in (self._chat_blocks or []):
            if not block:
                continue
            text = str(block)
            if text.startswith("👤 **Vous**"):
                body = text.split(":", 1)[1].strip() if ":" in text else text
                html_blocks.append(self._bubble_html("user", "Vous", body))
            elif text.startswith("🤖 **Mtumishi"):
                body = text.split(":", 1)[1].strip() if ":" in text else text
                html_blocks.append(self._bubble_html("assistant", "Mtumishi", body))
            elif text.startswith("🧠 **Ce que fait Mtumishi"):
                body = text.split("**Ce que fait Mtumishi en coulisse**", 1)[1].strip() if "**Ce que fait Mtumishi en coulisse**" in text else text
                html_blocks.append(self._bubble_html("trace", "Ce que fait Mtumishi", body))
            else:
                html_blocks.append(self._bubble_html("assistant", "Mtumishi", text))

        self.txt_chat_history.setHtml(style + "".join(html_blocks))
        scrollbar = self.txt_chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _bubble_html(self, role: str, title: str, body: str) -> str:
        cleaned = body.strip()
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = self._format_chat_html(cleaned)
        return (
            f'<div class="geo-bubble {role}">'
            f'<div class="geo-title">{title}</div>'
            f'<div class="geo-body">{cleaned}</div>'
            f'</div>'
        )

    def _format_chat_html(self, text: str) -> str:
        escaped = re.sub(r"\n+", "<br>", text)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
        return escaped

    def _append_chat_block(self, markdown_text: str):
        self._chat_blocks.append(markdown_text)
        self._render_chat_history()
        return len(self._chat_blocks) - 1

    def _build_user_block(self, message: str) -> str:
        return f"👤 **Vous** :\n\n{message}"

    def _build_assistant_block(self, message: str) -> str:
        return f"🤖 **Mtumishi (Assistant QGIS)** :\n\n{message}"

    def _build_trace_block(self) -> str:
        if not self._pending_trace_lines:
            return "🧠 **Ce que fait Mtumishi en coulisse**\n\n_En attente d'événements d'outils..._"
        body = "\n".join(f"- {line}" for line in self._pending_trace_lines)
        return f"🧠 **Ce que fait Mtumishi en coulisse**\n\n{body}"

    def _replace_chat_block(self, index: int, markdown_text: str):
        if index is None:
            return self._append_chat_block(markdown_text)
        if 0 <= index < len(self._chat_blocks):
            self._chat_blocks[index] = markdown_text
        else:
            while len(self._chat_blocks) < index:
                self._chat_blocks.append("")
            if len(self._chat_blocks) == index:
                self._chat_blocks.append(markdown_text)
            else:
                self._chat_blocks[index] = markdown_text
        self._render_chat_history()
        return index

    def _set_busy_state(self, busy: bool):
        self.btn_send.setEnabled(not busy)
        self.txt_chat_input.setReadOnly(busy)
        self.txt_chat_input.setEnabled(True)
        if busy:
            self._spinner_index = 0
            self.lbl_streaming_status.setVisible(True)
            self._advance_spinner()
            self._spinner_timer.start()
        else:
            self._spinner_timer.stop()
            self.lbl_streaming_status.setVisible(False)
            self.lbl_streaming_status.setText("")

    def _advance_spinner(self):
        frame = self._spinner_frames[self._spinner_index % len(self._spinner_frames)]
        self.lbl_streaming_status.setText(f"Mtumishi réfléchit {frame}")
        self._spinner_index += 1

    def _build_user_block(self, message: str) -> str:
        return f"👤 **Vous** :\n\n{message}"

    def _build_assistant_block(self, message: str) -> str:
        return f"🤖 **Mtumishi (Assistant QGIS)** :\n\n{message}"

    def _build_trace_block(self) -> str:
        if not self._pending_trace_lines:
            return "🧠 **Ce que fait Mtumishi en coulisse**\n\n_En attente d'événements d'outils..._"
        body = "\n".join(f"- {line}" for line in self._pending_trace_lines)
        return f"🧠 **Ce que fait Mtumishi en coulisse**\n\n{body}"

    def _format_trace_event(self, item: dict) -> str:
        kind = item.get("kind")
        content = (item.get("content") or "").strip()
        metadata = item.get("metadata") or {}

        if kind == "status":
            return f"`status` *{content}*"
        if kind == "thought":
            return f"`thought` *{content}*"
        if kind == "tool_call":
            tool_name = metadata.get("tool", "outil")
            args = metadata.get("args") or metadata.get("arguments") or {}
            return f"`tool_call` ***{tool_name}*** avec *`{args}`*"
        if kind == "tool_result":
            tool_name = metadata.get("tool", "outil")
            status = metadata.get("status", "success")
            result = metadata.get("result")
            result_str = str(result)
            if len(result_str) > 220:
                result_str = result_str[:217] + "..."
            return f"`tool_result` ***{tool_name}*** *[{status}]* *`{result_str}`*"
        if kind == "error":
            return f"`error` *{content}*"
        if kind == "text":
            return None
        return f"`{kind}` *{content}*" if content else None

    def _start_mtumishi_response(self, message: str, context_dict: dict):
        self._pending_assistant_text = ""
        self._pending_trace_lines = []
        self._active_trace_block_index = self._append_chat_block(self._build_trace_block())
        self._active_assistant_block_index = self._append_chat_block(
            self._build_assistant_block("_Mtumishi réfléchit..._")
        )
        self._set_busy_state(True)

        self._active_thread = QThread(self)
        self._active_worker = MtumishiResponseWorker(self.orchestrator, message, context_dict)
        self._active_worker.moveToThread(self._active_thread)

        self._active_thread.started.connect(self._active_worker.run)
        self._active_worker.eventReceived.connect(self._on_mtumishi_event)
        self._active_worker.chunkReceived.connect(self._on_mtumishi_chunk)
        self._active_worker.finished.connect(self._on_mtumishi_finished)
        self._active_worker.failed.connect(self._on_mtumishi_failed)
        self._active_worker.finished.connect(self._teardown_worker)
        self._active_worker.failed.connect(self._teardown_worker)
        self._active_thread.start()

    def _teardown_worker(self, *_args):
        if self._active_thread:
            self._active_thread.quit()
            self._active_thread.wait()
            self._active_thread.deleteLater()
            self._active_thread = None
        if self._active_worker:
            self._active_worker.deleteLater()
            self._active_worker = None
        self._active_assistant_block_index = None
        self._active_trace_block_index = None

    def _on_mtumishi_event(self, item: dict):
        line = self._format_trace_event(item)
        if not line:
            return
        self._pending_trace_lines.append(line)
        self._replace_chat_block(self._active_trace_block_index, self._build_trace_block())

    def _on_mtumishi_chunk(self, chunk: str):
        self._pending_assistant_text += chunk
        self._replace_chat_block(
            self._active_assistant_block_index,
            self._build_assistant_block(self._pending_assistant_text),
        )

    def _on_mtumishi_finished(self, final_text: str):
        self._set_busy_state(False)
        rendered_text = final_text or self._pending_assistant_text or "_Aucune réponse renvoyée._"
        self._replace_chat_block(
            self._active_assistant_block_index,
            self._build_assistant_block(rendered_text),
        )
        self._replace_chat_block(self._active_trace_block_index, self._build_trace_block())

    def _on_mtumishi_failed(self, error_message: str):
        self._set_busy_state(False)
        self._pending_trace_lines.append(f"`error` {error_message}")
        self._replace_chat_block(self._active_trace_block_index, self._build_trace_block())
        self._replace_chat_block(
            self._active_assistant_block_index,
            self._build_assistant_block(
                f"⚠️ **Erreur de streaming Mtumishi** : {error_message}\n\n"
                "Veuillez réessayer ou vérifier la connectivité du fournisseur IA."
            )
        )

    def send_mtumishi_message(self):
        if self._active_thread:
            QMessageBox.information(
                self,
                "Mtumishi occupé",
                "Mtumishi est déjà en train de répondre. Attendez la fin du streaming avant d'envoyer un nouveau message."
            )
            return

        msg = self.txt_chat_input.toPlainText().strip()
        if not msg:
            return

        self._append_chat_block(self._build_user_block(msg))
        self.txt_chat_input.clear()

        # Gather geospatial context
        bbox = get_canvas_extent_wgs84(self.iface)
        active_layer = self.iface.activeLayer() if hasattr(self.iface, "activeLayer") else None
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs().authid() if hasattr(self.iface, "mapCanvas") else "EPSG:4326"
        context_dict = {
            "bbox": bbox,
            "crs": canvas_crs or "EPSG:4326",
            "province": None,
            "active_layer": active_layer.name() if active_layer else "Aucune couche active",
            "metadata": {
                "plugin": "GeoCongo AI QGIS",
                "bbox_is_valid": validate_wgs84_bbox(bbox)[0],
            },
        }

        self._start_mtumishi_response(msg, context_dict)

    def log(self, message: str):
        self._append_chat_block(f"`[LOG] {message}`")

    def open_pekua_dialog(self):
        dlg = PekuaEngineDialog(self.iface, self)
        dlg.exec_()

    def open_gundua_dialog(self):
        dlg = GunduaEngineDialog(self.iface, self)
        dlg.exec_()

    def open_drillhole_dialog(self):
        try:
            dlg = DrillholeAnalysisDialog(self.iface, self)
            dlg.exec_()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "GeoCongo AI - Chimbua",
                f"Impossible d'ouvrir l'analyseur Chimbua 3D :\n{exc}",
            )

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()
        # Reload orchestrator keys after settings change
        if hasattr(self, "orchestrator"):
            self.orchestrator.reload_keys()
            self._refresh_runtime_banner(log_to_chat=False)
            if self.orchestrator.is_gemini_active():
                self._append_chat_block(
                    "✅ **Système** : "
                    f"{self.orchestrator.get_status_message()} "
                    "Mtumishi conserve maintenant une vraie session de conversation.\n"
                )
            else:
                self._append_chat_block(
                    "ℹ️ **Système** : "
                    f"{self.orchestrator.get_status_message()} "
                    "Mtumishi fonctionne en mode heuristique local.\n"
                )
