# Módulo de Workers (Query Service)

## 1. Propósito General

El módulo `workers` es el **punto de entrada de ejecución** del `Query Service` en un entorno de producción. Su función es conectar el servicio a la infraestructura de mensajería (Redis Streams) y consumir las tareas (en forma de `DomainAction`) que deben ser procesadas.

El worker actúa como un bucle continuo que escucha nuevos mensajes en una cola específica, los recoge y los pasa a la capa de servicio (`QueryService`) para su procesamiento real. Es, en esencia, el motor que impulsa el microservicio.

## 2. Archivos y Clases Implementadas

Este módulo contiene un archivo principal:

- **`query_worker.py`**: Define la clase `QueryWorker`.

### `QueryWorker`

- **Funcionalidad**: Esta clase es la responsable de la comunicación con Redis Streams. Se encarga de:
    1.  Conectarse a Redis.
    2.  Crear o unirse a un **grupo de consumidores** en un stream específico (definido en la configuración).
    3.  Escuchar y recibir mensajes de ese stream de manera continua.
    4.  Deserializar cada mensaje en un objeto `DomainAction`.
    5.  Delegar el `DomainAction` al `QueryService` para su procesamiento.
    6.  Manejar el ciclo de vida del mensaje, incluyendo el acuse de recibo (ACK) a Redis una vez que la tarea se completa con éxito.

## 3. Patrones y Conexión con `common`

El `QueryWorker` se apoya fuertemente en las abstracciones del módulo `common` para estandarizar su comportamiento:

- **`common.workers.BaseWorker`**: `QueryWorker` hereda de esta clase base. `BaseWorker` encapsula toda la lógica compleja y repetitiva de la interacción con Redis Streams:
    - Gestión de la conexión.
    - Creación del grupo de consumidores.
    - Bucle de lectura de mensajes (`read_from_stream`).
    - Manejo de errores y reintentos a nivel de infraestructura.
    - Acknowledgment (ACK) de mensajes.

Al heredar de `BaseWorker`, `QueryWorker` solo necesita implementar el método `_handle_action`, que define *qué hacer* con un mensaje una vez recibido. El *cómo recibirlo* ya está resuelto por la clase base.

## 4. Conexión con Otros Módulos

- **`services`**: Es la conexión más importante. El `QueryWorker` tiene una instancia del `QueryService` y le pasa cada `DomainAction` que consume. Actúa como el cliente directo de la capa de servicio.
- **`config`**: Utiliza `get_settings()` para obtener toda la configuración necesaria, como la URL de Redis, los nombres de los streams y los grupos de consumidores.
- **`main.py`**: El punto de entrada principal de la aplicación (`main.py`) es responsable de crear e iniciar una o más instancias del `QueryWorker`.

## 5. Opinión de la Implementación

La implementación del worker es **excelente** y sigue un patrón de diseño muy robusto y desacoplado.

- **Abstracción Limpia**: La herencia de `BaseWorker` es un gran acierto. Permite que `QueryWorker` se centre exclusivamente en su lógica de aplicación (delegar al servicio) sin preocuparse por los detalles de bajo nivel de Redis Streams.
- **Resiliencia**: Al delegar el manejo de errores de infraestructura a la clase base, se asegura un comportamiento resiliente. Por ejemplo, si el procesamiento de una acción falla, `BaseWorker` puede evitar hacer el ACK, permitiendo que el mensaje sea procesado de nuevo más tarde.
- **Escalabilidad**: El uso de grupos de consumidores de Redis Streams permite que múltiples instancias de `QueryWorker` se ejecuten en paralelo (incluso en diferentes máquinas), distribuyendo la carga de trabajo de manera automática. Esto hace que el servicio sea horizontalmente escalable.

No se observan inconsistencias ni debilidades en este módulo. Es un componente sólido que conecta eficazmente la lógica de negocio con la infraestructura de mensajería.
