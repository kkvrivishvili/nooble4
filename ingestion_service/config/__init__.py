"""
Configuración del servicio de ingestión.

Expone la configuración centralizada del servicio.
"""

from ingestion_service.config.settings import IngestionSettings, get_settings

__all__ = ['IngestionSettings', 'get_settings']
