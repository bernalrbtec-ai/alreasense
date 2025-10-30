# 📧 PLANO DE IMPLEMENTAÇÃO - CAMPANHAS POR EMAIL

> **Projeto:** ALREA Sense - Flow Campaigns  
> **Data:** 28 de Outubro de 2025  
> **Objetivo:** Expandir sistema de campanhas para suportar email além de WhatsApp  
> **Status:** 📋 Planejamento

---

## 📊 SUMÁRIO EXECUTIVO

### Visão Geral
Expandir o sistema de campanhas existente (atualmente WhatsApp) para suportar **envio de emails em massa** com:
- ✅ Tracking de entrega, abertura e cliques
- ✅ Controle de reputação e limites de envio
- ✅ Gerenciamento de bounces e unsubscribes
- ✅ Rotação de contas de envio (SMTP/API)
- ✅ Aproveitamento máximo da arquitetura existente

### Estimativa de Tempo
- **Mínimo:** 5-6 dias úteis
- **Realista:** 8-10 dias úteis
- **Com imprevistos:** 12-15 dias úteis

### Complexidade
- **Backend:** ⭐⭐⭐⭐ (Alta - integração com APIs, tracking)
- **Frontend:** ⭐⭐⭐ (Média - reutiliza componentes existentes)
- **Testes:** ⭐⭐⭐⭐ (Alta - deliverability é crítico)

---

## 🏗️ ANÁLISE DA ARQUITETURA ATUAL

### O que já existe e funciona (WhatsApp)

```python
# Estrutura Core do Sistema de Campanhas
Campaign                   # Modelo principal de campanha
├── CampaignMessage       # Múltiplas variações de mensagem
├── CampaignContact       # Tracking por contato (sent/delivered/read/failed)
├── CampaignLog           # Log detalhado de todas operações
├── CampaignNotification  # Respostas recebidas
└── Services
    ├── RotationService    # Rotação de instâncias WhatsApp
    ├── CampaignSender     # Envio e retry logic
    └── RabbitMQConsumer   # Processamento assíncrono
```

### Pontos fortes a aproveitar

1. **✅ Multi-tenancy robusto** - Cada cliente isolado
2. **✅ Sistema de filas RabbitMQ** - Processamento assíncrono escalável
3. **✅ Tracking granular** - `sent → delivered → read → failed`
4. **✅ Logs detalhados** - Auditoria completa com JSON fields
5. **✅ Rotação de "instâncias"** - Conceito reutilizável para contas SMTP
6. **✅ Rate limiting** - Intervalos configuráveis entre envios
7. **✅ Retry logic** - Backoff exponencial já implementado
8. **✅ Variáveis dinâmicas** - `{{nome}}`, `{{saudacao}}`, etc.
9. **✅ Contact model rico** - Email já está no modelo
10. **✅ Frontend React** - Componentes reutilizáveis

---

## 🎯 SERVIÇOS DE EMAIL RECOMENDADOS

### Comparação Técnica

| Serviço | Custo/mês | Envios/hora | Tracking | Reputação | API Quality | Recomendação |
|---------|-----------|-------------|----------|-----------|-------------|--------------|
| **SendGrid** | $15-90 | 40,000-200,000 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ **MELHOR** |
| **Resend** | $0-20 | 3,000-50,000 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Bom |
| **Postmark** | $15-1,750 | 10,000-1M+ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Excelente |
| **Mailgun** | $35-90 | 50,000-100,000 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⚠️ Médio |
| **AWS SES** | ~$0.10/1k | Ilimitado* | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⚠️ Complexo |
| **Brevo** | €0-69 | 20,000-350,000 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ Bom |

### 🏆 Recomendação: **SendGrid** (Principal) + **Resend** (Backup)

**Por quê?**

#### SendGrid (Principal)
```yaml
Prós:
  - API extremamente robusta e documentada
  - Webhook events detalhados (delivered, opened, clicked, bounced)
  - Dashboard analytics completo
  - Limites generosos (40k envios/hora no plano $15)
  - Suporte a múltiplas IPs dedicadas (reputação)
  - Validação de email integrada
  - Templates HTML/CSS renderizados
  - Unsubscribe group management
  - Bounce/spam complaint tracking
  - SDK Python oficial (sendgrid-python)

Contras:
  - Preço mais alto (mas vale a pena)
  - Curva de aprendizado média

Limites por plano:
  - Free: 100 emails/dia (teste)
  - Essentials ($15): 40,000 emails/mês, 40k/hora
  - Pro ($90): 100,000 emails/mês, 200k/hora
```

#### Resend (Backup/Alternativo)
```yaml
Prós:
  - API moderna e limpa (semelhante à Stripe)
  - Webhooks simples mas eficazes
  - Foco em developer experience
  - Pricing justo ($0 até 3k emails/mês)
  - React Email integration (futuro)
  - Domínio verification fácil

Contras:
  - Menos recursos avançados que SendGrid
  - Menor limite de envio/hora

Limites:
  - Free: 3,000 emails/mês
  - Pro ($20): 50,000 emails/mês
```

### Estratégia Multi-Provider

```python
# Rotação inteligente entre provedores
EmailProvider
├── SendGrid (80% do tráfego)
│   └── Para campanhas principais
├── Resend (15% do tráfego)
│   └── Para testes e campanhas menores
└── Postmark (5% do tráfego - opcional)
    └── Para emails transacionais críticos
```

---

## 📦 ESTRUTURA DE DADOS NECESSÁRIA

### 1. Modelo `EmailProvider`

```python
class EmailProvider(models.Model):
    """
    Provedor de email (equivalente a WhatsAppInstance)
    Suporta múltiplos provedores e contas
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)
    
    # Identificação
    name = models.CharField(max_length=100, help_text="Nome amigável (Ex: SendGrid Principal)")
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('sendgrid', 'SendGrid'),
            ('resend', 'Resend'),
            ('postmark', 'Postmark'),
            ('mailgun', 'Mailgun'),
            ('aws_ses', 'AWS SES'),
            ('smtp', 'SMTP Genérico'),
        ]
    )
    
    # Credenciais (criptografadas)
    api_key = models.CharField(max_length=500, help_text="API Key do provedor")
    api_secret = models.CharField(max_length=500, blank=True, null=True)
    
    # SMTP (fallback)
    smtp_host = models.CharField(max_length=200, blank=True, null=True)
    smtp_port = models.IntegerField(default=587, blank=True, null=True)
    smtp_username = models.CharField(max_length=200, blank=True, null=True)
    smtp_password = models.CharField(max_length=500, blank=True, null=True)
    smtp_use_tls = models.BooleanField(default=True)
    
    # Configuração de envio
    from_email = models.EmailField(help_text="Email remetente (ex: campaigns@alrea.com)")
    from_name = models.CharField(max_length=100, help_text="Nome do remetente")
    reply_to_email = models.EmailField(blank=True, null=True)
    
    # Domínio verificado
    verified_domain = models.CharField(max_length=200, help_text="Domínio verificado no provedor")
    domain_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Limites e controle
    max_emails_per_hour = models.IntegerField(default=10000)
    max_emails_per_day = models.IntegerField(default=100000)
    emails_sent_today = models.IntegerField(default=0)
    emails_sent_this_hour = models.IntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_hour_reset = models.DateTimeField(null=True, blank=True)
    last_day_reset = models.DateTimeField(null=True, blank=True)
    
    # Health & Reputação
    is_active = models.BooleanField(default=True)
    health_score = models.IntegerField(default=100, help_text="0-100 baseado em bounces/complaints")
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    complaint_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Contadores de eventos
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_opened = models.IntegerField(default=0)
    total_clicked = models.IntegerField(default=0)
    total_bounced = models.IntegerField(default=0)
    total_complaints = models.IntegerField(default=0)
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_provider'
        unique_together = ['tenant', 'from_email']
```

### 2. Extensão do `Campaign` Model

```python
# Adicionar ao Campaign existente:
class Campaign(models.Model):
    # ... campos existentes ...
    
    # NOVO: Tipo de campanha
    campaign_type = models.CharField(
        max_length=20,
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('email', 'Email'),
            ('sms', 'SMS'),  # Futuro
        ],
        default='whatsapp'
    )
    
    # NOVO: Email providers (se campaign_type='email')
    email_providers = models.ManyToManyField(
        'EmailProvider',
        related_name='campaigns',
        blank=True
    )
    
    # NOVO: Configurações de email
    email_subject = models.CharField(max_length=200, blank=True, null=True)
    email_preheader = models.CharField(max_length=150, blank=True, null=True)
    track_opens = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)
```

### 3. Extensão do `CampaignMessage`

```python
class CampaignMessage(models.Model):
    # ... campos existentes ...
    
    # NOVO: Conteúdo HTML para email
    html_content = models.TextField(
        blank=True, 
        null=True,
        help_text="Conteúdo HTML do email (se campaign_type='email')"
    )
    
    # NOVO: Template ID (SendGrid/Resend)
    template_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="ID do template no provedor de email"
    )
```

### 4. Extensão do `CampaignContact`

```python
class CampaignContact(models.Model):
    # ... campos existentes ...
    
    # NOVO: Email provider usado
    email_provider_used = models.ForeignKey(
        'EmailProvider',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # NOVO: Email message ID
    email_message_id = models.CharField(max_length=255, blank=True, null=True)
    
    # NOVO: Email tracking
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    bounce_reason = models.TextField(blank=True, null=True)
    complained_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
```

### 5. Novo Modelo `EmailEvent`

```python
class EmailEvent(models.Model):
    """
    Eventos de email recebidos via webhook (SendGrid/Resend)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)
    campaign = models.ForeignKey('Campaign', on_delete=models.CASCADE)
    campaign_contact = models.ForeignKey('CampaignContact', on_delete=models.CASCADE)
    
    # Evento
    event_type = models.CharField(
        max_length=20,
        choices=[
            ('delivered', 'Entregue'),
            ('open', 'Aberto'),
            ('click', 'Clicado'),
            ('bounce', 'Bounce'),
            ('dropped', 'Descartado'),
            ('spam_report', 'Marcado como Spam'),
            ('unsubscribe', 'Descadastrado'),
        ]
    )
    
    # IDs de rastreamento
    email_message_id = models.CharField(max_length=255)
    provider_event_id = models.CharField(max_length=255, unique=True)
    
    # Dados do evento
    timestamp = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    url_clicked = models.URLField(blank=True, null=True)
    bounce_type = models.CharField(max_length=50, blank=True, null=True)
    bounce_reason = models.TextField(blank=True, null=True)
    
    # Raw webhook data
    raw_data = models.JSONField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_event'
        indexes = [
            models.Index(fields=['campaign', 'event_type']),
            models.Index(fields=['email_message_id']),
            models.Index(fields=['timestamp']),
        ]
```

---

## 🔧 COMPONENTES A DESENVOLVER

### Backend Components

#### 1. Email Provider Service
```python
# backend/apps/campaigns/email_providers/base.py
class BaseEmailProvider(ABC):
    """Base abstrata para provedores de email"""
    
    @abstractmethod
    def send_email(self, to_email, subject, html_content, text_content, **kwargs):
        """Envia email"""
        pass
    
    @abstractmethod
    def verify_domain(self, domain):
        """Verifica domínio"""
        pass
    
    @abstractmethod
    def get_delivery_stats(self, days=7):
        """Obtém estatísticas de entrega"""
        pass
    
    @abstractmethod
    def process_webhook(self, payload):
        """Processa webhook do provedor"""
        pass

# backend/apps/campaigns/email_providers/sendgrid.py
class SendGridProvider(BaseEmailProvider):
    """Implementação SendGrid"""
    
    def send_email(self, to_email, subject, html_content, **kwargs):
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email=(self.config.from_email, self.config.from_name),
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        # Tracking
        message.tracking_settings = {
            'click_tracking': {'enable': self.track_clicks},
            'open_tracking': {'enable': self.track_opens}
        }
        
        # Custom args para webhook
        message.custom_args = {
            'campaign_id': kwargs.get('campaign_id'),
            'contact_id': kwargs.get('contact_id'),
            'tenant_id': kwargs.get('tenant_id'),
        }
        
        sg = SendGridAPIClient(self.config.api_key)
        response = sg.send(message)
        
        return {
            'message_id': response.headers.get('X-Message-Id'),
            'status_code': response.status_code
        }

# backend/apps/campaigns/email_providers/resend.py
class ResendProvider(BaseEmailProvider):
    """Implementação Resend"""
    
    def send_email(self, to_email, subject, html_content, **kwargs):
        import resend
        
        resend.api_key = self.config.api_key
        
        params = {
            'from': f'{self.config.from_name} <{self.config.from_email}>',
            'to': [to_email],
            'subject': subject,
            'html': html_content,
            'tags': [{
                'name': 'campaign_id',
                'value': kwargs.get('campaign_id')
            }]
        }
        
        email = resend.Emails.send(params)
        return {'message_id': email['id'], 'status_code': 200}
```

#### 2. Email Campaign Sender
```python
# backend/apps/campaigns/services/email_sender.py
class EmailCampaignSender:
    """Serviço para envio de emails de campanha"""
    
    def __init__(self, campaign: Campaign):
        self.campaign = campaign
        self.rotation_service = EmailProviderRotationService(campaign)
    
    def send_next_email(self) -> tuple[bool, str]:
        """Envia próximo email da campanha"""
        
        # 1. Buscar próximo contato pendente
        campaign_contact = self.campaign.campaign_contacts.filter(
            status='pending'
        ).select_related('contact').first()
        
        if not campaign_contact or not campaign_contact.contact.email:
            return False, "Nenhum contato com email pendente"
        
        # 2. Selecionar provider disponível
        provider = self.rotation_service.select_next_provider()
        if not provider:
            return False, "Nenhum provider de email disponível"
        
        # 3. Selecionar mensagem e preparar conteúdo
        message = self._select_message()
        subject = self._render_subject(campaign_contact.contact)
        html_content = self._render_html(message, campaign_contact.contact)
        text_content = self._render_text(message, campaign_contact.contact)
        
        # 4. Marcar como enviando
        campaign_contact.status = 'sending'
        campaign_contact.email_provider_used = provider
        campaign_contact.save()
        
        try:
            # 5. Enviar via provider
            result = provider.send_email(
                to_email=campaign_contact.contact.email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                campaign_id=str(self.campaign.id),
                contact_id=str(campaign_contact.contact.id),
                tenant_id=str(self.campaign.tenant.id)
            )
            
            # 6. Atualizar status
            campaign_contact.status = 'sent'
            campaign_contact.sent_at = timezone.now()
            campaign_contact.email_message_id = result['message_id']
            campaign_contact.save()
            
            # 7. Atualizar contadores
            provider.record_email_sent()
            self.campaign.messages_sent += 1
            self.campaign.save(update_fields=['messages_sent'])
            
            # 8. Log de sucesso
            CampaignLog.log_email_sent(
                self.campaign, provider, campaign_contact.contact, 
                campaign_contact, subject, result['message_id']
            )
            
            return True, f"Email enviado para {campaign_contact.contact.email}"
            
        except Exception as e:
            # Tratamento de erro similar ao WhatsApp
            campaign_contact.status = 'failed'
            campaign_contact.error_message = str(e)
            campaign_contact.failed_at = timezone.now()
            campaign_contact.save()
            
            provider.record_email_failed(str(e))
            self.campaign.messages_failed += 1
            self.campaign.save(update_fields=['messages_failed'])
            
            CampaignLog.log_email_failed(
                self.campaign, provider, campaign_contact.contact,
                campaign_contact, str(e)
            )
            
            return False, f"Erro ao enviar: {str(e)}"
    
    def _render_html(self, message, contact):
        """Renderiza HTML com variáveis substituídas"""
        html = message.html_content or self._text_to_html(message.content)
        
        # Substituir variáveis
        replacements = {
            '{{nome}}': contact.name,
            '{{email}}': contact.email,
            '{{primeiro_nome}}': contact.name.split()[0] if contact.name else '',
            # ... outras variáveis
        }
        
        for var, value in replacements.items():
            html = html.replace(var, value or '')
        
        # Adicionar tracking pixel (se habilitado)
        if self.campaign.track_opens:
            tracking_pixel = f'<img src="{settings.BACKEND_URL}/api/campaigns/track-open/{campaign_contact.id}/" width="1" height="1" />'
            html = html.replace('</body>', f'{tracking_pixel}</body>')
        
        return html
```

#### 3. Webhook Handlers
```python
# backend/apps/campaigns/webhooks/email.py
class EmailWebhookHandler:
    """Handler para webhooks de provedores de email"""
    
    @staticmethod
    def handle_sendgrid_webhook(request):
        """Processa webhook do SendGrid"""
        events = json.loads(request.body)
        
        for event in events:
            try:
                # Extrair IDs customizados
                campaign_id = event.get('campaign_id')
                contact_id = event.get('contact_id')
                email_message_id = event.get('sg_message_id')
                
                # Buscar CampaignContact
                campaign_contact = CampaignContact.objects.get(
                    email_message_id=email_message_id
                )
                
                # Processar evento
                event_type = event['event']
                
                if event_type == 'delivered':
                    campaign_contact.status = 'delivered'
                    campaign_contact.delivered_at = timezone.now()
                    campaign_contact.campaign.messages_delivered += 1
                    
                elif event_type == 'open':
                    if not campaign_contact.opened_at:
                        campaign_contact.opened_at = timezone.now()
                        campaign_contact.campaign.messages_read += 1
                    
                elif event_type == 'click':
                    if not campaign_contact.clicked_at:
                        campaign_contact.clicked_at = timezone.now()
                    
                elif event_type in ['bounce', 'dropped']:
                    campaign_contact.status = 'failed'
                    campaign_contact.bounced_at = timezone.now()
                    campaign_contact.bounce_reason = event.get('reason')
                    campaign_contact.campaign.messages_failed += 1
                
                elif event_type == 'spamreport':
                    campaign_contact.complained_at = timezone.now()
                    # Marcar contato como opted_out
                    campaign_contact.contact.opted_out = True
                    campaign_contact.contact.save()
                
                elif event_type == 'unsubscribe':
                    campaign_contact.unsubscribed_at = timezone.now()
                    campaign_contact.contact.opted_out = True
                    campaign_contact.contact.save()
                
                campaign_contact.save()
                campaign_contact.campaign.save()
                
                # Criar EmailEvent para auditoria
                EmailEvent.objects.create(
                    tenant=campaign_contact.campaign.tenant,
                    campaign=campaign_contact.campaign,
                    campaign_contact=campaign_contact,
                    event_type=event_type,
                    email_message_id=email_message_id,
                    provider_event_id=event.get('sg_event_id'),
                    timestamp=datetime.fromtimestamp(event.get('timestamp')),
                    raw_data=event
                )
                
                # Broadcast WebSocket (se opened/clicked)
                if event_type in ['open', 'click']:
                    broadcast_campaign_update(campaign_contact.campaign.id)
                
            except CampaignContact.DoesNotExist:
                logger.warning(f"CampaignContact não encontrado: {email_message_id}")
                continue
            except Exception as e:
                logger.error(f"Erro processando webhook: {e}")
                continue
        
        return JsonResponse({'status': 'ok'})
```

---

## 📊 MÉTRICAS E TRACKING

### Métricas Principais

```python
class EmailCampaignMetrics:
    """Cálculo de métricas de campanhas de email"""
    
    @staticmethod
    def calculate_metrics(campaign):
        """Calcula todas as métricas"""
        total_sent = campaign.messages_sent
        
        return {
            # Taxa de entrega (delivered / sent)
            'delivery_rate': (campaign.messages_delivered / total_sent * 100) if total_sent > 0 else 0,
            
            # Taxa de abertura (opened / delivered)
            'open_rate': (campaign.messages_read / campaign.messages_delivered * 100) if campaign.messages_delivered > 0 else 0,
            
            # Taxa de clique (clicked / delivered)
            'click_rate': (campaign.campaign_contacts.filter(clicked_at__isnull=False).count() / campaign.messages_delivered * 100) if campaign.messages_delivered > 0 else 0,
            
            # CTOR (click-to-open rate): clicked / opened
            'ctor': (campaign.campaign_contacts.filter(clicked_at__isnull=False).count() / campaign.messages_read * 100) if campaign.messages_read > 0 else 0,
            
            # Taxa de bounce
            'bounce_rate': (campaign.campaign_contacts.filter(bounced_at__isnull=False).count() / total_sent * 100) if total_sent > 0 else 0,
            
            # Taxa de reclamação (spam)
            'complaint_rate': (campaign.campaign_contacts.filter(complained_at__isnull=False).count() / total_sent * 100) if total_sent > 0 else 0,
            
            # Taxa de descadastro
            'unsubscribe_rate': (campaign.campaign_contacts.filter(unsubscribed_at__isnull=False).count() / total_sent * 100) if total_sent > 0 else 0,
        }
```

### Dashboard Analytics

```typescript
// frontend/src/modules/campaigns/components/EmailCampaignDashboard.tsx
interface EmailMetrics {
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  complained: number;
  unsubscribed: number;
  
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  ctor: number;
  bounce_rate: number;
  complaint_rate: number;
  unsubscribe_rate: number;
}

// Componente visual similar ao WhatsApp mas com métricas de email
<EmailCampaignDashboard>
  <MetricCard title="Taxa de Entrega" value="98.5%" status="success" />
  <MetricCard title="Taxa de Abertura" value="32.4%" status="good" />
  <MetricCard title="Taxa de Clique" value="4.7%" status="warning" />
  <MetricCard title="CTOR" value="14.5%" status="good" />
  <MetricCard title="Bounce Rate" value="1.2%" status="success" />
  <MetricCard title="Spam Rate" value="0.01%" status="success" />
</EmailCampaignDashboard>
```

---

## ⚙️ CONTROLE DE LIMITES E ENVIO

### Rate Limiting por Provider

```python
class EmailProviderRateLimiter:
    """Controle de limites de envio por provider"""
    
    def __init__(self, provider: EmailProvider):
        self.provider = provider
    
    def can_send_now(self) -> tuple[bool, str]:
        """Verifica se pode enviar agora"""
        
        # 1. Verificar se provider está ativo
        if not self.provider.is_active:
            return False, "Provider desativado"
        
        # 2. Verificar health score
        if self.provider.health_score < 50:
            return False, f"Health score baixo: {self.provider.health_score}"
        
        # 3. Reset de contadores se necessário
        self._reset_counters_if_needed()
        
        # 4. Verificar limite horário
        if self.provider.emails_sent_this_hour >= self.provider.max_emails_per_hour:
            return False, f"Limite horário atingido: {self.provider.emails_sent_this_hour}/{self.provider.max_emails_per_hour}"
        
        # 5. Verificar limite diário
        if self.provider.emails_sent_today >= self.provider.max_emails_per_day:
            return False, f"Limite diário atingido: {self.provider.emails_sent_today}/{self.provider.max_emails_per_day}"
        
        # 6. Verificar bounce rate
        if self.provider.bounce_rate > 5.0:
            return False, f"Bounce rate alto: {self.provider.bounce_rate}%"
        
        # 7. Verificar complaint rate
        if self.provider.complaint_rate > 0.1:
            return False, f"Complaint rate alto: {self.provider.complaint_rate}%"
        
        return True, "OK"
    
    def _reset_counters_if_needed(self):
        """Reset de contadores horários/diários"""
        now = timezone.now()
        
        # Reset horário
        if not self.provider.last_hour_reset or (now - self.provider.last_hour_reset).total_seconds() >= 3600:
            self.provider.emails_sent_this_hour = 0
            self.provider.last_hour_reset = now
            self.provider.save(update_fields=['emails_sent_this_hour', 'last_hour_reset'])
        
        # Reset diário
        if not self.provider.last_day_reset or (now - self.provider.last_day_reset).days >= 1:
            self.provider.emails_sent_today = 0
            self.provider.last_day_reset = now
            self.provider.save(update_fields=['emails_sent_today', 'last_day_reset'])
```

### Gerenciamento de Reputação

```python
class EmailReputationManager:
    """Gerencia reputação de provedores de email"""
    
    @staticmethod
    def update_health_score(provider: EmailProvider):
        """Atualiza health score baseado em métricas"""
        
        # Calcular bounce rate
        if provider.total_sent > 0:
            provider.bounce_rate = (provider.total_bounced / provider.total_sent) * 100
            provider.complaint_rate = (provider.total_complaints / provider.total_sent) * 100
        
        # Calcular health score (0-100)
        health = 100
        
        # Penalizar por bounce rate
        if provider.bounce_rate > 2.0:
            health -= (provider.bounce_rate - 2.0) * 10  # -10 pontos por 1% acima de 2%
        
        # Penalizar MUITO por complaint rate
        if provider.complaint_rate > 0.1:
            health -= (provider.complaint_rate - 0.1) * 100  # -100 pontos por 1% acima de 0.1%
        
        # Limitar entre 0-100
        provider.health_score = max(0, min(100, health))
        
        # Desativar se health muito baixo
        if provider.health_score < 30:
            provider.is_active = False
            logger.warning(f"⚠️ Provider {provider.name} desativado por health baixo: {provider.health_score}")
        
        provider.save()
```

### Conta Específica para Ler Retornos

```python
class BounceHandlerAccount:
    """Conta de email dedicada para processar bounces e respostas"""
    
    # Configuração
    BOUNCE_EMAIL = "bounces@alrea.com"
    REPLY_EMAIL = "noreply@alrea.com"
    
    @staticmethod
    def setup_return_path():
        """Configura Return-Path para bounces"""
        
        # No SendGrid:
        # 1. Verificar domínio alrea.com
        # 2. Configurar DKIM/SPF/DMARC
        # 3. Configurar Return-Path: bounces@alrea.com
        # 4. Webhook para bounces automático
        
        # Alternativa: IMAP polling
        # Se webhook não disponível, fazer polling IMAP:
        imap_server = 'imap.alrea.com'
        email = 'bounces@alrea.com'
        password = os.environ.get('BOUNCE_EMAIL_PASSWORD')
        
        # Ver EmailBounceProcessor abaixo
```

```python
# backend/apps/campaigns/services/bounce_processor.py
import imaplib
import email
from email.header import decode_header

class EmailBounceProcessor:
    """Processa bounces via IMAP (se webhook não disponível)"""
    
    def __init__(self):
        self.imap_server = settings.BOUNCE_IMAP_SERVER
        self.email_account = settings.BOUNCE_EMAIL_ACCOUNT
        self.password = settings.BOUNCE_EMAIL_PASSWORD
    
    def process_bounces(self):
        """Conecta via IMAP e processa bounces"""
        
        # Conectar
        mail = imaplib.IMAP4_SSL(self.imap_server)
        mail.login(self.email_account, self.password)
        mail.select('INBOX')
        
        # Buscar emails não lidos
        status, messages = mail.search(None, 'UNSEEN')
        
        for num in messages[0].split():
            status, data = mail.fetch(num, '(RFC822)')
            
            # Parse email
            msg = email.message_from_bytes(data[0][1])
            
            # Extrair original message ID
            original_msg_id = self._extract_message_id(msg)
            
            if original_msg_id:
                # Buscar CampaignContact
                try:
                    cc = CampaignContact.objects.get(email_message_id=original_msg_id)
                    
                    # Marcar como bounced
                    cc.status = 'failed'
                    cc.bounced_at = timezone.now()
                    cc.bounce_reason = self._extract_bounce_reason(msg)
                    cc.save()
                    
                    # Atualizar provider
                    if cc.email_provider_used:
                        cc.email_provider_used.total_bounced += 1
                        cc.email_provider_used.save()
                        EmailReputationManager.update_health_score(cc.email_provider_used)
                    
                    logger.info(f"✅ Bounce processado: {original_msg_id}")
                    
                except CampaignContact.DoesNotExist:
                    logger.warning(f"⚠️ CampaignContact não encontrado: {original_msg_id}")
            
            # Marcar como lido
            mail.store(num, '+FLAGS', '\\Seen')
        
        mail.close()
        mail.logout()
    
    def _extract_message_id(self, msg):
        """Extrai Message-ID original do bounce"""
        # Implementar parse de bounce message
        pass
    
    def _extract_bounce_reason(self, msg):
        """Extrai razão do bounce"""
        # Implementar parse de bounce reason
        pass

# Agendar task no RabbitMQ
# Rodar a cada 5 minutos
```

---

## 🗓️ PLANO DE IMPLEMENTAÇÃO POR FASES

### FASE 1: Infraestrutura Base (2-3 dias)

**Objetivo:** Estrutura de dados e providers funcionando

**Tarefas:**
```
□ Criar models (EmailProvider, EmailEvent)
□ Criar migrations
□ Estender Campaign model (campaign_type, email fields)
□ Estender CampaignMessage (html_content)
□ Estender CampaignContact (email tracking fields)
□ Criar admin interfaces
□ Testar migrations localmente e em Railway
```

**Entregável:** Banco de dados preparado para email campaigns

---

### FASE 2: Integrações com Provedores (2-3 dias)

**Objetivo:** SendGrid e Resend funcionando

**Tarefas:**
```
□ Implementar BaseEmailProvider (interface abstrata)
□ Implementar SendGridProvider
  □ send_email()
  □ verify_domain()
  □ get_stats()
□ Implementar ResendProvider
  □ send_email()
  □ verify_domain()
□ Criar EmailProviderRotationService
□ Criar EmailCampaignSender
□ Criar testes unitários
□ Testar envio real com ambos provedores
```

**Entregável:** Envio de emails funcionando via API

---

### FASE 3: Tracking e Webhooks (2 dias)

**Objetivo:** Tracking de delivery, opens, clicks

**Tarefas:**
```
□ Criar endpoint /api/campaigns/webhooks/sendgrid/
□ Criar endpoint /api/campaigns/webhooks/resend/
□ Implementar EmailWebhookHandler
□ Criar EmailEvent model e save logic
□ Processar eventos: delivered, opened, clicked, bounced, complained
□ Atualizar CampaignContact em tempo real
□ Broadcast via WebSocket
□ Testar webhooks localmente (ngrok)
□ Configurar webhooks em produção
```

**Entregável:** Tracking completo de emails

---

### FASE 4: Rate Limiting e Reputação (1-2 dias)

**Objetivo:** Controle de limites e health

**Tarefas:**
```
□ Implementar EmailProviderRateLimiter
□ Implementar EmailReputationManager
□ Criar job RabbitMQ para calcular metrics a cada hora
□ Auto-pausar providers com health baixo
□ Criar alertas de bounce/complaint rate alto
□ Dashboard de health por provider
```

**Entregável:** Proteção de reputação implementada

---

### FASE 5: Frontend - Criação de Campanhas (2 dias)

**Objetivo:** Interface para criar campanhas de email

**Tarefas:**
```
□ Adicionar "Email" como tipo de campanha no wizard
□ Criar EmailCampaignForm
  □ Seleção de email providers
  □ Campo de assunto (com preview de variáveis)
  □ Campo de preheader
  □ Toggle tracking (opens/clicks)
□ Email message editor
  □ Rich text editor (TipTap ou similar)
  □ Preview HTML
  □ Inserção de variáveis
□ Validação de email em contatos
□ Preview de email antes de enviar
```

**Entregável:** Criação de campanhas de email funcionando

---

### FASE 6: Frontend - Dashboard e Analytics (1-2 dias)

**Objetivo:** Visualização de métricas de email

**Tarefas:**
```
□ EmailCampaignDashboard component
  □ Métricas principais (delivery rate, open rate, click rate)
  □ Gráfico de opens ao longo do tempo
  □ Gráfico de clicks ao longo do tempo
  □ Lista de links mais clicados
  □ Lista de bounces (com razões)
  □ Lista de complaints
□ EmailProviderHealthDashboard
  □ Health score por provider
  □ Bounce rate
  □ Complaint rate
  □ Emails enviados (hora/dia)
□ Integração com WebSocket para updates em tempo real
```

**Entregável:** Dashboard completo de email campaigns

---

### FASE 7: Testes e Refinamentos (1-2 dias)

**Objetivo:** Testar tudo end-to-end

**Tarefas:**
```
□ Criar campanha de teste real
□ Enviar para lista pequena (10-20 emails)
□ Verificar delivery
□ Abrir emails e verificar tracking
□ Clicar em links e verificar tracking
□ Simular bounces
□ Verificar webhooks funcionando
□ Testar limites de rate
□ Testar rotação de providers
□ Ajustar intervalos de envio
□ Documentar fluxo completo
```

**Entregável:** Sistema testado e funcionando em produção

---

## ⏱️ ESTIMATIVA FINAL DE TEMPO

### Otimista: 5-6 dias
```
Dia 1-2: Fase 1 + Fase 2 (infraestrutura + providers)
Dia 3: Fase 3 (webhooks + tracking)
Dia 4: Fase 4 + Fase 5 (rate limiting + frontend criação)
Dia 5: Fase 6 (dashboard)
Dia 6: Fase 7 (testes)

Total: 5-6 dias se tudo fluir perfeitamente
```

### Realista: 8-10 dias ⭐ **RECOMENDADO**
```
Dia 1-2: Fase 1 (infraestrutura)
Dia 3-4: Fase 2 (providers)
Dia 5-6: Fase 3 + Fase 4 (webhooks + rate limiting)
Dia 7-8: Fase 5 (frontend criação)
Dia 9: Fase 6 (frontend dashboard)
Dia 10: Fase 7 (testes + refinamentos)

Total: 8-10 dias com buffer para imprevistos
```

### Pessimista: 12-15 dias
```
+ Problemas com webhooks SendGrid/Resend
+ Debugging de delivery issues
+ Ajustes de UI/UX
+ Bugs inesperados
+ Tempo para documentação extra

Total: 12-15 dias considerando Murphy
```

---

## 📋 CHECKLIST DE ENTREGA

### Backend Ready
```
□ Models criados e migrations aplicadas
□ SendGrid integration funcionando
□ Resend integration funcionando
□ Webhooks processando eventos corretamente
□ Rate limiting ativo
□ Health score calculando automaticamente
□ Bounces sendo processados
□ Complaints sendo processados
□ Logs detalhados criados
□ WebSocket broadcasting updates
□ RabbitMQ consumer processando emails
□ Testes unitários passando
```

### Frontend Ready
```
□ Wizard de criação aceita tipo "email"
□ Email message editor funcionando
□ Preview de email funcionando
□ Dashboard de métricas exibindo corretamente
□ Updates em tempo real via WebSocket
□ Gráficos de opens/clicks funcionando
□ Lista de bounces/complaints visível
□ Provider health dashboard visível
```

### Produção Ready
```
□ Domínio verificado no SendGrid
□ Domínio verificado no Resend
□ SPF/DKIM/DMARC configurados
□ Webhooks configurados em produção
□ Return-Path configurado
□ Bounce email configurado
□ Rate limits configurados por plano
□ Alertas de health configurados
□ Documentação para cliente escrita
□ Guia de troubleshooting criado
```

---

## 💡 MELHORES PRÁTICAS E RECOMENDAÇÕES

### Reputação de Email

1. **Aquecimento de IPs (IP Warming)**
   ```
   Dia 1-3: 50-100 emails/dia
   Dia 4-7: 200-500 emails/dia
   Dia 8-14: 1,000-2,000 emails/dia
   Dia 15+: Volume normal (10k+ emails/dia)
   ```

2. **Limites Conservadores Iniciais**
   ```python
   # Começar com limites baixos e aumentar gradualmente
   max_emails_per_hour = 1000  # Aumentar para 10k após 2 semanas
   max_emails_per_day = 10000  # Aumentar para 100k após 1 mês
   ```

3. **Monitoramento de Bounce Rate**
   ```
   < 2%: Excelente ✅
   2-5%: Aceitável ⚠️
   > 5%: Problemático ❌ (pausar envios e investigar)
   ```

4. **Monitoramento de Complaint Rate**
   ```
   < 0.1%: Excelente ✅
   0.1-0.3%: Aceitável ⚠️
   > 0.3%: Crítico ❌ (pausar imediatamente)
   ```

### Conteúdo de Email

1. **Sempre incluir:**
   - Endereço físico da empresa (exigência legal)
   - Link de unsubscribe claro
   - Razão do contato (ex: "Você recebeu porque...")
   
2. **Evitar:**
   - ALL CAPS no assunto
   - Excesso de pontuação (!!!, ???)
   - Palavras spam (FREE, GRÁTIS, CLIQUE AQUI)
   - Imagens muito grandes
   - Apenas uma imagem sem texto

3. **Assunto ideal:**
   - 40-50 caracteres
   - Personalizado (usar {{primeiro_nome}})
   - Criar curiosidade sem clickbait
   - Testar A/B diferentes versões

### Limpeza de Lista

```python
class EmailListCleaner:
    """Mantém lista de emails limpa"""
    
    @staticmethod
    def clean_contacts():
        """Remove/inativa contatos problemáticos"""
        
        # 1. Hard bounces permanentes (> 30 dias)
        Contact.objects.filter(
            campaign_contacts__bounced_at__lt=timezone.now() - timedelta(days=30),
            campaign_contacts__bounce_reason__icontains='permanent'
        ).update(is_active=False)
        
        # 2. Nunca abriram (> 6 meses)
        # Criar segment "inativos" ao invés de deletar
        
        # 3. Marcaram como spam
        Contact.objects.filter(
            campaign_contacts__complained_at__isnull=False
        ).update(opted_out=True)
        
        # 4. Unsubscribes
        Contact.objects.filter(
            campaign_contacts__unsubscribed_at__isnull=False
        ).update(opted_out=True)
```

---

## 🚨 PONTOS DE ATENÇÃO

### Crítico ❗

1. **NUNCA comprar lista de emails** - Bounce rate altíssimo, vai destruir reputação
2. **SEMPRE ter opt-in** - Double opt-in preferível
3. **Respeitar opted_out** - Lei anti-spam (CAN-SPAM, LGPD)
4. **Configurar SPF/DKIM/DMARC** - Essencial para deliverability
5. **Monitorar blacklists** - Usar ferramentas como MXToolbox

### Importante ⚠️

1. **Testar em múltiplos clients** - Gmail, Outlook, Apple Mail, Yahoo
2. **Versão texto sempre** - Alguns clients não renderizam HTML
3. **Responsivo** - Maioria abre em mobile
4. **Links rastreáveis** - Usar UTM parameters
5. **Unsubscribe com 1 clique** - Exigência do Gmail (2024)

### Bom ter 💡

1. **A/B testing de assunto** - Melhorar open rate
2. **Segmentação avançada** - Enviar conteúdo relevante
3. **Re-engagement campaigns** - Reativar inativos
4. **Email warm-up service** - Para novos domínios
5. **BIMI (Brand Indicators for Message Identification)** - Logo no inbox

---

## 📚 RECURSOS E REFERÊNCIAS

### Documentação de APIs

- **SendGrid:** https://docs.sendgrid.com/
  - Python SDK: https://github.com/sendgrid/sendgrid-python
  - Event Webhook: https://docs.sendgrid.com/for-developers/tracking-events/event
  
- **Resend:** https://resend.com/docs
  - Python SDK: https://github.com/resend/resend-python
  - Webhooks: https://resend.com/docs/api-reference/webhooks
  
- **Postmark:** https://postmarkapp.com/developer
  - Python SDK: https://github.com/themartorana/python-postmark

### Ferramentas Úteis

- **Email Testing:**
  - Litmus: https://litmus.com/ (pago)
  - Email on Acid: https://www.emailonacid.com/ (pago)
  - Mail Tester: https://www.mail-tester.com/ (grátis)
  - PutsMail: https://putsmail.com/ (grátis)

- **Blacklist Checking:**
  - MXToolbox: https://mxtoolbox.com/blacklists.aspx
  - MultiRBL: http://multirbl.valli.org/
  
- **SPF/DKIM Validators:**
  - DMARC Analyzer: https://www.dmarcanalyzer.com/
  - SPF Record Check: https://mxtoolbox.com/spf.aspx

### Guides

- **Email Deliverability Guide:** https://www.validity.com/resource-center/email-deliverability-guide/
- **CAN-SPAM Act:** https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
- **Gmail Sender Guidelines:** https://support.google.com/mail/answer/81126

---

## 🎯 CONCLUSÃO

### Viabilidade

**SIM, é totalmente viável implementar campanhas por email!** ✅

O sistema de campanhas WhatsApp já fornece uma base sólida que pode ser adaptada para email com relativa facilidade. As principais diferenças são:

1. **Provedores de envio** - SendGrid/Resend ao invés de Evolution API
2. **Tracking** - Webhooks mais robustos que WhatsApp
3. **Conteúdo** - HTML ao invés de texto puro
4. **Reputação** - Mais crítica que WhatsApp (bounce/complaint rates)

### Recomendação Final

**Plano de Execução Sugerido:**

```
Semana 1 (5 dias):
  - Infraestrutura + Providers + Webhooks
  - MVP funcional: enviar + trackear delivery

Semana 2 (5 dias):
  - Rate limiting + Frontend completo
  - Testes reais com volume pequeno
  
Total: 2 semanas (10 dias úteis)
```

**Custo Inicial Estimado:**
- SendGrid Essentials: $15/mês
- Resend Pro: $20/mês
- Desenvolvimento: 10 dias × custo hora do dev
- **Total mensal de serviços:** ~$35/mês

**ROI Esperado:**
- Permite múltiplas campanhas simultâneas (WhatsApp + Email)
- Maior alcance (nem todos respondem WhatsApp)
- Menor custo por contato vs WhatsApp
- Métricas mais detalhadas (clicks, heatmaps)

### Próximos Passos

1. ✅ **Aprovar este plano** com stakeholders
2. ✅ **Criar contas teste** SendGrid + Resend
3. ✅ **Verificar domínio** alrea.com nos provedores
4. ✅ **Configurar SPF/DKIM/DMARC** no DNS
5. ✅ **Começar Fase 1** (infraestrutura)

---

**Dúvidas? Sugestões? Vamos refinar o plano juntos!** 🚀




