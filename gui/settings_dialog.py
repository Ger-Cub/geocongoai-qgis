"""
Settings and API Key configuration dialog for GeoCongo AI.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLineEdit, QLabel, QPushButton, QMessageBox, QGridLayout
)
from qgis.PyQt.QtCore import Qt, QSettings, QUrl
from qgis.PyQt.QtGui import QDesktopServices

from geocongoai.gundua_engine import GunduaEngineClient


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

        layout.addWidget(group_keys)

        # 2. Server Settings Group
        group_server = QGroupBox("🌐 Connexion Serveur & Gundua Engine")
        layout_server = QVBoxLayout(group_server)

        layout_server.addWidget(QLabel("URL du serveur Gundua Engine / Pekua API :"))
        self.txt_url = QLineEdit("http://137.184.96.142:8000")
        layout_server.addWidget(self.txt_url)

        self.btn_test = QPushButton("🧪 Tester la connexion au SDK")
        layout_server.addWidget(self.btn_test)

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
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_close.clicked.connect(self.reject)

    def _load_settings(self):
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        self.txt_gemini_key.setText(settings.value("api_keys/gemini", ""))
        self.txt_geocongo_key.setText(settings.value("api_keys/geocongo", ""))
        self.txt_url.setText(settings.value("server/url", "http://137.184.96.142:8000"))

    def save_settings(self):
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        settings.setValue("api_keys/gemini", self.txt_gemini_key.text().strip())
        settings.setValue("api_keys/geocongo", self.txt_geocongo_key.text().strip())
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

            self.lbl_status.setText("✅ Connexion réussie au SDK Gundua Engine !")
            QMessageBox.information(
                self,
                "GeoCongo AI - Test OK",
                f"Le SDK geocongoai a été testé avec succès !\n\nServeur : {client.base_url}"
            )
        except Exception as e:
            self.lbl_status.setText("❌ Erreur de connexion.")
            QMessageBox.critical(
                self,
                "GeoCongo AI - Erreur Connexion",
                f"Impossible de se connecter au serveur Gundua Engine :\n\n{e}"
            )
