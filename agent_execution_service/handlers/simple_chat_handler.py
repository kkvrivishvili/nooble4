"""
Handler para chat simple con RAG.
"""
import logging
import time
from typing import Dict, Any, Optional
from common.handlers.base_handler import BaseHandler
from common.config.base_settings import CommonAppSettings
from common.errors.exceptions import ExternalServiceError

from ..clients.query_client import QueryClient
from ..clients.llm_client import LLMClient
from ..models.payloads import ExecuteSimpleChatPayload, ExecuteSimpleChatResponse

logger = logging.getLogger(__name__)

class SimpleChatHandler(BaseHandler):
    """Handler para modo simple: Chat + RAG."""

    def __init__(self, app_settings: CommonAppSettings):
        super().__init__(app_settings)
        
        # Inicializar cliente Query Service
        query_url = getattr(app_settings, 'query_service_url', 'http://localhost:8002')
        self.query_client = QueryClient(base_url=query_url)
        
        # Cliente LLM (se inicializa cuando sea necesario)
        self.llm_client: Optional[LLMClient] = None

    async def setup_llm_client(self, provider: str, api_key: str):
        """Configura el cliente LLM."""
        if self.llm_client:
            await self.llm_client.close()
        
        self.llm_client = LLMClient(provider=provider, api_key=api_key)
        self._logger.info(f"Cliente LLM configurado para proveedor: {provider}")

    async def execute_simple_chat(
        self,
        payload: ExecuteSimpleChatPayload,
        tenant_id: str,
        session_id: str
    ) -> ExecuteSimpleChatResponse:
        """
        Ejecuta chat simple con RAG delegando al Query Service.
        """
        start_time = time.time()
        
        try:
            self._logger.info(
                f"Iniciando chat simple para tenant {tenant_id}, session {session_id}"
            )

            if payload.use_rag:
                # Delegar completamente al Query Service para RAG
                self._logger.debug("Usando RAG - delegando al Query Service")
                
                result = await self.query_client.query_with_rag(
                    query_text=payload.user_message,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    collection_ids=payload.collection_ids,
                    llm_config=payload.llm_config.model_dump() if payload.llm_config else None
                )
                
                response_text = result.get("response", "")
                sources = result.get("sources", [])
                context = result.get("context", "")
                tokens_used = result.get("tokens_used")
                
            else:
                # Chat directo sin RAG
                self._logger.debug("Chat directo sin RAG")
                
                if not self.llm_client:
                    raise ExternalServiceError("Cliente LLM no configurado para chat directo")
                
                # Construir mensajes
                messages = []
                
                if payload.system_prompt:
                    messages.append({"role": "system", "content": payload.system_prompt})
                
                # Agregar historial de conversación
                for msg in payload.conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})
                
                # Agregar mensaje del usuario
                messages.append({"role": "user", "content": payload.user_message})
                
                # Configuración LLM
                llm_config = payload.llm_config or {}
                model = getattr(llm_config, 'model_name', 'llama-3.3-70b-versatile')
                temperature = getattr(llm_config, 'temperature', 0.7)
                max_tokens = getattr(llm_config, 'max_tokens', 1024)
                
                # Llamar al LLM
                llm_response = await self.llm_client.generate_response(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                response_text = llm_response["choices"][0]["message"]["content"]
                sources = []
                context = None
                tokens_used = llm_response.get("usage", {}).get("total_tokens")

            execution_time = time.time() - start_time

            self._logger.info(
                f"Chat simple completado en {execution_time:.2f}s, "
                f"tokens: {tokens_used or 'N/A'}"
            )

            return ExecuteSimpleChatResponse(
                response=response_text,
                sources_used=sources,
                rag_context=context,
                execution_time_seconds=execution_time,
                tokens_used=tokens_used
            )

        except ExternalServiceError:
            # Re-lanzar errores de servicios externos sin modificar
            raise
        except Exception as e:
            self._logger.error(f"Error en chat simple: {e}")
            raise ExternalServiceError(
                f"Error interno en chat simple: {str(e)}",
                original_exception=e
            )

    async def cleanup(self):
        """Limpia recursos del handler."""
        try:
            if hasattr(self.query_client, 'close'):
                await self.query_client.close()
            
            if self.llm_client:
                await self.llm_client.close()
                
            self._logger.debug("SimpleChatHandler limpiado correctamente")
        except Exception as e:
            self._logger.error(f"Error limpiando SimpleChatHandler: {e}")