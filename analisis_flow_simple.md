# Análisis del Flujo Simple en Nooble4

Este documento analiza el flujo completo desde la recepción del action domain hasta el agent executor, el procesamiento interno, la comunicación con query service y el flujo de retorno.

## Descripción del Flujo

### 1. Recepción de Action Domain en Agent Executor

  El flujo comienza cuando el Agent Execution Service recibe una solicitud de chat simple. Esta solicitud contiene un `ExecutionSimpleChatPayload` que incluye:
- Mensaje del usuario
- Configuración del modelo de chat (modelo, temperatura, tokens máximos, etc.)
- Parámetros de RAG (IDs de colección, IDs de documento, etc.)
- Historial de conversación (opcional)

### 2. Procesamiento en SimpleChatHandler

El `SimpleChatHandler` en el Agent Execution Service procesa la solicitud mediante estos pasos:
1. Recibe un `ExecutionSimpleChatPayload`
2. Genera IDs de conversación y mensaje
3. Transforma el payload a un `SimpleChatPayload` compatible con Query Service
4. Envía la solicitud al Query Service mediante `QueryClient.query_simple`
5. Recibe y procesa la respuesta
6. Guarda la conversación mediante `ConversationClient`
7. Devuelve un `SimpleChatResponse`

### 3. Comunicación Agent Execution Service → Query Service

La comunicación se realiza a través del `QueryClient` que:
1. Crea un `DomainAction` con tipo "query.simple"
2. Envía la acción al Query Service a través de Redis usando `send_action_pseudo_sync`
3. Espera la respuesta (con timeout configurable)
4. Maneja errores y timeouts
5. Retorna los datos de respuesta

### 4. Procesamiento en Query Service

El Query Service recibe la acción y:
1. El worker de Query Service enruta la acción al `SimpleHandler`
2. `SimpleHandler.process_simple_query` obtiene el embedding del mensaje del usuario
3. Busca resultados relevantes en el vector store usando `VectorClient`
4. Construye un prompt que incluye el contexto de RAG
5. Llama al modelo de lenguaje (Groq) con el prompt completo
6. Procesa la respuesta y extrae las fuentes usadas
7. Construye y devuelve un `SimpleChatResponse`

### 5. Retorno a Agent Execution Service

1. Agent Execution Service recibe la respuesta del Query Service
2. Actualiza el ID de conversación con el propio
3. Guarda la conversación (de forma asíncrona)
4. Devuelve la respuesta final al cliente

## Incidencias e Inconsistencias Detectadas

### Inconsistencias en el Flujo de Comunicación

1. **Generación de IDs de Conversación**: Tanto el Agent Execution Service como Query Service generan sus propios IDs de conversación. El Agent Execution Service sobrescribe el ID generado por Query Service, pero esto podría generar problemas de trazabilidad si se necesita correlacionar logs entre ambos servicios.

2. **Gestión de Timeouts**: En `QueryClient` se utiliza un timeout configurable, pero no está claro si este valor está alineado con los timeouts internos de `VectorClient` y `GroqClient` en Query Service. Un desajuste aquí podría resultar en timeouts prematuros o esperas innecesariamente largas.

3. **Error Handling**: Cuando ocurre un error en Query Service, la información detallada del error podría perderse en la traducción entre servicios. Aunque se está utilizando `ExternalServiceError`, no hay un mapeo claro de todos los tipos de errores que pueden ocurrir.

### Posibles Problemas en el Procesamiento de RAG

1. **Embedding Dimensions**: El parámetro `embedding_dimensions` se pasa de Agent Execution Service a Query Service, pero en el código de `SimpleHandler._get_query_embedding()` no está claro si este parámetro se está utilizando efectivamente cuando se llama al Embedding Service.

2. **Filtrado por document_ids**: Aunque el cliente acepta `document_ids` para filtrar resultados específicos, la implementación de filtrado en `VectorClient.search()` usa un formato de filtros que podría no ser compatible con todas las bases de datos vectoriales.

3. **Construcción de Contexto**: En `SimpleHandler._build_context()`, se limita a 5 el número máximo de resultados incluidos en el contexto, pero este valor es fijo y no configurable por el cliente, lo que podría ser una limitación.

### Otros Problemas Potenciales

1. **Modelo de Configuración de Embedding**: El modelo de embedding se especifica en el payload, pero no está claro si el Embedding Service soporta todos los modelos enumerados en `EmbeddingModel`. Podría haber una discrepancia entre los modelos enumerados y los implementados.

2. **Manejo de Historiales Largos**: El validador de `conversation_history` limita la cantidad a 50 mensajes, pero no hay un mecanismo claro para manejar historiales más largos (por ejemplo, resumirlos o truncarlos de forma inteligente).

3. **Gestión de Recursos Redis**: La comunicación a través de Redis utiliza un modelo pseudo-síncrono que podría acumular mensajes sin procesar si ocurren errores o si hay una alta carga de trabajo.

## Recomendaciones

1. Unificar la generación de IDs entre servicios para mejorar la trazabilidad.
2. Alinear los tiempos de timeout entre todos los componentes del sistema.
3. Implementar un mapeo más detallado de errores entre servicios.
4. Hacer que el número máximo de resultados RAG incluidos en el contexto sea configurable.
5. Implementar un mecanismo para manejar historiales de conversación largos.
6. Revisar la compatibilidad de modelos entre los servicios.
7. Implementar monitores para la cola de Redis para detectar acumulación de mensajes.