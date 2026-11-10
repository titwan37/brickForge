from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

class ChatProvider(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], model: Optional[str] = None):
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        pass

    @abstractmethod
    def cancel_request(self, request_id: str) -> None:
        pass

    @abstractmethod
    def set_timeout(self, timeout: float) -> None:
        pass

class OllamaProvider(ChatProvider):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint.rstrip("/")
        self.client = httpx.Client()
        self.timeout = 45.0

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        selected_model = model or "qwen2.5-coder:7b"
        prompt_payload = self._build_prompt_payload(messages)
        ollama_req = {
            "model": selected_model,
            "messages": prompt_payload,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 1024,
            },
        }
        response = self.client.post(f"{self.endpoint}/api/chat", json=ollama_req, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def chat_stream(self, messages: List[Dict[str, str]], model: Optional[str] = None):
        selected_model = model or "qwen2.5-coder:7b"
        prompt_payload = self._build_prompt_payload(messages)
        ollama_req = {
            "model": selected_model,
            "messages": prompt_payload,
            "stream": True,
            "options": {
                "temperature": 0.2,
                "num_predict": 1024,
            },
        }
        with self.client.stream("POST", f"{self.endpoint}/api/chat", json=ollama_req, timeout=self.timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    yield json.loads(line)

    def get_available_models(self) -> List[str]:
        response = self.client.get(f"{self.endpoint}/api/tags", timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", []) if "name" in m]

    def cancel_request(self, request_id: str) -> None:
        # Implement cancellation logic if Ollama supports it
        pass

    def set_timeout(self, timeout: float) -> None:
        self.timeout = timeout

    def _build_prompt_payload(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        return [{"role": m["role"], "content": m["content"]} for m in messages]

class OpenAIProvider(ChatProvider):
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(headers={"Authorization": f"Bearer {self.api_key}"})
        self.timeout = 45.0

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        selected_model = model or "gpt-3.5-turbo"
        prompt_payload = self._build_prompt_payload(messages)
        openai_req = {
            "model": selected_model,
            "messages": prompt_payload,
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        response = self.client.post(f"{self.endpoint}/v1/chat/completions", json=openai_req, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def chat_stream(self, messages: List[Dict[str, str]], model: Optional[str] = None):
        selected_model = model or "gpt-3.5-turbo"
        prompt_payload = self._build_prompt_payload(messages)
        openai_req = {
            "model": selected_model,
            "messages": prompt_payload,
            "stream": True,
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        with self.client.stream("POST", f"{self.endpoint}/v1/chat/completions", json=openai_req, timeout=self.timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    yield json.loads(line)

    def get_available_models(self) -> List[str]:
        # OpenAI does not provide an endpoint to list models, so this is a placeholder
        return ["gpt-3.5-turbo", "gpt-4"]

    def cancel_request(self, request_id: str) -> None:
        # Implement cancellation logic if OpenAI supports it
        pass

    def set_timeout(self, timeout: float) -> None:
        self.timeout = timeout

    def _build_prompt_payload(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        return [{"role": m["role"], "content": m["content"]} for m in messages]
