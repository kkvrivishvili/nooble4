📚 DOCUMENTACIÓN DE IMPLEMENTACIÓN
Configuración Requerida
Variables de Entorno
bash# Redis (requerido para todos los servicios)
REDIS_URL=redis://localhost:6379/0

# Rate Limiting (opcional, usa defaults si no se especifica)
RATE_LIMIT_FREE_PER_MINUTE=10
RATE_LIMIT_FREE_PER_DAY=100
RATE_LIMIT_ADVANCE_PER_MINUTE=50
RATE_LIMIT_ADVANCE_PER_DAY=1000
RATE_LIMIT_PROFESSIONAL_PER_MINUTE=200
RATE_LIMIT_PROFESSIONAL_PER_DAY=10000
# Enterprise no tiene límites

# Timeouts por tier (opcional)
TIMEOUT_FREE=30
TIMEOUT_ADVANCE=60
TIMEOUT_PROFESSIONAL=120
TIMEOUT_ENTERPRISE=300
Dependencias Python
txt# Agregar a requirements.txt de cada servicio:
redis==5.0.0
Especificaciones de Colas
Formato de Colas
{domain}:{context_id}:{tier}

Ejemplos:
- execution:agent-123:professional
- embedding:agent-456:enterprise  
- query:workflow-789:free
- orchestrator:tenant-123:callbacks
Prioridad de Procesamiento
1. enterprise    (prioridad 1 - más alta)
2. professional  (prioridad 2)
3. advance       (prioridad 3)  
4. free          (prioridad 4 - más baja)
Rate Limits por Tier
free:         10 req/min,  100 req/day
advance:      50 req/min,  1K req/day
professional: 200 req/min, 10K req/day
enterprise:   sin límites
Cómo Usar en Servicios
1. Inicialización en Servicio
python# En main.py de cada servicio
from common.services.domain_queue_manager import DomainQueueManager
from common.redis_pool import get_redis_client

# Inicializar
redis_client = get_redis_client()
queue_manager = DomainQueueManager(redis_client)
2. Encolado de Acciones
python# En routes o handlers
from common.models.execution_context import ExecutionContextResolver

# Resolver contexto desde URL
resolver = ExecutionContextResolver()
context = await resolver.resolve_from_url("usuario", "agente-ventas")

# Crear y encolar acción
action = ChatSendMessageAction(...)
await queue_manager.enqueue_execution(action, "execution", context)
3. Worker Configuration
python# En worker de cada servicio
class MyServiceWorker(BaseWorker):
    def __init__(self, redis_client, action_processor):
        super().__init__(redis_client, action_processor)
        self.domain = "my_service"  # IMPORTANTE: Definir dominio
Métricas y Observabilidad
Endpoints de Métricas
python# Agregar a cada servicio
@router.get("/metrics/queues")
async def get_queue_metrics():
    return await queue_manager.get_queue_stats(DOMAIN_NAME)

@router.get("/metrics/system")  
async def get_system_metrics():
    monitor = QueueMonitor(redis_client)
    return await monitor.get_system_overview()
Keys de Redis para Monitoring
# Métricas de uso
usage:{tenant_id}:{date}                   # Uso por tenant por día
usage:tier:{tier}:{date}                   # Uso por tier por día

# Estadísticas de colas  
queue_stats:{queue_name}                   # Stats por cola específica

# Rate limiting
rate_limit:{tenant_id}:minute:{timestamp}  # Rate limit por minuto
rate_limit:{tenant_id}:day:{date}          # Rate limit por día
Troubleshooting
Problemas Comunes

"Rate limit excedido": Verificar tier del tenant y límites configurados
"Cola no encontrada": Verificar formato de queue_name y que el dominio esté correcto
"Contexto no resuelto": Implementar lookup real en ExecutionContextResolver

Debugging
python# Ver estado de colas
await queue_manager.get_queue_stats("execution")

# Ver métricas de tenant
tenant_key = f"usage:{tenant_id}:{date.today().isoformat()}"
usage = await redis.hgetall(tenant_key)
Próximos Pasos

Implementar lookup real en ExecutionContextResolver._resolve_agent_context()
Configurar monitoreo con Prometheus/Grafana para métricas de colas
Implementar alertas para rate limits y colas saturadas
Testing con múltiples tenants y tiers simultáneamente