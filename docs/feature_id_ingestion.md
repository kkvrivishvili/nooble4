# Feature: Gestión de IDs Determinísticos y Contexto de Agente

## 1. Resumen Ejecutivo

Se ha implementado un sistema robusto para la generación y propagación de IDs determinísticos y el manejo del contexto de agente (`agent_id`) a lo largo de todo el `Ingestion Service`. El objetivo es garantizar la trazabilidad completa, la idempotencia de las operaciones y el aislamiento seguro de los datos por agente y tenant.

### Principios de Diseño Clave:
- **IDs Determinísticos**: `task_id` y `trace_id` se generan usando `UUIDv5` a partir del contexto (`tenant_id`, `session_id`, `agent_id`, `document_id`), asegurando que la misma solicitud siempre produzca los mismos IDs.
- **Generación en el Origen (Edge)**: Los IDs se generan en la capa de API (`router.py`) al crear el `DomainAction`, no en los servicios consumidores. Esto garantiza que el contexto de trazabilidad se establece desde el inicio y se propaga de manera consistente.
- **Contexto Explícito**: Toda la información de contexto (`agent_id`, `trace_id`, `rag_config`) viaja en campos explícitos del `DomainAction`, no mezclada en el `payload` de datos.
- **Componentes Agnósticos**: Los handlers de bajo nivel (como `QdrantHandler`) son agnósticos al contexto de negocio. Simplemente persisten los datos y la metadata que reciben, haciendo el sistema más modular y mantenible.

---

## 2. Flujo de Datos y Componentes

### Flujo de Ingestión

```mermaid
graph TD
    A[API Endpoint] -->|Request| B(1. API Router);
    B -->|Genera IDs, Crea DomainAction| C(2. Kafka);
    C --> D(3. Ingestion Service);
    D -->|Procesa Documento| E(4. Document Processor);
    E -->|Chunks con Metadata| D;
    D -->|Envía a Embeber| F(5. Embedding Service);
    F -->|Respuesta con Embeddings| D;
    D -->|Almacena Chunks| G(6. Qdrant Handler);
    G --> H[Qdrant DB];

    subgraph "Contexto de Trazabilidad (en DomainAction)"
        direction LR
        id1(task_id)
        id2(trace_id)
        id3(agent_id)
        id4(tenant_id)
        id5(session_id)
    end
|------|---------------|-----|-----------|
| **Agente** | `agent_id` | Datos específicos de agente | tenant_id, agent_id, document_id |
| **Documento** | `document_id` | Documentos independientes | tenant_id, document_id |

## Implementación en Qdrant Handler

### 1. Store Chunks con agent_id
```python
async def store_chunks(
    self,
    chunks: List[Chunk],
    agent_id: Optional[str] = None
) -> Dict[str, int]:
    points = []
    for chunk in chunks:
        metadata = {
            "tenant_id": chunk.tenant_id,
            "document_id": chunk.document_id,
            "chunk_id": str(chunk.id)
        }
        if agent_id:
            metadata["agent_id"] = agent_id  # Añadir agent_id si existe
        
        points.append(Point(
            id=str(uuid.uuid4()),
            vector=chunk.embedding,
            payload=metadata
        ))
    # Operación upsert...
```

### 2. Búsqueda con Filtro de Agente
```python
async def search(
    self,
    query_embedding: List[float],
    agent_id: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    
    filters = Filter()
    if agent_id:
        filters.must.append(
            FieldCondition(key="agent_id", match=MatchValue(value=agent_id))
    
    # Realizar búsqueda vectorial con filtro
    results = self.client.search(
        collection_name=self.collection_name,
        query_vector=query_embedding,
        query_filter=filters,
        limit=limit
    )
    # Procesar resultados...
```

### 3. Delete Document con agent_id
```python
async def delete_document(
    self, 
    tenant_id: str,
    agent_id: Optional[str] = None,
    document_id: str
) -> int:
    
    filters = [
        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
        FieldCondition(key="document_id", match=MatchValue(value=document_id))
    ]
    if agent_id:
        filters.append(FieldCondition(
            key="agent_id", match=MatchValue(value=agent_id)
        ))
    
    # Ejecutar delete con filtros combinados
    return self.client.delete(
        collection_name=self.collection_name,
        points_selector=Filter(must=filters)
    )
```

## Pruebas

### Matriz de Validación
| Escenario | Entrada | Resultado Esperado |
|-----------|---------|--------------------|
| Ingestión con agent_id | agent_id="agent_123" | Chunks almacenados con agent_id en metadata |
| Búsqueda con agent_id | agent_id="agent_123" | Solo chunks del agente 123 |
| Ingestión sin agent_id | agent_id=None | Chunks almacenados sin agent_id |
| Búsqueda sin agent_id | agent_id=None | Todos los chunks visibles |

## Beneficios
1. **Personalización por agente**: Modelos específicos
2. **Seguridad mejorada**: Aislamiento de datos
3. **Gestión granular**: Operaciones por agente
4. **Traza completa**: Ciclo de vida con un ID

## Plan de Implementación
1. Implementar `id_generation.py`
2. Refactorizar `QdrantHandler`
3. Actualizar `IngestionService` para pasar agent_id
4. Implementar pruebas unitarias e integración
5. Actualizar documentación

## Timeline
| Fase | Duración | Entregables |
|------|----------|-------------|
| Core | 1 día | Módulos ID + QdrantHandler |
| Pruebas Unitarias | 0.5 días | Cobertura >90% |
| Pruebas Integración | 1 día | Flujos con/sin agent_id |
| Refinamiento | 0.5 días | Optimización final |
