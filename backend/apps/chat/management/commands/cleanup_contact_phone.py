"""
Remove dados do Sense associados a um telefone (tenant + variantes BR/55).

Uso (dry-run — só mostra contagens):
    python manage.py cleanup_contact_phone --tenant-id <uuid> --phone 17991253112

Executar destruição:
    python manage.py cleanup_contact_phone --tenant-id <uuid> --phone 17991253112 --execute

Inclui registro em contacts.Contact (CRM) e histórico:
    python manage.py cleanup_contact_phone ... --execute --include-contact

Não remove campanhas / filas de disparo por defeito.
"""
from __future__ import annotations

import logging
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Apaga conversas, mensagens, RAG e dados de IA ligados a um telefone (escopo tenant)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=str, required=True, help="UUID do tenant")
        parser.add_argument("--phone", type=str, required=True, help="Telefone (qualquer formato; ex. 17991253112)")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Sem isto, apenas simula (dry-run).",
        )
        parser.add_argument(
            "--include-contact",
            action="store_true",
            help="Também apaga Contact CRM + histórico (CASCADE) desse telefone.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Com --execute, não pede confirmação interativa.",
        )

    def handle(self, *args, **options):
        from apps.tenancy.models import Tenant
        from apps.chat.models import Conversation
        from apps.chat.utils.phone_match import digit_variants_for_match, contact_model_phone_in_variants
        from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag
        from apps.ai.models import (
            AiGatewayAudit,
            AiKnowledgeDocument,
            AiMemoryItem,
            AiTriageResult,
            ConsolidationRecord,
            ConversationSummary,
        )
        from apps.contacts.models import Contact

        tenant_id = options["tenant_id"].strip()
        raw_phone = options["phone"].strip()
        do_execute = options["execute"]
        include_contact = options["include_contact"]
        skip_confirm = options["yes"]

        try:
            UUID(tenant_id)
        except ValueError as exc:
            raise CommandError("tenant-id deve ser um UUID válido.") from exc

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant não encontrado: {tenant_id}") from exc

        variants = digit_variants_for_match(raw_phone)
        if not variants:
            raise CommandError("Telefone inválido ou vazio após normalização.")

        conv_qs = Conversation.objects.filter(tenant_id=tenant_id).exclude(
            conversation_type="group",
        )
        matching = [c for c in conv_qs if _conv_match(c.contact_phone, variants)]
        conv_ids = [c.id for c in matching]

        variant_list = sorted(variants)

        contacts_qs = Contact.objects.filter(tenant_id=tenant_id)
        matching_contacts = [c for c in contacts_qs if contact_model_phone_in_variants(c.phone, variants)]
        contact_ids = [c.id for c in matching_contacts]

        # --- contagens ---
        doc_q = Q(tenant_id=tenant_id) & (
            Q(metadata__contact_phone__in=variant_list)
            | Q(metadata__conversation_id__in=[str(x) for x in conv_ids])
        )
        docs = AiKnowledgeDocument.objects.filter(doc_q)
        mem = AiMemoryItem.objects.filter(tenant_id=tenant_id, conversation_id__in=conv_ids)
        triage = AiTriageResult.objects.filter(tenant_id=tenant_id, conversation_id__in=conv_ids)
        audit_filter = Q(tenant_id=tenant_id, conversation_id__in=conv_ids)
        if contact_ids:
            audit_filter |= Q(tenant_id=tenant_id, contact_id__in=contact_ids)
        audit = AiGatewayAudit.objects.filter(audit_filter)

        summ_ids = []
        for s in ConversationSummary.objects.filter(tenant_id=tenant_id):
            if s.conversation_id in conv_ids or normalize_contact_phone_for_rag(s.contact_phone or "") in variants:
                summ_ids.append(s.id)

        consol_ids = []
        for r in ConsolidationRecord.objects.filter(tenant_id=tenant_id):
            if normalize_contact_phone_for_rag(r.contact_phone or "") in variants:
                consol_ids.append(r.id)

        self.stdout.write(self.style.WARNING("\n" + "=" * 72))
        self.stdout.write(self.style.WARNING(" Limpeza por telefone (escopo TENANT)"))
        self.stdout.write(self.style.WARNING("=" * 72))
        self.stdout.write(f"Tenant: {tenant.name} ({tenant_id})")
        self.stdout.write(f"Telefone / variantes dígitos: {variant_list}")
        self.stdout.write(f"Conversas (1:1) a apagar: {len(conv_ids)}")
        self.stdout.write(f"ai_knowledge_document (filtro): {docs.count()}")
        self.stdout.write(f"ai_memory_item: {mem.count()}")
        self.stdout.write(f"ai_triage_result: {triage.count()}")
        self.stdout.write(f"ai_gateway_audit: {audit.count()}")
        self.stdout.write(f"ai_conversation_summary: {len(summ_ids)}")
        self.stdout.write(f"ai_consolidation_record: {len(consol_ids)}")
        self.stdout.write(f"contacts.Contact: {len(matching_contacts)} (só apaga com --include-contact)")

        if not do_execute:
            self.stdout.write(self.style.SUCCESS("\nDry-run. Nada foi alterado. Use --execute para aplicar.\n"))
            return

        if not skip_confirm:
            self.stdout.write(self.style.ERROR("\nIRREVERSÍVEL. Digite EXCLUIR para confirmar: "))
            if input().strip() != "EXCLUIR":
                self.stdout.write(self.style.SUCCESS("Cancelado."))
                return

        with transaction.atomic():
            deleted = {}

            n_audit, _ = audit.delete()
            deleted["ai_gateway_audit"] = n_audit

            n_triage, _ = triage.delete()
            deleted["ai_triage_result"] = n_triage

            n_mem, _ = mem.delete()
            deleted["ai_memory_item"] = n_mem

            n_docs, _ = docs.delete()
            deleted["ai_knowledge_document"] = n_docs

            n_sum, _ = ConversationSummary.objects.filter(id__in=summ_ids).delete()
            deleted["ai_conversation_summary"] = n_sum

            n_con, _ = ConsolidationRecord.objects.filter(id__in=consol_ids).delete()
            deleted["ai_consolidation_record"] = n_con

            n_conv, _ = Conversation.objects.filter(id__in=conv_ids, tenant_id=tenant_id).delete()
            deleted["chat_conversation_tree"] = n_conv

            if include_contact:
                for c in matching_contacts:
                    c.delete()
                deleted["contacts_deleted"] = len(matching_contacts)

        self.stdout.write(self.style.SUCCESS("\nConcluído. Removidos (totais ORM / CASCADE):"))
        for k, v in deleted.items():
            self.stdout.write(f"  • {k}: {v}")
        self.stdout.write(
            self.style.WARNING(
                "\nNota: memória da conversa no painel Dify não é apagada por este comando.\n"
            )
        )
        logger.warning(
            "cleanup_contact_phone executed tenant=%s phone_variants=%s convs=%s include_contact=%s",
            tenant_id,
            variant_list,
            len(conv_ids),
            include_contact,
        )


def _conv_match(contact_phone: str, variants: set[str]) -> bool:
    from apps.chat.utils.phone_match import conversation_phone_in_variants

    return conversation_phone_in_variants(contact_phone, variants)
