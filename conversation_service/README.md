# Conversation Service - Implementación Completa

> **ACTUALIZACIÓN**: Se ha migrado toda la comunicación entre servicios de HTTP directo al patrón pseudo-síncrono sobre Redis. Todos los clientes y workers ahora implementan el patrón BaseWorker 4.0.

## 🎯 Visión General

El Conversation Service es el núcleo de memoria conversacional del sistema Nooble, diseñado para manejar conversaciones activas con integración LangChain y persistencia híbrida Redis + PostgreSQL.

## 🏗️ Arquitectura Refactorizada

### Integración con Servicios

```
Agent Execution ────(save_message)────▶ Conversation Service
                                              │
Query Service ─────(get_context)─────▶       │
                                              │
WebSocket Manager ─(session_closed)──▶       │
                                              ▼
                                        Redis (Activas)
                                              │
                                              │ (30s después del cierre)
                                              ▼
                                       PostgreSQL (Persistente)
                                              │
                                              ▼
                                        Frontend/CRM (API REST)
```

### Componentes Principales

1. **ConversationService**: Lógica principal con integración LangChain
2. **MemoryManager**: Gestión inteligente de memoria conversacional por modelo
3. **PersistenceManager**: Manejo híbrido Redis + PostgreSQL
4. **Specialized Workers**: MessageSaveWorker + MigrationWorker
5. **CRM API**: Endpoints REST para dashboard y estadísticas

## 🧠 Integración LangChain

### Estrategia de Memoria por Modelo

```python
model_strategies = {
    "llama3-8b-8192": ConversationTokenBufferMemory(max_token_limit=6000),
    "llama3-70b-8192": ConversationTokenBufferMemory(max_token_limit=6000), 
    "gpt-4": ConversationTokenBufferMemory(max_token_limit=28000),
    "claude-3-sonnet": ConversationSummaryBufferMemory(max_token_limit=120000)
}
```

### Optimización de Contexto

- **Token counting**: Estimación precisa por mensaje
- **Truncamiento inteligente**: LangChain maneja automáticamente
- **Context reservation**: 30% reservado para respuesta del modelo
- **Tier-aware limits**: Diferentes límites según tier del usuario

## 📊 Estructura de Datos

### Redis (Conversaciones Activas)

```
conversation:{tenant_id}:{conversation_id} → Conversation JSON
messages:{conversation_id} → List[Message] (LIFO)
session_conversation:{tenant_id}:{session_id} → conversation_id
active_conversations:{tenant_id} → Set[conversation_id]
```

### PostgreSQL (Preparado para Supabase)

```sql
-- Tabla principal de conversaciones
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    session_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    user_id VARCHAR,
    model_name VARCHAR DEFAULT 'llama3-8b-8192',
    status VARCHAR DEFAULT 'active',
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP,
    migrated_from_redis BOOLEAN DEFAULT false
);

-- Tabla de mensajes
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'function')),
    content TEXT NOT NULL,
    tokens_estimate INTEGER,
    processing_time_ms INTEGER,
    agent_id VARCHAR,
    model_used VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Índices para performance
CREATE INDEX idx_conversations_tenant_id ON conversations(tenant_id);
CREATE INDEX idx_conversations_agent_id ON conversations(agent_id);  
CREATE INDEX idx_conversations_created_at ON conversations(created_at);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
```

## 🔄 Domain Actions

### 1. save_message (desde Agent Execution)

```json
{
  "action_type": "conversation.save_message",
  "tenant_id": "tenant123",
  "session_id": "session_abc",
  "role": "assistant",
  "content": "Respuesta del agente...",
  "agent_id": "agent_xyz",
  "model_name": "llama3-70b-8192",
  "tokens_estimate": 150,
  "metadata": {
    "tenant_tier": "professional"
  }
}
```

### 2. get_context (desde Query Service)

```json
{
  "action_type": "conversation.get_context",
  "tenant_id": "tenant123", 
  "session_id": "session_abc",
  "model_name": "llama3-70b-8192",
  "tenant_tier": "professional"
}
```

### 3. session_closed (desde WebSocket Manager)

```json
{
  "action_type": "conversation.session_closed",
  "tenant_id": "tenant123",
  "session_id": "session_abc"
}
```

## 🎚️ Límites por Tier

| Tier | Conversaciones Activas | Mensajes/Conv | Retención | Contexto |
|------|----------------------|---------------|-----------|-----------|
| Free | 3 | 50 | 7 días | 5 mensajes |
| Advance | 10 | 200 | 30 días | 15 mensajes |
| Professional | 50 | 1,000 | 90 días | 30 mensajes |
| Enterprise | Ilimitado | Ilimitado | 365 días | 50 mensajes |

## 🚀 Plan de Implementación

### Fase 1: Core Implementation (Semana 1)
- [ ] Implementar ConversationService base
- [ ] Integrar MemoryManager con LangChain
- [ ] Configurar PersistenceManager para Redis
- [ ] Crear Domain Actions y Handlers
- [ ] Implementar ConversationWorker

### Fase 2: Persistence & Migration (Semana 2)  
- [ ] Preparar schema PostgreSQL/Supabase
- [ ] Implementar MigrationWorker
- [ ] Sistema de migración automática Redis → PostgreSQL
- [ ] Error handling y retry logic
- [ ] Testing de persistencia

### Fase 3: CRM Integration (Semana 3)
- [ ] Endpoints REST para CRM
- [ ] Listado de conversaciones con filtros
- [ ] Vista completa de conversación
- [ ] Estadísticas básicas por tenant/agente
- [ ] Dashboard data endpoints

### Fase 4: Optimization & Production (Semana 4)
- [ ] Performance tuning
- [ ] Monitoring y métricas
- [ ] Cleanup automático de datos antiguos
- [ ] Load testing
- [ ] Documentation final

## ⚙️ Configuración de Desarrollo

### Variables de Entorno

```env
# Conversation Service
CONVERSATION_REDIS_URL=redis://localhost:6379/0
CONVERSATION_DATABASE_URL=postgresql://user:pass@localhost/conversations
CONVERSATION_SUPABASE_URL=https://xyz.supabase.co
CONVERSATION_SUPABASE_KEY=eyJ...

# LangChain
CONVERSATION_LANGCHAIN_MEMORY_TYPE=token_buffer
CONVERSATION_WEBSOCKET_GRACE_PERIOD=30

# Workers
CONVERSATION_MESSAGE_SAVE_WORKER_BATCH_SIZE=50
CONVERSATION_PERSISTENCE_MIGRATION_INTERVAL=60
```

### Instalación

```bash
cd conversation_service
pip install -r requirements.txt

# Para desarrollo con auto-reload
uvicorn main:app --reload --port 8004

# Para producción
uvicorn main:app --host 0.0.0.0 --port 8004 --workers 4
```

## 📈 Recomendaciones de Performance

### Escalabilidad

- **Redis Clustering**: Para > 10,000 conversaciones concurrentes
- **Read Replicas**: PostgreSQL read replicas para CRM queries
- **Worker Scaling**: Múltiples instancias de workers según carga
- **Memory Optimization**: Cleanup de conversaciones inactivas cada hora

### Monitoring

```python
# Métricas críticas a monitorear
- Active conversations in Redis
- Memory usage per conversation
- Migration queue length  
- Token usage per tenant
- Average response time
- Redis memory usage
- PostgreSQL connection pool
```

### Performance Targets

- **Save Message**: < 50ms (p95)
- **Get Context**: < 100ms (p95)
- **Migration**: < 5 segundos por conversación
- **Redis Memory**: < 2GB para 1,000 conversaciones activas
- **CRM Queries**: < 500ms para listado de conversaciones

## 🔧 Troubleshooting

### Redis Failure Recovery

```python
# Si Redis falla:
1. Conversaciones activas se pierden
2. Fallback: usar PostgreSQL como cache temporal
3. Degraded mode: sin optimización LangChain
4. Recovery: restaurar Redis y recargar desde PostgreSQL
```

### Common Issues

- **Memory Leaks**: Limpiar instancias LangChain de conversaciones migradas
- **Migration Stuck**: Verificar PostgreSQL connectivity y schema
- **Context Too Large**: Verificar token limits por modelo
- **Session Mapping Lost**: Regenerar desde conversaciones activas

## 🧪 Testing Strategy

### Unit Tests

```bash
pytest tests/unit/
# - ConversationService methods
# - MemoryManager integration
# - PersistenceManager operations
# - Domain Actions parsing
```

### Integration Tests

```bash
pytest tests/integration/
# - Redis operations
# - LangChain memory behavior
# - Worker processing
# - Migration workflow
```

### Load Tests

```bash
# Simulate high conversation volume
python tests/load/conversation_load_test.py
# Target: 1000 concurrent conversations, 10 msgs/sec per conversation
```

## 🔮 Futuros Enhancements

### Análisis Sentimental
- Integración con servicios de sentiment analysis
- Tracking de sentiment por conversación
- Alertas para sentiment negativo

### Advanced Analytics
- Conversation flow analysis
- Topic modeling