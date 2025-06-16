"""
Este módulo proporciona una clase para generar nombres de colas Redis de manera consistente y centralizada.

Clases:
- QueueManager: Genera nombres de colas para acciones, respuestas y callbacks.
"""

from typing import Optional

class QueueManager:
    """
    Genera nombres de colas Redis estandarizados.

    La estructura de nombres de cola sigue el patrón:
    `{prefix}:{environment}:{service_name}:{queue_type}:{context}`
    """
    def __init__(self, prefix: str = "nooble4", environment: Optional[str] = None):
        self.prefix = prefix
        self.environment = environment or "dev"

    def _build_queue_name(self, service_name: str, queue_type: str, context: str) -> str:
        """Construye el nombre de la cola con el formato estandarizado."""
        return f"{self.prefix}:{self.environment}:{service_name}:{queue_type}:{context}"

    def get_service_action_stream(self, service_name: str) -> str:
        """
        Obtiene el nombre del stream de acciones principal para un servicio.
        Ej: nooble4:dev:embedding_service:streams:main
        """
        return self._build_queue_name(service_name, "streams", "main")

    def get_response_queue(self, client_service_name: str, action_type: str, correlation_id: str) -> str:
        """
        Obtiene el nombre de una cola de respuesta para una solicitud pseudo-síncrona.
        Ej: nooble4:dev:agent_execution_service:responses:get_agent_config:uuid-1234
        """
        action_type_short = action_type.replace(".", "_")
        context = f"{action_type_short}:{correlation_id}"
        return self._build_queue_name(client_service_name, "responses", context)

    def get_callback_queue(self, client_service_name: str, action_type: str, correlation_id: str) -> str:
        """
        Obtiene el nombre de una cola de callback para una solicitud asíncrona.
        Ej: nooble4:dev:ingestion_service:callbacks:embedding_result:uuid-5678
        """
        action_type_short = action_type.replace(".", "_")
        context = f"{action_type_short}:{correlation_id}"
        return self._build_queue_name(client_service_name, "callbacks", context)
