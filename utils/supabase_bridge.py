import json
import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


class SupabaseClient:
    def __init__(self):
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }

    def call_edge_function(self, function_name, payload):
        if not SUPABASE_URL:
            raise ValueError("SUPABASE_URL non configuré.")
        url = f"{SUPABASE_URL}/functions/v1/{function_name}"
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        return response.json()

def rag_agent(query):
    client = SupabaseClient()
    return client.call_edge_function("rag-agent", {"query": query})

def search_documents(params):
    client = SupabaseClient()
    return client.call_edge_function("search-documents", params)

def search_geological(params):
    client = SupabaseClient()
    return client.call_edge_function("search-geological", params)
