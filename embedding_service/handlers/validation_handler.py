"""
Handler para validación de textos y configuraciones.

Valida que los textos cumplan con los requisitos antes
de generar embeddings.
"""

import logging
from typing import List, Dict, Any, Optional

from common.handlers import BaseHandler


class ValidationHandler(BaseHandler):
    """
    Handler para validar textos antes de generar embeddings.
    
    Verifica formatos y disponibilidad de modelos.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler de validación.
        
        Args:
            app_settings: EmbeddingServiceSettings
            direct_redis_conn: Conexión Redis opcional
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Configurar límites básicos
        self.max_text_length = app_settings.default_max_text_length
        self.max_batch_size = app_settings.default_batch_size
        self.valid_models = list(app_settings.default_models_by_provider.values())
        
        self._logger.info("ValidationHandler inicializado")
    
    async def validate_texts(
        self,
        texts: List[str],
        model: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Valida una lista de textos para procesamiento.
        
        Args:
            texts: Textos a validar
            model: Modelo a usar
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
        
        if len(texts) > self.max_batch_size:
            validation_result["is_valid"] = False
            validation_result["can_process"] = False
            validation_result["messages"].append(
                f"Demasiados textos: {len(texts)} (máximo: {self.max_batch_size})"
            )
            return validation_result
        
        # Validar longitud de textos
        texts_too_long = []
        empty_texts = []
        total_chars = 0
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                empty_texts.append(i)
            elif len(text) > self.max_text_length:
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
                f"(máximo {self.max_text_length} caracteres)"
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