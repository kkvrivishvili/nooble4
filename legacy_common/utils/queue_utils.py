"""
Queue Utilities - Utilidades auxiliares para manejo de colas.
"""

import re
from typing import Dict, Any, Optional, Tuple


def parse_queue_name(queue_name: str) -> Dict[str, str]:
    """
    Parsea nombre de cola en sus componentes.
    
    Args:
        queue_name: Nombre de cola (ej: "execution:agent-123:professional")
        
    Returns:
        Dict con componentes: domain, context_id, tier
    """
    pattern = r"^([^:]+):([^:]+):([^:]+)$"
    match = re.match(pattern, queue_name)
    
    if not match:
        raise ValueError(f"Formato de cola inválido: {queue_name}")
    
    return {
        "domain": match.group(1),
        "context_id": match.group(2),
        "tier": match.group(3)
    }


def extract_context_info(context_id: str) -> Tuple[str, str]:
    """
    Extrae tipo y ID desde context_id.
    
    Args:
        context_id: ID de contexto (ej: "agent-123", "workflow-456")
        
    Returns:
        Tupla (tipo, id)
    """
    if context_id.startswith("agent-"):
        return "agent", context_id[6:]  # Remove "agent-"
    elif context_id.startswith("workflow-"):
        return "workflow", context_id[9:]  # Remove "workflow-"
    elif context_id.startswith("collection-"):
        return "collection", context_id[11:]  # Remove "collection-"
    else:
        return "unknown", context_id


def validate_tier(tier: str) -> bool:
    """Valida que el tier sea válido."""
    valid_tiers = {"free", "advance", "professional", "enterprise"}
    return tier in valid_tiers


def get_tier_priority(tier: str) -> int:
    """
    Obtiene prioridad numérica del tier.
    
    Returns:
        1 = highest priority (enterprise), 4 = lowest (free)
    """
    priorities = {
        "enterprise": 1,
        "professional": 2, 
        "advance": 3,
        "free": 4
    }
    return priorities.get(tier, 999)


def format_queue_pattern(domain: str, tier: Optional[str] = None) -> str:
    """
    Genera patrón de cola para búsquedas.
    
    Args:
        domain: Dominio (execution, embedding, etc.)
        tier: Tier específico o None para todos
        
    Returns:
        Patrón Redis (ej: "execution:*:professional")
    """
    if tier:
        return f"{domain}:*:{tier}"
    else:
        return f"{domain}:*:*"