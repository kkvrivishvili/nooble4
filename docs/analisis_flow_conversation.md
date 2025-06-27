# Análisis del Flujo entre Agent Execution Service y Conversation Service

## 1. Modelo de Comunicación Actual

El sistema actual implementa un modelo de comunicación entre `agent_execution_service` y `conversation_service` con las siguientes características:

### 1.1 Flujo de Guardado de Conversaciones (Implementado)

- **Patrón de comunicación**: Fire-and-forget mediante DomainAction asíncrona
- **Dirección**: agent_execution_service → conversation_service
- **Tipo de acción**: `conversation.message.create`

El flujo implementado funciona de la siguiente manera:

1. El `agent_execution_service` procesa una solicitud de chat:
   - En `SimpleChatHandler.handle_simple_chat()` o `AdvanceChatHandler.handle_advance_chat()`
   - Genera un `conversation_id` y `message_id` únicos (UUID)
   - Extrae el mensaje del usuario y la respuesta del agente

2. Al finalizar el procesamiento, se envía la conversación al `conversation_service`:
   ```python
   await self.conversation_client.save_conversation(
       conversation_id=conversation_id,
       message_id=message_id,
       user_message=user_message,
       agent_message=response.message.content,
       tenant_id=tenant_id,
       session_id=session_id,
       task_id=task_id,
       metadata={...}  # Metadatos específicos del tipo de conversación
   )
   ```

3. El `ConversationClient` envía la acción sin esperar respuesta:
   ```python
   # Fire-and-forget: enviamos sin esperar respuesta
   await self.redis_client.send_action_async(action)
   ```

4. El `ConversationService` recibe y procesa la acción:
   - Busca o crea una conversación basada en el `session_id`
   - Guarda el mensaje en Redis con información estructurada
   - No requiere respuesta al ser fire-and-forget

### 1.2 Flujo de Recuperación de Historial (No Implementado)

**ESTADO ACTUAL: No implementado**

No existe actualmente un mecanismo en `agent_execution_service` para:
1. Recuperar el historial de conversaciones desde `conversation_service` al inicio de una nueva interacción
2. Integrar mensajes previos en el contexto de la conversación actual

## 2. Implementación Propuesta para Recuperación de Historial

### 2.1 Modelo de Comunicación Sugerido

- **Patrón de comunicación**: Sincrónico mediante DomainAction
- **Dirección**: agent_execution_service → conversation_service
- **Tipo de acción**: `conversation.context.get`
- **Frecuencia**: Al inicio de cada interacción con el usuario

### 2.2 Flujo Propuesto

1. **Agent Execution Service**: Al recibir un nuevo mensaje del usuario:
   - Antes de procesar el mensaje, obtener el historial de conversación
   - Usar el `session_id` como identificador de la conversación
   - Llamar a `conversation_service` para obtener mensajes previos

2. **Conversation Service**: Proporcionar un endpoint para recuperar contexto:
   - Función ya existente: `get_context_for_query()`
   - Devolver mensajes previos, posiblemente truncados según limitaciones del modelo

3. **Integración en Agent Execution Service**:
   - Fusionar mensajes históricos con el nuevo mensaje del usuario
   - Mantener la coherencia del contexto de conversación

### 2.3 Código a Implementar (ConversationClient)

```python
async def get_conversation_context(
    self,
    tenant_id: str,
    session_id: str,
    model_name: str,
    task_id: uuid.UUID
) -> Optional[Dict[str, Any]]:
    """
    Obtiene el contexto de conversación desde Conversation Service.
    
    Args:
        tenant_id: ID del tenant
        session_id: ID de la sesión
        model_name: Nombre del modelo para optimizar contexto
        task_id: ID de la tarea
        
    Returns:
        Dict con contexto de conversación o None si hay error
    """
    payload = {
        "session_id": session_id,
        "model_name": model_name
    }

    action = DomainAction(
        action_id=uuid.uuid4(),
        action_type="conversation.context.get",
        timestamp=datetime.now(timezone.utc),
        tenant_id=tenant_id,
        session_id=session_id,
        task_id=task_id,
        origin_service=self.redis_client.service_name,
        data=payload
    )

    try:
        response = await self.redis_client.send_action_pseudo_sync(
            action, 
            timeout=5  # Timeout corto para no bloquear la interacción
        )
        
        if not response.success or response.data is None:
            self._logger.warning(
                f"No se pudo obtener contexto de conversación",
                extra={"session_id": session_id, "tenant_id": tenant_id}
            )
            return None
                
        return response.data
        
    except Exception as e:
        # Loguear error pero no fallar la operación principal
        self._logger.error(
            f"Error obteniendo contexto de conversación: {e}",
            extra={"session_id": session_id, "tenant_id": tenant_id}
        )
        return None
```

### 2.4 Modificación en Handlers (SimpleChatHandler)

```python
async def handle_simple_chat(
    self,
    payload: Dict[str, Any],
    tenant_id: str,
    session_id: str,
    task_id: uuid.UUID
) -> ChatResponse:
    """Ejecuta chat simple delegando al Query Service con contexto histórico."""
    start_time = time.time()
    
    try:
        # Parsear el ChatRequest
        chat_request = ChatRequest.model_validate(payload)
        
        # 1. NUEVO: Obtener contexto de conversación si existe
        context = await self.conversation_client.get_conversation_context(
            tenant_id=tenant_id,
            session_id=session_id,
            model_name=chat_request.model.value,
            task_id=task_id
        )
        
        # 2. NUEVO: Integrar mensajes históricos si hay contexto
        if context and "messages" in context:
            # Fusionar mensajes históricos con el mensaje actual
            historic_messages = [
                ChatMessage(role=msg["role"], content=msg["content"])
                for msg in context["messages"]
            ]
            
            # Mantener el primer mensaje system (instrucciones) y agregar histórico antes del último mensaje
            if chat_request.messages and len(chat_request.messages) > 1:
                system_message = chat_request.messages[0] if chat_request.messages[0].role == "system" else None
                user_message = chat_request.messages[-1]
                
                new_messages = []
                if system_message:
                    new_messages.append(system_message)
                
                new_messages.extend(historic_messages)
                new_messages.append(user_message)
                
                chat_request.messages = new_messages
                
                self.logger.info(
                    f"Contexto histórico integrado",
                    extra={
                        "session_id": session_id,
                        "messages_count": len(historic_messages)
                    }
                )

        # Resto del método igual...
```

## 3. Optimizaciones y Consideraciones

### 3.1 Cacheo Local en Agent Execution Service

Para mejorar el rendimiento, se podría implementar un cacheo local del contexto:

1. Al obtener el contexto de `conversation_service`, guardarlo en una caché local (Redis)
2. Al guardar nueva conversación en modo fire-and-forget, actualizar también la caché local
3. Usar un TTL apropiado para la caché (ej: 5-15 minutos)

### 3.2 Gestión de Contexto Extenso

Cuando el contexto histórico es muy extenso:

1. `conversation_service` ya implementa truncamiento en `get_context_for_query()` mediante `MemoryManager`
2. Se deben respetar los límites de tokens del modelo usado
3. Considerar estrategias de resumen para contextos muy largos

### 3.3 Manejo de Fallos

En caso de fallo al recuperar el contexto:

1. No bloquear la operación principal: seguir con el mensaje actual solamente
2. Implementar reintentos con backoff en caso de errores temporales
3. Monitorear fallos de comunicación para detectar problemas de conectividad

## 4. Conclusión y Estado Actual

La implementación actual tiene un flujo de guardado de conversaciones functional mediante DomainActions en modo fire-and-forget, que:

1. ✅ **Guarda mensajes**: El `agent_execution_service` envía conversaciones completas al `conversation_service`
2. ✅ **Estructura adecuada**: El `ConversationClient` encapsula la lógica de comunicación con `conversation_service`
3. ✅ **Manejo de errores**: Los errores en el guardado no afectan la operación principal

La recuperación de historial no está implementada actualmente, pero:

1. ❌ **No hay recuperación inicial**: No existe mecanismo para obtener mensajes previos
2. ❌ **No hay integración de contexto**: Los mensajes anteriores no se incorporan al contexto
3. ✅ **API disponible**: El `conversation_service` ya tiene implementado `get_context_for_query()`

Se recomienda implementar la recuperación de historial según el flujo propuesto en este documento, aprovechando las estructuras existentes y completando el ciclo de comunicación bidireccional entre los servicios.
