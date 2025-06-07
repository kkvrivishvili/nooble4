# Agent Management Service

Servicio de gestión de agentes con sistema de templates y validación por tiers.

## Características

- **CRUD completo de agentes**: Crear, leer, actualizar y eliminar agentes
- **Sistema de templates**: Templates predefinidos y personalizados por tenant
- **Validación por tiers**: Límites y capacidades según el tier del tenant
- **Integración con servicios**: Validación de collections y cache invalidation
- **Cache con Redis**: Configuraciones de agentes en cache para performance
- **Domain Actions**: Comunicación asíncrona con otros servicios

## Arquitectura

### Integración con Backend Existente
- **Domain Actions**: Usa el sistema de Domain Actions existente
- **DomainQueueManager**: Integra con colas por tier
- **ExecutionContext**: Compatible con contextos de ejecución unificados
- **Common utilities**: Usa helpers, configuración y workers base

### Servicios Integrados
- **Ingestion Service**: Para validar collections existentes
- **Agent Execution Service**: Para invalidación de cache de agentes

## Configuración

```env
# Agent Management Service
AGENT_MANAGEMENT_SERVICE_NAME=agent-management-service
AGENT_MANAGEMENT_SERVICE_VERSION=1.0.0
AGENT_MANAGEMENT_LOG_LEVEL=INFO

# Redis
AGENT_MANAGEMENT_REDIS_URL=redis://localhost:6379/0

# Servicios externos
AGENT_MANAGEMENT_INGESTION_SERVICE_URL=http://localhost:8006
AGENT_MANAGEMENT_EXECUTION_SERVICE_URL=http://localhost:8005

# Cache
AGENT_MANAGEMENT_AGENT_CONFIG_CACHE_TTL=300

# Base de datos (futuro)
AGENT_MANAGEMENT_DATABASE_URL=postgresql://user:pass@localhost/nooble_agents
```

## Uso

### Crear agente
```http
POST /api/v1/agents
Headers: X-Tenant-ID, X-Tenant-Tier
Body: CreateAgentRequest
```

### Crear agente desde template
```http
POST /api/v1/templates/from-template
Headers: X-Tenant-ID, X-Tenant-Tier
Body: {
  "template_id": "customer_service_v1",
  "name": "Mi Agente de Soporte",
  "customizations": {"temperature": 0.5}
}
```

### Listar templates disponibles
```http
GET /api/v1/templates
Headers: X-Tenant-ID, X-Tenant-Tier
```

## Templates Predefinidos

1. **Customer Service** (free+): Atención al cliente básica
2. **Knowledge Base** (advance+): Agente RAG para documentación
3. **Sales Assistant** (professional+): Asistente de ventas avanzado

## Límites por Tier

- **Free**: 1 agente, herramientas básicas, 1 collection
- **Advance**: 3 agentes, herramientas RAG, 3 collections
- **Professional**: 10 agentes, todas las herramientas, templates custom
- **Enterprise**: Sin límites, workflows avanzados, white label

## Desarrollo

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servicio
uvicorn main:app --reload --port 8003
```