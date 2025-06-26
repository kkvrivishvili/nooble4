"""
Handler para chat simple con RAG automático.
"""
import logging
import time
from typing import List, Dict, Any
from uuid import UUID, uuid4

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError, AppValidationError
from common.models.chat_models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    EmbeddingRequest,
    TokenUsage
)
from common.models.config_models import RAGConfig

from ..clients.groq_client import GroqClient
from ..clients.vector_client import VectorClient
from ..clients.embedding_client import EmbeddingClient


class SimpleHandler(BaseHandler):
    """Handler para procesamiento de chat simple con RAG automático."""
    
    def __init__(self, app_settings, embedding_client: EmbeddingClient, vector_client: VectorClient, 
                 groq_client: GroqClient, direct_redis_conn=None):
        """
        Inicializa el handler recibiendo todos los clientes como dependencias.
        
        Args:
            app_settings: Configuración del servicio
            embedding_client: Cliente para comunicación con Embedding Service
            vector_client: Cliente para búsqueda vectorial en Qdrant
            groq_client: Cliente para consultas LLM en Groq
            direct_redis_conn: Conexión directa a Redis (opcional)
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Validar que todos los clientes requeridos estén presentes
        if not embedding_client:
            raise ValueError("embedding_client es requerido para SimpleHandler")
        if not vector_client:
            raise ValueError("vector_client es requerido para SimpleHandler")
        if not groq_client:
            raise ValueError("groq_client es requerido para SimpleHandler")
            
        # Asignar los clientes recibidos como dependencias
        self.embedding_client = embedding_client
        self.vector_client = vector_client
        self.groq_client = groq_client
        
        self._logger.info("SimpleHandler inicializado con inyección de clientes")
    
    async def process_simple_query(
        self,
        data: Dict[str, Any],
        query_config: "QueryConfig",  # Config explícita desde DomainAction
        rag_config: "RAGConfig",      # Config explícita desde DomainAction
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID,
        agent_id: UUID,
    ) -> ChatResponse:
        """Procesa una consulta simple con RAG automático."""
        start_time = time.time()
        conversation_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            # Extraer datos limpios del payload (sin configuraciones)
            raw_messages = data.get("messages", [])
            
            # Validar datos requeridos
            if not raw_messages:
                raise AppValidationError("messages es requerido")
            if not query_config:
                raise AppValidationError("query_config es requerido")
            
            # Validaciones específicas de Query Service para query_config
            self._validate_query_config(query_config)
            
            # Validaciones específicas de Query Service para rag_config (si está presente)
            if rag_config:
                self._validate_rag_config(rag_config)
            
            # Convertir raw messages a ChatMessage objects
            messages = []
            for msg_data in raw_messages:
                if isinstance(msg_data, dict):
                    messages.append(ChatMessage.model_validate(msg_data))
                else:
                    messages.append(msg_data)  # Ya es ChatMessage
            
            # Extraer mensaje del usuario (último mensaje con role="user")
            user_message = None
            for msg in reversed(messages):
                if msg.role == "user" and msg.content:
                    user_message = msg.content
                    break
            
            if not user_message:
                raise AppValidationError("No se encontró mensaje del usuario")
            
            self._logger.info(
                f"Procesando simple query: '{user_message[:50]}...'",
                extra={
                    "query_id": conversation_id,
                    "tenant_id": str(tenant_id),
                    "collections": rag_config.collection_ids if rag_config else []
                }
            )
            
            # Copiar mensajes originales para construir el payload final
            final_messages = messages.copy()
            sources = []
            
            # ORQUESTACIÓN RAG: Si hay configuración RAG, hacer búsqueda
            if rag_config:
                # 1. Obtener embedding de la consulta
                embedding_request = EmbeddingRequest(
                    input=user_message,
                    model=rag_config.embedding_model,
                    dimensions=rag_config.embedding_dimensions
                )
                
                query_embedding = await self._get_query_embedding(
                    embedding_request=embedding_request,
                    rag_config=rag_config,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    trace_id=trace_id,
                    agent_id=agent_id
                )
                
                # 2. Buscar en vector store (implementando paralelismo si está habilitado)
                if query_config.enable_parallel_search and len(rag_config.collection_ids) > 1:
                    # Búsqueda paralela cuando hay múltiples colecciones
                    import asyncio
                    
                    self._logger.info(
                        f"Iniciando búsqueda paralela en {len(rag_config.collection_ids)} colecciones", 
                        extra={"tenant_id": str(tenant_id), "parallel_search": True}
                    )
                    
                    # Crear tareas de búsqueda para cada colección
                    search_tasks = []
                    for collection_id in rag_config.collection_ids:
                        task = asyncio.create_task(self.vector_client.search(
                            query_embedding=query_embedding,
                            collection_ids=[collection_id],  # Una sola colección por tarea
                            top_k=rag_config.top_k,
                            similarity_threshold=rag_config.similarity_threshold,
                            tenant_id=str(tenant_id),
                            filters={"document_ids": rag_config.document_ids} if rag_config.document_ids else None
                        ))
                        search_tasks.append(task)
                    
                    # Esperar a que todas las tareas terminen
                    search_results_by_collection = await asyncio.gather(*search_tasks, return_exceptions=True)
                    
                    # Procesar resultados y manejar errores
                    all_search_results = []
                    for i, result in enumerate(search_results_by_collection):
                        if isinstance(result, Exception):
                            self._logger.error(
                                f"Error en búsqueda para colección {rag_config.collection_ids[i]}: {str(result)}", 
                                exc_info=True
                            )
                        else:
                            all_search_results.extend(result)
                    
                    # Ordenar todos los resultados por score de similitud
                    search_results = sorted(
                        all_search_results, 
                        key=lambda x: x.similarity_score if hasattr(x, 'similarity_score') else 0,
                        reverse=True
                    )
                    
                    # Limitar al top_k global
                    search_results = search_results[:rag_config.top_k]
                    
                else:
                    # Búsqueda secuencial tradicional
                    search_results = await self.vector_client.search(
                        query_embedding=query_embedding,
                        collection_ids=rag_config.collection_ids,
                        top_k=rag_config.top_k,
                        similarity_threshold=rag_config.similarity_threshold,
                        tenant_id=str(tenant_id),
                        filters={"document_ids": rag_config.document_ids} if rag_config.document_ids else None
                    )
                
                # 3. FORMATO GROQ: Inyectar contexto como ChatMessage con role="system" antes del último user message
                if search_results:
                    # Usar el límite de tokens configurado para el contexto
                    context = self._build_context(
                        search_results, 
                        max_results=rag_config.top_k,
                        max_context_tokens=query_config.max_context_tokens
                    )
                    
                    # Crear mensaje de contexto siguiendo las mejores prácticas del SDK de Groq
                    context_msg = ChatMessage(
                        role="system",
                        content=f"Información de contexto relevante:\n{context}"
                    )
                    
                    # Insertar el contexto justo antes del último mensaje del usuario para máxima relevancia
                    # Encontrar la posición del último mensaje del usuario
                    user_msg_index = None
                    for i in range(len(final_messages) - 1, -1, -1):
                        if final_messages[i].role == "user":
                            user_msg_index = i
                            break
                    
                    if user_msg_index is not None:
                        # Insertar contexto justo antes del último mensaje del usuario
                        final_messages.insert(user_msg_index, context_msg)
                    else:
                        # Fallback: agregar al final si no se encuentra user message
                        final_messages.append(context_msg)
                    
                    # Extraer sources para la respuesta
                    sources = [UUID(chunk.chunk_id) for chunk in search_results]
            
            # CONSTRUCCIÓN DEL SYSTEM PROMPT desde query_config
            # Si ya hay un system message, lo actualizamos. Si no, lo creamos
            system_prompt = query_config.system_prompt_template
            
            # Verificar si ya existe un system message
            has_system_msg = any(msg.role == "system" for msg in final_messages)
            if not has_system_msg:
                # Agregar system prompt al inicio
                system_msg = ChatMessage(role="system", content=system_prompt)
                final_messages.insert(0, system_msg)
            else:
                # Actualizar el primer system message encontrado
                for msg in final_messages:
                    if msg.role == "system":
                        msg.content = system_prompt
                        break
            
            # LLAMADA A GROQ: Formatear payload según especificaciones oficiales del SDK
            groq_payload = {
                "messages": [{"role": msg.role, "content": msg.content} for msg in final_messages],
                "model": query_config.model.value,  # Usar el enum ChatModel
                "temperature": query_config.temperature,
                "max_tokens": query_config.max_tokens,
                "top_p": query_config.top_p,
                "frequency_penalty": query_config.frequency_penalty,
                "presence_penalty": query_config.presence_penalty,
                "stop": query_config.stop if query_config.stop else None,
            }
            
            # Aplicar configuración dinámica si está especificada en query_config
            groq_client_instance = self.groq_client
            
            # Si hay configuración específica en query_config (timeout o max_retries), usar with_options
            if query_config.timeout is not None or query_config.max_retries is not None:
                options = {}
                if query_config.timeout is not None:
                    options["timeout"] = query_config.timeout
                if query_config.max_retries is not None:
                    options["max_retries"] = query_config.max_retries
                
                # Crear una copia del cliente con las opciones específicas
                groq_client_instance = self.groq_client.with_options(**options)
            
            # Llamar al cliente de Groq (original o con opciones específicas)
            response_text, token_usage = await groq_client_instance.generate(**groq_payload)
            
            # Construir respuesta
            end_time = time.time()
            
            # Crear mensaje de respuesta
            response_message = ChatMessage(
                role="assistant",
                content=response_text
            )
            
            response = ChatResponse(
                conversation_id=UUID(conversation_id),
                message=response_message,
                usage=token_usage,
                sources=sources,
                execution_time_ms=int((end_time - start_time) * 1000)
            )
            
            self._logger.info(
                f"Simple query procesada exitosamente. Tokens: {token_usage.total_tokens}",
                extra={
                    "query_id": conversation_id,
                    "processing_time": response.execution_time_ms,
                    "context_chunks": len(sources)
                }
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error procesando simple query: {str(e)}", exc_info=True)
            if isinstance(e, (AppValidationError, ExternalServiceError)):
                raise
            raise ExternalServiceError(f"Error interno en simple query: {str(e)}")
    
    async def _get_query_embedding(
        self,
        embedding_request: EmbeddingRequest,
        rag_config: RAGConfig,
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        trace_id: UUID,
        agent_id: UUID,
    ) -> List[float]:
        """Obtiene el embedding de la consulta usando el Embedding Service con configuración RAG."""
        # Usar el embedding client refactorizado para obtener el embedding
        response = await self.embedding_client.get_embeddings(
            texts=[embedding_request.input],
            rag_config=rag_config,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            trace_id=trace_id
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
            
        # El response.data debería contener una lista de embeddings para los textos
        embeddings = response.data.get("embeddings", [])
        if not embeddings or len(embeddings) == 0:
            raise ExternalServiceError("No se recibió embedding del Embedding Service")
            
        # Retornamos el primer embedding (corresponde a la consulta)
        return embeddings[0]
    
    def _build_context(self, search_results, max_results: int = 5, max_context_tokens: int = 4000) -> str:
        """Construye el contexto a partir de los resultados de búsqueda respetando límite de tokens."""
        if not search_results:
            return ""
        
        # Importar funciones para tokenización (dentro del método para evitar importación circular)
        import tiktoken
        
        # Inicializar encoder para contar tokens
        try:
            # Este encoder es compatible con la mayoría de modelos modernos
            encoder = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            self._logger.warning(f"No se pudo inicializar tokenizer: {str(e)}. Usando aproximación por caracteres.")
            # Fallback: aproximación simple (4 caracteres ≈ 1 token)
            encoder = None
        
        context_parts = []
        total_tokens = 0
        
        for i, result in enumerate(search_results[:max_results]):
            # Construir información de la fuente
            source_info = f"[Source {i+1}: {result.collection_id}"
            if hasattr(result, 'document_id') and result.document_id:
                source_info += f"/{result.document_id}"
            source_info += f", Score: {result.similarity_score:.3f}]"
            
            # Texto completo del fragmento con metadata
            fragment_text = f"{source_info}\n{result.content}"
            
            # Calcular tokens del fragmento
            fragment_tokens = 0
            if encoder:
                try:
                    fragment_tokens = len(encoder.encode(fragment_text))
                except Exception:
                    # Fallback si falla codificación
                    fragment_tokens = len(fragment_text) // 4
            else:
                # Aproximación simple
                fragment_tokens = len(fragment_text) // 4
            
            # Verificar si excedemos el límite de tokens
            if total_tokens + fragment_tokens > max_context_tokens:
                # Si ya tenemos al menos un fragmento, paramos aquí para no exceder el límite
                if context_parts:
                    self._logger.info(
                        f"Límite de tokens alcanzado ({total_tokens}/{max_context_tokens}). "
                        f"Truncando después de {len(context_parts)} fragmentos."
                    )
                    break
                else:
                    # Si es el primer fragmento y ya excede el límite, truncamos el texto
                    if encoder:
                        try:
                            tokens = encoder.encode(fragment_text)
                            # Truncar tokens y decodificar de vuelta
                            truncated_tokens = tokens[:max_context_tokens - 50]  # Dejar margen
                            fragment_text = encoder.decode(truncated_tokens)
                            fragment_tokens = len(truncated_tokens)
                        except Exception:
                            # Si falla, truncar por caracteres
                            safe_length = (max_context_tokens - 50) * 4
                            fragment_text = fragment_text[:safe_length] + "... [truncado]"
                            fragment_tokens = max_context_tokens - 50
                    else:
                        # Truncar por aproximación de caracteres
                        safe_length = (max_context_tokens - 50) * 4
                        fragment_text = fragment_text[:safe_length] + "... [truncado]"
                        fragment_tokens = max_context_tokens - 50
            
            # Agregar fragmento y actualizar contador de tokens
            context_parts.append(fragment_text)
            total_tokens += fragment_tokens
            
            # Si ya alcanzamos el límite después de agregar, paramos
            if total_tokens >= max_context_tokens:
                self._logger.info(f"Límite de tokens alcanzado ({total_tokens}/{max_context_tokens}). Truncando contexto.")
                break
        
        self._logger.info(f"Contexto construido con {len(context_parts)} fragmentos. Total tokens: {total_tokens}/{max_context_tokens}")
        return "\n\n".join(context_parts)
    
    def _validate_query_config(self, query_config: "QueryConfig"):
        # Validar campos requeridos
        if not query_config.model:
            raise AppValidationError("Modelo de lenguaje es requerido")
        if not query_config.system_prompt_template:
            raise AppValidationError("Plantilla de prompt del sistema es requerida")
        if not query_config.temperature:
            raise AppValidationError("Temperatura es requerida")
        if not query_config.max_tokens:
            raise AppValidationError("Cantidad máxima de tokens es requerida")
        if not query_config.top_p:
            raise AppValidationError("Umbral de probabilidad es requerido")
        if not query_config.frequency_penalty:
            raise AppValidationError("Penalización de frecuencia es requerida")
        if not query_config.presence_penalty:
            raise AppValidationError("Penalización de presencia es requerida")
        
        # Validar valores válidos
        if query_config.temperature < 0 or query_config.temperature > 1:
            raise AppValidationError("Temperatura debe estar entre 0 y 1")
        if query_config.max_tokens < 1:
            raise AppValidationError("Cantidad máxima de tokens debe ser mayor que 0")
        if query_config.top_p < 0 or query_config.top_p > 1:
            raise AppValidationError("Umbral de probabilidad debe estar entre 0 y 1")
        if query_config.frequency_penalty < 0 or query_config.frequency_penalty > 1:
            raise AppValidationError("Penalización de frecuencia debe estar entre 0 y 1")
        if query_config.presence_penalty < 0 or query_config.presence_penalty > 1:
            raise AppValidationError("Penalización de presencia debe estar entre 0 y 1")
    
    def _validate_rag_config(self, rag_config: "RAGConfig"):
        # Validar campos requeridos
        if not rag_config.collection_ids:
            raise AppValidationError("IDs de colección son requeridos")
        if not rag_config.embedding_model:
            raise AppValidationError("Modelo de embedding es requerido")
        if not rag_config.embedding_dimensions:
            raise AppValidationError("Dimensiones de embedding son requeridas")
        if not rag_config.top_k:
            raise AppValidationError("Cantidad de resultados es requerida")
        if not rag_config.similarity_threshold:
            raise AppValidationError("Umbral de similitud es requerido")
        
        # Validar valores válidos
        if rag_config.top_k < 1:
            raise AppValidationError("Cantidad de resultados debe ser mayor que 0")
        if rag_config.similarity_threshold < 0 or rag_config.similarity_threshold > 1:
            raise AppValidationError("Umbral de similitud debe estar entre 0 y 1")