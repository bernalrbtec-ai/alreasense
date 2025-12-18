"""
BillingCycle - Ciclo completo de mensagens de cobrança
"""
from django.db import models
from django.utils import timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class BillingCycle(models.Model):
    """
    Ciclo completo de mensagens de cobrança
    
    Gerencia o ciclo completo de 6 mensagens (3 upcoming + 3 overdue)
    para uma cobrança específica.
    """
    
    STATUS_CHOICES = [
        ('active', 'Ativo'),
        ('cancelled', 'Cancelado'),
        ('paid', 'Pago'),
        ('completed', 'Completado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Tenant
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='billing_cycles',
        verbose_name='Tenant'
    )
    
    # ID externo da cobrança (único por tenant)
    external_billing_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text='ID da cobrança no sistema externo'
    )
    
    # Contato
    contact_phone = models.CharField(
        max_length=20,
        help_text='Telefone do contato (normalizado)'
    )
    contact_name = models.CharField(
        max_length=255,
        help_text='Nome do contato'
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billing_cycles',
        help_text='Contato cadastrado automaticamente'
    )
    
    # Dados da cobrança
    billing_data = models.JSONField(
        default=dict,
        help_text='Dados da cobrança (valor, vencimento, link, pix, etc.)'
    )
    due_date = models.DateField(
        db_index=True,
        help_text='Data de vencimento'
    )
    
    # Status do ciclo
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        help_text='Status do ciclo'
    )
    
    # Configurações de notificação
    notify_before_due = models.BooleanField(
        default=False,
        help_text='Enviar avisos antes do vencimento?'
    )
    notify_after_due = models.BooleanField(
        default=True,
        help_text='Enviar avisos depois do vencimento?'
    )
    
    # Contadores
    total_messages = models.IntegerField(
        default=0,
        help_text='Total de mensagens do ciclo'
    )
    sent_messages = models.IntegerField(
        default=0,
        help_text='Mensagens enviadas com sucesso'
    )
    failed_messages = models.IntegerField(
        default=0,
        help_text='Mensagens falhadas'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando foi cancelado'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando foi completado'
    )
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_cycle'
        verbose_name = 'Ciclo de Billing'
        verbose_name_plural = 'Ciclos de Billing'
        unique_together = [['tenant', 'external_billing_id']]
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['external_billing_id']),
            models.Index(fields=['due_date']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"BillingCycle - {self.external_billing_id} ({self.get_status_display()})"
    
    def check_and_complete(self):
        """
        Verifica se ciclo deve ser marcado como 'completed'.
        
        Um ciclo é considerado completo quando:
        - Todas as mensagens foram processadas (sent ou failed)
        - Nenhuma mensagem está pendente (pending, pending_retry, sending)
        """
        if self.status in ['cancelled', 'paid', 'completed']:
            return False
        
        # Conta mensagens por status
        total = self.billing_contacts.count()
        if total == 0:
            # Ciclo sem mensagens não pode ser completado
            return False
        
        sent = self.billing_contacts.filter(status='sent').count()
        failed = self.billing_contacts.filter(status='failed').count()
        cancelled = self.billing_contacts.filter(status='cancelled').count()
        
        # Mensagens ainda pendentes (não processadas)
        pending_statuses = ['pending', 'pending_retry', 'sending']
        pending_count = self.billing_contacts.filter(status__in=pending_statuses).count()
        
        # Se todas foram processadas (sent + failed + cancelled = total) e nenhuma pendente
        processed = sent + failed + cancelled
        if processed == total and pending_count == 0:
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.sent_messages = sent
            self.failed_messages = failed
            self.save(update_fields=['status', 'completed_at', 'sent_messages', 'failed_messages', 'updated_at'])
            
            logger.info(
                f"✅ Ciclo {self.id} completado: {sent} enviadas, {failed} falhadas, {cancelled} canceladas",
                extra={
                    'cycle_id': str(self.id),
                    'sent': sent,
                    'failed': failed,
                    'cancelled': cancelled
                }
            )
            return True
        
        return False


