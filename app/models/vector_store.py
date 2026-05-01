from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

_chroma_client = None


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb

            settings = get_settings()
            persist_dir = Path(settings.vector_db.persist_directory)
            persist_dir.mkdir(parents=True, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=str(persist_dir))
        except ImportError:
            logger.warning("chromadb not installed, vector store features disabled")
            return None
    return _chroma_client


def _get_or_create_collection(name: str):
    client = _get_chroma_client()
    if client is None:
        return None
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._standards_collection_name = settings.vector_db.collection_standards
        self._code_collection_name = settings.vector_db.collection_code

    def index_standards(
        self,
        doc_name: str,
        version: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> int:
        collection = _get_or_create_collection(self._standards_collection_name)
        if collection is None:
            return 0

        ids = []
        documents = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_name}_{version}_{chunk.get('section', i)}"
            ids.append(chunk_id)
            documents.append(chunk.get("content", ""))
            metadatas.append({
                "doc_name": doc_name,
                "version": version,
                "section": chunk.get("section", str(i)),
            })

        if ids:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        return len(ids)

    def search_standards(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_dict: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        collection = _get_or_create_collection(self._standards_collection_name)
        if collection is None:
            return []

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if filter_dict:
            kwargs["where"] = filter_dict

        results = collection.query(**kwargs)

        items = []
        if results and results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                items.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                })
        return items

    def index_code_snippets(
        self,
        repo: str,
        snippets: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> int:
        collection = _get_or_create_collection(self._code_collection_name)
        if collection is None:
            return 0

        ids = []
        documents = []
        metadatas = []
        for i, snippet in enumerate(snippets):
            snippet_id = f"{repo}_{snippet.get('file_path', '')}_{snippet.get('function_name', i)}"
            ids.append(snippet_id)
            documents.append(snippet.get("code", ""))
            metadatas.append({
                "repo": repo,
                "file_path": snippet.get("file_path", ""),
                "function_name": snippet.get("function_name", ""),
                "language": snippet.get("language", "python"),
            })

        if ids:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        return len(ids)

    def search_code(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_dict: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        collection = _get_or_create_collection(self._code_collection_name)
        if collection is None:
            return []

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if filter_dict:
            kwargs["where"] = filter_dict

        results = collection.query(**kwargs)

        items = []
        if results and results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                items.append({
                    "id": results["ids"][0][i],
                    "code": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                })
        return items

    def delete_collection(self, name: str) -> None:
        client = _get_chroma_client()
        if client is None:
            return
        try:
            client.delete_collection(name)
        except Exception:
            logger.warning(f"Failed to delete collection: {name}")
