# agent_execution_service/tools/base_tool.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class BaseTool(ABC):
    """Clase base abstracta para todas las herramientas."""

    name: str
    description: str
    args_schema: Optional[type[BaseModel]] = None # Pydantic model for arguments

    def __init__(self, name: str, description: str, args_schema: Optional[type[BaseModel]] = None):
        self.name = name
        self.description = description
        self.args_schema = args_schema

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """
        Ejecuta la lógica de la herramienta.
        Debe ser implementado por las subclases.
        Los argumentos se pasan como kwargs.
        """
        pass

    def get_openapi_schema(self) -> Dict[str, Any]:
        """
        Genera el schema de la función en formato OpenAI / Groq.
        Utiliza el args_schema (Pydantic model) para definir los parámetros.
        """
        if not self.args_schema:
            # Herramienta sin parámetros
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }

        # Pydantic v2 usa model_json_schema(), v1 schema()
        try:
            # For Pydantic v2
            if hasattr(self.args_schema, 'model_json_schema'):
                schema = self.args_schema.model_json_schema()
            # For Pydantic v1
            elif hasattr(self.args_schema, 'schema'):
                schema = self.args_schema.schema()
            else:
                raise AttributeError("args_schema no tiene método model_json_schema() ni schema()")
        except Exception as e:
            # Log error or handle appropriately
            # print(f"Error generating schema for {self.name}: {e}")
            # Fallback to a basic schema if generation fails
            return {
                "name": self.name,
                "description": f"{self.description} (Error al generar schema de parámetros)",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        
        # Limpiar el schema para que coincida con el formato de OpenAI
        # OpenAI espera 'parameters' como el schema del objeto de argumentos.
        # Pydantic schema() devuelve el schema del modelo directamente.
        # No necesitamos el 'title' o 'description' del modelo en el nivel superior de 'parameters'.
        
        parameters_schema = {
            "type": "object",
            "properties": schema.get("properties", {}),
        }
        if "required" in schema:
            parameters_schema["required"] = schema.get("required", [])

        return {
            "name": self.name,
            "description": self.description,
            "parameters": parameters_schema
        }

# Ejemplo de un Pydantic model para los argumentos de una herramienta
class ExampleToolArgs(BaseModel):
    query: str = Field(..., description="La consulta a realizar")
    limit: Optional[int] = Field(10, description="Número máximo de resultados")

# Ejemplo de uso (opcional, para pruebas)
if __name__ == '__main__':
    class MyExampleTool(BaseTool):
        def __init__(self):
            super().__init__(
                name="my_example_tool", 
                description="Una herramienta de ejemplo que toma una consulta y un límite.",
                args_schema=ExampleToolArgs
            )

        async def execute(self, query: str, limit: Optional[int] = 10) -> Dict[str, Any]:
            return {"message": f"Ejecutando {self.name} con query='{query}', limit={limit}"}

    example_tool = MyExampleTool()
    print(f"Nombre: {example_tool.name}")
    print(f"Descripción: {example_tool.description}")
    print("Schema OpenAI:")
    import json
    print(json.dumps(example_tool.get_openapi_schema(), indent=2))

    # Ejemplo de herramienta sin argumentos
    class NoArgsTool(BaseTool):
        def __init__(self):
            super().__init__(
                name="no_args_tool",
                description="Una herramienta que no toma argumentos."
            )
        async def execute(self) -> str:
            return f"{self.name} ejecutada."
    
    no_args_tool = NoArgsTool()
    print(f"\nNombre: {no_args_tool.name}")
    print(f"Descripción: {no_args_tool.description}")
    print("Schema OpenAI (sin args):")
    print(json.dumps(no_args_tool.get_openapi_schema(), indent=2))
