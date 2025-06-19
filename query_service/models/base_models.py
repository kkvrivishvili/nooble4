"""
Base constants for the Query Service interface.
Specific Pydantic models are now defined in common.models.chat_models
or other specific model files if not covered by common models.
"""

# --- Action Type Constants for Query Service --- #
ACTION_QUERY_SIMPLE = "query.simple"      # For simple chat with automatic RAG
ACTION_QUERY_ADVANCE = "query.advance"    # For advanced chat with tools support
ACTION_QUERY_RAG = "query.rag"           # For knowledge tool search