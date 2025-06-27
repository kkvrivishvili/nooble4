import uuid
from typing import Optional

def generate_deterministic_id(
    tenant_id: str,
    session_id: str,
    agent_id: Optional[str] = None,
    document_id: Optional[str] = None
) -> uuid.UUID:
    """
    Genera un UUID determinístico usando el algoritmo SHA-1 basado en el namespace OID.
    Combina tenant_id, session_id, y opcionalmente agent_id y document_id.
    """
    base_parts = [tenant_id, session_id]
    if agent_id:
        base_parts.append(agent_id)
    if document_id:
        base_parts.append(document_id)
    
    input_str = "|".join(base_parts)
    return uuid.uuid5(uuid.NAMESPACE_OID, input_str)
