# Estándar de Gestión de Tiers - Contabilización Downstream (`standart_tiers_downstream.md`)

Este documento describe cómo los servicios downstream (Agent Execution Service, Query Service, etc.) reportan el consumo de recursos al sistema de gestión de tiers. Este proceso es fundamental para la contabilización precisa del uso.

## 1. Objetivos de la Contabilización Downstream

*   **Contabilización en Origen:** Asegurar que el consumo de un recurso se registre en el momento y lugar exacto donde ocurre la acción, garantizando la máxima precisión.
*   **Responsabilidad Única:** Los servicios downstream son responsables de reportar el uso; no realizan validaciones. Asumen que la solicitud ya fue validada por AOS.
*   **Robustez:** La interacción para reportar el uso debe ser directa y fiable, minimizando puntos de fallo.

## 2. Abandono del Patrón de Cola y Worker

La arquitectura anterior se basaba en publicar mensajes en una cola de Redis para que un `UsageUpdateWorker` los procesara de forma asíncrona. Este patrón se **ABANDONA** por las siguientes razones:

*   **Complejidad:** Introduce un componente adicional (el worker) y una dependencia (la cola) que deben ser mantenidos y monitorizados.
*   **Punto de Fallo:** La cola puede convertirse en un punto de fallo. Si el worker se detiene, el uso no se contabiliza. Los mensajes podrían perderse si no hay una estrategia de DLQ (Dead Letter Queue).
*   **Falta de Inmediatez:** La contabilización no es en tiempo real, lo que podría llevar a condiciones de carrera donde un tenant consume más de su límite antes de que el contador se actualice.

## 3. Nuevo Estándar: Interacción Directa con `TierUsageService`

Los servicios downstream ahora interactuarán directamente con el `TierUsageService` definido en `standart_tiers_common.md`.

### 3.1. Integración de Componentes

Los servicios downstream que consumen recursos integrarán:

*   **`common.tiers.services.TierUsageService`**: El servicio que centraliza la lógica de actualización de contadores de uso.
*   **`common.tiers.models.TierResourceKey`**: La enumeración para identificar el recurso consumido.

### 3.2. Lógica de Reporte de Uso

1.  **Identificar Punto de Consumo:** Cada servicio identifica el punto en su código donde un recurso es efectivamente consumido (ej. después de una operación de base de datos exitosa, después de una llamada a una API externa, etc.).

2.  **Llamada a `increment_usage`:**
    *   Una vez consumido el recurso, el servicio realizará una llamada `await` directa al servicio de uso.
    *   El `TierUsageService` será inyectado en el handler o componente correspondiente del servicio downstream.

    ```python
    # Firma del método en TierUsageService
    async def increment_usage(
        self,
        tenant_id: str,
        resource: TierResourceKey,
        amount: int = 1
    ) -> None:
        # ... lógica interna para actualizar el repositorio (PostgreSQL/Redis) ...
    ```

3.  **Manejo de Errores:**
    *   Dado que la llamada es directa, si `increment_usage` falla (ej. por un problema de base de datos), la excepción se propagará. El servicio downstream debe decidir cómo manejarla. Generalmente, el error debe ser logueado, pero **NO** debe interrumpir la respuesta al usuario, ya que la tarea principal (ej. responder una query) ya se completó. Se recomienda un bloque `try...except` alrededor de la llamada a `increment_usage`.

## 4. Ejemplos de Reporte de Uso (Nueva Arquitectura)

*   **Query Service (QS):** Después de generar y retornar exitosamente una respuesta.
    ```python
    # En el handler de Query Service
    # ... lógica de la query ...
    try:
        await self.tier_usage_service.increment_usage(
            tenant_id=action.tenant_id,
            resource=TierResourceKey.QUERIES_PER_HOUR,
            amount=1
        )
    except Exception as e:
        logger.error(f"Fallo al contabilizar el uso de la query para el tenant {action.tenant_id}: {e}", exc_info=True)
    
    return QueryResponse(...)
    ```

*   **Embedding Service (ES):** Después de generar N embeddings.
    ```python
    # En el handler de Embedding Service
    # ... lógica de embeddings ...
    num_texts = len(request_data.texts)
    try:
        await self.tier_usage_service.increment_usage(
            tenant_id=action.tenant_id,
            resource=TierResourceKey.EMBEDDINGS_TOKENS, # Usar una clave más granular como tokens
            amount=total_tokens_consumed # Calcular el total de tokens
        )
    except Exception as e:
        logger.error(f"Fallo al contabilizar el uso de embeddings para el tenant {action.tenant_id}: {e}", exc_info=True)

    return EmbeddingResponse(...)
    ```

## 5. Configuración

*   `settings.TIER_USAGE_TRACKING_ENABLED`: Esta variable de entorno sigue siendo relevante. El `TierUsageService` la usará internamente para decidir si ejecuta la lógica de actualización o la omite (retornando inmediatamente), lo cual es útil para entornos de desarrollo y pruebas.

---

## 6. Estado de la Implementación

**La lógica de contabilización de uso ha sido implementada en el módulo `refactorizado/common/tiers` y está lista para ser integrada en los servicios downstream.**

La implementación del `TierUsageService` y su método `increment_usage` se encargan de:

1.  **Recibir la clave estandarizada** del recurso (`TierResourceKey`) y la cantidad a incrementar.
2.  **Invocar al `TierRepository`**, que es la capa de abstracción de la base de datos.
3.  **El repositorio simula una operación atómica** (usando `asyncio.Lock`) para actualizar el contador de uso del tenant en una base de datos en memoria.
4.  El manejo de errores (`try...except`) dentro del servicio que consume el recurso sigue siendo una responsabilidad del llamador, como se describe en los ejemplos.
