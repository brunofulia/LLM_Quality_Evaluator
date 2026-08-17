import requests
from typing import List

class ModelFetcher:
    """
    Utility class to discover available models for a given provider dynamically.
    """
    
    @staticmethod
    def fetch_models(provider: str, api_key: str) -> List[str]:
        provider = provider.lower()
        try:
            if provider in ["google", "gemini"]:
                return ModelFetcher._fetch_google(api_key)
            elif provider in ["openai", "gpt"]:
                return ModelFetcher._fetch_openai(api_key)
            elif provider == "groq":
                return ModelFetcher._fetch_groq(api_key)
            elif provider in ["anthropic", "claude"]:
                return ModelFetcher._fetch_anthropic(api_key)
            else:
                return []
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (400, 401, 403):
                raise ValueError(f"Invalid credentials or request rejected (Error {e.response.status_code}).")
            return []
        except Exception:
            return []
            
    @staticmethod
    def _fetch_google(api_key: str) -> List[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = []
        for m in data.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                # Remove 'models/' prefix since DeepEval adapter handles it or expects it without prefix depending on version
                name = m["name"].replace("models/", "")
                models.append(name)
        return models
        
    @staticmethod
    def _fetch_openai(api_key: str) -> List[str]:
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return sorted([m["id"] for m in data.get("data", []) if "gpt" in m["id"]])
        
    @staticmethod
    def _fetch_groq(api_key: str) -> List[str]:
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return sorted([m["id"] for m in data.get("data", [])])

    @staticmethod
    def _fetch_anthropic(api_key: str) -> List[str]:
        url = "https://api.anthropic.com/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        response = requests.get(url, headers=headers, timeout=10)
        
        # If the models endpoint returns 404 (in older versions), we try with a known endpoint
        # just to force the 401 error if the key is bad.
        if response.status_code == 404:
            val_resp = requests.get(
                "https://api.anthropic.com/v1/messages", 
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            )
            if val_resp.status_code == 401:
                val_resp.raise_for_status() # Raises error if key is bad
            # If validation passed, return the static list
            return ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307"]
            
        response.raise_for_status()
        data = response.json()
        return sorted([m["id"] for m in data.get("data", []) if m["type"] == "model"])
