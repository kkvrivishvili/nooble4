# Propuesta de Estandarización de Clientes Inter-Servicios en Nooble4

## 1. Introducción

Este documento propone un conjunto de directrices para estandarizar la implementación de clientes de comunicación inter-servicios dentro del ecosistema Nooble4. El objetivo es mejorar la coherencia, reducir la duplicación de código, simplificar el mantenimiento y asegurar patrones de comunicación robustos y predecibles.

Las recomendaciones se basan en el análisis de la documentación existente (`inter_service_communication_v2.md`, `inter_service_flow_communications.md`, `ingestion_embedding_communication.md`) y las prácticas observadas.

## 2. Principios de Estandarización de Clientes

### 2.1. Protocolo de Comunicación Unificado

*   **Recomendación Principal**: Estandarizar el uso de **colas Redis como el principal mecanismo para toda la comunicación inter-servicios interna**. Esto incluye tanto solicitudes pseudo-síncronas como mensajes asíncronos (fire-and-forget y callbacks).
*   **Justificación**: La mayoría de los servicios ya utilizan Redis. Unificar este enfoque simplifica la infraestructura de comunicación, el monitoreo, y la lógica de los clientes y workers. Reduce la complejidad de tener mecanismos mixtos (como el actual HTTP POST de `IngestionService` a `EmbeddingService` para la solicitud inicial).
*   **Excepciones**: Las llamadas HTTP directas deben limitarse a casos estrictamente necesarios y bien justificados, como la exposición de APIs públicas por parte de un servicio. La comunicación interna entre servicios debe priorizar Redis.

### 2.2. Clase Base para Clientes Redis (`BaseRedisClient`)

*   **Propuesta**: Crear una clase `BaseRedisClient` en un módulo común (ej. `nooble4.common.clients.base_redis_client`).
*   **Responsabilidades de `BaseRedisClient`**:
    *   Gestión de la conexión a Redis (reutilizando instancias si es posible).
    *   Serialización y deserialización de objetos `DomainAction` (preferiblemente usando Pydantic models para la validación y estructura de `data`).
    *   Lógica para publicar `DomainAction` a colas de solicitud específicas.
    *   Implementación del **patrón pseudo-síncrono**:
        *   Generación automática de `correlation_id` (UUID).
        *   Construcción estandarizada de nombres de colas de respuesta (ej. `<target_service_prefix>:responses:<action_name>:{correlation_id}`).
        *   Operación de espera bloqueante (ej. `BLPOP`) en la cola de respuesta con un timeout configurable.
        *   Manejo básico de errores (timeouts, respuestas malformadas, `success: false` genérico).
    *   Implementación del **patrón asíncrono fire-and-forget**:
        *   Publicación de `DomainAction` sin esperar respuesta.
    *   (Opcional, si se decide mantener/expandir) Lógica para **patrón asíncrono con callbacks**: 
        *   Incluir un campo `callback_queue_name` en el `DomainAction` enviado.
        *   No esperar respuesta directa.
*   **Beneficios**: Centraliza la lógica común, reduce el código repetitivo en clientes específicos, y asegura consistencia en la implementación de los patrones de comunicación.

### 2.3. Estructura y Ubicación de Clientes Específicos

*   **Herencia**: Los clientes específicos para cada servicio (ej. `AgentManagementClient`, `EmbeddingServiceClient`) deben heredar de `BaseRedisClient`.
*   **Ubicación**: Mantener la estructura actual: `service_root/clients/target_service_client.py` (ej. `agent_execution_service/clients/agent_management_client.py`).
*   **Responsabilidad**: Los clientes específicos definirán métodos para cada acción que exponen del servicio destino. Estos métodos se encargarán de:
    *   Construir el payload (`data`) específico de la acción (usando Pydantic models).
    *   Invocar los métodos correspondientes de `BaseRedisClient` (ej. `send_sync_request`, `send_async_request`).
    *   Interpretar y validar la respuesta específica de la acción (transformando el payload de respuesta en un Pydantic model).

### 2.4. Manejo del `correlation_id`

*   **Estándar**: El `correlation_id` debe ser incluido **únicamente a nivel raíz** del objeto `DomainAction` para las comunicaciones pseudo-síncronas.
*   **Eliminación**: Remover la duplicación del `correlation_id` dentro del payload `data` observada en algunas interacciones.
*   **Implementación**: La generación y gestión del `correlation_id` para la cola de respuesta debe ser manejada transparentemente por `BaseRedisClient`.

### 2.5. Modelos de Datos (Payloads)

*   **Pydantic**: Utilizar Pydantic models para definir la estructura y validación de los payloads de solicitud (`data` dentro de `DomainAction`) y los payloads de respuesta.
*   **Ubicación**: Estos modelos deberían residir en un lugar común accesible por los servicios relevantes, idealmente en un paquete `nooble4.common.schemas` o `nooble4.common.models`, organizados por servicio o por dominio de acción.
*   **Beneficios**: Asegura la consistencia de los datos, facilita la validación, y mejora la claridad de las interfaces de comunicación.

### 2.6. Configuración de Clientes

*   **Centralización**: La configuración de la conexión a Redis (host, puerto, etc.) y los prefijos de las colas base para cada servicio deben gestionarse a través de un sistema de configuración centralizado y accesible (ej. variables de entorno cargadas en un objeto de settings).
*   **Inyección**: `BaseRedisClient` debería recibir la configuración de Redis necesaria, y los clientes específicos los prefijos de cola del servicio destino.

### 2.7. Estrategia de Callbacks Asíncronos

*   **Clarificación Necesaria**: Se debe tomar una decisión arquitectónica clara sobre el uso de callbacks asíncronos versus el patrón pseudo-síncrono.
    *   La documentación (`inter_service_flow_communications.md`, Flujo D) sugiere que los listeners de callbacks en `ExecutionWorker` podrían ser legacy, ya que los clientes (`EmbeddingClient`, `QueryClient` en AES) usan métodos `_sync`.
*   **Opción 1 (Recomendada si el pseudo-síncrono es suficiente)**: Si el patrón pseudo-síncrono cubre la mayoría de las necesidades y los tiempos de respuesta son aceptables, considerar simplificar la arquitectura eliminando los mecanismos de callback no utilizados o poco claros. Las notificaciones de eventos (ej. `ingestion.completed`) pueden seguir siendo asíncronas (fire-and-forget) a colas dedicadas.
*   **Opción 2 (Si se requieren callbacks activamente)**: Si se decide que los callbacks son esenciales para ciertas operaciones de larga duración donde el bloqueo no es una opción:
    *   `BaseRedisClient` debe tener un método explícito para enviar solicitudes que esperan un callback (ej. `send_request_with_callback(action: DomainAction, callback_queue: str)`).
    *   Los servicios que inician estas solicitudes deben proveer la `callback_queue_name` en el `DomainAction`.
    *   Los servicios receptores deben tener una lógica clara para enviar la respuesta a dicha `callback_queue_name`.

### 2.8. Manejo de Errores

*   **Excepciones Comunes**: `BaseRedisClient` debe definir y utilizar un conjunto de excepciones comunes (ej. `RequestTimeoutError`, `ServiceErrorResponse`, `MalformedResponseError`).
*   **Respuestas de Error Estructuradas**: Las respuestas de error de los servicios (cuando `success: false`) deben seguir una estructura consistente, incluyendo al menos un mensaje y un código de error, encapsulados en un Pydantic model.
    ```json
    {
      "success": false,
      "error": {
        "code": "ERROR_CODE_EXAMPLE",
        "message": "Detailed error message.",
        "details": { /* Opcional, para información adicional */ }
      }
    }
    ```
*   **Manejo en Clientes Específicos**: Los clientes específicos pueden capturar las excepciones genéricas de `BaseRedisClient` y, si es necesario, envolverlas en excepciones más específicas del dominio o añadir contexto.

## 3. Pasos Siguientes Sugeridos

1.  **Desarrollar `BaseRedisClient`**: Implementar la clase base con la funcionalidad descrita.
2.  **Definir Modelos Pydantic Comunes**: Crear los modelos para `DomainAction` y las estructuras de error estándar.
3.  **Refactorizar un Cliente Piloto**: Seleccionar un servicio y refactorizar su cliente (y el cliente correspondiente en otros servicios que lo llaman) para usar `BaseRedisClient` y los modelos Pydantic.
4.  **Evaluar y Ajustar**: Revisar la implementación piloto, ajustar `BaseRedisClient` y las directrices según sea necesario.
5.  **Extender la Estandarización**: Aplicar gradualmente la estandarización al resto de los clientes de servicios.
6.  **Actualizar Documentación**: Asegurar que `inter_service_communication_v2.md` y otros documentos relevantes reflejen estos estándares una vez implementados.

Al adoptar estas directrices, Nooble4 puede lograr un sistema de comunicación inter-servicios más robusto, mantenible y fácil de entender.
