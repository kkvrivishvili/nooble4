# Error Handling Strategy in Nooble4 Common Module

This document outlines the strategy for error and exception handling within the `common` module and by extension, for services built upon it.

## Core Principles

1.  **Custom Exceptions**: Services should raise custom exceptions derived from `common.errors.exceptions.BaseAppException` for known error conditions. This allows for structured error information.
2.  **`ErrorDetail` Model**: All errors intended to be communicated back to a client (e.g., in a `DomainActionResponse`) should be convertible to the `common.models.actions.ErrorDetail` Pydantic model. This ensures a consistent error payload structure.
3.  **Worker Responsibility**: The `BaseWorker` is responsible for catching exceptions during `_handle_action` processing.
    *   If a `BaseAppException` is caught, its `to_error_detail()` method is used to populate the `error` field in `DomainActionResponse`.
    *   If a generic `Exception` is caught, it's converted into a generic `ErrorDetail` (e.g., `error_type="UnhandledException"`), logging the original exception for debugging.
4.  **Service/Handler Responsibility**: Services and handlers are responsible for:
    *   Validating specific `action.data` payloads.
    *   Catching foreseeable errors (e.g., database errors, external API call failures, business logic violations) and re-raising them as appropriate `BaseAppException` subtypes.
5.  **No Sensitive Data in Errors**: Error messages and details sent to clients should not expose sensitive internal system information.

## Exception Classes (`common.errors.exceptions.py`)

The `exceptions.py` file defines a hierarchy of custom exceptions:

*   `BaseAppException`: The root for all custom application exceptions. It includes `error_type`, `error_code`, `message`, `details`, and a `to_error_detail()` method.
*   `ValidationAppException`: For input validation errors (e.g., invalid Pydantic model).
*   `NotFoundAppException`: When a requested resource is not found.
*   `AuthenticationAppException`: For issues related to user authentication.
*   `AuthorizationAppException`: When an authenticated user lacks permission for an action.
*   `ServiceUnavailableAppException`: If a downstream dependency is unavailable.
*   *(Others as needed)*

## Decorators (Proposed/Considered)

A decorator-based approach could be considered for service methods to:

*   **Standardize Exception Wrapping**: Automatically wrap common third-party exceptions (e.g., `sqlalchemy.exc.NoResultFound`) into custom `NotFoundAppException` or similar.
*   **Centralized Logging**: Ensure consistent logging of errors before they are re-raised or handled.
*   **Transaction Management**: For database operations, ensure rollback on unhandled exceptions.

**Example Decorator Concept (Illustrative):**

```python
# In a service or a common utility module
def handle_service_errors(logger):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except sqlalchemy.exc.NoResultFound as e:
                logger.error(f"Database entity not found: {e}")
                raise NotFoundAppException(entity_name="DatabaseRecord", message=str(e))
            except pydantic.ValidationError as e:
                logger.error(f"Service layer Pydantic validation error: {e}")
                raise ValidationAppException(message="Service data validation failed.", details=e.errors())
            except BaseAppException: # Re-raise known app exceptions
                raise
            except Exception as e:
                logger.exception(f"Unhandled exception in service method {func.__name__}: {e}")
                raise BaseAppException(message=f"An unexpected error occurred in {func.__name__}.", error_type="ServiceInternalError")
        return wrapper
    return decorator

# Usage in a service:
# @handle_service_errors(logger)
# async def my_service_method(self, ...):
#     # ...
```

This decorator approach is optional and can be implemented if it simplifies error handling patterns across multiple service methods. The primary mechanism remains the `try/except` blocks within service logic and the `BaseWorker`.

## Future Considerations

*   Integration with distributed tracing systems to correlate errors with traces.
*   More granular error codes for specific business logic failures.
