"""
Cliente para interactuar con la API de Groq.

Proporciona una interfaz limpia para generar respuestas usando
los modelos de lenguaje de Groq, con manejo de errores y reintentos.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple, Union

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from common.clients.base_http_client import BaseHTTPClient
from common.errors.http_errors import ServiceUnavailableError


class GroqClient(BaseHTTPClient):
    """
    Cliente asíncrono para la API de Groq.
    
    Extiende BaseHTTPClient para proporcionar funcionalidad
    específica para la generación de texto con LLMs de Groq.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.groq.com/openai/v1", timeout: int = 30):
        """
        Inicializa el cliente con la API key.
        
        Args:
            api_key: API key de Groq
            base_url: URL base de la API
            timeout: Timeout en segundos para las peticiones
        """
        if not api_key:
            raise ValueError("API key de Groq es requerida")
        
        # Headers con autenticación
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Inicializar cliente base
        super().__init__(
            base_url=base_url,
            headers=headers
        )
        
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ServiceUnavailableError)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        n: int = 1,
        stream: bool = False,
        stop: Optional[Union[str, List[str]]] = None,
        user: Optional[str] = None
    ) -> Tuple[str, Dict[str, int]]:
        """
        Genera una respuesta usando el modelo especificado.
        
        Args:
            prompt: Prompt principal del usuario
            system_prompt: Prompt de sistema (opcional)
            model: Modelo a usar
            temperature: Controla la aleatoriedad (0-2)
            max_tokens: Máximo de tokens en la respuesta
            top_p: Nucleus sampling
            frequency_penalty: Penalización de frecuencia (-2 a 2)
            presence_penalty: Penalización de presencia (-2 a 2)
            n: Número de respuestas a generar
            stream: Si usar streaming (no implementado)
            stop: Secuencias donde parar la generación
            user: Identificador único del usuario
            
        Returns:
            Tupla de (respuesta_generada, uso_de_tokens)
            
        Raises:
            ServiceUnavailableError: Si el servicio no está disponible
            Exception: Para otros errores
        """
        start_time = time.time()
        
        # Construir mensajes
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Preparar payload según la documentación de Groq
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "n": n,
            "stream": stream
        }
        
        # Agregar parámetros opcionales si están presentes
        if stop is not None:
            payload["stop"] = stop
        
        if user is not None:
            payload["user"] = user
        
        self.logger.debug(
            f"Generando respuesta con {model}, "
            f"temp={temperature}, max_tokens={max_tokens}"
        )
        
        try:
            # Hacer petición
            response = await self.post(
                "/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            
            # Parsear respuesta
            data = response.json()
            
            # Validar estructura de respuesta
            if "choices" not in data or not data["choices"]:
                raise ValueError("Respuesta inválida de Groq API: sin choices")
            
            # Extraer respuesta principal
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason")
            
            # Verificar si se truncó
            if finish_reason == "length":
                self.logger.warning(
                    f"Respuesta truncada por límite de tokens ({max_tokens})"
                )
            
            # Extraer uso de tokens
            usage = data.get("usage", {})
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "queue_time": usage.get("queue_time", 0),
                "prompt_time": usage.get("prompt_time", 0),
                "completion_time": usage.get("completion_time", 0),
                "total_time": usage.get("total_time", 0)
            }
            
            # Log métricas
            elapsed = time.time() - start_time
            self.logger.info(
                f"Generación completada en {elapsed:.2f}s. "
                f"Tokens: {token_usage['total_tokens']} "
                f"(prompt: {token_usage['prompt_tokens']}, "
                f"completion: {token_usage['completion_tokens']})"
            )
            
            return content, token_usage
            
        except httpx.TimeoutException:
            self.logger.error(f"Timeout en llamada a Groq API después de {self.timeout}s")
            raise ServiceUnavailableError(
                f"Groq API timeout después de {self.timeout} segundos"
            )
        
        except Exception as e:
            self.logger.error(f"Error en llamada a Groq API: {str(e)}")
            raise
    
    async def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs
    ) -> Tuple[str, Dict[str, int]]:
        """
        Genera una respuesta usando una lista completa de mensajes.
        
        Args:
            messages: Lista de mensajes con formato {"role": "...", "content": "..."}
            model: Modelo a usar
            temperature: Temperatura de generación
            max_tokens: Máximo de tokens
            **kwargs: Otros parámetros opcionales
            
        Returns:
            Tupla de (respuesta_generada, uso_de_tokens)
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        try:
            response = await self.post(
                "/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                raise ValueError("Respuesta inválida de Groq API")
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return content, usage
            
        except Exception as e:
            self.logger.error(f"Error en generate_with_messages: {e}")
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Lista los modelos disponibles en Groq.
        
        Returns:
            Lista de modelos disponibles
        """
        try:
            response = await self.get("/models")
            data = response.json()
            return data.get("data", [])
            
        except Exception as e:
            self.logger.error(f"Error listando modelos: {e}")
            raise
    
    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Obtiene información detallada de un modelo específico.
        
        Args:
            model_id: ID del modelo
            
        Returns:
            Información del modelo
        """
        try:
            response = await self.get(f"/models/{model_id}")
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error obteniendo info del modelo {model_id}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Verifica si la API de Groq está disponible.
        
        Returns:
            True si está disponible, False en caso contrario
        """
        try:
            # Intentar listar modelos como health check
            models = await self.list_models()
            return len(models) > 0
            
        except Exception:
            return False
    
    async def close(self):
        """Cierra el cliente HTTP subyacente."""
        await self._client.aclose()