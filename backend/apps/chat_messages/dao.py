"""
Data Access Object for pgvector operations.
"""

from django.db import connection
from typing import List, Tuple, Optional


def write_embedding(message_id: int, embedding: List[float]) -> None:
    """
    Write embedding vector to database.
    
    Args:
        message_id: ID of the message
        embedding: List of float values representing the embedding
    """
    if not embedding:
        return
    
    # Convert list to pgvector format
    vec_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE messages_message SET embedding = %s::vector WHERE id = %s",
            [vec_str, message_id]
        )


def semantic_search(
    tenant_id: str, 
    query_embedding: List[float], 
    limit: int = 20,
    similarity_threshold: float = 0.7
) -> List[Tuple]:
    """
    Perform semantic search using pgvector.
    
    Args:
        tenant_id: UUID of the tenant
        query_embedding: Query embedding vector
        limit: Maximum number of results
        similarity_threshold: Minimum similarity score (0-1)
    
    Returns:
        List of tuples (id, text, sentiment, satisfaction, similarity_score)
    """
    if not query_embedding:
        return []
    
    # Convert list to pgvector format
    vec_str = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id, 
                text, 
                sentiment, 
                satisfaction,
                1 - (embedding <=> %s::vector) as similarity_score
            FROM messages_message
            WHERE tenant_id = %s 
                AND embedding IS NOT NULL
                AND (1 - (embedding <=> %s::vector)) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, [vec_str, tenant_id, vec_str, similarity_threshold, vec_str, limit])
        
        return cursor.fetchall()


def get_embedding(message_id: int) -> Optional[List[float]]:
    """
    Get embedding vector for a message.
    
    Args:
        message_id: ID of the message
    
    Returns:
        List of float values or None if not found
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT embedding FROM messages_message WHERE id = %s",
            [message_id]
        )
        result = cursor.fetchone()
        
        if result and result[0]:
            # Convert pgvector back to list
            vec_str = result[0].strip('[]')
            return [float(x) for x in vec_str.split(',')]
        
        return None


def get_similar_messages(
    message_id: int, 
    tenant_id: str, 
    limit: int = 10,
    similarity_threshold: float = 0.8
) -> List[Tuple]:
    """
    Find messages similar to a given message.
    
    Args:
        message_id: ID of the reference message
        tenant_id: UUID of the tenant
        limit: Maximum number of results
        similarity_threshold: Minimum similarity score
    
    Returns:
        List of tuples (id, text, sentiment, satisfaction, similarity_score)
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                m2.id, 
                m2.text, 
                m2.sentiment, 
                m2.satisfaction,
                1 - (m2.embedding <=> m1.embedding) as similarity_score
            FROM messages_message m1
            JOIN messages_message m2 ON m1.tenant_id = m2.tenant_id
            WHERE m1.id = %s 
                AND m2.id != %s
                AND m1.embedding IS NOT NULL 
                AND m2.embedding IS NOT NULL
                AND (1 - (m2.embedding <=> m1.embedding)) >= %s
            ORDER BY m2.embedding <=> m1.embedding
            LIMIT %s
        """, [message_id, message_id, similarity_threshold, limit])
        
        return cursor.fetchall()


def get_embedding_stats(tenant_id: str) -> dict:
    """
    Get embedding statistics for a tenant.
    
    Args:
        tenant_id: UUID of the tenant
    
    Returns:
        Dictionary with embedding statistics
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(embedding) as messages_with_embeddings,
                AVG(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as embedding_coverage
            FROM messages_message
            WHERE tenant_id = %s
        """, [tenant_id])
        
        result = cursor.fetchone()
        
        return {
            'total_messages': result[0] or 0,
            'messages_with_embeddings': result[1] or 0,
            'embedding_coverage': float(result[2] or 0) * 100
        }
