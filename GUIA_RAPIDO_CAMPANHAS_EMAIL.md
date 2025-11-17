# 📧 GUIA RÁPIDO - Implementação de Campanhas Email

> **Complemento do PLANO_IMPLEMENTACAO_CAMPANHAS_EMAIL.md**  
> **Foco:** Exemplos práticos e código copy-paste

---

## 🚀 INÍCIO RÁPIDO - DIA 1

### 1. Criar Conta SendGrid (5 min)

```bash
# 1. Acessar https://signup.sendgrid.com/
# 2. Criar conta (Free tier: 100 emails/dia)
# 3. Ir em Settings > API Keys
# 4. Create API Key com permissão "Full Access"
# 5. Copiar key (começa com SG.)
```

### 2. Adicionar ao Railway (2 min)

```bash
# No Railway, adicionar variáveis de ambiente:
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=campaigns@alrea.com
SENDGRID_FROM_NAME=Alrea Campaigns

# Opcional (para Resend):
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Instalar Dependências (2 min)

```bash
# backend/requirements.txt
echo "sendgrid==6.10.0" >> requirements.txt
echo "python-resend==0.7.0" >> requirements.txt
echo "beautifulsoup4==4.12.2" >> requirements.txt  # Para parse HTML
echo "html2text==2020.1.16" >> requirements.txt  # HTML -> texto

pip install -r requirements.txt
```

---

## 📦 CÓDIGO ESSENCIAL

### Migration Inicial

```python
# backend/apps/campaigns/migrations/0011_add_email_support.py
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('campaigns', '0010_add_performance_indexes'),
    ]

    operations = [
        # 1. Adicionar campo campaign_type ao Campaign
        migrations.AddField(
            model_name='campaign',
            name='campaign_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('whatsapp', 'WhatsApp'),
                    ('email', 'Email'),
                ],
                default='whatsapp'
            ),
        ),
        
        # 2. Adicionar campos de email ao Campaign
        migrations.AddField(
            model_name='campaign',
            name='email_subject',
            field=models.CharField(max_length=200, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='campaign',
            name='track_opens',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='campaign',
            name='track_clicks',
            field=models.BooleanField(default=True),
        ),
        
        # 3. Adicionar html_content ao CampaignMessage
        migrations.AddField(
            model_name='campaignmessage',
            name='html_content',
            field=models.TextField(blank=True, null=True),
        ),
        
        # 4. Criar modelo EmailProvider
        migrations.CreateModel(
            name='EmailProvider',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True)),
                ('tenant', models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)),
                ('name', models.CharField(max_length=100)),
                ('provider_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('sendgrid', 'SendGrid'),
                        ('resend', 'Resend'),
                    ]
                )),
                ('api_key', models.CharField(max_length=500)),
                ('from_email', models.EmailField()),
                ('from_name', models.CharField(max_length=100)),
                ('max_emails_per_hour', models.IntegerField(default=10000)),
                ('emails_sent_this_hour', models.IntegerField(default=0)),
                ('health_score', models.IntegerField(default=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'email_provider'},
        ),
        
        # 5. Adicionar tracking fields ao CampaignContact
        migrations.AddField(
            model_name='campaigncontact',
            name='email_provider_used',
            field=models.ForeignKey(
                'EmailProvider',
                null=True,
                blank=True,
                on_delete=models.SET_NULL
            ),
        ),
        migrations.AddField(
            model_name='campaigncontact',
            name='email_message_id',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='campaigncontact',
            name='opened_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='campaigncontact',
            name='clicked_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='campaigncontact',
            name='bounced_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
```

### EmailProvider Model

```python
# backend/apps/campaigns/models.py
class EmailProvider(models.Model):
    """Provedor de email (SendGrid, Resend, etc.)"""
    
    PROVIDER_CHOICES = [
        ('sendgrid', 'SendGrid'),
        ('resend', 'Resend'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, related_name='email_providers')
    
    # Config
    name = models.CharField(max_length=100, help_text="Nome amigável")
    provider_type = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    api_key = models.CharField(max_length=500)
    from_email = models.EmailField()
    from_name = models.CharField(max_length=100)
    
    # Limites
    max_emails_per_hour = models.IntegerField(default=10000)
    emails_sent_this_hour = models.IntegerField(default=0)
    last_hour_reset = models.DateTimeField(null=True, blank=True)
    
    # Health
    health_score = models.IntegerField(default=100)
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    
    # Stats
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_bounced = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_provider'
        unique_together = ['tenant', 'from_email']
    
    def __str__(self):
        return f"{self.name} ({self.provider_type})"
    
    def can_send_now(self) -> bool:
        """Verifica se pode enviar"""
        if not self.is_active:
            return False
        if self.health_score < 50:
            return False
        
        # Reset contador se passou 1 hora
        if self.last_hour_reset and (timezone.now() - self.last_hour_reset).total_seconds() >= 3600:
            self.emails_sent_this_hour = 0
            self.last_hour_reset = timezone.now()
            self.save()
        
        return self.emails_sent_this_hour < self.max_emails_per_hour
    
    def record_sent(self):
        """Registra email enviado"""
        self.emails_sent_this_hour += 1
        self.total_sent += 1
        if not self.last_hour_reset:
            self.last_hour_reset = timezone.now()
        self.save(update_fields=['emails_sent_this_hour', 'total_sent', 'last_hour_reset'])
```

### SendGrid Service (Copy-Paste)

```python
# backend/apps/campaigns/services/sendgrid_service.py
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking, OpenTracking
from django.conf import settings

logger = logging.getLogger(__name__)


class SendGridService:
    """Serviço para envio via SendGrid"""
    
    def __init__(self, provider):
        self.provider = provider
        self.client = SendGridAPIClient(provider.api_key)
    
    def send_email(self, to_email: str, subject: str, html_content: str, 
                   campaign_id: str, contact_id: str, tenant_id: str) -> dict:
        """
        Envia email via SendGrid
        
        Retorna:
            {'success': bool, 'message_id': str, 'error': str}
        """
        try:
            # Criar mensagem
            message = Mail(
                from_email=(self.provider.from_email, self.provider.from_name),
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            # Configurar tracking
            message.tracking_settings = TrackingSettings()
            message.tracking_settings.click_tracking = ClickTracking(enable=True, enable_text=False)
            message.tracking_settings.open_tracking = OpenTracking(enable=True)
            
            # Custom args para identificar no webhook
            message.custom_arg = [
                {'campaign_id': campaign_id},
                {'contact_id': contact_id},
                {'tenant_id': tenant_id},
            ]
            
            # Enviar
            response = self.client.send(message)
            
            # Extrair message ID
            message_id = response.headers.get('X-Message-Id', '')
            
            logger.info(f"✅ Email enviado: {to_email} | ID: {message_id}")
            
            return {
                'success': True,
                'message_id': message_id,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email: {e}")
            return {
                'success': False,
                'message_id': None,
                'error': str(e)
            }
```

### Email Sender (Copy-Paste)

```python
# backend/apps/campaigns/services/email_sender.py
import logging
import time
import random
from django.utils import timezone
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog, EmailProvider
from .sendgrid_service import SendGridService

logger = logging.getLogger(__name__)


class EmailCampaignSender:
    """Envia emails de campanha"""
    
    def __init__(self, campaign: Campaign):
        self.campaign = campaign
    
    def send_next_email(self) -> tuple[bool, str]:
        """Envia próximo email da campanha"""
        
        # 1. Buscar próximo contato pendente COM EMAIL
        campaign_contact = self.campaign.campaign_contacts.filter(
            status='pending',
            contact__email__isnull=False
        ).exclude(
            contact__email=''
        ).select_related('contact').first()
        
        if not campaign_contact:
            return False, "Nenhum contato com email pendente"
        
        contact = campaign_contact.contact
        
        # 2. Selecionar provider disponível
        provider = EmailProvider.objects.filter(
            tenant=self.campaign.tenant,
            is_active=True
        ).first()
        
        if not provider or not provider.can_send_now():
            return False, "Nenhum provider de email disponível"
        
        # 3. Preparar conteúdo
        message = self.campaign.messages.first()
        if not message:
            return False, "Nenhuma mensagem configurada"
        
        subject = self._render_subject(contact)
        html_content = self._render_html(message, contact)
        
        # 4. Marcar como enviando
        campaign_contact.status = 'sending'
        campaign_contact.email_provider_used = provider
        campaign_contact.save()
        
        try:
            # 5. Enviar via SendGrid
            service = SendGridService(provider)
            result = service.send_email(
                to_email=contact.email,
                subject=subject,
                html_content=html_content,
                campaign_id=str(self.campaign.id),
                contact_id=str(contact.id),
                tenant_id=str(self.campaign.tenant.id)
            )
            
            if not result['success']:
                raise Exception(result['error'])
            
            # 6. Atualizar status
            campaign_contact.status = 'sent'
            campaign_contact.sent_at = timezone.now()
            campaign_contact.email_message_id = result['message_id']
            campaign_contact.save()
            
            # 7. Atualizar contadores
            provider.record_sent()
            self.campaign.messages_sent += 1
            self.campaign.save(update_fields=['messages_sent'])
            
            # 8. Log
            CampaignLog.objects.create(
                campaign=self.campaign,
                log_type='message_sent',
                severity='info',
                message=f'Email enviado para {contact.email}',
                details={
                    'contact_id': str(contact.id),
                    'email': contact.email,
                    'subject': subject,
                    'message_id': result['message_id'],
                }
            )
            
            logger.info(f"✅ Email enviado: {contact.email}")
            return True, f"Email enviado para {contact.email}"
            
        except Exception as e:
            # Erro ao enviar
            campaign_contact.status = 'failed'
            campaign_contact.error_message = str(e)
            campaign_contact.failed_at = timezone.now()
            campaign_contact.save()
            
            self.campaign.messages_failed += 1
            self.campaign.save(update_fields=['messages_failed'])
            
            CampaignLog.objects.create(
                campaign=self.campaign,
                log_type='message_failed',
                severity='error',
                message=f'Erro ao enviar email para {contact.email}',
                details={'error': str(e)}
            )
            
            logger.error(f"❌ Erro ao enviar email: {e}")
            return False, f"Erro: {str(e)}"
    
    def _render_subject(self, contact) -> str:
        """Renderiza assunto com variáveis"""
        subject = self.campaign.email_subject or "Nova mensagem"
        
        replacements = {
            '{{nome}}': contact.name or '',
            '{{primeiro_nome}}': contact.name.split()[0] if contact.name else '',
            '{{email}}': contact.email or '',
        }
        
        for var, value in replacements.items():
            subject = subject.replace(var, value)
        
        return subject
    
    def _render_html(self, message, contact) -> str:
        """Renderiza HTML com variáveis"""
        html = message.html_content or f"<html><body>{message.content}</body></html>"
        
        replacements = {
            '{{nome}}': contact.name or '',
            '{{primeiro_nome}}': contact.name.split()[0] if contact.name else '',
            '{{email}}': contact.email or '',
        }
        
        for var, value in replacements.items():
            html = html.replace(var, value)
        
        # Adicionar unsubscribe link
        unsubscribe_url = f"{settings.FRONTEND_URL}/unsubscribe/{contact.id}"
        footer = f'<p style="font-size:12px;color:#999;">Para descadastrar, <a href="{unsubscribe_url}">clique aqui</a>.</p>'
        html = html.replace('</body>', f'{footer}</body>')
        
        return html
```

### Webhook Handler (Copy-Paste)

```python
# backend/apps/campaigns/views/webhooks.py
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from apps.campaigns.models import CampaignContact

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def sendgrid_webhook(request):
    """
    Processa webhooks do SendGrid
    
    Doc: https://docs.sendgrid.com/for-developers/tracking-events/event
    """
    try:
        events = json.loads(request.body)
        
        for event in events:
            event_type = event.get('event')
            message_id = event.get('sg_message_id')
            
            # Extrair custom args
            campaign_id = event.get('campaign_id')
            contact_id = event.get('contact_id')
            
            logger.info(f"📧 Webhook recebido: {event_type} | ID: {message_id}")
            
            # Buscar CampaignContact
            try:
                cc = CampaignContact.objects.get(email_message_id=message_id)
            except CampaignContact.DoesNotExist:
                logger.warning(f"⚠️ CampaignContact não encontrado: {message_id}")
                continue
            
            # Processar evento
            if event_type == 'delivered':
                cc.status = 'delivered'
                cc.delivered_at = timezone.now()
                cc.campaign.messages_delivered += 1
                logger.info(f"✅ Email entregue: {cc.contact.email}")
            
            elif event_type == 'open':
                if not cc.opened_at:  # Primeira abertura
                    cc.opened_at = timezone.now()
                    cc.campaign.messages_read += 1
                    logger.info(f"👁️ Email aberto: {cc.contact.email}")
            
            elif event_type == 'click':
                if not cc.clicked_at:  # Primeiro clique
                    cc.clicked_at = timezone.now()
                    logger.info(f"🖱️ Email clicado: {cc.contact.email}")
            
            elif event_type == 'bounce':
                cc.status = 'failed'
                cc.bounced_at = timezone.now()
                cc.bounce_reason = event.get('reason', 'Unknown')
                cc.campaign.messages_failed += 1
                
                # Atualizar provider
                if cc.email_provider_used:
                    cc.email_provider_used.total_bounced += 1
                    cc.email_provider_used.save()
                
                logger.warning(f"⚠️ Email bounce: {cc.contact.email}")
            
            elif event_type == 'spamreport':
                cc.complained_at = timezone.now()
                cc.contact.opted_out = True
                cc.contact.save()
                logger.error(f"🚨 Spam report: {cc.contact.email}")
            
            elif event_type == 'unsubscribe':
                cc.unsubscribed_at = timezone.now()
                cc.contact.opted_out = True
                cc.contact.save()
                logger.info(f"❌ Unsubscribe: {cc.contact.email}")
            
            # Salvar
            cc.save()
            if event_type in ['delivered', 'bounce']:
                cc.campaign.save()
        
        return JsonResponse({'status': 'ok', 'processed': len(events)})
        
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
```

### URL Config

```python
# backend/apps/campaigns/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet
from .views.webhooks import sendgrid_webhook

router = DefaultRouter()
router.register(r'', CampaignViewSet, basename='campaign')

urlpatterns = [
    path('', include(router.urls)),
    path('webhooks/sendgrid/', sendgrid_webhook, name='sendgrid-webhook'),  # ⬅️ NOVO
]
```

---

## 🧪 TESTES RÁPIDOS

### 1. Criar EmailProvider via Admin

```bash
# Acessar Django Admin
python manage.py createsuperuser  # Se não tem superuser

# Ou via shell:
python manage.py shell
```

```python
from apps.campaigns.models import EmailProvider
from apps.tenancy.models import Tenant

tenant = Tenant.objects.first()

provider = EmailProvider.objects.create(
    tenant=tenant,
    name="SendGrid Principal",
    provider_type="sendgrid",
    api_key="SG.YOUR_API_KEY_HERE",
    from_email="campaigns@alrea.com",
    from_name="Alrea Campaigns",
    max_emails_per_hour=1000,
    is_active=True
)

print(f"✅ Provider criado: {provider.id}")
```

### 2. Criar Campanha de Teste

```python
from apps.campaigns.models import Campaign, CampaignMessage
from apps.contacts.models import Contact

# Criar campanha
campaign = Campaign.objects.create(
    tenant=tenant,
    name="Teste Email - Primeira Campanha",
    description="Primeira campanha de email de teste",
    campaign_type="email",  # ⬅️ IMPORTANTE
    email_subject="Olá {{primeiro_nome}}, bem-vindo!",
    status="draft",
    track_opens=True,
    track_clicks=True
)

# Criar mensagem
message = CampaignMessage.objects.create(
    campaign=campaign,
    content="Olá {{nome}}, tudo bem? Este é um teste!",
    html_content="""
    <html>
    <body>
        <h1>Olá {{nome}}!</h1>
        <p>Este é um email de teste da plataforma Alrea.</p>
        <p>Esperamos que goste! 🚀</p>
        <a href="https://alrea.com">Visite nosso site</a>
    </body>
    </html>
    """,
    order=0
)

# Adicionar contato de teste (use seu próprio email!)
contact = Contact.objects.create(
    tenant=tenant,
    name="Seu Nome",
    email="seu.email@exemplo.com",  # ⬅️ TROCAR
    phone="+5511999999999",
    is_active=True,
    opted_out=False
)

# Vincular contato à campanha
from apps.campaigns.models import CampaignContact
cc = CampaignContact.objects.create(
    campaign=campaign,
    contact=contact,
    status="pending"
)

campaign.total_contacts = 1
campaign.save()

print(f"✅ Campanha criada: {campaign.id}")
print(f"✅ Contato adicionado: {contact.email}")
```

### 3. Enviar Email de Teste

```python
from apps.campaigns.services.email_sender import EmailCampaignSender

# Criar sender
sender = EmailCampaignSender(campaign)

# Enviar
success, message = sender.send_next_email()

if success:
    print(f"✅ {message}")
    print(f"📧 Verifique seu email: {contact.email}")
else:
    print(f"❌ Erro: {message}")
```

### 4. Configurar Webhook (ngrok local)

```bash
# Terminal 1: Rodar backend
python manage.py runserver

# Terminal 2: Ngrok
ngrok http 8000

# Copiar URL (ex: https://abc123.ngrok.io)
# Ir em SendGrid:
# Settings > Mail Settings > Event Webhook
# HTTP POST URL: https://abc123.ngrok.io/api/campaigns/webhooks/sendgrid/
# Selecionar eventos: Delivered, Opened, Clicked, Bounced, Spam Report
```

---

## 📊 MÉTRICAS DE SUCESSO

### O que monitorar nos primeiros 30 dias:

```python
# Dashboard inicial - Métricas críticas
✅ Delivery Rate > 95%
✅ Bounce Rate < 2%
✅ Spam Complaint Rate < 0.1%
⭐ Open Rate: 15-25% é bom
⭐ Click Rate: 2-5% é bom
```

### Script de Monitoring

```python
# backend/scripts/monitor_email_health.py
from apps.campaigns.models import EmailProvider, Campaign

def check_email_health():
    """Verifica health dos email providers"""
    
    providers = EmailProvider.objects.filter(is_active=True)
    
    for p in providers:
        bounce_rate = (p.total_bounced / p.total_sent * 100) if p.total_sent > 0 else 0
        delivery_rate = (p.total_delivered / p.total_sent * 100) if p.total_sent > 0 else 0
        
        print(f"\n📊 {p.name} ({p.provider_type})")
        print(f"  ✉️ Enviados: {p.total_sent}")
        print(f"  ✅ Entregues: {p.total_delivered} ({delivery_rate:.1f}%)")
        print(f"  ⚠️ Bounces: {p.total_bounced} ({bounce_rate:.1f}%)")
        print(f"  💚 Health Score: {p.health_score}")
        
        # Alertas
        if bounce_rate > 5:
            print(f"  🚨 ALERTA: Bounce rate alto!")
        if delivery_rate < 95 and p.total_sent > 100:
            print(f"  ⚠️ ATENÇÃO: Delivery rate baixo!")
        if p.health_score < 70:
            print(f"  ⚠️ ATENÇÃO: Health score baixo!")

# Rodar:
# python manage.py shell
# exec(open('scripts/monitor_email_health.py').read())
# check_email_health()
```

---

## 🔧 TROUBLESHOOTING

### Problema: Emails não chegam

**Checklist:**
```
□ API Key válida?
□ Domínio verificado no SendGrid?
□ SPF/DKIM configurados?
□ From email usa domínio verificado?
□ Email não está em sandbox mode?
□ Destinatário não está em blacklist?
```

**Teste:**
```python
# Teste direto SendGrid (sem campanha)
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email='campaigns@alrea.com',
    to_emails='seu.email@exemplo.com',
    subject='Teste direto SendGrid',
    html_content='<strong>Funcionou!</strong>'
)

sg = SendGridAPIClient('SG.YOUR_API_KEY')
response = sg.send(message)
print(response.status_code)  # Deve ser 202
```

### Problema: Webhooks não chegam

```bash
# Ver logs do ngrok
ngrok http 8000 --log=stdout

# Testar endpoint manualmente
curl -X POST http://localhost:8000/api/campaigns/webhooks/sendgrid/ \
  -H "Content-Type: application/json" \
  -d '[{"event":"delivered","sg_message_id":"test123"}]'
```

### Problema: Bounce rate alto

**Causas comuns:**
- Lista velha (emails inativos)
- Typos em emails
- Domínios inexistentes
- Caixas cheias

**Solução:**
```python
# Limpar lista antes de campanha
from apps.contacts.models import Contact

# 1. Remover emails claramente inválidos
Contact.objects.filter(email__icontains='@test').update(is_active=False)
Contact.objects.filter(email__icontains='example.com').update(is_active=False)

# 2. Validar formato
import re
email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

for contact in Contact.objects.filter(email__isnull=False):
    if not re.match(email_regex, contact.email):
        contact.is_active = False
        contact.save()
        print(f"❌ Email inválido: {contact.email}")
```

---

## 📚 RECURSOS ÚTEIS

### SendGrid Dashboard

- **Activity:** https://app.sendgrid.com/email_activity
- **Stats:** https://app.sendgrid.com/statistics
- **Suppressions:** https://app.sendgrid.com/suppressions

### Testar Deliverability

```bash
# Mail Tester (grátis, 3 testes/dia)
# 1. Acessar https://www.mail-tester.com/
# 2. Copiar email temporário mostrado
# 3. Enviar campanha de teste para esse email
# 4. Clicar em "Check Score"
# 5. Objetivo: score > 8/10
```

### Validar SPF/DKIM

```bash
# MXToolbox
https://mxtoolbox.com/SuperTool.aspx

# Digitar: alrea.com
# Ver:
# - SPF Record
# - DKIM Record  
# - DMARC Record
```

---

## ✅ CHECKLIST FINAL - DIA 1

Antes de dormir no primeiro dia:

```
□ SendGrid account criada
□ API key gerada e salva
□ Variáveis de ambiente configuradas
□ Dependências instaladas
□ Migration criada e testada localmente
□ EmailProvider model funcionando
□ SendGridService testado (envio manual)
□ Webhook endpoint criado
□ Ngrok rodando (para testes)
□ Email de teste enviado e recebido
□ Webhook recebeu evento "delivered"

Se todos ✅ acima OK: Dia 1 completo! 🎉
```

---

**Dúvidas? Continue para o PLANO_IMPLEMENTACAO_CAMPANHAS_EMAIL.md completo!**



























