"""
Validation Service - Servicio de validación de textos para embeddings.

Maneja validaciones específicas por tier y modelo.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from common.models.execution_context import ExecutionContext
from embedding_service.config.settings import get_settings, OPENAI_MODELS

logger = logging.getLogger(__name__)
settings = get_settings()


class ValidationService:
    """
    Servicio de validación para textos de embedding.
    
    Proporciona validaciones específicas por tier y modelo
    con cache de resultados.
    """
    
    def __init__(self, redis_client=None):
        """
        Inicializa servicio.
        
        Args:
            redis_client: Cliente Redis para cache
        """
        self.redis = redis_client
    
    async def validate_texts(
        self,
        texts: List[str],
        model: str,
        context: ExecutionContext,
        raise_error: bool = True
    ) -> Dict[str, Any]:
        """
        Valida textos para generación de embeddings.

        Args:
            texts: Lista de textos
            model: Modelo de embedding
            context: Contexto de ejecución
            raise_error: Si es True, lanza excepciones; si es False, retorna problemas

        Returns:
            Dict con resultados de la validación

        Raises:
            ValueError: Si hay problemas de validación y raise_error=True
        """
        validation_issues = []

        # Validar lista de textos no vacía
        if not texts:
            issue = {
                "type": "empty_list",
                "message": "No se proporcionaron textos"
            }
            if raise_error:
                raise ValueError(issue["message"])
            validation_issues.append(issue)
            return {"valid": False, "issues": validation_issues}

        # Obtener información del modelo y límites base
        model_info = OPENAI_MODELS.get(model, OPENAI_MODELS[settings.default_embedding_model])

        # Validar tamaño de batch
        max_texts = settings.max_texts_per_request
        if len(texts) > max_texts:
            issue = {
                "type": "batch_too_large",
                "message": f"El número de textos ({len(texts)}) excede el límite de {max_texts}",
                "limit": max_texts,
                "actual": len(texts)
            }
            if raise_error:
                raise ValueError(issue["message"])
            validation_issues.append(issue)

        # Validar longitud de cada texto
        max_length = settings.max_text_length
        for i, text in enumerate(texts):
            if not text:  # Text is None or empty
                continue

            if len(text) > max_length:
                issue = {
                    "type": "text_too_long",
                    "message": f"El texto {i} excede el límite de longitud de {max_length} caracteres",
                    "index": i,
                    "limit": max_length,
                    "actual": len(text)
                }
                if raise_error:
                    raise ValueError(issue["message"])
                validation_issues.append(issue)

        # Validar límite de tokens del modelo
        total_estimated_tokens = sum(len(text.split()) for text in texts if text)
        model_max_tokens = model_info["max_tokens"]

        if total_estimated_tokens > model_max_tokens:
            issue = {
                "type": "tokens_exceeded",
                "message": f"Tokens estimados ({total_estimated_tokens}) exceden el límite del modelo {model} ({model_max_tokens})",
                "estimated_tokens": total_estimated_tokens,
                "model_limit": model_max_tokens,
                "model": model
            }
            if raise_error:
                raise ValueError(issue["message"])
            validation_issues.append(issue)

        # Retornar resultado
        return {
            "valid": len(validation_issues) == 0,
            "issues": validation_issues,
            "model_info": model_info
        }

    async def validate_model_compatibility(
        self,
        model: str,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Valida compatibilidad del modelo con el tier.
        
        Args:
            model: Modelo a validar
            context: Contexto de ejecución
            
        Returns:
            Dict con resultado de validación
        """
        model_info = OPENAI_MODELS.get(model)
        if not model_info:
            return {
                "valid": False,
                "message": f"Modelo no soportado: {model}",
                "supported_models": list(OPENAI_MODELS.keys())
            }
        
        # TODO: Implementar restricciones de modelo por tier si es necesario
        # Por ahora todos los tiers pueden usar todos los modelos
        
        return {
            "valid": True,
            "model_info": model_info,
            "tier": context.tenant_tier
        }
    
    async def get_validation_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de validación para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            today = datetime.now().date().isoformat()
            
            # Por ahora retornar estructura básica
            # En el futuro se pueden agregar métricas específicas de validación
            return {
                "date": today,
                "validation_enabled": True,
                "tier_validation": "active"
            }
            
        except (ValueError, TypeError) as e:
            # Captura errores de conversión de tipos o valores incorrectos
            logger.error(f"Error de datos en validation stats: {str(e)}")
            return {"error": "Error en datos de validación", "details": str(e)}
        except ConnectionError as e:
            # Captura errores de conexión específicos
            logger.error(f"Error de conexión al obtener validation stats: {str(e)}")
            return {"error": "Error de conexión en servicio de validación", "details": str(e)}
        except Exception as e:
            # Fallback para otros errores inesperados
            logger.error(f"Error inesperado en validation stats: {str(e)}")
            return {"error": "Error interno en servicio", "details": str(e)}