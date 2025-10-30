from django.core.management.base import BaseCommand
from django.db import transaction
from apps.chat.models import MessageAttachment
from apps.chat.utils.s3 import S3Manager


class Command(BaseCommand):
    help = "Reescreve file_url antigos (S3 direto) para usar o proxy interno em todos os anexos."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Apenas mostrar o que seria alterado')
        parser.add_argument('--limit', type=int, default=0, help='Limitar quantidade de registros processados')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        s3 = S3Manager()

        qs = MessageAttachment.objects.filter(storage_type='s3').exclude(file_path='')
        # Apenas os que não estão no proxy
        qs = qs.exclude(file_url__icontains='/api/chat/media-proxy')

        total = qs.count()
        if limit:
            qs = qs[:limit]

        self.stdout.write(self.style.NOTICE(f"Encontrados {total} anexos S3 sem proxy."))
        if limit and total > limit:
            self.stdout.write(self.style.NOTICE(f"Processando apenas os primeiros {limit} registros"))

        updated = 0
        with transaction.atomic():
            for att in qs:
                new_url = s3.get_public_url(att.file_path)
                if not dry_run:
                    att.file_url = new_url
                    att.save(update_fields=['file_url'])
                updated += 1
                self.stdout.write(f"✔ {att.id} → proxy")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run concluído. {updated} anexos seriam atualizados."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Concluído. {updated} anexos atualizados para proxy."))
