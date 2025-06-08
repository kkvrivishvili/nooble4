# Análisis de Handlers en Servicios Nooble4

Este documento contiene un análisis detallado de los handlers en cada servicio del sistema Nooble4, con el objetivo de:

1. Identificar patrones comunes
2. Detectar problemas de inicialización asíncrona
3. Proponer un modelo de `BaseHandler` para estandarización

## Contenido

- [Agent Orchestrator Service](#agent-orchestrator-service)
- [Agent Execution Service](#agent-execution-service)
- [Agent Management Service](#agent-management-service) 
- [Query Service](#query-service)
- [Embedding Service](#embedding-service)
- [Conversation Service](#conversation-service)
- [Propuesta de BaseHandler](#propuesta-de-basehandler)

## Agent Orchestrator Service

El Agent Orchestrator Service actúa como intermediario entre los clientes frontend y el Agent Execution Service, permitiendo comunicación bidireccional en tiempo real mediante WebSockets.

### Handlers Implementados

#### 1. CallbackHandler

**Archivo:** `agent_orchestrator_service/handlers/callback_handler.py`

**Responsabilidad:** Procesar callbacks desde Agent Execution Service y enviar respuestas/errores a través de WebSockets.

**Inicialización:**
```python
def __init__(self, websocket_manager: WebSocketManager, redis_client=None):
    self.websocket_manager = websocket_manager
    self.redis = redis_client
```

**Métodos principales:**
- `async handle_execution_callback(self, action: DomainAction) -> Dict[str, Any]`
- `async _handle_successful_execution(self, callback: ExecutionCallbackAction)`
- `async _handle_failed_execution(self, callback: ExecutionCallbackAction)`
- `async _track_callback_performance(self, callback, start_time)`
- `async get_callback_stats(self, tenant_id: str) -> Dict[str, Any]`

**Observaciones:**
- No requiere inicialización asíncrona
- Combina manejo de callbacks con lógica de métricas
- Dependencia directa de WebSocketManager
- Asume conexión exitosa a Redis para métricas

#### 2. ContextHandler

**Archivo:** `agent_orchestrator_service/handlers/context_handler.py`

**Responsabilidad:** Crear y validar contextos de ejecución desde headers HTTP.

**Inicialización:**
```python
def __init__(self, redis_client=None, db_client=None):
    self.redis = redis_client
    self.db = db_client
    self.validation_cache_ttl = 300
    self.valid_tiers = {...}
    self.valid_context_types = {...}
```

**Métodos principales:**
- `async create_context_from_headers(...) -> ExecutionContext`
- `async _validate_required_fields(...)`
- `async _validate_access(...)`
- `async _check_database_access(...) -> bool`
- `async invalidate_cache(self, tenant_id: str, agent_id: str)`
- `async get_cache_stats(self) -> Dict[str, Any]`

**Observaciones:**
- No requiere inicialización asíncrona explícita
- Implementa cache de validaciones en Redis
- Manejo de errores con HTTPException (acoplado a FastAPI)
- Usa factory function `get_context_handler` para instanciación

#### 3. WebSocketHandler y ChatHandler

**Archivo:** `agent_orchestrator_service/handlers/handlers_domain_actions.py`

**Responsabilidad:** Manejar acciones específicas para WebSocket y procesamiento de chat.

**Inicialización WebSocketHandler:**
```python
def __init__(self, connection_manager):
    self.connection_manager = connection_manager
```

**Métodos principales WebSocketHandler:**
- `async handle_send(self, action: WebSocketSendAction) -> Dict[str, Any]`
- `async handle_broadcast(self, action: WebSocketBroadcastAction) -> Dict[str, Any]`

**Inicialización ChatHandler:**
```python
def __init__(self, chat_service):
    self.chat_service = chat_service
```

**Métodos principales ChatHandler:**
- `async handle_process(self, action: ChatProcessAction) -> Dict[str, Any]`
- `async handle_status(self, action: ChatStatusAction) -> Dict[str, Any]`
- `async handle_cancel(self, action: ChatCancelAction) -> Dict[str, Any]`

**Observaciones:**
- Sin inicialización asíncrona
- Patrones similares: inyección de dependencias en constructor, manejo de errores try/except
- Cada método handle_* tiene su propio patrón de manejo de errores con retorno de diccionarios similares
- Método handle_* por cada tipo de acción
- Sin factory function

### Patrones Identificados en Agent Orchestrator

1. **Inyección de Dependencias**: Todos los handlers reciben sus dependencias en el constructor.
2. **Factory Functions**: Solo ContextHandler utiliza factory function para instanciación asíncrona.
3. **Consistencia de Métodos**: Todos utilizan métodos `handle_*` para procesar diferentes tipos de acciones.
4. **Manejo de Errores**: Combinación de try/except con HTTPException (para API) y devolución de diccionarios de error (para Domain Actions).
5. **Métricas**: Varios implementan métodos `get_*_stats()` para estadísticas.
6. **Cache**: Implementación ad-hoc de cache en Redis.

## Agent Execution Service

El Agent Execution Service es responsable de procesar la ejecución de agentes conversacionales utilizando LangChain, integrando múltiples servicios y gestionando herramientas y callbacks.

### Handlers Implementados

#### 1. AgentExecutionHandler

**Archivo:** `agent_execution_service/handlers/agent_execution_handler.py`

**Responsabilidad:** Ejecutar agentes con LangChain, gestionar timeouts y límites por tier.

**Inicialización:**
```python
def __init__(self, context_handler: ExecutionContextHandler, redis_client=None):
    self.context_handler = context_handler
    self.redis = redis_client
    self.agent_executor = AgentExecutor(context_handler, redis_client)
```

**Métodos principales:**
- `async handle_agent_execution(self, action: AgentExecutionAction) -> Dict[str, Any]`
- `def _get_execution_timeout(self, tenant_tier: str, custom_timeout: Optional[int]) -> int`
- `async _save_conversation_messages(...)`
- `async _track_execution_metrics(...)`
- `async get_execution_stats(self, tenant_id: str)`

**Observaciones:**
- No tiene inicialización asíncrona explícita
- Inyección de dependencias del context_handler
- Manejo de timeouts según tier del tenant
- Tracking de métricas de ejecución
- Estructura de respuesta estandarizada con manejo de errores consistente

#### 2. ExecutionContextHandler

**Archivo:** `agent_execution_service/handlers/context_handler.py`

**Responsabilidad:** Resolver y validar contextos de ejecución, preparar entorno para LangChain.

**Inicialización:**
```python
def __init__(self, redis_client=None):
    self.redis = redis_client
    self.agent_config_cache_ttl = 300
    self.agent_management_client = AgentManagementClient()
    self.conversation_client = ConversationServiceClient()
```

**Métodos principales:**
- `async resolve_execution_context(self, context_dict: Dict[str, Any]) -> ExecutionContext`
- `async get_agent_configuration(self, agent_id: str, tenant_id: str) -> Dict[str, Any]`
- `async validate_execution_permissions(self, context: ExecutionContext, agent_config: Dict[str, Any])`
- `async get_conversation_history(...)`
- `async invalidate_agent_cache(self, agent_id: str, tenant_id: str)`

**Observaciones:**
- No tiene inicialización asíncrona explícita pero crea clientes externos
- Usa cache de configuraciones en Redis con TTL configurable
- Validación de permisos y límites por tier
- Manejo de errores usando excepciones (ValueError) con mensajes descriptivos

#### 3. ExecutionCallbackHandler

**Archivo:** `agent_execution_service/handlers/execution_callback_handler.py`

**Responsabilidad:** Envío de callbacks a Agent Orchestrator para resultados de ejecución.

**Inicialización:**
```python
def __init__(self, queue_manager: DomainQueueManager, redis_client=None):
    self.queue_manager = queue_manager
    self.redis = redis_client
```

**Métodos principales:**
- `async send_success_callback(...) -> bool`
- `async send_error_callback(...) -> bool` 
- `async _track_callback_sent(self, task_id, tenant_id, result_type) -> None`
- `async _format_execution_result(self, execution_result: ExecutionResult) -> Dict[str, Any]`
- `def _extract_token_usage(self, execution_result: ExecutionResult) -> int`

#### 4. QueryCallbackHandler y EmbeddingCallbackHandler

**Archivos:** 
- `agent_execution_service/handlers/query_callback_handler.py`
- `agent_execution_service/handlers/embedding_callback_handler.py`

**Responsabilidad:** Procesar callbacks de servicios externos y sincronización asíncrona.

**Inicialización:**
```python
def __init__(self):
    # Diccionario para almacenar resultados de callbacks
    self._pending_callbacks = {}
    
    # Eventos para sincronizar espera
    self._callback_events = {}
```

**Métodos principales QueryCallbackHandler:**
- `async handle_query_callback(self, action: DomainAction) -> Dict[str, Any]`
- `async wait_for_query_result(self, task_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]`
- `async wait_for_search_result(self, task_id: str, timeout: float = 15.0) -> Optional[Dict[str, Any]]`

**Métodos principales EmbeddingCallbackHandler:**
- `async handle_embedding_callback(self, action: DomainAction) -> Dict[str, Any]`
- `async wait_for_embedding_result(self, task_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]`

**Observaciones:**
- Casi idénticos en estructura y patrón
- Comentarios TODO explícitos mencionando la necesidad de un BaseCallbackHandler
- Ambos usan diccionarios (_pending_callbacks) combinados con asyncio.Event (_callback_events) para sincronización
- Implementan mecanismos similares para manejo de timeouts
- Tienen métodos especializados wait_for_* con parámetros de timeout y limpieza de recursos
- Manejan errores propagando excepciones en vez de retornar diccionarios de errores
- Se encuentran entre los casos más claros para refactorización con una clase base

### Patrones Identificados en Agent Execution

1. **Duplicación de Código**: QueryCallbackHandler y EmbeddingCallbackHandler tienen implementación casi idéntica.
2. **Sincronización Asíncrona**: Uso de asyncio.Event para sincronizar callbacks.
3. **Inyección de Dependencias**: Similar a Orchestrator, todos reciben dependencias en constructor.
4. **Cache**: Implementación ad-hoc de cache en algunos handlers.
5. **Tracking de Métricas**: Diferentes implementaciones para métricas en Redis.
6. **Manejo de Estados**: Uso de diccionarios internos para seguimiento de estados.
7. **Validación de Modelos**: Conversión explícita de Domain Actions a tipos específicos.

## Query Service

El Query Service es un componente dedicado a resolver consultas en lenguaje natural mediante el flujo RAG (Retrieval-Augmented Generation) con búsqueda vectorial e integración con LLM.

### Handlers Implementados

#### 1. QueryContextHandler

**Archivo:** `query_service/handlers/context_handler.py`

**Responsabilidad:** Resolver y validar contextos para consultas RAG y búsquedas vectoriales.

**Inicialización:**
```python
def __init__(self, redis_client=None, supabase_client=None):
    self.redis = redis_client
    self.supabase = supabase_client
    self.collection_config_cache_ttl = 600
```

**Métodos principales:**
- `async resolve_query_context(self, context_dict: Dict[str, Any]) -> ExecutionContext`
- `async validate_query_limits(self, context: ExecutionContext)`
- `async load_collection_config(self, collection_id: str) -> Dict[str, Any]`

**Observaciones:**
- No tiene inicialización asíncrona explícita
- Usa factory function `get_query_context_handler` para instanciación
- Implementa cache de configuraciones en Redis
- Patrón similar a otros ContextHandlers

#### 2. QueryHandler

**Archivo:** `query_service/handlers/query_handler.py`

**Responsabilidad:** Procesar acciones de consulta RAG y búsqueda de documentos.

**Inicialización:**
```python
def __init__(self, context_handler: QueryContextHandler, redis_client=None):
    self.context_handler = context_handler
    self.redis = redis_client
    self.vector_search_service = VectorSearchService(redis_client)
    self.rag_processor = RAGProcessor(self.vector_search_service, redis_client)
```

**Métodos principales:**
- `async handle_query_generate(self, action: QueryGenerateAction) -> Dict[str, Any]`
- `async handle_search_docs(self, action: SearchDocsAction) -> Dict[str, Any]`
- `async _track_query_metrics(...)`

**Observaciones:**
- No tiene inicialización asíncrona explícita pero crea servicios que podrían requerirla
- Dependencia directa de QueryContextHandler
- Sigue patrón handle_* para procesar diferentes acciones

#### 3. QueryCallbackHandler

**Archivo:** `query_service/handlers/query_callback_handler.py`

**Responsabilidad:** Envío de callbacks de consultas completadas a servicios solicitantes.

**Inicialización:**
```python
def __init__(self, queue_manager: DomainQueueManager, redis_client=None):
    self.queue_manager = queue_manager
    self.redis = redis_client
```

**Métodos principales:**
- `async send_query_success_callback(...) -> bool`
- `async send_query_error_callback(...) -> bool`
- `async _track_callback_metrics(...)`

**Observaciones:**
- No requiere inicialización asíncrona
- Muy similar a ExecutionCallbackHandler del Agent Execution Service
- Enfocado en envío de callbacks y métricas

#### 4. EmbeddingCallbackHandler (en Query Service)

**Archivo:** `query_service/handlers/embedding_callback_handler.py`

**Responsabilidad:** Procesar callbacks del servicio de embeddings en el flujo de consulta RAG.

**Inicialización:**
```python
def __init__(self):
    self._pending_callbacks = {}
    self._callback_events = {}
```

**Observaciones:**
- Estructura idéntica al EmbeddingCallbackHandler del Agent Execution Service
- Incluye TODOs explícitos sobre refactorización y la necesidad de un BaseCallbackHandler
- Evidente duplicación de código entre servicios

### Patrones Identificados en Query Service

1. **Tipos de Handlers**: Claras divisiones entre manejadores de contexto, acciones principales y callbacks.
2. **Inyección de Dependencias**: Patrones consistentes con otros servicios.
3. **Duplicación**: Alta similitud entre handlers de callbacks entre servicios.

## Embedding Service

El Embedding Service es responsable de la generación de embeddings (vectores) para textos utilizando modelos como OpenAI, con procesamiento por lotes y validación por tier.

### Handlers Implementados

#### 1. EmbeddingContextHandler

**Archivo:** `embedding_service/handlers/context_handler.py`

**Responsabilidad:** Resolver y validar contextos para generación de embeddings.

**Inicialización:**
```python
def __init__(self, redis_client=None):
    self.redis = redis_client
    self.validation_cache_ttl = 300
```

**Métodos principales:**
- `async resolve_embedding_context(self, context_dict: Dict[str, Any]) -> ExecutionContext`
- `async validate_embedding_limits(self, context: ExecutionContext)`

**Observaciones:**
- Misma estructura que otros ContextHandlers
- Usa factory function `get_embedding_context_handler`

#### 2. EmbeddingHandler

**Archivo:** `embedding_service/handlers/embedding_handler.py`

**Responsabilidad:** Procesar acciones de generación de embeddings.

**Inicialización:**
```python
def __init__(self, context_handler: EmbeddingContextHandler, redis_client=None):
    self.context_handler = context_handler
    self.redis = redis_client
    self.validation_service = ValidationService(redis_client)
    self.embedding_processor = EmbeddingProcessor(self.validation_service, redis_client)
```

**Observaciones:**
- Estructura idéntica a QueryHandler
- No tiene inicialización asíncrona explícita pero crea servicios

#### 3. EmbeddingCallbackHandler (en Embedding Service)

**Archivo:** `embedding_service/handlers/embedding_callback_handler.py`

**Responsabilidad:** Envío de callbacks de embeddings completados.

**Inicialización:**
```python
def __init__(self, queue_manager: DomainQueueManager, redis_client=None):
    self.queue_manager = queue_manager
    self.redis = redis_client
```

**Observaciones:**
- Estructura similar a QueryCallbackHandler
- Duplicación de código entre servicios para funciones similares

## Conversation Service

El Conversation Service gestiona el historial de conversaciones y contexto para agentes, a través de un handler unificado.

### Handlers Implementados

#### 1. ConversationHandler

**Archivo:** `conversation_service/handlers/conversation_handler.py`

**Responsabilidad:** Manejar acciones de conversación como guardado de mensajes y recuperación de contexto.

**Inicialización:**
```python
def __init__(self, conversation_service: ConversationService):
    self.conversation_service = conversation_service
```

**Métodos principales:**
- `async handle_save_message(self, action: DomainAction) -> Dict[str, Any]`
- `async handle_get_context(self, action: DomainAction) -> Dict[str, Any]`
- `async handle_session_closed(self, action: DomainAction) -> Dict[str, Any]`

**Observaciones:**
- Implementación más simple que otros handlers
- No tiene inicialización asíncrona
- Sigue patrón handle_* para diferentes acciones
- Delegación directa a un servicio sin lógica compleja

## Propuesta de BaseHandler

Después de analizar los handlers en todos los servicios, se identifican claros patrones y oportunidades para crear una arquitectura estandarizada de handlers que resuelva los problemas de inicialización asíncrona, elimine código duplicado y proporcione interfaces consistentes.

### Problemas Identificados

1. **Duplicación de Código**: Existe una significativa duplicación de lógica entre servicios, especialmente en handlers de callback y context.

2. **Inicialización Asíncrona Inconsistente**: Algunos handlers crean dependencias en el constructor que podrían requerir inicialización asíncrona.

3. **Variación en Manejo de Errores**: Combinación inconsistente de excepciones y diccionarios de error.

4. **Diferencias en Métricas y Tracking**: Cada servicio implementa su propio sistema de métricas.

5. **Acoplamiento a Frameworks Específicos**: Algunos handlers dependen directamente de FastAPI (HTTPExceptions).

### Arquitectura Propuesta

#### 1. Jerarquía de Clases Base

```
BaseHandler
  |
  +-- BaseContextHandler
  |     |
  |     +-- OrchestratorContextHandler
  |     +-- ExecutionContextHandler
  |     +-- QueryContextHandler
  |     +-- EmbeddingContextHandler
  |
  +-- BaseActionHandler
  |     |
  |     +-- WebSocketHandler
  |     +-- ChatHandler
  |     +-- AgentExecutionHandler
  |     +-- QueryHandler
  |     +-- EmbeddingHandler
  |     +-- ConversationHandler
  |
  +-- BaseCallbackHandler
        |
        +-- CallbackSenderHandler (para enviar callbacks)
        |     |
        |     +-- ExecutionCallbackHandler
        |     +-- QueryCallbackHandler (de Query Service)
        |     +-- EmbeddingCallbackHandler (de Embedding Service)
        |
        +-- CallbackReceiverHandler (para recibir/procesar callbacks)
              |
              +-- OrchestratorCallbackHandler (antes CallbackHandler de Orchestrator)
              +-- QueryCallbackHandler (de Agent Execution)
              +-- EmbeddingCallbackHandler (de Agent Execution)
```

#### 2. Propuesta de BaseHandler

```python
class BaseHandler:
    """Clase base para todos los handlers del sistema."""
    
    def __init__(self, *args, **kwargs):
        """Inicialización básica del handler."""
        self._initialized = False
        self._logger = logging.getLogger(self.__class__.__name__)
    
    async def initialize(self) -> None:
        """Inicialización asíncrona explícita."""
        if self._initialized:
            return
            
        await self._async_init()
        self._initialized = True
    
    async def _async_init(self) -> None:
        """Implementación específica de inicialización asíncrona."""
        # Para ser implementado por subclases
        pass
    
    async def _check_initialized(self) -> None:
        """Verifica que el handler esté inicializado."""
        if not self._initialized:
            await self.initialize()
    
    def _create_success_response(self, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Crea respuesta estándar de éxito."""
        response = {"success": True}
        if data:
            response.update(data)
        return response
    
    def _create_error_response(self, error: Exception) -> Dict[str, Any]:
        """Crea respuesta estándar de error."""
        error_type = type(error).__name__
        error_message = str(error)
        
        self._logger.error(f"Error en {self.__class__.__name__}: {error_message}")
        
        # Mapeo de tipos de error a códigos específicos
        error_type_map = {
            "ValueError": "validation_error",
            "KeyError": "missing_key",
            "TimeoutError": "timeout",
            "ConnectionError": "connection_error"
        }
        
        error_code = error_type_map.get(error_type, "processing_error")
        
        return {
            "success": False,
            "error": {
                "type": error_code,
                "message": error_message
            }
        }
    
    async def track_metric(self, metric_name: str, value: Any, **tags) -> None:
        """API unificada para tracking de métricas."""
        # Para ser implementado por subclases o middleware
        pass
```

#### 3. Propuesta de BaseContextHandler

```python
class BaseContextHandler(BaseHandler):
    """Clase base para manejadores de contexto."""
    
    def __init__(self, redis_client=None, db_client=None, **kwargs):
        super().__init__(**kwargs)
        self.redis = redis_client
        self.db = db_client
        self.cache_ttl = 300  # 5 minutos por defecto
    
    async def resolve_context(self, context_dict: Dict[str, Any]) -> ExecutionContext:
        """Método común para resolver contextos."""
        await self._check_initialized()
        
        try:
            # Crear contexto desde diccionario
            context = ExecutionContext.from_dict(context_dict)
            
            # Validar contexto
            await self._validate_context(context)
            
            return context
            
        except Exception as e:
            raise ValueError(f"Error resolviendo contexto: {str(e)}")
    
    async def _validate_context(self, context: ExecutionContext) -> None:
        """Validación específica del contexto."""
        # Para implementar en subclases
        pass
    
    async def get_from_cache(self, key: str) -> Optional[Any]:
        """Obtener valor desde cache."""
        if not self.redis:
            return None
            
        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except:
                return value
        return None
    
    async def set_in_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Guardar valor en cache."""
        if not self.redis:
            return False
            
        ttl = ttl or self.cache_ttl
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self.redis.setex(key, ttl, value)
            return True
        except Exception as e:
            self._logger.error(f"Error cacheando {key}: {str(e)}")
            return False
```

#### 4. Propuesta de BaseCallbackHandler

```python
class BaseCallbackHandler(BaseHandler):
    """Clase base para manejadores de callbacks."""
    
    def __init__(self, redis_client=None, **kwargs):
        super().__init__(**kwargs)
        self.redis = redis_client
        
    async def track_callback_metric(self, callback_type: str, success: bool, 
                                   tenant_id: str, processing_time: float):
        """Registra métrica de callback."""
        if not self.redis:
            return
            
        try:
            # Base para tracking de callbacks
            key_prefix = f"metrics:callbacks:{callback_type}:{tenant_id}"
            timestamp = datetime.utcnow().timestamp()
            
            # Contador general
            await self.redis.hincrby(f"{key_prefix}:counts", "total", 1)
            
            # Contador de éxito/error
            result_type = "success" if success else "error"
            await self.redis.hincrby(f"{key_prefix}:counts", result_type, 1)
            
            # Tiempos de procesamiento
            await self.redis.lpush(f"{key_prefix}:times", processing_time)
            await self.redis.ltrim(f"{key_prefix}:times", 0, 99)  # Mantener últimas 100
            
        except Exception as e:
            self._logger.error(f"Error tracking callback metric: {str(e)}")
```

#### 5. Propuesta de CallbackReceiverHandler

```python
class CallbackReceiverHandler(BaseCallbackHandler):
    """Base para handlers que reciben y procesan callbacks."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pending_callbacks = {}
        self._callback_events = {}
    
    async def register_callback_wait(self, task_id: str) -> None:
        """Registra espera de callback."""
        self._callback_events[task_id] = asyncio.Event()
    
    async def handle_callback(self, action: DomainAction) -> Dict[str, Any]:
        """Procesa un callback genérico."""
        await self._check_initialized()
        start_time = time.time()
        task_id = action.task_id
        
        try:
            # Procesar callback según tipo
            if action.status == "completed":
                result = await self._process_success_callback(action)
            elif action.status == "failed":
                result = await self._process_error_callback(action)
            else:
                raise ValueError(f"Estado de callback desconocido: {action.status}")
            
            # Almacenar resultado
            self._pending_callbacks[task_id] = result
            
            # Disparar evento si hay alguien esperando
            if task_id in self._callback_events:
                self._callback_events[task_id].set()
                
            # Tracking
            await self.track_callback_metric(
                callback_type=self._get_callback_type(),
                success=True,
                tenant_id=action.tenant_id,
                processing_time=time.time() - start_time
            )
            
            return {"success": True, "task_id": task_id}
            
        except Exception as e:
            return await self.handle_error(e)
    
    async def wait_for_callback(self, task_id: str, timeout: float = 30.0) -> Dict[str, Any]:
        """Espera por un callback específico."""
        # Si ya tenemos el resultado, devolverlo inmediatamente
        if task_id in self._pending_callbacks:
            return self._pending_callbacks[task_id]
        
        # Registrar evento si no existe
        if task_id not in self._callback_events:
            self._callback_events[task_id] = asyncio.Event()
        
        # Esperar por el evento con timeout
        try:
            await asyncio.wait_for(self._callback_events[task_id].wait(), timeout=timeout)
            return self._pending_callbacks.get(task_id, {"error": "Callback no encontrado"})
        except asyncio.TimeoutError:
            return {"error": "Timeout esperando callback"}
    
    async def _process_success_callback(self, action: DomainAction) -> Dict[str, Any]:
        """Procesa callback exitoso (implementar en subclases)."""
        raise NotImplementedError()
    
    async def _process_error_callback(self, action: DomainAction) -> Dict[str, Any]:
        """Procesa callback fallido (implementar en subclases)."""
        raise NotImplementedError()
    
    async def _get_callback_type(self) -> str:
        """Devuelve tipo de callback para métricas."""
        return "generic"
```

### Recomendaciones de Implementación

1. **Implementación Gradual**: 
   - Primero crear las clases base en `common/handlers/`
   - Luego adaptar handlers existentes a la nueva estructura
   - Priorizar los CallbackHandlers para reducir duplicación

2. **Compatibilidad hacia atrás**:
   - Mantener interfaces públicas existentes
   - Agregar métodos de Factory para instanciación

3. **Pruebas Unitarias**:
   - Desarrollar pruebas completas para cada clase base
   - Verificar inicialización asíncrona funciona correctamente
   - Asegurar manejo de errores consistente

4. **Documentación**:
   - Documentar claramente el propósito y responsabilidad de cada clase
   - Proporcionar ejemplos de uso para desarrolladores

### Beneficios Esperados

1. **Reducción de Código**: Menos duplicación, mejor mantenibilidad
2. **Inicialización Robusta**: Patrón consistente para manejo de dependencias asíncronas
3. **Manejo de Errores Unificado**: Respuestas consistentes en toda la aplicación
4. **Métricas Estandarizadas**: Base común para análisis de rendimiento
5. **Extensibilidad**: Facilidad para crear nuevos handlers especializados
