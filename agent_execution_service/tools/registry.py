"""
Registro de herramientas disponibles.
"""
import logging
from typing import Dict, Optional, List, Any  
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registra y gestiona las herramientas disponibles."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def register(self, tool: BaseTool) -> None:
        """Registra una herramienta."""
        if not isinstance(tool, BaseTool):
            raise ValueError("La herramienta debe heredar de BaseTool")
            
        self._tools[tool.name] = tool
        self._logger.info(f"Herramienta '{tool.name}' registrada")

    def get(self, name: str) -> Optional[BaseTool]:
        """Obtiene una herramienta por nombre."""
        return self._tools.get(name)

    def get_all(self) -> Dict[str, BaseTool]:
        """Obtiene todas las herramientas registradas."""
        return self._tools.copy()

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Obtiene los schemas de todas las herramientas."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": tool.get_schema()
            })
        return schemas

    def clear(self) -> None:
        """Limpia el registro de herramientas."""
        self._tools.clear()
        self._logger.info("Registro de herramientas limpiado")