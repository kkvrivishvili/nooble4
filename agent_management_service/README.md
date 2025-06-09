# Agent Management Service

> **ACTUALIZACIÓN**: Se ha migrado toda la comunicación entre servicios de HTTP directo al patrón pseudo-síncrono sobre Redis. Todos los clientes y workers ahora implementan el patrón BaseWorker 4.0.

> **OPTIMIZACIÓN PROPUESTA**: Se propone almacenar toda la información de configuración de agentes (incluyendo collection_ids asociados y modelos de embeddings) directamente en la estructura del agente, eliminando así la necesidad de comunicación adicional con el Ingestion Service durante la carga de la configuración del agente.

## Características y Estado

| Característica | Descripción | Estado |
|-----------------|-------------|--------|
| **CRUD de Agentes** | Gestión completa de agentes con configuración personalizada | ✅ Completo |
| **Sistema de Templates** | Templates predefinidos y personalizados por tenant | ✅ Completo |
| **Validación por Tiers** | Límites y capacidades según el tier del tenant | ✅ Completo |
| **Integración RAG** | Conexión con collections para búsqueda | ✅ Completo |
| **Cache de Agentes** | Configuración de agentes en Redis con TTL | ✅ Completo |
| **Domain Actions** | Comunicación asíncrona con otros servicios | ✅ Completo |
| **Slug y URLs Públicas** | Acceso público a agentes vía URL personalizada | ⚠️ Parcial |
| **Sistema de Métricas** | Estadísticas de uso, rendimiento y costos | ⚠️ Parcial |
| **Persistencia en DB** | Almacenamiento en PostgreSQL | ❌ Pendiente |
| **Sistema de Workflows** | Flujos avanzados para tier Enterprise | ❌ Pendiente |

## Estructura de Archivos y Carpetas

```plaintext
agent_management_service/
├ __init__.py
├ main.py
├ README.md
├ requirements.txt
├ clients/
│  ├ __init__.py
│  ├ execution_client.py
│  └ ingestion_client.py
├ config/
│  ├ __init__.py
│  └ settings.py
├ models/
│  ├ __init__.py
│  ├ agent_model.py
│  ├ template_model.py
│  └ actions_model.py
├ routes/
│  ├ __init__.py
│  ├ agents.py
│  ├ templates.py
│  └ health.py
├ services/
│  ├ __init__.py
│  ├ agent_service.py
│  ├ template_service.py
│  └ validation_service.py
├ templates/
│  ├ customer_service.json
│  ├ knowledge_base.json
│  └ sales_assistant.json
└ workers/
   ├ __init__.py
   └ management_worker.py
```

## Arquitectura

### Diagrama de Integración

```
┌─────────────────┐      ┌─────────────────────┐      ┌────────────────────┐
│                 │      │                     │      │                    │
│     Cliente     │<---->│  Agent Management   │<---->│  Agent Execution   │
│    Frontend     │ REST │      Service        │ Redis │     Service        │
│                 │      │                     │ Queue │                    │
└─────────────────┘      └─────────────────┬───┘      └────────────────────┘
                                           │
                                           │
                                           ▼
                         ┌─────────────────────────────┐
                         │                             │
                         │     Ingestion Service       │
                         │  (Validación Collections)   │
                         │                             │
                         └─────────────────────────────┘
```

### Flujo de Creación y Uso de Agentes

```
Frontend               Management Service         Execution Service         Ingestion Service
   │                         │                         │                         │
   │ 1. Crear Agente         │                         │                         │
   │─────────────────────────>                         │                         │
   │                         │                         │                         │
   │                         │ 2. Validar Collections  │                         │
   │                         │───────────────────────────────────────────────────>
   │                         │                         │                         │
   │                         │ 3. Resultado Validación │                         │
   │                         │<───────────────────────────────────────────────────
   │                         │                         │                         │
   │                         │ 4. Almacenar Agente     │                         │
   │                         │─────────┐               │                         │
   │                         │         │               │                         │
   │                         │<────────┘               │                         │
   │                         │                         │                         │
   │                         │ 5. Notificar Agente     │                         │
   │                         │────────────────────────>│                         │
   │                         │                         │                         │
   │ 6. Respuesta Creación   │                         │                         │
   │<─────────────────────────                         │                         │
   │                         │                         │                         │
   │ 7. Usar Agente          │                         │                         │
   │───────────────────────────────────────────────────>                         │
   │                         │                         │                         │
   │ 8. Respuestas Agente    │                         │                         │
   │<───────────────────────────────────────────────────                         │
```

### Integración con Backend Existente

- **Domain Actions**: Implementa el sistema de Domain Actions para comunicación asíncrona
- **DomainQueueManager**: Integrado con colas por tier para priorización de tareas
- **ExecutionContext**: Compatible con contextos de ejecución unificados entre servicios
- **Redis**: Utiliza Redis para colas de mensajes, caché y almacenamiento temporal

### Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **AgentService** | Lógica CRUD de agentes y validación | ✅ Completo |
| **TemplateService** | Gestión de templates y aplicación | ✅ Completo |
| **ValidationService** | Validaciones de configuración y tier | ✅ Completo |
| **ManagementWorker** | Procesamiento asíncrono de tareas | ✅ Completo |
| **ExecutionClient** | Cliente para comunicación con Execution Service | ✅ Completo |
| **IngestionClient** | Cliente para validar collections | ✅ Completo |

## Domain Actions

El servicio procesa las siguientes acciones de dominio:

### AgentValidationAction

```json
{
  "action_type": "agent.validate",
  "tenant_id": "client123",
  "agent_id": "agent_xyz789",
  "tier": "professional",
  "collections": ["docs_collection_1", "kb_collection_2"],
  "callback_queue": "management:client123:callback"
}
```

### CacheInvalidationAction

```json
{
  "action_type": "cache.invalidate",
  "tenant_id": "client123",
  "agent_id": "agent_xyz789",
  "object_type": "agent_config"
}
```

## API HTTP

### Gestión de Agentes

**POST** `/api/v1/agents`

Crea un nuevo agente.

- **Headers**:
  - `X-Tenant-ID`: ID del tenant
  - `X-Tenant-Tier`: Tier del tenant
- **Body**:
  ```json
  {
    "name": "Mi Asistente de Soporte",
    "description": "Asistente para atención al cliente",
    "agent_type": "customer_support",
    "configuration": {
      "model": "llama3-70b-8192",
      "temperature": 0.7,
      "tools": ["datetime", "rag_query"],
      "collections": ["docs_collection_1"],
      "system_prompt": "Eres un asistente de soporte..."
    },
    "metadata": {
      "team": "soporte",
      "version": "1.0"
    }
  }
  ```

**GET** `/api/v1/agents`

Obtiene la lista de agentes del tenant.

**GET** `/api/v1/agents/{agent_id}`

Obtiene un agente específico.

**PATCH** `/api/v1/agents/{agent_id}`

Actualiza un agente existente.

### Gestión de Templates

**GET** `/api/v1/templates`

Obtiene la lista de templates disponibles para el tenant/tier.

**POST** `/api/v1/templates/from-template`

Crea un agente a partir de un template existente.

- **Headers**:
  - `X-Tenant-ID`: ID del tenant
  - `X-Tenant-Tier`: Tier del tenant
- **Body**:
  ```json
  {
    "template_id": "customer_service_v1",
    "name": "Mi Agente de Soporte",
    "customizations": {
      "temperature": 0.5,
      "collections": ["support_docs"]
    }
  }
  ```

## Configuración

### Variables de Entorno

Todas las variables de entorno utilizan el prefijo `AGENT_MANAGEMENT_`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `AGENT_MANAGEMENT_REDIS_URL` | URL para conexión Redis | redis://localhost:6379/0 |
| `AGENT_MANAGEMENT_INGESTION_SERVICE_URL` | URL del servicio de ingestión | http://localhost:8006 |
| `AGENT_MANAGEMENT_EXECUTION_SERVICE_URL` | URL del servicio de ejecución | http://localhost:8005 |
| `AGENT_MANAGEMENT_AGENT_CONFIG_CACHE_TTL` | TTL del caché de configuración (segundos) | 300 |
| `AGENT_MANAGEMENT_DATABASE_URL` | URL para base de datos PostgreSQL | postgresql://user:pass@localhost/nooble_agents |

## Límites por Tier

| Tier | Agentes | Herramientas | Modelos | Collections/Agente | Templates |
|------|---------|--------------|---------|-------------------|-----------|
| **Free** | 1 | Básicas | llama3-8b-8192 | 1 | Solo Customer Service |
| **Advance** | 3 | Básicas + RAG | llama3-8b/70b | 3 | CS + Knowledge Base |
| **Professional** | 10 | Todas | Todos | 10 | Todos + Custom |
| **Enterprise** | Ilimitado | Todas + Custom | Todos + Custom | Ilimitado | Todos + Custom + Workflows |

## Templates Predefinidos

1. **Customer Service** (free+): Atención al cliente básica
2. **Knowledge Base** (advance+): Agente RAG para documentación
3. **Sales Assistant** (professional+): Asistente de ventas avanzado

## Health Checks

- `GET /health` ➔ 200 OK
- `GET /health/detailed` ➔ Estado detallado de componentes

## Inconsistencias y Próximos Pasos

### Inconsistencias Actuales

- **Persistencia Temporal**: Actualmente se utiliza Redis para almacenar datos que deberían estar en una base de datos persistente. Es necesario implementar la capa de persistencia con PostgreSQL.

- **Métricas Básicas**: El endpoint `/internal/metrics` devuelve valores estáticos. Es necesario implementar la recolección real de métricas de uso y rendimiento.

- **URLs Públicas Parciales**: El sistema de slugs y URLs públicas para acceso directo a agentes está parcialmente implementado, falta integración con frontend.

- **Validación de Collections Asíncrona**: La validación de collections podría optimizarse para ser más eficiente.

### Próximos Pasos

1. **Migración a PostgreSQL**: Implementar persistencia en base de datos relacional para datos permanentes de agentes, templates y configuraciones.

2. **Sistema de Workflows**: Desarrollar el sistema de workflows avanzados para el tier Enterprise, permitiendo encadenamiento de agentes y procesos complejos.

3. **Dashboard de Analíticas**: Implementar un dashboard para visualización de estadísticas de uso y rendimiento de agentes.

4. **Expansión de Templates**: Añadir más templates predefinidos y mejorar el sistema de personalización con IA generativa.

5. **Integración Frontend Completa**: Completar las rutas para la integración con la interfaz de usuario, especialmente para slugs y URLs públicas.

## Desarrollo

Para ejecutar el servicio en modo desarrollo:

```bash
uvicorn main:app --reload --port 8003
```
