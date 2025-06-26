import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import hashlib

from llama_index.core import SimpleDirectoryReader, Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
import requests

from common.handlers import BaseHandler
from common.config import CommonAppSettings
from ..models import DocumentIngestionRequest, ChunkModel, DocumentType


class DocumentProcessorHandler(BaseHandler):
    """Handler for processing documents using LlamaIndex"""
    
    def __init__(self, app_settings: CommonAppSettings):
        super().__init__(app_settings)
        self.chunk_parser = SentenceSplitter()
        
    async def process_document(
        self, 
        request: DocumentIngestionRequest,
        document_id: str,
        agent_id: str
    ) -> List[ChunkModel]:
        """Process document and return chunks"""
        try:
            # Load document based on type
            document = await self._load_document(request)
            
            # Configure chunk parser
            self.chunk_parser = SentenceSplitter(
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                include_metadata=True,
                include_prev_next_rel=True
            )
            
            # Parse into nodes
            nodes = self.chunk_parser.get_nodes_from_documents([document])
            
            # Convert nodes to ChunkModel
            chunks = []
            for idx, node in enumerate(nodes):
                chunk = ChunkModel(
                    document_id=document_id,
                    tenant_id=request.tenant_id,
                    agent_id=agent_id,
                    collection_id=request.collection_id,
                    text=node.get_content(),
                    chunk_index=idx,
                    metadata={
                        **request.metadata,
                        "document_name": request.document_name,
                        "document_type": request.document_type.value,
                        "agent_id": agent_id,
                        "start_char_idx": node.start_char_idx,
                        "end_char_idx": node.end_char_idx,
                        "relationships": self._extract_relationships(node)
                    }
                )
                chunks.append(chunk)
                
            self._logger.info(f"Processed document {document_id} into {len(chunks)} chunks for agent {agent_id}")
            return chunks
            
        except Exception as e:
            self._logger.error(f"Error processing document: {e}")
            raise
    
    async def _load_document(self, request: DocumentIngestionRequest) -> Document:
        """Load document from various sources"""
        content = None
        metadata = {"source": request.document_type.value}
        
        if request.file_path:
            # Load from file
            file_path = Path(request.file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {request.file_path}")
                
            if request.document_type in [DocumentType.PDF, DocumentType.DOCX]:
                # Use SimpleDirectoryReader for complex formats
                reader = SimpleDirectoryReader(input_files=[str(file_path)])
                docs = reader.load_data()
                if docs:
                    content = "\n\n".join([doc.text for doc in docs])
            else:
                # Plain text formats
                content = file_path.read_text(encoding='utf-8')
                
        elif request.url:
            # Fetch from URL
            response = requests.get(str(request.url), timeout=30)
            response.raise_for_status()
            content = response.text
            metadata["url"] = str(request.url)
            
        elif request.content:
            # Direct content
            content = request.content
            
        else:
            raise ValueError("No content source provided")
        
        # Create document
        document = Document(
            text=content,
            metadata=metadata,
            id_=self._generate_doc_hash(content)
        )
        
        return document
    
    def _generate_doc_hash(self, content: str) -> str:
        """Generate unique hash for document content"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _extract_relationships(self, node: TextNode) -> Dict[str, Any]:
        """Extract node relationships for metadata"""
        relationships = {}
        if hasattr(node, 'relationships'):
            for rel_type, rel_node in node.relationships.items():
                relationships[rel_type.value] = rel_node.node_id if rel_node else None
        return relationships
