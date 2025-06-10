import uuid
import json
import logging
from typing import Optional, TypeVar, Any, Generic

import redis # Using synchronous redis client for now

from .payloads import DomainAction, DomainActionResponse, DataT, ErrorDetail
from .queue_manager import QueueManager # Import QueueManager

# Configure basic logging
logger = logging.getLogger(__name__)

class BaseRedisClient:
    """
    Base client for sending DomainActions to other services via Redis queues.
    """
    def __init__(self, redis_connection: redis.Redis, origin_service_name: str, environment: str = "dev", global_prefix: str = "nooble4"):
        if not isinstance(redis_connection, redis.Redis):
            raise TypeError("redis_connection must be an instance of redis.Redis")
        self.redis: redis.Redis = redis_connection
        self.origin_service_name: str = origin_service_name
        self.environment: str = environment
        self.queue_manager: QueueManager = QueueManager(global_prefix=global_prefix, environment=self.environment)

    # Removed _get_target_action_queue_name and _get_client_response_queue_name
    # as QueueManager will handle this directly where needed.

    def _send_domain_action_to_specific_queue(self, queue_name: str, action: DomainAction) -> None:
        """Helper method to send a DomainAction to a specific queue name."""
        try:
            logger.debug(f"Sending action {action.action_id} ({action.action_type}) directly to queue {queue_name} via _send_domain_action_to_specific_queue")
            self.redis.rpush(queue_name, action.model_dump_json())
        except redis.exceptions.RedisError as e:
            logger.exception(f"Redis error sending action {action.action_id} to queue {queue_name}: {e}")
            raise # Re-raise to allow calling method to handle
        except Exception as e:
            logger.exception(f"Unexpected error sending action {action.action_id} to queue {queue_name}: {e}")
            raise # Re-raise

    def send_action_pseudo_sync(self,
                                action_type: str,
                                target_service_name: str,
                                data: Optional[DataT] = None,
                                tenant_id: Optional[str] = None,
                                user_id: Optional[str] = None,
                                session_id: Optional[str] = None,
                                existing_trace_id: Optional[uuid.UUID] = None,
                                timeout_seconds: int = 30) -> DomainActionResponse[Any]:
        """
        Sends an action and waits for a response in a pseudo-synchronous manner.
        """
        correlation_id = uuid.uuid4()
        trace_id = existing_trace_id or uuid.uuid4()
        action_id = uuid.uuid4()

        action_type_short = self.queue_manager._sanitize(action_type.split('.')[-1]) # Sanitize for queue name
        response_queue_name = self.queue_manager.get_client_response_queue(
            client_service_name=self.origin_service_name,
            action_type_short_name=action_type_short,
            correlation_id=correlation_id
        )

        domain_action = DomainAction(
            action_id=action_id,
            action_type=action_type,
            origin_service=self.origin_service_name,
            target_service=target_service_name,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            callback_queue_name=response_queue_name,
            data=data
        )

        target_action_queue = self.queue_manager.get_service_actions_queue(target_service_name=target_service_name, tenant_id=domain_action.tenant_id, context=domain_action.session_id)

        try:
            logger.debug(f"Sending pseudo-sync action {action_id} ({action_type}) to {target_action_queue}, expecting response on {response_queue_name}")
            self.redis.rpush(target_action_queue, domain_action.model_dump_json())

            # Blocking pop from the response queue
            response_data = self.redis.blpop([response_queue_name], timeout=timeout_seconds)
            if response_data is None:
                logger.error(f"Timeout waiting for response on {response_queue_name} for action {action_id}")
                error_detail = ErrorDetail(error_code="CLIENT_TIMEOUT", message="Client timed out waiting for response.")
                return DomainActionResponse(
                    success=False, 
                    correlation_id=correlation_id, 
                    trace_id=trace_id,
                    action_type_response_to=action_type,
                    error=error_detail
                )

            # response_data is a tuple (queue_name, message_bytes)
            _, message_json = response_data
            response_dict = json.loads(message_json.decode('utf-8'))
            
            # Determine the type of 'data' or 'error' for parsing
            # This is a simplification; a more robust solution might involve a model registry
            # or passing the expected response model type.
            # For now, we parse into a generic DomainActionResponse.
            parsed_response = DomainActionResponse[Any].model_validate(response_dict) # type: ignore
            logger.debug(f"Received response for action {action_id} on {response_queue_name}")
            return parsed_response

        except redis.exceptions.RedisError as e:
            logger.exception(f"Redis error during pseudo-sync action {action_id}: {e}")
            error_detail = ErrorDetail(error_code="REDIS_CLIENT_ERROR", message=str(e))
            return DomainActionResponse(
                success=False, 
                correlation_id=correlation_id, 
                trace_id=trace_id,
                action_type_response_to=action_type,
                error=error_detail
            )
        except json.JSONDecodeError as e:
            logger.exception(f"JSON decode error for response to action {action_id}: {e}")
            error_detail = ErrorDetail(error_code="RESPONSE_DECODE_ERROR", message=f"Could not decode response JSON: {e}")
            return DomainActionResponse(
                success=False, 
                correlation_id=correlation_id, 
                trace_id=trace_id,
                action_type_response_to=action_type,
                error=error_detail
            )
        except Exception as e:
            logger.exception(f"Unexpected error during pseudo-sync action {action_id}: {e}")
            error_detail = ErrorDetail(error_code="CLIENT_UNEXPECTED_ERROR", message=str(e))
            return DomainActionResponse(
                success=False, 
                correlation_id=correlation_id, 
                trace_id=trace_id,
                action_type_response_to=action_type,
                error=error_detail
            )

    def send_action_async(self,
                          action_type: str,
                          target_service_name: str,
                          data: Optional[DataT] = None,
                          tenant_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          session_id: Optional[str] = None,
                          existing_correlation_id: Optional[uuid.UUID] = None,
                          existing_trace_id: Optional[uuid.UUID] = None) -> uuid.UUID:
        """
        Sends an action asynchronously (fire-and-forget).
        Returns the action_id of the sent message.
        """
        action_id = uuid.uuid4()
        correlation_id = existing_correlation_id or uuid.uuid4()
        trace_id = existing_trace_id or uuid.uuid4()

        domain_action = DomainAction(
            action_id=action_id,
            action_type=action_type,
            origin_service=self.origin_service_name,
            target_service=target_service_name,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            data=data
        )

        target_action_queue = self.queue_manager.get_service_actions_queue(target_service_name=target_service_name, tenant_id=domain_action.tenant_id, context=domain_action.session_id)

        try:
            logger.debug(f"Sending async action {action_id} ({action_type}) to {target_action_queue}")
            self.redis.rpush(target_action_queue, domain_action.model_dump_json())
            return action_id
        except redis.exceptions.RedisError as e:
            logger.exception(f"Redis error during async action {action_id}: {e}")
            # In fire-and-forget, we might not be able to do much more than log
            # Or raise an exception to indicate sending failure
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during async action {action_id}: {e}")
            raise

    def send_action_async_with_callback(self,
                                        action_type: str,
                                        target_service_name: str,
                                        callback_queue_name: str,
                                        callback_action_type: str,
                                        data: Optional[DataT] = None,
                                        tenant_id: Optional[str] = None,
                                        user_id: Optional[str] = None,
                                        session_id: Optional[str] = None,
                                        existing_correlation_id: Optional[uuid.UUID] = None,
                                        existing_trace_id: Optional[uuid.UUID] = None) -> uuid.UUID:
        """
        Sends an action asynchronously and specifies a queue and action type for a callback.
        Returns the action_id of the sent message.
        """
        action_id = uuid.uuid4()
        # For async_with_callback, correlation_id is crucial for matching the callback to the original request.
        # If not provided, a new one is generated for this specific request-callback pair.
        correlation_id = existing_correlation_id or uuid.uuid4()
        trace_id = existing_trace_id or uuid.uuid4()

        domain_action = DomainAction(
            action_id=action_id,
            action_type=action_type,
            origin_service=self.origin_service_name,
            target_service=target_service_name,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            callback_queue_name=callback_queue_name,
            callback_action_type=callback_action_type,
            data=data
        )

        target_action_queue = self.queue_manager.get_service_actions_queue(target_service_name=target_service_name, tenant_id=domain_action.tenant_id, context=domain_action.session_id)

        try:
            logger.debug(f"Sending async action {action_id} ({action_type}) to {target_action_queue} with callback to {callback_queue_name} ({callback_action_type})")
            self.redis.rpush(target_action_queue, domain_action.model_dump_json())
            return action_id
        except redis.exceptions.RedisError as e:
            logger.exception(f"Redis error during async_with_callback action {action_id}: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during async_with_callback action {action_id}: {e}")
            raise

# Example Usage (illustrative, requires a running Redis instance and a listening worker)
if __name__ == '__main__':
    # This example won't run without a Redis server and a worker.
    # It's for illustration of how the client might be used.
    
    # Dummy Redis connection (replace with actual connection)
    try:
        redis_conn = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False) # decode_responses=False for bytes
        redis_conn.ping() 
        print("Connected to Redis!")
    except redis.exceptions.ConnectionError as e:
        print(f"Could not connect to Redis: {e}. Skipping BaseRedisClient example.")
        redis_conn = None

    if redis_conn:
        client = BaseRedisClient(redis_connection=redis_conn, origin_service_name="example_service")

        # 1. Example: Pseudo-synchronous call
        print("\n--- Example: Pseudo-synchronous call ---")
        class PingPayload(BaseModel):
            message: str
        
        class PongPayload(BaseModel):
            response_message: str
            original_message: str

        # To test this, a worker on 'test_target_service' needs to:
        # 1. Listen on 'nooble4:dev:test_target_service:actions'
        # 2. On receiving a 'test.ping' action, construct a PongPayload
        # 3. Send a DomainActionResponse[PongPayload] to the 'callback_queue_name' from the request.
        
        # Simulating that the worker would do this (this part is manual for the example):
        # target_service_response_queue = "nooble4:dev:example_service:responses:ping:some_correlation_id"
        # response_payload = PongPayload(response_message="Pong!", original_message="Ping from client")
        # success_response = DomainActionResponse[PongPayload](success=True, correlation_id=uuid.uuid4(), trace_id=uuid.uuid4(), action_type_response_to="test.ping", data=response_payload)
        # redis_conn.rpush(target_service_response_queue, success_response.model_dump_json())
        
        # This call would typically be made by the client:
        # response_sync = client.send_action_pseudo_sync(
        #     action_type="test.ping",
        #     target_service_name="test_target_service",
        #     data=PingPayload(message="Ping from client"),
        #     timeout_seconds=5
        # )
        # print(f"Pseudo-sync response: {response_sync.model_dump_json(indent=2) if response_sync else 'No response'}")
        print("Pseudo-sync example commented out as it requires a live worker to respond.")

        # 2. Example: Asynchronous fire-and-forget call
        print("\n--- Example: Asynchronous fire-and-forget call ---")
        class LogEventPayload(BaseModel):
            event_type: str
            event_details: dict

        try:
            action_id_async = client.send_action_async(
                action_type="system.log.event",
                target_service_name="logging_service",
                data=LogEventPayload(event_type="USER_LOGIN", event_details={"user": "test_user"})
            )
            print(f"Async action sent. Action ID: {action_id_async}")
            print(f"Check queue 'nooble4:dev:logging_service:actions' in Redis for message with action_id {action_id_async}.")
        except Exception as e:
            print(f"Error sending async action: {e}")

        # 3. Example: Asynchronous call with callback
        print("\n--- Example: Asynchronous call with callback ---")
        class ProcessDataPayload(BaseModel):
            input_data: str
            processing_id: str
        
        callback_q = f"{client.queue_prefix}:{client.origin_service_name}:callbacks:data_processed:{uuid.uuid4()}"
        try:
            action_id_callback = client.send_action_async_with_callback(
                action_type="data.processing.start",
                target_service_name="processing_service",
                callback_queue_name=callback_q, # Client needs to listen on this queue
                callback_action_type="data.processing.completed",
                data=ProcessDataPayload(input_data="some important data", processing_id="proc_123")
            )
            print(f"Async action with callback sent. Action ID: {action_id_callback}")
            print(f"Client should listen on '{callback_q}' for a callback action of type 'data.processing.completed'.")
            print(f"Check queue 'nooble4:dev:processing_service:actions' in Redis for message with action_id {action_id_callback}.")
        except Exception as e:
            print(f"Error sending async_with_callback action: {e}")
