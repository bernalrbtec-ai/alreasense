"""
Consolidação de resumos aprovados em uma única memória RAG por contato.
Um documento consolidado por (tenant, contact_phone); ordem: mais recente no topo.
"""
import logging
import uuid
from django.db import IntegrityError
from django.utils import timezone

from apps.ai.models import ConversationSummary, ConsolidationRecord
from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag
from apps.ai.summary_rag import (
    rag_upsert_consolidated,
    rag_remove_consolidated,
    rag_upsert_for_summary,
    rag_remove_for_summary,
)

logger = logging.getLogger(__name__)


def _format_datetime(dt):
    if not dt:
        return ""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M")


def build_consolidated_content(summaries):
    """
    Monta o texto consolidado a partir dos resumos, mais recente primeiro.
    Cada bloco: Data do atendimento, Departamento, Assunto, conteúdo.
    summaries: queryset ou lista de ConversationSummary, já ordenados por -created_at.
    """
    lines = []
    for s in summaries:
        meta = s.metadata or {}
        date_str = _format_datetime(s.created_at)
        department = (meta.get("department_name") or meta.get("department") or "").strip()
        subject = (meta.get("subject") or "").strip()
        block = [
            f"Data do atendimento: {date_str}",
            f"Departamento: {department or '—'}",
            f"Assunto: {subject or '—'}",
            "",
            (s.content or "").strip(),
        ]
        lines.append("\n".join(block))
    return "\n\n---\n\n".join(lines) if lines else ""


def consolidate_approved_summaries_for_contact(tenant_id, contact_phone_normalized, summary_ids=None):
    """
    Consolida todos os resumos aprovados do contato em um único documento RAG.
    - Se summary_ids for passado: valida que existem, são do tenant, aprovados e do mesmo contact_phone
      normalizado; consolida todos os aprovados desse contato (não só os IDs).
    - Ordem: (1) upsert consolidado, (2) em sucesso remove cada resumo individual da RAG,
      (3) cria ou atualiza ConsolidationRecord.
    - contact_phone_normalized: já normalizado com normalize_contact_phone_for_rag.
    - Gera consolidated_id novo na criação; reutiliza no refresh.
    - Returns: (consolidated_id, summaries_count).
    """
    if not contact_phone_normalized:
        raise ValueError("contact_phone não pode ser vazio para consolidação")

    base_qs = ConversationSummary.objects.filter(
        tenant_id=tenant_id,
        status=ConversationSummary.STATUS_APPROVED,
    )
    # Filtrar por contact_phone: comparar normalizado (resumos podem ter formato variado)
    all_approved = list(base_qs.order_by("-created_at"))
    normalized_by_id = {}
    for s in all_approved:
        normalized_by_id[s.id] = normalize_contact_phone_for_rag(s.contact_phone or "")
    approved_for_contact = [s for s in all_approved if normalized_by_id.get(s.id) == contact_phone_normalized]

    if summary_ids is not None:
        summary_ids_set = set(summary_ids)
        for sid in summary_ids_set:
            s = next((x for x in approved_for_contact if x.id == sid), None)
            if not s:
                raise ValueError(f"Resumo {sid} não encontrado, não aprovado ou não pertence ao mesmo contato")
        if len(approved_for_contact) < 2:
            raise ValueError("É necessário pelo menos 2 resumos aprovados do mesmo contato para consolidar")

    if len(approved_for_contact) < 2:
        raise ValueError("É necessário pelo menos 2 resumos aprovados do mesmo contato para consolidar")

    content = build_consolidated_content(approved_for_contact)
    ids_list = [s.id for s in approved_for_contact]

    try:
        record = ConsolidationRecord.objects.filter(
            tenant_id=tenant_id,
            contact_phone=contact_phone_normalized,
        ).first()
        if record:
            consolidated_id = record.consolidated_id
            rag_upsert_consolidated(
                tenant_id=tenant_id,
                consolidated_id=consolidated_id,
                contact_phone=contact_phone_normalized,
                content=content,
                metadata={},
            )
        else:
            consolidated_id = uuid.uuid4()
            rag_upsert_consolidated(
                tenant_id=tenant_id,
                consolidated_id=consolidated_id,
                contact_phone=contact_phone_normalized,
                content=content,
                metadata={},
            )
    except Exception as e:
        logger.exception("Consolidação: upsert RAG falhou para contact_phone=%s: %s", contact_phone_normalized, e)
        raise

    for s in approved_for_contact:
        try:
            rag_remove_for_summary(s, raise_on_failure=True)
        except Exception as e:
            logger.error("Consolidação: falha ao remover resumo individual id=%s da RAG: %s", s.id, e)
            raise RuntimeError(
                "Falha ao remover resumo id=%s da RAG: %s" % (s.id, e)
            ) from e

    if record:
        record.summary_ids = ids_list
        record.save()
    else:
        try:
            ConsolidationRecord.objects.create(
                tenant_id=tenant_id,
                contact_phone=contact_phone_normalized,
                consolidated_id=consolidated_id,
                summary_ids=ids_list,
            )
        except IntegrityError:
            existing = ConsolidationRecord.objects.filter(
                tenant_id=tenant_id,
                contact_phone=contact_phone_normalized,
            ).first()
            if existing:
                try:
                    rag_remove_consolidated(tenant_id=tenant_id, consolidated_id=consolidated_id)
                except Exception as e:
                    logger.warning("Consolidação: falha ao remover consolidado duplicado %s: %s", consolidated_id, e)
                existing.summary_ids = ids_list
                existing.save()
            else:
                raise
    return consolidated_id, len(ids_list)


def refresh_consolidation_for_contact(tenant_id, contact_phone):
    """
    Atualiza a consolidação do contato após aprovar/reprovar/editar um resumo.
    - Se o contato tem ConsolidationRecord: recalcula conteúdo com todos os aprovados;
      se 0 ou 1 aprovado, desconsolida (remove documento RAG, apaga record, re-insere 1 na RAG se houver 1).
    - contact_phone: pode ser o valor bruto; será normalizado internamente.
    """
    normalized = normalize_contact_phone_for_rag(contact_phone or "")
    if not normalized:
        return

    record = ConsolidationRecord.objects.filter(
        tenant_id=tenant_id,
        contact_phone=normalized,
    ).first()

    approved = list(
        ConversationSummary.objects.filter(
            tenant_id=tenant_id,
            status=ConversationSummary.STATUS_APPROVED,
        ).order_by("-created_at")
    )
    approved_for_contact = [s for s in approved if normalize_contact_phone_for_rag(s.contact_phone or "") == normalized]

    if not record:
        # Sem record: nada a desconsolidar; se um resumo foi aprovado/editado, rag_upsert_for_summary já foi chamado
        return

    if len(approved_for_contact) <= 1:
        # Desconsolidar
        try:
            rag_remove_consolidated(tenant_id=tenant_id, consolidated_id=record.consolidated_id)
        except Exception as e:
            logger.warning("Refresh consolidação: falha ao remover consolidado %s: %s", record.consolidated_id, e)
        record.delete()
        if len(approved_for_contact) == 1:
            try:
                rag_upsert_for_summary(approved_for_contact[0])
            except Exception as e:
                logger.warning("Refresh consolidação: falha ao re-inserir resumo único id=%s: %s", approved_for_contact[0].id, e)
        return

    # 2+ aprovados: refresh do conteúdo consolidado
    content = build_consolidated_content(approved_for_contact)
    ids_list = [s.id for s in approved_for_contact]
    try:
        rag_upsert_consolidated(
            tenant_id=tenant_id,
            consolidated_id=record.consolidated_id,
            contact_phone=normalized,
            content=content,
            metadata={},
        )
        record.summary_ids = ids_list
        record.save()
    except Exception as e:
        logger.exception("Refresh consolidação: falha ao re-upsert consolidado contact_phone=%s: %s", normalized, e)
        raise
