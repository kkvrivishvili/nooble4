# Optimización de la Comunicación Entre Servicios

## Introducción

Este documento analiza la comunicación actual entre los microservicios de nooble4, identificando puntos de ineficiencia y proponiendo optimizaciones para reducir consultas redundantes y mejorar el rendimiento del sistema.

## Estado Actual de la Comunicación

### 1. Flujo de Información Actual

El flujo de información entre servicios sigue actualmente este patrón:

```
Frontend --[Headers HTTP]--> Agent Orchestrator
  |
  +--> Agent Management Service (consulta config) 
  |
  +--> Redis Queue --[AgentExecutionAction]--> Agent Execution Service
       |
       +--> Agent Management Service (consulta config nuevamente)
       |
       +--> Redis Queue --[EmbeddingAction]--> Embedding Service
       |    |
       |    +--> Redis Queue --[Callback]--> Agent Execution Service
       |
       +--> Redis Queue --[QueryAction]--> Query Service
            |
            +--> Redis Queue --[Callback]--> Agent Execution Service
  |
  +--> Redis Queue --[ExecutionCallbackAction]--> Agent Orchestrator
  |
  +--> WebSocket --[Respuesta]--> Frontend
```

### 2. Problemas Identificados

1. **Consultas Redundantes a Agent Management Service**:
   - Agent Orchestrator consulta para enriquecer contexto
   - Agent Execution consulta nuevamente para obtener la misma información
   - Query Service puede consultar nuevamente para configuración RAG

2. **Información Fragmentada**:
   - No hay un objeto de contexto unificado que viaje entre servicios
   - Cada servicio reconstruye parcialmente el contexto

3. **Valores Hardcodeados**:
   - Los servicios caen en valores por defecto hardcodeados cuando falta información
   - No hay propagación consistente de parámetros de configuración

4. **Sin Aprovechamiento de Caché**:
   - Se realizan consultas HTTP repetitivas en lugar de cachear resultados
   - No hay TTL optimizado para diferentes tipos de configuración

## Propuesta de Optimización

### 1. Modelo de Contexto Unificado

Crear un modelo de contexto completo que incluya toda la información necesaria:

```python
class ExecutionContext(BaseModel):
    # Campos de identificación
    context_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    agent_id: str
    tenant_tier: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Configuraciones que antes estaban fragmentadas
    llm_config: Dict[str, Any] = Field(default_factory=dict)
    embedding_config: Dict[str, Any] = Field(default_factory=dict)
    rag_config: Dict[str, Any] = Field(default_factory=dict)
    agent_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadatos adicionales
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Configuración de límites y rate limiting
    rate_limits: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps para control de tiempo
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Método para actualizar campos específicos
    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()
        
    # Serialización para caché
    def to_cache_dict(self) -> Dict[str, Any]:
        return self.dict()
        
    @classmethod
    def from_cache_dict(cls, data: Dict[str, Any]) -> 'ExecutionContext':
        return cls(**data)
```

### 2. Estrategia de Caché por Niveles

Implementar una estrategia de caché en múltiples niveles:

```python
class ContextCacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl_config = {
            "conversation": 1800,  # 30 minutos
            "agent_config": 600,   # 10 minutos
            "collection_config": 900  # 15 minutos
        }
        
    async def get_cached_context(self, key: str, default_factory=None) -> Optional[ExecutionContext]:
        """Obtiene contexto de caché o lo crea usando factory si no existe."""
        cached_value = await self.redis.get(key)
        
        if cached_value:
            try:
                return ExecutionContext.from_cache_dict(json.loads(cached_value))
            except Exception as e:
                logger.error(f"Error deserializando contexto: {e}")
                
        if default_factory:
            # Crear nuevo valor
            new_value = await default_factory()
            # Guardar en caché
            await self.set_cached_context(key, new_value)
            return new_value
            
        return None
        
    async def set_cached_context(self, key: str, context: ExecutionContext, ttl_type: str = "conversation"):
        """Guarda contexto en caché con TTL específico."""
        ttl = self.ttl_config.get(ttl_type, 300)  # Default 5 minutos
        
        try:
            serialized = json.dumps(context.to_cache_dict())
            await self.redis.set(key, serialized, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Error guardando contexto en caché: {e}")
            return False
            
    async def invalidate_context(self, key: str):
        """Invalida un contexto específico."""
        await self.redis.delete(key)
```

### 3. Propagación Eficiente en Domain Actions

Modificar el modelo `DomainAction` para referenciar contexto unificado:

```python
class DomainAction(BaseModel):
    # Campos existentes
    
    # Referencia a contexto cacheado
    context_cache_key: Optional[str] = None
    
    # Método para resolver contexto
    async def resolve_context(self, cache_manager) -> Optional[ExecutionContext]:
        """Resuelve ExecutionContext desde caché si está disponible."""
        if not self.context_cache_key:
            return None
            
        return await cache_manager.get_cached_context(self.context_cache_key)
```

### 4. Uso en Agent Orchestrator

Implementar enriquecimiento de contexto con caché:

```python
# En un handler de Agent Orchestrator
async def process_agent_execution_request(self, request, headers):
    # Obtener información básica
    tenant_id = headers.get("X-Tenant-ID")
    agent_id = headers.get("X-Agent-ID")
    conversation_id = headers.get("X-Conversation-ID", str(uuid4()))
    
    # Clave de caché de contexto
    context_key = f"context:{tenant_id}:{conversation_id}"
    
    # Crear factory para contexto nuevo si no está en caché
    async def create_new_context():
        # Crear contexto básico
        context = ExecutionContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            tenant_tier=headers.get("X-Tenant-Tier", "free"),
            conversation_id=conversation_id,
            session_id=headers.get("X-Session-ID")
        )
        
        # Enriquecer con configuración de agente
        agent_config = await self._fetch_agent_configuration(tenant_id, agent_id)
        context.agent_config = agent_config
        
        # Extraer configuraciones específicas
        context.llm_config = self._extract_llm_config(agent_config, headers)
        context.embedding_config = self._extract_embedding_config(agent_config, headers)
        context.rag_config = await self._extract_rag_config(agent_config, headers)
        
        return context
    
    # Obtener o crear contexto cacheado
    context = await self.context_cache.get_cached_context(
        context_key, 
        default_factory=create_new_context
    )
    
    # Crear Domain Action con referencia al caché
    action = AgentExecutionAction(
        task_id=str(uuid4()),
        tenant_id=tenant_id,
        tenant_tier=context.tenant_tier,
        action_type="execution.agent_run",
        context_cache_key=context_key,
        # Otros campos...
    )
    
    # Enviar a cola
    await self.queue_manager.enqueue_action("execution", action)
    
    return {"task_id": action.task_id}
```

### 5. Uso en Servicios Downstream (Agent Execution, Query, Embedding)

Implementar recuperación de contexto desde caché:

```python
# En un worker de Agent Execution
async def _handle_agent_run(self, action: AgentExecutionAction):
    # Obtener contexto completo desde caché
    context = await action.resolve_context(self.context_cache)
    
    if not context:
        # Fallback: Reconstruir contexto parcial (menos eficiente)
        context = ExecutionContext(
            tenant_id=action.tenant_id,
            agent_id=action.agent_id,
            tenant_tier=action.tenant_tier
        )
        # Aquí tendría que consultar Agent Management Service
        
    # Ejecutar con contexto completo que ya incluye configuración
    result = await self.agent_executor.execute(
        action.message,
        context=context
    )
    
    # Crear callback con la misma referencia de contexto
    callback = ExecutionCallbackAction(
        task_id=action.task_id,
        tenant_id=action.tenant_id,
        tenant_tier=action.tenant_tier,
        context_cache_key=action.context_cache_key,  # Mantener referencia
        result=result
    )
    
    # Enviar callback
    await self.queue_manager.enqueue_action("execution", callback, action_type="callback")
```

## Beneficios de la Optimización

1. **Reducción de Consultas HTTP**:
   - Hasta un 70% menos de llamadas a Agent Management Service
   - Eliminación de consultas redundantes para configuración

2. **Mejora de Latencia**:
   - Respuestas más rápidas al usuario (especialmente en conversaciones largas)
   - Reducción de tiempo de procesamiento en cada servicio

3. **Consistencia Garantizada**:
   - El mismo contexto y configuración se usa en toda la cadena de servicios
   - Previene inconsistencias por datos parciales o desactualizados

4. **Mejor Escalabilidad**:
   - Menos carga en servicios críticos como Agent Management
   - Uso más eficiente de recursos de red y procesamiento

## Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Fallo del caché | Implementar fallbacks para reconstrucción de contexto |
| Contexto desactualizado | Establecer TTL apropiados por tipo de datos |
| Tamaño excesivo del contexto | Monitorear tamaño y optimizar serialización |
| Inconsistencia por actualización | Sistema de invalidación de caché cuando cambios importantes |

## Próximos Pasos

1. Implementar el modelo `ExecutionContext` extendido
2. Desarrollar `ContextCacheManager` en servicios compartidos
3. Modificar Agent Orchestrator para usar el sistema de caché
4. Actualizar workers de servicios downstream para resolver contexto desde caché
5. Implementar métricas para monitorear eficacia del caché
6. Realizar pruebas con conversaciones largas para validar mejoras
