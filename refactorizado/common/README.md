# Módulo Común (`refactorizado.common`)

Este directorio (`refactorizado/common/`) alberga el código compartido y las utilidades fundamentales utilizadas por los diversos microservicios que componen la aplicación Nooble4. Su objetivo es promover la reutilización de código, asegurar la consistencia y centralizar la lógica de negocio transversal.

## Estructura del Módulo

El módulo `common` está organizado en los siguientes submódulos:

-   **`clients/`**: Contiene clientes base para interactuar con servicios externos o sistemas de mensajería, como el `BaseRedisClient` para la comunicación vía Redis.
-   **`config/`**: Define la configuración base de la aplicación (`CommonAppSettings`) y las clases de configuración específicas para cada servicio, facilitando una gestión de settings centralizada y heredable.
-   **`exceptions/`**: Agrupa un conjunto de clases de excepción personalizadas y estandarizadas para el manejo de errores a lo largo de la aplicación.
-   **`handlers/`**: Proporciona la lógica base para el manejo de acciones o mensajes, como el `BaseActionHandler`.
-   **`models/`**: Define los modelos de datos Pydantic comunes que se utilizan para la comunicación entre servicios y la representación de entidades, como `DomainAction`, `DomainActionResponse`, y `ExecutionContext`.
-   **`utils/`**: Contiene diversas utilidades compartidas, como la inicialización del logging (`init_logging`) y el gestor de colas (`QueueManager`).
-   **`workers/`**: Incluye la implementación base para los workers (`BaseWorker`) que procesan tareas de forma asíncrona.

## Uso

Los componentes de este módulo se importan directamente en los servicios que los requieren. El archivo `refactorizado/common/__init__.py` exporta las clases y funciones más relevantes para facilitar su acceso, permitiendo importaciones como:

```python
from refactorizado.common import CommonAppSettings, BaseWorker, DomainAction
```
