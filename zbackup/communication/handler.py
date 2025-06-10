import logging
from abc import ABC, abstractmethod
from typing import Type, Optional, Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .payloads import DomainAction, DomainActionResponse, ErrorDetail, DataT
from .client import BaseRedisClient # Assuming client.py is in the same directory

logger = logging.getLogger(__name__)

# Type variable for the specific Pydantic model expected in DomainAction.data
RequestDataT = TypeVar('RequestDataT', bound=BaseModel)
# Type variable for the specific Pydantic model expected in DomainActionResponse.data or callback DomainAction.data
ResponseDataT = TypeVar('ResponseDataT', bound=BaseModel)

class BaseActionHandler(ABC, Generic[RequestDataT, ResponseDataT]):
    """
    Abstract base class for handling DomainActions.
    Subclasses should specify the expected Pydantic model for request data (RequestDataT)
    and the Pydantic model for response/callback data (ResponseDataT).
    """

    def __init__(self, redis_client: Optional[BaseRedisClient] = None, service_name: Optional[str] = None):
        """
        Initializes the handler.
        Args:
            redis_client: An instance of BaseRedisClient, required if the handler needs to send callbacks or other actions.
            service_name: The name of the service this handler belongs to, used for originating callbacks.
        """
        self.redis_client = redis_client
        self.service_name = service_name
        if self.service_name is None and redis_client is not None:
            self.service_name = redis_client.origin_service_name

    def _parse_action_data(self, action: DomainAction, expected_model: Type[RequestDataT]) -> Optional[RequestDataT]:
        """
        Parses the data from a DomainAction into the expected Pydantic model.
        Returns the parsed model or None if data is missing or parsing fails.
        """
        if action.data is None:
            logger.warning(f"No data provided in DomainAction {action.action_id} ({action.action_type}) when {expected_model.__name__} was expected.")
            return None
        try:
            # If action.data is already the correct model instance (e.g., if constructed internally)
            if isinstance(action.data, expected_model):
                return action.data
            # If action.data is a dict (e.g., from JSON deserialization before reaching handler)
            if isinstance(action.data, dict):
                return expected_model.model_validate(action.data)
            
            logger.error(f"Unsupported data type in DomainAction {action.action_id}: {type(action.data)}. Expected dict or {expected_model.__name__}.")
            return None
        except ValidationError as e:
            logger.error(f"Validation error parsing data for action {action.action_id} ({action.action_type}) into {expected_model.__name__}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error parsing data for action {action.action_id}: {e}")
            return None

    @abstractmethod
    async def process_action(self, action: DomainAction, parsed_data: Optional[RequestDataT]) -> DomainActionResponse[ResponseDataT]:
        """
        Abstract method to process the action.
        This method MUST be implemented by subclasses.
        It should contain the core business logic for the action.

        Args:
            action: The raw DomainAction received.
            parsed_data: The DomainAction.data parsed into the expected Pydantic model (RequestDataT), or None if parsing failed or no data.

        Returns:
            A DomainActionResponse. For fire-and-forget or async-with-callback where no direct response is sent,
            this might still be used internally by the worker to log completion or errors, or could be a simplified response.
            For pseudo-synchronous, this is the response sent back to the client's callback_queue_name.
        """
        pass

    def create_success_response(self, 
                                original_action: DomainAction, 
                                response_data: Optional[ResponseDataT] = None) -> DomainActionResponse[ResponseDataT]:
        """
        Helper to create a successful DomainActionResponse.
        """
        return DomainActionResponse[ResponseDataT](
            success=True,
            correlation_id=original_action.correlation_id,
            trace_id=original_action.trace_id,
            action_type_response_to=original_action.action_type,
            data=response_data
        )

    def create_error_response(self, 
                              original_action: DomainAction, 
                              error_code: str, 
                              message: str, 
                              details: Optional[dict] = None,
                              retryable: bool = False) -> DomainActionResponse[Any]: # Error response data is not typed with ResponseDataT
        """
        Helper to create an error DomainActionResponse.
        """
        error_detail = ErrorDetail(error_code=error_code, message=message, details=details, retryable=retryable)
        return DomainActionResponse[Any](
            success=False,
            correlation_id=original_action.correlation_id,
            trace_id=original_action.trace_id,
            action_type_response_to=original_action.action_type,
            error=error_detail
        )

    async def send_callback(self, 
                          original_action: DomainAction, 
                          callback_data: ResponseDataT, 
                          callback_action_type: Optional[str] = None) -> None:
        """
        Sends a callback DomainAction to the queue specified in the original action.
        The callback itself is a new DomainAction.

        Args:
            original_action: The action that requested this callback.
            callback_data: The data payload for the callback action.
            callback_action_type: Override for the callback action type. If None, uses original_action.callback_action_type.

        Raises:
            ValueError: If redis_client or service_name is not configured, or if callback info is missing.
        """
        if not self.redis_client:
            logger.error(f"Cannot send callback for action {original_action.action_id}: Redis client not configured in handler.")
            raise ValueError("Redis client not configured in handler for sending callbacks.")
        if not self.service_name:
            logger.error(f"Cannot send callback for action {original_action.action_id}: Handler's service_name not configured.")
            raise ValueError("Handler's service_name not configured for sending callbacks.")

        callback_queue = original_action.callback_queue_name
        cb_action_type = callback_action_type or original_action.callback_action_type

        if not callback_queue:
            logger.warning(f"No callback_queue_name in original_action {original_action.action_id}. Cannot send callback.")
            # Depending on strictness, could raise ValueError here
            return 
        if not cb_action_type:
            logger.warning(f"No callback_action_type for original_action {original_action.action_id}. Cannot send callback.")
            # Depending on strictness, could raise ValueError here
            return

        callback_action = DomainAction[ResponseDataT](
            action_type=cb_action_type, # This is the type the recipient is expecting for the callback
            origin_service=self.service_name, # This handler's service is originating the callback
            target_service=original_action.origin_service, # Callback goes back to original requester
            correlation_id=original_action.correlation_id, # CRITICAL: Must be the same to correlate
            trace_id=original_action.trace_id, # Propagate trace ID
            tenant_id=original_action.tenant_id, # Propagate context
            user_id=original_action.user_id,
            session_id=original_action.session_id,
            data=callback_data
            # callback_queue_name and callback_action_type are typically None for a callback message itself,
            # unless this callback is part of a multi-step callback chain.
        )

        try:
            logger.info(f"Sending callback action {callback_action.action_id} ({callback_action.action_type}) to {callback_queue} for original action {original_action.action_id}")
            # Use the client's send_action_async method to send the callback DomainAction.
            # Note: send_action_async sends to a service's main action queue.
            # Callbacks are sent to a specific queue name directly.
            # We need a way for the client to send to an arbitrary queue if send_action_async is strictly for service action queues.
            # For now, let's assume send_action_async can take a direct queue_name or we add a method for it.
            # Alternative: A more direct send method in BaseRedisClient for specific queues.
            # For simplicity, if send_action_async is tied to target_service_name, we might need to adjust.
            # Let's assume for now we can use a generic send method or rpush if client doesn't have one for arbitrary queues.
            # Re-evaluating: The callback_queue is a specific queue, not a generic service action queue.
            # So, a direct rpush might be acceptable here if the client doesn't have a generic "send_to_queue" method.
            # However, the spirit is to use client methods. Let's assume BaseRedisClient should have a method for this.
            # Modifying the call to send_action_async to reflect it's sending a DomainAction.
            # The `send_action_async` is designed to send to a *service's* action queue.
            # A callback is sent to a *specific* queue name.
            # We will use a direct rpush for now, and note that BaseRedisClient might need a more generic send method.
            if hasattr(self.redis_client, '_send_domain_action_to_queue'): # Check for a hypothetical direct send method
                 self.redis_client._send_domain_action_to_queue(callback_queue, callback_action) # type: ignore
            else:
                 # Fallback to direct rpush if a dedicated client method isn't available yet
                 self.redis_client.redis.rpush(callback_queue, callback_action.model_dump_json())
            # Ideal call would be something like:
            # self.redis_client.send_raw_action_to_queue(queue_name=callback_queue, action=callback_action)

        except Exception as e:
            logger.exception(f"Failed to send callback for action {original_action.action_id}: {e}")
            # Potentially raise or handle retry

# Example (Illustrative - would be in a specific service's handler implementation)
if __name__ == '__main__':
    class SampleRequestData(BaseModel):
        input_value: str

    class SampleResponseData(BaseModel):
        output_value: str
        processed_input: str

    class MySpecificHandler(BaseActionHandler[SampleRequestData, SampleResponseData]):
        async def process_action(self, action: DomainAction, parsed_data: Optional[SampleRequestData]) -> DomainActionResponse[SampleResponseData]:
            if parsed_data is None:
                logger.error(f"No valid data for action {action.action_id}")
                return self.create_error_response(action, "INVALID_PAYLOAD", "Parsed data is missing or invalid.")

            logger.info(f"Processing action {action.action_id} with data: {parsed_data.input_value}")
            
            # Simulate business logic
            processed_text = parsed_data.input_value.upper() + "_processed"
            response_payload = SampleResponseData(output_value="Successfully processed", processed_input=processed_text)
            
            # If it was an async task needing a callback:
            if action.callback_queue_name and action.callback_action_type and self.redis_client:
                logger.info(f"This action {action.action_id} expects a callback. Sending it...")
                try:
                    await self.send_callback(action, response_payload) # Assuming callback_data is SampleResponseData
                    # For async with callback, the main response might just be an ack or not sent to original queue
                    # Here we'll return a success response as if it could be pseudo-sync too.
                    return self.create_success_response(action, response_payload) # Or a simpler ack
                except Exception as e:
                    logger.exception("Failed to send callback during process_action")
                    return self.create_error_response(action, "CALLBACK_FAILED", f"Failed to send callback: {e}")
            else:
                # For pseudo-sync or fire-and-forget
                return self.create_success_response(action, response_payload)

    # --- How a worker might use it (very simplified) ---
    # import asyncio
    # from .client import BaseRedisClient # (if running from this dir)
    # import redis

    # async def main_example():
    #     # Setup (dummy redis for example)
    #     try:
    #         r_conn = redis.Redis(decode_responses=True) # For BaseRedisClient, use decode_responses=False
    #         r_conn_for_client = redis.Redis(decode_responses=False)
    #         r_conn.ping()
    #     except Exception:
    #         print("Redis not available, skipping handler example run")
    #         return

    #     # Mock Redis client for the handler
    #     mock_redis_client = BaseRedisClient(redis_connection=r_conn_for_client, origin_service_name="my_test_service")
        
    #     handler_instance = MySpecificHandler(redis_client=mock_redis_client, service_name="my_test_service")

    #     # 1. Simulate a pseudo-synchronous action
    #     print("\n--- Simulating pseudo-sync action ---")
    #     sample_data_sync = SampleRequestData(input_value="hello world")
    #     action_sync = DomainAction[SampleRequestData](
    #         action_type="sample.process.text",
    #         origin_service="test_caller",
    #         data=sample_data_sync,
    #         correlation_id=uuid.uuid4(),
    #         trace_id=uuid.uuid4()
    #     )
    #     response_sync = await handler_instance.process_action(action_sync, handler_instance._parse_action_data(action_sync, SampleRequestData))
    #     print(f"Response from handler (sync): {response_sync.model_dump_json(indent=2)}")

    #     # 2. Simulate an action requiring a callback
    #     print("\n--- Simulating action requiring callback ---")
    #     sample_data_async = SampleRequestData(input_value="async task data")
    #     action_async_cb = DomainAction[SampleRequestData](
    #         action_type="sample.process.long_task",
    #         origin_service="another_caller",
    #         data=sample_data_async,
    #         correlation_id=uuid.uuid4(),
    #         trace_id=uuid.uuid4(),
    #         callback_queue_name="nooble4:dev:another_caller:callbacks:task_done:some_corr_id",
    #         callback_action_type="sample.task.completed"
    #     )
    #     # The worker would parse data before calling process_action
    #     parsed_async_data = handler_instance._parse_action_data(action_async_cb, SampleRequestData)
    #     response_async = await handler_instance.process_action(action_async_cb, parsed_async_data)
    #     print(f"Response from handler (async_cb initial): {response_async.model_dump_json(indent=2)}")
    #     print(f"Check queue '{action_async_cb.callback_queue_name}' in Redis for the callback message.")

    # if __name__ == '__main__':
    #     # asyncio.run(main_example())
    #     print("Handler example commented out - run manually if needed with Redis.")
