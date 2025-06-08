# Análisis del Ciclo de Vida de Conversaciones

## Introducción

Este documento analiza el ciclo de vida actual de las conversaciones en el sistema nooble4, identificando cómo se gestiona el estado entre mensajes y proponiendo mejoras para optimizar el flujo de comunicación entre servicios.

## Ciclo de Vida Actual de una Conversación

### 1. Inicio de Conversación

Cuando un usuario inicia una conversación:

1. El frontend establece conexión WebSocket con un `session_id` único
2. Se envían headers HTTP iniciales (X-Tenant-ID, X-Agent-ID, X-Session-ID, etc.)
3. El Agent Orchestrator Service recibe y valida estos headers
4. Se crea un `task_id` único para la solicitud
5. Se crea un contexto de ejecución inicial (`ExecutionContext`)

```
Frontend --(WebSocket/headers)--> Agent Orchestrator
```

### 2. Procesamiento del Mensaje Inicial

Para cada mensaje del usuario:

1. Se crea un nuevo `DomainAction` de tipo `AgentExecutionAction`
2. Se consulta Agent Management Service para obtener configuración del agente
3. Se enriquece el contexto con esta información
4. Se envía la acción a la cola específica por tier

```
Agent Orchestrator --(AgentExecutionAction)--> Redis Queue (execution:agent_run:{tier}:{task_id})
```

### 3. Ejecución del Agente

El Agent Execution Service:

1. Recibe la acción de la cola
2. Reconstruye el contexto de ejecución desde la acción
3. Si es necesario, consulta nuevamente información del agente
4. Ejecuta el agente LLM según la configuración
5. Si requiere RAG, crea nuevas acciones para Embedding y Query

```
Agent Execution --(EmbeddingAction)--> Redis Queue (embedding:generate:{tier}:{task_id})
Agent Execution --(QueryAction)--> Redis Queue (query:search:{tier}:{task_id})
```

### 4. Procesamiento de Servicios Auxiliares

Los servicios de Embedding y Query:

1. Procesan sus respectivas acciones independientemente
2. No tienen referencia directa al estado de la conversación completa
3. Utilizan valores hardcodeados o configuraciones por defecto cuando falta información
4. Envían callbacks con los resultados

```
Embedding Service --(EmbeddingResultAction)--> Redis Queue (embedding:callback:{task_id})
Query Service --(QueryResultAction)--> Redis Queue (query:callback:{task_id})
```

### 5. Finalización del Procesamiento

El Agent Execution Service:

1. Recibe los callbacks
2. Completa el procesamiento del agente
3. Envía la respuesta final como callback

```
Agent Execution --(ExecutionCallbackAction)--> Redis Queue (execution:callback:{task_id})
```

### 6. Respuesta al Usuario

El Agent Orchestrator:

1. Recibe el callback
2. Envía la respuesta al usuario a través del WebSocket
3. No mantiene explícitamente el contexto para futuros mensajes

```
Agent Orchestrator --(WebSocket)--> Frontend
```

## Problema Identificado: Estado No Persistente

**El problema principal es que el sistema no mantiene un estado persistente de la conversación:**

1. Cada mensaje inicia un nuevo ciclo completo de consultas y enriquecimiento
2. No hay un mecanismo de caché que asocie una conversación en curso con su contexto
3. Las configuraciones y preferencias se consultan repetidamente
4. Las colas de Redis no se limpian automáticamente cuando finaliza el procesamiento

## Impacto del Problema

Este enfoque genera:

1. **Sobrecarga de consultas**: Múltiples llamadas innecesarias a servicios como Agent Management
2. **Inconsistencias potenciales**: La configuración podría cambiar entre mensajes de la misma conversación
3. **Uso ineficiente de recursos**: Se reconstruye el mismo contexto repetidamente
4. **Acumulación de colas Redis**: Las colas utilizadas para un mensaje pueden no limpiarse adecuadamente

## Próximos Pasos

Los documentos adicionales explorarán:

1. Propuesta de sistema de caché para contextos de conversación
2. Mejora de la propagación de configuraciones entre servicios
3. Optimización del ciclo de vida de las colas Redis
