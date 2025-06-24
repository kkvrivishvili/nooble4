"""
Modelos específicos del Query Service que no están en common.

Nota: SearchResult ha sido movido a vector_search_result.py para 
prevenir imports circulares con VectorClient.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

# Espacio para futuros modelos específicos del Query Service...