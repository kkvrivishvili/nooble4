"""
Parsers para respuestas de LLM y formato ReAct.
"""
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ReactParser:
    """Parser para respuestas en formato ReAct."""

    def parse_react_response(self, content: str) -> Dict[str, Any]:
        """
        Parsea una respuesta del LLM en formato ReAct.
        
        Formato esperado:
        Thought: <pensamiento>
        Action: <acción>
        Action Input: <input_json>
        """
        result = {}
        
        try:
            # Extraer pensamiento
            thought_match = re.search(
                r"Thought:\s*(.*?)(?=\n(?:Action|Final Answer|$))", 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            if thought_match:
                result["thought"] = thought_match.group(1).strip()

            # Extraer acción
            action_match = re.search(
                r"Action:\s*(.*?)(?=\n|$)", 
                content, 
                re.IGNORECASE
            )
            if action_match:
                result["action"] = action_match.group(1).strip()

            # Extraer input de acción
            action_input_match = re.search(
                r"Action Input:\s*(.*?)(?=\n(?:Observation|Thought|$))", 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            if action_input_match:
                input_str = action_input_match.group(1).strip()
                try:
                    # Intentar parsear como JSON
                    result["action_input"] = json.loads(input_str)
                except json.JSONDecodeError:
                    # Si no es JSON válido, usar como string
                    result["action_input"] = {"input": input_str}

        except Exception as e:
            logger.error(f"Error parseando respuesta ReAct: {e}")
            result["thought"] = content  # Fallback

        return result

    def extract_final_answer(self, content: str) -> Optional[str]:
        """Extrae la respuesta final de una respuesta ReAct."""
        match = re.search(
            r"Final Answer:\s*(.*)", 
            content, 
            re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return None