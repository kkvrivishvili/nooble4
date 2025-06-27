# Plan de Implementación: Mejoras al Servicio de Ingestión

## 1. Configuración de Embeddings

### 1.1 Revisión de Modelos de Configuración
- **Ubicación propuesta**: `common/models/config_models.py`
- **Análisis**:
  - Evaluar si `RAGConfig` puede ser extendido o si se necesita un nuevo modelo
  - Considerar si los embeddings de ingesta y query deben tener configuraciones separadas
- **Acción**:
  ```python
  class EmbeddingConfig(BaseModel):
      model: str = Field(default="text-embedding-3-small")
      dimensions: int = Field(default=1536)
      batch_size: int = Field(default=32)
  ```

## 2. Refactorización de QdrantHandler a Cliente

### 2.1 Estructura Propuesta
- **Ubicación actual**: `ingestion_service/handlers/qdrant_handler.py`
- **Nueva ubicación**: `ingestion_service/clients/qdrant_client.py`
- **Cambios principales**:
  - Renombrar clase a `QdrantClient`
  - Simplificar interfaz pública
  - Mantener la lógica de conexión con Qdrant

### 2.2 Migración
1. Crear nuevo cliente
2. Actualizar referencias en servicios
3. Eliminar handler antiguo después de la migración

## 3. Mejoras al DocumentProcessor

### 3.1 Robustez
- Añadir manejo de errores detallado
- Validar parámetros de entrada
- Mejorar logs para diagnóstico

### 3.2 Estandarización
- Usar nombres de variables consistentes
- Documentar métodos públicos
- Añadir type hints completos

## 4. Procesamiento por Lotes (Batch Processing)

### 4.1 Implementación Actual
- Procesa documentos uno por uno
- Sin paralelismo
- Llamadas secuenciales a servicios externos

### 4.2 Mejora Propuesta
```python
async def process_batch(self, documents: list[Document]) -> list[ChunkModel]:
    """Procesa múltiples documentos en paralelo."""
    tasks = [self._process_single(doc) for doc in documents]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

## 5. Optimización de Redis

### 5.1 Estado Actual
- Operaciones individuales por chunk
- Sin pipeline
- Posible cuello de botella

### 5.2 Mejora Propuesta
```python
async def save_chunks_batch(self, chunks: list[ChunkModel]):
    """Guarda múltiples chunks en una sola operación Redis."""
    async with self.redis.pipeline() as pipe:
        for chunk in chunks:
            pipe.set(f"chunk:{chunk.id}", chunk.json())
        await pipe.execute()
```

## 6. Seguridad y Validación

### 6.1 Validación de Entrada
- Validar formatos de IDs
- Verificar permisos a nivel de endpoint
- Sanitizar contenido

### 6.2 Integración con Kong
- Confiar en headers de autenticación
- Validar `X-Tenant-ID` y `X-User-ID`
- No duplicar lógica de autenticación

## Cronograma de Implementación

### Día 1: Configuración y Estructura
- [ ] Revisar y actualizar modelos de configuración
- [ ] Crear estructura de cliente Qdrant

### Día 2: Refactorización
- [ ] Implementar QdrantClient
- [ ] Actualizar servicios para usar el nuevo cliente

### Día 3: Mejoras de Procesamiento
- [ ] Implementar procesamiento por lotes
- [ ] Optimizar operaciones Redis

### Día 4: Pruebas
- [ ] Pruebas unitarias
- [ ] Pruebas de integración
- [ ] Pruebas de carga

### Día 5: Despliegue
- [ ] Desplegar en staging
- [ ] Monitorear rendimiento
- [ ] Desplegar en producción

## Notas Importantes
- Las métricas se implementarán en una fase posterior
- La validación de seguridad se delega a Kong
- Mantener compatibilidad con versiones anteriores durante la migración
