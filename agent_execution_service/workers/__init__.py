"""
Workers para Agent Execution Service.

Implementa workers basados en Domain Actions para procesamiento asíncrono.
"""

from .domain_execution_worker import DomainExecutionWorker as ExecutionWorker

__all__ = ['ExecutionWorker']
