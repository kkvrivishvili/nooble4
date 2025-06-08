# Conversation Service - Arquitectura Completa

## 🏗️ Flujo de Datos Principal

```
┌─────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│                 │    │                     │    │                  │
│ Agent Execution │───▶│ Conversation Service │───▶│ Redis (Active)   │
│                 │    │                     │    │                  │
└─────────────────┘    └─────────────────────┘    └──────────────────┘
                                │                           │
                                │                           │ (30s after WS close)
                                ▼                           ▼
                       ┌─────────────────┐         ┌──────────────────┐
                       │                 │         │                  │
                       │ Query Service   │         │ PostgreSQL       │
                       │ (Get Context)   │         │ (Persistent)     │
                       │                 │         │                  │
                       └─────────────────┘         └──────────────────┘
                                                            │
                                                            ▼
                                                   ┌──────────────────┐
                                                   │                  │
                                                   │ Frontend/CRM     │
                                                   │ (REST API)       │
                                                   │                  │
                                                   └──────────────────┘
```

## 🔄 Domain Actions Flow

### 1. **save_message** (desde Agent Execution)
```
Agent Execution → conversation.save_message → Redis Cache → [Async] PostgreSQL
```

### 2. **get_context** (desde Query Service)  
```
Query Service → conversation.get_context → LangChain Memory → Optimized Context
```

### 3. **session_closed** (desde WebSocket Manager)
```
WebSocket Close → conversation.session_closed → (30s delay) → Move to PostgreSQL
```

## 🧠 LangChain Memory Integration

```python
# Diferentes estrategias según modelo
strategies = {
    "8k": ConversationTokenBufferMemory(max_token_limit=6000),
    "32k": ConversationTokenBufferMemory(max_token_limit=28000), 
    "128k": ConversationSummaryBufferMemory(max_token_limit=120000)
}
```

## 📚 Componentes Principales

### 1. **ConversationService**
- **save_message()**: Guarda en Redis + actualiza LangChain memory
- **get_context()**: Obtiene contexto optimizado para modelo específico
- **move_to_persistent()**: Mueve conversación completa a PostgreSQL
- **get_stats()**: Estadísticas básicas para dashboard

### 2. **MemoryManager** (nuevo)
- **Integración LangChain**: Manejo inteligente de contexto por modelo
- **Token counting**: Estimación precisa de tokens por mensaje
- **Context optimization**: Truncamiento inteligente para RAG

### 3. **PersistenceManager** (nuevo)
- **Redis operations**: CRUD en cache activo
- **PostgreSQL operations**: Persistencia permanente (preparado)
- **Migration logic**: Movimiento automático Redis → PostgreSQL

### 4. **StatisticsService** (nuevo)
- **Basic metrics**: Conteos, duraciones, agentes más usados
- **Dashboard data**: Datos listos para visualización
- **Export functions**: Preparado para análisis externos

## 🎯 Workers Especializados

### 1. **MessageSaveWorker**
- **Único propósito**: Guardar mensajes de forma confiable
- **High performance**: Optimizado para escritura rápida
- **Error recovery**: Retry logic + dead letter queue

### 2. **PersistenceMigrationWorker**
- **Session monitoring**: Detecta WebSocket disconnections
- **Delayed migration**: 30s grace period para reconexiones
- **Batch operations**: Migración eficiente a PostgreSQL

### 3. **StatisticsWorker** (opcional)
- **Background processing**: Cálculo de métricas sin impacto
- **Aggregation**: Datos preparados para dashboard
- **Cleanup**: Limpieza de datos antiguos

## 📊 Estructura de Datos

### Redis Structure
```
conversation:{tenant_id}:{conversation_id} → Conversation JSON
messages:{conversation_id} → List[Message]
session_mapping:{session_id} → conversation_id
active_sessions → Set[session_id]
```

### PostgreSQL Tables (preparado)
```sql
conversations(id, tenant_id, session_id, agent_id, status, created_at, ...)
messages(id, conversation_id, role, content, tokens, created_at, ...)
conversation_stats(conversation_id, message_count, duration, satisfaction, ...)
```

## 🔌 API Endpoints (solo CRM/Frontend)

### Dashboard/Statistics
```
GET /api/conversations/stats/{tenant_id}
GET /api/conversations/list/{tenant_id}?filters
GET /api/conversations/{conversation_id}/full
GET /api/agents/{agent_id}/stats
```

## 🚨 Error Handling Strategy

### Redis Failure
```
Redis Down → Fallback to PostgreSQL → Continue operations
```

### Message Save Failure
```
Save Fails → Retry (3x) → Dead Letter Queue → Alert
```

### Context Retrieval Failure
```
Context Fails → Return empty → Log warning → Continue
```

## 📈 Performance Considerations

### Memory Management
- **Active conversations**: Solo en Redis
- **LangChain memory**: En memoria del proceso
- **Token counting**: Cache de conteos para eficiencia

### Database Strategy
- **Read replica**: Para estadísticas y dashboard
- **Write optimization**: Batch inserts para migración
- **Indexing**: Por tenant_id, agent_id, created_at

### Scaling Strategy
- **Redis sharding**: Por tenant_id si es necesario
- **Worker scaling**: Múltiples instancias de workers
- **Memory optimization**: Cleanup de conversaciones inactivas