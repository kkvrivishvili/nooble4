# Módulo Común (`refactorizado.common`)

Este directorio (`refactorizado/common/`) alberga Este módulo, `common`, es el corazón de la infraestructura compartida y los patrones de diseño para todos los microservicios dentro del proyecto Nooble4, alineado con la **Arquitectura v4.0**. Su objetivo es proporcionar una base sólida y consistente para el desarrollo, asegurando que los servicios se construyan de manera modular, mantenible y escalable.

La Arquitectura v4.0 se basa en tres pilares fundamentales definidos en `common`:
1.  **`common.workers.BaseWorker`**: La capa de infraestructura. Responsable de la comunicación con Redis (consumir acciones) y delegar la lógica de negocio.
2.  **`common.services.BaseService`**: La capa de lógica de negocio. Orquesta las operaciones y utiliza componentes especializados para tareas específicas.
3.  **`common.handlers.BaseHandler` y derivados**: Componentes especializados y de responsabilidad única (ej. `BaseContextHandler`, `BaseCallbackHandler`) utilizados por la Capa de Servicio.

## Estructura del Módulo

El módulo `common` está organizado en los siguientes submódulos:

-   **`clients/`**: Contiene clientes base para interactuar con servicios externos o sistemas de mensajería, como el `BaseRedisClient` para la comunicación vía Redis.
-   **`config/`**: Define la configuración base de la aplicación (`CommonAppSettings`) y las clases de configuración específicas para cada servicio, facilitando una gestión de settings centralizada y heredable.
-   **`exceptions/`**: Agrupa un conjunto de clases de excepción personalizadas y estandarizadas para el manejo de errores a lo largo de la aplicación.
-   **`handlers/`**: Proporciona la lógica base para el manejo de acciones o mensajes, como el `BaseActionHandler`.
-   **`models/`**: Define los modelos de datos Pydantic comunes que se utilizan para la comunicación entre servicios y la representación de entidades, como `DomainAction`, `DomainActionResponse`, y `ExecutionContext`.
-   **`redis_pool.py`**: Gestión centralizada de pools de conexiones Redis, utilizada por los componentes de infraestructura.
-   **`utils/`**: Contiene diversas utilidades compartidas, como la inicialización del logging (`init_logging`) y el gestor de colas (`QueueManager`).
-   **`workers/`**: Incluye la implementación base para los workers (`BaseWorker`) que procesan tareas de forma asíncrona.

## Uso

Los componentes de este módulo se importan directamente en los servicios que los requieren. El archivo `refactorizado/common/__init__.py` exporta las clases y funciones más relevantes para facilitar su acceso, permitiendo importaciones como:

```python
from refactorizado.common import CommonAppSettings, BaseWorker, DomainAction
```
