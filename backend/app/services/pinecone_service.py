"""Shared Pinecone indexing and retrieval service."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pinecone import Pinecone

from app.config import Settings
from app.core.exceptions import PineconeConfigurationError

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - optional dependency in local dev.
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:  # pragma: no cover - fallback path is tested instead.
        RecursiveCharacterTextSplitter = None  # type: ignore[assignment]

PINECONE_CONTROL_API_VERSION = "2025-04"
PINECONE_DATA_API_VERSION = "2025-04"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
RELEVANCE_THRESHOLD = 0.75
TEXT_FILE_EXTENSIONS = {
    ".c",
    ".cpp",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
IMAGE_FILE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PDF_FILE_EXTENSIONS = {".pdf"}

logger = logging.getLogger(__name__)


class PineconeService:
    """Async Pinecone wrapper with asset indexing and retrieval helpers."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_key: str = "",
        index_name: str = "",
        index_host: str = "",
        client: httpx.AsyncClient | None = None,
        pinecone_client: Pinecone | None = None,
        vision_model: ChatOpenAI | None = None,
    ) -> None:
        resolved_api_key = api_key.strip()
        resolved_index_name = index_name.strip()
        resolved_index_host = index_host.strip()

        if settings is not None:
            resolved_api_key = resolved_api_key or settings.pinecone_api_key.strip()
            resolved_index_name = (
                resolved_index_name or settings.pinecone_index_name.strip()
            )
            resolved_index_host = (
                resolved_index_host or settings.pinecone_index_host.strip()
            )
            self.namespace = settings.pinecone_namespace.strip() or "project-default"
            self.embedding_model = (
                settings.pinecone_embed_model.strip() or "multilingual-e5-large"
            )
            self.openai_api_key = settings.openai_api_key.strip()
            self.vision_model_name = settings.openai_vision_model.strip()
        else:
            self.namespace = "project-default"
            self.embedding_model = "multilingual-e5-large"
            self.openai_api_key = ""
            self.vision_model_name = "gpt-4o-mini"

        self.api_key = resolved_api_key
        self.index_name = resolved_index_name
        self.index_host = resolved_index_host
        self._resolved_host: str | None = self.index_host or None
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=20.0)
        self._pinecone_client = pinecone_client
        self._vision_model = vision_model

    @property
    def enabled(self) -> bool:
        """Return whether Pinecone can be reached with the current settings."""
        return bool(self.api_key and self.index_name)

    async def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            await self.client.aclose()

    async def upsert(
        self,
        *,
        namespace: str,
        vectors: list[dict[str, Any]],
    ) -> int:
        """Upsert vectors into the namespace and return the upsert count."""
        response = await self.client.post(
            await self._data_url("/vectors/upsert"),
            headers=self._data_headers(),
            json={"namespace": namespace, "vectors": vectors},
        )
        response.raise_for_status()
        payload = response.json()
        return int(payload.get("upsertedCount", 0))

    async def query(
        self,
        *,
        namespace: str,
        vector: list[float],
        top_k: int,
        filter_expression: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query the namespace and return raw match objects."""
        payload: dict[str, Any] = {
            "namespace": namespace,
            "vector": vector,
            "topK": top_k,
            "includeMetadata": True,
        }
        if filter_expression:
            payload["filter"] = filter_expression

        response = await self.client.post(
            await self._data_url("/query"),
            headers=self._data_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return list(data.get("matches", []))

    async def delete_by_filter(
        self,
        *,
        namespace: str,
        filter_expression: dict[str, Any],
    ) -> None:
        """Delete vectors from the namespace by metadata filter."""
        response = await self.client.post(
            await self._data_url("/vectors/delete"),
            headers=self._data_headers(),
            json={"namespace": namespace, "filter": filter_expression},
        )
        response.raise_for_status()

    def build_user_namespace(self, *, user_id: str) -> str:
        """Return the per-user asset namespace."""
        return f"{self.namespace}:{user_id.strip()}"

    def build_memory_namespace(self, *, user_id: str) -> str:
        """Return the per-user long-term memory namespace."""
        return f"{self.namespace}:memory:{user_id.strip()}"

    async def chunk_and_index(
        self,
        *,
        asset_id: str,
        user_id: str,
        file_path: str,
        file_name: str,
        mime_type: str,
    ) -> dict[str, int]:
        """Read, chunk, embed, and upsert a stored asset."""
        if not self.enabled:
            return {"chunks_created": 0, "vectors_upserted": 0}

        document_text = await self._load_document_text(
            path=Path(file_path),
            file_name=file_name,
            mime_type=mime_type,
        )
        chunks = self._split_text(document_text or f"Stored asset: {file_name}")
        embeddings = await self._embed_documents(chunks)
        if not embeddings:
            return {"chunks_created": 0, "vectors_upserted": 0}

        namespace = self.build_user_namespace(user_id=user_id)
        vectors: list[dict[str, Any]] = []
        for chunk_index, (chunk_text, values) in enumerate(
            zip(chunks, embeddings, strict=True)
        ):
            vectors.append(
                {
                    "id": f"{asset_id}:{chunk_index}",
                    "values": values,
                    "metadata": {
                        "asset_id": asset_id,
                        "user_id": user_id,
                        "asset_name": file_name,
                        "source_file": file_name,
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                        "chunk_text": chunk_text,
                        "mime_type": mime_type,
                    },
                }
            )

        upserted_count = await self.upsert(namespace=namespace, vectors=vectors)
        return {
            "chunks_created": len(chunks),
            "vectors_upserted": upserted_count,
        }

    async def delete_asset_vectors(self, *, asset_id: str, user_id: str) -> None:
        """Delete all indexed vectors for a stored asset."""
        if not self.enabled:
            return

        await self.delete_by_filter(
            namespace=self.build_user_namespace(user_id=user_id),
            filter_expression={
                "asset_id": {"$eq": asset_id},
                "user_id": {"$eq": user_id},
            },
        )

    async def retrieve_context(
        self,
        *,
        user_message: str,
        user_id: str,
        top_k: int = 5,
        relevance_threshold: float = RELEVANCE_THRESHOLD,
    ) -> list[str]:
        """Return the most relevant indexed asset chunks for a user message."""
        if not self.enabled or not user_message.strip():
            return []

        query_vector = await self._embed_query(user_message)
        if not query_vector:
            return []

        matches = await self.query(
            namespace=self.build_user_namespace(user_id=user_id),
            vector=query_vector,
            top_k=top_k,
            filter_expression={"user_id": {"$eq": user_id}},
        )

        context_blocks: list[str] = []
        for match in matches:
            score = match.get("score")
            if not isinstance(score, (int, float)) or (
                float(score) < relevance_threshold
            ):
                continue

            metadata = match.get("metadata") or {}
            chunk_text = metadata.get("text") or metadata.get("chunk_text")
            asset_name = metadata.get("asset_name") or metadata.get("source_file")
            if not isinstance(chunk_text, str) or not isinstance(asset_name, str):
                continue

            normalized_text = chunk_text.strip()
            if not normalized_text:
                continue
            context_blocks.append(f"{normalized_text} (source: {asset_name})")

        return context_blocks

    async def store_memory_summary(
        self,
        *,
        user_id: str,
        conversation_id: str,
        summary: str,
        segment_key: str,
    ) -> bool:
        """Embed and store a conversation summary in the memory namespace."""
        if not self.enabled or not summary.strip():
            return False

        embedding = await self._embed_query(summary)
        if not embedding:
            return False

        upserted = await self.upsert(
            namespace=self.build_memory_namespace(user_id=user_id),
            vectors=[
                {
                    "id": f"{conversation_id}:{segment_key}",
                    "values": embedding,
                    "metadata": {
                        "conversation_id": conversation_id,
                        "type": "memory",
                        "summary": summary,
                    },
                }
            ],
        )
        return upserted > 0

    async def retrieve_memories(
        self,
        *,
        user_id: str,
        user_message: str,
        top_k: int = 3,
        relevance_threshold: float = RELEVANCE_THRESHOLD,
    ) -> list[str]:
        """Return semantically relevant conversation summaries for a user."""
        if not self.enabled or not user_message.strip():
            return []

        query_vector = await self._embed_query(user_message)
        if not query_vector:
            return []

        matches = await self.query(
            namespace=self.build_memory_namespace(user_id=user_id),
            vector=query_vector,
            top_k=top_k,
            filter_expression={"type": {"$eq": "memory"}},
        )

        memories: list[str] = []
        for match in matches:
            score = match.get("score")
            if not isinstance(score, (int, float)) or (
                float(score) < relevance_threshold
            ):
                continue

            metadata = match.get("metadata") or {}
            summary = metadata.get("summary")
            if isinstance(summary, str) and summary.strip():
                memories.append(summary.strip())
        return memories

    async def summarize_conversation_segment(
        self,
        *,
        messages: list[dict[str, Any]],
        model_name: str,
    ) -> str:
        """Summarize a conversation segment for long-term retrieval."""
        if not messages:
            return ""

        llm = await self._get_vision_model(model_name=model_name)
        if llm is None:
            return ""

        transcript_lines = [
            f"{item.get('role', 'unknown')}: {str(item.get('content', '')).strip()}"
            for item in messages
            if str(item.get("content", "")).strip()
        ]
        if not transcript_lines:
            return ""

        response = await llm.ainvoke(
            [
                HumanMessage(
                    content=(
                        "Summarize this conversation segment in 3-5 sentences, "
                        "capturing key facts, decisions, and user preferences.\n\n"
                        + "\n".join(transcript_lines)
                    )
                )
            ]
        )
        summary = self._extract_text(getattr(response, "content", response)).strip()
        return summary

    async def _get_index_host(self) -> str:
        if self._resolved_host:
            return self._resolved_host
        if not self.enabled:
            raise PineconeConfigurationError()

        response = await self.client.get(
            f"https://api.pinecone.io/indexes/{self.index_name}",
            headers={
                "Api-Key": self.api_key,
                "X-Pinecone-Api-Version": PINECONE_CONTROL_API_VERSION,
            },
        )
        response.raise_for_status()
        payload = response.json()
        host = payload.get("host")
        if not isinstance(host, str) or not host.strip():
            raise PineconeConfigurationError(
                "Could not resolve the Pinecone index host."
            )
        self._resolved_host = host.strip()
        return self._resolved_host

    def _data_headers(self) -> dict[str, str]:
        return {
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
            "X-Pinecone-Api-Version": PINECONE_DATA_API_VERSION,
        }

    async def _data_url(self, path: str) -> str:
        host = await self._get_index_host()
        return f"https://{host}{path}"

    async def _embed_documents(self, chunks: list[str]) -> list[list[float]]:
        if not self.enabled or not chunks:
            return []

        return await self._pinecone_embed(chunks, input_type="passage")

    async def _embed_query(self, text: str) -> list[float]:
        if not self.enabled or not text.strip():
            return []

        vectors = await self._pinecone_embed([text], input_type="query")
        return vectors[0] if vectors else []

    async def _pinecone_embed(
        self,
        texts: list[str],
        *,
        input_type: str,
    ) -> list[list[float]]:
        if not texts:
            return []

        try:
            client = self._get_pinecone_client()
            response = await asyncio.to_thread(
                client.inference.embed,
                model=self.embedding_model,
                inputs=texts,
                parameters={"input_type": input_type},
            )
            return self._extract_vectors(response)
        except Exception:
            logger.exception("Pinecone inference embedding failed.")
            return []

    def _get_pinecone_client(self) -> Pinecone:
        if self._pinecone_client is not None:
            return self._pinecone_client

        self._pinecone_client = Pinecone(api_key=self.api_key)
        return self._pinecone_client

    @staticmethod
    def _extract_vectors(response: Any) -> list[list[float]]:
        if isinstance(response, dict):
            data = response.get("data", [])
        else:
            data = getattr(response, "data", [])

        vectors: list[list[float]] = []
        for item in data:
            if isinstance(item, dict):
                raw = item.get("values") or item.get("vector")
            else:
                raw = getattr(item, "values", None) or getattr(item, "vector", None)

            if isinstance(raw, list) and all(isinstance(v, (float, int)) for v in raw):
                vectors.append([float(v) for v in raw])

        return vectors

    async def _get_vision_model(
        self,
        *,
        model_name: str | None = None,
    ) -> ChatOpenAI | None:
        if self._vision_model is not None and model_name in {
            None,
            self.vision_model_name,
        }:
            return self._vision_model
        if not self.openai_api_key.strip():
            return None

        resolved_model_name = (model_name or self.vision_model_name).strip()
        model = ChatOpenAI(
            model=resolved_model_name,
            api_key=self.openai_api_key,
            max_retries=2,
            temperature=0,
        )
        if model_name is None or resolved_model_name == self.vision_model_name:
            self._vision_model = model
        return model

    async def _load_document_text(
        self,
        *,
        path: Path,
        file_name: str,
        mime_type: str,
    ) -> str:
        suffix = path.suffix.lower()
        if suffix in PDF_FILE_EXTENSIONS or mime_type == "application/pdf":
            return self._extract_pdf_text(path)
        if suffix in IMAGE_FILE_EXTENSIONS or mime_type.startswith("image/"):
            return await self._describe_image(path=path, file_name=file_name)
        if suffix == ".svg" and mime_type.startswith("image/"):
            return await self._describe_image(path=path, file_name=file_name)
        return path.read_text(encoding="utf-8", errors="ignore")

    def _extract_pdf_text(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.exception("PDF parsing is unavailable because pypdf is missing.")
            return f"PDF asset: {path.name}"

        try:
            reader = PdfReader(str(path))
            text_parts = [page.extract_text() or "" for page in reader.pages]
        except Exception:
            logger.exception("PDF text extraction failed for %s.", path)
            return f"PDF asset: {path.name}"

        return "\n\n".join(part.strip() for part in text_parts if part.strip())

    async def _describe_image(self, *, path: Path, file_name: str) -> str:
        data_url = self._path_to_data_url(path)
        model = await self._get_vision_model()
        if model is None:
            return f"Image asset: {file_name}"

        try:
            response = await model.ainvoke(
                [
                    HumanMessage(
                        content=[
                            {
                                "type": "text",
                                "text": (
                                    "Describe this image for retrieval. Summarize the "
                                    "important visible content and any readable text."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                        ]
                    )
                ]
            )
            description = self._extract_text(getattr(response, "content", response))
            if description.strip():
                return f"Image asset: {file_name}\n{description.strip()}"
        except Exception:
            logger.exception("Image analysis failed for %s.", path)

        if path.suffix.lower() == ".svg":
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
            return f"Image asset: {file_name}\n{raw_text[:4000]}"
        return f"Image asset: {file_name}"

    def _split_text(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+\n", "\n", text).strip()
        if not normalized:
            return ["No extractable content was available."]

        if RecursiveCharacterTextSplitter is not None:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )
            chunks = [chunk.strip() for chunk in splitter.split_text(normalized)]
            return [chunk for chunk in chunks if chunk] or [normalized]

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(len(normalized), start + CHUNK_SIZE)
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
        return chunks or [normalized]

    @staticmethod
    def _extract_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return str(value) if value is not None else ""

    @staticmethod
    def _path_to_data_url(path: Path) -> str:
        mime_type = "image/png"
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            mime_type = "image/jpeg"
        elif path.suffix.lower() == ".svg":
            mime_type = "image/svg+xml"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
