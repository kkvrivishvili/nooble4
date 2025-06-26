"""
Handler para validación de textos y configuraciones.

Valida que los textos cumplan con los requisitos antes
de generar embeddings.
"""

import logging
from typing import List, Dict, Any, Optional

from common.handlers import BaseHandler
from common.models.config_models import RAGConfig


class ValidationHandler(BaseHandler):
    """
    Handler para validar textos antes de generar embeddings.
    
    Verifica formatos y disponibilidad de modelos.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler de validación.
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Modelos válidos (valores string, no enums)
        self.valid_models = [
            "text-embedding-3-small",
            "text-embedding-3-large", 
            "text-embedding-ada-002"
        ]
        
        self._logger.info("ValidationHandler inicializado")
    
    async def validate_texts(
        self,
        texts: List[str],
        rag_config: Optional[RAGConfig] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Valida una lista de textos para procesamiento.
        
        Args:
            texts: Textos a validar
            rag_config: Configuración RAG para la solicitud (contiene modelo, max_text_length, etc.)
            tenant_id: ID del tenant
            
        Returns:
            Dict con resultado de validación
        """
        validation_result = {
            "is_valid": True,
            "can_process": True,
            "messages": [],
            "warnings": [],
            "estimated_tokens": 0,
            "model_available": True
        }
        
        # Validar cantidad de textos
        if not texts:
            validation_result["is_valid"] = False
            validation_result["can_process"] = False
            validation_result["messages"].append("No se proporcionaron textos")
            return validation_result
        
        # El límite de batch de OpenAI es 2048, HAY QUE REVISAR QUE INGESTION SERVICE NO ENVIA MAS QUE 2048 TEXTOS
        MAX_BATCH_SIZE = 2048
        if len(texts) > MAX_BATCH_SIZE:
            validation_result["is_valid"] = False
            validation_result["can_process"] = False
            validation_result["messages"].append(
                f"Demasiados textos: {len(texts)} (máximo: {MAX_BATCH_SIZE})"
            )
            return validation_result
        
        # Obtener configuración desde rag_config
        max_len = rag_config.max_text_length if rag_config and rag_config.max_text_length is not None else None
        model = rag_config.embedding_model.value if rag_config else None

        # Validar longitud de textos
        texts_too_long = []
        empty_texts = []
        total_chars = 0
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                empty_texts.append(i)
            # Solo validar si max_len está definido en la configuración de la solicitud
            elif max_len is not None and len(text) > max_len:
                texts_too_long.append(i)
            else:
                total_chars += len(text)
        
        if empty_texts:
            validation_result["warnings"].append(
                f"Textos vacíos en posiciones: {empty_texts}"
            )
        
        if texts_too_long:
            validation_result["is_valid"] = False
            validation_result["can_process"] = False
            validation_result["messages"].append(
                f"Textos muy largos en posiciones: {texts_too_long} "
                f"(máximo {max_len} caracteres)"
            )
        
        # Estimar tokens
        validation_result["estimated_tokens"] = max(1, total_chars // 4)
        
        # Validar modelo si se especifica
        if model and model not in self.valid_models:
            validation_result["model_available"] = False
            validation_result["warnings"].append(
                f"Modelo '{model}' no reconocido, se usará el modelo por defecto"
            )
        
        # Log del resultado
        self._logger.debug(
            f"Validación completada: {len(texts)} textos, "
            f"válido={validation_result['is_valid']}, "
            f"tokens estimados={validation_result['estimated_tokens']}",
            extra={"tenant_id": tenant_id}
        )
        
        return validation_result