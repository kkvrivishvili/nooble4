"""
Implementación del servicio principal de Embedding Service.

Este servicio extiende BaseService y orquesta la lógica de negocio,
delegando operaciones específicas a los handlers correspondientes.
"""

import logging
from typing import Optional, Dict, Any
from uuid import uuid4

from pydantic import ValidationError

from common.services import BaseService
from common.models import DomainAction
from common.errors.exceptions import InvalidActionError, ExternalServiceError
from common.models.chat_models import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingModel,
    TokenUsage
)

from ..models.payloads import (
    EmbeddingBatchPayload,
    EmbeddingBatchResult
)
from ..handlers.openai_handler import OpenAIHandler
from ..handlers.validation_handler import ValidationHandler


class EmbeddingService(BaseService):
    """
    Servicio principal para generación de embeddings.
    
    Maneja las acciones:
    - embedding.generate: Generación de embeddings para múltiples textos
    - embedding.generate_query: Generación de embedding para consulta única
    - embedding.batch_process: Procesamiento por lotes
    """
    
    def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
        """
        Inicializa el servicio con sus clientes y handlers.
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Inicializar clientes a nivel de servicio
        self.openai_client = OpenAIClient(
            api_key=app_settings.openai_api_key,
            timeout=app_settings.openai_timeout_seconds,
            max_retries=app_settings.openai_max_retries,
            base_url=app_settings.openai_base_url
        )
        
        # Inicializar handlers e inyectar dependencias
        self.openai_handler = OpenAIHandler(
            app_settings=app_settings,
            openai_client=self.openai_client,
            direct_redis_conn=direct_redis_conn
        )
        
        self.validation_handler = ValidationHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self._logger.info("EmbeddingService inicializado correctamente con inyección de cliente")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction según su tipo.
        """
        self._logger.info(
            f"Procesando acción: {action.action_type} ({action.action_id})",
            extra={
                "action_id": str(action.action_id),
                "action_type": action.action_type,
                "tenant_id": action.tenant_id,
                "correlation_id": str(action.correlation_id) if action.correlation_id else None
            }
        )
        
        try:
            # Enrutar según el tipo de acción
            if action.action_type == "embedding.generate":
                return await self._handle_generate(action)
                
            elif action.action_type == "embedding.generate_query":
                return await self._handle_generate_query(action)
                
            elif action.action_type == "embedding.batch_process":
                return await self._handle_batch_process(action)
                
            else:
                self._logger.warning(f"Tipo de acción no soportado: {action.action_type}")
                raise InvalidActionError(
                    f"Acción '{action.action_type}' no es soportada por Embedding Service"
                )
                
        except ValidationError as e:
            self._logger.error(f"Error de validación en {action.action_type}: {e}")
            raise InvalidActionError(f"Error de validación en el payload: {str(e)}")
            
        except ExternalServiceError:
            raise
            
        except Exception as e:
            self._logger.exception(f"Error inesperado procesando {action.action_type}")
            raise ExternalServiceError(f"Error interno en Embedding Service: {str(e)}")
    
    async def _handle_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.generate para múltiples textos.
        """
        # Validar y parsear payload
        payload = EmbeddingRequest.model_validate(action.data)
        
        # Convertir input a lista si es string
        texts = [payload.input] if isinstance(payload.input, str) else payload.input
        
        # Validar los textos
        validation_result = await self.validation_handler.validate_texts(
            texts=texts,
            model=payload.model.value,
            tenant_id=action.tenant_id
        )
        
        if not validation_result["is_valid"]:
            raise ValueError(f"Validación fallida: {validation_result['messages'][0]}")
        
        # Extraer rag_config del DomainAction si existe
        # Esto sigue el flujo arquitectónico correcto donde las configuraciones
        # viajan explícitamente en el DomainAction
        rag_config = action.rag_config.dict() if action.rag_config else None
        
        # Generar embeddings con la configuración dinámica
        result = await self.openai_handler.generate_embeddings(
            texts=texts,
            model=payload.model.value,
            dimensions=payload.dimensions,
            encoding_format=payload.encoding_format,
            tenant_id=action.tenant_id,
            agent_id=action.agent_id,
            trace_id=action.trace_id,
            rag_config=rag_config
        )
        
        # Construir respuesta
        response = EmbeddingResponse(
            embeddings=result["embeddings"],
            model=result["model"],
            dimensions=result["dimensions"],
            usage=TokenUsage(
                prompt_tokens=result.get("prompt_tokens", 0),
                completion_tokens=0,  # Embeddings no tienen completion tokens
                total_tokens=result.get("total_tokens", 0)
            )
        )
        
        return response.model_dump()
    
    async def _handle_generate_query(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.generate_query para consulta única.
        """
        # Validar y parsear payload
        payload = EmbeddingRequest.model_validate(action.data)
        
        # Para query, el input debe ser un string
        if isinstance(payload.input, list):
            query_text = payload.input[0] if payload.input else ""
        else:
            query_text = payload.input
        
        # Extraer configuración RAG del DomainAction
        rag_config = action.rag_config.dict() if action.rag_config else None
        
        # Generar embedding con configuración dinámica
        result = await self.openai_handler.generate_embeddings(
            texts=[query_text],
            model=payload.model.value,
            dimensions=payload.dimensions,
            encoding_format=payload.encoding_format,
            tenant_id=action.tenant_id,
            agent_id=action.agent_id,
            trace_id=action.trace_id,
            rag_config=rag_config
        )
        
        # Para query única, retornar solo el primer embedding
        response_data = {
            "embedding": result["embeddings"][0] if result["embeddings"] else [],
            "model": result["model"],
            "dimensions": result["dimensions"],
            "usage": {
                "prompt_tokens": result.get("prompt_tokens", 0),
                "completion_tokens": 0,
                "total_tokens": result.get("total_tokens", 0)
            }
        }
        
        return response_data
    
    async def _handle_batch_process(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.batch_process para procesamiento por lotes.
        """
        # Validar y parsear payload
        payload = EmbeddingBatchPayload.model_validate(action.data)
        
        try:
            # El modelo ahora es un campo obligatorio en el payload
            model = payload.model
            
            # Extraer configuración RAG del DomainAction
            rag_config = action.rag_config.dict() if action.rag_config else None
            
            # Generar embeddings con configuración dinámica
            result = await self.openai_handler.generate_embeddings(
                texts=payload.texts,
                model=model,
                dimensions=payload.dimensions,
                tenant_id=action.tenant_id,
                agent_id=action.agent_id,
                trace_id=action.trace_id,
                rag_config=rag_config
            )
            
            # Construir respuesta de batch
            batch_result = EmbeddingBatchResult(
                chunk_ids=payload.chunk_ids or [f"idx_{i}" for i in range(len(payload.texts))],
                embeddings=result["embeddings"],
                model=result["model"],
                dimensions=result["dimensions"],
                total_tokens=result.get("total_tokens", 0),
                processing_time_ms=result.get("processing_time_ms", 0),
                status="completed",
                failed_indices=[],
                metadata=payload.metadata
            )
            
            return batch_result.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en batch process: {e}", exc_info=True)
            
            # En caso de error, devolver resultado fallido
            batch_result = EmbeddingBatchResult(
                chunk_ids=payload.chunk_ids or [],
                embeddings=[],
                model=payload.model or "unknown",
                dimensions=0,
                total_tokens=0,
                processing_time_ms=0,
                status="failed",
                failed_indices=list(range(len(payload.texts))),
                metadata=payload.metadata
            )
            
            return batch_result.model_dump()
    
    async def _track_metrics(self, action: DomainAction, response: Any):
        """
        Registra métricas del servicio.
        """
        if not self.direct_redis_conn or not self.app_settings.enable_embedding_tracking:
            return
        
        try:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            
            # Clave de métricas por tenant
            metrics_key = f"embedding_metrics:{action.tenant_id}:{today}"
            
            # Incrementar contadores
            await self.direct_redis_conn.hincrby(metrics_key, "total_requests", 1)
            
            # TTL de 7 días
            await self.direct_redis_conn.expire(metrics_key, 86400 * 7)
            
        except Exception as e:
            self._logger.error(f"Error tracking metrics: {e}")