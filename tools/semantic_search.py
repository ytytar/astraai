import os
import asyncio
import threading
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, model_validator
import chromadb

from core.tool_creation.tool_factories import BaseFunctionToolFactory
from core.tool_creation.models import ToolParam


# ============================================================================
# Embedding Provider Abstraction
# ============================================================================

class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        pass


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """HuggingFace SentenceTransformer embedding provider."""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        try:
            from sentence_transformers import SentenceTransformer
            self.SentenceTransformer = SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for HuggingFace embeddings. "
                "Install it with: pip install sentence-transformers"
            )
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load the model only when first accessed."""
        if self._model is None:
            import os
            # Reduce HuggingFace Hub retries from default (unlimited) to 3
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '30')
            os.environ.setdefault('CURL_CA_BUNDLE', '')

            # SentenceTransformer will respect HF_HUB_OFFLINE if network is unavailable
            try:
                self._model = self.SentenceTransformer(self.model_name)
            except Exception as e:
                # If download fails, try offline mode (use cached model)
                os.environ['HF_HUB_OFFLINE'] = '1'
                self._model = self.SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        embedding = self.model.encode([query], convert_to_numpy=True)
        return embedding[0].tolist()


class VertexAIGeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google VertexAI Gemini embedding provider."""

    def __init__(
        self,
        model_name: str = 'text-embedding-004',
        project_id: Optional[str] = None,
        location: str = 'us-central1'
    ):
        try:
            from vertexai.language_models import TextEmbeddingModel
            import vertexai
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform is required for VertexAI embeddings. "
                "Install it with: pip install google-cloud-aiplatform"
            )

        # Initialize VertexAI
        vertexai.init(project=project_id, location=location)
        self.model = TextEmbeddingModel.from_pretrained(model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.model.get_embeddings(texts)
        return [emb.values for emb in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query."""
        embeddings = self.model.get_embeddings([query])
        return embeddings[0].values


# ============================================================================
# Configuration Models
# ============================================================================


class SemanticSearchConfig(BaseModel):
    """Configuration for semantic search tool."""
    # Background process configuration (required)
    scan_directory: str = Field(
        description="Directory path to scan and index for semantic search"
    )
    file_extensions: List[str] = Field(
        default=[".md", ".txt", ".py", ".js", ".ts", ".yaml", ".yml"],
        description="File extensions to include when scanning directory"
    )
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=4000,
        description="Size of text chunks for indexing (in characters)"
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=500,
        description="Overlap between chunks (in characters)"
    )

    # Embedding provider configuration
    embedding_provider: Literal["huggingface", "vertexai"] = Field(
        default="huggingface",
        description="Embedding provider to use: 'huggingface' or 'vertexai'"
    )

    # HuggingFace configuration (used when embedding_provider='huggingface')
    huggingface_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="HuggingFace model name for embeddings"
    )

    # VertexAI configuration (used when embedding_provider='vertexai')
    vertexai_model: str = Field(
        default="text-embedding-004",
        description="VertexAI embedding model name"
    )
    vertexai_project_id: Optional[str] = Field(
        default=None,
        description="GCP project ID for VertexAI (if not provided, uses default from environment)"
    )
    vertexai_location: str = Field(
        default="us-central1",
        description="GCP location/region for VertexAI"
    )

    # Default values for LLM parameters
    similarity_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Default minimum similarity score for results"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default maximum number of search results to return"
    )

    # LLM callable parameters definition
    params: List[ToolParam] = Field(
        default=[
            ToolParam(
                name="query",
                type="string",
                description="The query to search for",
                required=True
            )
        ],
        description="Parameters that the LLM can use when calling this tool"
    )


class SemanticSearchTool(BaseFunctionToolFactory):
    """Tool for searching the semantic index with ChromaDB."""

    # Static Pydantic data model for this tool
    data_model = SemanticSearchConfig

    def __init__(self, name: str, description: str, **config):
        super().__init__(name, description, **config)
        # Validate configuration using the static data model
        self.tool_config = self.data_model(**config)

        # Setup logging
        self.logger = logging.getLogger(f"semantic_search_{name}")
        self.logger.setLevel(logging.INFO)

        # Initialize embedding provider based on configuration
        self.embedding_provider = self._create_embedding_provider()
        self.logger.info(f"Initialized {self.tool_config.embedding_provider} embedding provider")

        # Initialize ChromaDB client - store in the scan directory
        chroma_path = os.path.join(self.tool_config.scan_directory, f".chroma_db_{name}")
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)

        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=f"semantic_search_{name}",
            metadata={"hnsw:space": "cosine"}
        )

        # Track indexing state
        self._indexing_complete = False
        self._indexing_lock = threading.Lock()

        # Start background indexing
        self._start_background_indexing()

    def _create_embedding_provider(self) -> BaseEmbeddingProvider:
        """Factory method to create the appropriate embedding provider."""
        provider_type = self.tool_config.embedding_provider

        if provider_type == "huggingface":
            return HuggingFaceEmbeddingProvider(
                model_name=self.tool_config.huggingface_model
            )
        elif provider_type == "vertexai":
            return VertexAIGeminiEmbeddingProvider(
                model_name=self.tool_config.vertexai_model,
                project_id=self.tool_config.vertexai_project_id,
                location=self.tool_config.vertexai_location
            )
        else:
            raise ValueError(
                f"Unsupported embedding provider: {provider_type}. "
                f"Supported providers: huggingface, vertexai"
            )

    def _start_background_indexing(self):
        """Start background indexing process."""
        def index_worker():
            try:
                self.logger.info("Background indexing thread started")
                self._index_directory()
                self.logger.info("Background indexing thread completed")
            except Exception as e:
                self.logger.error(f"Background indexing failed: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                # Mark as complete even on failure to avoid infinite waiting
                self._indexing_complete = True

        indexing_thread = threading.Thread(target=index_worker, daemon=True)
        indexing_thread.start()
        self.logger.info("Background indexing thread launched")

    def _index_directory(self):
        """Index files in the configured directory."""
        with self._indexing_lock:
            if self._indexing_complete:
                return

            self.logger.info(f"Starting indexing of directory: {self.tool_config.scan_directory}")

            scan_path = Path(self.tool_config.scan_directory)
            if not scan_path.exists():
                self.logger.error(f"Directory does not exist: {self.tool_config.scan_directory}")
                self._indexing_complete = True  # Mark as complete to avoid infinite retries
                return

            documents = []
            metadatas = []
            ids = []
            doc_id = 0
            files_processed = 0

            # Scan files (one level deep as requested)
            for file_path in scan_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.tool_config.file_extensions:
                    try:
                        before_count = len(documents)
                        self._process_file(file_path, documents, metadatas, ids, doc_id)
                        chunks_added = len(documents) - before_count
                        doc_id += chunks_added
                        files_processed += 1
                        self.logger.debug(f"Processed {file_path.name}: {chunks_added} chunks")
                    except Exception as e:
                        self.logger.warning(f"Failed to process file {file_path}: {e}")
                elif file_path.is_dir():
                    # One level of depth - scan subdirectories
                    for sub_file in file_path.iterdir():
                        if sub_file.is_file() and sub_file.suffix.lower() in self.tool_config.file_extensions:
                            try:
                                before_count = len(documents)
                                self._process_file(sub_file, documents, metadatas, ids, doc_id)
                                chunks_added = len(documents) - before_count
                                doc_id += chunks_added
                                files_processed += 1
                                self.logger.debug(f"Processed {sub_file}: {chunks_added} chunks")
                            except Exception as e:
                                self.logger.warning(f"Failed to process file {sub_file}: {e}")

            self.logger.info(f"Scanned {files_processed} files, found {len(documents)} document chunks")

            # Add documents to ChromaDB in batches with embeddings
            if documents:
                try:
                    batch_size = 100
                    for i in range(0, len(documents), batch_size):
                        batch_docs = documents[i:i + batch_size]
                        batch_metas = metadatas[i:i + batch_size]
                        batch_ids = ids[i:i + batch_size]

                        # Generate embeddings for this batch
                        batch_embeddings = self.embedding_provider.embed_texts(batch_docs)

                        self.collection.add(
                            documents=batch_docs,
                            metadatas=batch_metas,
                            ids=batch_ids,
                            embeddings=batch_embeddings
                        )
                        self.logger.debug(f"Added batch {i//batch_size + 1}: {len(batch_docs)} chunks")

                    self.logger.info(f"Successfully indexed {len(documents)} document chunks")
                except Exception as e:
                    self.logger.error(f"Failed to add documents to ChromaDB: {e}")
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    return  # Don't mark as complete if indexing failed
            else:
                self.logger.info("No documents found to index")

            self._indexing_complete = True
            self.logger.info("Indexing completed successfully")

    def _process_file(self, file_path: Path, documents: List[str], metadatas: List[Dict], ids: List[str], doc_id: int):
        """Process a single file and add chunks to the document list."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Skip binary files
            return

        # Split content into chunks
        chunks = self._chunk_text(content)

        for i, chunk in enumerate(chunks):
            if chunk.strip():  # Skip empty chunks
                documents.append(chunk)
                metadatas.append({
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "chunk_index": i,
                    "file_extension": file_path.suffix
                })
                ids.append(f"{doc_id}_{i}")

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        chunk_size = self.tool_config.chunk_size
        overlap = self.tool_config.chunk_overlap

        if len(text) <= chunk_size:
            return [text]

        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)

            if end >= len(text):
                break

            start = end - overlap

        return chunks

    async def _execute(self, params) -> Any:
        """Search the semantic index."""
        query = params.get("query")
        if not query:
            return {"error": "Query parameter is required"}

        # Use defaults from config for optional parameters
        limit = params.get("limit", self.tool_config.limit)
        similarity_threshold = params.get("similarity_threshold", self.tool_config.similarity_threshold)

        try:
            # Check if indexing is complete or if we have data in collection (fallback)
            collection_count = self.collection.count()

            if not self._indexing_complete and collection_count == 0:
                # Actually still indexing
                scan_path = Path(self.tool_config.scan_directory)
                files_in_dir = list(scan_path.glob("*")) if scan_path.exists() else []
                return {
                    "status": "indexing_in_progress",
                    "message": "Search index is still being built. Please try again in a moment.",
                    "query": query,
                    "debug_info": {
                        "indexing_complete": self._indexing_complete,
                        "collection_count": collection_count,
                        "scan_directory": str(scan_path),
                        "directory_exists": scan_path.exists(),
                        "files_in_directory": [str(f) for f in files_in_dir[:5]],
                        "supported_extensions": self.tool_config.file_extensions
                    }
                }
            elif not self._indexing_complete and collection_count > 0:
                # Indexing completed but flag wasn't set - fix it
                self.logger.info(f"Indexing appears complete ({collection_count} documents), fixing completion flag")
                self._indexing_complete = True

            # Generate query embedding
            query_embedding = self.embedding_provider.embed_query(query)

            # Perform semantic search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=['documents', 'metadatas', 'distances']
            )

            # Format results
            search_results = []
            all_similarities = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Convert distance to similarity score (ChromaDB uses cosine distance)
                    similarity = 1 - distance
                    all_similarities.append(round(similarity, 4))

                    if similarity >= similarity_threshold:
                        search_results.append({
                            "content": doc,
                            "similarity_score": round(similarity, 4),
                            "file_path": metadata.get("file_path"),
                            "file_name": metadata.get("file_name"),
                            "chunk_index": metadata.get("chunk_index"),
                            "file_extension": metadata.get("file_extension")
                        })

            return {
                "status": "success",
                "query": query,
                "results_count": len(search_results),
                "results": search_results,
                "debug": {
                    "all_similarity_scores": all_similarities,
                    "max_similarity": max(all_similarities) if all_similarities else 0,
                    "min_similarity": min(all_similarities) if all_similarities else 0
                },
                "config": {
                    "limit": limit,
                    "similarity_threshold": similarity_threshold,
                    "indexed_directory": self.tool_config.scan_directory
                }
            }

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "query": query
            }
    
    @classmethod
    def schema(cls) -> Dict[str, Any]:
        """Return the full configuration schema matching YAML structure."""
        return cls.data_model.model_json_schema()
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get the configuration schema for this tool instance."""
        return self.tool_config.model_dump()
    
    def get_llm_params(self) -> List[Dict[str, Any]]:
        """Get the parameters that LLM can use when calling this tool."""
        return [param.model_dump() for param in self.tool_config.params]
    
    def get_background_config(self) -> Dict[str, Any]:
        """Get configuration for background indexing process."""
        return {
            "scan_directory": self.tool_config.scan_directory,
            "file_extensions": self.tool_config.file_extensions,
            "chunk_size": self.tool_config.chunk_size,
            "chunk_overlap": self.tool_config.chunk_overlap
        }
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> SemanticSearchConfig:
        """Validate and return typed configuration."""
        return cls.data_model(**config) 
