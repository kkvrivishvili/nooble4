from abc import abstractmethod
from typing import Type, Optional, Any, Tuple

import redis.asyncio as redis_async # Importación para Redis asíncrono
from pydantic import BaseModel, ValidationError

from .base_action_handler import BaseActionHandler
# from refactorizado.common.redis_pool import RedisPool # Eliminada importación síncrona
from refactorizado.common.models.actions import DomainAction
from refactorizado.common.config import CommonAppSettings # Para tipado y constructor
from refactorizado.common.clients import BaseRedisClient # Para tipado y constructor


class BaseContextHandler(BaseActionHandler):
    """
    Extiende BaseActionHandler para añadir la gestión de un 'contexto' persistente en Redis.

    Este handler orquesta un ciclo de vida completo de "leer-modificar-guardar" para un
    objeto de estado (el contexto) antes de producir una respuesta para el worker.

    El flujo de trabajo es:
    1. `execute()` determina la clave de Redis para el contexto (`get_context_key`).
    2. Carga y valida el contexto desde Redis usando el `context_model`.
    3. Valida el payload de la `DomainAction` entrante usando `action_data_model`.
    4. Llama al método `handle()` con el contexto cargado y los datos de la acción validados.
    5. El método `handle()` implementa la lógica de negocio y devuelve una tupla:
       (contexto_actualizado, respuesta_para_el_worker)
    6. `execute()` guarda el `contexto_actualizado` de vuelta en Redis (o lo borra si es `None`).
    7. `execute()` valida la `respuesta_para_el_worker` contra `response_data_model`.
    8. Finalmente, `execute()` devuelve la respuesta al worker para su envío.
    """

    action_data_model: Optional[Type[BaseModel]] = None
    response_data_model: Optional[Type[BaseModel]] = None
    context_model: Type[BaseModel]

    def __init__(self, 
                 action: DomainAction, 
                 app_settings: CommonAppSettings, 
                 redis_client: BaseRedisClient, 
                 context_redis_client: redis_async.Redis, 
                 **kwargs):
        super().__init__(app_settings=app_settings, redis_client=redis_client, **kwargs)
        if not isinstance(action, DomainAction):
            raise TypeError("El parámetro 'action' debe ser una instancia de DomainAction.")
        self.action = action
        self.context_redis_client = context_redis_client # Cliente Redis asíncrono para contexto

    @abstractmethod
    async def get_context_key(self) -> str:
        """
        Debe ser implementado por la subclase para devolver la clave única de Redis
        bajo la cual se almacena el objeto de contexto.

        Ejemplo: f'nooble4:dev:context:agent:{self.action.tenant_id}:{agent_id}'

        Returns:
            La clave completa de Redis para el contexto.
        """
        raise NotImplementedError("Las subclases deben implementar 'get_context_key'.")

    async def _load_context(self, redis_key: str) -> Optional[BaseModel]:
        """Carga y deserializa el contexto desde Redis de forma asíncrona."""
        self._logger.debug(f"Cargando contexto desde la clave: {redis_key}")
        try:
            context_data_bytes = await self.context_redis_client.get(redis_key)
            
            if not context_data_bytes:
                self._logger.debug(f"No se encontró contexto para la clave: {redis_key}")
                return None
            
            context_data_str = context_data_bytes.decode('utf-8') if isinstance(context_data_bytes, bytes) else context_data_bytes
            return self.context_model.model_validate_json(context_data_str)
        except redis_async.RedisError as e: # Excepción del cliente Redis asíncrono
            self._logger.error(f"Error de Redis al cargar contexto desde '{redis_key}': {e}", exc_info=True)
            raise  # Re-lanzar para que el worker lo maneje como un error de procesamiento
        except ValidationError as e:
            self._logger.error(f"Error de validación al deserializar contexto desde '{redis_key}': {e}", exc_info=True)
            raise

    async def _save_context(self, redis_key: str, context: Optional[BaseModel]):
        """Guarda el contexto en Redis o lo elimina si es None, de forma asíncrona."""
        try:
            if context:
                self._logger.debug(f"Guardando contexto en la clave: {redis_key}")
                await self.context_redis_client.set(redis_key, context.model_dump_json())
            else:
                self._logger.debug(f"Eliminando contexto de la clave: {redis_key}")
                await self.context_redis_client.delete(redis_key)
        except redis_async.RedisError as e: # Excepción del cliente Redis asíncrono
            self._logger.error(f"Error de Redis al guardar/borrar contexto en '{redis_key}': {e}", exc_info=True)
            raise

    async def execute(self) -> Optional[BaseModel]:
        """Implementa el punto de entrada principal para Context Handlers."""
        # 1. Cargar contexto
        redis_key = await self.get_context_key()
        context = await self._load_context(redis_key)

        # 2. Validar datos de la acción (lógica similar a la del padre)
        validated_action_data = None
        if self.action_data_model:
            validated_action_data = self.action_data_model.model_validate(self.action.data)
        elif self.action.data is not None:
            self._logger.warning(
                f"Acción '{self.action.action_type}' recibió datos pero no tiene 'action_data_model' definido."
            )
            validated_action_data = self.action.data

                # 3. Llamar a la lógica de negocio
        updated_context, response_object = await self.handle(context, validated_action_data)


        # 4. Guardar el contexto
        await self._save_context(redis_key, updated_context)

                # 5. Validar y devolver la respuesta
        if self.response_data_model:
            if response_object is None:
                self._logger.debug(f"Handler para '{self.action.action_type}' devolvió None, lo cual es permitido.")
                return None
            
            if not isinstance(response_object, self.response_data_model):
                msg = f"El handler para '{self.action.action_type}' devolvió un objeto de tipo '{type(response_object).__name__}' pero se esperaba '{self.response_data_model.__name__}'"
                self._logger.error(msg, extra=self.action.get_log_extra())
                raise TypeError(msg)
        
        elif response_object is not None:
             self._logger.warning(
                f"Handler para '{self.action.action_type}' devolvió datos pero no tiene 'response_data_model' definido.",
                extra=self.action.get_log_extra()
            )

        return response_object

    @abstractmethod
    async def handle(
        self, context: Optional[BaseModel], validated_data: Optional[Any]
    ) -> Tuple[Optional[BaseModel], Optional[BaseModel]]:
        """
        Lógica de negocio principal que opera sobre un contexto.

        Args:
            context: La instancia del `context_model` cargada desde Redis, o None si no existía.
            validated_data: El payload de la acción, ya validado.

        Returns:
            Una tupla conteniendo:
            - [0]: El contexto actualizado para ser guardado en Redis (o None para borrarlo).
            - [1]: El objeto de respuesta (instancia de `response_data_model`) para ser enviado por el worker (o None).
        """
        raise NotImplementedError("Las subclases deben implementar el método 'handle'.")
