"""
Utilidades de logging comunes.
"""

import logging
import sys
from typing import Optional

def init_logging(log_level: str = "INFO", service_name: Optional[str] = None):
    """Inicializa logging estandarizado."""
    
    # Configurar formato
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if service_name:
        log_format = f"%(asctime)s - {service_name} - %(name)s - %(levelname)s - %(message)s"
    
    # Configurar handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format))
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers = [handler]
    
    # Silenciar loggers muy verbosos de librerías externas
    logging.getLogger("redis").setLevel(logging.WARNING)
