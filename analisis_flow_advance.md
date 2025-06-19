# Análisis del Flujo Avanzado: Chat + RAG + Tools (ReAct)

## Resumen del Flujo

El flujo avanzado implementa un proceso de chat con capacidades de ReAct (Reasoning and Acting), que incluye tanto RAG como el uso de herramientas. La comunicación fluye desde el Agent Execution Service al Query Service con múltiples iteraciones para el bucle ReAct.

## Componentes del Flujo

### 1. Inicio en Agent Execution Service (`advance_chat_handler.py`)

- **Payload de Entrada**: No se ha confirmado aún, posiblemente `ExecutionAdvanceChatPayload`
- **Procesamiento Inicial**:
  - Registra herramientas disponibles (incluyendo `KnowledgeTool`)
  - Configura el contexto de conversación
  - Inicia el bucle ReAct

### 2. Bucle ReAct

- **Iteración del Bucle**:
  - Envía mensajes y definiciones de herramientas a Query Service
  - Recibe respuesta del LLM con posibles llamadas a herramientas
  - Ejecuta las llamadas a herramientas (incluyendo RAG)
  - Añade resultados de las herramientas a la conversación
  - Repite hasta obtener una respuesta final o alcanzar un límite de iteraciones

### 3. Herramienta de Conocimiento (`knowledge_tool.py`)

- **Función Principal**: Realizar búsquedas RAG para consultas específicas
- **Comunicación**:
  - Utiliza `query_client.query_rag()` para comunicarse con el Query Service
  - Formatea y procesa resultados para incluirlos en el contexto de conversación

### 4. Comunicación con Query Service (`query_client.py`)

- **Métodos de Comunicación**:
  - `query_advance()`: Para el flujo principal de ReAct
  - `query_rag()`: Para búsquedas RAG desde el KnowledgeTool

- **Mecanismo**:
  - Construye objetos `DomainAction` con tipos "query.advance" o "query.rag"
  - Envía a través de Redis y espera respuestas sincrónicas

### 5. Procesamiento en Query Service

- **Handlers Específicos**:
  - `AdvanceHandler`: Procesa chat avanzado con herramientas
  - `RAGHandler`: Procesa búsquedas RAG específicas

- **Integración con Servicios Externos**:
  - Comunicación con LLMClient para generaciones de texto
  - Comunicación con EmbeddingClient para búsquedas vectoriales

### 6. Finalización y Respuesta

- **Respuesta Final**: `AdvanceExecutionResponse`
  - Contiene: mensaje final, pasos de razonamiento, herramientas utilizadas

- **Persistencia**:
  - Guarda la conversación completa con todos los pasos intermedios

## Modelos Utilizados (Pendiente de verificación completa)

### Agent Execution Service
- Posiblemente `ExecutionAdvanceChatPayload` (no confirmado)
- `ChatMessage` - Para construir la conversación
- `AdvanceExecutionResponse` - Para la respuesta final
- `ToolDefinition` - Para definir herramientas disponibles

### Query Service
- `QueryAdvancePayload` - Para procesar el avance en modo ReAct
- `QueryAdvanceResponseData` - Para devolver resultados del LLM

## Estado Actual del Análisis

Este documento está en construcción. Se irá actualizando a medida que se analice en detalle el código del flujo avanzado con ReAct, particularmente los siguientes aspectos:

- Estructura completa del bucle ReAct en `advance_chat_handler.py`
- Implementación precisa de `QueryAdvancePayload` y su uso
- Detalles de la integración de herramientas con el LLM
- Mapeo completo de todos los modelos Pydantic utilizados
- Verificación de compatibilidad con APIs externas (Groq, OpenAI)
