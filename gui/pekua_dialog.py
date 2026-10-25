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
        self.txt_results.setAcceptRichText(True)
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

    def _set_results_markdown(self, markdown_text: str):
        try:
            self.txt_results.setMarkdown(markdown_text)
        except AttributeError:
            self.txt_results.setPlainText(markdown_text)

    def _build_rag_query(self, query: str, domain: str = None, province: str = None) -> str:
        constraints = []
        if domain and domain != "all":
            constraints.append(f"domaine: {domain}")
        if province:
            constraints.append(f"province: {province}")

        if not constraints:
            return query

        return (
            "Réponds en tenant compte des contraintes documentaires suivantes: "
            + ", ".join(constraints)
            + f".\n\nQuestion utilisateur: {query}"
        )

    def _format_rag_sources(self, sources) -> str:
        if not sources:
            return "_Aucune source citée par le moteur RAG._"

        lines = []
        for idx, src in enumerate(sources[:5], start=1):
            similarity = ""
            if getattr(src, "similarity", None) is not None:
                similarity = f" | similarité: {src.similarity:.3f}"
            author = f" | auteur: {src.author}" if getattr(src, "author", None) else ""
            title = getattr(src, "title", "Sans titre")
            document_id = getattr(src, "document_id", "")
            lines.append(f"{idx}. **{title}**{author}{similarity} | id: `{document_id or 'n/a'}`")
        return "\n".join(lines)

    def _format_document_results(self, docs) -> str:
        if not docs or not getattr(docs, "results", None):
            return "_Aucun document ciblé trouvé avec les filtres sélectionnés._"

        lines = [f"**Documents trouvés** : {docs.total_found}"]
        for idx, item in enumerate(docs.results[:5], start=1):
            similarity = ""
            if getattr(item, "similarity", None) is not None:
                similarity = f" | similarité: {item.similarity:.3f}"
            author = f" | auteur: {item.author}" if getattr(item, "author", None) else ""
            url = f" | url: {item.document_url}" if getattr(item, "document_url", None) else ""
            lines.append(f"{idx}. **{item.title}**{author}{similarity}{url}")

            if getattr(item, "relevant_chunks", None):
                excerpt = item.relevant_chunks[0].strip()
                if len(excerpt) > 240:
                    excerpt = excerpt[:237] + "..."
                lines.append(f"   - Extrait: {excerpt}")
        return "\n".join(lines)

    def perform_search(self):
        query = self.txt_query.text().strip()
        if not query:
            QMessageBox.warning(self, "Champ requis", "Veuillez saisir une question ou des mots-clés.")
            return

        domain = self.cb_domain.currentData()
        province = self.cb_province.currentData()

        self._set_results_markdown(f"⌛ Interrogation de la base Pekua RAG pour : `{query}`...")
        self.btn_search.setEnabled(False)

        # Récupération de la clé API depuis les paramètres
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        api_key = settings.value("api_keys/geocongo", "").strip()
        if not api_key:
             QMessageBox.critical(self, "Clé API manquante", "Veuillez configurer votre clé API GeoCongo AI dans les Paramètres.")
             self.btn_search.setEnabled(True)
             self._set_results_markdown("❌ Erreur : aucune clé API configurée.")
             return

        try:
            from geocongoai.client import GeoCongoClient
            # Pour Pekua, on laisse le SDK gérer son endpoint par défaut.
            # Le plugin ne fournit ici que la clé API utilisateur.
            client = GeoCongoClient(api_key=api_key)

            rag_query = self._build_rag_query(query, domain=domain, province=province)
            rag_response = client.ask_rag(query=rag_query)

            docs_response = client.search_documents(
                query=query,
                domain=None if domain in (None, "all") else domain,
                province=province,
            )

            response_text = (
                "### Résultats Pekua RAG (SDK v0.4.3)\n"
                f"- **Question** : {query}\n"
                f"- **Domaine** : {domain or 'Tous'}\n"
                f"- **Province** : {province or 'Toutes'}\n\n"
                "**Synthèse RAG**\n"
                f"{rag_response.answer}\n\n"
                "**Sources citées par Pekua**\n"
                f"{self._format_rag_sources(rag_response.sources)}\n\n"
                "**Recherche documentaire filtrée**\n"
                f"{self._format_document_results(docs_response)}"
            )

            self._set_results_markdown(response_text)
            QgsMessageLog.logMessage(f"Recherche Pekua réussie pour : {query}", "GeoCongoAI", Qgis.Info)
        except Exception as e:
            error_text = str(e)
            if "ConnectTimeout" in error_text or "timed out" in error_text.lower():
                error_text += (
                    "\n\nLe plugin transmet bien votre clé API, mais le service Pekua n'a pas répondu à temps. "
                    "Vérifiez la connectivité réseau ou la disponibilité du service GeoCongo AI."
                )
            self._set_results_markdown(f"❌ Erreur lors de la recherche Pekua RAG :\n`{error_text}`")
        finally:
            self.btn_search.setEnabled(True)
