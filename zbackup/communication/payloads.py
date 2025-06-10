from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar, Generic

from pydantic import BaseModel, Field, validator

# Generic type for Pydantic models used in data fields
DataT = TypeVar('DataT', bound=BaseModel)

class ErrorDetail(BaseModel):
    """Standardized error detail model."""
    error_code: str = Field(..., description="A unique code for this type of error.")
    message: str = Field(..., description="A human-readable message describing the error.")
    details: Optional[Dict[str, Any]] = Field(None, description="Optional additional details about the error.")
    retryable: bool = Field(default=False, description="Indicates if the operation that caused the error can be retried.")

class DomainAction(BaseModel, Generic[DataT]):
    """Generic wrapper for all requests/actions sent between services."""
    action_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique ID for this specific action instance.")
    action_type: str = Field(..., description="Type of the action, e.g., 'user.create', 'document.process'. Uses dot notation: {service}.{entity}.{verb}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of when the action was created (UTC).")
    
    origin_service: str = Field(..., description="Name of the service that originated this action.")
    target_service: Optional[str] = Field(None, description="Name of the service this action is intended for. Can be derived from action_type or queue name.")
    
    tenant_id: Optional[str] = Field(None, description="Identifier for the tenant, if applicable.")
    user_id: Optional[str] = Field(None, description="Identifier for the user, if applicable.")
    session_id: Optional[str] = Field(None, description="Identifier for the session, if applicable.")
    
    correlation_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="ID to correlate related actions, e.g., a request and its response/callback, or multiple steps in a workflow.")
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="ID for distributed tracing across multiple services for an entire operation flow.")
    
    callback_queue_name: Optional[str] = Field(None, description="Name of the Redis queue where a response or callback should be sent. Used by pseudo-synchronous and async-with-callback patterns.")
    callback_action_type: Optional[str] = Field(None, description="The expected action_type of the callback message. Used by async-with-callback pattern.")
    
    data: Optional[DataT] = Field(None, description="The actual payload of the action, validated by a specific Pydantic model.")
    
    version: str = Field(default="1.0.0", description="Version of the DomainAction schema.")

    @validator('action_type')
    def action_type_format(cls, v):
        parts = v.split('.')
        if not (2 <= len(parts) <= 5):
            raise ValueError('action_type must be in format like {service}.{entity}.{verb} or {service}.{entity}.{sub_entity}.{verb}')
        return v

class DomainActionResponse(BaseModel, Generic[DataT]):
    """Generic wrapper for responses in pseudo-synchronous communication."""
    success: bool = Field(..., description="Indicates if the action was successful.")
    correlation_id: uuid.UUID = Field(..., description="Correlation ID from the original DomainAction this is a response to.")
    trace_id: uuid.UUID = Field(..., description="Trace ID from the original DomainAction.")
    action_type_response_to: str = Field(..., description="The action_type of the DomainAction this is a response to.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of when the response was created (UTC).")
    
    data: Optional[DataT] = Field(None, description="The actual payload of the response, validated by a specific Pydantic model. Present if success is True and there is data to return.")
    error: Optional[ErrorDetail] = Field(None, description="Error details if success is False.")

    version: str = Field(default="1.0.0", description="Version of the DomainActionResponse schema.")

    @validator('error', always=True)
    def check_error_if_not_success(cls, v, values):
        if not values.get('success') and v is None:
            raise ValueError('error must be provided if success is False')
        if values.get('success') and v is not None:
            raise ValueError('error must not be provided if success is True')
        return v

    @validator('data', always=True)
    def check_data_if_success(cls, v, values):
        # Data can be None even if success is True (e.g., for actions with no return value)
        if not values.get('success') and v is not None:
            raise ValueError('data must not be provided if success is False')
        return v

# Example Usage (can be removed or moved to tests)
if __name__ == '__main__':
    class CreateUserPayload(BaseModel):
        username: str
        email: str

    class UserCreatedPayload(BaseModel):
        user_id: uuid.UUID
        username: str
        status: str

    # Example DomainAction
    create_user_data = CreateUserPayload(username="john_doe", email="john.doe@example.com")
    action = DomainAction[CreateUserPayload](
        action_type="user.management.create",
        origin_service="api_gateway",
        target_service="user_service",
        tenant_id="tenant123",
        correlation_id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        data=create_user_data
    )
    print("DomainAction:")
    print(action.model_dump_json(indent=2))

    # Example successful DomainActionResponse
    user_created_data = UserCreatedPayload(user_id=uuid.uuid4(), username="john_doe", status="created")
    response_success = DomainActionResponse[UserCreatedPayload](
        success=True,
        correlation_id=action.correlation_id,
        trace_id=action.trace_id,
        action_type_response_to=action.action_type,
        data=user_created_data
    )
    print("\nSuccessful DomainActionResponse:")
    print(response_success.model_dump_json(indent=2))

    # Example error DomainActionResponse
    error_detail = ErrorDetail(error_code="USER_ALREADY_EXISTS", message="User with this email already exists.")
    response_error = DomainActionResponse(
        success=False,
        correlation_id=action.correlation_id,
        trace_id=action.trace_id,
        action_type_response_to=action.action_type,
        error=error_detail
    )
    print("\nError DomainActionResponse:")
    print(response_error.model_dump_json(indent=2))

    # Example DomainAction for an async task with callback info
    process_doc_data = {"document_id": "doc_xyz", "source_url": "http://example.com/doc.pdf"}
    class ProcessDocumentPayload(BaseModel):
        document_id: str
        source_url: str

    action_async_callback = DomainAction[ProcessDocumentPayload](
        action_type="ingestion.document.process",
        origin_service="file_monitor_service",
        target_service="ingestion_service",
        correlation_id=uuid.uuid4(), # This ID will be used to match the callback
        trace_id=uuid.uuid4(),
        callback_queue_name="nooble4:dev:file_monitor_service:callbacks:ingestion_result:corr_abc123",
        callback_action_type="ingestion.document.processed",
        data=ProcessDocumentPayload(**process_doc_data)
    )
    print("\nDomainAction with callback info:")
    print(action_async_callback.model_dump_json(indent=2))
