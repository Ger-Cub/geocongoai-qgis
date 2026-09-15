"""
Settings and API Key configuration dialog for GeoCongo AI.
"""

import textwrap

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLineEdit, QLabel, QPushButton, QMessageBox, QGridLayout
)
from qgis.PyQt.QtCore import Qt, QSettings, QUrl
from qgis.PyQt.QtGui import QDesktopServices

from geocongoai.gundua_engine import GunduaEngineClient
from ..utils.mtumishi_orchestrator import MtumishiOrchestrator


class SettingsDialog(QDialog):
    """
    Configuration dialog for GeoCongo AI server endpoints and API keys (Gemini & GeoCongo AI).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoCongo AI - Paramètres & Clés API")
        self.resize(520, 480)
        
        import os
        from qgis.PyQt.QtGui import QIcon
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 1. API Keys Group (Gemini & GeoCongo AI)
        group_keys = QGroupBox("🔑 Clés API & Fournisseurs")
        grid_keys = QGridLayout(group_keys)

        # Gemini API Key
        grid_keys.addWidget(QLabel("Clé API Google Gemini :"), 0, 0)
        self.txt_gemini_key = QLineEdit()
        self.txt_gemini_key.setEchoMode(QLineEdit.Password)
        self.txt_gemini_key.setPlaceholderText("AIzaSy...")
        grid_keys.addWidget(self.txt_gemini_key, 0, 1)

        btn_gemini_link = QPushButton("Obtenir une clé Gemini")
        btn_gemini_link.setToolTip("Ouvrir Google AI Studio pour générer une clé API Gemini")
        btn_gemini_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://aistudio.google.com/app/apikey")))
        grid_keys.addWidget(btn_gemini_link, 0, 2)

        # GeoCongo AI API Key
        grid_keys.addWidget(QLabel("Clé API GeoCongo AI :"), 1, 0)
        self.txt_geocongo_key = QLineEdit()
        self.txt_geocongo_key.setEchoMode(QLineEdit.Password)
        self.txt_geocongo_key.setPlaceholderText("gc_live_...")
        grid_keys.addWidget(self.txt_geocongo_key, 1, 1)

        btn_geocongo_link = QPushButton("Obtenir une clé GeoCongo")
        btn_geocongo_link.setToolTip("Ouvrir le portail GeoCongo AI pour demander ou retrouver votre clé API")
        btn_geocongo_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://geocongoai.com/api-keys")) )
        grid_keys.addWidget(btn_geocongo_link, 1, 2)

        grid_keys.addWidget(QLabel("Modele Gemini (optionnel) :"), 2, 0)
        self.txt_gemini_model = QLineEdit()
        self.txt_gemini_model.setPlaceholderText("Laisser vide pour detection automatique")
        grid_keys.addWidget(self.txt_gemini_model, 2, 1, 1, 2)

        layout.addWidget(group_keys)

        # 2. Server Settings Group
        group_server = QGroupBox("🌐 Connexion Serveur & Gundua Engine")
        layout_server = QVBoxLayout(group_server)

        layout_server.addWidget(QLabel("URL du serveur Gundua Engine / Pekua API :"))
        self.txt_url = QLineEdit("http://137.184.96.142:8000")
        layout_server.addWidget(self.txt_url)

        self.btn_test = QPushButton("🧪 Tester la connexion au SDK")
        layout_server.addWidget(self.btn_test)

        repair_layout = QHBoxLayout()
        self.btn_diagnose_mtumishi = QPushButton("🔎 Diagnostiquer Mtumishi")
        self.btn_repair_mtumishi = QPushButton("🩹 Réparer Mtumishi")
        repair_layout.addWidget(self.btn_diagnose_mtumishi)
        repair_layout.addWidget(self.btn_repair_mtumishi)
        layout_server.addLayout(repair_layout)

        layout.addWidget(group_server)

        # Status Label
        self.lbl_status = QLabel("Statut : Prêt.")
        layout.addWidget(self.lbl_status)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white;")
        self.btn_close = QPushButton("Annuler")

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        # Signals
        self.btn_test.clicked.connect(self.test_connection)
        self.btn_diagnose_mtumishi.clicked.connect(self.diagnose_mtumishi)
        self.btn_repair_mtumishi.clicked.connect(self.repair_mtumishi)
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_close.clicked.connect(self.reject)

    def _build_orchestrator_from_form(self):
        orchestrator = MtumishiOrchestrator()
        orchestrator.reload_keys(
            force=True,
            gemini_key=self.txt_gemini_key.text().strip(),
            geocongo_key=self.txt_geocongo_key.text().strip(),
            server_url=self.txt_url.text().strip(),
            preferred_model=self.txt_gemini_model.text().strip(),
        )
        return orchestrator

    def _format_diagnostics_text(self, diagnostics: dict) -> str:
        packages = ", ".join(diagnostics.get("recommended_packages", []))
        return textwrap.dedent(
            f"""
            Python QGIS détecté : {diagnostics.get("python_executable", "inconnu")}
            Moteur conversationnel disponible : {diagnostics.get("antigravity_available")}
            Version du moteur conversationnel : {diagnostics.get("antigravity_version", "inconnue")}
            Version protobuf : {diagnostics.get("protobuf_version", "inconnue")}
            Clé Gemini présente : {diagnostics.get("gemini_key_present")}
            Clé GeoCongo AI présente : {diagnostics.get("geocongo_key_present")}

            Diagnostic :
            {diagnostics.get("resolution_hint", "Aucun diagnostic")}

            Paquets recommandés :
            {packages}
            """
        ).strip()

    def _load_settings(self):
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        self.txt_gemini_key.setText(settings.value("api_keys/gemini", ""))
        self.txt_geocongo_key.setText(settings.value("api_keys/geocongo", ""))
        self.txt_gemini_model.setText(settings.value("llm/gemini_model", ""))
        self.txt_url.setText(settings.value("server/url", "http://137.184.96.142:8000"))

    def save_settings(self):
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        settings.setValue("api_keys/gemini", self.txt_gemini_key.text().strip())
        settings.setValue("api_keys/geocongo", self.txt_geocongo_key.text().strip())
        settings.setValue("llm/gemini_model", self.txt_gemini_model.text().strip())
        settings.setValue("server/url", self.txt_url.text().strip())
        
        QMessageBox.information(
            self,
            "GeoCongo AI - Paramètres enregistrés",
            "Les clés API et les paramètres de configuration ont été enregistrés avec succès."
        )
        self.accept()

    def test_connection(self):
        try:
            client = GunduaEngineClient()
            url = self.txt_url.text().strip()
            if url:
                client.base_url = url
            orchestrator = self._build_orchestrator_from_form()

            if self.txt_gemini_key.text().strip():
                gemini_ok, gemini_msg = orchestrator.validate_gemini_connection()
            else:
                gemini_ok, gemini_msg = False, "Aucune cle Gemini saisie."

            if gemini_ok:
                self.lbl_status.setText("✅ GeoCongo AI et Gemini sont opérationnels.")
                QMessageBox.information(
                    self,
                    "GeoCongo AI - Test OK",
                    "La connexion Mtumishi a ete testee avec succes.\n\n"
                    f"Serveur SDK : {client.base_url}\n"
                    f"LLM : {orchestrator.active_model_name or 'Gemini'}\n"
                    f"Reponse test : {gemini_msg}"
                )
            else:
                self.lbl_status.setText("⚠️ SDK charge, mais liaison Gemini indisponible.")
                QMessageBox.warning(
                    self,
                    "GeoCongo AI - Test partiel",
                    "GeoCongo AI est accessible, mais Mtumishi n'a pas pu établir une vraie conversation IA.\n\n"
                    f"Serveur SDK : {client.base_url}\n"
                    f"Statut Gemini : {gemini_msg}\n\n"
                    "Verifiez votre cle API Gemini, le modele choisi et la connectivite reseau."
                )
        except Exception as e:
            self.lbl_status.setText("❌ Erreur de connexion.")
            QMessageBox.critical(
                self,
                "GeoCongo AI - Erreur Connexion",
                f"Impossible de se connecter au serveur Gundua Engine :\n\n{e}"
            )

    def diagnose_mtumishi(self):
        orchestrator = self._build_orchestrator_from_form()
        diagnostics = orchestrator.get_dependency_diagnostics()
        self.lbl_status.setText("ℹ️ Diagnostic Mtumishi prêt.")
        QMessageBox.information(
            self,
            "GeoCongo AI - Diagnostic Mtumishi",
            self._format_diagnostics_text(diagnostics),
        )

    def repair_mtumishi(self):
        answer = QMessageBox.question(
            self,
            "GeoCongo AI - Réparer Mtumishi",
            "Le plugin va installer ou mettre à jour automatiquement les dépendances Mtumishi "
            "dans le Python utilisé par QGIS. Voulez-vous continuer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return

        self.lbl_status.setText("⏳ Réparation Mtumishi en cours...")
        orchestrator = self._build_orchestrator_from_form()
        result = orchestrator.repair_antigravity_dependencies()
        diagnostics = result.get("diagnostics", {})

        if result.get("success"):
            self.lbl_status.setText("✅ Dépendances Mtumishi réparées.")
            QMessageBox.information(
                self,
                "GeoCongo AI - Réparation terminée",
                "Les dépendances Mtumishi ont été installées ou mises à jour avec succès.\n\n"
                f"{self._format_diagnostics_text(diagnostics)}\n\n"
                "Redémarrez QGIS pour garantir la prise en compte complète des nouveaux paquets.",
            )
        else:
            self.lbl_status.setText("❌ Échec de la réparation Mtumishi.")
            QMessageBox.critical(
                self,
                "GeoCongo AI - Réparation échouée",
                "La réparation automatique n'a pas abouti.\n\n"
                f"{self._format_diagnostics_text(diagnostics)}\n\n"
                f"STDERR :\n{result.get('stderr', '')}\n\n"
                f"STDOUT :\n{result.get('stdout', '')}",
            )
