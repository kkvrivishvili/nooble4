"""
Cliente para interactuar con la API de Groq.
"""

import logging
import time
from typing import Optional, Dict, Any, List

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class GroqClient:
    """
    Cliente asincrónico para generar respuestas con Groq LLM.
    """
    
    def __init__(self):
        """Inicializa el cliente con la API key desde configuración."""
        self.api_key = settings.groq_api_key
        self.api_base_url = "https://api.groq.com/openai/v1"
        self.default_model = settings.default_llm_model
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024
    ) -> str:
        """
        Genera respuesta basada en el prompt.
        
        Args:
            prompt: Prompt principal
            system_prompt: Prompt de sistema (opcional)
            model: Modelo específico a usar
            temperature: Temperatura (creatividad)
            max_tokens: Máximo de tokens en respuesta
            
        Returns:
            String con la respuesta generada
            
        Raises:
            Exception: Si hay error en la generación
        """
        start_time = time.time()
        model = model or self.default_model
        
        messages = []
        
        # Agregar system prompt si existe
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Agregar prompt principal
        messages.append({"role": "user", "content": prompt})
        
        # Preparar payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # Enviar request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=settings.llm_timeout_seconds
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Error Groq API ({response.status}): {error_text}")
                        raise Exception(f"Error de API Groq: {response.status}")
                    
                    result = await response.json()
                    
                    # Extraer respuesta
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0].get("message", {}).get("content", "")
                        
                        # Registrar uso
                        if "usage" in result:
                            usage = result["usage"]
                            logger.info(f"Tokens: prompt={usage.get('prompt_tokens', 0)}, "
                                       f"completion={usage.get('completion_tokens', 0)}, "
                                       f"total={usage.get('total_tokens', 0)}")
                            
                            # Aquí se podría trackear tokens usando un servicio común
                        
                        execution_time = time.time() - start_time
                        logger.info(f"Generación con {model} completada en {execution_time:.2f}s")
                        return content
                    else:
                        raise Exception("Formato de respuesta inesperado de Groq API")
                        
        except aiohttp.ClientError as e:
            logger.error(f"Error de conexión con Groq API: {str(e)}")
            raise Exception(f"Error conectando con Groq API: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error generando respuesta: {str(e)}")
            raise
