# Módulo de Workers (Query Service)

## 1. Propósito del Módulo

El módulo `workers` es el **punto de entrada de ejecución y el motor de procesamiento de tareas** del `Query Service` cuando opera en un entorno asíncrono basado en mensajería. Su función principal es conectar el servicio a la infraestructura de mensajería (específicamente Redis Streams) y consumir las tareas (encapsuladas como objetos `DomainAction`) que deben ser procesadas.

El worker actúa como un bucle continuo que escucha nuevos mensajes en un stream de Redis específico, los recoge, los deserializa y los pasa a la capa de servicio (`QueryService`) para su procesamiento lógico. Es, en esencia, el componente que impulsa el microservicio en respuesta a eventos externos.

## 2. Archivos y Clases Implementadas

Este módulo se centra en un archivo principal:

-   **`query_worker.py`**: Define la clase `QueryWorker`.

### `QueryWorker` (Clase Principal)

-   **Herencia de `common.workers.BaseWorker`**: Esta es la característica de diseño más importante. `QueryWorker` hereda de `BaseWorker`, una clase del módulo `common` que abstrae toda la lógica compleja y genérica de la interacción con Redis Streams. Esto incluye:
    -   Gestión de la conexión asíncrona a Redis.
    -   Creación o unión a un grupo de consumidores en un stream específico.
    -   El bucle principal de lectura de mensajes (`read_from_stream`).
    -   Deserialización básica del mensaje de Redis a un objeto `DomainAction`.
    -   Manejo de errores a nivel de infraestructura (ej. problemas de conexión).
    -   Gestión del ciclo de vida del mensaje, incluyendo el acuse de recibo (ACK) a Redis tras un procesamiento exitoso, o el manejo de fallos para posibles reintentos.
-   **Responsabilidad Específica**: Gracias a `BaseWorker`, `QueryWorker` se puede centrar en las tareas específicas del `Query Service`:
    1.  **Inicialización del Servicio**: Preparar e instanciar `QueryService`.
    2.  **Manejo de la Acción**: Implementar el método `_handle_action(action: DomainAction)`, que define *qué hacer* con una `DomainAction` una vez que `BaseWorker` la ha consumido y deserializado.

#### Proceso de Inicialización Detallado (`__init__` y `async initialize`)

La inicialización del `QueryWorker` ocurre en dos fases:

1.  **`__init__(app_settings, async_redis_conn, consumer_id_suffix)`**:
    -   Recibe la configuración de la aplicación (`app_settings` o la carga con `get_settings()`) y una conexión Redis asíncrona (`async_redis_conn`), que es obligatoria.
    -   Llama al `super().__init__(...)` de `BaseWorker` para configurar la infraestructura básica del worker (nombre del consumidor, nombres de streams, etc.).
    -   Deja `self.query_service` como `None`, ya que su instanciación completa requiere operaciones asíncronas.

2.  **`async initialize()`**: Este método se llama después de la inicialización de `BaseWorker` y antes de que comience el bucle de consumo de mensajes.
    -   Llama a `await super().initialize()` para asegurar que `BaseWorker` haya completado su propia configuración asíncrona (ej. asegurar la existencia del grupo de consumidores).
    -   **Creación de `service_redis_client`**: Se instancia un `BaseRedisClient` (de `common.clients`) utilizando la misma conexión `self.async_redis_conn`. Este cliente se pasa al `QueryService`.
        -   *Importancia*: Esto permite que `QueryService` (o los componentes que utiliza, como `EmbeddingClient`) pueda, a su vez, enviar *nuevas* `DomainAction` a otros servicios a través de Redis si fuera necesario, manteniendo un patrón de comunicación consistente.
    -   **Instanciación de `QueryService`**: Se crea la instancia de `self.query_service`, inyectándole `app_settings`, el `service_redis_client` y la conexión `self.async_redis_conn` (para uso directo si es necesario por el servicio o sus componentes).
    -   Se registra un mensaje informativo confirmando la inicialización y los detalles del stream y grupo que está escuchando.

#### Método `async _handle_action(action: DomainAction)`

Este es el método que `BaseWorker` invoca para cada `DomainAction` consumida:

1.  **Verificación**: Asegura que `self.query_service` haya sido inicializado.
2.  **Logging**: Registra detalles de la acción que se va a procesar.
3.  **Delegación al Servicio**: La lógica principal es `result = await self.query_service.process_action(action)`. Toda la complejidad del procesamiento de la acción se delega al `QueryService`.
4.  **Logging del Resultado**: Se registra si la acción produjo un resultado o si fue una operación de tipo "fire-and-forget".
5.  **Manejo de Errores y Re-lanzamiento**: Si `self.query_service.process_action()` lanza cualquier excepción:
    -   El `QueryWorker` la captura y la registra detalladamente (incluyendo `exc_info=True` para el stack trace).
    -   Crucialmente, **re-lanza la excepción**. `BaseWorker` está diseñado para capturar estas excepciones. Dependiendo de la configuración de `BaseWorker` y la naturaleza del error, `BaseWorker` puede decidir no acusar recibo (ACK) del mensaje (permitiendo que sea procesado de nuevo por otro consumidor o por el mismo tras un tiempo), moverlo a una cola de "letras muertas" (dead-letter queue), o simplemente registrar el fallo y continuar. Este patrón es fundamental para la resiliencia del sistema.

## 3. Conexión e Interacciones con Otros Módulos

-   **`services.QueryService`**: Es la dependencia más crítica. `QueryWorker` instancia y delega el procesamiento de cada `DomainAction` al `QueryService`.
-   **`config.settings`**: Utiliza `get_settings()` para obtener la configuración de la aplicación, incluyendo detalles de Redis (URL, nombres de streams, grupos de consumidores).
-   **`main.py` (Punto de Entrada de la Aplicación)**: Es responsable de crear, inicializar e iniciar una o más instancias del `QueryWorker`.
-   **`common` (Módulo Compartido)**:
    -   `common.workers.BaseWorker`: Clase base fundamental.
    -   `common.models.DomainAction`: Modelo para los mensajes consumidos.
    -   `common.clients.BaseRedisClient`: Utilizado para crear el cliente Redis que se pasa al `QueryService`.

## 4. Evaluación de la Implementación

La implementación del `QueryWorker` es **excelente** y ejemplifica un diseño de worker robusto, desacoplado y resiliente:

-   **Abstracción Limpia y Reutilización**: La herencia de `BaseWorker` es un acierto mayor, permitiendo que `QueryWorker` se enfoque exclusivamente en la lógica de aplicación específica del `Query Service` (inicializar su servicio y delegar acciones) sin duplicar la compleja lógica de interacción con Redis Streams.
-   **Resiliencia**: El sistema de manejo de errores, donde las excepciones del servicio se propagan al `BaseWorker` para que este gestione el ciclo de vida del mensaje (ACK/NACK), es clave para construir un sistema que pueda recuperarse de fallos transitorios o manejar errores persistentes de manera adecuada.
-   **Escalabilidad**: El uso de grupos de consumidores de Redis Streams, gestionado por `BaseWorker`, permite que múltiples instancias de `QueryWorker` se ejecuten en paralelo (incluso en diferentes contenedores o máquinas). Esto distribuye la carga de trabajo automáticamente, haciendo que el servicio sea horizontalmente escalable.
-   **Mantenibilidad**: La clara separación de responsabilidades simplifica el mantenimiento y la evolución tanto del worker específico del servicio como de la lógica común de `BaseWorker`.

No se observan inconsistencias o debilidades significativas en este módulo. Es un componente sólido que conecta de manera eficaz y fiable la lógica de negocio del `Query Service` con la infraestructura de mensajería asíncrona.
