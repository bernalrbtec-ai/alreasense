"""
Management command to start Evolution API ingestion service.
"""

from django.core.management.base import BaseCommand
from ingestion.evolution_ws import run_ingestion_service


class Command(BaseCommand):
    help = 'Start Evolution API ingestion service'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting Evolution API ingestion service...')
        )
        
        try:
            run_ingestion_service()
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('Ingestion service stopped by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Fatal error: {e}')
            )
            raise
