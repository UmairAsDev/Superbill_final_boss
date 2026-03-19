"""OpenAI embedding utility for vector similarity search."""
import asyncio
from openai import OpenAI
from config.sqlconfig import modelconfig
from loguru import logger

_client = None


def _get_client() -> OpenAI:
    """Lazy-initialize OpenAI client."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=modelconfig.OPENAI_API_KEY)
    return _client


def get_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI text-embedding-3-small.
    
    Args:
        text: Input text to embed
        
    Returns:
        List of floats (1536 dimensions)
    """
    try:
        client = _get_client()
        response = client.embeddings.create(
            input=text,
            model=modelconfig.EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to get embedding: {e}")
        raise


async def async_get_embedding(text: str) -> list[float]:
    """Async wrapper for embedding retrieval using thread pool."""
    return await asyncio.to_thread(get_embedding, text)
