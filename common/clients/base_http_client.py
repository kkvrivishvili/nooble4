import httpx
from typing import Any, Dict, Optional

from common.errors.exceptions import (BadRequestError, UnauthorizedError, ForbiddenError, 
                                     NotFoundError, ConflictError, InternalServerError, ServiceUnavailableError)

class BaseHTTPClient:
    """Base class for HTTP clients."""

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initializes the HTTP client.

        Args:
            base_url: The base URL for the client.
            headers: A dictionary of headers to include in all requests.
        """
        self.base_url = base_url
        self.headers = headers or {}
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Makes an HTTP request and handles errors."""
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            return response
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e.response)
        except httpx.RequestError as e:
            # For connection errors, timeouts, etc.
            raise ServiceUnavailableError(f"Request to {e.request.url} failed: {e}") from e

    def _handle_http_error(self, response: httpx.Response) -> None:
        """Handles HTTP errors by raising appropriate exceptions."""
        status_code = response.status_code
        error_message = f"HTTP error {status_code}: {response.text}"

        if status_code == 400:
            raise BadRequestError(error_message)
        elif status_code == 401:
            raise UnauthorizedError(error_message)
        elif status_code == 403:
            raise ForbiddenError(error_message)
        elif status_code == 404:
            raise NotFoundError(error_message)
        elif status_code == 409:
            raise ConflictError(error_message)
        elif status_code >= 500:
            raise InternalServerError(error_message)
        else:
            # For other 4xx errors
            raise InternalServerError(f"Unhandled HTTP error {status_code}: {response.text}")

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> httpx.Response:
        """Sends a GET request."""
        return await self._request("GET", url, params=params, **kwargs)

    async def post(self, url: str, json: Optional[Dict[str, Any]] = None, **kwargs: Any) -> httpx.Response:
        """Sends a POST request."""
        return await self._request("POST", url, json=json, **kwargs)

    async def put(self, url: str, json: Optional[Dict[str, Any]] = None, **kwargs: Any) -> httpx.Response:
        """Sends a PUT request."""
        return await self._request("PUT", url, json=json, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Sends a DELETE request."""
        return await self._request("DELETE", url, **kwargs)

    async def close(self):
        """Closes the underlying HTTP client."""
        await self._client.aclose()
