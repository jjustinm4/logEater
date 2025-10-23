# core/llm/ollama_client.py
from urllib import request, error
import json
from typing import Optional, Dict, Any


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    """
    Minimal Ollama client using stdlib (no 'requests' dependency).
    Assumes Ollama is running locally: `ollama serve`
    """

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 90):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict[str, Any]] = None,
        keep_alive: Optional[str] = None,
    ) -> str:
        """
        Calls /api/generate with stream=false and returns the full response text.
        Raises OllamaError on failure.
        """
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if options:
            payload["options"] = options
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
        except error.URLError as e:
            raise OllamaError(f"Ollama unreachable at {self.base_url}: {e}") from e
        except Exception as e:
            raise OllamaError(f"Ollama call failed: {e}") from e

        try:
            parsed = json.loads(body)
        except Exception as e:
            raise OllamaError(f"Invalid JSON from Ollama: {e}\nRaw: {body[:500]}") from e

        # /api/generate returns {"response": "...", ...}
        resp_text = parsed.get("response")
        if not isinstance(resp_text, str):
            raise OllamaError(f"Missing 'response' in Ollama result. Raw: {body[:500]}")
        return resp_text
