# Módulo de Servicios (Query Service)

## 1. Propósito General

El módulo `services` actúa como la **fachada** o el **punto de entrada lógico** para la lógica de negocio del `Query Service`. Su responsabilidad principal es recibir solicitudes de alto nivel, en forma de `DomainAction`, y delegar el trabajo al `handler` apropiado que se especializa en esa tarea específica.

Al hacer esto, desacopla al `worker` (que se ocupa de la comunicación con Redis) de la implementación detallada de la lógica de negocio (que reside en los `handlers`).

## 2. Archivos y Clases Implementadas

Este módulo contiene un archivo clave:

- **`query_service.py`**: Define la clase `QueryService`.

### `QueryService`

- **Funcionalidad**: Esta clase es el orquestador principal. Se inicializa con instancias de todos los `handlers` necesarios (`RAGHandler`, `SearchHandler`). Su método principal, `handle_action`, funciona como un **despachador (dispatcher)**.

- **Flujo de Trabajo del Despachador**:
    1.  Recibe un objeto `DomainAction` del `worker`.
    2.  Inspecciona el campo `action.action_type` (ej. `"query.generate"` o `"query.search"`).
    3.  Basado en este tipo, invoca el método correspondiente en el handler apropiado.
        - Si es `"query.generate"`, llama a `rag_handler.process_rag_query()`.
        - Si es `"query.search"`, llama a `search_handler.search_documents()`.
    4.  Captura la respuesta del handler.
    5.  Construye y devuelve un `DomainActionResponse`, que contiene el resultado de la operación o un error si algo falló.

## 3. Patrones de Diseño

- **Patrón Fachada (Facade)**: `QueryService` simplifica la interacción con un subsistema complejo (los handlers). El `worker` no necesita saber qué handler existe ni cuál invocar; simplemente le pasa la acción al `QueryService`.
- **Patrón Estrategia (Strategy)**: De manera implícita, se utiliza una forma de este patrón. Los `handlers` representan diferentes estrategias para procesar una consulta. El `QueryService` selecciona la estrategia correcta en tiempo de ejecución basándose en el `action_type`.
- **Inyección de Dependencias**: El `QueryService` recibe los handlers ya inicializados, lo que facilita las pruebas y la modularidad.

## 4. Conexión con Otros Módulos

- **`workers`**: El `QueryWorker` tiene una instancia de `QueryService` y le pasa las `DomainAction` que consume de Redis.
- **`handlers`**: `QueryService` depende directamente de los handlers (`RAGHandler`, `SearchHandler`) para ejecutar la lógica de negocio.
- **`models`**: Utiliza los modelos de `payloads.py` para validar y estructurar los datos dentro de las `DomainAction` y `DomainActionResponse`.
- **`common`**: Depende crucialmente de `common.models` para las definiciones de `DomainAction` y `DomainActionResponse`.

## 5. Opinión de la Implementación

La implementación de este módulo es **excelente** y demuestra una arquitectura de software muy sólida y bien pensada.

- **Claridad y Cohesión**: La clase `QueryService` tiene una única y clara responsabilidad: despachar acciones. No se mezcla con la lógica de negocio de los handlers.
- **Extensibilidad**: El diseño es muy extensible. Si en el futuro se necesitara añadir una nueva funcionalidad (ej. `"query.summarize"`), solo se requeriría:
    1.  Crear un nuevo `SummarizeHandler`.
    2.  Añadir una nueva condición en el método `handle_action` del `QueryService` para delegar a este nuevo handler.
    El resto del sistema no se vería afectado.

No se observan inconsistencias ni debilidades en este módulo. Es un ejemplo perfecto de cómo estructurar la capa de servicio en una aplicación de microservicios.
