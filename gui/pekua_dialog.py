"""
Pekua Engine RAG Knowledge Base Dialog for GeoCongo AI.
Provides a search interface for geological reports, exploration data, and bibliographic queries.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLineEdit, QTextEdit, QComboBox, QPushButton,
    QLabel, QMessageBox
)
from qgis.PyQt.QtCore import Qt, QSettings
from qgis.core import QgsMessageLog, Qgis
import os
from qgis.PyQt.QtGui import QIcon, QPixmap


class PekuaEngineDialog(QDialog):
    """
    Dialog for querying Pekua Engine Geological Knowledge Base (RAG).
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface

        self.setWindowTitle("GeoCongo AI - Recherche Documentaire (Pekua Engine)")
        self.setMinimumSize(600, 480)
        self.setSizeGripEnabled(True)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Header Box
        header_box = QGroupBox("🔍 Base de Connaissances Géologiques (Pekua RAG)")
        header_layout = QHBoxLayout(header_box)

        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(logo_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(lbl_logo)

        lbl_info = QLabel(
            "Interrogez la base documentaire géoscientifique de la RDC "
            "(Rapports d'exploration, thèses, cartes géologiques et publications techniques)."
        )
        lbl_info.setWordWrap(True)
        header_layout.addWidget(lbl_info)
        main_layout.addWidget(header_box)

        # Search Form Box
        search_box = QGroupBox("Paramètres de Recherche RAG")
        search_layout = QVBoxLayout(search_box)

        # Domain filter
        domain_layout = QHBoxLayout()
        domain_layout.addWidget(QLabel("Domaine / Thématique :"))
        self.cb_domain = QComboBox()
        self.cb_domain.addItem("Tous les domaines", "all")
        self.cb_domain.addItem("Mines & Minéralisation", "Mines")
        self.cb_domain.addItem("Géologie Régionale", "Geology")
        self.cb_domain.addItem("Télédétection & Imagerie", "RemoteSensing")
        domain_layout.addWidget(self.cb_domain)
        search_layout.addLayout(domain_layout)

        # Province filter
        province_layout = QHBoxLayout()
        province_layout.addWidget(QLabel("Province (RDC) :"))
        self.cb_province = QComboBox()
        self.cb_province.addItem("Toutes les provinces", None)
        self.cb_province.addItem("Haut-Katanga", "Haut-Katanga")
        self.cb_province.addItem("Lualaba", "Lualaba")
        self.cb_province.addItem("Nord-Kivu", "Nord-Kivu")
        self.cb_province.addItem("Ituri", "Ituri")
        self.cb_province.addItem("Kinshasa", "Kinshasa")
        province_layout.addWidget(self.cb_province)
        search_layout.addLayout(province_layout)

        # Query input
        query_layout = QHBoxLayout()
        query_layout.addWidget(QLabel("Question / Mots-clés :"))
        self.txt_query = QLineEdit()
        self.txt_query.setPlaceholderText("Ex: Gisement de cuivre stratiforme dans le Katanga...")
        query_layout.addWidget(self.txt_query)
        search_layout.addLayout(query_layout)

        # Search Button
        self.btn_search = QPushButton("🔍 Interroger Pekua RAG")
        self.btn_search.setStyleSheet("font-weight: bold; background-color: #1976d2; color: white; padding: 6px;")
        self.btn_search.clicked.connect(self.perform_search)
        search_layout.addWidget(self.btn_search)

        main_layout.addWidget(search_box)

        # Results Box
        results_box = QGroupBox("Résultats & Synthèse RAG")
        results_layout = QVBoxLayout(results_box)

        self.txt_results = QTextEdit()
        self.txt_results.setReadOnly(True)
        self.txt_results.setPlaceholderText("Les résultats et sources documentaires s'afficheront ici...")
        results_layout.addWidget(self.txt_results)

        main_layout.addWidget(results_box)

        # Close button
        btn_close_layout = QHBoxLayout()
        btn_close_layout.addStretch()
        self.btn_close = QPushButton("Fermer")
        self.btn_close.clicked.connect(self.accept)
        btn_close_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_close_layout)

    def perform_search(self):
        query = self.txt_query.text().strip()
        if not query:
            QMessageBox.warning(self, "Champ requis", "Veuillez saisir une question ou des mots-clés.")
            return

        domain = self.cb_domain.currentData()
        province = self.cb_province.currentData()

        self.txt_results.setText(f"⌛ Interrogation de la base Pekua RAG pour : '{query}'...")
        self.btn_search.setEnabled(False)

        # Récupération de la clé API depuis les paramètres
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        api_key = settings.value("api_keys/geocongo", "").strip()

        if not api_key:
             QMessageBox.critical(self, "Clé API manquante", "Veuillez configurer votre clé API GeoCongo AI dans les Paramètres.")
             self.btn_search.setEnabled(True)
             self.txt_results.setText("❌ Erreur : Aucune clé API configurée.")
             return

        try:
            from geocongoai.client import GeoCongoClient
            client = GeoCongoClient(api_key=api_key)
            
            # Appel API RAG : ajout des paramètres domaine/province
            res = client.ask_rag(query=query, domain=domain, province=province)
            
            response_text = f"### Résultats Pekua RAG (Live)\n- **Requête** : {query}\n\n**Synthèse :**\n{res.answer}\n\n**Sources :**\n{res.sources}"
            
            self.txt_results.setText(response_text)
            QgsMessageLog.logMessage(f"Recherche Pekua réussie pour : {query}", "GeoCongoAI", Qgis.Info)
        except Exception as e:
            self.txt_results.setText(f"❌ Erreur lors de la recherche Pekua RAG :\n{str(e)}")
        finally:
            self.btn_search.setEnabled(True)
