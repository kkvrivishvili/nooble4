# Propuesta de Estandarización de Payloads y Modelos de Datos en Nooble4

## 1. Introducción

Este documento establece directrices para la estandarización de los payloads de datos utilizados en la comunicación inter-servicios en Nooble4. Cubre la estructura de los mensajes, el uso de modelos Pydantic para validación y serialización, y consideraciones sobre cuándo usar comunicación pseudo-asíncrona versus asíncrona en relación con la naturaleza del payload.

El objetivo es asegurar la integridad de los datos, la claridad de las interfaces entre servicios y facilitar el desarrollo y mantenimiento.

## 2. Estructura del Mensaje Principal: `DomainAction` y `DomainActionResponse`

La comunicación vía Redis se basa en el intercambio de mensajes serializados. Se propone estandarizar dos estructuras principales:

### 2.1. `DomainAction` (Para Solicitudes y Mensajes Asíncronos)

Este es el objeto enviado por un cliente a un servicio o por un servicio a una cola de callbacks/notificaciones. Su diseño se inspira en los datos intercambiados según `inter_service_communication_v2.md`.

*   **Ubicación del Modelo Pydantic**: `nooble4.common.messaging.domain_actions.py` (o similar en un módulo común).
*   **Campos Estándar**:

    ```python
    # nooble4/common/messaging/domain_actions.py
    from typing import Optional, Dict, Any, List
    from pydantic import BaseModel, Field
    import uuid
    from datetime import datetime, timezone

    class DomainAction(BaseModel):
        action_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Identificador único de esta acción específica.")
        action_type: str = Field(..., description='Tipo de acción en formato "servicio_destino.entidad.verbo" o "servicio_origen.evento.tipo_notificacion". Ej: "management.agent.get_config", "ingestion.document.processed".')
        timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp UTC de creación de la acción.")
        
        # --- Contexto de Negocio y Enrutamiento ---
        # Estos campos son cruciales y deben ser propagados consistentemente.
        tenant_id: Optional[str] = Field(None, description="Identificador del tenant al que pertenece esta acción.")
        session_id: Optional[str] = Field(None, description="Identificador de la sesión de conversación, si la acción es parte de una.")
        
        # --- Información de Origen y Seguimiento ---
        origin_service: Optional[str] = Field(None, description="Nombre del servicio que emite la acción. Ej: 'AgentExecutionService'.")
        # correlation_id se usa para encadenar múltiples acciones dentro de un flujo más grande o para pseudo-síncrono.
        correlation_id: Optional[uuid.UUID] = Field(None, description="ID para correlacionar esta acción con otras en un flujo o con una respuesta.")
        # trace_id es para observabilidad extremo a extremo a través de múltiples servicios.
        trace_id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, description="ID de rastreo para seguir la solicitud a través de múltiples servicios.")

        # --- Para Callbacks ---
        # callback_queue_name es la cola específica donde el servicio receptor debe enviar su respuesta/evento de callback.
        callback_queue_name: Optional[str] = Field(None, description="Nombre de la cola Redis donde se espera el callback.")
        # callback_action_type es el action_type esperado para el mensaje de callback.
        callback_action_type: Optional[str] = Field(None, description="El action_type que tendrá el mensaje de callback.")

        # --- Payload y Metadatos ---
        data: Dict[str, Any] = Field(..., description="Payload específico de la acción, validado por un modelo Pydantic dedicado.")
        metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos adicionales no críticos para la lógica principal pero útiles para logging, debugging o información contextual.")
        
        # --- Versionado (Opcional, pero recomendado para la evolución del schema de 'data') ---
        # data_schema_version: str = Field("1.0", description="Versión del schema del payload en 'data'.")

        class Config:
            validate_assignment = True # Asegura que los campos se validen también al ser asignados después de la creación.
    ```
*   **`action_type`**: Debe ser una cadena estructurada que identifique claramente la intención. Se recomienda el formato `servicio_destino.entidad.verbo` para solicitudes directas, y `servicio_origen.evento_principal.detalle_evento` para notificaciones o callbacks. Ejemplos:
    *   Solicitudes: `management.agent.get_config`, `embedding.batch.generate`, `query.rag.execute_sync`.
    *   Callbacks: `embedding.batch.completed`, `embedding.batch.failed`, `query.rag.results_ready`.
    *   Notificaciones: `ingestion.document.processed`, `conversation.session.ended`.
*   **`data`**: El contenido de `data` **DEBE** ser validado por un modelo Pydantic específico para esa `action_type`. Esto se discutirá en la sección 2.3.
*   **`correlation_id` vs `trace_id`**:
    *   `trace_id`: Se genera al inicio de una interacción de alto nivel (ej. una petición API del usuario) y se propaga a TODAS las `DomainActions` subsecuentes generadas dentro de ese flujo, incluso a través de múltiples servicios. Sirve para la observabilidad y el rastreo distribuido.
    *   `correlation_id`: Se usa para enlazar una `DomainAction` específica con su respuesta directa (en pseudo-síncrono) o para agrupar una serie de acciones que forman parte de una sub-operación lógica más pequeña dentro del `trace_id` general. Un nuevo `correlation_id` puede ser generado por un servicio si inicia una nueva sub-operación con otro servicio y espera un callback específico para ella, pero el `trace_id` original se mantiene.

### 2.2. `DomainActionResponse` (Para Respuestas en Patrón Pseudo-Síncrono)

Este es el objeto enviado por un servicio de vuelta al cliente en la cola de respuesta temporal, como se describe en `inter_service_communication_v2.md` para flujos pseudo-síncronos.

*   **Ubicación del Modelo Pydantic**: `nooble4.common.messaging.domain_actions.py`
*   **Campos Estándar**:

    ```python
    # nooble4/common/messaging/domain_actions.py (continuación)
    from pydantic import root_validator

    class ErrorDetail(BaseModel):
        error_type: str = Field(..., description="Tipo de error general. Ej: 'NotFound', 'ValidationError', 'ResourceConflict', 'UpstreamServiceError', 'InternalError'.")
        error_code: Optional[str] = Field(None, description="Código de error específico del servicio o de la lógica de negocio. Ej: 'AGENT_NOT_FOUND', 'EMBEDDING_MODEL_UNAVAILABLE'.")
        message: str = Field(..., description="Mensaje descriptivo del error, orientado al desarrollador.")
        details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detalles adicionales estructurados, como errores de validación por campo.")
        # upstream_error: Optional[Dict[str, Any]] = Field(None, description="Si el error se originó en un servicio externo, aquí se pueden incluir detalles de ese error.")

    class DomainActionResponse(BaseModel):
        action_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Identificador único de este mensaje de respuesta.")
        correlation_id: uuid.UUID = Field(..., description="ID de correlación de la DomainAction original para que el cliente pueda emparejar la respuesta.")
        trace_id: uuid.UUID = Field(..., description="ID de rastreo de la DomainAction original para mantener la observabilidad end-to-end.")
        action_type_response_to: str = Field(..., description="El 'action_type' de la solicitud original, para claridad del cliente.")

        success: bool = Field(..., description="Indica si la acción fue procesada exitosamente.")
        timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp UTC de creación de la respuesta.")
        
        data: Optional[Dict[str, Any]] = Field(None, description="Payload de respuesta si success=True, validado por un modelo Pydantic específico.")
        error: Optional[ErrorDetail] = Field(None, description="Detalles del error si success=False.")
        
        # Para telemetría (opcional)
        # service_processing_time_ms: Optional[float] = None 

        @root_validator
        def check_data_or_error(cls, values):
            success, data, error = values.get('success'), values.get('data'), values.get('error')
            if success and data is None:
                raise ValueError("'data' must be provided when success is True")
            if not success and error is None:
                raise ValueError("'error' must be provided when success is False")
            if success and error is not None:
                raise ValueError("'error' must be None when success is True")
            if not success and data is not None:
                raise ValueError("'data' must be None when success is False")
            return values

        class Config:
            validate_assignment = True
    ```
*   **`action_id`**: Identificador único del propio mensaje de respuesta.
*   **`correlation_id`, `trace_id`, `action_type_response_to`**: Esenciales para que el cliente pueda emparejar la respuesta con su solicitud original, mantener el contexto de seguimiento y saber a qué tipo de acción responde.
*   **`data`**: Si `success` es `True`, este campo contiene el resultado. Su estructura también **DEBE** ser validada por un modelo Pydantic específico.
*   **`error`**: Si `success` es `False`, este campo proporciona detalles estructurados del error. El modelo `ErrorDetail` se ha expandido para ser más informativo.

### 2.3. Modelos Pydantic Específicos para `data` (Solicitudes, Respuestas y Callbacks)

Para cada `action_type` que lleva un payload en `DomainAction.data` o `DomainActionResponse.data`, se debe definir un modelo Pydantic específico. Esto es crucial para la validación y la claridad contractual entre servicios.

*   **Ubicación Sugerida**: En un paquete común, organizado por servicio o dominio, para facilitar la importación tanto por el cliente como por el servidor.
    *   `nooble4.common.schemas.{nombre_servicio}.{nombre_entidad_o_flujo}_schemas.py`
    *   Ejemplo: `nooble4.common.schemas.management.agent_schemas.py`, `nooble4.common.schemas.embedding.batch_schemas.py`

*   **Ejemplo 1: Solicitud y Respuesta para `management.agent.get_config`**

    ```python
    # nooble4/common/schemas/management/agent_schemas.py
    from pydantic import BaseModel, Field
    from typing import List, Dict, Any, Optional
    import uuid

    # Solicitud para action_type="management.agent.get_config"
    class GetAgentConfigRequestData(BaseModel):
        agent_id: uuid.UUID
        # tenant_id, user_id, etc., están en la DomainAction raíz.

    # Parte de la respuesta
    class ToolConfigSchema(BaseModel):
        tool_name: str
        tool_config: Optional[Dict[str, Any]] = None
        # Otras propiedades relevantes de la herramienta para el agente

    class CollectionAssociationSchema(BaseModel):
        collection_id: uuid.UUID
        collection_name: str # Denormalizado para conveniencia del cliente
        # Otros detalles de la asociación si son necesarios

    # Respuesta para action_type="management.agent.get_config" (va en DomainActionResponse.data)
    class GetAgentConfigResponseData(BaseModel):
        agent_id: uuid.UUID
        name: str
        system_prompt: str
        llm_model_name: str
        llm_temperature: float = Field(..., ge=0, le=1)
        llm_max_tokens: Optional[int] = None
        associated_tools: List[ToolConfigSchema] = []
        associated_collections: List[CollectionAssociationSchema] = []
        # Otros campos de configuración del agente...
        # metadata específica del agente si es diferente de DomainAction.metadata
    ```

*   **Ejemplo 2: Solicitud y Callback para `embedding.batch.generate` / `embedding.batch.completed`** (basado en `ingestion_embedding_communication.md`)

    ```python
    # nooble4/common/schemas/embedding/batch_schemas.py
    from pydantic import BaseModel, Field
    from typing import List, Dict, Any, Optional
    import uuid

    class TextToEmbed(BaseModel):
        text_id: str # ID único proporcionado por el cliente para este texto
        text_content: str
        metadata: Optional[Dict[str, Any]] = None # Metadatos asociados al texto

    # Solicitud para action_type="embedding.batch.generate"
    class GenerateEmbeddingsBatchRequestData(BaseModel):
        # correlation_id y callback_queue_name están en la DomainAction raíz
        embedding_model: str # Ej. "text-embedding-ada-002"
        texts_to_embed: List[TextToEmbed]
        # Otros parámetros específicos del proveedor de embeddings

    # --- Para el Callback --- 
    # action_type="embedding.batch.completed" o "embedding.batch.failed"
    
    class EmbeddingResult(BaseModel):
        text_id: str # Corresponde al text_id de la solicitud
        embedding_vector: Optional[List[float]] = None
        error_message: Optional[str] = None # Si este texto específico falló

    # Payload para DomainAction.data cuando action_type="embedding.batch.completed"
    class EmbeddingsBatchCompletedCallbackData(BaseModel):
        original_correlation_id: uuid.UUID # El correlation_id de la GenerateEmbeddingsBatchRequestData
        embedding_model_used: str
        results: List[EmbeddingResult]
        # Podría incluir un resumen, como num_successful, num_failed

    # Payload para DomainAction.data cuando action_type="embedding.batch.failed"
    class EmbeddingsBatchFailedCallbackData(BaseModel):
        original_correlation_id: uuid.UUID
        error_type: str # Ej. "MODEL_UNAVAILABLE", "QUOTA_EXCEEDED", "PARTIAL_FAILURE"
        error_message: str
        # Podría incluir detalles de qué falló si es un error general del batch
    ```

*   **Uso**: 
    *   El servicio cliente instancia el modelo `...RequestData` y lo pasa como `data` en `DomainAction`.
    *   El servicio worker deserializa `DomainAction.data` al mismo modelo para validación y acceso.
    *   Para respuestas pseudo-síncronas, el worker instancia el modelo `...ResponseData` y lo pasa como `data` en `DomainActionResponse`.
    *   Para callbacks, el servicio que completa la tarea asíncrona instancia el modelo `...CallbackData` y lo pasa como `data` en un nuevo `DomainAction` enviado a la `callback_queue_name`.

## 3. Elección del Patrón de Comunicación Basado en el Payload y Necesidades

La naturaleza del payload y los requisitos de la interacción influyen en si se debe usar un patrón pseudo-síncrono o asíncrono.

### 3.1. Pseudo-Síncrono

*   **Cuándo Usar**: 
    *   El cliente necesita una respuesta *inmediata* para continuar su flujo (ej. AES necesita la config del agente de AMS antes de ejecutar).
    *   La operación en el servicio destino es relativamente rápida (ej. lectura de datos, validaciones simples).
    *   El payload de respuesta es esencial para el siguiente paso del cliente.
*   **Payloads Típicos**: Solicitudes de lectura (GET), operaciones CRUD que devuelven el estado del recurso, validaciones.
*   **Ejemplos de `inter_service_communication_v2.md`**: `management.get_agent_config`, `conversation.get_history`, `embedding.generate.sync`, `query.rag.sync`.

### 3.2. Asíncrono Fire-and-Forget

*   **Cuándo Usar**:
    *   El cliente no necesita una confirmación inmediata de que la acción se completó.
    *   La acción puede tomar tiempo en procesarse y el cliente no quiere/puede esperar.
    *   El resultado de la acción no es directamente necesario para el flujo inmediato del cliente (podría haber notificaciones posteriores).
*   **Payloads Típicos**: Operaciones de escritura que no requieren el resultado inmediato (ej. guardar un mensaje, iniciar una tarea de fondo), envío de eventos o telemetría.
*   **Ejemplos**: `conversation.save_message` (como se usa actualmente por AES).

### 3.3. Asíncrono con Callbacks

*   **Cuándo Usar**:
    *   La operación en el servicio destino es de larga duración (ej. procesamiento de archivos, tareas de machine learning complejas como la generación de embeddings para lotes grandes, ingesta masiva).
    *   El cliente no puede bloquearse esperando, pero necesita ser notificado del resultado final (éxito, fallo, datos resultantes).
    *   Se requiere un desacoplamiento fuerte entre el solicitante y el procesador.
*   **Payloads Típicos**:
    *   **Solicitud (`DomainAction`)**: 
        *   `action_type` indica la operación asíncrona (ej. `embedding.batch.generate`).
        *   `callback_queue_name` (en `DomainAction` raíz) es **obligatorio** e indica dónde enviar el resultado.
        *   `callback_action_type` (en `DomainAction` raíz) puede especificar el `action_type` esperado para el mensaje de callback (ej. `embedding.batch.completed`).
        *   `correlation_id` (en `DomainAction` raíz) es **obligatorio** para que el solicitante pueda correlacionar el callback con la solicitud original.
        *   `data` (en `DomainAction` raíz) contiene el payload específico de la solicitud (ej. `GenerateEmbeddingsBatchRequestData`).
    *   **Callback (es otro `DomainAction` enviado a `callback_queue_name`)**:
        *   `action_type` indica el resultado del callback (ej. `embedding.batch.completed` o `embedding.batch.failed`).
        *   `correlation_id` (en `DomainAction` raíz) **DEBE** ser el mismo que el de la `DomainAction` de solicitud original.
        *   `trace_id` (en `DomainAction` raíz) **DEBE** ser el mismo que el de la `DomainAction` de solicitud original.
        *   `data` (en `DomainAction` raíz) contiene el payload específico del callback (ej. `EmbeddingsBatchCompletedCallbackData` o `EmbeddingsBatchFailedCallbackData`), que a su vez debe incluir el `original_correlation_id` para una doble verificación si se desea.
*   **Ejemplos**: 
    *   Proceso de ingesta (`IngestionService` -> `EmbeddingService`): `IngestionService` envía `DomainAction` con `action_type='embedding.batch.generate'`, especificando `callback_queue_name` y `correlation_id`. `EmbeddingService` procesa y luego envía un nuevo `DomainAction` (ej. `action_type='embedding.batch.completed'`) a esa cola, incluyendo el mismo `correlation_id` y los resultados en su campo `data`.
    *   Tareas de ejecución de agentes muy largas que podrían dividirse en fases con callbacks intermedios o finales.

## 4. Consideraciones Adicionales para Payloads

*   **Tamaño del Payload**: Evitar payloads excesivamente grandes en Redis. Si se necesita transferir archivos grandes, considerar un almacenamiento intermedio (ej. S3) y pasar solo la URL/referencia en el payload.
*   **Sensibilidad de los Datos**: Si se transmiten datos sensibles, asegurar que la instancia de Redis esté adecuadamente protegida. Para datos extremadamente sensibles, considerar si Redis es el canal apropiado o si se requiere encriptación a nivel de payload (aunque esto añade complejidad).
*   **Versionado de Schemas**: Para `DomainAction.data` y `DomainActionResponse.data`, si se anticipan cambios frecuentes en sus estructuras que podrían romper la compatibilidad, considerar incluir un campo `data_schema_version` en `DomainAction` y `DomainActionResponse`. Los servicios podrían usar esto para manejar diferentes versiones del payload.
*   **Idempotencia**: Para acciones que podrían ser reenviadas (ej. por reintentos del cliente o del worker), el payload de la solicitud (`DomainAction.data`) debería, si es posible, contener suficiente información para que el servicio receptor pueda detectar y manejar duplicados de forma idempotente (ej. usando un `request_id` único dentro de `data` además del `action_id`).

## 5. Pasos Siguientes Sugeridos

1.  **Crear Módulo Común de Mensajería**: Establecer `nooble4.common.messaging` (o similar) y definir `DomainAction`, `DomainActionResponse`, y `ErrorDetail`.
2.  **Crear Repositorio de Schemas Pydantic**: Establecer `nooble4.common.schemas` y comenzar a definir los modelos Pydantic para los payloads `data` de las acciones y respuestas más comunes, empezando por un servicio piloto.
3.  **Refactorizar Clientes y Handlers**: Modificar los clientes (ver `standart_client.md`) para que construyan `DomainActions` usando estos modelos. Modificar los handlers (ver `standart_handler.md`) para que esperen y validen `DomainActions` y sus payloads `data` con estos modelos.
4.  **Actualizar Documentación**: Asegurar que `inter_service_communication_v2.md` refleje estas estructuras de payload estandarizadas.

Al estandarizar los payloads y modelos de datos, Nooble4 mejorará significativamente la robustez, claridad y mantenibilidad de sus comunicaciones inter-servicios.
