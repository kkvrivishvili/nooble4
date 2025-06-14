# Estándar: Capa de Servicio y Componentes de Negocio

## 1. Introducción: De Handlers a Servicios

La arquitectura v4.0 abandona el concepto de "handlers" como funciones individuales registradas en un worker. En su lugar, introduce una **Capa de Servicio** (`Service Layer`) como el **cerebro de la lógica de negocio** de un microservicio.

- **Contrato Explícito:** Toda clase de servicio **debe** heredar de la clase base `common.services.BaseService`. Esto asegura un contrato común y un punto de anclaje para futuras funcionalidades compartidas.

El antiguo patrón de `register_handler("action.type", handler_func)` está **OBSOLETO** y no debe utilizarse.

## 2. La Capa de Servicio (`Service Layer`)

Una clase de servicio (ej: `GenerationService` en `embedding_service`) es una clase Python que encapsula y orquesta un proceso de negocio de alto nivel. Es el principal colaborador del `Worker`.

**Responsabilidades Clave:**

- **Recibir `DomainAction`s**: Sus métodos públicos aceptan `DomainAction`s del `Worker`.
- **Orquestar el Flujo de Trabajo**: Define los pasos necesarios para completar una tarea (ej: validar, procesar, guardar, notificar).
- **Delegar a Componentes Especializados**: No implementa toda la lógica por sí misma. En su lugar, utiliza otros componentes más pequeños y enfocados (ver sección 3).
- **Ser Agnóstica a la Infraestructura**: No debe saber nada sobre Redis, colas o el `Worker`. Su única dependencia externa debería ser a través de inyección de dependencias (ej: un cliente de base de datos, otro cliente de servicio).
- **Devolver Resultados Estandarizados**: Sus métodos deben devolver un diccionario simple (`Dict[str, Any]`) que indique el éxito o fracaso de la operación, para que el `Worker` pueda actuar en consecuencia.

### Ejemplo: `GenerationService`

```python
# embedding_service/services/generation_service.py

class GenerationService:
    """
    Servicio que encapsula la lógica de negocio para las acciones de embeddings.
    """

    def __init__(self, context_handler: EmbeddingContextHandler, redis_client=None):
        """Inyecta sus dependencias."""
        self.context_handler = context_handler
        self.redis = redis_client

        # Inicializa y posee los componentes especializados
        self.validation_service = ValidationService(redis_client)
        self.embedding_processor = EmbeddingProcessor(self.validation_service, redis_client)

    async def generate_embeddings(self, action: EmbeddingGenerateAction) -> Dict[str, Any]:
        """
        Orquesta el proceso de generación de embeddings.
        """
        try:
            # 1. Delegar al ContextHandler para resolver y validar permisos
            context = await self.context_handler.resolve_embedding_context(action.execution_context)
            await self.context_handler.validate_embedding_permissions(context, ...)

            # 2. Delegar al EmbeddingProcessor para el trabajo pesado
            embedding_result = await self.embedding_processor.process_embedding_request(action, context)

            # 3. Realizar tareas propias (ej: tracking de métricas)
            await self._track_embedding_metrics(...)

            # 4. Devolver un resultado estandarizado
            return {
                "success": True,
                "result": embedding_result
            }

        except Exception as e:
            logger.error(f"Error en embedding: {str(e)}")
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)}
            }
```

## 3. Componentes de Negocio Especializados

La Capa de Servicio delega tareas específicas a otras clases más pequeñas. Estas clases siguen el **Principio de Responsabilidad Única**.

**Tipos Comunes de Componentes:**

- **Processors** (ej: `EmbeddingProcessor`): Clases que realizan el "trabajo pesado" o el núcleo de la lógica algorítmica. Suelen interactuar con sistemas externos (modelos de IA, APIs de terceros).
- **Validators** (ej: `ValidationService`): Se especializan en validar datos de entrada, permisos o reglas de negocio complejas.
- **Context Handlers** (ej: `EmbeddingContextHandler`): Se encargan de cargar, validar y enriquecer el contexto de ejecución (`ExecutionContext`) necesario para una operación.
- **Callback Handlers** (ej: `EmbeddingCallbackHandler`): Clases dedicadas a construir y enviar `DomainAction`s de callback a través de un `BaseRedisClient`.

## 4. Interacción y Flujo

El flujo completo es el siguiente:

`Worker` -> `Service Layer` -> `(Processor, Validator, etc.)`

1.  El **Worker** recibe una `DomainAction` de Redis.
2.  La pasa al método apropiado de la **Capa de Servicio** (ej: `generation_service.generate_embeddings(...)`).
3.  La **Capa de Servicio** orquesta la operación, llamando a uno o más **Componentes Especializados** en la secuencia correcta.
4.  Los componentes devuelven sus resultados al servicio.
5.  El servicio consolida los resultados y devuelve un diccionario final al worker.
6.  El worker utiliza este resultado para finalizar el ciclo (enviando un callback, una respuesta, o simplemente terminando).
