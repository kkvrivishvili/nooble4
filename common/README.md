# Common Module

## Características y Estado

| Característica | Descripción | Estado |
|-----------------|-------------|--------|
| **DomainAction** | Sistema unificado de acciones entre servicios | ✅ Completo |
| **ExecutionContext** | Contexto unificado para agentes y workflows | ✅ Completo |
| **DomainQueueManager** | Gestión de colas por dominio y tier | ✅ Completo |
| **BaseWorker** | Workers asíncronos para procesamiento de tareas | ✅ Completo |
| **Settings** | Configuración centralizada para todos los servicios | ✅ Completo |
| **Redis Pool** | Pool de conexiones Redis compartido | ✅ Completo |
| **Error Handling** | Manejo unificado de errores | ✅ Completo |
| **Métricas** | Sistema básico de métricas | ⚠️ Parcial |
| **Persistencia DB** | Capa de acceso a base de datos | ❌ Pendiente |
| **Observabilidad** | Logging y tracing avanzado | ❌ Pendiente |

## Estructura de Archivos y Carpetas

```plaintext
common/
├ __init__.py
├ config.py
├ context.py
├ errors.py
├ redis_pool.py
├ helpers/
│  ├ __init__.py
│  └ logging_helper.py
├ models/
│  ├ __init__.py
│  ├ actions.py
│  └ execution_context.py
├ services/
│  ├ __init__.py
│  ├ action_processor.py
│  └ domain_queue_manager.py
├ utils/
│  ├ __init__.py
│  └ validation.py
└ workers/
   ├ __init__.py
   └ base_worker.py
```

## Arquitectura

El módulo Common proporciona la infraestructura compartida para todos los servicios backend de nooble4, implementando patrones comunes para comunicación, procesamiento, configuración y gestión de errores.

### Diagrama de Integración

```
                      ┌─────────────────────────────────────────┐
                      │              Common Module              │
                      │                                         │
                      │  ┌───────────┐        ┌────────────┐    │
                      │  │           │        │            │    │
                      │  │ Models    │        │ Services   │    │
                      │  │           │        │            │    │
                      │  └───────────┘        └────────────┘    │
                      │                                         │
                      │  ┌───────────┐        ┌────────────┐    │
                      │  │           │        │            │    │
                      │  │ Workers   │        │ Utils      │    │
                      │  │           │        │            │    │
                      │  └───────────┘        └────────────┘    │
                      │                                         │
                      └─────────────────────────────────────────┘
                                       │
                                       │
                                       ▼
┌─────────────────┐   ┌─────────────────────┐   ┌───────────────────┐
│                 │   │                     │   │                   │
│ Agent Execution │   │ Agent Management    │   │ Embedding Service │
│                 │   │                     │   │                   │
└─────────────────┘   └─────────────────────┘   └───────────────────┘
                                   
          ┌─────────────────┐   ┌───────────────────┐   ┌─────────────────┐
          │                 │   │                   │   │                 │
          │ Query Service   │   │ Ingestion Service │   │ Orchestrator    │
          │                 │   │                   │   │                 │
          └─────────────────┘   └───────────────────┘   └─────────────────┘
```

### Flujo de Domain Actions

```
Servicio A                 Redis                    Servicio B
   │                        │                          │
   │                        │                          │
   │ 1. Crear DomainAction  │                          │
   │───────┐                │                          │
   │       │                │                          │
   │<──────┘                │                          │
   │                        │                          │
   │ 2. Encolar con         │                          │
   │    DomainQueueManager  │                          │
   │─────────────────────────>                         │
   │                        │                          │
   │                        │  3. BaseWorker procesa   │
   │                        │     mensajes en cola     │
   │                        │<─────────────────────────│
   │                        │                          │
   │                        │  4. Procesar con         │
   │                        │     ActionProcessor      │
   │                        │      ┌──────────────────>│
   │                        │      │                   │
   │                        │      │                   │
   │                        │      │                   │
   │                        │      │                   │
   │                        │  5. Enviar resultado     │
   │                        │     a callback_queue     │
   │                        │<─────────────────────────│
   │                        │                          │
   │ 6. Procesar callback   │                          │
   │<─────────────────────────                         │
   │                        │                          │
```

## Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **DomainAction** | Modelo base para comunicación entre servicios | ✅ Completo |
| **ExecutionContext** | Contexto unificado para operaciones | ✅ Completo |
| **DomainQueueManager** | Gestión avanzada de colas por tier | ✅ Completo |
| **BaseWorker** | Procesamiento asíncrono de tareas | ✅ Completo |
| **ActionProcessor** | Framework para procesar acciones | ✅ Completo |
| **RedisPool** | Gestión optimizada de conexiones Redis | ✅ Completo |

## Sistema de Colas y Prioridades

El módulo implementa un sistema avanzado de colas con las siguientes características:

1. **Formato de Colas**: `{domain}:{tenant_id}:{tier}`
   - Ejemplo: `embedding:tenant123:professional`

2. **Prioridades por Tier**:
   - Enterprise: Prioridad 1 (máxima)
   - Professional: Prioridad 2
   - Advance: Prioridad 3
   - Free: Prioridad 4 (mínima)

3. **Rate Limiting por Tier**:

| Tier | Reqs/Minuto | Reqs/Día | Timeout (s) |
|------|-------------|----------|-------------|
| Free | 10 | 100 | 30 |
| Advance | 50 | 1,000 | 60 |
| Professional | 200 | 10,000 | 120 |
| Enterprise | Sin límite | Sin límite | 300 |

## Implementación de Domain Actions

Las Domain Actions son el patrón fundamental para la comunicación entre servicios siguiendo estas convenciones:

1. **Nomenclatura**: `{dominio}.{acción}`
   - Ejemplos: `embedding.generate`, `query.search`, `agent.execute`

2. **Estructura**:
   - `action_id`: Identificador único
   - `action_type`: Tipo de acción (dominio.acción)
   - `task_id`: ID de la tarea relacionada
   - `tenant_id`: ID del tenant
   - `tenant_tier`: Tier del tenant
   - `session_id`: ID de sesión (opcional)
   - `callback_queue`: Cola para enviar resultados
   - `data`: Payload específico de la acción
   - `metadata`: Metadatos adicionales

## Configuración

El módulo Common proporciona una clase base `Settings` que todos los servicios extienden con sus configuraciones específicas:

```python
# Ejemplo de uso en servicios
class MyServiceSettings(Settings):
    domain_name: str = "myservice"
    custom_setting: str = Field(default="value", description="Mi configuración")
    
    class Config:
        env_prefix = "MY_SERVICE_"
```

## Inconsistencias y Próximos Pasos

### Inconsistencias Actuales

- **Persistencia Parcial**: Similar a todos los servicios, se utiliza Redis como almacén temporal pero falta implementar una capa de persistencia para datos permanentes en PostgreSQL.

- **Métricas Básicas**: El sistema de métricas está implementado parcialmente pero carece de agregación, visualización y almacenamiento.

- **Observabilidad Limitada**: Aunque incluye manejo básico de errores, falta implementar tracing distribuido y logging avanzado.

- **Falta Multi-tenancy Completo**: El sistema está diseñado para multi-tenancy pero faltan algunas validaciones y separaciones completas de datos entre tenants.

### Próximos Pasos

1. **Migración a PostgreSQL**: Implementar capa de persistencia en base de datos relacional para datos permanentes.

2. **Sistema de Métricas Completo**: Expandir la recolección de métricas con dashboard de visualización y alertas.

3. **Observabilidad Avanzada**: Implementar tracing distribuido y logging centralizado para todos los servicios.

4. **Testing Automático**: Mejorar cobertura de pruebas para componentes críticos.

5. **Documentación API**: Añadir documentación detallada para cada componente y patrón.

## Desarrollo

Para usar el módulo Common en un nuevo servicio:

```python
from common import (
    DomainAction, BaseWorker, 
    get_redis_client, Settings,
    setup_error_handling
)
```
