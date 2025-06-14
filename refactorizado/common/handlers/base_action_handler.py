from abc import abstractmethod
from typing import Type, Optional

from pydantic import BaseModel, ValidationError

from refactorizado.common.redis_pool import RedisPool
from refactorizado.common.models.actions import DomainAction
from .base_handler import BaseHandler


class BaseActionHandler(BaseHandler):
    """
    Clase base abstracta para handlers que procesan una `DomainAction` específica.

    Hereda de `BaseHandler` y define un flujo de trabajo estándar:
    1. El worker llama a `execute()`.
    2. `execute()` valida el payload de la acción (`action.data`) usando `action_data_model`.
    3. `execute()` llama a `handle()` con los datos ya validados.
    4. `handle()` devuelve una instancia de `response_data_model` (o `None`).
    5. `execute()` devuelve esta instancia al worker.
    """
    action_data_model: Optional[Type[BaseModel]] = None
    response_data_model: Optional[Type[BaseModel]] = None

    def __init__(self, action: DomainAction, redis_pool: RedisPool, service_name: str, **kwargs):
        super().__init__(service_name=service_name, **kwargs)
        if not isinstance(action, DomainAction):
            raise TypeError("El parámetro 'action' debe ser una instancia de DomainAction.")
        self.action = action
        self.redis_pool = redis_pool

    async def execute(self) -> Optional[BaseModel]:
        """
        Implementación del punto de entrada principal para Action Handlers.

        Orquesta la validación del payload, la ejecución de la lógica de negocio
        y la validación de la respuesta.
        """
        validated_data = None
        if self.action_data_model:
            # Pydantic lanzará ValidationError si action.data es inválido.
            validated_data = self.action_data_model.model_validate(self.action.data)
        elif self.action.data is not None:
            self._logger.warning(
                f"Acción '{self.action.action_type}' recibió datos pero no tiene 'action_data_model' definido para validación.",
                extra=getattr(self.action, 'get_log_extra', lambda: {})
            )
            validated_data = self.action.data # Aunque no haya modelo, si hay datos, se pasan al handle.

        response_object = await self.handle(validated_data)

        if self.response_data_model:
            if response_object is None:
                # Es válido devolver None incluso si se espera un response_data_model (ej. acción no produce salida)
                self._logger.debug(f"Handler para '{self.action.action_type}' devolvió None, lo cual es permitido.")
                return None
            
            if not isinstance(response_object, self.response_data_model):
                msg = f"El handler para '{self.action.action_type}' devolvió un objeto de tipo '{type(response_object).__name__}' pero se esperaba '{self.response_data_model.__name__}'."
                self._logger.error(msg, extra=getattr(self.action, 'get_log_extra', lambda: {}))
                raise TypeError(msg) # Forzar error si el tipo no coincide y se esperaba uno específico
        
        elif response_object is not None:
             # Si no se espera un response_data_model pero el handler devuelve algo, es solo un warning.
             self._logger.warning(
                f"Handler para '{self.action.action_type}' devolvió datos pero no tiene 'response_data_model' definido.",
                extra=getattr(self.action, 'get_log_extra', lambda: {})
            )

        return response_object

    @abstractmethod
    async def handle(self, validated_data: Optional[Any]) -> Optional[BaseModel]:
        """
        Contiene la lógica de negocio principal del handler.

        Args:
            validated_data: El payload de la acción, ya validado como una instancia
                            de `action_data_model` (o los datos crudos si no se definió modelo).

        Returns:
            Una instancia del `response_data_model` definido en la clase, o `None`.
        """
        raise NotImplementedError("Las subclases deben implementar el método 'handle'.")

