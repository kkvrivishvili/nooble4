# agent_execution_service/tools/tool_registry.py
import logging
from typing import Dict, Optional, List

from .base_tool import BaseTool # Assuming BaseTool is in the same directory or accessible

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registra y gestiona las herramientas disponibles para el agente."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        logger.info("ToolRegistry inicializado.")

    def register_tool(self, tool: BaseTool) -> None:
        """Registra una instancia de herramienta."""
        if not tool or not hasattr(tool, 'name') or not tool.name:
            logger.error("Intento de registrar una herramienta inválida o sin nombre.")
            # Considerar lanzar un error aquí si es crítico
            return
        
        if tool.name in self._tools:
            logger.warning(f"La herramienta '{tool.name}' ya está registrada. Será sobrescrita.")
        
        self._tools[tool.name] = tool
        logger.info(f"Herramienta '{tool.name}' registrada exitosamente.")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Obtiene una herramienta por su nombre."""
        tool = self._tools.get(tool_name)
        if not tool:
            logger.warning(f"Herramienta '{tool_name}' no encontrada en el registro.")
        return tool

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Devuelve un diccionario con todas las herramientas registradas."""
        return self._tools.copy() # Devuelve una copia para evitar modificaciones externas

    def get_tool_names(self) -> List[str]:
        """Devuelve una lista con los nombres de todas las herramientas registradas."""
        return list(self._tools.keys())

    def clear_tools(self) -> None:
        """Limpia todas las herramientas registradas."""
        self._tools.clear()
        logger.info("Todas las herramientas han sido eliminadas del registro.")

# Ejemplo de uso (opcional, para pruebas)
if __name__ == '__main__':
    # Crear una clase BaseTool mock para probar
    class MockTool(BaseTool):
        def __init__(self, name: str, description: str):
            super().__init__(name, description)

        async def execute(self, **kwargs) -> str:
            return f"MockTool {self.name} ejecutada con {kwargs}"
        
        def get_openapi_schema(self) -> Dict[str, Any]:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string", "description": "Un parámetro de ejemplo"}
                    },
                    "required": ["param1"]
                }
            }

    registry = ToolRegistry()
    tool1 = MockTool(name="mock_tool_1", description="Una herramienta de prueba 1")
    tool2 = MockTool(name="mock_tool_2", description="Una herramienta de prueba 2")

    registry.register_tool(tool1)
    registry.register_tool(tool2)

    print("Herramientas registradas:", registry.get_tool_names())

    retrieved_tool = registry.get_tool("mock_tool_1")
    if retrieved_tool:
        print(f"Herramienta recuperada: {retrieved_tool.name}, Descripción: {retrieved_tool.description}")
        print(f"Schema de la herramienta: {retrieved_tool.get_openapi_schema()}")
    
    registry.clear_tools()
    print("Herramientas después de limpiar:", registry.get_tool_names())
