"""ChromaDB-based vector memory for semantic search over artifacts."""

import logging
import uuid

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


class VectorMemory:
    """Semantic search over past artifacts using ChromaDB."""

    def __init__(self, persist_directory: str = "./chroma_data") -> None:
        self._client = chromadb.Client(
            ChromaSettings(
                persist_directory=persist_directory,
                anonymized_telemetry=False,
            )
        )
        self._collection = self._client.get_or_create_collection(
            name="aeco_artifacts",
            metadata={"description": "AECO agent artifacts and knowledge"},
        )

    def add(
        self,
        content: str,
        metadata: dict | None = None,
        doc_id: str | None = None,
    ) -> str:
        """Add a document to the vector store."""
        doc_id = doc_id or str(uuid.uuid4())
        self._collection.add(
            documents=[content],
            metadatas=[metadata or {}],
            ids=[doc_id],
        )
        return doc_id

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search for similar documents."""
        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        docs = []
        for i in range(len(results["ids"][0])):
            docs.append(
                {
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                }
            )
        return docs

    def count(self) -> int:
        return self._collection.count()
