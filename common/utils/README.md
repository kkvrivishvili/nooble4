# Módulo de Utilidades Comunes (`refactorizado.common.utils`)

Este directorio contiene utilidades genéricas y compartidas que pueden ser utilizadas por cualquier otro módulo o servicio dentro del proyecto Nooble4, complementando la Arquitectura v4.0.

## Contenido del Módulo

Actualmente, este directorio incluye los siguientes módulos:

1. ### 1. `logging.py`

- **Propósito**: Proporciona una función `init_logging()` para configurar el sistema de logging de manera estandarizada en toda la aplicación. Permite la configuración del nivel de log, formato, y handlers (ej. consola, archivo).

(Anteriormente, este módulo también contenía `QueueManager`, que ha sido movido a `common.clients` ya que su funcionalidad está estrechamente ligada a la gestión de colas para el cliente Redis).

**Componentes Principales:**

-   **`init_logging(log_level: str = "INFO", service_name: Optional[str] = None)` (función):**
    -   Inicializa el sistema de logging de Python.
    -   Configura un formato de log que incluye timestamp, nombre del servicio (si se proporciona), nombre del logger, nivel de log y mensaje.
        -   Formato con `service_name`: `%(asctime)s - {service_name} - %(name)s - %(levelname)s - %(message)s`
        -   Formato sin `service_name`: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
    -   Configura un `StreamHandler` para enviar logs a `sys.stdout`.
    -   Establece el nivel de log para el logger raíz (`root_logger`).
    -   Silencia loggers de librerías externas verbosas (ej., `redis` se establece a `WARNING`).

**Uso:**

Se espera que esta función sea llamada una vez al inicio de cada servicio, pasando el `log_level` y `service_name` obtenidos de la configuración centralizada (`CommonAppSettings`).

```python
# Ejemplo de uso en un servicio
from refactorizado.common.utils import init_logging
from refactorizado.common.config import CommonAppSettings

# Asumiendo que 'settings' es una instancia cargada de CommonAppSettings
settings = CommonAppSettings(
    service_name="mi_servicio", 
    log_level="DEBUG", 
    # ... otros settings
)

init_logging(log_level=settings.log_level, service_name=settings.service_name)

import logging
logger = logging.getLogger(__name__)
logger.info("Logging inicializado para mi_servicio.")
```

**Puntos de Configuración (vía `CommonAppSettings` indirectamente):**

-   `log_level`: Determina el nivel mínimo de severidad para los mensajes de log.
-   `service_name`: Identifica el servicio que origina el log.

**Consideraciones:**

-   Este módulo interactúa indirectamente con `CommonAppSettings` para obtener `log_level` y `service_name`. Para más detalles sobre la configuración general y posibles inconsistencias en otros módulos, consulte el archivo principal [`../../inconsistencias.md`](../../inconsistencias.md).

---

### 2. `queue_manager.py`

**Propósito:** Centralizar y estandarizar la generación de nombres para las colas y canales de Redis utilizados en la comunicación inter-servicios.

**Componentes Principales:**

-   **`QueueManager` (clase):**
    -   **Constructor `__init__(self, prefix: str = "nooble4", environment: Optional[str] = None)`:**
        -   `prefix`: Un prefijo global para todos los nombres de colas (ej., "nooble4").
        -   `environment`: El entorno de despliegue (ej., "dev", "staging", "prod"). Intenta obtenerlo de la variable de entorno `ENVIRONMENT` si no se proporciona, con "dev" como valor por defecto.
    -   **Métodos de generación de nombres de colas:**
        -   `get_action_queue(self, service_name: str, context: Optional[str] = None) -> str`:
            -   Formato: `{prefix}:{env}:{service_name}:{context}:actions`
            -   Para colas donde un servicio escucha por acciones a procesar.
        -   `get_response_queue(self, origin_service: str, action_name: str, correlation_id: str, context: Optional[str] = None) -> str`:
            -   Formato: `{prefix}:{env}:{origin_service}:{context}:responses:{action_name}:{correlation_id}`
            -   Para colas de respuesta únicas en flujos pseudo-síncronos.
        -   `get_callback_queue(self, origin_service: str, event_name: str, context: Optional[str] = None) -> str`:
            -   Formato: `{prefix}:{env}:{origin_service}:{context}:callbacks:{event_name}`
            -   Para colas donde un servicio espera callbacks asíncronos.
        -   `get_notification_channel(self, origin_service: str, event_name: str, context: Optional[str] = None) -> str`:
            -   Formato: `{prefix}:{env}:{origin_service}:{context}:notifications:{event_name}`
            -   Para canales de Pub/Sub de Redis.

**Uso:**

Se instancia `QueueManager` (preferiblemente una vez por servicio o componente que interactúa con Redis) y se utilizan sus métodos para obtener los nombres de cola necesarios.

```python
# Ejemplo de uso
from refactorizado.common.utils import QueueManager

# Asumiendo que 'environment' se obtiene de CommonAppSettings o se pasa explícitamente
qm = QueueManager(environment="production")

action_q = qm.get_action_queue(service_name="agent_execution_service")
# Resultado: "nooble4:production:agent_execution_service:actions"

response_q = qm.get_response_queue(
    origin_service="orchestrator_service",
    action_name="run_agent",
    correlation_id="xyz123"
)
# Resultado: "nooble4:production:orchestrator_service:responses:run_agent:xyz123"
```

**Puntos de Configuración:**

-   `prefix` (en el constructor)
-   `environment` (en el constructor o vía variable de entorno `ENVIRONMENT`)

**Consideraciones:**

-   La integración de `QueueManager` con otros componentes como `BaseWorker` y `BaseRedisClient` es un punto importante. Para detalles sobre esto y cómo `prefix` y `environment` podrían integrarse con `CommonAppSettings`, consulte la sección "Módulo `utils`" en el archivo principal [`../../inconsistencias.md`](../../inconsistencias.md).

---

Este directorio está destinado a crecer a medida que se identifican más utilidades comunes. Mantener la documentación actualizada aquí es crucial para la mantenibilidad del proyecto.

Para una visión global de las inconsistencias y puntos de mejora en todos los módulos comunes, por favor refiérase al documento centralizado: [`../../inconsistencias.md`](../../inconsistencias.md).
