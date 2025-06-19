"""
Utilidades para formatear datos.
"""
from typing import List, Dict, Any


def format_tool_result(tool_name: str, result: Any) -> str:
    """Formatea el resultado de una herramienta para el LLM."""
    if isinstance(result, dict):
        if "error" in result:
            return f"Error ejecutando {tool_name}: {result['error']}"
        return f"Resultado de {tool_name}: {result}"
    return f"Resultado de {tool_name}: {str(result)}"


def format_chunks_for_llm(chunks: List[Dict[str, Any]]) -> str:
    """Formatea chunks de conocimiento para el LLM."""
    if not chunks:
        return "No se encontró información relevante."
    
    formatted = "Información relevante encontrada:\n\n"
    for i, chunk in enumerate(chunks, 1):
        content = chunk.get("content", "")
        source = chunk.get("source", "desconocido")
        score = chunk.get("score", 0.0)
        
        formatted += f"[{i}] (Fuente: {source}, Relevancia: {score:.2f})\n{content}\n\n"
    
    return formatted