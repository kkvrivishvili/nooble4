# Plan de Debugging - Query Service
Fecha: 2025-06-08

## 🔍 Tabla de Errores e Inconsistencias Críticas

| # | Error/Inconsistencia | Archivo | Línea | Criticidad | Descripción Técnica | Posible Solución | Archivos a Revisar | Servicios Afectados | Verificación |
|---|---------------------|---------|------|------------|---------------------|-----------------|-------------------|-------------------|-------------|
| **1** | **Import datetime faltante** | `services/vector_search_service.py` | 88 | 🔴 **CRÍTICO** | `NameError: name 'datetime' is not defined` en `_track_search_metrics()` | Agregar `from datetime import datetime` al inicio | `services/vector_search_service.py` | Agent Execution, Embedding (consumen search) | Verificar que métricas se registren correctamente |
| **2** | **Import lru_cache faltante** | `config/settings.py` | 76 | 🔴 **CRÍTICO** | `NameError: name 'lru_cache' is not defined` en `@lru_cache()` decorator | Agregar `from functools import lru_cache` | `config/settings.py` | Todos los servicios usan settings cacheados | Verificar performance sin cache |
| **3** | **Import get_service_settings incorrecto** | `config/settings.py` | 6 | 🔴 **CRÍTICO** | `ImportError: cannot import name 'get_service_settings'` | Cambiar a `get_service_settings as get_base_settings` | `config/settings.py` | Common module, otros servicios | Verificar pattern consistency |
| **4** | **Dependencia circular con embedding_service** | `clients/embedding_client.py` | 11 | 🔴 **CRÍTICO** | `from embedding_service.models.actions import EmbeddingGenerateAction` crea import circular | Mover models a common o usar forward references | `clients/embedding_client.py`, `models/actions.py` | Embedding Service | Reestructurar imports entre servicios |
| **5** | **Atributo domain_name inexistente** | `workers/query_worker.py` | 37 | 🔴 **CRÍTICO** | `AttributeError: 'QueryServiceSettings' object has no attribute 'domain_name'` | Agregar field `domain_name = "query"` a settings | `config/settings.py`, `workers/query_worker.py` | Agent Execution, Embedding (mismo pattern) | Verificar domain names consistency |
| **6** | **Atributo enable_query_tracking inexistente** | `handlers/query_handler.py` | 134 | 🔴 **CRÍTICO** | `AttributeError: 'QueryServiceSettings' object has no attribute 'enable_query_tracking'` | Agregar field `enable_query_tracking` a settings | `config/settings.py`, `handlers/query_handler.py` | Embedding Service (mismo pattern) | Verificar tracking patterns |
| **7** | **Worker initialization pattern inconsistente** | `workers/query_worker.py` | 30-34 | 🟡 **ALTO** | Pattern `redis_client or get_redis_client()` no es async | Refactorizar para async initialization como BaseWorker | `workers/query_worker.py` | Embedding, Agent Execution, Conversation | Estandarizar worker patterns |
| **8** | **Supabase client sin inicializar** | `handlers/context_handler.py` | 43 | 🟡 **ALTO** | `self.supabase` referenciado pero nunca inicializado en `__init__` | Inicializar `self.supabase = supabase_client` o validar None | `handlers/context_handler.py` | Conversation Service (usa Supabase) | Verificar Supabase integration |
| **9** | **Import datetime faltante** | `handlers/context_handler.py` | 95 | 🟡 **ALTO** | `datetime.utcnow()` sin import explícito | Agregar `from datetime import datetime` | `handlers/context_handler.py` | Ninguno directo | Verificar datetime usage patterns |
| **10** | **Hard-coded model_dump() call** | `config/settings.py` | 79 | 🟡 **ALTO** | `base_settings.model_dump()` asume Pydantic v2, puede fallar en v1 | Usar `.dict()` para compatibilidad o verificar versión | `config/settings.py` | Todos los servicios | Verificar Pydantic version consistency |
| **11** | **Common.errors import sin definir** | `clients/vector_store_client.py` | 13 | 🟡 **ALTO** | `from common.errors import ServiceError` pero ServiceError no está definido en common.errors | Definir ServiceError en common.errors o usar Exception estándar | `clients/vector_store_client.py`, `common/errors.py` | Todos los servicios | Definir error hierarchy común |
| **12** | **Referencias a settings.search_cache_ttl inexistente** | `services/vector_search_service.py` | 46 | 🟡 **ALTO** | Código referencia atributo que no existe en settings | Agregar `search_cache_ttl` field a settings | `config/settings.py`, `services/vector_search_service.py` | Embedding Service (similar cache pattern) | Verificar cache TTL values |
| **13** | **Pattern de colas inconsistente** | `clients/embedding_client.py` | 49-56 | 🟠 **MEDIO** | Mezcla ActionProcessor y DomainQueueManager patterns | Usar solo DomainQueueManager como otros servicios | `clients/embedding_client.py` | Embedding, Agent Execution | Estandarizar queue patterns |
| **14** | **Hard-coded "all" en stats methods** | `handlers/query_handler.py` | 160, 174 | 🟠 **MEDIO** | `get_query_stats("all")` no maneja tenant_id correctamente | Cambiar para aceptar tenant_id real o None | `handlers/query_handler.py`, `workers/query_worker.py` | Embedding, Agent Execution | Verificar stats patterns |
| **15** | **Exception handling genérico** | `workers/query_worker.py` | 89, 113 | 🟠 **MEDIO** | `except Exception` muy amplio, no diferencia tipos | Implementar exception handling específico | `workers/query_worker.py` | Embedding, Agent Execution | Estandarizar error handling |
| **16** | **Import missing common.redis_pool** | `workers/query_worker.py` | 32 | 🟠 **MEDIO** | `get_redis_client()` usado sin import explícito | Agregar import explícito | `workers/query_worker.py` | Todos los workers | Verificar import consistency |
| **17** | **Groq API key hardcoded check** | `config/settings.py` | 30 | 🟠 **MEDIO** | No valida que groq_api_key no esté vacío | Agregar validación de API key | `config/settings.py` | Ninguno directo | Verificar API key validation |
| **18** | **Cache key collision potential** | `services/vector_search_service.py` | 139-148 | 🟠 **MEDIO** | MD5 hash de embedding sample puede tener colisiones | Incluir más información en hash (timestamp, tenant) | `services/vector_search_service.py` | Embedding Service | Verificar cache key strategies |

## 🔥 Problemas Críticos que Causan Startup/Runtime Failure

### **Error #1-3: Import Errors**
```python
# STARTUP FAILURE
ImportError: cannot import name 'get_service_settings' from 'common.config'
NameError: name 'lru_cache' is not defined
NameError: name 'datetime' is not defined
```
**Impacto**: Servicio no puede iniciarse o falla en runtime

### **Error #4: Dependencia Circular**
```python
# IMPORT CIRCULAR FAILURE
query_service.clients.embedding_client → embedding_service.models.actions
embedding_service.handlers → query_service.models.actions
```
**Impacto**: Python no puede resolver imports, startup failure

### **Error #5-6: AttributeError en Runtime**
```python
# RUNTIME FAILURE AL PROCESAR REQUESTS
settings.domain_name                # AttributeError
settings.enable_query_tracking      # AttributeError
```
**Impacto**: Service crash en primera request

### **Error #11: ServiceError Undefined**
```python
# RUNTIME FAILURE EN ERROR HANDLING
raise ServiceError("Vector store error")  # NameError
```
**Impacto**: Error handling falla, causando crashes no controlados

## 🔗 Dependencias y Servicios Afectados

### **Servicios que Dependen de Query Service:**
1. **Agent Execution Service** - Usa Query para RAG
2. **Embedding Service** - Query consume embeddings (circular dependency)
3. **Orchestrator Service** - Coordina queries

### **Servicios que Query Service Consume:**
1. **Embedding Service** - Para generar embeddings
2. **Vector Store** - Para búsqueda de documentos
3. **Groq LLM API** - Para generación de respuestas

### **Efecto Cascada de Errores:**
```
Query Service FALLA (import circular)
    ↓
Agent Execution no puede hacer RAG queries
    ↓
Embedding Service no puede procesar requests (callback fails)
    ↓
Sistema RAG completo FALLA
```

## 🛠️ Plan de Corrección Prioritizada

### **FASE 1: Critical Import Fixes (10 minutos)**
1. Resolver dependencia circular (Error #4)
2. Corregir imports datetime (Error #1, #9)
3. Corregir import lru_cache (Error #2)
4. Corregir import settings (Error #3)

### **FASE 2: Settings & Runtime Fixes (20 minutos)**
5. Agregar domain_name (Error #5)
6. Agregar enable_query_tracking (Error #6)
7. Definir ServiceError en common (Error #11)
8. Agregar search_cache_ttl (Error #12)

### **FASE 3: Pattern Consistency (45 minutos)**
9. Refactorizar worker initialization (Error #7)
10. Fix Supabase initialization (Error #8)
11. Estandarizar queue patterns (Error #13)

### **FASE 4: Quality Improvements (opcional)**
12. Mejorar error handling (Error #15)
13. Fix hardcoded values (Error #14, #17)
14. Mejorar cache keys (Error #18)

## ⚠️ Riesgo de Dependencia Circular

### **Problema Crítico #4:**
```
query_service/clients/embedding_client.py:
    from embedding_service.models.actions import EmbeddingGenerateAction

embedding_service/handlers/[algunos archivos]:
    # Potencialmente importan de query_service
```

### **Solución Recomendada:**
1. **Mover models comunes a `common/models/`**
2. **Usar forward references**
3. **Reestructurar imports para evitar cycles**

## 🟢 Correcciones Implementadas (2025-06-08)

| # | Error Corregido | Archivo Modificado | Descripción de la Corrección | Fase | Estado |
|---|----------------|-------------------|----------------------------|------|--------|
| **1** |  |  |  |  | ⏳ PENDIENTE |
| **2** |  |  |  |  | ⏳ PENDIENTE |
| **3** |  |  |  |  | ⏳ PENDIENTE |
| **4** |  |  |  |  | ⏳ PENDIENTE |
| **5** |  |  |  |  | ⏳ PENDIENTE |
| **6** |  |  |  |  | ⏳ PENDIENTE |
| **7** |  |  |  |  | ⏳ PENDIENTE |
| **8** |  |  |  |  | ⏳ PENDIENTE |
| **9** |  |  |  |  | ⏳ PENDIENTE |
| **10** |  |  |  |  | ⏳ PENDIENTE |
| **11** |  |  |  |  | ⏳ PENDIENTE |
| **12** |  |  |  |  | ⏳ PENDIENTE |
| **13** |  |  |  |  | ⏳ PENDIENTE |
| **14** |  |  |  |  | ⏳ PENDIENTE |
| **15** |  |  |  |  | ⏳ PENDIENTE |
| **16** |  |  |  |  | ⏳ PENDIENTE |
| **17** |  |  |  |  | ⏳ PENDIENTE |
| **18** |  |  |  |  | ⏳ PENDIENTE |

## ✅ Verificación de Correcciones

### **Script de Validación:**
```python
# query_service_test.py - Pendiente de implementar

import sys
import os
from pathlib import Path

print("=== TEST DE QUERY SERVICE ===\n")
print("⏳ Pendiente de implementar")
```

### **Tareas Pendientes para Próxima Revisión:**
- Implementar script de validación `query_service_test.py`
- Ejecutar pruebas unitarias para verificar funcionalidad
- Verificar integración con Embedding Service
- Probar flujo RAG end-to-end

### **Servicios a Re-testar:**
- Agent Execution Service (RAG functionality)
- Embedding Service (callbacks)
- Integration tests con Vector Store
- End-to-end RAG pipeline
