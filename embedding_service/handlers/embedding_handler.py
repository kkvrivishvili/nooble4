"""
Handler para procesar Domain Actions de embeddings.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from uuid import UUID

from common.errors import ServiceError
from embedding_service.models.actions import EmbeddingGenerateAction, EmbeddingValidateAction
from embedding_service.clients.openai_client import OpenAIClient
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingHandler:
    """
    Handler para procesar acciones de embeddings.
    
    Procesa las siguientes acciones:
    - embedding.generate: Genera embeddings para textos
    - embedding.validate: Valida textos antes de procesar
    """
    
    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        """
        Inicializa el handler.
        
        Args:
            openai_client: Cliente de OpenAI (inyectado para tests)
        """
        self.openai_client = openai_client or OpenAIClient()
    
    async def handle_generate(self, action: EmbeddingGenerateAction) -> Dict[str, Any]:
        """
        Maneja la acción de generación de embeddings.
        
        Args:
            action: EmbeddingGenerateAction con textos a procesar
            
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = time.time()
        
        try:
            # Validar request
            await self._validate_texts(
                texts=action.texts,
                model=action.model
            )
            
            # Generar embeddings
            result = await self.openai_client.generate_embeddings(
                texts=action.texts,
                model=action.model,
                tenant_id=action.tenant_id,
                collection_id=str(action.collection_id) if action.collection_id else None,
                chunk_ids=action.chunk_ids,
                metadata=action.metadata
            )
            
            # Calcular tiempo de procesamiento
            processing_time = time.time() - start_time
            
            # Preparar resultado
            return {
                "success": True,
                "embeddings": result["embeddings"],
                "model": result["model"],
                "dimensions": result["dimensions"],
                "total_tokens": result["usage"].get("total_tokens", 0),
                "processing_time": processing_time,
            }
            
        except Exception as e:
            logger.error(f"Error en handle_generate: {str(e)}")
            processing_time = time.time() - start_time
            
            # Estructurar error para devolución controlada
            error_msg = str(e)
            error_type = "ValidationError" if isinstance(e, ServiceError) else "ProcessingError"
            
            return {
                "success": False,
                "error": {
                    "message": error_msg,
                    "type": error_type
                },
                "processing_time": processing_time
            }
    
    async def handle_validate(self, action: EmbeddingValidateAction) -> Dict[str, Any]:
        """
        Maneja la acción de validación de textos.
        
        Args:
            action: EmbeddingValidateAction con textos a validar
            
        Returns:
            Dict con resultado de la validación
        """
        try:
            # Realizar validaciones
            model = action.model or settings.default_embedding_model
            validation_results = await self._validate_texts(
                texts=action.texts,
                model=model,
                raise_error=False
            )
            
            return {
                "success": True,
                "validation_results": validation_results,
                "model": model,
            }
            
        except Exception as e:
            logger.error(f"Error en handle_validate: {str(e)}")
            
            return {
                "success": False,
                "error": {
                    "message": str(e),
                    "type": "ValidationError"
                }
            }
    
    async def _validate_texts(
        self, 
        texts: List[str],
        model: Optional[str] = None,
        raise_error: bool = True
    ) -> Dict[str, Any]:
        """
        Valida los textos para generación de embeddings.
        
        Args:
            texts: Lista de textos
            model: Modelo de embedding
            raise_error: Si es True, lanza excepciones; si es False, retorna problemas
            
        Returns:
            Dict con resultados de la validación
        Raises:
            ServiceError: Si hay problemas de validación
        """
        model = model or settings.default_embedding_model
        validation_issues = []
        
        # Validar lista de textos no vacía
        if not texts:
            if raise_error:
                raise ServiceError("No se proporcionaron textos")
            else:
                validation_issues.append({
                    "type": "empty_list",
                    "message": "No se proporcionaron textos"
                })
                return {"valid": False, "issues": validation_issues}
        
        # Validar tamaño de batch
        if len(texts) > settings.max_batch_size:
            if raise_error:
                raise ServiceError(
                    f"Batch excede el límite de {settings.max_batch_size} textos"
                )
            else:
                validation_issues.append({
                    "type": "batch_too_large",
                    "message": f"Batch excede el límite de {settings.max_batch_size} textos",
                    "limit": settings.max_batch_size,
                    "actual": len(texts)
                })
        
        # Validar longitud de cada texto
        for i, text in enumerate(texts):
            if not text:  # Text is None or empty
                continue
                
            if len(text) > settings.max_text_length:
                if raise_error:
                    raise ServiceError(
                        f"Texto {i} excede el límite de {settings.max_text_length} caracteres"
                    )
                else:
                    validation_issues.append({
                        "type": "text_too_long",
                        "message": f"Texto {i} excede el límite de {settings.max_text_length} caracteres",
                        "index": i,
                        "limit": settings.max_text_length,
                        "actual": len(text)
                    })
        
        # Retornar resultado
        if validation_issues and raise_error:
            raise ServiceError(f"Validación fallida: {validation_issues[0]['message']}")
            
        return {
            "valid": len(validation_issues) == 0,
            "issues": validation_issues
        }
