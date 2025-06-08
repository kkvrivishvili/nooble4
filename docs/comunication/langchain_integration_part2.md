# Integración de LangChain en Agent Execution Service (Parte 2)

## Tipos de Agentes Implementados

### 1. Agente Conversacional

El agente más simple, enfocado en diálogo:

```python
async def _execute_conversational_agent(
    self,
    agent_config: Dict[str, Any],
    message: str,
    conversation_history: List[Dict[str, Any]],
    user_info: Dict[str, Any],
    execution_context: ExecutionContext,
    **params
) -> Dict[str, Any]:
    # Obtener system prompt de la configuración
    system_prompt = agent_config.get("system_prompt", "Eres un asistente útil.")
    
    # Construir cadena LangChain (implementación real)
    llm = self._create_llm_from_config(agent_config, execution_context)
    memory = self._create_memory(conversation_history)
    
    # Crear agente con LangChain
    agent_chain = ConversationalChain.from_llm(
        llm=llm,
        memory=memory,
        system_message=system_prompt,
        verbose=True
    )
    
    # Ejecutar agente
    result = await agent_chain.arun(
        input=message,
        user_info=user_info
    )
    
    # Estructurar respuesta
    return {
        "response": result,
        "tool_calls": [],  # Agente conversacional simple no usa herramientas
        "sources": [],
        "iterations_used": 1,
        "model_used": agent_config.get("model"),
        "total_tokens": self._estimate_tokens(message, result)
    }
```

### 2. Agente RAG (Retrieval Augmented Generation)

Integra búsqueda de documentos con generación de respuestas:

```python
async def _execute_rag_agent(...):
    # 1. Generar embedding de la consulta
    embedding_result = await self.embedding_client.generate_embeddings(
        texts=[message],
        tenant_id=execution_context.tenant_id,
        session_id=execution_context.context_id
    )
    
    # 2. Buscar documentos relevantes
    query_result = await self.query_client.generate_query(
        tenant_id=execution_context.tenant_id,
        query=message,
        query_embedding=embedding_result.embeddings[0],
        collection_id=execution_context.collections[0]
    )
    
    # 3. Construir contexto RAG
    rag_context = self._build_rag_context(
        query_result.documents,
        agent_config
    )
    
    # 4. Crear y ejecutar agente LangChain con contexto RAG
    llm = self._create_llm_from_config(agent_config, execution_context)
    rag_chain = self._create_rag_chain(llm, rag_context, agent_config)
    
    # 5. Ejecutar cadena RAG
    result = await rag_chain.arun(
        query=message,
        context=rag_context
    )
    
    return {
        "response": result,
        "sources": query_result.documents,
        # Otros campos...
    }
```

### 3. Agente Workflow

Implementa flujos de trabajo multi-paso con herramientas:

```python
async def _execute_workflow_agent(...):
    # 1. Definir herramientas disponibles basadas en configuración
    tools = self._create_tools_from_config(agent_config, execution_context)
    
    # 2. Crear agente LangChain con herramientas
    llm = self._create_llm_from_config(agent_config, execution_context)
    agent = self._create_agent_with_tools(llm, tools, agent_config)
    
    # 3. Configurar seguimiento de iteraciones
    max_iterations = params.get("max_iterations", 5)
    iterations_tracker = self._create_iterations_tracker(max_iterations)
    
    # 4. Ejecutar agente con seguimiento
    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        max_iterations=max_iterations,
        verbose=True,
        callbacks=[iterations_tracker]
    )
    
    # 5. Ejecutar workflow
    result = await agent_executor.arun(
        input=message,
        chat_history=conversation_history
    )
    
    return {
        "response": result,
        "tool_calls": iterations_tracker.tool_calls,
        "iterations_used": iterations_tracker.iterations,
        # Otros campos...
    }
```
