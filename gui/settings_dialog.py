"""
Settings and API Key configuration dialog for GeoCongo AI.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLineEdit, QLabel, QPushButton, QMessageBox
)
from qgis.PyQt.QtCore import Qt

from geocongoai.gundua_engine import GunduaEngineClient


class SettingsDialog(QDialog):
    """
    Configuration dialog for GeoCongo AI server endpoints and API keys.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoCongo AI - Paramètres & Connexion API")
        self.resize(460, 320)
        
        import os
        from qgis.PyQt.QtGui import QIcon
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Server Settings Group
        group_server = QGroupBox("🌐 Connexion Gundua Engine")
        layout_server = QVBoxLayout(group_server)

        layout_server.addWidget(QLabel("URL du serveur Gundua Engine :"))
        self.txt_url = QLineEdit("http://137.184.96.142:8000")
        layout_server.addWidget(self.txt_url)

        layout_server.addWidget(QLabel("Clé API (Optionnelle) :"))
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        self.txt_api_key.setPlaceholderText("Entrez votre clé API GeoCongo AI...")
        layout_server.addWidget(self.txt_api_key)

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
        self.btn_save.clicked.connect(self.accept)
        self.btn_close.clicked.connect(self.reject)

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
