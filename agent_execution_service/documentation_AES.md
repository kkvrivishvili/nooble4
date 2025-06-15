# Agent Execution Service Documentation

## 1. Objective and Function of the Service

The Agent Execution Service (AES) is a core component of the Nooble4 platform, designed to orchestrate and manage the lifecycle of AI agent executions. Its primary responsibilities include:

*   **Receiving Execution Requests:** AES listens for `DomainAction` messages (typically `execution.agent_run`) on Redis queues, which trigger the execution of a specified agent.
*   **Context Management:** It resolves and manages the `ExecutionContext`, which includes tenant information, session details, user data, and agent configurations.
*   **Configuration Retrieval:** It fetches agent configurations from the Agent Management Service, utilizing a caching mechanism (Redis) to optimize performance. This includes agent-specific settings, tool access, and model parameters.
*   **Conversation History Management:** It interacts with the Conversation Service to retrieve and save conversation history, also employing caching to reduce latency.
*   **Permission Validation:** Before execution, AES validates if the agent run is permissible based on tenant tier, agent status, and other configured rules.
*   **Orchestrating Agent Logic:** While the core agent execution logic (the actual "thinking" part of an agent) is **currently not implemented** within `AgentExecutor`, AES is structured to call this component. It prepares execution parameters based on tier limits (e.g., max iterations, timeouts).
*   **Inter-Service Communication (Pseudo-Synchronous & Asynchronous):**
    *   It makes pseudo-synchronous calls to other services (Agent Management, Conversation, Embedding, Query) via Redis queues to gather necessary data for an agent's operation. These calls use a `correlation_id` and a dedicated callback queue for the response.
    *   It handles asynchronous callbacks from services like Embedding and Query for operations that don't require immediate blocking (e.g., when an agent requests an embedding or a RAG query during its run).
*   **Callback Handling:** Upon completion (or failure/timeout) of an agent execution, AES sends a callback `DomainAction` (typically `execution.callback`) to the originating service (e.g., Agent Orchestrator Service) via a specified Redis queue.
*   **Metric Tracking:** It tracks various execution metrics (e.g., total executions, status counts, execution times) using Redis.

Essentially, AES acts as the central nervous system for running agents, ensuring they have the necessary data and context, adhere to platform rules, and that their results are communicated back appropriately.

## 2. Communications with Other Services

AES communicates extensively with other Nooble4 services, primarily using Redis queues and a `DomainAction`-based messaging pattern. The communication can be categorized as follows:

**Outgoing Communications (AES initiates):**

*   **Agent Management Service (AMS):**
    *   **Action:** `management.get_agent_config` (via `AgentManagementClient`)
    *   **Purpose:** To fetch the configuration details of a specific agent.
    *   **Pattern:** Pseudo-synchronous (AES sends request and waits for response on a temporary callback queue).
*   **Conversation Service (CS):**
    *   **Action:** `conversation.get_history` (via `ConversationServiceClient`)
    *   **Purpose:** To retrieve the historical messages for a given session.
    *   **Pattern:** Pseudo-synchronous.
    *   **Action:** `conversation.save_message` (via `ConversationServiceClient`)
    *   **Purpose:** To save user and assistant messages to the conversation history.
    *   **Pattern:** Can be pseudo-synchronous or fire-and-forget depending on tier configuration (`wait_for_persistence`).
*   **Embedding Service (ES):**
    *   **Action:** `embedding.request` (via `EmbeddingClient`)
    *   **Purpose:** To request text embeddings (e.g., if an agent tool needs to embed content).
    *   **Pattern:** Asynchronous (AES sends request and expects a callback via `embedding.callback`).
*   **Query Service (QS):**
    *   **Action:** `query.request` (via `QueryClient`)
    *   **Purpose:** To perform RAG queries or document searches.
    *   **Pattern:** Asynchronous (AES sends request and expects a callback via `query.callback`).
*   **Agent Orchestrator Service (AOS) or other client-specified callback queue:**
    *   **Action:** `execution.callback` (via `ExecutionCallbackHandler`)
    *   **Purpose:** To send the final result (success, failure, error) of an agent execution back to the service that initiated it.
    *   **Pattern:** Asynchronous (fire-and-forget).

**Incoming Communications (AES receives):**

*   **From Agent Orchestrator Service (or any client capable of sending DomainActions):**
    *   **Action:** `execution.agent_run`
    *   **Purpose:** The primary trigger to start an agent execution.
    *   **Handled by:** `ExecutionWorker` -> `AgentExecutionHandler`.
    *   **Action:** `execution.management.get_agent_config`, `execution.conversation.get_history`, `execution.conversation.get_context`
    *   **Purpose:** These are requests for AES to act as a proxy and fetch data from AMS or CS respectively, then return it to the original requester's callback queue.
    *   **Pattern:** Pseudo-synchronous from the perspective of the original requester; AES handles the downstream pseudo-sync call.
*   **From Embedding Service:**
    *   **Action:** `embedding.callback`
    *   **Purpose:** Response to an `embedding.request` initiated by AES.
    *   **Handled by:** `ExecutionWorker` -> `EmbeddingCallbackHandler`.
*   **From Query Service:**
    *   **Action:** `query.callback`
    *   **Purpose:** Response to a `query.request` initiated by AES.
    *   **Handled by:** `ExecutionWorker` -> `QueryCallbackHandler`.

## 3. Detailed Description of File Functions

Below is a description of the key files and their roles within the Agent Execution Service:

*   **`main.py`**: 
    *   Sets up the FastAPI application.
    *   Initializes and starts the `ExecutionWorker` during the application lifecycle (`startup` event).
    *   Manages Redis client connections and the `DomainQueueManager`.
    *   Defines basic health check endpoints (`/health`).

*   **`README.md`**: 
    *   Provides an overview of the service, its purpose, architecture, communication patterns, and main workflows. Includes details on `DomainAction` payloads.

*   **`requirements.txt`**: 
    *   Lists all Python dependencies for the service (e.g., `fastapi`, `redis`, `pydantic`).

*   **`__init__.py` (root)**: 
    *   Defines the service version (`__version__`).

*   **`workers/`**
    *   **`execution_worker.py` (`ExecutionWorker` class):**
        *   The main worker class, inheriting from `BaseWorker` (common library).
        *   Listens to Redis queues for incoming `DomainAction` messages.
        *   The `_handle_action` method is the core dispatcher, routing actions to appropriate handlers based on `action_type`.
        *   Manages the lifecycle of action processing, including calling `AgentExecutionHandler` for `execution.agent_run`, and specific callback handlers (`EmbeddingCallbackHandler`, `QueryCallbackHandler`) for incoming results from other services.
        *   Handles sending pseudo-synchronous responses back to client-specified callback queues for actions like `execution.management.get_agent_config`.
        *   Orchestrates sending the final `execution.callback` via `ExecutionCallbackHandler` after an agent run completes.
    *   **`__init__.py`**: Exports `ExecutionWorker`.

*   **`clients/`** (Contain Pydantic models for `DomainAction` payloads and client logic for pseudo-synchronous communication over Redis)
    *   **`agent_management_client.py` (`AgentManagementClient`):** Client to request agent configurations from AMS.
    *   **`conversation_client.py` (`ConversationServiceClient`):** Client to get/save conversation history from/to CS.
    *   **`embedding_client.py` (`EmbeddingClient`):** Client to request embeddings from ES.
    *   **`query_client.py` (`QueryClient`):** Client to send RAG/search queries to QS.
    *   **`__init__.py`**: Exports all client classes.

*   **`handlers/`**
    *   **`agent_execution_handler.py` (`AgentExecutionHandler`):** 
        *   Orchestrates the entire agent execution flow when an `execution.agent_run` action is received.
        *   Uses `ExecutionContextHandler` to manage context, agent config, and conversation history.
        *   Calls `AgentExecutor` to (theoretically) run the agent logic.
        *   Saves conversation messages and tracks execution metrics.
    *   **`context_handler.py` (`ExecutionContextHandler`):** 
        *   Manages `ExecutionContext` creation and resolution.
        *   Handles caching (Redis) for agent configurations and conversation history, with tier-specific TTLs and limits.
        *   Provides methods to get agent config, conversation history, and save messages, interacting with respective clients.
        *   Validates execution permissions.
    *   **`embedding_callback_handler.py` (`EmbeddingCallbackHandler`):** 
        *   Processes `embedding.callback` actions received from the Embedding Service.
        *   Stores results and uses `asyncio.Event` to notify waiting tasks within AES.
    *   **`query_callback_handler.py` (`QueryCallbackHandler`):** 
        *   Processes `query.callback` actions received from the Query Service.
        *   Similar to `EmbeddingCallbackHandler`, stores results and uses `asyncio.Event`.
    *   **`execution_callback_handler.py` (`ExecutionCallbackHandler`):** 
        *   Responsible for sending the final `execution.callback` (success or error) to the original requester's callback queue after an agent execution is finished.
    *   **`handlers_domain_action.py` (`ExecutionHandler`):** 
        *   Contains an `ExecutionHandler` with a `handle_agent_run` method. This appears to be a simplified or potentially legacy way to trigger agent execution, bypassing some of an `AgentExecutionHandler`'s more comprehensive orchestration. Its current role and necessity in the main flow are unclear and might represent dead/redundant code if `AgentExecutionHandler` is the primary path.
    *   **`__init__.py`**: Exports all handler classes.

*   **`services/`**
    *   **`agent_executor.py` (`AgentExecutor`):**
        *   This class is **intended** to contain the core logic for actually executing an agent (e.g., interacting with an LLM, using tools).
        *   Currently, its `execute_agent` method **raises a `NotImplementedError`**, indicating this core functionality is a placeholder and not yet implemented.
        *   It includes a `_prepare_execution_params` method to determine execution parameters (iterations, timeout, tools) based on tenant tier and agent configuration.
    *   **`__init__.py`**: Exports `AgentExecutor`.

*   **`models/`**
    *   **`actions_model.py`**: Defines Pydantic models for various `DomainAction` types used by AES, including:
        *   `AgentExecutionAction`: For triggering an agent run.
        *   `ExecutionCallbackAction`: For sending execution results back.
        *   Actions for requesting data from other services (e.g., `EmbeddingRequestAction`, `QueryRequestAction`, `ConversationGetHistoryAction`).
        *   Actions received by AES that trigger pseudo-sync calls (e.g., `ExecutionGetAgentConfigAction`).
    *   **`execution_model.py`**: Defines Pydantic models related to the execution lifecycle:
        *   `ExecutionStatus` (Enum: PENDING, RUNNING, COMPLETED, etc.).
        *   `ExecutionRequest` (Likely for HTTP API, though primary interaction is via Redis).
        *   `ExecutionResult` (Detailed structure for the outcome of an execution).
    *   **`__init__.py`**: Exports all models.

*   **`config/`**
    *   **`settings.py` (`ExecutionSettings` class):** 
        *   Defines service-specific configurations using Pydantic, loaded via `get_settings()`.
        *   Includes URLs for other services, default parameters, cache TTLs, and crucially, `tier_limits` which dictate behavior and resource allocation based on tenant subscription level.
    *   **`constants.py`**: 
        *   Defines various static values used across the service, such as default model names, LLM provider identifiers, tier-based limits (which seem to overlap somewhat with `settings.py` but might be defaults or for different contexts), and API endpoint paths.
    *   **`__init__.py`**: Exports `ExecutionSettings` and `get_settings`.

## 4. Communication Mechanisms and Patterns

AES employs several communication mechanisms and patterns:

1.  **Redis as a Message Broker (Primary):**
    *   **`DomainAction` Pattern:** All inter-service communication via Redis uses standardized `DomainAction` Pydantic models. Each action has a `action_type`, `tenant_id`, `task_id`, `correlation_id`, `payload`, and `callback_queue_name` (for responses).
    *   **Tier-Based Queues:** The `DomainQueueManager` ensures that actions are enqueued and dequeued from Redis lists (queues) that are specific to tenant tiers (e.g., `execution_service:free:default`, `execution_service:enterprise:high_priority`). This allows for differentiated processing based on service levels.
    *   **Worker Pattern:** The `ExecutionWorker` continuously polls these Redis queues for new actions to process.

2.  **Pseudo-Synchronous Communication (for Client Calls):**
    *   When AES needs data from another service (e.g., agent config from AMS), its clients (`AgentManagementClient`, `ConversationServiceClient`, etc.) implement a pseudo-synchronous pattern:
        1.  AES generates a unique `correlation_id`.
        2.  It specifies a unique, temporary callback queue name (often including the `correlation_id`) in the `DomainAction` it sends to the target service.
        3.  AES then performs a blocking listen (`BLPOP`) on this temporary response queue with a timeout.
        4.  The target service processes the request and sends its `DomainActionResponse` back to the specified temporary queue.
        5.  AES receives the response and continues processing.
    *   This pattern is also used by AES itself when it receives actions like `execution.management.get_agent_config`. AES makes the downstream call and sends the response back to the original requester's callback queue.

3.  **Asynchronous Callbacks (for Service Responses to AES):**
    *   For operations like embedding generation or RAG queries, where AES initiates a request (`embedding.request`, `query.request`) but doesn't need to block its main thread, it relies on asynchronous callbacks.
    *   The Embedding Service or Query Service will send a `DomainAction` (e.g., `embedding.callback`, `query.callback`) back to a standard AES queue (e.g., `agent_execution_service:{tier}:callbacks`).
    *   The `ExecutionWorker` picks up these callback actions, and dedicated handlers (`EmbeddingCallbackHandler`, `QueryCallbackHandler`) process them. These handlers often use `asyncio.Event` objects to signal the completion of the asynchronous operation to any internal task within AES that might be waiting for that specific result (identified by `task_id` or `correlation_id`).

4.  **Asynchronous Fire-and-Forget (for Final Execution Callbacks):**
    *   When AES completes an agent execution, the `ExecutionCallbackHandler` sends an `execution.callback` `DomainAction` to the queue specified in the original `execution.agent_run` action. This is typically a fire-and-forget operation from AES's perspective.

5.  **Caching (Redis):**
    *   AES extensively uses Redis for caching to improve performance and reduce load on downstream services:
        *   **Agent Configurations:** Cached by `ExecutionContextHandler` with keys like `agent_config:{tenant_id}:{agent_id}` and potentially session-specific keys. TTLs are tier-dependent.
        *   **Conversation History:** Cached by `ExecutionContextHandler` with keys like `conversation_history:{tenant_id}:{session_id}`. TTLs and cache size limits are tier-dependent.

6.  **HTTP (Potentially for API, but not primary for inter-service):**
    *   FastAPI is used, implying HTTP endpoints exist (e.g., `/health`). While `ExecutionRequest` model suggests an HTTP endpoint for execution, the primary inter-service flow described and implemented revolves around Redis queues.

## 5. Identification of Inconsistencies (Current or Past)

Based on the codebase review:

1.  **Core Logic Not Implemented:** The most significant point is that the central purpose of the service – executing agent logic – is not implemented. `AgentExecutor.execute_agent()` raises `NotImplementedError`. This means the service can orchestrate, manage context, and communicate, but cannot perform actual agent tasks.
2.  **Potential Redundancy in `handlers_domain_action.py`:** The `ExecutionHandler` in this file seems to offer a simplified path for `handle_agent_run`. Its relationship with the more comprehensive `AgentExecutionHandler` is unclear. If `AgentExecutionHandler` is the standard, then `handlers_domain_action.py` might contain redundant or dead code.
3.  **Overlap in Tier Limit Definitions:** Constants related to tier limits (e.g., `MAX_TOOLS_BY_TIER`, `MAX_TOKENS_BY_TIER`) are defined in `config/constants.py` and also within the `tier_limits` dictionary in `config/settings.py`. While `settings.py` is likely the source of truth at runtime, this duplication could lead to confusion or inconsistencies if not managed carefully.
4.  **`python-multipart` Dependency:** The `python-multipart` dependency is listed, but its direct use case within AES is not immediately apparent from the reviewed files, which focus on Redis-based communication. This might be a remnant or for a minor, unobserved feature.
5.  **`asyncio` in `requirements.txt`:** `asyncio` is part of the Python standard library. Explicitly listing it is unusual and generally unnecessary unless pinning to a very specific patch version for critical reasons, which is not common practice for `asyncio` itself.
6.  **Commented out `QueryCallbackAction` Model:** In `query_callback_handler.py`, there's a commented-out import for a specific `QueryCallbackAction` model, with the code currently using the generic `DomainAction`. This suggests a potential past or future intent to use a more specific model for type validation for these callbacks.

## 6. Detection of Duplicated or Dead Code

*   **`handlers/handlers_domain_action.py` (`ExecutionHandler`):** As mentioned above, this file is a strong candidate for containing duplicated or dead code if the primary execution path is through `agent_execution_service.handlers.agent_execution_handler.AgentExecutionHandler`. The `ExecutionHandler` here seems to bypass much of the setup and context management that `AgentExecutionHandler` provides.
*   **Disabled `handle_session_closed` in `AgentExecutionHandler`:** The `handle_session_closed` method in `AgentExecutionHandler` is explicitly disabled but kept for compatibility. While not strictly dead (as it's callable), its functionality is intentionally nullified.
*   **Placeholder Agent Logic in `AgentExecutor`:** The entire `execute_agent` method in `AgentExecutor` is effectively dead code in terms of actual agent execution, as it only raises `NotImplementedError`.

This concludes the detailed analysis for the Agent Execution Service documentation.
