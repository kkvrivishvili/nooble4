# Módulo de Utilidades Comunes (`common/utils/`)

Este módulo alberga clases y funciones de utilidad que son compartidas y utilizadas por múltiples servicios y componentes comunes dentro de la arquitectura.

## Componentes Principales

### 1. `QueueManager`

`QueueManager` es una clase de utilidad esencial responsable de generar nombres estandarizados para colas y, más recientemente, para Redis Streams, utilizados en la comunicación entre servicios.

#### Propósito:
-   Asegurar una nomenclatura consistente y predecible para los streams de acciones y las colas de respuesta/callback.
-   Centralizar la lógica de generación de nombres para facilitar cambios o actualizaciones en las convenciones de nomenclatura.
-   Incorporar el entorno (`environment`) en los nombres para aislar los flujos de mensajes entre diferentes despliegues (ej., `dev`, `staging`, `prod`).

#### Configuración:
-   Se inicializa con el parámetro `environment: str`.
    ```python
    from common.utils.queue_manager import QueueManager

    # Ejemplo: Cargar 'environment' desde settings
    # environment = common_app_settings.environment 
    # queue_manager = QueueManager(environment=environment)
    ```

#### Métodos y Convenciones de Nomenclatura:

1.  **`get_service_action_stream(self, service_name: str) -> str`**
    -   **Propósito:** Genera el nombre del Redis Stream principal al que un servicio debe enviar acciones destinadas a `service_name`.
    -   **Convención:** `{environment}:stream:{service_name}:action`
    -   **Ejemplo:**
        ```python
        # qm = QueueManager(environment="dev")
        # stream_name = qm.get_service_action_stream("user_service")
        # # Resultado: "dev:stream:user_service:action"
        ```
    -   **Uso:** Utilizado por `BaseRedisClient` para determinar a qué stream enviar una `DomainAction` y por `BaseWorker` para saber de qué stream leer.

2.  **`get_response_queue_for_action(self, action_id: str) -> str`**
    -   **Propósito:** Genera el nombre de la cola (lista Redis) temporal y única donde un cliente esperará la `DomainActionResponse` en un patrón de comunicación pseudo-síncrono.
    -   **Convención:** `{environment}:queue:response:{action_id}`
    -   **Ejemplo:**
        ```python
        # qm = QueueManager(environment="prod")
        # response_q_name = qm.get_response_queue_for_action("abc-123-xyz")
        # # Resultado: "prod:queue:response:abc-123-xyz"
        ```
    -   **Uso:** Utilizado por `BaseRedisClient` (en `send_action_pseudo_sync`) para establecer el `callback_queue_name` en la `DomainAction` saliente y para escuchar la respuesta.

3.  **`get_callback_queue_name(self, origin_service_name: str, action_id: str) -> str`**
    -   **Propósito:** Genera el nombre de la cola (lista Redis) donde un cliente esperará una `DomainAction` de callback en un patrón asíncrono con callback.
    -   **Convención:** `{environment}:queue:callback:{origin_service_name}:{action_id}` (Esta convención puede variar o simplificarse si `action_id` ya garantiza unicidad globalmente para callbacks).
    -   **Ejemplo:**
        ```python
        # qm = QueueManager(environment="dev")
        # cb_q_name = qm.get_callback_queue_name("order_service", "order-456")
        # # Resultado: "dev:queue:callback:order_service:order-456"
        ```
    -   **Uso:** Utilizado por `BaseRedisClient` (en `send_action_async_with_callback`) para establecer el `callback_queue_name`.

#### Integración:
-   `BaseRedisClient` instancia y utiliza `QueueManager` internamente para determinar los nombres correctos de los streams/colas al enviar acciones.
-   `BaseWorker` también utiliza `QueueManager` para determinar el nombre del stream de acciones que debe escuchar.
-   La correcta configuración del `environment` en `QueueManager` (derivada de `CommonAppSettings`) es crucial para asegurar que los componentes interactúen con los streams/colas correctos en el entorno de despliegue adecuado.


