from typing import List, Dict, Any, Optional
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from apps.ai.embeddings import cosine_similarity


def _to_vector_str(embedding: List[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"


_pgvector_checked = False
_pgvector_available = False


def _has_pgvector() -> bool:
    global _pgvector_checked, _pgvector_available
    if _pgvector_checked:
        return _pgvector_available
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_type WHERE typname = 'vector'")
            _pgvector_available = cursor.fetchone() is not None
    except Exception:
        _pgvector_available = False
    _pgvector_checked = True
    return _pgvector_available


def search_memory(
    tenant_id: str,
    query_embedding: List[float],
    limit: int = 5,
    similarity_threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    if not query_embedding:
        return []

    if _has_pgvector():
        vec_str = _to_vector_str(query_embedding)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    kind,
                    content,
                    metadata,
                    1 - (embedding <=> %s::vector) as similarity_score
                FROM ai_memory_item
                WHERE tenant_id = %s
                  AND embedding IS NOT NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                  AND (1 - (embedding <=> %s::vector)) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [vec_str, tenant_id, vec_str, similarity_threshold, vec_str, limit],
            )
            rows = cursor.fetchall()

        return [
            {
                'id': row[0],
                'kind': row[1],
                'content': row[2],
                'metadata': row[3] or {},
                'similarity': float(row[4] or 0),
            }
            for row in rows
        ]

    # Fallback sem pgvector: busca limitada e calcula similaridade em Python
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, kind, content, metadata, embedding
            FROM ai_memory_item
            WHERE tenant_id = %s
              AND embedding IS NOT NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
            LIMIT %s
            """,
            [tenant_id, max(limit * 50, 200)],
        )
        rows = cursor.fetchall()

    scored = []
    for row in rows:
        embedding = row[4] or []
        similarity = cosine_similarity(query_embedding, embedding)
        if similarity >= similarity_threshold:
            scored.append((similarity, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for similarity, row in scored[:limit]:
        results.append({
            'id': row[0],
            'kind': row[1],
            'content': row[2],
            'metadata': row[3] or {},
            'similarity': float(similarity),
        })
    return results


def search_knowledge(
    tenant_id: str,
    query_embedding: List[float],
    limit: int = 5,
    similarity_threshold: float = 0.7,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Busca semântica em documentos de conhecimento do tenant.
    Se source for informado (ex: 'secretary'), filtra apenas documentos desse source.
    """
    if not query_embedding:
        return []

    if _has_pgvector():
        vec_str = _to_vector_str(query_embedding)
        sql_extra = " AND source = %s" if source else ""
        params = [vec_str, tenant_id]
        if source:
            params.append(source)
        params.extend([vec_str, similarity_threshold, vec_str, limit])
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    content,
                    source,
                    tags,
                    metadata,
                    1 - (embedding <=> %s::vector) as similarity_score
                FROM ai_knowledge_document
                WHERE tenant_id = %s
                  AND embedding IS NOT NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                  """ + sql_extra + """
                  AND (1 - (embedding <=> %s::vector)) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            rows = cursor.fetchall()

        return [
            {
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'source': row[3],
                'tags': row[4] or [],
                'metadata': row[5] or {},
                'similarity': float(row[6] or 0),
            }
            for row in rows
        ]

    with connection.cursor() as cursor:
        sql_extra = " AND source = %s" if source else ""
        params = [tenant_id]
        if source:
            params.append(source)
        params.append(max(limit * 50, 200))
        cursor.execute(
            """
            SELECT id, title, content, source, tags, metadata, embedding
            FROM ai_knowledge_document
            WHERE tenant_id = %s
              AND embedding IS NOT NULL
              AND (expires_at IS NULL OR expires_at > NOW())
              """ + sql_extra + """
            ORDER BY created_at DESC
            LIMIT %s
            """,
            params,
        )
        rows = cursor.fetchall()

    scored = []
    for row in rows:
        embedding = row[6] or []
        similarity = cosine_similarity(query_embedding, embedding)
        if similarity >= similarity_threshold:
            scored.append((similarity, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for similarity, row in scored[:limit]:
        results.append({
            'id': row[0],
            'title': row[1],
            'content': row[2],
            'source': row[3],
            'tags': row[4] or [],
            'metadata': row[5] or {},
            'similarity': float(similarity),
        })
    return results


def search_memory_for_contact(
    tenant_id: str,
    contact_phone: str,
    query_embedding: List[float],
    within_days: int = 365,
    limit: int = 5,
    similarity_threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Busca memória restrita ao contato: mesmo tenant + mesmo contact_phone,
    apenas conversas dos últimos within_days (padrão 1 ano). Hierarquia tenant → contato → histórico.
    """
    if not query_embedding or not contact_phone:
        return []

    from apps.chat.models import Conversation
    since = timezone.now() - timedelta(days=within_days)
    conversation_ids = list(
        Conversation.objects.filter(
            tenant_id=tenant_id,
            contact_phone=contact_phone,
            updated_at__gte=since,
        ).values_list('id', flat=True)[:500]
    )
    if not conversation_ids:
        return []

    if _has_pgvector():
        vec_str = _to_vector_str(query_embedding)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    kind,
                    content,
                    metadata,
                    1 - (embedding <=> %s::vector) as similarity_score
                FROM ai_memory_item
                WHERE tenant_id = %s
                  AND conversation_id = ANY(%s)
                  AND created_at >= %s
                  AND embedding IS NOT NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                  AND (1 - (embedding <=> %s::vector)) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [vec_str, tenant_id, conversation_ids, since, vec_str, similarity_threshold, vec_str, limit],
            )
            rows = cursor.fetchall()
        return [
            {
                'id': row[0],
                'kind': row[1],
                'content': row[2],
                'metadata': row[3] or {},
                'similarity': float(row[4] or 0),
            }
            for row in rows
        ]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, kind, content, metadata, embedding
            FROM ai_memory_item
            WHERE tenant_id = %s
              AND conversation_id = ANY(%s)
              AND created_at >= %s
              AND embedding IS NOT NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
            LIMIT %s
            """,
            [tenant_id, conversation_ids, since, max(limit * 50, 200)],
        )
        rows = cursor.fetchall()

    scored = []
    for row in rows:
        embedding = row[4] or []
        similarity = cosine_similarity(query_embedding, embedding)
        if similarity >= similarity_threshold:
            scored.append((similarity, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            'id': row[0],
            'kind': row[1],
            'content': row[2],
            'metadata': row[3] or {},
            'similarity': float(similarity),
        }
        for similarity, row in scored[:limit]
    ]
