# Agent Management Service

Servicio de gestión de agentes con sistema de templates y validación por tiers. Permite crear, configurar, monitorear y administrar agentes conversacionales con diferentes capacidades según el nivel (tier) del usuario.

## Características y Estado de Implementación

| Característica | Descripción | Estado |
|---------------|-------------|--------|
| **Gestión de agentes** | CRUD completo de agentes con configuración personalizada | Operativo |
| **Sistema de templates** | Templates predefinidos y personalizados por tenant | Operativo |
| **Validación por tiers** | Límites y capacidades según el tier del tenant | Operativo |
| **Integración RAG** | Conexión con collections para búsqueda | Operativo |
| **Cache de agentes** | Configuraciones de agentes en cache con Redis | Operativo |
| **Domain Actions** | Comunicación asíncrona con otros servicios | Operativo |
| **Slug y URLs públicas** | Acceso público a agentes vía URL personalizada | Parcial (falta frontend) |
| **Persistencia en DB** | Almacenamiento en base de datos PostgreSQL | Pendiente (usando Redis) |
| **Métricas avanzadas** | Estadísticas de uso y rendimiento detalladas | Parcial (básicas implementadas) |
| **Sistema de workflows** | Flujos avanzados para Enterprise tier | Pendiente |

## Arquitectura

### Integración con Backend Existente
- **Domain Actions**: Implementa el sistema de Domain Actions para comunicación asíncrona
- **DomainQueueManager**: Integrado con colas por tier para priorización de tareas
- **ExecutionContext**: Compatible con contextos de ejecución unificados entre servicios
- **Common utilities**: Utiliza helpers, configuración y workers base del sistema

### Servicios Integrados
- **Ingestion Service**: Para validar collections existentes y listar collections disponibles
- **Agent Execution Service**: Para invalidación de cache de agentes y coordinación de ejecución

### Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **AgentService** | Lógica principal para CRUD de agentes | ✅ Completo |
| **TemplateService** | Gestión de templates y aplicación | ✅ Completo |
| **ValidationService** | Validaciones de configuración y tier | ✅ Completo |
| **ManagementWorker** | Procesamiento asíncrono de tareas | ✅ Completo |
| **ExecutionClient** | Cliente para comunicación con Execution Service | ✅ Completo |
| **IngestionClient** | Cliente para validar collections | ✅ Completo |

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

## Inconsistencias y Pendientes

### Inconsistencias Actuales
1. **Persistencia**: Actualmente se utiliza Redis para almacenar datos que deberían estar en una base de datos persistente. Es necesario implementar la capa de persistencia con PostgreSQL.

2. **Tests**: La cobertura de pruebas es limitada. Se deben implementar pruebas unitarias y de integración más robustas.

3. **Métricas**: El endpoint `/internal/metrics` devuelve valores estáticos. Es necesario implementar la recolección real de métricas.

### Próximos Pasos

1. **Implementar persistencia en PostgreSQL**: Migrar del almacenamiento en Redis a una base de datos relacional para datos permanentes.

2. **Sistema de workflows**: Desarrollar el sistema de workflows avanzados para el tier Enterprise.

3. **Dashboard de analíticas**: Implementar un dashboard para visualización de estadísticas de uso y rendimiento.

4. **Integración con frontend**: Completar las rutas para la integración con la interfaz de usuario.

5. **Expansión de templates**: Añadir más templates predefinidos y mejorar el sistema de personalización.

## Conclusión

El servicio de Agent Management está operativo para las funcionalidades principales de gestión de agentes y templates. Se requieren mejoras en la persistencia y funciones avanzadas para ser considerado una solución completa y robusta en producción.