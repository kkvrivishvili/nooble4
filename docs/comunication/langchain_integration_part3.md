# Integración de LangChain en Agent Execution Service (Parte 3)

## Integración con LLMs

El sistema soporta múltiples proveedores de LLMs a través de una capa de abstracción:

```python
def _create_llm_from_config(self, agent_config, context):
    # Obtener proveedor y modelo
    provider = agent_config.get("provider", context.llm_config.get("provider", "openai"))
    model = agent_config.get("model", context.llm_config.get("model", "gpt-3.5-turbo"))
    
    # Parámetros para el LLM
    params = {
        "temperature": agent_config.get("temperature", 0.7),
        "top_p": agent_config.get("top_p", 1.0),
        "max_tokens": agent_config.get("max_tokens", 2048)
    }
    
    # Crear LLM según proveedor
    if provider == "openai":
        return ChatOpenAI(model=model, **params)
    elif provider == "anthropic":
        return ChatAnthropic(model=model, **params)
    elif provider == "groq":
        return ChatGroq(model=model, **params)
    elif provider == "cohere":
        return ChatCohere(model=model, **params)
    else:
        raise ValueError(f"Proveedor no soportado: {provider}")
```

## Gestión de Memoria y Contexto

El sistema utiliza diferentes tipos de memoria para mantener el contexto de la conversación:

```python
def _create_memory(self, conversation_history):
    messages = []
    
    for message in conversation_history:
        role = message.get("role", "user")
        content = message.get("content", "")
        
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))
    
    return ConversationBufferMemory(
        chat_memory=ChatMessageHistory(messages),
        return_messages=True
    )
```

## Herramientas Disponibles para Agentes

Los agentes pueden utilizar varias herramientas:

```python
def _create_tools_from_config(self, agent_config, context):
    tools_config = agent_config.get("tools", [])
    tools = []
    
    for tool_config in tools_config:
        tool_type = tool_config.get("type")
        
        if tool_type == "search":
            tools.append(
                VectorStoreTool(
                    name="search_documents",
                    description="Buscar en documentos relevantes",
                    vector_store=self._get_vector_store(context)
                )
            )
        elif tool_type == "calculator":
            tools.append(Calculator())
        elif tool_type == "web_search":
            tools.append(
                WebSearchTool(
                    api_key=context.metadata.get("search_api_key")
                )
            )
    
    return tools
```

## Flujo de Callback

El sistema utiliza callbacks para comunicar resultados asíncronos:

```python
# Estructura de callback retornada al Agent Execution Service
callback_data = {
    "task_id": execution_context.task_id,
    "status": "success",
    "result": {
        "response": result,
        "tool_calls": tool_calls,
        "sources": sources,
        "iterations_used": iterations_used,
        "model_used": model_used,
        "total_tokens": total_tokens,
        "metadata": execution_metadata
    }
}

# Enviar a cola de callbacks
await self.action_processor.enqueue_action(
    queue_name=f"execution.{execution_context.tenant_id}.callbacks",
    action=callback_data
)
```
