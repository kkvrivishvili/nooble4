"""
Conversation Service - Servicio de gestión de conversaciones.

Este servicio maneja la persistencia y gestión de conversaciones
y la interacción con otros servicios como el Query Service.
"""

__version__ = "1.0.0"

# Importaciones desde los submódulos
from .config import ConversationSettings, get_settings
from .handlers import ConversationHandler
from .models import Action, Conversation
from .routes import crm_router, health_router
from .services import ConversationService, MemoryManager, PersistenceManager
from .workers import ConversationWorker, MigrationWorker

# Definir exportaciones públicas
__all__ = [
    # Configuración
    "ConversationSettings",
    "get_settings",
    
    # Handlers
    "ConversationHandler",
    
    # Modelos
    "Action",
    "Conversation",
    
    # Rutas
    "crm_router",
    "health_router",
    
    # Servicios
    "ConversationService",
    "MemoryManager",
    "PersistenceManager",
    
    # Workers
    "ConversationWorker",
    "MigrationWorker"
]