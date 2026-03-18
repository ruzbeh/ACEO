"""ChromaDB-based vector memory for semantic search over artifacts."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


def _create_chroma_client(
    *,
    host: str | None = None,
    port: int = 8001,
    persist_directory: str = "./chroma_data",
) -> Any:
    """Create Chroma client: HttpClient if host is set, else PersistentClient."""
    if host:
        return chromadb.HttpClient(host=host, port=port)
    return chromadb.PersistentClient(
        path=persist_directory,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


class VectorMemory:
    """Semantic search over past artifacts using ChromaDB."""

    def __init__(
        self,
        persist_directory: str = "./chroma_data",
        host: str | None = None,
        port: int = 8001,
    ) -> None:
        self._client = _create_chroma_client(
            host=host,
            port=port,
            persist_directory=persist_directory,
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
        ids = results.get("ids") and results["ids"][0]
        if not ids:
            return []
        docs = []
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        for i in range(len(ids)):
            docs.append(
                {
                    "id": ids[i],
                    "content": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                }
            )
        return docs

    def count(self) -> int:
        return self._collection.count()
