"""
Clientes para comunicación entre servicios.
"""

from .execution_client import ExecutionClient
from .management_client import ManagementClient

__all__ = [
    "ExecutionClient",
    "ManagementClient",
]