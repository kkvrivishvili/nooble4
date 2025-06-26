"""
Cliente para interactuar con la API de Groq usando el SDK oficial.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple, Union

from groq import AsyncGroq, APIConnectionError, RateLimitError, APIStatusError
from common.errors.exceptions import ServiceUnavailableError


class GroqClient:
    """Cliente asíncrono para la API de Groq."""
    
    def __init__(self, api_key: str, timeout: int, max_retries: int):
        """
        Inicializa el cliente con la API key.
        
        Args:
            api_key: API key de Groq
            timeout: Timeout en segundos (desde QueryServiceSettings)
            max_retries: Número máximo de reintentos (desde QueryServiceSettings)
        """
        if not api_key:
            raise ValueError("API key de Groq es requerida")
        
        self.client = AsyncGroq(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries
        )
        
        self._logger = logging.getLogger(__name__)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        stop: Optional[Union[str, List[str]]] = None
    ) -> Tuple[str, Dict[str, int]]:
        """
        Genera una respuesta usando el modelo especificado.
        
        Returns:
            Tupla de (respuesta_generada, uso_de_tokens)
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stop=stop
            )
            
            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return content, usage
            
        except APIConnectionError as e:
            self._logger.debug(f"Error de conexión con Groq API: {e}")
            raise ServiceUnavailableError("Error de conexión con la API de Groq")
        
        except RateLimitError as e:
            self._logger.debug(f"Límite de peticiones excedido: {e}")
            raise ServiceUnavailableError("Límite de peticiones de Groq API excedido")
        
        except APIStatusError as e:
            self._logger.debug(f"Error de API de Groq: {e}")
            if 400 <= e.status_code < 500:
                raise ValueError(f"Error en la petición: {e.message}")
            raise ServiceUnavailableError(f"Error en el servidor de Groq: {e.message}")
    
    async def close(self):
        """Cierra el cliente."""
        await self.client.close()