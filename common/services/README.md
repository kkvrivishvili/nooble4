# Módulo de Servicios Comunes (`common.services`)

Este módulo es un pilar fundamental de la **Arquitectura v4.0** de Nooble4.

## Propósito

Define la capa de **Lógica de Negocio** de los microservicios. Su principal responsabilidad es orquestar las operaciones y la lógica específica del dominio del servicio.

## Componentes Clave

### 1. `base_service.py`

- **`BaseService` (Clase Abstracta)**:
    - **Propósito**: Es la clase base abstracta de la cual **deben** heredar todas las clases de la Capa de Servicio en los microservicios.
    - **Contrato**: Establece un contrato formal para la Capa de Servicio. Aunque no impone métodos abstractos específicos (ya que la lógica de cada servicio es única), la herencia asegura un punto de anclaje común y promueve la consistencia arquitectónica.
    - **Características**:
        - Es agnóstica a la infraestructura de workers y colas (Redis).
        - Recibe dependencias comunes como `app_settings` y opcionalmente un `redis_client` (para interactuar con otros servicios si es necesario).
        - Utiliza **Handlers Especializados** (definidos en `common.handlers`) para delegar tareas específicas y mantener su propia lógica cohesiva y centrada en la orquestación.

## Interacción con Otros Módulos

- **Workers (`common.workers.BaseWorker`)**: El `BaseWorker` (capa de infraestructura) recibe un `DomainAction` de Redis y delega su procesamiento a una instancia de una clase derivada de `BaseService` a través del método `_handle_action` del worker.
- **Handlers (`common.handlers`)**: La `BaseService` utiliza varios handlers especializados para tareas como la gestión del contexto (`BaseContextHandler`), el manejo de callbacks (`BaseCallbackHandler`), o cualquier otra lógica específica que pueda ser encapsulada.
- **Models (`common.models`)**: Utiliza `DomainAction` y `DomainActionResponse` para recibir datos de entrada y formular respuestas.
- **Clients (`common.clients.BaseRedisClient`)**: Puede utilizar el `BaseRedisClient` para enviar `DomainAction` a otros servicios si necesita coordinar operaciones distribuidas.

Al estandarizar la Capa de Servicio a través de `BaseService`, se promueve la modularidad, la testeabilidad y la mantenibilidad de la lógica de negocio en todo el ecosistema de Nooble4.
