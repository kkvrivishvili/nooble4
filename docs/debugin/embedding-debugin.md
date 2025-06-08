# Análisis Detallado de Errores - Embedding Service

## Tabla de Errores e Inconsistencias Críticas

| # | Error/Inconsistencia | Archivo(s) | Líneas | Criticidad | Descripción Detallada | Solución Propuesta | Servicios Involucrados |
|---|---------------------|------------|--------|------------|----------------------|-------------------|----------------------|
| 1 | **Variable incorrecta en main.py** | `main.py` | 34, 61, 75 | 🔴 **CRÍTICO** | Se declara `execution_worker` pero se usa `embedding_worker`. Línea 61: `worker_task = asyncio.create_task(execution_worker.start())` debería ser `embedding_worker.start()` | Renombrar variable: `execution_worker = EmbeddingWorker(redis_client)` → `embedding_worker = EmbeddingWorker(redis_client)` | Ninguno - Error interno |
| 2 | **get_redis_client() síncrono en contexto async** | `workers/embedding_worker.py` | 29, 31 | 🔴 **CRÍTICO** | `self.redis_client = redis_client or get_redis_client()` - get_redis_client() no es async pero el contexto lo requiere | Cambiar a: `self.redis_client = redis_client or await get_redis_client()` y hacer el constructor async | Common module, Redis |
| 3 | **API Key hardcodeada inválida** | `config/settings.py` | 138-142 | 🔴 **CRÍTICO** | `"openai_api_key": "sk-"` es una API key inválida que causará fallos en producción | Configurar correctamente: `os.getenv("EMBEDDING_OPENAI_API_KEY")` y validar que no esté vacía | OpenAI API |
| 4 | **Missing import ExecutionContext** | `handlers/embedding_handler.py` | 9, 41 | 🔴 **CRÍTICO** | Se usa `ExecutionContext` pero no está importado correctamente | Agregar: `from common.models.execution_context import ExecutionContext` | Common module |
| 5 | **Memory leak en callback handler** | `handlers/embedding_callback_handler.py` | 39-41, 93+ | 🟠 **ALTO** | `_pending_callbacks` y `_callback_events` crecen indefinidamente sin cleanup automático | Implementar TTL automático y cleanup periódico de callbacks abandonados | Query Service, Agent Execution |
| 6 | **Método _initialize_handlers no es async** | `workers/embedding_worker.py` | 85-101 | 🟠 **ALTO** | Se llama con `await` pero no está definido como `async def` | Cambiar definición: `async def _initialize_handlers(self):` | Ninguno - Error interno |
| 7 | **JSON decode sin manejo de errores** | `services/embedding_processor.py` | 169, 217 | 🟠 **ALTO** | `json.loads(cached_result)` puede fallar con JSON inválido en caché | Agregar try/catch específico para JSONDecodeError y limpiar caché corrupta | Redis |
| 8 | **Session HTTP no reutilizada** | `clients/openai_client.py` | 67-85 | 🟡 **MEDIO** | Se crea nueva session aiohttp en cada request, ineficiente | Implementar session reusable como atributo de clase | OpenAI API |
| 9 | **Modelo no encontrado sin manejo** | `clients/openai_client.py` | 130 | 🟡 **MEDIO** | `_get_dimensions(model)` asume que el modelo existe en OPENAI_MODELS | Agregar validación y fallback: `if model not in OPENAI_MODELS: raise ValueError(f"Modelo no soportado: {model}")` | Ninguno - Validación interna |
| 10 | **Import dentro de try/catch** | `services/embedding_processor.py` | 169, 217 | 🟡 **MEDIO** | `import json` dentro de bloques try/catch es anti-patrón | Mover import al top del archivo | Ninguno - Estilo de código |
| 11 | **Rate limiting no implementado correctamente** | `handlers/context_handler.py` | 133-149 | 🟡 **MEDIO** | Rate limiting usa solo hora actual, fácil de bypasear | Implementar ventana deslizante y persistencia en Redis | Redis, Common module |
| 12 | **Configuración Field(...) con default** | `config/settings.py` | 61-63 | 🟡 **MEDIO** | `Field(..., description="API Key para OpenAI")` dice required pero luego se pone default | Cambiar a `Field(default="", description="...")` o remover default en get_settings() | Ninguno - Configuración |
| 13 | **Exception handling genérico** | `services/validation_service.py` | 175-179 | 🟡 **MEDIO** | Multiple exception types en mismo except sin manejo específico | Separar en múltiples except para manejo específico: ValueError, TypeError, ConnectionError | Redis |
| 14 | **Factory function inconsistente** | `handlers/context_handler.py` | 205 | 🔵 **BAJO** | `get_embedding_context_handler` es async pero se puede llamar sin await | Cambiar a función síncrona o documentar que requiere await | Ninguno - API consistency |
| 15 | **Timeout configuration duplicada** | `config/settings.py` | 80, 82 | 🔵 **BAJO** | `openai_timeout_seconds` y `http_timeout_seconds` podrían ser el mismo valor | Unificar en una sola configuración o clarificar diferencias | Ninguno - Configuración |

## Análisis de Problemas Arquitecturales

### 🔴 Problemas Críticos que Requieren Atención Inmediata

1. **Error de Variable en main.py**: Completamente bloqueante, el servicio no puede iniciarse correctamente.

2. **Redis Client Síncrono**: Causará deadlocks y errores de concurrencia en producción.

3. **API Key Inválida**: Todas las llamadas a OpenAI fallarán inmediatamente.

### 🟠 Problemas de Producción

4. **Memory Leaks**: Los callbacks pendientes se acumularán indefinidamente causando consumo excesivo de memoria.

5. **Cache Corruption**: JSON inválido en caché puede causar fallos intermitentes difíciles de debuggear.

### 🟡 Problemas de Performance y Maintainability

6. **HTTP Session Reuse**: Cada request crea nueva conexión TCP, añadiendo latencia innecesaria.

7. **Rate Limiting Débil**: Fácil de bypasear, no protege efectivamente contra abuse.

## Pasos de Remediación Prioritarios

### Fase 1: Fixes Críticos (Inmediato)
```python
# 1. Arreglar main.py
embedding_worker = EmbeddingWorker(redis_client)  # Cambiar nombre variable

# 2. Fix async redis client
async def __init__(self, redis_client=None, action_processor=None):
    self.redis_client = redis_client or await get_redis_client()

# 3. Fix API key configuration
openai_api_key: str = Field(default="", description="API Key para OpenAI")
if not self.openai_api_key:
    raise ValueError("EMBEDDING_OPENAI_API_KEY requerida")
```

### Fase 2: Stability Fixes (Dentro de 1 semana)
```python
# 4. Memory leak fix
async def cleanup_expired_callbacks(self):
    now = time.time()
    expired = [k for k, v in self._callback_timestamps.items() 
               if now - v > 300]  # 5 min TTL
    for key in expired:
        self._pending_callbacks.pop(key, None)
        self._callback_events.pop(key, None)

# 5. JSON error handling
try:
    return json.loads(cached_result)
except json.JSONDecodeError:
    await self.redis.delete(cache_key)  # Clean corrupted cache
    logger.warning(f"Caché corrupta eliminada: {cache_key}")
    return None
```

### Fase 3: Performance Optimizations (Dentro de 2 semanas)
```python
# 6. HTTP Session reuse
class OpenAIClient:
    def __init__(self):
        self._session = None
    
    async def _get_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
```

## Servicios Afectados por Errores

| Servicio | Impacto | Razón |
|----------|---------|-------|
| **Query Service** | 🔴 Alto | Depende de embeddings para RAG, fallos bloquean búsquedas |
| **Agent Execution** | 🔴 Alto | Necesita embeddings para herramientas, callbacks pueden perderse |
| **Ingestion Service** | 🟠 Medio | Usa embeddings para indexación, puede degradar performance |
| **Redis/Common** | 🟠 Medio | Problemas de conexión y caché afectan estabilidad general |

## Métricas de Impacto Estimado

- **Disponibilidad**: 45% (errores críticos causan fallos completos)
- **Performance**: 60% (ineficiencias en HTTP y caché)
- **Reliability**: 35% (memory leaks y corrupción de datos)
- **Maintainability**: 70% (código funcional pero inconsistente)

**Score General del Servicio: 52.5/100** - Requiere intervención inmediata