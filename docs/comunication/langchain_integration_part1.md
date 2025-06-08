# Integración de LangChain en Agent Execution Service (Parte 1)

## Introducción

Este documento describe cómo el Agent Execution Service integra el framework LangChain para la ejecución de agentes inteligentes en nooble4, detallando los componentes clave, flujos de trabajo y patrones de integración implementados.

## Arquitectura de la Integración

### Componentes Principales

1. **AgentExecutor**: Clase principal que orquesta la ejecución de los agentes.
2. **LangChainIntegrator**: Encapsula la lógica de integración con LangChain y coordina la creación y ejecución de agentes.
3. **ExecutionContext**: Modelo que mantiene el contexto completo para la ejecución del agente.
4. **Clientes de Servicio**: Conectores a servicios como Embedding y Query para funcionalidades externas.

```
AgentExecutor
    |
    +--> LangChainIntegrator
         |
         +--> Agentes LangChain
         |    |
         |    +--> Agent Conversacional
         |    +--> Agent RAG
         |    +--> Agent Workflow
         |
         +--> EmbeddingClient
         +--> QueryClient
```

## Flujo de Ejecución

### 1. Inicialización

```python
# En agent_executor.py
def __init__(self, context_handler: ExecutionContextHandler, redis_client=None):
    self.context_handler = context_handler
    self.redis = redis_client
    
    # Inicializar integrador de LangChain
    self.langchain_integrator = LangChainIntegrator(redis_client)
```

### 2. Preparación del Contexto de Ejecución

El `AgentExecutor` recibe un `ExecutionContext` que contiene toda la información necesaria para la ejecución:

```python
async def execute_agent(
    self,
    context: ExecutionContext,  # Contexto completo de ejecución
    agent_config: Dict[str, Any],  # Configuración específica del agente
    message: str,  # Mensaje del usuario 
    message_type: str = "text",
    conversation_history: List[Dict[str, Any]] = None,
    user_info: Dict[str, Any] = None,
    max_iterations: Optional[int] = None
) -> ExecutionResult:
```

### 3. Selección de Tipo de Agente

El `LangChainIntegrator` determina el tipo de agente a ejecutar basado en la configuración:

```python
# En langchain_integrator.py
async def execute_agent(...):
    # Determinar tipo de agente
    agent_type = agent_config.get("type", "conversational")
    
    if agent_type == "conversational":
        return await self._execute_conversational_agent(...)
    elif agent_type == "rag":
        return await self._execute_rag_agent(...)
    elif agent_type == "workflow":
        return await self._execute_workflow_agent(...)
```
