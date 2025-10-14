from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Campaign(models.Model):
    """
    Campanha de disparo em massa via WhatsApp
    """
    
    ROTATION_MODE_CHOICES = [
        ('round_robin', 'Round Robin'),
        ('balanced', 'Balanceado'),
        ('intelligent', 'Inteligente'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Rascunho'),
        ('scheduled', 'Agendada'),
        ('running', 'Em Execução'),
        ('paused', 'Pausada'),
        ('completed', 'Concluída'),
        ('cancelled', 'Cancelada'),
    ]
    
    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=255, verbose_name='Nome da Campanha')
    description = models.TextField(blank=True, null=True, verbose_name='Descrição')
    
    # Configurações
    rotation_mode = models.CharField(
        max_length=20,
        choices=ROTATION_MODE_CHOICES, 
        default='intelligent',
        verbose_name='Modo de Rotação'
    )
    
    # Instâncias selecionadas para rotação
    instances = models.ManyToManyField(
        'notifications.WhatsAppInstance',
        related_name='campaigns',
        verbose_name='Instâncias'
    )
    
    # Lista de contatos
    contact_list = models.ForeignKey(
        'contacts.ContactList',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
        verbose_name='Lista de Contatos'
    )
    
    # Contatos individuais (se não usar lista)
    contacts = models.ManyToManyField(
        'contacts.Contact',
        through='CampaignContact',
        related_name='campaigns',
        verbose_name='Contatos'
    )
    
    # Configurações de envio
    interval_min = models.IntegerField(
        default=25, 
        verbose_name='Intervalo Mínimo (seg)',
        validators=[
            MinValueValidator(20, message="Intervalo mínimo deve ser pelo menos 20 segundos"),
            MaxValueValidator(420, message="Intervalo máximo deve ser no máximo 420 segundos")
        ],
        help_text="Intervalo mínimo entre mensagens (20-420 segundos)"
    )
    interval_max = models.IntegerField(
        default=50, 
        verbose_name='Intervalo Máximo (seg)',
        validators=[
            MinValueValidator(20, message="Intervalo mínimo deve ser pelo menos 20 segundos"),
            MaxValueValidator(420, message="Intervalo máximo deve ser no máximo 420 segundos")
        ],
        help_text="Intervalo máximo entre mensagens (20-420 segundos)"
    )
    daily_limit_per_instance = models.IntegerField(
        default=100, 
        verbose_name='Limite Diário por Instância'
    )
    pause_on_health_below = models.IntegerField(
        default=30,
        verbose_name='Pausar se Health Score abaixo de'
    )
    
    # Agendamento
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='Agendada Para')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Iniciada Em')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Concluída Em')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Status'
    )
    
    # Contadores
    total_contacts = models.IntegerField(default=0, verbose_name='Total de Contatos')
    messages_sent = models.IntegerField(default=0, verbose_name='Mensagens Enviadas')
    messages_delivered = models.IntegerField(default=0, verbose_name='Mensagens Entregues')
    messages_read = models.IntegerField(default=0, verbose_name='Mensagens Lidas')
    messages_failed = models.IntegerField(default=0, verbose_name='Mensagens com Erro')
    
    # Rotação (para round robin)
    current_instance_index = models.IntegerField(default=0, verbose_name='Índice da Instância Atual')
    
    # Controle de timing
    last_message_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Última Mensagem Enviada Em')
    next_message_scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='Próxima Mensagem Agendada Para')
    next_contact_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Nome do Próximo Contato')
    next_contact_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name='Telefone do Próximo Contato')
    next_instance_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Nome da Próxima Instância')
    last_contact_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Nome do Último Contato')
    last_contact_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name='Telefone do Último Contato')
    last_instance_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Nome da Última Instância')
    
    # Metadados
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_campaigns',
        verbose_name='Criado Por'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado Em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado Em')
    
    class Meta:
        db_table = 'campaigns_campaign'
        verbose_name = 'Campanha'
        verbose_name_plural = 'Campanhas'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def success_rate(self):
        """Taxa de entrega da campanha (entregues / (entregues + falhas))"""
        total_processed = self.messages_delivered + self.messages_failed
        if total_processed == 0:
            return 0
        return (self.messages_delivered / total_processed) * 100
    
    @property
    def read_rate(self):
        """Taxa de leitura"""
        if self.messages_delivered == 0:
            return 0
        return (self.messages_read / self.messages_delivered) * 100
    
    @property
    def progress_percentage(self):
        """Progresso da campanha"""
        if self.total_contacts == 0:
            return 0
        return (self.messages_sent / self.total_contacts) * 100
    
    def start(self):
        """Inicia a campanha"""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save()
    
    def pause(self):
        """Pausa a campanha"""
        self.status = 'paused'
        self.next_message_scheduled_at = None
        self.next_contact_name = None
        self.next_contact_phone = None
        self.save()
    
    def resume(self):
        """Resume a campanha"""
        self.status = 'running'
        # next_message_scheduled_at será definido no próximo envio
        self.save()
    
    def complete(self):
        """Completa a campanha"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.next_message_scheduled_at = None
        self.next_contact_name = None
        self.next_contact_phone = None
        self.save()
    
    def cancel(self):
        """Cancela a campanha"""
        self.status = 'cancelled'
        self.next_message_scheduled_at = None
        self.next_contact_name = None
        self.next_contact_phone = None
        self.save()
    
    def update_next_contact_info(self):
        """Atualiza informações do próximo contato para campanhas em execução"""
        if self.status == 'running':
            next_campaign_contact = self.campaign_contacts.filter(
                status='pending'
            ).select_related('contact').first()
            
            if next_campaign_contact:
                self.next_contact_name = next_campaign_contact.contact.name
                self.next_contact_phone = next_campaign_contact.contact.phone
                
                # Obter próxima instância usando o serviço de rotação
                from .services import RotationService
                rotation_service = RotationService(self)
                next_instance = rotation_service.select_next_instance()
                if next_instance:
                    self.next_instance_name = next_instance.friendly_name
                else:
                    self.next_instance_name = None
            else:
                self.next_contact_name = None
                self.next_contact_phone = None
                self.next_instance_name = None
            
            self.save(update_fields=['next_contact_name', 'next_contact_phone', 'next_instance_name'])
    
    def clean(self):
        """Validação adicional do modelo"""
        from django.core.exceptions import ValidationError
        
        # Validar que interval_min <= interval_max
        if self.interval_min > self.interval_max:
            raise ValidationError({
                'interval_min': 'Intervalo mínimo não pode ser maior que o máximo.',
                'interval_max': 'Intervalo máximo não pode ser menor que o mínimo.'
            })
        
        # Validar que interval_max <= 420 (limite de timeout)
        if self.interval_max > 420:
            raise ValidationError({
                'interval_max': 'Intervalo máximo deve ser no máximo 420 segundos para evitar timeouts.'
            })


class CampaignMessage(models.Model):
    """
    Variações de mensagem para a campanha
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(verbose_name='Conteúdo da Mensagem')
    order = models.IntegerField(default=0, verbose_name='Ordem')
    times_used = models.IntegerField(default=0, verbose_name='Vezes Utilizada')
    
    # Mídia (opcional)
    media_url = models.URLField(blank=True, null=True, verbose_name='URL da Mídia')
    media_type = models.CharField(
        max_length=20,
        choices=[
            ('image', 'Imagem'),
            ('video', 'Vídeo'),
            ('audio', 'Áudio'),
            ('document', 'Documento'),
        ],
        blank=True,
        null=True,
        verbose_name='Tipo de Mídia'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_message'
        verbose_name = 'Mensagem da Campanha'
        verbose_name_plural = 'Mensagens da Campanha'
        ordering = ['order']
    
    def __str__(self):
        return f"Mensagem #{self.order} - {self.campaign.name}"


class CampaignContact(models.Model):
    """
    Relacionamento entre campanha e contato com status de envio
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('sending', 'Enviando'),
        ('sent', 'Enviada'),
        ('delivered', 'Entregue'),
        ('read', 'Lida'),
        ('failed', 'Falhou'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='campaign_contacts')
    contact = models.ForeignKey('contacts.Contact', on_delete=models.CASCADE, related_name='campaign_contacts')
    
    # Instância usada para enviar
    instance_used = models.ForeignKey(
        'notifications.WhatsAppInstance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_messages_sent'
    )
    
    # Mensagem usada
    message_used = models.ForeignKey(
        CampaignMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contacts_sent'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='Agendado Para')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Enviado Em')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='Entregue Em')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Lido Em')
    failed_at = models.DateTimeField(null=True, blank=True, verbose_name='Falhou Em')
    
    # Erro (se houver)
    error_message = models.TextField(blank=True, null=True, verbose_name='Mensagem de Erro')
    
    # ID da mensagem no WhatsApp
    whatsapp_message_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Tentativas
    retry_count = models.IntegerField(default=0, verbose_name='Tentativas')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_contact'
        verbose_name = 'Contato da Campanha'
        verbose_name_plural = 'Contatos da Campanha'
        unique_together = ['campaign', 'contact']
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.contact.name} - {self.campaign.name} ({self.get_status_display()})"


class CampaignLog(models.Model):
    """
    Log detalhado de todas as ações da campanha
    Para investigação, análise e criação de indicadores
    """
    
    LOG_TYPE_CHOICES = [
        ('created', 'Campanha Criada'),
        ('started', 'Campanha Iniciada'),
        ('paused', 'Campanha Pausada'),
        ('resumed', 'Campanha Retomada'),
        ('completed', 'Campanha Concluída'),
        ('cancelled', 'Campanha Cancelada'),
        ('instance_selected', 'Instância Selecionada'),
        ('instance_paused', 'Instância Pausada'),
        ('instance_resumed', 'Instância Retomada'),
        ('message_sent', 'Mensagem Enviada'),
        ('message_delivered', 'Mensagem Entregue'),
        ('message_read', 'Mensagem Lida'),
        ('message_failed', 'Mensagem Falhou'),
        ('rotation_changed', 'Modo de Rotação Alterado'),
        ('contact_added', 'Contato Adicionado'),
        ('contact_removed', 'Contato Removido'),
        ('limit_reached', 'Limite Atingido'),
        ('health_issue', 'Problema de Saúde'),
        ('error', 'Erro'),
    ]
    
    SEVERITY_CHOICES = [
        ('info', 'Informação'),
        ('warning', 'Aviso'),
        ('error', 'Erro'),
        ('critical', 'Crítico'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='logs')
    
    # Tipo e severidade
    log_type = models.CharField(max_length=30, choices=LOG_TYPE_CHOICES, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='info', db_index=True)
    
    # Contexto
    message = models.TextField(verbose_name='Mensagem do Log')
    details = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Detalhes (JSON)',
        help_text='Dados estruturados: instance_id, contact_id, error_code, etc.'
    )
    
    # Relacionamentos opcionais (para facilitar queries)
    instance = models.ForeignKey(
        'notifications.WhatsAppInstance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_logs'
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_logs'
    )
    campaign_contact = models.ForeignKey(
        CampaignContact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    
    # Performance/Timing
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Duração (ms)',
        help_text='Tempo de execução da operação'
    )
    
    # Request/Response (para debug)
    request_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Dados da Requisição',
        help_text='Payload enviado para API'
    )
    response_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Dados da Resposta',
        help_text='Resposta recebida da API'
    )
    http_status = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Status HTTP'
    )
    
    # Métricas no momento do log
    campaign_progress = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Progresso da Campanha (%)',
        help_text='Snapshot do progresso quando log foi criado'
    )
    instance_health_score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Health Score da Instância',
        help_text='Snapshot do health quando log foi criado'
    )
    
    # Metadados
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='campaign_logs',
        help_text='Tenant que possui este log'
    )
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_logs_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'campaigns_log'
        verbose_name = 'Log da Campanha'
        verbose_name_plural = 'Logs das Campanhas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', '-created_at']),
            models.Index(fields=['log_type', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['instance', '-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.get_severity_display()}] {self.get_log_type_display()} - {self.campaign.name}"
    
    @staticmethod
    def log_campaign_created(campaign, user=None):
        """Log de criação de campanha"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='created',
            severity='info',
            message=f'Campanha "{campaign.name}" criada',
            details={
                'rotation_mode': campaign.rotation_mode,
                'total_contacts': campaign.total_contacts,
                'instances_count': campaign.instances.count(),
            },
            created_by=user
        )
    
    @staticmethod
    def log_campaign_started(campaign, user=None):
        """Log de início de campanha"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='started',
            severity='info',
            message=f'Campanha "{campaign.name}" iniciada',
            details={
                'total_contacts': campaign.total_contacts,
                'rotation_mode': campaign.rotation_mode,
            },
            created_by=user
        )
    
    @staticmethod
    def log_campaign_paused(campaign, user=None):
        """Log de pausa de campanha"""
        try:
            return CampaignLog.objects.create(
                campaign=campaign,
                log_type='paused',
                severity='info',
                message=f'Campanha "{campaign.name}" pausada',
                details={
                    'total_contacts': campaign.total_contacts,
                    'messages_sent': campaign.messages_sent,
                    'messages_delivered': campaign.messages_delivered,
                },
                created_by=user
            )
        except Exception as e:
            # Se falhar, criar log simples sem tenant
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Erro ao criar log de pausa: {str(e)}")
            # Não falhar a operação principal por causa do log
            return None
    
    @staticmethod
    def log_campaign_resumed(campaign, user=None):
        """Log de retomada de campanha"""
        try:
            return CampaignLog.objects.create(
                campaign=campaign,
                log_type='resumed',
                severity='info',
                message=f'Campanha "{campaign.name}" retomada',
                details={
                    'total_contacts': campaign.total_contacts,
                    'messages_sent': campaign.messages_sent,
                    'messages_delivered': campaign.messages_delivered,
                },
                created_by=user
            )
        except Exception as e:
            # Se falhar, criar log simples sem tenant
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Erro ao criar log de retomada: {str(e)}")
            # Não falhar a operação principal por causa do log
            return None
    
    @staticmethod
    def log_message_sent(campaign, instance, contact, campaign_contact, duration_ms=None, message_content=None, whatsapp_message_id=None):
        """Log de mensagem enviada"""
        details = {
            'contact_id': str(contact.id),
            'contact_phone': contact.phone,
            'instance_id': str(instance.id),
            'instance_name': instance.friendly_name,
            'delivery_status': 'sent',  # Status inicial
            'delivery_timestamp': None,
        }
        
        # Adicionar conteúdo da mensagem se fornecido
        if message_content:
            details['message_content'] = message_content
            
        # Adicionar ID da mensagem WhatsApp se disponível
        if whatsapp_message_id:
            details['whatsapp_message_id'] = whatsapp_message_id
        
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='message_sent',
            severity='info',
            message=f'Mensagem enviada para {contact.name}',
            details=details,
            instance=instance,
            contact=contact,
            campaign_contact=campaign_contact,
            duration_ms=duration_ms,
            campaign_progress=campaign.progress_percentage,
            instance_health_score=instance.health_score
        )
    
    @staticmethod
    def log_message_delivered(campaign, instance, contact, campaign_contact, response_data=None):
        """Log de mensagem entregue"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='message_delivered',
            severity='info',
            message=f'Mensagem entregue para {contact.name}',
            details={
                'contact_id': str(contact.id),
                'contact_phone': contact.phone,
            },
            instance=instance,
            contact=contact,
            campaign_contact=campaign_contact,
            response_data=response_data,
            instance_health_score=instance.health_score
        )
    
    @staticmethod
    def log_message_delivered(campaign, instance, contact, campaign_contact):
        """Log de mensagem entregue"""
        from django.utils import timezone
        
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='message_delivered',
            severity='info',
            message=f'Mensagem entregue para {contact.name}',
            details={
                'contact_id': str(contact.id),
                'contact_phone': contact.phone,
                'delivered_at': timezone.now().isoformat(),
                'whatsapp_message_id': campaign_contact.whatsapp_message_id,
            },
            instance=instance,
            contact=contact,
            campaign_contact=campaign_contact
        )
    
    @staticmethod
    def log_message_read(campaign, instance, contact, campaign_contact):
        """Log de mensagem lida"""
        from django.utils import timezone
        
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='message_read',
            severity='info',
            message=f'Mensagem lida por {contact.name}',
            details={
                'contact_id': str(contact.id),
                'contact_phone': contact.phone,
                'read_at': timezone.now().isoformat(),
                'delivered_at': campaign_contact.delivered_at.isoformat() if campaign_contact.delivered_at else None,
                'whatsapp_message_id': campaign_contact.whatsapp_message_id,
            },
            instance=instance,
            contact=contact,
            campaign_contact=campaign_contact
        )
    
    @staticmethod
    def update_message_delivery_status(campaign_contact, status='delivered'):
        """Atualiza o status de entrega no log de mensagem enviada E cria log separado"""
        try:
            from django.utils import timezone
            
            # Buscar o log de mensagem enviada mais recente para este campaign_contact
            log = CampaignLog.objects.filter(
                campaign_contact=campaign_contact,
                log_type='message_sent'
            ).order_by('-created_at').first()
            
            if log:
                # Atualizar details com novo status
                details = log.details or {}
                details['delivery_status'] = status
                details['delivery_timestamp'] = timezone.now().isoformat()
                
                log.details = details
                
                # Atualizar mensagem também
                if status == 'delivered':
                    log.message = f'Mensagem enviada e entregue para {log.contact.name if log.contact else "contato"}'
                elif status == 'read':
                    log.message = f'Mensagem enviada, entregue e lida por {log.contact.name if log.contact else "contato"}'
                
                log.save(update_fields=['message', 'details'])
                
                # 🆕 CRIAR LOG SEPARADO para o novo status (além de atualizar o original)
                if status == 'delivered':
                    CampaignLog.log_message_delivered(
                        campaign=log.campaign,
                        instance=log.instance,
                        contact=log.contact,
                        campaign_contact=campaign_contact
                    )
                elif status == 'read':
                    CampaignLog.log_message_read(
                        campaign=log.campaign,
                        instance=log.instance,
                        contact=log.contact,
                        campaign_contact=campaign_contact
                    )
                
        except Exception as e:
            pass
    
    @staticmethod
    def log_message_failed(campaign, instance, contact, campaign_contact, error_msg, request_data=None, response_data=None, http_status=None):
        """Log de falha no envio"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='message_failed',
            severity='error',
            message=f'Falha ao enviar para {contact.name}: {error_msg}',
            details={
                'contact_id': str(contact.id),
                'contact_phone': contact.phone,
                'error': error_msg,
            },
            instance=instance,
            contact=contact,
            campaign_contact=campaign_contact,
            request_data=request_data,
            response_data=response_data,
            http_status=http_status,
            instance_health_score=instance.health_score
        )
    
    @staticmethod
    def log_instance_selected(campaign, instance, reason=''):
        """Log de seleção de instância (rotação)"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='instance_selected',
            severity='info',
            message=f'Instância "{instance.friendly_name}" selecionada para envio',
            details={
                'instance_id': str(instance.id),
                'instance_name': instance.friendly_name,
                'health_score': instance.health_score,
                'msgs_sent_today': instance.msgs_sent_today,
                'reason': reason,
            },
            instance=instance,
            instance_health_score=instance.health_score
        )
    
    @staticmethod
    def log_instance_paused(campaign, instance, reason=''):
        """Log de pausa de instância"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='instance_paused',
            severity='warning',
            message=f'Instância "{instance.friendly_name}" pausada',
            details={
                'instance_id': str(instance.id),
                'health_score': instance.health_score,
                'consecutive_errors': instance.consecutive_errors,
                'reason': reason,
            },
            instance=instance,
            instance_health_score=instance.health_score
        )
    
    @staticmethod
    def log_limit_reached(campaign, instance, limit_type='daily'):
        """Log de limite atingido"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='limit_reached',
            severity='warning',
            message=f'Limite {limit_type} atingido para instância "{instance.friendly_name}"',
            details={
                'instance_id': str(instance.id),
                'limit_type': limit_type,
                'msgs_sent_today': instance.msgs_sent_today,
            },
            instance=instance
        )
    
    @staticmethod
    def log_health_issue(campaign, instance, issue_description):
        """Log de problema de saúde"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='health_issue',
            severity='warning',
            message=f'Problema de saúde detectado em "{instance.friendly_name}"',
            details={
                'instance_id': str(instance.id),
                'health_score': instance.health_score,
                'issue': issue_description,
            },
            instance=instance,
            instance_health_score=instance.health_score
        )
    
    @staticmethod
    def log_error(campaign, error_msg, details=None, severity='error'):
        """Log genérico de erro"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='error',
            severity=severity,
            message=error_msg,
            details=details or {}
        )
    
    @staticmethod
    def log_notification_created(campaign, contact, notification, message_content):
        """Log de notificação criada"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='notification_created',
            severity='info',
            message=f'Contato {contact.name} respondeu na campanha',
            details={
                'contact_id': str(contact.id),
                'contact_phone': contact.phone,
                'notification_id': str(notification.id),
                'message_preview': message_content[:100] + '...' if len(message_content) > 100 else message_content,
            },
            contact=contact
        )
    
    @staticmethod
    def log_notification_read(campaign, contact, notification, user=None):
        """Log de notificação lida"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='notification_read',
            severity='info',
            message=f'Notificação de {contact.name} marcada como lida',
            details={
                'contact_id': str(contact.id),
                'contact_phone': contact.phone,
                'notification_id': str(notification.id),
                'read_by': user.email if user else None,
            },
            contact=contact,
            created_by=user
        )
    
    @staticmethod
    def log_notification_reply(campaign, contact, notification, reply_message, user=None):
        """Log de resposta enviada"""
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='notification_reply',
            severity='info',
            message=f'Resposta enviada para {contact.name}',
            details={
                'contact_id': str(contact.id),
                'contact_phone': contact.phone,
                'notification_id': str(notification.id),
                'reply_preview': reply_message[:100] + '...' if len(reply_message) > 100 else reply_message,
                'sent_by': user.email if user else None,
            },
            contact=contact,
            created_by=user
        )


class CampaignNotification(models.Model):
    """
    Notificações de respostas de contatos em campanhas
    """
    NOTIFICATION_TYPES = [
        ('response', 'Resposta do Contato'),
        ('delivery', 'Entrega Confirmada'),
        ('read', 'Mensagem Lida'),
    ]
    
    STATUS_CHOICES = [
        ('unread', 'Não Lida'),
        ('read', 'Lida'),
        ('replied', 'Respondida'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, related_name='campaign_notifications')
    campaign = models.ForeignKey('campaigns.Campaign', on_delete=models.CASCADE, related_name='notifications')
    contact = models.ForeignKey('contacts.Contact', on_delete=models.CASCADE, related_name='campaign_notifications')
    campaign_contact = models.ForeignKey('campaigns.CampaignContact', on_delete=models.CASCADE, related_name='notifications')
    instance = models.ForeignKey('notifications.WhatsAppInstance', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    
    # Dados da notificação
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='response')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unread')
    
    # Mensagem recebida
    received_message = models.TextField(help_text="Mensagem recebida do contato")
    received_timestamp = models.DateTimeField(auto_now_add=True)
    
    # Resposta enviada (se houver)
    sent_reply = models.TextField(blank=True, null=True, help_text="Resposta enviada pelo usuário")
    sent_timestamp = models.DateTimeField(blank=True, null=True)
    sent_by = models.ForeignKey('authn.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_replies')
    
    # Metadados
    whatsapp_message_id = models.CharField(max_length=255, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['contact', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
        verbose_name = 'Notificação de Campanha'
        verbose_name_plural = 'Notificações de Campanhas'
    
    def __str__(self):
        return f"{self.contact.name} - {self.campaign.name} ({self.get_status_display()})"
    
    def mark_as_read(self, user=None):
        """Marca notificação como lida"""
        self.status = 'read'
        self.save(update_fields=['status', 'updated_at'])
        
        # Log da ação
        CampaignLog.log_notification_read(
            campaign=self.campaign,
            contact=self.contact,
            notification=self,
            user=user
        )
    
    def mark_as_replied(self, reply_message, user):
        """Marca notificação como respondida"""
        from django.utils import timezone
        self.status = 'replied'
        self.sent_reply = reply_message
        self.sent_timestamp = timezone.now()
        self.sent_by = user
        self.save(update_fields=['status', 'sent_reply', 'sent_timestamp', 'sent_by', 'updated_at'])
        
        # Log da resposta
        CampaignLog.log_notification_reply(
            campaign=self.campaign,
            contact=self.contact,
            notification=self,
            reply_message=reply_message,
            user=user
        )
    
    def mark_as_failed(self, user, error_message=None):
        """Marca notificação como falhou ao responder"""
        from django.utils import timezone
        self.status = 'read'  # Volta para read se falhou
        self.save(update_fields=['status', 'updated_at'])
        
        # Log do erro
        CampaignLog.log_error(
            campaign=self.campaign,
            error_msg=f"Falha ao enviar resposta para {self.contact.name}: {error_message or 'Erro desconhecido'}"
        )


# Métodos adicionais para logs estruturados
class CampaignLogManager:
    """Manager para logs estruturados de campanha"""
    
    @staticmethod
    def log_worker_started(campaign, worker_info=None):
        """Log de worker iniciado"""
        print(f"🚀 [WORKER] Iniciando worker para campanha: {campaign.name}")
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='worker_started',
            severity='info',
            message='Worker iniciado para processar campanha',
            details={
                'worker_info': worker_info or {},
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @staticmethod
    def log_batch_started(campaign, batch_size, batch_number):
        """Log de início de lote"""
        print(f"📦 [BATCH] Iniciando lote {batch_number} com {batch_size} mensagens - Campanha: {campaign.name}")
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='batch_started',
            severity='info',
            message=f'Iniciando lote {batch_number} com {batch_size} mensagens',
            details={
                'batch_size': batch_size,
                'batch_number': batch_number,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @staticmethod
    def log_batch_completed(campaign, batch_number, results):
        """Log de conclusão de lote"""
        print(f"✅ [BATCH] Lote {batch_number} concluído: {results['sent']} enviadas, {results['failed']} falhas - Campanha: {campaign.name}")
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='batch_completed',
            severity='info',
            message=f'Lote {batch_number} concluído: {results["sent"]} enviadas, {results["failed"]} falhas',
            details={
                'batch_number': batch_number,
                'results': results,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @staticmethod
    def log_disparo_started(campaign, contact, instance, message_content):
        """Log de início de disparo individual"""
        print(f"🎯 [DISPARO] Iniciando disparo para {contact.name} via {instance.friendly_name} - Campanha: {campaign.name}")
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='disparo_started',
            severity='info',
            message=f'Iniciando disparo para {contact.name} via {instance.friendly_name}',
            details={
                'contact_id': str(contact.id),
                'contact_name': contact.name,
                'contact_phone': contact.phone,
                'instance_id': str(instance.id),
                'instance_name': instance.friendly_name,
                'message_preview': message_content[:100] + '...' if len(message_content) > 100 else message_content,
                'timestamp': timezone.now().isoformat()
            },
            contact=contact
        )
    
    @staticmethod
    def log_disparo_timeout(campaign, contact, instance, elapsed_time):
        """Log de timeout de disparo"""
        print(f"⏰ [TIMEOUT] Timeout no disparo para {contact.name}: {elapsed_time:.1f}s - Campanha: {campaign.name}")
        return CampaignLog.objects.create(
            campaign=campaign,
            log_type='disparo_timeout',
            severity='warning',
            message=f'Timeout no disparo para {contact.name}: {elapsed_time:.1f}s',
            details={
                'contact_id': str(contact.id),
                'contact_name': contact.name,
                'contact_phone': contact.phone,
                'instance_id': str(instance.id),
                'instance_name': instance.friendly_name,
                'elapsed_time': elapsed_time,
                'timestamp': timezone.now().isoformat()
            },
            contact=contact
        )
