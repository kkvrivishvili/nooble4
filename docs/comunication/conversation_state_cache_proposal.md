# Propuesta: Sistema de Caché para Estado de Conversaciones

## Introducción

Este documento presenta una propuesta detallada para implementar un sistema de caché que mantenga el estado de las conversaciones activas en nooble4, reduciendo consultas redundantes y optimizando el flujo de comunicación entre servicios.

## Problema Actual

Actualmente, el sistema nooble4 no mantiene el estado de conversación entre mensajes:

1. Cada nuevo mensaje del usuario reinicia el ciclo completo de enriquecimiento
2. Se consulta repetidamente la misma información al Agent Management Service
3. No existe asociación persistente entre `session_id`, `conversation_id` y contexto de ejecución
4. Los servicios auxiliares (Embedding, Query) reciben información fragmentada

## Propuesta de Sistema de Caché

### 1. Caché de Contexto de Conversación

Implementar un sistema de caché en Redis que mantenga el contexto enriquecido por conversación:

```python
# Estructura clave-valor en Redis:
# conversation_context:{tenant_id}:{conversation_id} -> ExecutionContext serializado
```

El contexto cacheado contendría:
- Configuración completa del agente
- Parámetros de LLM
- Configuración de RAG
- Configuración de embeddings
- Referencias a colecciones
- Metadatos de la conversación

### 2. API en Agent Orchestrator Service

```python
class ConversationContextManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.ttl_seconds = 1800  # 30 minutos por defecto

    async def get_or_create_context(
        self,
        conversation_id: str,
        tenant_id: str,
        agent_id: str,
        headers: Dict[str, Any] = None
    ) -> ExecutionContext:
        """
        Obtiene contexto cacheado o crea uno nuevo si no existe.
        
        Args:
            conversation_id: ID único de la conversación
            tenant_id: ID del tenant
            agent_id: ID del agente
            headers: Headers HTTP opcionales para actualizar el contexto
            
        Returns:
            Contexto de ejecución completo
        """
        # Clave de caché
        cache_key = f"conversation_context:{tenant_id}:{conversation_id}"
        
        # Intentar recuperar de caché
        cached_context = await self.redis_client.get(cache_key)
        
        if cached_context:
            # Deserializar contexto
            context_dict = json.loads(cached_context)
            context = ExecutionContext.from_dict(context_dict)
            
            # Actualizar TTL para mantener activo
            await self.redis_client.expire(cache_key, self.ttl_seconds)
            
            # Actualizar si hay nuevos headers
            if headers and any(headers.values()):
                context = await self._update_context_from_headers(context, headers)
                await self._save_context(cache_key, context)
            
            return context
        
        # Si no existe, crear nuevo contexto enriquecido
        if not headers:
            raise ValueError("Headers son requeridos para crear nuevo contexto")
        
        # Llamar al método existente de enriquecimiento
        context = await self.create_enriched_context(
            tenant_id, agent_id, headers
        )
        
        # Guardar en caché
        await self._save_context(cache_key, context)
        
        return context
    
    async def _save_context(self, cache_key: str, context: ExecutionContext):
        """Guarda contexto en caché con TTL."""
        await self.redis_client.set(
            cache_key,
            context.json(),
            ex=self.ttl_seconds
        )
    
    async def invalidate_context(self, conversation_id: str, tenant_id: str):
        """Invalida el contexto de una conversación."""
        cache_key = f"conversation_context:{tenant_id}:{conversation_id}"
        await self.redis_client.delete(cache_key)
```

### 3. Modificaciones en Domain Actions

Extender el modelo `DomainAction` para incluir referencia al contexto cacheado:

```python
class DomainAction(BaseModel):
    # Campos existentes...
    
    # Nuevos campos para referencia de caché
    conversation_id: Optional[str] = Field(None)
    context_reference_key: Optional[str] = Field(None)  # Clave de caché
    
    # Método helper para obtener clave de caché
    @property
    def context_cache_key(self) -> Optional[str]:
        """Retorna la clave de caché para el contexto si está disponible."""
        if self.conversation_id and self.tenant_id:
            return f"conversation_context:{self.tenant_id}:{self.conversation_id}"
        return self.context_reference_key
```

### 4. Integración en Agent Orchestrator

Modificar el handler de WebSocket para mantener el mapeo:

```python
class WebSocketHandler:
    # Campos existentes...
    
    async def on_connect(self, websocket, session_id, tenant_id, agent_id, conversation_id=None):
        # Registrar conexión WebSocket
        await self.websocket_manager.register_connection(session_id, websocket)
        
        # Asociar session_id con conversation_id
        if conversation_id:
            await self.redis_client.set(
                f"session_conversation:{session_id}",
                conversation_id,
                ex=1800  # 30 minutos
            )
    
    async def on_message(self, session_id, message_data):
        # Obtener conversation_id asociado
        conversation_id = await self.redis_client.get(f"session_conversation:{session_id}")
        if not conversation_id:
            conversation_id = str(uuid4())  # Crear nuevo si no existe
            await self.redis_client.set(
                f"session_conversation:{session_id}",
                conversation_id,
                ex=1800
            )
        
        # Obtener o crear contexto de conversación
        context = await self.context_manager.get_or_create_context(
            conversation_id=conversation_id,
            tenant_id=message_data.get("tenant_id"),
            agent_id=message_data.get("agent_id"),
            headers=message_data.get("headers")
        )
        
        # Crear Domain Action con referencia al contexto
        action = AgentExecutionAction(
            task_id=str(uuid4()),
            conversation_id=conversation_id,
            context_reference_key=context.context_cache_key,
            # Otros campos...
        )
        
        # Continuar con el flujo normal...
```

### 5. Consumo en Servicios Downstream

Los servicios como Agent Execution, Embedding y Query podrían recuperar el contexto completo:

```python
class BaseWorker:
    # Campos existentes...
    
    async def _resolve_context_from_action(self, action: DomainAction) -> ExecutionContext:
        """Resuelve contexto completo desde caché si está disponible."""
        
        # Verificar si hay referencia a caché
        if action.context_cache_key:
            cached_context = await self.redis_client.get(action.context_cache_key)
            if cached_context:
                try:
                    return ExecutionContext.from_dict(json.loads(cached_context))
                except Exception as e:
                    logger.error(f"Error deserializando contexto cacheado: {e}")
        
        # Fallback: Construir desde los campos de la acción
        return ExecutionContext(
            tenant_id=action.tenant_id,
            tenant_tier=action.tenant_tier,
            # Otros campos disponibles...
        )
```

## Beneficios de la Propuesta

1. **Reducción de consultas redundantes**: La información del agente se obtiene una sola vez por conversación
2. **Consistencia garantizada**: La misma configuración se usa durante toda la conversación
3. **Optimización de rendimiento**: Menos consultas a servicios como Agent Management
4. **Mejor experiencia de usuario**: Respuestas más rápidas y coherentes

## Consideraciones Técnicas

1. **Tiempo de vida (TTL)**: El contexto debe expirar después de un periodo de inactividad (ej: 30 minutos)
2. **Tamaño de datos**: Monitorear el tamaño del contexto cacheado para evitar sobrecarga de memoria
3. **Recuperación ante fallos**: Implementar fallbacks para situaciones donde el caché no está disponible
4. **Sincronización**: Mecanismos para invalidar caché cuando la configuración del agente cambia

## Próximos Pasos

1. Implementar `ConversationContextManager` en Agent Orchestrator
2. Extender modelo `DomainAction` para incluir referencias de caché
3. Modificar workers para aprovechar el contexto cacheado
4. Implementar sistema de limpieza de contextos expirados
5. Añadir métricas para monitoreo de aciertos y fallos de caché
