# Análisis del Flujo Avanzado (ReAct) en Nooble4

Este documento analiza el flujo completo del modo avanzado (ReAct) desde la recepción del action domain en el agent executor hasta el procesamiento y retorno de la respuesta final, incluyendo el ciclo de herramientas.

## Descripción del Flujo

### 1. Recepción de Action Domain en Agent Executor

El flujo comienza cuando el Agent Execution Service recibe una solicitud de chat avanzado. Esta solicitud contiene un `AdvanceChatPayload` que incluye:
- Mensaje del usuario
- Configuración del modelo y del agente
- Definiciones de herramientas disponibles
- Parámetros de RAG (collection_ids, document_ids, etc.)
- Historial de conversación (opcional)

### 2. Procesamiento Inicial en AdvanceChatHandler

El `AdvanceChatHandler` en Agent Execution Service procesa la solicitud mediante estos pasos iniciales:
1. Recibe el payload de chat avanzado
2. Genera IDs de conversación y mensaje
3. Registra las herramientas disponibles en `ToolRegistry`
4. Inicializa el ciclo ReAct

### 3. Ciclo ReAct

El ciclo ReAct es el núcleo del flujo avanzado y consiste en:

#### 3.1 Preparación del Contexto
- Construye los mensajes iniciales (system prompt, historial, mensaje del usuario)
- Prepara las herramientas disponibles, incluyendo la `KnowledgeTool` para búsquedas RAG

#### 3.2 Llamada a Query Service
- Crea un `QueryAdvancePayload` con mensajes, configuración y herramientas
- Envía la acción "query.advance" al Query Service mediante `QueryClient.query_advance`
- El Query Service procesa la solicitud con `AdvanceHandler.process_advance_query`
- La respuesta puede contener texto y/o llamadas a herramientas (`tool_calls`)

#### 3.3 Ejecución de Herramientas
- Si hay `tool_calls`, Agent Execution Service las ejecuta una por una
- Para la herramienta "knowledge", se realiza una llamada adicional a Query Service con `query_rag`
- Los resultados de las herramientas se formatean y se añaden como mensajes de tipo "tool"
- El ciclo continúa con estos nuevos mensajes hasta obtener una respuesta final

#### 3.4 Finalización
- El ciclo termina cuando se recibe una respuesta sin llamadas a herramientas o se alcanza el límite de iteraciones
- Se guarda la conversación con metadatos como herramientas usadas y pasos de razonamiento
- Se devuelve un `AdvanceExecutionResponse`

### 4. Comunicación Agent Execution Service → Query Service

La comunicación durante el flujo avanzado implica múltiples interacciones:

#### 4.1 Solicitud Principal (query.advance)
1. El `QueryClient` crea un `DomainAction` con tipo "query.advance"
2. Envía la acción a través de Redis usando `send_action_pseudo_sync`
3. El `AdvanceHandler` en Query Service procesa la solicitud
4. Utiliza Groq para generar una respuesta o llamadas a herramientas

#### 4.2 Solicitudes RAG (query.rag)
1. Cuando se ejecuta la herramienta "knowledge", se crea otra acción de tipo "query.rag"
2. Esta acción es procesada por el `RAGHandler` en Query Service
3. Se obtiene el embedding de la consulta y se realiza una búsqueda vectorial
4. Los resultados se devuelven como `RAGChunk`

### 5. Procesamiento en Query Service

#### 5.1 AdvanceHandler
- Recibe solicitudes de tipo "query.advance"
- Prepara la solicitud para Groq con messages, tools y tool_choice
- Llama a la API de Groq para obtener una respuesta o tool_calls
- Maneja errores y timeouts
- Devuelve un `QueryAdvanceResponseData`

#### 5.2 RAGHandler
- Recibe solicitudes de tipo "query.rag" (desde la herramienta "knowledge")
- Obtiene embeddings para la consulta a través del Embedding Service
- Realiza búsquedas en el vector store mediante `VectorClient`
- Formatea los resultados como `RAGChunk`
- Devuelve un `QueryRAGResponseData`

### 6. Retorno a Agent Execution Service

- Después de completar el ciclo ReAct, se genera una respuesta final
- Se incluyen metadatos como pasos de razonamiento y herramientas utilizadas
- Se guarda la conversación mediante `ConversationClient`
- Se devuelve un `AdvanceExecutionResponse` al cliente

## Incidencias e Inconsistencias Detectadas

### Gestión del Ciclo ReAct

1. **Límite de Iteraciones**: El número máximo de iteraciones en el ciclo ReAct es fijo y no configurable por el cliente. Si un problema requiere más iteraciones, el agente podría cortar prematuramente la resolución.

2. **Manejo de Herramientas Fallidas**: No hay un mecanismo claro para reintentar herramientas que han fallado. El agente simplemente continúa con el resultado de error, lo que podría llevar a respuestas sub-óptimas.

3. **Gestión del Contexto**: A medida que avanza el ciclo ReAct, los mensajes se acumulan y podrían exceder el máximo permitido por el modelo. No hay un mecanismo para resumir o truncar este historial.

### Problemas en la Comunicación de Herramientas

1. **Sincronización de Herramientas**: Las herramientas definidas en `AdvanceChatHandler` deben mantenerse sincronizadas con las definiciones en el modelo de agente. No hay validación para asegurar que las herramientas disponibles coincidan con las que el modelo conoce.

2. **Serialización de Argumentos**: Las llamadas a herramientas dependen de la correcta serialización de argumentos JSON entre Query Service y Agent Execution Service. Diferencias en los esquemas podrían causar errores difíciles de depurar.

3. **Falta de Versión en Tools**: No hay un sistema de versionado para las herramientas, lo que podría causar problemas cuando se actualizan las definiciones de herramientas pero no se actualizan en todos los servicios.

### Manejo de Errores y Timeouts

1. **Timeouts Desalineados**: Los timeouts para llamadas a Groq en `AdvanceHandler` se calculan basándose en `max_tokens // 100`, pero no está claro si este valor está alineado con los timeouts de `QueryClient` o si es adecuado para todos los modelos.

2. **Propagación de Errores**: Cuando falla una herramienta, el error se encapsula en la respuesta, pero no hay un mecanismo para que el modelo decida si reintentarla o cambiar de estrategia.

3. **Manejo de Interrupciones**: Si se interrumpe una solicitud durante el ciclo ReAct, no hay un mecanismo para limpiar recursos o guardar el estado parcial de la conversación.

### Inconsistencias en el Conocimiento (RAG)

1. **Parámetros de Embedding**: La herramienta `knowledge` utiliza `EmbeddingConfig` desde payload, pero no está claro si todos los parámetros (como dimensiones) se pasan correctamente al Embedding Service.

2. **Formateo de Resultados de RAG**: Los resultados de RAG se formatean de manera diferente en `_execute_tool` y en la respuesta de `RAGHandler`, lo que requiere una conversión adicional que podría ser fuente de errores.

3. **Límites Hardcodeados**: En `_execute_tool`, los resultados de RAG se limitan a los 3 primeros chunks sin importar la configuración de `top_k` en la solicitud original.

## Recomendaciones

1. **Configuración Dinámica**: Hacer que el límite de iteraciones del ciclo ReAct sea configurable según la complejidad de la tarea.

2. **Sistema de Reintentos**: Implementar un mecanismo para detectar y reintentar herramientas fallidas antes de continuar con el ciclo.

3. **Gestión de Contexto Inteligente**: Implementar un sistema para resumir o truncar el historial de mensajes cuando se acerca al límite del modelo.

4. **Validación de Herramientas**: Validar que las herramientas registradas coincidan con las definiciones en el modelo de agente.

5. **Versionado de Herramientas**: Implementar un sistema de versionado para las definiciones de herramientas.

6. **Alineación de Timeouts**: Establecer un sistema coherente para calcular timeouts basados en la complejidad de la tarea y el modelo utilizado.

7. **Interrupción Segura**: Implementar un mecanismo para manejar interrupciones durante el ciclo ReAct y guardar el estado parcial.

8. **Consistencia en Formateo RAG**: Unificar el formateo de resultados RAG entre los diferentes componentes del sistema.

9. **Configuración de Límites**: Hacer que los límites hardcodeados (como el número de chunks mostrados) sean configurables.