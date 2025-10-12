"""
Celery tasks para processamento assíncrono de contatos
"""

from celery import shared_task
from django.utils import timezone
import logging
import os

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_contact_import_async(self, import_id, tenant_id, user_id):
    """
    Processa importação de contatos de forma assíncrona
    
    Args:
        import_id: UUID do ContactImport
        tenant_id: UUID do Tenant
        user_id: UUID do User
    """
    from .models import ContactImport
    from apps.tenancy.models import Tenant
    from apps.authn.models import User
    from .services import ContactImportService
    
    try:
        import_record = ContactImport.objects.get(id=import_id)
    except ContactImport.DoesNotExist:
        logger.error(f'ContactImport {import_id} não encontrado')
        return {'status': 'error', 'message': 'Import record not found'}
    
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)
    except (Tenant.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f'Tenant ou User não encontrado: {e}')
        import_record.status = ContactImport.Status.FAILED
        import_record.errors.append({'error': 'Tenant ou User não encontrado'})
        import_record.save()
        return {'status': 'error', 'message': str(e)}
    
    # Marcar como processando
    import_record.status = ContactImport.Status.PROCESSING
    import_record.save()
    
    try:
        # Ler arquivo
        import csv
        import io
        
        with open(import_record.file_path, 'r', encoding='utf-8-sig') as f:
            csv_reader = csv.DictReader(f)
            rows = list(csv_reader)
        
        import_record.total_rows = len(rows)
        import_record.save()
        
        # Processar cada linha
        service = ContactImportService(tenant=tenant, user=user)
        
        for i, row in enumerate(rows):
            try:
                service._process_row(row, import_record)
                import_record.processed_rows = i + 1
                import_record.save()
                
                # Atualizar progresso no Celery (para UI)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i + 1,
                        'total': import_record.total_rows,
                        'created': import_record.created_count,
                        'updated': import_record.updated_count,
                        'skipped': import_record.skipped_count,
                        'errors': import_record.error_count,
                        'percentage': int(((i + 1) / import_record.total_rows) * 100)
                    }
                )
                
            except Exception as e:
                logger.error(f'Erro na linha {i + 2}: {e}')
                import_record.error_count += 1
                import_record.errors.append({
                    'row': i + 2,  # +2 porque linha 1 é header e index é 0-based
                    'error': str(e),
                    'severity': 'critical'
                })
                import_record.save()
        
        # Marcar como concluído
        import_record.status = ContactImport.Status.COMPLETED
        import_record.completed_at = timezone.now()
        import_record.save()
        
        # Limpar arquivo temporário
        try:
            if os.path.exists(import_record.file_path):
                os.remove(import_record.file_path)
        except:
            pass
        
        logger.info(
            f'Importação {import_id} concluída. '
            f'Criados: {import_record.created_count}, '
            f'Atualizados: {import_record.updated_count}, '
            f'Erros: {import_record.error_count}'
        )
        
        # TODO: Enviar notificação para o usuário
        # send_import_completion_notification(import_record)
        
        return {
            'status': 'success',
            'created': import_record.created_count,
            'updated': import_record.updated_count,
            'skipped': import_record.skipped_count,
            'errors': import_record.error_count
        }
        
    except Exception as e:
        logger.error(f'Erro fatal no import {import_id}: {e}', exc_info=True)
        import_record.status = ContactImport.Status.FAILED
        import_record.errors.append({
            'row': 0,
            'error': f'Erro fatal: {str(e)}',
            'severity': 'critical'
        })
        import_record.save()
        
        # Limpar arquivo temporário
        try:
            if os.path.exists(import_record.file_path):
                os.remove(import_record.file_path)
        except:
            pass
        
        raise


@shared_task
def cleanup_old_import_files():
    """
    Task periódica para limpar arquivos antigos de importação
    Roda uma vez por dia
    """
    from datetime import timedelta
    from .models import ContactImport
    
    # Buscar importações antigas (>7 dias)
    old_date = timezone.now() - timedelta(days=7)
    old_imports = ContactImport.objects.filter(
        created_at__lt=old_date,
        status__in=[ContactImport.Status.COMPLETED, ContactImport.Status.FAILED]
    )
    
    cleaned = 0
    for import_record in old_imports:
        try:
            if os.path.exists(import_record.file_path):
                os.remove(import_record.file_path)
                cleaned += 1
        except Exception as e:
            logger.error(f'Erro ao limpar arquivo {import_record.file_path}: {e}')
    
    logger.info(f'Limpeza concluída. {cleaned} arquivos removidos.')
    return {'cleaned': cleaned}




