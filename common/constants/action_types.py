# Centralized definition of DomainAction action_type constants.
# This helps avoid typos and provides a single source of truth for action types.

# Example structure:
# class ServiceNameActionTypes:
#     ENTITY_VERB = "service_name.entity.verb"
#     ANOTHER_ENTITY_ANOTHER_VERB = "service_name.another_entity.another_verb"

# Example for a hypothetical Management Service
class ManagementActionTypes:
    AGENT_CREATE = "management.agent.create"
    AGENT_GET_CONFIG = "management.agent.get_config"
    AGENT_UPDATE_CONFIG = "management.agent.update_config"
    AGENT_DELETE = "management.agent.delete"
    # ... add other management related action types

# Example for a hypothetical Embedding Service
class EmbeddingActionTypes:
    DOCUMENT_PROCESS = "embedding.document.process"
    DOCUMENT_GET_STATUS = "embedding.document.get_status"
    # ... add other embedding related action types

# Example for a hypothetical Query Service
class QueryActionTypes:
    KNOWLEDGE_QUERY = "query.knowledge.execute"
    # ... add other query related action types

# Add more classes for other services as they are developed.

# It's also possible to have a flat structure if preferred, but classes group them nicely:
# ACTION_AGENT_CREATE = "management.agent.create"
# ACTION_DOCUMENT_PROCESS = "embedding.document.process"

# Ensure this file is imported where action types are needed, e.g.:
# from common.constants.action_types import ManagementActionTypes
# action = DomainAction(action_type=ManagementActionTypes.AGENT_CREATE, ...)
