from functools import lru_cache
from common.config import IngestionServiceSettings


@lru_cache()
def get_settings() -> IngestionServiceSettings:
    """Get cached settings instance"""
    return IngestionServiceSettings()