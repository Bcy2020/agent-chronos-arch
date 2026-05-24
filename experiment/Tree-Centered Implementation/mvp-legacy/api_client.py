"""
DeepSeek API client using OpenAI SDK.
"""
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI

from config import Config


class APIClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 4096
    ) -> str:
        """
        Send a chat completion request to DeepSeek API.
        Retries on failure up to max_retries times.
        """
        temp = temperature if temperature is not None else self.config.temperature
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                print(f"API call failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        raise RuntimeError(f"API call failed after {self.config.max_retries} retries: {last_error}")
    
    def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
        stub_response: Optional[str] = None
    ) -> str:
        """
        Send a chat completion request with fallback to stub response.
        """
        try:
            return self.chat(messages, temperature, max_tokens)
        except RuntimeError as e:
            if stub_response is not None:
                print(f"Using stub response due to API failure: {e}")
                return stub_response
            raise
    
    def test_connection(self) -> bool:
        """Test if the API connection is working."""
        try:
            response = self.chat([{"role": "user", "content": "Hello"}], max_tokens=10)
            return len(response) > 0
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
