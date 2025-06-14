"""
Constantes para el Embedding Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de generación de embeddings. Los valores configurables se gestionan a través de
la clase EmbeddingServiceSettings.

Las definiciones de EmbeddingProviders, EncodingFormats y SUPPORTED_OPENAI_MODELS_INFO
se encuentran ahora en 'refactorizado.common.config.service_settings.embedding.py'
junto con EmbeddingServiceSettings para mantener la cohesión.
"""

# Nombres de colas
# (Los nombres de las colas ahora se construyen dinámicamente en el código
# utilizando los valores de 'domain_name' y/o 'callback_queue_prefix' de EmbeddingServiceSettings)

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    EMBED = "/embed"
    BATCH_EMBED = "/batch-embed"
    ASYNC_EMBED = "/async-embed"
    MODELS = "/models"
    DIMENSIONS = "/dimensions"
    STATUS = "/status/{job_id}"
    METRICS = "/metrics"

# Si alguna otra constante es verdaderamente fija y no configurable,
# y no está directamente ligada a la definición de EmbeddingServiceSettings,
# puede permanecer aquí.
