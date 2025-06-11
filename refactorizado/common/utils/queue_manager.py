"""
Gestor de Nombres de Colas Redis.

Este módulo proporciona una forma centralizada y estandarizada de generar
los nombres de las colas Redis utilizadas para la comunicación entre servicios.
"""

import os
from enum import Enum
from typing import Optional


class QueueManager:
    """
    Gestiona la nomenclatura de las colas y canales de Redis siguiendo el estándar
    jerárquico definido en `standart_colas.md`.

    Formato: {prefix}:{env}:{service}:{context_spec?}:{type}:{detail}
    """

    def __init__(
        self,
        prefix: str = "nooble4",
        environment: Optional[str] = None
    ):
        """
        Inicializa el gestor de colas.

        Args:
            prefix (str, optional): El prefijo global para todas las claves. Por defecto "nooble4".
            environment (Optional[str], optional): El entorno de despliegue. Si es None, se
                intentará obtener de la variable de entorno 'ENVIRONMENT'. Por defecto "dev".
        """
        self.prefix = prefix
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self.base_parts = f"{self.prefix}:{self.environment}"

    def get_action_queue(
        self, 
        service_name: str, 
        context: Optional[str] = None
    ) -> str:
        """
        Devuelve el nombre de la cola de acciones para un servicio.

        Args:
            service_name (str): El servicio de destino que escuchará en esta cola.
            context (Optional[str], optional): Contexto específico (ej. tenant_id).

        Formato: {base}:{service_name}:{context}:actions
        Ej: "nooble4:dev:agent_execution:actions" 
        Ej: "nooble4:dev:agent_execution:tenant_123:actions"
        """
        parts = [self.base_parts, service_name]
        if context:
            parts.append(context)
        parts.append("actions")
        return ":".join(parts)

    def get_response_queue(
        self, 
        origin_service: str, 
        action_name: str, 
        correlation_id: str,
        context: Optional[str] = None
    ) -> str:
        """
        Devuelve el nombre de una cola de respuesta única para un flujo pseudo-síncrono.

        Args:
            origin_service (str): El servicio que espera la respuesta (el propietario de la cola).
            action_name (str): El nombre de la acción que se invocó.
            correlation_id (str): El ID de correlación que une la solicitud y la respuesta.
            context (Optional[str], optional): Contexto específico (ej. session_id).

        Formato: {base}:{origin_service}:{context}:responses:{action_name}:{correlation_id}
        Ej: "nooble4:dev:orchestrator:responses:run_agent:a1b2c3d4"
        """
        parts = [self.base_parts, origin_service]
        if context:
            parts.append(context)
        parts.extend(["responses", action_name, correlation_id])
        return ":".join(parts)

    def get_callback_queue(
        self, 
        origin_service: str, 
        event_name: str,
        context: Optional[str] = None
    ) -> str:
        """
        Devuelve el nombre de una cola de callback.

        Args:
            origin_service (str): El servicio que espera el callback (propietario).
            event_name (str): El evento o tarea que generará el callback.
            context (Optional[str], optional): Contexto específico (ej. session_id).

        Formato: {base}:{origin_service}:{context}:callbacks:{event_name}
        Ej: "nooble4:dev:orchestrator:session_xyz:callbacks:agent_finished"
        """
        parts = [self.base_parts, origin_service]
        if context:
            parts.append(context)
        parts.extend(["callbacks", event_name])
        return ":".join(parts)

    def get_notification_channel(
        self, 
        origin_service: str, 
        event_name: str,
        context: Optional[str] = None
    ) -> str:
        """
        Devuelve el nombre de un canal de notificación para patrones Pub/Sub.

        Args:
            origin_service (str): El servicio que emite la notificación (propietario).
            event_name (str): El nombre del evento que se está publicando.
            context (Optional[str], optional): Contexto específico.

        Formato: {base}:{origin_service}:{context}:notifications:{event_name}
        Ej: "nooble4:dev:ingestion:notifications:document_processed"
        """
        parts = [self.base_parts, origin_service]
        if context:
            parts.append(context)
        parts.extend(["notifications", event_name])
        return ":".join(parts)
