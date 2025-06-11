import uuid
from datetime import datetime
from typing import Optional

import redis
from pydantic import BaseModel

from refactorizado.common.models.actions import DomainAction
from .base_action_handler import BaseActionHandler


class BaseCallbackHandler(BaseActionHandler):
    """
    Extiende BaseActionHandler para simplificar el envío de callbacks asíncronos.

    Esta clase base está diseñada para handlers que, como parte de su lógica,
    necesitan enviar una nueva DomainAction (un callback) a la cola especificada
    en la acción original, siguiendo el "Patrón 3: Asíncrono con Callbacks".
    """

    async def _send_callback(self, callback_data: BaseModel, callback_action_type: Optional[str] = None, callback_queue_name: Optional[str] = None):
        """
        Construye y envía una DomainAction de callback.

        Utiliza `callback_action_type` y `callback_queue_name` de la acción original
        a menos que se proporcionen explícitamente. Propaga los identificadores
        clave (correlation_id, task_id, trace_id).

        Args:
            callback_data: El modelo Pydantic con los datos para el payload del callback.
            callback_action_type: (Opcional) Sobrescribe el tipo de acción del callback.
            callback_queue_name: (Opcional) Sobrescribe la cola de destino del callback.
        """
        queue_name = callback_queue_name or self.action.callback_queue_name
        action_type = callback_action_type or self.action.callback_action_type

        if not queue_name or not action_type:
            self._logger.error(
                f"No se puede enviar callback para la acción {self.action.action_id}. "
                f"Falta 'callback_queue_name' o 'callback_action_type' en la acción original o en los parámetros.",
                extra=self.action.get_log_extra()
            )
            raise ValueError("Faltan los parámetros necesarios para enviar el callback.")

        callback_action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            timestamp=datetime.utcnow(),
            origin_service=self.service_name,
            tenant_id=self.action.tenant_id,
            session_id=self.action.session_id,
            correlation_id=self.action.correlation_id,  # Propagado
            task_id=self.action.task_id,              # Propagado
            trace_id=self.action.trace_id,            # Propagado
            data=callback_data.model_dump(mode='json'),
            callback_queue_name=None,  # Los callbacks no suelen encadenar más callbacks
            callback_action_type=None
        )

        try:
            with self.redis_pool.get_connection() as conn:
                conn.lpush(queue_name, callback_action.model_dump_json())
            self._logger.info(
                f"Callback '{action_type}' ({callback_action.action_id}) enviado a la cola '{queue_name}'.",
                extra=callback_action.get_log_extra()
            )
        except redis.RedisError as e:
            self._logger.error(
                f"Error de Redis al enviar callback a la cola '{queue_name}': {e}",
                extra=callback_action.get_log_extra(),
                exc_info=True
            )
            raise  # Re-lanzar para que el handler que llama sepa que el envío falló
