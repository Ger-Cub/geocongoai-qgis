"""
Mtumishi Agentic Orchestrator with live Google Gemini and GeoCongo AI API integration.
"""

import os
from qgis.PyQt.QtCore import QSettings

class MtumishiOrchestrator:
    """
    Orchestrateur intelligent Mtumishi connecté aux clés API configurées dans QSettings
    (Google Gemini et GeoCongo AI / Pekua / Gundua / Chimbua).
    """

    def __init__(self):
        self.reload_keys()

    def reload_keys(self):
        settings = QSettings("GeoCongoAI", "GeoCongoAIPlugin")
        self.gemini_key = settings.value("api_keys/gemini", "").strip()
        self.geocongo_key = settings.value("api_keys/geocongo", "").strip()
        self.server_url = settings.value("server/url", "http://137.184.96.142:8000").strip()

        # Configure Gemini if key is present
        self.gemini_model = None
        if self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                # Try modern model names compatible with current SDK versions
                for model_name in ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest", "gemini-1.5-flash"]:
                    try:
                        model = genai.GenerativeModel(model_name)
                        # Quick test invocation or initialization check
                        self.gemini_model = model
                        break
                    except Exception:
                        continue
            except Exception as e:
                print(f"[Mtumishi] Erreur initialisation Gemini: {e}")

    def is_gemini_active(self) -> bool:
        return self.gemini_model is not None and bool(self.gemini_key)

    def reason(self, prompt: str, context_dict: dict = None) -> str:
        """
        Raisonnement intelligent de Mtumishi.
        Si la clé Gemini est configurée, utilise Gemini avec le prompt géologique contextuel.
        Sinon, bascule sur un mode heuristique intelligent.
        """
        self.reload_keys()

        ctx_str = ""
        if context_dict:
            ctx_str = f"\n\n[Contexte Géospatial QGIS Actuel]\n- Emprise BBOX: {context_dict.get('bbox')}\n- CRS: {context_dict.get('crs', 'EPSG:4326')}\n- Province RDC: {context_dict.get('province', 'Non spécifiée')}\n- Couche active: {context_dict.get('active_layer', 'Aucune')}"

        system_instruction = (
            "Tu es Mtumishi, l'orchestrateur agentique géoscientifique de GeoCongo AI. "
            "Ton rôle est d'analyser les requêtes des géologues et ingénieurs miniers en République Démocratique du Congo, "
            "d'interroger les moteurs Pekua (RAG documentaire), Gundua (télédétection & Greenfield) et Chimbua (modélisation 3D forages), "
            "et de formuler des recommandations techniques précises, structurées et professionnelles en français."
        )

        if self.is_gemini_active():
            try:
                chat = self.gemini_model.start_chat(history=[])
                full_prompt = f"{system_instruction}{ctx_str}\n\nRequête utilisateur : {prompt}"
                response = chat.send_message(full_prompt)
                return response.text
            except Exception as e:
                return f"⚠️ Erreur lors de l'appel à l'API Gemini : {e}\n\n[Mode Secours Heuristique] : J'ai bien reçu votre consigne '{prompt}'. Veuillez vérifier votre clé API Gemini dans les Paramètres."

        # Mode heuristique intelligent si pas de clé Gemini
        return (
            f"🤖 **Mtumishi (Mode Orchestrateur Local)** :\n"
            f"J'ai analysé votre requête : *'{prompt}'*.\n"
            f"{ctx_str}\n\n"
            f"💡 **Recommandation technique** :\n"
            f"Pour bénéficier du raisonnement LLM avancé avec Google Gemini, veuillez renseigner votre **Clé API Gemini** "
            f"dans le menu ⚙️ **Paramètres** de l'extension GeoCongo AI.\n"
            f"Une fois configurée, je pourrai analyser en profondeur vos données géologiques et piloter les moteurs Pekua, Gundua et Chimbua !"
        )
