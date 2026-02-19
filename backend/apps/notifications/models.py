from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_cryptography.fields import encrypt
from apps.tenancy.models import Tenant
import uuid

User = get_user_model()


# ========== SISTEMA DE NOTIFICAÇÕES PERSONALIZADAS ==========

class UserNotificationPreferences(models.Model):
    """
    Preferências de notificação individuais do usuário.
    Cada usuário pode configurar suas próprias notificações.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Usuário'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='user_notification_preferences',
        verbose_name='Tenant'
    )
    
    # Horários de resumo diário
    daily_summary_enabled = models.BooleanField(
        default=False,
        verbose_name='Resumo diário ativado'
    )
    daily_summary_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do resumo diário',
        help_text='Ex: 07:00'
    )
    last_daily_summary_sent_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data do último resumo enviado',
        help_text='Usado para evitar duplicação entre workers'
    )
    
    # Lembrete de agenda
    agenda_reminder_enabled = models.BooleanField(
        default=False,
        verbose_name='Lembrete de agenda ativado'
    )
    agenda_reminder_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do lembrete de agenda',
        help_text='Ex: 08:00'
    )
    
    # Tipos de notificação
    notify_pending = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas pendentes'
    )
    notify_in_progress = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas em progresso'
    )
    notify_status_changes = models.BooleanField(
        default=True,
        verbose_name='Notificar mudanças de status'
    )
    notify_completed = models.BooleanField(
        default=False,
        verbose_name='Notificar tarefas concluídas'
    )
    notify_overdue = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas atrasadas'
    )
    
    # Canais de notificação
    notify_via_whatsapp = models.BooleanField(
        default=True,
        verbose_name='Notificar via WhatsApp'
    )
    notify_via_websocket = models.BooleanField(
        default=True,
        verbose_name='Notificar via WebSocket'
    )
    notify_via_email = models.BooleanField(
        default=False,
        verbose_name='Notificar via Email'
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications_user_notification_preferences'
        verbose_name = 'Preferência de Notificação do Usuário'
        verbose_name_plural = 'Preferências de Notificação dos Usuários'
        unique_together = ['user', 'tenant']
        indexes = [
            models.Index(fields=['user', 'tenant']),
            models.Index(fields=['daily_summary_enabled', 'daily_summary_time']),
            models.Index(fields=['agenda_reminder_enabled', 'agenda_reminder_time']),
        ]
    
    def __str__(self):
        return f'Notificações de {self.user.email}'


class DepartmentNotificationPreferences(models.Model):
    """
    Preferências de notificação do departamento para gestores.
    Apenas gestores do departamento podem configurar.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.OneToOneField(
        'authn.Department',
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Departamento'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='department_notification_preferences',
        verbose_name='Tenant'
    )
    
    # Horários de resumo diário
    daily_summary_enabled = models.BooleanField(
        default=False,
        verbose_name='Resumo diário ativado'
    )
    daily_summary_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do resumo diário',
        help_text='Ex: 07:00'
    )
    last_daily_summary_sent_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data do último resumo enviado',
        help_text='Usado para evitar duplicação entre workers'
    )
    
    # Lembrete de agenda
    agenda_reminder_enabled = models.BooleanField(
        default=False,
        verbose_name='Lembrete de agenda ativado'
    )
    agenda_reminder_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Horário do lembrete de agenda',
        help_text='Ex: 08:00'
    )
    
    # Tipos de notificação
    notify_pending = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas pendentes'
    )
    notify_in_progress = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas em progresso'
    )
    notify_status_changes = models.BooleanField(
        default=True,
        verbose_name='Notificar mudanças de status'
    )
    notify_completed = models.BooleanField(
        default=False,
        verbose_name='Notificar tarefas concluídas'
    )
    notify_overdue = models.BooleanField(
        default=True,
        verbose_name='Notificar tarefas atrasadas'
    )
    
    # Filtros avançados para gestores
    notify_only_critical = models.BooleanField(
        default=False,
        verbose_name='Apenas tarefas críticas',
        help_text='Se True, apenas tarefas com prioridade alta ou atrasadas'
    )
    notify_only_assigned = models.BooleanField(
        default=False,
        verbose_name='Apenas tarefas atribuídas',
        help_text='Se True, apenas tarefas com assigned_to definido'
    )
    max_tasks_per_notification = models.IntegerField(
        default=20,
        verbose_name='Máximo de tarefas por notificação',
        help_text='Limite para evitar mensagens muito longas'
    )
    
    # Canais de notificação
    notify_via_whatsapp = models.BooleanField(
        default=True,
        verbose_name='Notificar via WhatsApp'
    )
    notify_via_websocket = models.BooleanField(
        default=True,
        verbose_name='Notificar via WebSocket'
    )
    notify_via_email = models.BooleanField(
        default=False,
        verbose_name='Notificar via Email'
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_department_notification_preferences',
        verbose_name='Criado por'
    )
    
    class Meta:
        db_table = 'notifications_department_notification_preferences'
        verbose_name = 'Preferência de Notificação do Departamento'
        verbose_name_plural = 'Preferências de Notificação dos Departamentos'
        unique_together = ['department', 'tenant']
        indexes = [
            models.Index(fields=['department', 'tenant']),
            models.Index(fields=['daily_summary_enabled', 'daily_summary_time']),
            models.Index(fields=['agenda_reminder_enabled', 'agenda_reminder_time']),
        ]
    
    def __str__(self):
        return f'Notificações de {self.department.name}'


class NotificationTemplate(models.Model):
    """Template for email and WhatsApp notifications."""
    
    TYPE_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    CATEGORY_CHOICES = [
        ('welcome', 'Boas-vindas'),
        ('plan_change', 'Alteração de Plano'),
        ('payment_due', 'Vencimento de Pagamento'),
        ('payment_success', 'Pagamento Confirmado'),
        ('payment_failed', 'Falha no Pagamento'),
        ('trial_ending', 'Fim do Período Trial'),
        ('account_suspended', 'Conta Suspensa'),
        ('account_reactivated', 'Conta Reativada'),
        ('password_reset', 'Redefinição de Senha'),
        ('custom', 'Personalizado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='notification_templates',
        null=True,
        blank=True,
        help_text="Tenant específico (null = template global)"
    )
    name = models.CharField(max_length=100, help_text="Nome identificador do template")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    
    # Email fields
    subject = models.CharField(max_length=200, blank=True, help_text="Assunto do email")
    
    # Content (supports both email and WhatsApp)
    content = models.TextField(
        help_text="Conteúdo do template. Use {{variavel}} para variáveis dinâmicas"
    )
    
    # HTML content (only for emails)
    html_content = models.TextField(
        blank=True,
        help_text="Conteúdo HTML do email (opcional)"
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    is_global = models.BooleanField(
        default=False,
        help_text="Template global (disponível para todos os tenants)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_templates'
    )
    
    class Meta:
        db_table = 'notifications_template'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        ordering = ['-created_at']
        unique_together = [['tenant', 'name', 'type']]
    
    def __str__(self):
        tenant_name = self.tenant.name if self.tenant else 'Global'
        return f"{self.name} ({self.get_type_display()}) - {tenant_name}"
    
    def render(self, context):
        """Render template with context variables."""
        import re
        content = self.content
        html_content = self.html_content
        
        # Replace {{variable}} with context values
        for key, value in context.items():
            pattern = r'\{\{\s*' + key + r'\s*\}\}'
            content = re.sub(pattern, str(value), content)
            if html_content:
                html_content = re.sub(pattern, str(value), html_content)
        
        return {
            'subject': self.subject,
            'content': content,
            'html_content': html_content
        }


class WhatsAppInstance(models.Model):
    """WhatsApp instance configuration for notifications."""
    
    STATUS_CHOICES = [
        ('active', 'Ativa'),
        ('inactive', 'Inativa'),
        ('error', 'Erro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='whatsapp_instances',
        null=True,
        blank=True,
        help_text="Tenant específico (null = instância global)"
    )
    
    friendly_name = models.CharField(
        max_length=100,
        default='Instância WhatsApp',
        help_text="Nome amigável para o cliente (pode repetir entre clientes)"
    )
    instance_name = models.CharField(
        max_length=100,
        help_text="Nome da instância no Evolution API (UUID interno)"
    )
    
    # Evolution API config
    api_url = models.URLField(blank=True, null=True, help_text="URL da Evolution API (geralmente usa servidor global)")
    # API key específica da instância (retornada pela Evolution API ao criar)
    api_key = models.CharField(max_length=255, blank=True, null=True, help_text="API Key específica da instância")
    
    # Connection info
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Número do WhatsApp conectado"
    )
    qr_code = models.TextField(
        blank=True,
        help_text="QR Code para conexão (se necessário)"
    )
    qr_code_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o QR code expira"
    )
    connection_state = models.CharField(
        max_length=20,
        default='close',
        help_text="Estado da conexão (open, close, connecting)"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    last_check = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Instância padrão para notificações"
    )
    
    # Chat routing
    default_department = models.ForeignKey(
        'authn.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_instances',
        help_text="Departamento padrão para novas conversas desta instância (null = Inbox)"
    )
    
    # Campaign settings
    delay_min_seconds = models.IntegerField(
        default=20,
        help_text="Delay mínimo entre envios de campanha (segundos)"
    )
    delay_max_seconds = models.IntegerField(
        default=50,
        help_text="Delay máximo entre envios de campanha (segundos)"
    )
    evolution_instance_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nome da instância no Evolution (geralmente igual a instance_name)"
    )
    
    # Meta Cloud API (WhatsApp Cloud API) - quando integration_type == 'meta_cloud'
    INTEGRATION_TYPE_EVOLUTION = 'evolution'
    INTEGRATION_TYPE_META_CLOUD = 'meta_cloud'
    INTEGRATION_TYPE_CHOICES = [
        (INTEGRATION_TYPE_EVOLUTION, 'Evolution (QR)'),
        (INTEGRATION_TYPE_META_CLOUD, 'API oficial Meta'),
    ]
    integration_type = models.CharField(
        max_length=20,
        choices=INTEGRATION_TYPE_CHOICES,
        default=INTEGRATION_TYPE_EVOLUTION,
        help_text="Evolution (QR) ou API oficial Meta (Cloud API)"
    )
    phone_number_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Meta Phone Number ID (só para integration_type=meta_cloud)"
    )
    access_token = models.TextField(
        blank=True,
        null=True,
        help_text="Meta permanent/system user token (só para meta_cloud)"
    )
    business_account_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Meta WABA ID (opcional)"
    )
    app_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Meta App ID (opcional)"
    )
    access_token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiração do token Meta (se aplicável)"
    )
    
    # Health Tracking para Campanhas
    health_score = models.IntegerField(
        default=100,
        help_text="Score de saúde da instância (0-100)"
    )
    msgs_sent_today = models.IntegerField(
        default=0,
        help_text="Mensagens enviadas hoje"
    )
    msgs_delivered_today = models.IntegerField(
        default=0,
        help_text="Mensagens entregues hoje"
    )
    msgs_read_today = models.IntegerField(
        default=0,
        help_text="Mensagens lidas hoje"
    )
    msgs_failed_today = models.IntegerField(
        default=0,
        help_text="Mensagens com erro hoje"
    )
    consecutive_errors = models.IntegerField(
        default=0,
        help_text="Erros consecutivos"
    )
    last_success_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última mensagem enviada com sucesso"
    )
    last_health_update = models.DateTimeField(
        auto_now=True,
        help_text="Última atualização do health score"
    )
    health_last_reset = models.DateField(
        null=True,
        blank=True,
        help_text="Última vez que os contadores diários foram resetados"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_whatsapp_instances'
    )
    
    class Meta:
        db_table = 'notifications_whatsapp_instance'
        verbose_name = 'WhatsApp Instance'
        verbose_name_plural = 'WhatsApp Instances'
        ordering = ['-created_at']
    
    def __str__(self):
        tenant_name = self.tenant.name if self.tenant else 'Global'
        return f"{self.friendly_name} ({self.instance_name}) - {tenant_name}"
    
    @property
    def evolution_api_instance_name(self):
        """Nome usado nas chamadas à Evolution API (UUID). Preferir evolution_instance_name se preenchido."""
        return (self.evolution_instance_name or self.instance_name or '').strip()
    
    def generate_qr_code(self):
        """Generate QR code for connection."""
        if getattr(self, 'integration_type', None) == self.INTEGRATION_TYPE_META_CLOUD:
            return None  # no-op para API oficial Meta (sem QR)
        import requests
        from django.utils import timezone
        from datetime import timedelta
        from apps.connections.models import EvolutionConnection
        
        # Buscar servidor Evolution ativo do sistema (configuração global do admin)
        evolution_server = EvolutionConnection.objects.filter(
            is_active=True
        ).first()
        
        if not evolution_server:
            error_msg = (
                '❌ Nenhum servidor Evolution API configurado!\n\n'
                '📋 Passos para configurar:\n'
                '1. Acesse: Admin → Servidor de Instância\n'
                '2. Configure a URL e API Key do Evolution API\n'
                '3. Teste a conexão\n'
                '4. Volte aqui e tente novamente'
            )
            self.last_error = error_msg
            self.status = 'error'
            self.save()
            return None
        
        # SEMPRE usar URL e API Key do servidor global
        api_url = evolution_server.base_url
        system_api_key = evolution_server.api_key
        
        if not api_url:
            error_msg = f'❌ Servidor Evolution "{evolution_server.name}" sem URL configurada. Configure em Admin → Servidor de Instância'
            self.last_error = error_msg
            self.status = 'error'
            self.save()
            return None
        
        if not system_api_key:
            error_msg = f'❌ Servidor Evolution "{evolution_server.name}" sem API Key configurada. Configure em Admin → Servidor de Instância'
            self.last_error = error_msg
            self.status = 'error'
            self.save()
            return None
        
        # Salvar api_url da instância para referência
        if not self.api_url:
            self.api_url = api_url
            self.save()
        
        try:
            # ETAPA 1: Verificar se instância já existe no Evolution API
            check_response = requests.get(
                f"{api_url}/instance/fetchInstances",
                headers={'apikey': system_api_key},
                params={'instanceName': self.instance_name},
                timeout=10
            )
            
            instance_exists = False
            if check_response.status_code == 200:
                instances = check_response.json()
                # Verificar se nossa instância está na lista
                if isinstance(instances, list):
                    instance_exists = any(
                        inst.get('instance', {}).get('instanceName') == self.instance_name or
                        inst.get('name') == self.instance_name
                        for inst in instances
                    )
                print(f"🔍 Verificação: instância '{self.instance_name}' {'existe' if instance_exists else 'não existe'} no Evolution")
            
            # Se não tem API key E instância não existe, criar no Evolution API
            if not self.api_key and not instance_exists:
                print(f"🆕 Criando nova instância no Evolution: {self.instance_name}")
                create_response = requests.post(
                    f"{api_url}/instance/create",
                    headers={
                        'Content-Type': 'application/json',
                        'apikey': system_api_key,
                    },
                    json={
                        'instanceName': self.instance_name,
                        'qrcode': True,
                        'integration': 'WHATSAPP-BAILEYS',
                        # ❌ REMOVIDO: webhook por instância (usa webhook global da Evolution)
                        # Produto Notifications desabilitado - usar Flow Chat
                        # 'webhook': {
                        #     'enabled': True,
                        #     'url': f"{getattr(settings, 'BASE_URL', '')}/api/notifications/webhook/",
                        #     'webhook_by_events': False,
                        #     'webhook_base64': True,
                        #     'events': [...]
                        # },
                        'settings': {
                            'reject_call': True,
                            'msg_call': 'Desculpe, não atendemos chamadas. Use mensagens de texto!',
                            'groups_ignore': False,
                            'always_online': False,
                            'read_messages': False,
                            'read_status': False,
                            'sync_full_history': False,
                        }
                    },
                    timeout=30
                )
                
                if create_response.status_code in [200, 201]:
                    create_data = create_response.json()
                    print(f"📋 Resposta criar instância: {create_data}")
                    
                    # Capturar API key específica (múltiplas possibilidades - padrão whatsapp-orchestrator)
                    instance_api_key = (
                        create_data.get('instance', {}).get('apikey') or
                        create_data.get('instance', {}).get('apiKey') or
                        create_data.get('apikey') or
                        create_data.get('apiKey') or
                        create_data.get('key')
                    )
                    
                    if instance_api_key:
                        self.api_key = instance_api_key
                        self.save()
                        print(f"✅ API key específica capturada: {instance_api_key[:20]}...")
                        
                        # Log
                        WhatsAppConnectionLog.objects.create(
                            instance=self,
                            action='created',
                            details=f'Instância criada com API key específica',
                            user=self.created_by
                        )
                    else:
                        print(f"⚠️  API key não retornada, continuando sem ela...")
                        # Continuar mesmo sem API key (será buscada depois se necessário)
                    
                    # 🆕 ETAPA 1.5: Atualizar webhook após criação (garantir configuração completa)
                    print(f"🔧 Configurando webhook completo...")
                    self._update_webhook_after_create(api_url, system_api_key)
                    
                else:
                    self.last_error = f'Erro ao criar instância (Status {create_response.status_code}): {create_response.text}'
                    self.save()
                    return None
            elif instance_exists:
                print(f"♻️  Instância já existe no Evolution, pulando criação")
                # 🆕 Atualizar webhook mesmo se instância já existe
                print(f"🔧 Atualizando webhook da instância existente...")
                self._update_webhook_after_create(api_url, system_api_key)
            
            # ETAPA 2: Gerar QR code usando API MASTER (padrão whatsapp-orchestrator)
            # IMPORTANTE: Usar API MASTER, não API da instância!
            response = requests.get(
                f"{api_url}/instance/connect/{self.instance_name}",
                headers={'apikey': system_api_key},  # ← API MASTER
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                qr_code = data.get('base64', '')
                
                if qr_code:
                    self.qr_code = qr_code
                    # QR code expires in 5 minutes
                    self.qr_code_expires_at = timezone.now() + timedelta(minutes=5)
                    self.connection_state = 'connecting'
                    self.save()
                    
                    # Log the QR code generation
                    WhatsAppConnectionLog.objects.create(
                        instance=self,
                        action='qr_generated',
                        details='QR code gerado para conexão',
                        user=self.created_by
                    )
                    
                    return qr_code
                else:
                    self.last_error = f'QR code não retornado. Resposta: {response.text}'
                    self.save()
                    return None
            else:
                self.last_error = f'Erro ao gerar QR code (Status {response.status_code}): {response.text}'
                self.save()
                return None
            
        except Exception as e:
            self.last_error = f'Exceção ao gerar QR code: {str(e)}'
            self.save()
            return None
    
    def _update_webhook_after_create(self, api_url, api_key):
        """
        Atualiza webhook após criação da instância (uso interno).
        Garante que todos eventos e base64 estão ativos.
        """
        import requests
        from django.conf import settings
        
        try:
            # ❌ REMOVIDO: webhook por instância (usa webhook global da Evolution)
            # Produto Notifications desabilitado - usar Flow Chat
            # webhook_config = {
            #     'enabled': True,
            #     'url': f"{getattr(settings, 'BASE_URL', '')}/api/notifications/webhook/",
            #     'webhookByEvents': False,
            #     'webhookBase64': True,
            #     'events': [...]
            # }
            
            # Usar webhook global da Evolution - NÃO configurar por instância
            print(f"   ⏭️ PULANDO configuração de webhook (usando webhook global da Evolution)")
            return True  # Retorna sucesso sem configurar webhook por instância
                
        except Exception as e:
            print(f"   ❌ EXCEÇÃO ao configurar webhook!")
            print(f"   ⚠️  Erro: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_webhook_config(self):
        """
        Atualiza configuração de webhook em instância existente (uso público).
        Pode ser chamado via API ou admin action.
        """
        import requests
        from django.conf import settings
        from apps.connections.models import EvolutionConnection
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server or not evolution_server.base_url or not evolution_server.api_key:
            self.last_error = 'Servidor Evolution não configurado'
            self.save()
            return False
        
        api_url = evolution_server.base_url.rstrip('/')
        api_key = evolution_server.api_key
        
        print(f"🔧 Atualizando webhook para instância: {self.instance_name}")
        
        return self._update_webhook_after_create(api_url, api_key)
    
    def check_connection_status(self):
        """
        Check connection status and update phone number if connected.
        Usa API MASTER para operações admin (padrão whatsapp-orchestrator).
        Usa /instance/fetchInstances para obter TODOS os dados de uma vez.
        """
        if getattr(self, 'integration_type', None) == self.INTEGRATION_TYPE_META_CLOUD:
            return True  # no-op para API oficial Meta (conexão é sempre via token)
        import requests
        from apps.connections.models import EvolutionConnection
        
        # Buscar servidor Evolution global
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server or not evolution_server.base_url or not evolution_server.api_key:
            self.last_error = 'Servidor Evolution não configurado'
            self.save()
            return False
        
        api_url = evolution_server.base_url
        api_master = evolution_server.api_key  # ← API MASTER
        api_instance_name = self.evolution_api_instance_name or self.instance_name
        
        print(f"🔍 Verificando status da instância {api_instance_name}")
        print(f"   URL: {api_url}/instance/connectionState/{api_instance_name}")
            
        try:
            # MÉTODO 1: Usar connectionState específico (mais rápido e direto)
            # Referência: https://doc.evolution-api.com/v2/api-reference/instance-controller/connection-state
            response = requests.get(
                f"{api_url}/instance/connectionState/{api_instance_name}",
                headers={'apikey': api_master},  # ← API MASTER
                timeout=10
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text[:300]}")
            
            if response.status_code == 200:
                data = response.json()
                instance_data = data.get('instance', {})
                # Evolution pode retornar state no topo ou dentro de instance
                state = data.get('state') or instance_data.get('state') or 'close'
                print(f"   📱 State: {state}")
                
                # Atualizar estado
                if state == 'open':
                    self.connection_state = 'open'
                    self.status = 'active'
                    print(f"   ✅ Instância CONECTADA!")
                    
                    # MÉTODO 2: Buscar dados completos em fetchInstances
                    # Referência: https://doc.evolution-api.com/v2/api-reference/instance-controller/fetch-instances
                    fetch_response = requests.get(
                        f"{api_url}/instance/fetchInstances",
                        headers={'apikey': api_master},
                        timeout=10
                    )
                    
                    if fetch_response.status_code == 200:
                        instances_data = fetch_response.json()
                        print(f"   📋 Buscando dados completos em fetchInstances...")
                        print(f"   🔍 Total retornado: {len(instances_data)}")
                        
                        found_in_fetch = False
                        for inst_item in instances_data:
                            # Evolution API retorna objeto direto, não dentro de 'instance'
                            inst_name = inst_item.get('name', 'N/A')
                            if inst_name == api_instance_name or inst_name == self.instance_name:
                                instance_data = inst_item
                                found_in_fetch = True
                                print(f"   ✅ Encontrada em fetchInstances!")
                                print(f"   📋 Dados completos: {instance_data}")
                                
                                # Pegar número de telefone (ownerJid)
                                owner_jid = instance_data.get('ownerJid', '')
                                # Extrair número (remover @s.whatsapp.net)
                                phone = owner_jid.replace('@s.whatsapp.net', '') if owner_jid else ''
                                print(f"   📞 ownerJid: {owner_jid}")
                                print(f"   📞 Phone extraído: {phone}")
                                
                                # Pegar API key (token)
                                if not self.api_key:
                                    api_key = instance_data.get('token')
                                    if api_key:
                                        self.api_key = api_key
                                        print(f"   🔑 API Key (token) capturada: {api_key[:20]}...")
                                
                                if phone:
                                    old_phone = self.phone_number
                                    self.phone_number = phone
                                    
                                    if not old_phone:
                                        # Log da conexão (só primeira vez)
                                        WhatsAppConnectionLog.objects.create(
                                            instance=self,
                                            action='connected',
                                            details=f'Instância conectada com número {phone}',
                                            user=self.created_by
                                        )
                                        print(f"   ✅ Número salvo: {phone}")
                                else:
                                    print(f"   ℹ️  Número já estava salvo: {old_phone}")
                                break
                        
                        if not found_in_fetch:
                            print(f"   ⚠️  Instância não encontrada em fetchInstances (pode demorar alguns segundos para indexar)")
                    
                    self.last_error = ''
                elif state == 'connecting':
                    self.connection_state = 'connecting'
                    self.status = 'inactive'
                    print(f"   ⏳ Instância ainda conectando...")
                else:
                    self.connection_state = 'close'
                    self.status = 'inactive'
                    print(f"   ❌ Instância desconectada")
                
                self.last_check = timezone.now()
                self.save()
                return True
                
            else:
                print(f"   ❌ Erro ao buscar instâncias: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.last_error = f'Erro {response.status_code}: {response.text[:200]}'
                self.save()
                return False
            
        except Exception as e:
            print(f"   ⚠️  Exceção ao verificar status: {str(e)}")
            import traceback
            traceback.print_exc()
            self.last_error = str(e)
            self.save()
            return False
    
    def disconnect(self, user=None):
        """
        Disconnect the instance.
        Usa API MASTER para operações admin (padrão whatsapp-orchestrator).
        """
        if getattr(self, 'integration_type', None) == self.INTEGRATION_TYPE_META_CLOUD:
            return True  # no-op para API oficial Meta
        import requests
        from apps.connections.models import EvolutionConnection
        
        # Buscar servidor Evolution global
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server or not evolution_server.base_url or not evolution_server.api_key:
            self.last_error = 'Servidor Evolution não configurado'
            self.save()
            return False
        
        api_url = evolution_server.base_url
        api_master = evolution_server.api_key  # ← API MASTER
        
        try:
            response = requests.delete(
                f"{api_url}/instance/logout/{self.instance_name}",
                headers={'apikey': api_master},  # ← API MASTER (não da instância!)
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                self.connection_state = 'close'
                self.phone_number = ''
                self.qr_code = ''
                self.qr_code_expires_at = None
                self.status = 'inactive'
                self.save()
                
                # Log the disconnection
                WhatsAppConnectionLog.objects.create(
                    instance=self,
                    action='disconnected',
                    details='Instância desconectada',
                    user=user
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.last_error = str(e)
            self.save()
            return False
    
    def check_status(self):
        """
        Check instance status via Evolution API (for Celery tasks).
        Usa API MASTER para operações admin (padrão whatsapp-orchestrator).
        """
        import requests
        from apps.connections.models import EvolutionConnection
        
        # Buscar servidor Evolution global
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server or not evolution_server.base_url or not evolution_server.api_key:
            self.last_error = 'Servidor Evolution não configurado'
            self.status = 'error'
            self.connection_state = 'error'
            self.save()
            return False
        
        api_url = evolution_server.base_url
        api_master = evolution_server.api_key  # ← API MASTER
        api_instance_name = self.evolution_api_instance_name or self.instance_name
        
        try:
            response = requests.get(
                f"{api_url}/instance/connectionState/{api_instance_name}",
                headers={'apikey': api_master},  # ← API MASTER (não da instância!)
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                instance_data = data.get('instance', {})
                # Evolution pode retornar state no topo ou dentro de instance
                state = data.get('state') or instance_data.get('state') or 'close'
                
                if state == 'open':
                    self.status = 'active'
                    self.connection_state = 'open'
                    self.last_error = ''
                    self.last_check = timezone.now()
                    self.save()
                    return True
                else:
                    self.status = 'inactive'
                    self.connection_state = state
                    # Detectar problemas específicos
                    self._detect_specific_problems(response.text)
                    self.last_check = timezone.now()
                    self.save()
                    return False
            else:
                self.status = 'error'
                self.connection_state = 'error'
                self.last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                self._detect_specific_problems(response.text)
                self.last_check = timezone.now()
                self.save()
                return False
        
        except Exception as e:
            self.status = 'error'
            self.last_error = str(e)
            self.connection_state = 'error'
            self.last_check = timezone.now()
            self.save()
            return False

    def _detect_specific_problems(self, response_text: str):
        """
        Detecta problemas específicos baseado na resposta da API.
        """
        if not response_text:
            return
            
        response_lower = response_text.lower()
        
        # Problemas conhecidos
        if 'suspended' in response_lower or 'suspenso' in response_lower:
            self.last_error = 'Conta WhatsApp suspensa - verifique com o provedor'
        elif 'unauthorized' in response_lower or '401' in response_text:
            self.last_error = 'API Key inválida ou expirada'
        elif 'forbidden' in response_lower or '403' in response_text:
            self.last_error = 'Acesso negado - verifique permissões da API'
        elif 'not found' in response_lower or '404' in response_text:
            self.last_error = 'Instância não encontrada no servidor Evolution'
        elif 'timeout' in response_lower:
            self.last_error = 'Timeout na conexão - servidor Evolution indisponível'
        elif 'connection closed' in response_lower:
            self.last_error = 'Conexão fechada - WhatsApp desconectado'
        elif 'instance not connected' in response_lower:
            self.last_error = 'Instância não conectada - gere novo QR Code'
        elif 'phone not registered' in response_lower:
            self.last_error = 'Número não registrado no WhatsApp'
    
    # ========== Health Tracking Methods ==========
    
    def reset_daily_counters_if_needed(self):
        """Reseta contadores diários se mudou de dia"""
        from datetime import date
        today = date.today()
        
        if self.health_last_reset != today:
            self.msgs_sent_today = 0
            self.msgs_delivered_today = 0
            self.msgs_read_today = 0
            self.msgs_failed_today = 0
            self.health_last_reset = today
            # Regenerar health score (bônus por novo dia)
            if self.health_score < 100:
                self.health_score = min(100, self.health_score + 10)
            self.save()
    
    def record_message_sent(self):
        """Registra envio de mensagem"""
        self.reset_daily_counters_if_needed()
        self.msgs_sent_today += 1
        self.save()
    
    def record_message_delivered(self):
        """Registra mensagem entregue"""
        from django.utils import timezone
        self.reset_daily_counters_if_needed()
        self.msgs_delivered_today += 1
        self.consecutive_errors = 0  # Reset erros consecutivos
        self.last_success_at = timezone.now()
        # Pequeno bônus no health
        if self.health_score < 100:
            self.health_score = min(100, self.health_score + 0.5)
        self.save()
    
    def record_message_read(self):
        """Registra mensagem lida"""
        self.reset_daily_counters_if_needed()
        self.msgs_read_today += 1
        # Bônus maior no health
        if self.health_score < 100:
            self.health_score = min(100, self.health_score + 1)
        self.save()
    
    def record_message_failed(self, error_msg=''):
        """Registra falha no envio"""
        self.reset_daily_counters_if_needed()
        self.msgs_failed_today += 1
        self.consecutive_errors += 1
        self.last_error = error_msg[:500]  # Limitar tamanho
        # Penalidade no health
        self.health_score = max(0, self.health_score - 10)
        self.save()
    
    @property
    def delivery_rate(self):
        """Taxa de entrega hoje (apenas entregues)"""
        if self.msgs_sent_today == 0:
            return 100.0
        return (self.msgs_delivered_today / self.msgs_sent_today) * 100
    
    @property
    def read_rate(self):
        """Taxa de leitura hoje"""
        if self.msgs_delivered_today == 0:
            return 0.0
        return (self.msgs_read_today / self.msgs_delivered_today) * 100
    
    @property
    def is_healthy(self):
        """Instância está saudável?"""
        return (
            self.health_score >= 50 and
            self.connection_state == 'open' and
            self.consecutive_errors < 5
        )
    
    @property
    def health_status(self):
        """Status de saúde textual"""
        if self.health_score >= 95:
            return 'excellent'  # Excelente
        elif self.health_score >= 80:
            return 'good'  # Boa
        elif self.health_score >= 50:
            return 'warning'  # Atenção
        else:
            return 'critical'  # Crítica
    
    def can_send_message(self, daily_limit=100):
        """Verifica se pode enviar mensagem (considerando limites)"""
        self.reset_daily_counters_if_needed()
        return (
            self.is_healthy and
            self.msgs_sent_today < daily_limit
        )


class WhatsAppTemplate(models.Model):
    """
    Template de mensagem WhatsApp (Meta Cloud API).
    Usado para envio fora da janela de 24h (apenas mensagens inbound do contato renovam a janela).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='whatsapp_templates',
        verbose_name='Tenant',
    )
    # Instância opcional: se preenchido, template disponível só para essa instância (Meta)
    wa_instance = models.ForeignKey(
        WhatsAppInstance,
        on_delete=models.CASCADE,
        related_name='templates',
        null=True,
        blank=True,
        verbose_name='Instância WhatsApp',
        help_text='Opcional. Se vazio, template disponível para qualquer instância Meta do tenant.',
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Nome (exibição)',
        help_text='Nome amigável para identificar o template no sistema',
    )
    template_id = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name='ID do template na Meta',
        help_text='Nome do template aprovado no Meta Business (ex: hello_world, nome_da_sua_empresa)',
    )
    language_code = models.CharField(
        max_length=10,
        default='pt_BR',
        verbose_name='Código do idioma',
        help_text='Código do idioma do template (ex: pt_BR, en_US)',
    )
    # Parâmetros do body: lista de textos na ordem (ex: ["{{1}}", "{{2}}"] substituídos pelo Meta)
    body_parameters_default = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Parâmetros padrão do body',
        help_text='Lista de valores padrão para variáveis do body (ex: ["Olá", "João"])',
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Ativo',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications_whatsapp_template'
        verbose_name = 'Template WhatsApp'
        verbose_name_plural = 'Templates WhatsApp'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'template_id', 'language_code'],
                name='notifications_wa_template_tenant_id_lang_uniq',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.template_id})"


class WhatsAppConnectionLog(models.Model):
    """Log of WhatsApp instance connection events."""
    
    ACTION_CHOICES = [
        ('created', 'Criada'),
        ('qr_generated', 'QR Code Gerado'),
        ('qr_scanned', 'QR Code Escaneado'),
        ('connected', 'Conectada'),
        ('disconnected', 'Desconectada'),
        ('error', 'Erro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(
        WhatsAppInstance,
        on_delete=models.CASCADE,
        related_name='connection_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Usuário que executou a ação"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications_whatsapp_connection_log'
        verbose_name = 'WhatsApp Connection Log'
        verbose_name_plural = 'WhatsApp Connection Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.instance.friendly_name} - {self.get_action_display()} ({self.created_at})"


class NotificationLog(models.Model):
    """Log of sent notifications."""
    
    TYPE_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('sent', 'Enviado'),
        ('failed', 'Falhou'),
        ('delivered', 'Entregue'),
        ('read', 'Lido'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='notification_logs'
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    whatsapp_instance = models.ForeignKey(
        WhatsAppInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    
    # Recipient
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_notifications'
    )
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    
    # Notification details
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    
    # External IDs (for tracking)
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID externo (Evolution message ID, etc.)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dados adicionais (context, tracking, etc.)"
    )
    
    class Meta:
        db_table = 'notifications_log'
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['recipient', 'created_at']),
            models.Index(fields=['type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} to {self.recipient.email} - {self.get_status_display()}"


class SMTPConfig(models.Model):
    """SMTP server configuration for sending emails."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='smtp_configs',
        null=True,
        blank=True,
        help_text="Tenant específico (null = configuração global)"
    )
    
    name = models.CharField(max_length=100, help_text="Nome identificador da configuração")
    
    # SMTP Settings
    host = models.CharField(max_length=255, help_text="Servidor SMTP (ex: smtp.gmail.com)")
    port = models.IntegerField(default=587, help_text="Porta SMTP (587 para TLS, 465 para SSL)")
    username = models.CharField(max_length=255, help_text="Usuário/Email para autenticação")
    password = encrypt(models.CharField(max_length=255, help_text="Senha do email"))
    use_tls = models.BooleanField(default=True, help_text="Usar TLS (Transport Layer Security)")
    use_ssl = models.BooleanField(default=False, help_text="Usar SSL (Secure Sockets Layer)")
    verify_ssl = models.BooleanField(
        default=True, 
        help_text="Verificar certificado SSL (desative se usar certificado auto-assinado)"
    )
    
    # Email Settings
    from_email = models.EmailField(help_text="Email do remetente")
    from_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nome do remetente (ex: Alrea Sense)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Configuração padrão para envio de emails"
    )
    
    # Test info
    last_test = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('success', 'Sucesso'),
            ('failed', 'Falhou'),
        ]
    )
    last_test_error = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_smtp_configs'
    )
    
    class Meta:
        db_table = 'notifications_smtp_config'
        verbose_name = 'SMTP Configuration'
        verbose_name_plural = 'SMTP Configurations'
        ordering = ['-created_at']
    
    def __str__(self):
        tenant_name = self.tenant.name if self.tenant else 'Global'
        return f"{self.name} ({self.host}) - {tenant_name}"
    
    def test_connection(self, test_email):
        """Test SMTP connection by sending a test email."""
        from django.core.mail import send_mail, EmailMessage
        from django.core.mail import get_connection
        from django.utils import timezone
        import socket
        import ssl
        
        try:
            # Set socket timeout to avoid hanging
            socket.setdefaulttimeout(30)
            
            # Disable SSL verification if needed
            ssl_context = None
            if not self.verify_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create email connection with these settings
            connection = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=self.use_tls,
                use_ssl=self.use_ssl,
                fail_silently=False,
                timeout=30,  # Add explicit timeout
            )
            
            # Apply SSL context if needed
            if ssl_context and hasattr(connection, 'ssl_context'):
                connection.ssl_context = ssl_context
            
            # Test connection first
            connection.open()
            
            # Send test email
            from_address = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
            
            email = EmailMessage(
                subject='Teste de Configuração SMTP - Alrea Sense',
                body='Este é um email de teste para verificar a configuração do servidor SMTP.\n\nSe você recebeu esta mensagem, a configuração está funcionando corretamente!',
                from_email=from_address,
                to=[test_email],
                connection=connection,
            )
            
            email.send(fail_silently=False)
            connection.close()
            
            # Update test status
            self.last_test = timezone.now()
            self.last_test_status = 'success'
            self.last_test_error = ''
            self.save()
            
            return True, 'Email de teste enviado com sucesso!'
        
        except socket.timeout:
            error_msg = f'Timeout ao conectar com {self.host}:{self.port}. Verifique se o servidor está acessível.'
            self.last_test = timezone.now()
            self.last_test_status = 'failed'
            self.last_test_error = error_msg
            self.save()
            return False, error_msg
            
        except ssl.SSLError as e:
            error_msg = f'Erro SSL: {str(e)}. Tente desabilitar "Verificar SSL" se usar certificado auto-assinado.'
            self.last_test = timezone.now()
            self.last_test_status = 'failed'
            self.last_test_error = error_msg
            self.save()
            return False, error_msg
            
        except Exception as e:
            # Update test status with error
            error_msg = str(e)
            self.last_test = timezone.now()
            self.last_test_status = 'failed'
            self.last_test_error = error_msg
            self.save()
            
            return False, error_msg

