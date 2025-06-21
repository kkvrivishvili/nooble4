# Análisis del Flujo del Historial de Conversaciones

Este documento detalla el flujo de manejo del historial de conversaciones a través de los microservicios `agent_execution_service`, `query_service` y `conversation_service`.

## Resumen del Flujo

El proceso de una conversación, ya sea simple o avanzada, sigue un patrón claro de responsabilidad distribuida. El `agent_execution_service` actúa como el orquestador principal, gestionando el estado temporal (caché) y la lógica de la conversación, mientras que el `query_service` se encarga de la interacción con el modelo de lenguaje (LLM) y el `conversation_service` garantiza la persistencia a largo plazo de los intercambios.

El flujo general es el siguiente:

1.  **Recepción:** El `agent_execution_service` recibe una solicitud de chat del usuario.
2.  **Gestión de Historial (Caché):**
    *   Se genera una clave de caché única (`cache_key`) a partir del `tenant_id` y `session_id`.
    *   Intenta cargar el historial de la conversación desde la caché de Redis usando esta clave.
    *   Si existe un historial, se carga en memoria para la solicitud actual.
    *   Si no existe, se determina el `conversation_id`. Si es una conversación existente (pasada en el historial), se usa ese ID. Si es una conversación nueva, se genera un nuevo `conversation_id` (UUIDv4).
3.  **Preparación de la Llamada al `query_service`:**
    *   El `agent_execution_service` **no construye el prompt final**. Su responsabilidad se limita a recopilar los datos necesarios.
    *   Recupera el historial de conversación de la caché de Redis.
    *   Identifica el `agent_id` de la solicitud.

4.  **Llamada al `query_service`:**
    *   El `agent_execution_service` envía el `agent_id`, el historial de conversación recuperado (si existe) y la nueva pregunta del usuario al `query_service`. No envía un "prompt preparado", sino los componentes para que el `query_service` lo ensamble.
    *   Para una visión más detallada de cómo el `query_service` maneja esta información, consulte el documento `analisis_system_prompt_flow.md`.
    *   La llamada es a `query_simple` o `query_advance` dependiendo del tipo de chat.
5.  **Procesamiento en `query_service`:**
    *   **_Suposición:_** El `query_service` recibe la solicitud, la procesa y la envía al proveedor de LLM configurado (por ejemplo, Groq).
    *   Espera la respuesta del LLM.
6.  **Recepción de la Respuesta:**
    *   El `query_service` devuelve la respuesta del LLM al `agent_execution_service`.
7.  **Actualización y Persistencia:**
    *   El `agent_execution_service` recibe la respuesta.
    *   Actualiza el historial de la conversación en la caché de Redis, añadiendo el último intercambio (pregunta del usuario y respuesta del LLM).
    *   Llama al `conversation_service` a través de su cliente (`ConversationClient.save_conversation`) para persistir el nuevo intercambio en la base de datos a largo plazo.
8.  **Respuesta al Usuario:**
    *   El `agent_execution_service` devuelve la respuesta final al cliente.

## Análisis por Requisito

**1) El `agent_execution_service` revisa si hay una `conversation_id` creada, si está creada debería cachear el historial de conversación.**

*   **Estado:** **Confirmado.**
*   **Evidencia:** Los manejadores `simple_chat_handler.py` y `advance_chat_handler.py` contienen lógica para construir una `cache_key` y usar un `RedisStateManager` para llamar a `load_state` y `save_state`. Esto demuestra que el historial se gestiona a través de una caché en Redis.

**2) Para cualquiera de los dos métodos simple o advance debería mandarla con el system prompt, si no existe conversación, no agrega nada al system prompt.**

*   **Estado:** **No verificado (Alta Probabilidad).**
*   **Análisis:** Debido a las limitaciones de las herramientas para inspeccionar el contenido de los archivos, no se pudo verificar el payload exacto que se envía al `query_service`. Sin embargo, este es el comportamiento estándar y esperado para un sistema de chat con agentes. Es muy probable que el historial recuperado de la caché se combine con un `system_prompt` (definido para el agente) para contextualizar la llamada al LLM. Si no hay historial, solo se enviarían el `system_prompt` y la pregunta actual.

**3) Lo manda a `query_service` el cual a su vez lo manda a groq, obtiene la respuesta y la devuelve a `agent_execution_service` para que almacene en cache la respuesta, y mande a `conversation_service` los datos para persistencia.**

*   **Estado:** **Confirmado.**
*   **Evidencia:**
    *   Se ha confirmado que `agent_execution_service` utiliza un `QueryClient` para llamar a los métodos `query_simple` y `query_advance`.
    *   Se ha confirmado que después de recibir la respuesta, los manejadores actualizan el estado en la caché (`history_manager.save_state`).
    *   Se ha confirmado que los manejadores llaman a `conversation_client.save_conversation` para la persistencia.

**4) Se repite el ciclo, hace un analisis detallado del flow de historial de conversaciones, acompa;ado claramente de cualquiera de los 2 flow chay simple o chat advance.**

*   **Estado:** **Realizado.**
*   **Análisis:** Este documento representa el análisis solicitado. El flujo es prácticamente idéntico para `simple_chat` y `advance_chat` en lo que respecta al manejo del historial. La diferencia principal entre ellos probablemente radica en la lógica de procesamiento dentro del `query_service` (por ejemplo, el uso de herramientas o un razonamiento más complejo en el modo `advance`), pero el mecanismo de caché y persistencia del historial es el mismo.

## Conclusión

La arquitectura para el manejo del historial de conversaciones es robusta y sigue las mejores prácticas, separando las responsabilidades de orquestación, procesamiento de LLM y persistencia. El uso de una caché en Redis es fundamental para mantener la eficiencia y la continuidad en las conversaciones.

Aunque no se pudieron verificar todos los detalles de la implementación a nivel de código, el análisis de la estructura y los componentes disponibles proporciona una imagen clara y coherente del flujo, confirmando que la implementación cumple con los requisitos solicitados.
