"""
Cliente para la API de Groq.

Este cliente maneja la comunicación con la API de Groq para
generación de texto con modelos LLM.
"""

import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Dict

from common.errors.exceptions import ExternalServiceError

class GroqClient:
    """Cliente para interactuar con la API de Groq."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.groq.com/openai/v1", timeout: int = 30):
        """
        Inicializa el cliente Groq.
        
        Args:
            api_key: Clave de API para Groq.
            base_url: URL base de la API.
            timeout: Timeout para las peticiones.
        """
        if not api_key:
            raise ValueError("La API key de Groq no puede ser nula.")
            
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._logger = logging.getLogger(__name__)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int
    ) -> tuple[str, Dict[str, int]]:
        """
        Genera una respuesta de texto usando un modelo de Groq.
        
        Args:
            prompt: El prompt principal para el modelo.
            system_prompt: El prompt de sistema.
            model: El modelo a usar (e.g., 'llama3-8b-8192').
            temperature: Temperatura de generación.
            max_tokens: Máximo de tokens en la respuesta.
            
        Returns:
            Una tupla con (texto_generado, uso_de_tokens).
            
        Raises:
            ExternalServiceError: Si la API de Groq falla.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                self._logger.debug(f"Enviando request a Groq con modelo {model}")
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                
                generated_text = data['choices'][0]['message']['content']
                token_usage = data.get('usage', {})
                
                self._logger.info(f"Respuesta recibida de Groq. Uso de tokens: {token_usage}")
                
                return generated_text, {
                    "prompt_tokens": token_usage.get("prompt_tokens", 0),
                    "completion_tokens": token_usage.get("completion_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0)
                }
                
            except httpx.HTTPStatusError as e:
                self._logger.error(f"Error de estado HTTP de Groq: {e.response.status_code} - {e.response.text}")
                raise ExternalServiceError(
                    f"Error en la API de Groq: {e.response.status_code}",
                    original_exception=e
                )
            except Exception as e:
                self._logger.error(f"Error inesperado con Groq: {e}")
                raise ExternalServiceError("Error inesperado al contactar Groq", original_exception=e)
