"""Configuración del Agent Management Service.

Expone las configuraciones y utilidades para el acceso a settings.
"""

from agent_management_service.config.settings import get_settings, AgentManagementSettings

__all__ = ['get_settings', 'AgentManagementSettings']
