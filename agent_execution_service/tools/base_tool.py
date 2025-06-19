"""
Clase base para herramientas del Agent Execution Service.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class BaseTool(ABC):
    """Clase base abstracta para todas las herramientas."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """
        Ejecuta la herramienta con los argumentos proporcionados.
        
        Returns:
            Resultado de la ejecución (serializable)
        """
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Retorna el schema de la herramienta en formato OpenAI/Groq.
        
        Returns:
            Schema de la función
        """
        pass