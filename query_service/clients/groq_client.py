"""
Cliente para interactuar con la API de Groq usando el SDK oficial.

Proporciona una interfaz limpia y robusta para generar respuestas usando
los modelos de lenguaje de Groq, aprovechando los reintentos nativos del SDK
y funcionalidades avanzadas como el modo JSON.
"""

import logging
import time
import json
from typing import Optional, Dict, Any, List, Tuple, Union

# SDK oficial de Groq
from groq import AsyncGroq, APIConnectionError, RateLimitError, APIStatusError

# Ya no se necesita tenacity
from common.errors.http_errors import ServiceUnavailableError


class GroqClient:
    """
    Cliente asíncrono para la API de Groq, utilizando el SDK oficial.
    
    Este cliente está configurado para usar los reintentos nativos del SDK,
    lo que lo hace más robusto ante errores transitorios de red o de la API.
    """
    
    def __init__(self, api_key: str, timeout: int = 60, max_retries: int = 3):
        """
        Inicializa el cliente con la API key y configuración de reintentos.
        
        Args:
            api_key: API key de Groq.
            timeout: Timeout en segundos para las peticiones.
            max_retries: Número máximo de reintentos para errores recuperables.
        """
        if not api_key:
            raise ValueError("API key de Groq es requerida")
        
        # Inicializar cliente asíncrono del SDK de Groq con configuración de reintentos
        self.client = AsyncGroq(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries
        )
        
        self.logger = logging.getLogger(__name__)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "llama3-70b-8192",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop: Optional[Union[str, List[str]]] = None,
        user: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Genera una respuesta de texto plano usando el modelo especificado.
        
        Utiliza los reintentos nativos del SDK para manejar errores transitorios.
        
        Returns:
            Tupla de (respuesta_generada, uso_de_tokens)
        """
        return await self._create_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=stop,
            user=user,
            json_mode=False
        )

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = "Responde únicamente con un objeto JSON válido.",
        model: str = "llama3-70b-8192",
        temperature: float = 0.1, # Más bajo para respuestas más deterministas
        max_tokens: int = 2048,
        user: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Genera una respuesta en formato JSON garantizado por la API.

        Args:
            prompt: Prompt que describe la estructura JSON deseada.
            system_prompt: Instrucción para asegurar la salida en JSON.
            ...

        Returns:
            Tupla de (respuesta_json_parseada, uso_de_tokens)
        """
        response_text, usage = await self._create_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            user=user,
            json_mode=True
        )
        
        try:
            # Aunque la API garantiza un JSON válido, parsearlo es buena práctica
            json_response = json.loads(response_text)
            return json_response, usage
        except json.JSONDecodeError:
            self.logger.error("La API de Groq no devolvió un JSON válido a pesar del modo JSON.")
            raise ValueError("La respuesta no pudo ser decodificada como JSON.")

    async def _create_completion(
        self, 
        prompt: str, 
        system_prompt: Optional[str], 
        model: str, 
        json_mode: bool, 
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Método privado para centralizar la lógica de llamada a la API de Groq.
        """
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        request_params = {
            "messages": messages,
            "model": model,
            **kwargs
        }

        if json_mode:
            request_params["response_format"] = {"type": "json_object"}
        
        self.logger.debug(f"Enviando petición a Groq con modelo {model} (JSON mode: {json_mode})...")

        try:
            chat_completion = await self.client.chat.completions.create(**request_params)
            
            content = chat_completion.choices[0].message.content
            token_usage = chat_completion.usage.model_dump() if chat_completion.usage else {}
            
            if chat_completion.choices[0].finish_reason == "length":
                self.logger.warning(f"Respuesta truncada por límite de tokens ({kwargs.get('max_tokens')})")

            elapsed = time.time() - start_time
            self.logger.info(
                f"Generación completada en {elapsed:.2f}s. "
                f"Tokens: {token_usage.get('total_tokens', 0)}"
            )
            
            return content, token_usage

        except APIConnectionError as e:
            self.logger.error(f"Error de conexión con Groq API: {e.__cause__}")
            raise ServiceUnavailableError("Error de conexión con la API de Groq.")
        
        except RateLimitError as e:
            self.logger.error(f"Límite de peticiones de Groq API excedido: {e}")
            raise ServiceUnavailableError("Límite de peticiones de Groq API excedido.")

        except APIStatusError as e:
            self.logger.error(f"Error de API de Groq (status {e.status_code}): {e.response}")
            if 400 <= e.status_code < 500:
                raise ValueError(f"Error en la petición a Groq API: {e.message}")
            raise ServiceUnavailableError(f"Error en el servidor de Groq API: {e.message}")

        except Exception as e:
            self.logger.error(f"Error inesperado en llamada a Groq API: {e}", exc_info=True)
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