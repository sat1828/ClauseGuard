"""
Embedder — Stage 2.5 (runs after chunking)
============================================
Embeds contract chunks and upserts to Pinecone.
Uses per-contract namespaces (NOT separate indexes — see config.py for reasoning).

At query time: embeds the user's question and retrieves top-k similar chunks.
"""

import json
import time
from typing import Optional

import structlog
from openai import AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec

from config import get_settings
from schemas.analysis import LegalChunk

logger = structlog.get_logger(__name__)
settings = get_settings()

# Module-level clients — initialized once
_openai_client: Optional[AsyncOpenAI] = None
_pinecone_client: Optional[Pinecone] = None
_pinecone_index = None


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def get_pinecone_index():
    """
    Get or create the Pinecone index.
    Uses a single shared index with per-contract namespaces.

    Index creation is idempotent — calling this multiple times is safe.
    """
    global _pinecone_client, _pinecone_index

    if _pinecone_index is not None:
        return _pinecone_index

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    _pinecone_client = pc

    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if settings.PINECONE_INDEX_NAME not in existing_indexes:
        logger.info("creating_pinecone_index", name=settings.PINECONE_INDEX_NAME)
        pc.create_index(
            name=settings.PINECONE_INDEX_NAME,
            dimension=settings.OPENAI_EMBEDDING_DIMENSIONS,
            metric=settings.PINECONE_METRIC,
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1",
            ),
        )
        # Wait for index to be ready (serverless indexes are fast but need a moment)
        timeout = 60
        start = time.time()
        while time.time() - start < timeout:
            status = pc.describe_index(settings.PINECONE_INDEX_NAME)
            if status.status.get("ready", False):
                break
            time.sleep(2)

    _pinecone_index = pc.Index(settings.PINECONE_INDEX_NAME)
    return _pinecone_index


async def embed_text(text: str) -> list[float]:
    """Embed a single text string using OpenAI text-embedding-3-small."""
    client = get_openai_client()
    response = await client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
        dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed multiple texts in a single API call.
    OpenAI allows up to 2048 inputs per request; we batch at 100 for safety.
    """
    client = get_openai_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), 100):
        batch = texts[i: i + 100]
        response = await client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=batch,
            dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
        )
        # OpenAI returns embeddings in order
        all_embeddings.extend([item.embedding for item in response.data])

    return all_embeddings


async def upsert_chunks(chunks: list[LegalChunk], contract_id: str) -> str:
    """
    Embed all chunks and upsert to Pinecone under a per-contract namespace.

    Namespace format: "contract_{contract_id}" — allows targeted deletion.

    Returns the namespace name for storage in the database.
    """
    namespace = f"contract_{contract_id}"
    index = get_pinecone_index()

    logger.info("embedding_chunks", contract_id=contract_id, chunk_count=len(chunks))

    # Embed all chunk texts
    texts = [chunk.text for chunk in chunks]
    embeddings = await embed_batch(texts)

    # Build Pinecone vectors
    # Metadata stored per vector for retrieval reconstruction
    vectors = []
    for chunk, embedding in zip(chunks, embeddings):
        metadata = {
            "chunk_id": chunk.chunk_id,
            "section_heading": chunk.section_heading,
            "page_start": chunk.page_range[0],
            "page_end": chunk.page_range[1],
            "chunk_index": chunk.chunk_index,
            "token_count": chunk.token_count,
            # Store text in metadata for retrieval (Pinecone metadata limit: 40KB)
            "text": chunk.text[:3000],  # Truncate to stay within limits
            # context_header is NOT stored — it's rebuilt at query time
        }
        vectors.append({
            "id": chunk.chunk_id,
            "values": embedding,
            "metadata": metadata,
        })

    # Upsert in batches of 100 (Pinecone's recommended batch size)
    for i in range(0, len(vectors), 100):
        batch = vectors[i: i + 100]
        index.upsert(vectors=batch, namespace=namespace)

    logger.info(
        "chunks_upserted",
        contract_id=contract_id,
        namespace=namespace,
        vectors=len(vectors),
    )

    return namespace


async def query_chunks(
    question: str,
    contract_id: str,
    top_k: int = 5,
    contract_namespace: Optional[str] = None,
) -> list[dict]:
    """
    Query Pinecone for the most relevant chunks for a user question.

    Returns a list of chunk metadata dicts (not LegalChunk objects —
    those were serialized on upsert).
    """
    namespace = contract_namespace or f"contract_{contract_id}"
    index = get_pinecone_index()

    # Embed the question
    question_embedding = await embed_text(question)

    # Query Pinecone
    results = index.query(
        vector=question_embedding,
        top_k=top_k,
        namespace=namespace,
        include_metadata=True,
    )

    retrieved = []
    for match in results.matches:
        metadata = match.metadata or {}
        retrieved.append({
            "chunk_id": metadata.get("chunk_id", match.id),
            "text": metadata.get("text", ""),
            "section_heading": metadata.get("section_heading", "Unknown"),
            "page_range": [
                metadata.get("page_start", 1),
                metadata.get("page_end", 1),
            ],
            "score": match.score,
        })

    logger.debug(
        "chunks_retrieved",
        contract_id=contract_id,
        question_length=len(question),
        results=len(retrieved),
        top_score=retrieved[0]["score"] if retrieved else 0,
    )

    return retrieved


async def delete_contract_namespace(contract_id: str) -> None:
    """
    Delete all vectors for a contract from Pinecone.
    Called when a contract is deleted via the API.
    """
    namespace = f"contract_{contract_id}"
    index = get_pinecone_index()

    try:
        index.delete(delete_all=True, namespace=namespace)
        logger.info("pinecone_namespace_deleted", contract_id=contract_id, namespace=namespace)
    except Exception as e:
        # Non-fatal: log the error but don't fail the DELETE request
        logger.error("pinecone_deletion_failed", contract_id=contract_id, error=str(e))
