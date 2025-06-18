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

from ..models.payloads import (
    EmbeddingGeneratePayload,
    EmbeddingGenerateQueryPayload,
    EmbeddingBatchPayload,
    EmbeddingValidatePayload,
    EmbeddingErrorResponse
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
    - embedding.validate: Validación de capacidad
    """
    
    def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
        """
        Inicializa el servicio con sus handlers.
        
        Args:
            app_settings: EmbeddingServiceSettings con la configuración
            service_redis_client: Cliente Redis para enviar acciones a otros servicios
            direct_redis_conn: Conexión Redis directa para operaciones internas
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Inicializar handlers
        self.openai_handler = OpenAIHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.validation_handler = ValidationHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self._logger.info("EmbeddingService inicializado correctamente")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction según su tipo.
        
        Args:
            action: La acción a procesar
            
        Returns:
            Diccionario con los datos de respuesta o None
            
        Raises:
            InvalidActionError: Si el tipo de acción no es soportado
            ValidationError: Si el payload no es válido
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
                
            elif action.action_type == "embedding.validate":
                return await self._handle_validate(action)
                
            else:
                self._logger.warning(f"Tipo de acción no soportado: {action.action_type}")
                raise InvalidActionError(
                    f"Acción '{action.action_type}' no es soportada por Embedding Service"
                )
                
        except ValidationError as e:
            self._logger.error(f"Error de validación en {action.action_type}: {e}")
            # Crear respuesta de error
            error_response = EmbeddingErrorResponse(
                error_type="ValidationError",
                error_message="Error de validación en el payload",
                error_details={"validation_errors": e.errors()},
                action_type=action.action_type
            )
            return error_response.model_dump()
            
        except ExternalServiceError as e:
            self._logger.error(f"Error de servicio externo en {action.action_type}: {e}")
            error_response = EmbeddingErrorResponse(
                error_type="ExternalServiceError",
                error_message=str(e),
                error_details={"original_error": str(e.original_exception) if e.original_exception else None},
                action_type=action.action_type
            )
            return error_response.model_dump()
            
        except Exception as e:
            self._logger.exception(f"Error inesperado procesando {action.action_type}")
            # Re-lanzar para que BaseWorker maneje el error
            raise
    
    async def _handle_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.generate para múltiples textos.
        
        Args:
            action: DomainAction con EmbeddingGeneratePayload
            
        Returns:
            Diccionario con EmbeddingResponse
        """
        # Validar y parsear payload
        payload = EmbeddingGeneratePayload(**action.data)
        
        # Obtener configuración de metadata si existe
        config_overrides = action.metadata or {}
        
        # Primero validar los textos
        validation_result = await self.validation_handler.validate_texts(
            texts=payload.texts,
            model=payload.model or config_overrides.get("model"),
            tenant_id=action.tenant_id
        )
        
        if not validation_result["is_valid"]:
            raise ValueError(f"Validación fallida: {validation_result['messages'][0]}")
        
        # Generar embeddings directamente
        response = await self.openai_handler.generate_embeddings(
            texts=payload.texts,
            model=payload.model,
            dimensions=payload.dimensions,
            encoding_format=payload.encoding_format,
            tenant_id=action.tenant_id,
            trace_id=action.trace_id
        )
        
        # Construir respuesta
        from ..models.payloads import EmbeddingResponse
        embedding_response = EmbeddingResponse(
            embeddings=response["embeddings"],
            model=response["model"],
            dimensions=response["dimensions"],
            total_tokens=response.get("total_tokens", 0),
            processing_time_ms=response.get("processing_time_ms", 0),
            metadata={
                "collection_id": str(payload.collection_id) if payload.collection_id else None,
                "chunk_ids": payload.chunk_ids
            }
        )
        
        # Tracking de métricas
        await self._track_metrics(action, embedding_response)
        
        return embedding_response.model_dump()
    
    async def _handle_generate_query(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.generate_query para consulta única.
        
        Args:
            action: DomainAction con EmbeddingGenerateQueryPayload
            
        Returns:
            Diccionario con EmbeddingQueryResponse
        """
        # Validar y parsear payload
        payload = EmbeddingGenerateQueryPayload(**action.data)
        
        # Obtener el único texto
        query_text = payload.texts[0]
        
        # Generar embedding
        result = await self.openai_handler.generate_embeddings(
            texts=[query_text],
            model=payload.model,
            tenant_id=action.tenant_id,
            trace_id=action.trace_id
        )
        
        embedding = result["embeddings"][0]
        
        from ..models.payloads import EmbeddingQueryResponse
        response = EmbeddingQueryResponse(
            embedding=embedding,
            model=result["model"],
            dimensions=result["dimensions"],
            tokens=result.get("prompt_tokens", 0),
            processing_time_ms=result.get("processing_time_ms", 0)
        )
        
        return response.model_dump()
    
    async def _handle_batch_process(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.batch_process para procesamiento por lotes.
        
        Args:
            action: DomainAction con EmbeddingBatchPayload
            
        Returns:
            Diccionario con EmbeddingBatchResponse
        """
        # Por ahora, implementación básica que delega a generate
        payload = EmbeddingBatchPayload(**action.data)
        
        try:
            # Procesar como generate normal
            generate_action = DomainAction(
                action_id=action.action_id,
                action_type="embedding.generate",
                tenant_id=action.tenant_id,
                session_id=action.session_id,
                task_id=action.task_id,
                user_id=action.user_id,
                origin_service=action.origin_service,
                trace_id=action.trace_id,
                data={
                    "texts": payload.texts,
                    "model": payload.model,
                    "collection_id": payload.collection_id
                }
            )
            
            result = await self._handle_generate(generate_action)
            
            # Convertir a batch response
            from ..models.payloads import EmbeddingBatchResponse, EmbeddingResult
            
            embedding_results = []
            for i, embedding in enumerate(result["embeddings"]):
                embedding_results.append(
                    EmbeddingResult(
                        text_index=i,
                        embedding=embedding,
                        dimensions=result["dimensions"]
                    )
                )
            
            response = EmbeddingBatchResponse(
                batch_id=payload.batch_id,
                status="completed",
                embeddings=embedding_results,
                successful_count=len(embedding_results),
                failed_count=0,
                total_tokens=result.get("total_tokens", 0),
                processing_time_ms=result.get("processing_time_ms", 0),
                metadata=payload.metadata
            )
            
            return response.model_dump()
            
        except Exception as e:
            # En caso de error, devolver respuesta parcial
            from ..models.payloads import EmbeddingBatchResponse
            response = EmbeddingBatchResponse(
                batch_id=payload.batch_id,
                status="failed",
                embeddings=[],
                successful_count=0,
                failed_count=len(payload.texts),
                total_tokens=0,
                processing_time_ms=0,
                errors=[{"error": str(e)}]
            )
            return response.model_dump()
    
    async def _handle_validate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.validate para validación de capacidad.
        
        Args:
            action: DomainAction con EmbeddingValidatePayload
            
        Returns:
            Diccionario con EmbeddingValidationResponse
        """
        # Validar y parsear payload
        payload = EmbeddingValidatePayload(**action.data)
        
        # Usar validation handler
        validation_result = await self.validation_handler.validate_texts(
            texts=payload.texts,
            model=payload.model,
            tenant_id=action.tenant_id
        )
        
        from ..models.payloads import EmbeddingValidationResponse
        response = EmbeddingValidationResponse(
            is_valid=validation_result["is_valid"],
            can_process=validation_result["can_process"],
            text_count=len(payload.texts),
            estimated_tokens=validation_result["estimated_tokens"],
            model_available=validation_result["model_available"],
            messages=validation_result.get("messages", []),
            warnings=validation_result.get("warnings", [])
        )
        
        return response.model_dump()
    
    async def _track_metrics(self, action: DomainAction, response: Any):
        """
        Registra métricas del servicio.
        
        Args:
            action: La acción procesada
            response: La respuesta generada
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
            
            if hasattr(response, "total_tokens"):
                await self.direct_redis_conn.hincrby(metrics_key, "total_tokens", response.total_tokens)
            
            # TTL de 7 días
            await self.direct_redis_conn.expire(metrics_key, 86400 * 7)
            
        except Exception as e:
            self._logger.error(f"Error tracking metrics: {e}")