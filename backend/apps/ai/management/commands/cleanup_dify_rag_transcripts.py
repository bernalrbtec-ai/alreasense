from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ai.models import AiKnowledgeDocument
from apps.ai.services.dify_rag_memory_service import SOURCE_CHAT_TEXT_TRANSCRIPT


class Command(BaseCommand):
    help = "Remove documentos RAG de transcript Dify expirados."

    def handle(self, *args, **options):
        now = timezone.now()
        qs = AiKnowledgeDocument.objects.filter(
            source=SOURCE_CHAT_TEXT_TRANSCRIPT,
            expires_at__isnull=False,
            expires_at__lt=now,
        )
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nenhum documento expirado encontrado."))
            return
        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Documentos removidos: {deleted} (registros-alvo: {total})"))

