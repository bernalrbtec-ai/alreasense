from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django_cryptography.fields import encrypt
from apps.tenancy.models import Tenant
import uuid

User = get_user_model()


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
    
    def generate_qr_code(self):
        """Generate QR code for connection."""
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
            # Se não tem API key, primeiro criar a instância no Evolution API
            if not self.api_key:
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
                        'webhook': {
                            'url': f"{getattr(settings, 'BASE_URL', '')}/api/notifications/webhook/",
                            'events': ['messages.upsert', 'connection.update']
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
                else:
                    self.last_error = f'Erro ao criar instância (Status {create_response.status_code}): {create_response.text}'
                    self.save()
                    return None
            
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
    
    def check_connection_status(self):
        """
        Check connection status and update phone number if connected.
        Usa API MASTER para operações admin (padrão whatsapp-orchestrator).
        """
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
        
        print(f"🔍 Verificando status da instância {self.instance_name}")
        print(f"   URL: {api_url}/instance/connectionState/{self.instance_name}")
            
        try:
            response = requests.get(
                f"{api_url}/instance/connectionState/{self.instance_name}",
                headers={'apikey': api_master},  # ← API MASTER (não da instância!)
                timeout=10
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
            if response.status_code == 200:
                data = response.json()
                state = data.get('state', 'close')
                
                if state == 'open':
                    self.connection_state = 'open'
                    self.status = 'active'
                    
                    # Tentar obter informações da instância para pegar o número
                    # Usar API MASTER (padrão whatsapp-orchestrator)
                    info_response = requests.get(
                        f"{api_url}/instance/fetchInstances",
                        headers={'apikey': api_master},  # ← API MASTER
                        timeout=10
                    )
                    
                    if info_response.status_code == 200:
                        instances_data = info_response.json()
                        for instance_info in instances_data:
                            if instance_info.get('instance', {}).get('instanceName') == self.instance_name:
                                phone = instance_info.get('instance', {}).get('owner')
                                if phone and not self.phone_number:
                                    self.phone_number = phone
                                    
                                    # Log the connection
                                    WhatsAppConnectionLog.objects.create(
                                        instance=self,
                                        action='connected',
                                        details=f'Instância conectada com número {phone}',
                                        user=self.created_by
                                    )
                                break
                    
                    self.last_error = ''
                else:
                    self.connection_state = 'close'
                    self.status = 'inactive'
                
                self.last_check = timezone.now()
                self.save()
                return True
            else:
                print(f"   ❌ Erro ao verificar status: {response.status_code} - {response.text[:200]}")
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
            self.save()
            return
        
        api_url = evolution_server.base_url
        api_master = evolution_server.api_key  # ← API MASTER
        
        try:
            response = requests.get(
                f"{api_url}/instance/connectionState/{self.instance_name}",
                headers={'apikey': api_master},  # ← API MASTER (não da instância!)
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                state = data.get('state', 'close')
                
                if state == 'open':
                    self.status = 'active'
                    self.connection_state = 'open'
                    self.last_error = ''
                else:
                    self.status = 'inactive'
                    self.connection_state = state
            else:
                self.status = 'error'
                self.last_error = f"HTTP {response.status_code}: {response.text[:100]}"
        
        except Exception as e:
            self.status = 'error'
            self.last_error = str(e)
        
        from django.utils import timezone
        self.last_check = timezone.now()
        self.save()


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

