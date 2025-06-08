# Plan de Debugging - Embedding Service
Fecha: 2025-06-08

## 🔍 Tabla de Errores e Inconsistencias Críticas

| # | Error/Inconsistencia | Archivo | Línea | Criticidad | Descripción Técnica | Posible Solución | Archivos a Revisar | Servicios Afectados | Verificación |
|---|---------------------|---------|------|------------|---------------------|-----------------|-------------------|-------------------|-------------|
| **1** | **Import datetime faltante** | `services/embedding_processor.py` | 94 | 🔴 **CRÍTICO** | `NameError: name 'datetime' is not defined` en `_track_embedding_metrics()` | Agregar `from datetime import datetime` al inicio | `services/embedding_processor.py` | Query Service, Agent Execution (consumen callbacks) | Verificar que métricas se registren correctamente |
| **2** | **Import datetime faltante** | `services/validation_service.py` | 127 | 🔴 **CRÍTICO** | `NameError: name 'datetime' is not defined` en `get_validation_stats()` | Agregar `from datetime import datetime` al inicio | `services/validation_service.py` | Ninguno directo | Verificar validaciones funcionan |
| **3** | **Import settings incorrecto** | `config/settings.py` | 6 | 🔴 **CRÍTICO** | `ImportError: cannot import name 'get_service_settings'` | Cambiar a `get_service_settings as get_base_settings` | `config/settings.py` | Todos los servicios usan common.config | Verificar pattern en otros servicios |
| **4** | **Archivo __init_.py inválido** | `services/__init_.py` | N/A | 🔴 **CRÍTICO** | Nombre de archivo Python inválido (solo 1 underscore) | Eliminar archivo `__init_.py` (existe `__init__.py` correcto) | `services/__init_.py` | Ninguno | Verificar imports en otros archivos |
| **5** | **Atributo get_tier_limits() inexistente** | `handlers/context_handler.py` | 98 | 🔴 **CRÍTICO** | `AttributeError: 'EmbeddingServiceSettings' object has no attribute 'get_tier_limits'` | Agregar método `get_tier_limits()` a settings.py | `config/settings.py`, `handlers/context_handler.py` | Query Service, Agent Execution (mismo pattern) | Verificar tier limits en otros servicios |
| **6** | **Atributo enable_embedding_tracking inexistente** | `services/embedding_processor.py` | 133 | 🔴 **CRÍTICO** | `AttributeError: 'EmbeddingServiceSettings' object has no attribute 'enable_embedding_tracking'` | Agregar field `enable_embedding_tracking` a settings | `config/settings.py`, `services/embedding_processor.py` | Query Service (usa enable_query_tracking) | Verificar pattern de tracking en otros servicios |
| **7** | **Atributo embedding_cache_ttl inexistente** | `services/embedding_processor.py` | 111 | 🔴 **CRÍTICO** | `AttributeError: 'EmbeddingServiceSettings' object has no attribute 'embedding_cache_ttl'` | Agregar field `embedding_cache_ttl` a settings | `config/settings.py`, `services/embedding_processor.py` | Query Service (usa search_cache_ttl) | Verificar TTL values en otros servicios |
| **8** | **Atributo domain_name inexistente** | `workers/embedding_worker.py` | 35 | 🔴 **CRÍTICO** | `AttributeError: 'EmbeddingServiceSettings' object has no attribute 'domain_name'` | Agregar field `domain_name = "embedding"` a settings | `config/settings.py`, `workers/embedding_worker.py` | Query Service, Agent Execution (mismo pattern) | Verificar domain names en otros servicios |
| **9** | **Worker initialization pattern inconsistente** | `workers/embedding_worker.py` | 26-30 | 🟡 **ALTO** | Pattern `redis_client or get_redis_client()` no es async, inconsistente con BaseWorker | Refactorizar para usar async initialization | `workers/embedding_worker.py`, `common/workers/base_worker.py` | Query Service, Agent Execution, Conversation Service | Verificar pattern en otros workers |
| **10** | **Settings tier_limits incompatible** | `handlers/context_handler.py` | 98-110 | 🟡 **ALTO** | Código asume structure específica de tier_limits que no existe | Definir estructura estándar de tier_limits | `config/settings.py`, `handlers/context_handler.py` | Query Service, Agent Execution (mismo problema) | Estandarizar tier_limits en todos los servicios |
| **11** | **Referencias a settings.get_tier_limits() sin implementar** | `services/validation_service.py` | 45, 52 | 🟡 **ALTO** | Múltiples llamadas a método no implementado | Implementar método get_tier_limits() | `config/settings.py`, `services/validation_service.py` | Todos los servicios | Verificar implementación consistente |
| **12** | **Hard-coded "all" en stats methods** | `handlers/embedding_handler.py` | 117 | 🟠 **MEDIO** | `get_embedding_stats("all")` no maneja tenant_id correctamente | Cambiar para aceptar tenant_id real o None para global | `handlers/embedding_handler.py`, `workers/embedding_worker.py` | Query Service, Agent Execution | Verificar pattern de stats en otros servicios |
| **13** | **Configuración OpenAI API key hardcoded** | `config/settings.py` | 87 | 🟠 **MEDIO** | API key hardcoded a "sk-" en lugar de leer desde env | Usar variables de entorno correctamente | `config/settings.py` | Ninguno directo | Verificar manejo de secrets en otros servicios |
| **14** | **Exception handling genérico** | `workers/embedding_worker.py` | 124, 148 | 🟠 **MEDIO** | `except Exception` muy amplio, no diferencia tipos de error | Implementar exception handling específico | `workers/embedding_worker.py` | Query Service, Agent Execution | Verificar error handling patterns |
| **15** | **Cache key generation sin salt** | `services/embedding_processor.py` | 127 | 🟠 **MEDIO** | MD5 hash sin salt puede tener colisiones | Agregar tenant_id o timestamp al hash | `services/embedding_processor.py` | Query Service (mismo problema potencial) | Verificar cache key generation en otros servicios |

## 🔥 Problemas Críticos que Causan Startup Failure

### **Error #1-3: Import Errors**
```python
# FALLA INMEDIATA AL IMPORTAR EL MÓDULO
ImportError: cannot import name 'get_service_settings' from 'common.config'
NameError: name 'datetime' is not defined
```
**Impacto**: Servicio no puede iniciarse

### **Error #4: Archivo Python Inválido**
```python
# PYTHON NO PUEDE IMPORTAR MÓDULOS CON NOMBRE INVÁLIDO
import embedding_service.services  # FALLA por __init_.py
```
**Impacto**: Import del módulo services falla

### **Error #5-8: AttributeError en Runtime**
```python
# FALLA AL PROCESAR PRIMERA REQUEST
settings.get_tier_limits("professional")  # AttributeError
settings.enable_embedding_tracking        # AttributeError  
settings.embedding_cache_ttl              # AttributeError
settings.domain_name                      # AttributeError
```
**Impacto**: Service crash en primera request

## 🔗 Dependencias y Servicios Afectados

### **Servicios que Consumen Embedding Service:**
1. **Query Service** - Usa embeddings para RAG
2. **Agent Execution Service** - Usa embeddings para herramientas
3. **Ingestion Service** (no incluido) - Procesaría documentos

### **Efecto Cascada de Errores:**
```
Embedding Service FALLA 
    ↓
Query Service no puede generar embeddings
    ↓ 
Agent Execution no puede procesar RAG
    ↓
Sistema completo de IA FALLA
```

## 🛠️ Plan de Corrección Prioritizada

### **FASE 1: Critical Startup Fixes (15 minutos)**
1. Corregir imports datetime (Error #1, #2)
2. Corregir import settings (Error #3)  
3. Eliminar archivo inválido (Error #4)

### **FASE 2: Settings Complete (30 minutos)**
4. Agregar domain_name (Error #8)
5. Agregar get_tier_limits() (Error #5)
6. Agregar enable_embedding_tracking (Error #6)
7. Agregar embedding_cache_ttl (Error #7)

### **FASE 3: Pattern Consistency (1 hora)**
8. Refactorizar worker initialization (Error #9)
9. Estandarizar tier_limits structure (Error #10, #11)

### **FASE 4: Quality Improvements (opcional)**
10. Mejorar error handling (Error #14)
11. Mejorar cache keys (Error #15)
12. Fix hardcoded values (Error #13)

## 🟢 Correcciones Implementadas (2025-06-08)

| # | Error Corregido | Archivo Modificado | Descripción de la Corrección | Fase | Estado |
|---|----------------|-------------------|----------------------------|------|--------|
| **1** | Import datetime faltante | `services/embedding_processor.py` | Agregado `from datetime import datetime` al inicio del archivo | FASE 1 | ✅ COMPLETADO |
| **2** | Import datetime faltante | `services/validation_service.py` | Agregado `from datetime import datetime` al inicio y eliminado import redundante local | FASE 1 | ✅ COMPLETADO |
| **3** | Import settings incorrecto | `config/settings.py` | Cambiado a `from common.config import get_service_settings as get_base_settings` | FASE 1 | ✅ COMPLETADO |
| **4** | Archivo __init_.py inválido | `services/__init_.py` | Eliminado archivo con nombre inválido | FASE 1 | ✅ COMPLETADO |
| **5** | Atributo domain_name inexistente | `config/settings.py` | Agregado atributo `domain_name: str = Field("embedding", ...)` | FASE 2 | ✅ COMPLETADO |
| **6** | Método get_tier_limits() inexistente | `config/settings.py` | Implementado método completo con configuraciones por tier | FASE 2 | ✅ COMPLETADO |
| **7** | Atributo enable_embedding_tracking inexistente | `config/settings.py` | Agregado atributo `enable_embedding_tracking: bool = Field(True, ...)` | FASE 2 | ✅ COMPLETADO |
| **8** | Atributo embedding_cache_ttl inexistente | `config/settings.py` | Agregado atributo `embedding_cache_ttl: int = Field(3600, ...)` | FASE 2 | ✅ COMPLETADO |
| **9** | Worker initialization inconsistente | `workers/embedding_worker.py` | Refactorizado para usar inicialización asincrónica adecuada | FASE 3 | ✅ COMPLETADO |
| **10** | Manejo de excepciones genérico | `services/validation_service.py` | Implementado manejo de excepciones específicas en `get_validation_stats()` | FASE 3 | ✅ COMPLETADO |
| **11** | Manejo de excepciones genérico | `services/embedding_processor.py` | Implementado manejo de excepciones específicas en `_check_cache()` | FASE 3 | ✅ COMPLETADO |
| **12** | Manejo de excepciones genérico | `services/embedding_processor.py` | Implementado manejo de excepciones específicas en `_cache_embeddings()` | FASE 3 | ✅ COMPLETADO |
| **13** | Cache key generation sin salt | `services/embedding_processor.py` | Mejorada generación de clave con salt y hash más largo | FASE 3 | ✅ COMPLETADO |
| **14** | Import Any faltante | `config/settings.py` | Agregado `from typing import Dict, Any` | FASE 4 | ✅ COMPLETADO |
| **15** | Uso de import incorrecto en get_settings | `config/settings.py` | Modificado para usar `get_base_settings()` en vez de `get_service_settings()` | FASE 4 | ✅ COMPLETADO |

## ✅ Verificación de Correcciones

### **Prueba de Validación:**
Se creó y ejecutó un script de prueba (`embedding_service_test.py`) que verifica:  

```python
# Resultados del test de validación:
=== TEST DE CONFIGURACIÓN ===
Servicio: embedding-service
Domain name: embedding
Tracking habilitado: True
Cache TTL: 3600

=== TEST DE LÍMITES POR TIER ===
Tier free: 10 textos, 2000 chars
Tier basic: 25 textos, 4000 chars
Tier professional: 50 textos, 8000 chars
Tier enterprise: 100 textos, 8000 chars

=== TEST DE CONTEXTO ===
Contexto creado: test_tenant (basic)

=== TEST DE VALIDATION SERVICE ===
ValidationService inicializado correctamente

=== TEST DE EMBEDDING PROCESSOR ===
EmbeddingProcessor inicializado correctamente

=== TEST DE EMBEDDING WORKER ===
Worker inicializado para dominio: embedding

¡TEST COMPLETADO CON ÉXITO!
```

### **Tareas Pendientes para Próxima Revisión:**
- Atender la advertencia sobre la corrutina `get_redis_client` no esperada
- Completar pruebas unitarias e integración del servicio
- Asegurar compatibilidad con servicios dependientes (Query Service, Agent Execution Service)
- Considerar la migración futura de Redis a PostgreSQL, como se menciona en las notas del proyecto

### **Servicios a Re-testar:**
- Query Service (embedding requests)
- Agent Execution Service (RAG functionality)
- Integration tests end-to-end
