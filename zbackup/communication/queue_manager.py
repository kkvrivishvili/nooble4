import uuid
from typing import Optional

class QueueManager:
    """
    Manages the generation of standardized Redis queue names for Nooble4.
    Follows conventions from standart_colas.md.
    """
    def __init__(self, global_prefix: str = "nooble4", environment: str = "dev"):
        if not global_prefix:
            raise ValueError("global_prefix cannot be empty.")
        if not environment:
            raise ValueError("environment cannot be empty.")
        self.global_prefix = global_prefix
        self.environment = environment
        self.base_prefix = f"{self.global_prefix}:{self.environment}"

    def _sanitize(self, part: str) -> str:
        """Sanitizes a part of the queue name, replacing colons and other disallowed chars."""
        return part.replace(":", "_").replace(" ", "_")

    def get_service_actions_queue(self, target_service_name: str, tenant_id: Optional[str] = None, context: Optional[str] = None) -> str:
        """
        Generates the primary action queue name for a target service.
        Example: nooble4:dev:management:actions
        Example: nooble4:dev:embedding:tenant_xyz:actions
        Example: nooble4:dev:execution:session_123:actions

        Args:
            target_service_name: The name of the service that will listen on this queue.
            tenant_id: Optional tenant identifier.
            context: Optional specific context (e.g., session_id, worker_instance_id).
                     If tenant_id is also provided, context might be a sub-context.
        """
        if not target_service_name:
            raise ValueError("target_service_name cannot be empty.")
        
        service_part = self._sanitize(target_service_name)
        queue_parts = [self.base_prefix, service_part]

        if tenant_id:
            queue_parts.append(self._sanitize(tenant_id))
        if context:
            # If tenant_id is not present, context becomes the primary specifier.
            # If tenant_id is present, context is a sub-specifier.
            queue_parts.append(self._sanitize(context))
        
        queue_parts.append("actions")
        return ":".join(queue_parts)

    def get_client_response_queue(self, 
                                  client_service_name: str, 
                                  action_type_short_name: str, 
                                  correlation_id: uuid.UUID) -> str:
        """
        Generates a unique response queue name for a client in a pseudo-synchronous call.
        The client creates and listens on this queue.
        Example: nooble4:dev:execution_service:responses:get_config:c1a2b3d4-e5f6

        Args:
            client_service_name: The name of the client service initiating the request.
            action_type_short_name: A short, sanitized version of the action type (e.g., verb or last part).
            correlation_id: The correlation ID of the request.
        """
        if not client_service_name:
            raise ValueError("client_service_name cannot be empty.")
        if not action_type_short_name:
            raise ValueError("action_type_short_name cannot be empty.")
        if not correlation_id:
            raise ValueError("correlation_id cannot be empty.")

        return f"{self.base_prefix}:{self._sanitize(client_service_name)}:responses:{self._sanitize(action_type_short_name)}:{str(correlation_id)}"

    def get_client_callback_queue(self, 
                                  client_service_name: str, 
                                  callback_context_name: str, 
                                  unique_identifier: Optional[str] = None) -> str:
        """
        Generates a queue name where a client service expects to receive asynchronous callbacks.
        Example: nooble4:dev:ingestion_service:callbacks:embedding_results:batch_abc
        Example: nooble4:dev:execution_service:callbacks:query_results:session_123
        Example: nooble4:dev:frontend_service:callbacks:notification_stream:{user_id}

        Args:
            client_service_name: The name of the client service that will listen on this queue.
            callback_context_name: A name describing the context of the callback (e.g., 'embedding_results', 'task_completed').
            unique_identifier: Optional unique ID (e.g., correlation_id, task_id, session_id, user_id) to make the queue more specific if needed.
                               If not provided, the queue is more general for that context.
        """
        if not client_service_name:
            raise ValueError("client_service_name cannot be empty.")
        if not callback_context_name:
            raise ValueError("callback_context_name cannot be empty.")

        parts = [
            self.base_prefix, 
            self._sanitize(client_service_name), 
            "callbacks", 
            self._sanitize(callback_context_name)
        ]
        if unique_identifier:
            parts.append(self._sanitize(str(unique_identifier))) # Ensure it's a string
        
        return ":".join(parts)
    
    def get_dead_letter_queue(self, original_queue_name: str) -> str:
        """
        Generates the dead-letter queue (DLQ) name for a given original queue.
        Example: nooble4:dev:management:actions:dead_letter

        Args:
            original_queue_name: The name of the queue for which to create a DLQ name.
        """
        if not original_queue_name:
            raise ValueError("original_queue_name cannot be empty.")
        return f"{original_queue_name}:dead_letter"

# Example Usage:
if __name__ == '__main__':
    qm_dev = QueueManager(environment="dev")
    qm_prod = QueueManager(environment="prod")

    print("--- Development Queues (dev) ---")
    print(f"Management Actions: {qm_dev.get_service_actions_queue('management_service')}")
    print(f"Embedding Actions (tenant specific): {qm_dev.get_service_actions_queue('embedding_service', tenant_id='tenant_alpha')}")
    print(f"Execution Actions (session specific): {qm_dev.get_service_actions_queue('execution_service', context='session_xyz123')}")
    
    corr_id_1 = uuid.uuid4()
    print(f"Client Response Queue (AES for get_config): {qm_dev.get_client_response_queue('agent_execution_service', 'get_config', corr_id_1)}")
    
    print(f"Client Callback Queue (Ingestion for embedding results): {qm_dev.get_client_callback_queue('ingestion_service', 'embedding_results', unique_identifier='batch_789')}")
    print(f"Client Callback Queue (General task completion): {qm_dev.get_client_callback_queue('orchestration_service', 'task_completed')}")

    action_q = qm_dev.get_service_actions_queue('payment_service')
    print(f"Payment Service DLQ: {qm_dev.get_dead_letter_queue(action_q)}")

    print("\n--- Production Queues (prod) ---")
    print(f"Management Actions: {qm_prod.get_service_actions_queue('management_service')}")
    corr_id_2 = uuid.uuid4()
    print(f"Client Response Queue (WebUI for user_data): {qm_prod.get_client_response_queue('web_ui_service', 'get_user_data', corr_id_2)}")
