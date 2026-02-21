import re
import os
import requests
from typing import Optional


class SLMCodeAgent:
    """
    Uses Groq API (free) — runs LLaMA 3 in the cloud.
    Much higher rate limits than Gemini free tier.
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "llama-3.1-8b-instant",
        request_timeout: int = 60,
    ):
        self.model_name = model_name
        self.timeout = request_timeout
        self.api_key = api_key

        if not self.api_key:
            self.api_key = os.environ.get("enter api", "")

        if not self.api_key:
            raise ValueError(
                "\n[ERROR] Groq API Key is missing.\n"
                "Get a free key from: https://console.groq.com/keys\n"
            )

        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        if not text:
            return ""
        pattern = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def generate_python_script(
        self, action_description: str, gesture_name: Optional[str] = None
    ) -> str:
        gesture_info = (
            f'For hand gesture "{gesture_name}".' if gesture_name else ""
        )

        prompt = f"""Write a standalone Python 3 script for Windows that does:
"{action_description}"
{gesture_info}
Output ONLY Python code. Use webbrowser for URLs, os.startfile for apps.
Include if __name__ == "__main__": main() and try/except."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        try:
            print("[SLM] Sending request to Groq...")
            resp = requests.post(
                self.api_url, json=payload,
                headers=headers, timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            code = self._strip_code_fences(text)
            print("[SLM] Script generated successfully!")
            return code

        except Exception as e:
            print(f"[SLM] Error: {e}")
            return ""