"""
Embedding generation for semantic search with caching.
"""

import requests
import numpy as np
from typing import List, Optional
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Flag para habilitar/desabilitar cache (configurável via settings)
_EMBEDDING_CACHE_ENABLED = getattr(settings, "AI_EMBEDDING_CACHE_ENABLED", True)


def embed_text(text: str, use_cache: bool = True) -> List[float]:
    """
    Generate embedding for text using AI service with caching.
    
    Args:
        text: Text to embed
        use_cache: Whether to use cache (default: True, respects AI_EMBEDDING_CACHE_ENABLED)
    
    Returns:
        List of float values representing the embedding
    """
    if not text or not text.strip():
        return []
    
    # Usar cache se habilitado
    if use_cache and _EMBEDDING_CACHE_ENABLED:
        try:
            from apps.ai.models import MessageEmbedding
            
            embedding, was_cached = MessageEmbedding.get_or_create_embedding(
                text=text,
                embedding_func=_embed_text_uncached
            )
            
            if was_cached:
                logger.debug(f"Embedding cache hit for text: {text[:50]}...")
            
            return embedding
        except Exception as e:
            logger.warning(f"Failed to use embedding cache, falling back to direct: {e}")
            # Fallback: gerar sem cache
            return _embed_text_uncached(text)
    
    # Gerar sem cache
    return _embed_text_uncached(text)


def _embed_text_uncached(text: str) -> List[float]:
    """
    Generate embedding without cache (internal function).
    
    Args:
        text: Text to embed
    
    Returns:
        List of float values representing the embedding
    """
    try:
        # Try N8N webhook first
        if settings.N8N_AI_WEBHOOK:
            return _embed_via_n8n(text)
        
        # Fallback to local model (placeholder)
        return _embed_via_local(text)
        
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        # Return zero vector as fallback
        return [0.0] * 768


def _embed_via_n8n(text: str) -> List[float]:
    """Generate embedding via N8N webhook."""
    
    payload = {
        "text": text,
        "model": settings.AI_EMBEDDING_MODEL,
        "action": "embed"
    }
    
    response = requests.post(
        settings.N8N_AI_WEBHOOK,
        json=payload,
        timeout=10.0
    )
    response.raise_for_status()
    
    data = response.json()
    return data.get('embedding', [])


def _embed_via_local(text: str) -> List[float]:
    """
    Generate embedding using local model (placeholder).
    
    In a real implementation, this would use:
    - Ollama API
    - Local Qwen model
    - Transformers library
    """
    
    # Placeholder: return random embedding
    # In production, replace with actual local model
    np.random.seed(hash(text) % 2**32)
    return np.random.normal(0, 1, 768).tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
    
    Returns:
        List of embeddings
    """
    embeddings = []
    
    for text in texts:
        embedding = embed_text(text)
        embeddings.append(embedding)
    
    return embeddings


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        a: First embedding
        b: Second embedding
    
    Returns:
        Cosine similarity score (0-1)
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    
    a_np = np.array(a)
    b_np = np.array(b)
    
    dot_product = np.dot(a_np, b_np)
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)
