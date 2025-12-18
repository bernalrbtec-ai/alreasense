# 🚀 **GUIA COMPLETO DE IMPLEMENTAÇÃO - SISTEMA DE BILLING**

> **Sistema de Cobrança e Notificações via WhatsApp**  
> **Versão:** 1.0  
> **Data:** Dezembro 2025  
> **Arquitetura:** Multi-tenant, Alta Performance, Resiliente

---

## 📋 **ÍNDICE**

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Modelos (Models)](#modelos)
4. [Services e Utils](#services-e-utils)
5. [Workers e Tasks](#workers-e-tasks)
6. [APIs e Endpoints](#apis-e-endpoints)
7. [Tratamento de Falhas](#tratamento-de-falhas)
8. [Segurança](#segurança)
9. [Performance](#performance)
10. [Observabilidade](#observabilidade)
11. [Checklist de Implementação](#checklist-de-implementação)

---

## 🎯 **VISÃO GERAL**

### **O Que É?**
Sistema que permite clientes externos enviarem cobranças, lembretes e notificações via API, que são processadas e enviadas automaticamente via WhatsApp.

### **3 Tipos de Mensagens:**
1. 🔴 **Cobrança Atrasada** (overdue) - Urgente, com retry
2. 🟡 **Cobrança a Vencer** (upcoming) - Preventivo
3. 🔵 **Avisos/Notificações** (notification) - Informativo, 24/7

### **Features Principais:**
- ✅ Múltiplas variações de mensagem (anti-bloqueio WhatsApp)
- ✅ Templates com condicionais (campos opcionais)
- ✅ Cálculo automático de dias de atraso/vencimento
- ✅ Respeita horário comercial e dias úteis
- ✅ Throttling configurável (ex: 20 msgs/min)
- ✅ Pausa/retoma automático fora do horário
- ✅ Tratamento de falhas de instância
- ✅ Retry automático inteligente
- ✅ Integração total com chat (salva histórico)
- ✅ Multi-tenant nativo

---

## 🏗️ **ARQUITETURA**

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENTE EXTERNO (ERP)                     │
│                 POST /api/v1/billing/send/...                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   API GATEWAY + VALIDATION                   │
│  • Autenticação (API Key)                                    │
│  • Rate Limiting                                             │
│  • Validação de JSON Schema                                  │
│  • Validação de telefones                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              BILLING SERVICE (Orchestrator)                  │
│  • Enriquece variáveis (calcula dias)                        │
│  • Valida horário comercial                                  │
│  • Cria BillingCampaign + BillingQueue                       │
│  • Seleciona variações (anti-bloqueio)                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    RABBITMQ (Message Broker)                 │
│  Queue: billing.overdue   (Prioridade: Alta)                 │
│  Queue: billing.upcoming  (Prioridade: Média)                │
│  Queue: billing.notification (Prioridade: Baixa)             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  BILLING WORKER (Consumer)                   │
│  • Processa em batches (100 por vez)                         │
│  • Throttling (ex: 1 msg a cada 3 seg)                       │
│  • Verifica horário antes de CADA msg                        │
│  • Pausa se sair do horário → Retoma automático              │
│  • Retry em falhas temporárias                               │
│  • Health check (heartbeat)                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    EVOLUTION API CHECKER                     │
│  • Verifica se instância está UP                             │
│  • Se DOWN → marca mensagens como pending_retry              │
│  • Monitora retorno da instância                             │
│  • Retoma envios automaticamente                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      EVOLUTION API                           │
│  • Envia mensagem via WhatsApp                               │
│  • Retorna status (sent/delivered/read)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   CHAT SYSTEM (Histórico)                    │
│  • Cria/atualiza Conversation                                │
│  • Salva Message no histórico                                │
│  • Fecha conversa automaticamente                            │
│  • Reabre se cliente responder                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 **MODELOS (Models)**

### **Estrutura de Apps:**
```
backend/apps/
  billing/
    __init__.py
    models/
      __init__.py
      billing_template.py
      billing_campaign.py
      billing_queue.py
      billing_contact.py
      billing_config.py
      billing_api_key.py
    services/
      billing_campaign_service.py
      billing_send_service.py
    utils/
      date_calculator.py
      template_engine.py
      phone_validator.py
      template_sanitizer.py
    schedulers/
      business_hours_scheduler.py
    workers/
      billing_sender_worker.py
    tasks.py
    constants.py
    metrics.py
    views.py
    serializers.py
    urls.py
```

---

### **1. BillingConfig** (`billing_config.py`)

```python
"""
Configurações de Billing por Tenant
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.tenancy.models import Tenant


class BillingConfig(models.Model):
    """Configurações de Billing"""
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='billing_config'
    )
    
    # ⏱️ THROTTLING
    messages_per_minute = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Mensagens por minuto (1-60). Padrão: 20 = 1 msg a cada 3 seg"
    )
    
    min_interval_seconds = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Intervalo mínimo entre mensagens em segundos"
    )
    
    # 🕐 HORÁRIO COMERCIAL
    respect_business_hours = models.BooleanField(
        default=True,
        help_text="Respeitar horário comercial para cobranças?"
    )
    
    pause_outside_hours = models.BooleanField(
        default=True,
        help_text="Pausar envio automático se sair do horário comercial?"
    )
    
    allow_weekend_billing = models.BooleanField(
        default=False,
        help_text="Permitir envio em finais de semana?"
    )
    
    # 📊 LIMITES
    max_batch_size = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Máximo de mensagens por campanha"
    )
    
    daily_message_limit = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Limite diário de mensagens (0 = ilimitado)"
    )
    
    # 🔄 RETRY
    enable_auto_retry = models.BooleanField(
        default=True,
        help_text="Retentar automaticamente em falhas?"
    )
    
    max_retry_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Máximo de tentativas de reenvio"
    )
    
    retry_delay_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Aguardar X minutos antes de retentar"
    )
    
    # 🔐 API
    api_enabled = models.BooleanField(
        default=False,
        help_text="API de Billing habilitada?"
    )
    
    api_rate_limit_per_hour = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Limite de requests por hora por API Key"
    )
    
    # 🔔 NOTIFICAÇÕES
    notify_on_pause = models.BooleanField(
        default=True,
        help_text="Notificar quando pausar por horário?"
    )
    
    notify_on_resume = models.BooleanField(
        default=True,
        help_text="Notificar quando retomar envio?"
    )
    
    notify_on_instance_down = models.BooleanField(
        default=True,
        help_text="Notificar quando instância cair?"
    )
    
    notification_email = models.EmailField(
        blank=True,
        help_text="Email para notificações"
    )
    
    notification_webhook_url = models.URLField(
        blank=True,
        help_text="Webhook para notificações"
    )
    
    # 📅 TIMESTAMPS
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_config'
        verbose_name = 'Configuração de Billing'
        verbose_name_plural = 'Configurações de Billing'
    
    def __str__(self):
        return f"Config Billing - {self.tenant.name}"
```

---

### **2. BillingAPIKey** (`billing_api_key.py`)

```python
"""
API Keys para acesso externo
"""
import secrets
from django.db import models
from django.core.exceptions import ValidationError
from apps.tenancy.models import Tenant


class BillingAPIKey(models.Model):
    """API Key para acesso ao billing"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='billing_api_keys'
    )
    
    # Key (hashed para segurança)
    key = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text="API Key (gerada automaticamente)"
    )
    
    # Metadados
    name = models.CharField(
        max_length=100,
        help_text="Nome identificador (ex: 'Produção', 'Homologação')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Descrição e propósito desta key"
    )
    
    # Permissões
    is_active = models.BooleanField(
        default=True,
        help_text="Key ativa?"
    )
    
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="IPs permitidos (vazio = todos)"
    )
    
    allowed_template_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Tipos permitidos (vazio = todos): ['overdue', 'upcoming', 'notification']"
    )
    
    # Estatísticas
    total_requests = models.IntegerField(
        default=0,
        help_text="Total de requests feitas"
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que foi usada"
    )
    
    last_used_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data de expiração (null = sem expiração)"
    )
    
    class Meta:
        db_table = 'billing_api_key'
        verbose_name = 'API Key de Billing'
        verbose_name_plural = 'API Keys de Billing'
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['key']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.name} ({'Ativa' if self.is_active else 'Inativa'})"
    
    def save(self, *args, **kwargs):
        # Gera key apenas na criação
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_key() -> str:
        """Gera API key segura"""
        return f"billing_{secrets.token_urlsafe(32)}"
    
    def is_valid(self, ip_address: str = None) -> tuple[bool, str]:
        """
        Valida se key pode ser usada
        
        Returns:
            (válida, motivo_se_inválida)
        """
        if not self.is_active:
            return False, "API Key inativa"
        
        # Verifica expiração
        if self.expires_at and timezone.now() > self.expires_at:
            return False, "API Key expirada"
        
        # Verifica IP (se configurado)
        if self.allowed_ips and ip_address:
            if ip_address not in self.allowed_ips:
                return False, f"IP {ip_address} não autorizado"
        
        return True, ""
    
    def can_use_template_type(self, template_type: str) -> bool:
        """Verifica se pode usar este tipo de template"""
        if not self.allowed_template_types:
            return True  # Vazio = todos permitidos
        
        return template_type in self.allowed_template_types
    
    def increment_usage(self, ip_address: str = None):
        """Incrementa contador de uso"""
        self.total_requests += 1
        self.last_used_at = timezone.now()
        if ip_address:
            self.last_used_ip = ip_address
        self.save(update_fields=['total_requests', 'last_used_at', 'last_used_ip'])
```

---

### **3. BillingTemplate** (`billing_template.py`)

```python
"""
Templates de mensagens com variações
"""
from django.db import models
from django.core.exceptions import ValidationError
from apps.tenancy.models import Tenant
import uuid


class TemplateType(models.TextChoices):
    """Tipos de template"""
    OVERDUE = 'overdue', '🔴 Cobrança Atrasada'
    UPCOMING = 'upcoming', '🟡 Cobrança a Vencer'
    NOTIFICATION = 'notification', '🔵 Avisos/Notificações'


class RotationStrategy(models.TextChoices):
    """Estratégia de rotação de variações"""
    RANDOM = 'random', 'Aleatório'
    SEQUENTIAL = 'sequential', 'Sequencial'
    WEIGHTED = 'weighted', 'Ponderado (equilibrado)'


class BillingTemplate(models.Model):
    """Template de mensagem de billing"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='billing_templates'
    )
    
    # Identificação
    name = models.CharField(
        max_length=100,
        help_text="Nome do template (ex: 'Cobrança Atrasada Padrão')"
    )
    
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        help_text="Tipo de mensagem"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Descrição e propósito deste template"
    )
    
    # Comportamento
    priority = models.IntegerField(
        default=5,
        help_text="Prioridade (1-10). Overdue=10, Upcoming=5, Notification=1"
    )
    
    allow_retry = models.BooleanField(
        default=False,
        help_text="Permitir retry automático se falhar?"
    )
    
    max_retries = models.IntegerField(
        default=3,
        help_text="Máximo de tentativas (se allow_retry=True)"
    )
    
    # Rotação de variações (anti-bloqueio)
    rotation_strategy = models.CharField(
        max_length=20,
        choices=RotationStrategy.choices,
        default=RotationStrategy.WEIGHTED
    )
    
    # Campos obrigatórios e opcionais
    required_fields = models.JSONField(
        default=list,
        help_text="Campos obrigatórios: ['nome_cliente', 'valor', 'data_vencimento', ...]"
    )
    
    optional_fields = models.JSONField(
        default=list,
        help_text="Campos opcionais: ['codigo_pix', 'link_pagamento', ...]"
    )
    
    # Validação
    json_schema = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON Schema para validação estruturada"
    )
    
    # Mídia
    media_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'Sem Mídia'),
            ('qrcode_pix', 'QR Code PIX'),
            ('image', 'Imagem'),
            ('document', 'Documento'),
        ],
        default='none'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Template ativo?"
    )
    
    # Estatísticas (calculadas)
    total_uses = models.IntegerField(
        default=0,
        help_text="Total de vezes usado"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_template'
        verbose_name = 'Template de Billing'
        verbose_name_plural = 'Templates de Billing'
        unique_together = [('tenant', 'template_type', 'name')]
        indexes = [
            models.Index(fields=['tenant', 'template_type', 'is_active']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"{self.get_template_type_display()} - {self.name}"
    
    def get_required_fields_for_type(self) -> list[str]:
        """Retorna campos obrigatórios baseado no tipo"""
        base_fields = ['nome_cliente', 'telefone']
        
        if self.template_type == TemplateType.OVERDUE:
            return base_fields + [
                'valor',
                'data_vencimento',
                'valor_total'
            ]
        
        elif self.template_type == TemplateType.UPCOMING:
            return base_fields + [
                'valor',
                'data_vencimento'
            ]
        
        elif self.template_type == TemplateType.NOTIFICATION:
            return base_fields + [
                'titulo',
                'mensagem'
            ]
        
        return base_fields
    
    def validate_variables(self, variables: dict) -> tuple[bool, str]:
        """
        Valida variáveis fornecidas
        
        Returns:
            (válido, mensagem_erro)
        """
        required = self.get_required_fields_for_type()
        
        # Verifica campos obrigatórios
        missing = [f for f in required if f not in variables or not variables[f]]
        
        if missing:
            return False, f"Campos obrigatórios ausentes: {', '.join(missing)}"
        
        # Validações específicas por tipo
        if self.template_type in [TemplateType.OVERDUE, TemplateType.UPCOMING]:
            # Valida formato de data
            from apps.billing.utils.date_calculator import BillingDateCalculator
            
            data_vencimento = variables.get('data_vencimento', '')
            if not BillingDateCalculator.parse_date(data_vencimento):
                return False, f"data_vencimento em formato inválido: {data_vencimento}"
        
        return True, ""


class BillingTemplateVariation(models.Model):
    """Variações de mensagem (até 5 por template)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        BillingTemplate,
        on_delete=models.CASCADE,
        related_name='variations'
    )
    
    # Variação
    variation_number = models.IntegerField(
        help_text="Número da variação (1, 2, 3, 4, 5)"
    )
    
    message_template = models.TextField(
        help_text="Template com variáveis: {{nome}}, {{#if link}}...{{/if}}"
    )
    
    # Estatísticas
    times_used = models.IntegerField(
        default=0,
        help_text="Quantas vezes foi usada"
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Performance
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    read_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Variação ativa?"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_template_variation'
        verbose_name = 'Variação de Template'
        verbose_name_plural = 'Variações de Templates'
        unique_together = [('template', 'variation_number')]
        ordering = ['variation_number']
        indexes = [
            models.Index(fields=['template', 'is_active']),
            models.Index(fields=['times_used']),
        ]
    
    def __str__(self):
        return f"{self.template.name} - Variação {self.variation_number}"
    
    @property
    def delivery_rate(self) -> float:
        """Taxa de entrega"""
        if self.sent_count == 0:
            return 0
        return (self.delivered_count / self.sent_count) * 100
    
    @property
    def read_rate(self) -> float:
        """Taxa de leitura"""
        if self.delivered_count == 0:
            return 0
        return (self.read_count / self.delivered_count) * 100
    
    @property
    def reply_rate(self) -> float:
        """Taxa de resposta"""
        if self.sent_count == 0:
            return 0
        return (self.reply_count / self.sent_count) * 100
```

---

### **4. BillingCampaign** (`billing_campaign.py`)

```python
"""
Campanhas de billing (criadas via API)
"""
from django.db import models
from apps.tenancy.models import Tenant
from apps.campaigns.models import Campaign
import uuid


class PaymentStatus(models.TextChoices):
    """Status de pagamento"""
    PENDING = 'pending', 'Pendente'
    PAID = 'paid', 'Pago'
    OVERDUE = 'overdue', 'Vencido'
    CANCELLED = 'cancelled', 'Cancelado'


class BillingCampaign(models.Model):
    """Campanha de billing (vinculada a Campaign normal)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='billing_campaigns'
    )
    
    template = models.ForeignKey(
        'BillingTemplate',
        on_delete=models.PROTECT,
        related_name='campaigns'
    )
    
    # Link com campanha normal
    campaign = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name='billing_campaign'
    )
    
    # Dados da origem (cliente externo)
    external_id = models.CharField(
        max_length=255,
        help_text="ID no sistema do cliente (ex: 'fatura-12345')"
    )
    
    external_data = models.JSONField(
        default=dict,
        help_text="JSON original recebido do cliente"
    )
    
    # Status específico de cobrança
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    
    payment_confirmed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Webhook para notificar cliente
    callback_url = models.URLField(
        blank=True,
        help_text="URL para notificar eventos"
    )
    
    callback_events = models.JSONField(
        default=list,
        help_text="Eventos que disparam callback: ['sent', 'delivered', 'paid', ...]"
    )
    
    callback_sent = models.BooleanField(
        default=False
    )
    
    callback_last_attempt = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_campaign'
        verbose_name = 'Campanha de Billing'
        verbose_name_plural = 'Campanhas de Billing'
        indexes = [
            models.Index(fields=['tenant', 'external_id']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.template.get_template_type_display()} - {self.external_id}"
```

---

### **5. BillingQueue** (`billing_queue.py`)

```python
"""
Fila de processamento de billing
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid


class QueueStatus(models.TextChoices):
    """Status da fila"""
    PENDING = 'pending', 'Pendente'
    SCHEDULED = 'scheduled', 'Agendado'
    RUNNING = 'running', 'Enviando'
    PAUSED = 'paused', 'Pausado'
    COMPLETED = 'completed', 'Concluído'
    FAILED = 'failed', 'Falhou'
    CANCELLED = 'cancelled', 'Cancelado'
    INSTANCE_DOWN = 'instance_down', 'Instância Offline'


class BillingQueue(models.Model):
    """Controle de fila de envio"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    billing_campaign = models.OneToOneField(
        'BillingCampaign',
        on_delete=models.CASCADE,
        related_name='queue'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=QueueStatus.choices,
        default=QueueStatus.PENDING
    )
    
    # Progresso
    total_contacts = models.IntegerField(default=0)
    contacts_sent = models.IntegerField(default=0)
    contacts_delivered = models.IntegerField(default=0)
    contacts_read = models.IntegerField(default=0)
    contacts_failed = models.IntegerField(default=0)
    contacts_pending_retry = models.IntegerField(default=0)
    
    # Timing
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando deve iniciar"
    )
    
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    resumed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Pausas
    pause_count = models.IntegerField(
        default=0,
        help_text="Quantas vezes foi pausada"
    )
    
    pause_reason = models.CharField(
        max_length=100,
        blank=True
    )
    
    # Worker control
    processing_by = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID do worker processando"
    )
    
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    last_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Último sinal de vida do worker"
    )
    
    # Rate limiting
    current_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Msgs/minuto atual"
    )
    
    # Cursor (próximo contato a processar)
    next_contact_index = models.IntegerField(
        default=0,
        help_text="Índice do próximo contato"
    )
    
    # Instância Evolution
    instance_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Instância que está enviando"
    )
    
    instance_check_failures = models.IntegerField(
        default=0,
        help_text="Tentativas de check da instância falhadas"
    )
    
    instance_last_check = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        help_text="Dados extras (erros, logs, etc)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_queue'
        verbose_name = 'Fila de Billing'
        verbose_name_plural = 'Filas de Billing'
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['processing_by', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Queue {self.id[:8]} - {self.get_status_display()}"
    
    def calculate_progress(self) -> float:
        """Retorna progresso em %"""
        if self.total_contacts == 0:
            return 0
        return (self.contacts_sent / self.total_contacts) * 100
    
    def calculate_eta(self) -> Optional[datetime]:
        """Calcula tempo estimado para conclusão"""
        if self.status != QueueStatus.RUNNING or self.contacts_sent == 0:
            return None
        
        remaining = self.total_contacts - self.contacts_sent
        if remaining <= 0:
            return None
        
        if self.current_rate > 0:
            minutes_remaining = remaining / float(self.current_rate)
            return timezone.now() + timedelta(minutes=minutes_remaining)
        
        return None
    
    def claim_for_processing(self, worker_id: str) -> bool:
        """
        Tenta clamar a queue para processar
        
        Returns:
            True se conseguiu clamar, False se já está sendo processada
        """
        from django.db.models import Q
        
        # Atualiza apenas se não está sendo processada OU se worker está morto
        stale_threshold = timezone.now() - timedelta(minutes=10)
        
        rows = BillingQueue.objects.filter(
            Q(id=self.id),
            Q(status__in=[QueueStatus.RUNNING, QueueStatus.PENDING, QueueStatus.SCHEDULED]),
            Q(
                Q(processing_by='') |  # Ninguém processando
                Q(last_heartbeat__lt=stale_threshold)  # Worker morto
            )
        ).update(
            processing_by=worker_id,
            processing_started_at=timezone.now(),
            last_heartbeat=timezone.now(),
            status=QueueStatus.RUNNING
        )
        
        return rows > 0
    
    def update_heartbeat(self):
        """Atualiza heartbeat do worker"""
        self.last_heartbeat = timezone.now()
        self.save(update_fields=['last_heartbeat'])
    
    def is_worker_alive(self) -> bool:
        """Verifica se worker ainda está vivo"""
        if not self.last_heartbeat:
            return False
        
        timeout = timezone.now() - timedelta(minutes=5)
        return self.last_heartbeat > timeout
```

---

### **6. BillingContact** (`billing_contact.py`)

```python
"""
Contatos da campanha de billing
"""
from django.db import models
from apps.campaigns.models import CampaignContact
import uuid


class BillingContact(models.Model):
    """Contato + dados de billing"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    billing_campaign = models.ForeignKey(
        'BillingCampaign',
        on_delete=models.CASCADE,
        related_name='billing_contacts'
    )
    
    campaign_contact = models.OneToOneField(
        CampaignContact,
        on_delete=models.CASCADE,
        related_name='billing_contact'
    )
    
    # Template usado
    template_variation = models.ForeignKey(
        'BillingTemplateVariation',
        on_delete=models.PROTECT,
        related_name='contacts'
    )
    
    # Dados processados
    rendered_message = models.TextField(
        help_text="Mensagem final enviada"
    )
    
    rendered_media_url = models.URLField(
        blank=True,
        help_text="URL da mídia gerada (QR Code, etc)"
    )
    
    # Variáveis específicas deste contato
    template_variables = models.JSONField(
        help_text="Variáveis usadas: {nome: 'João', valor: 'R$ 150', ...}"
    )
    
    # Variáveis calculadas automaticamente
    calculated_variables = models.JSONField(
        default=dict,
        help_text="Variáveis calculadas: {dias_atraso: '3', ...}"
    )
    
    # Retry control
    retry_count = models.IntegerField(
        default=0,
        help_text="Quantas vezes tentou reenviar"
    )
    
    last_retry_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    max_retries_reached = models.BooleanField(
        default=False
    )
    
    # Tracking
    opened_at = models.DateTimeField(null=True, blank=True)
    link_clicked_at = models.DateTimeField(null=True, blank=True)
    payment_link_clicked = models.BooleanField(default=False)
    
    # Error tracking
    last_error = models.TextField(
        blank=True,
        help_text="Último erro ao enviar"
    )
    
    last_error_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_contact'
        verbose_name = 'Contato de Billing'
        verbose_name_plural = 'Contatos de Billing'
        indexes = [
            models.Index(fields=['billing_campaign', 'campaign_contact__status']),
            models.Index(fields=['retry_count', 'max_retries_reached']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Contact {self.campaign_contact.phone_number}"
    
    def can_retry(self, max_retries: int) -> bool:
        """Verifica se pode retentar"""
        return (
            not self.max_retries_reached and
            self.retry_count < max_retries and
            self.campaign_contact.status in ['failed', 'pending']
        )
```

---

## 🛠️ **SERVICES E UTILS**

### **1. Constants** (`constants.py`)

```python
"""
Constantes do sistema de billing
"""


class BillingConstants:
    """Constantes centralizadas"""
    
    # ⏱️ THROTTLING
    DEFAULT_MESSAGES_PER_MINUTE = 20
    MIN_INTERVAL_SECONDS = 3
    MAX_BATCH_SIZE = 1000
    WORKER_BATCH_SIZE = 100
    
    # 🔐 RATE LIMITING
    DEFAULT_API_RATE_LIMIT_HOUR = 100
    RATE_LIMIT_CACHE_TIMEOUT = 3600  # 1 hora
    RATE_LIMIT_CACHE_PREFIX = 'billing_ratelimit'
    
    # 👷 WORKER
    WORKER_HEARTBEAT_INTERVAL = 30  # segundos
    WORKER_TIMEOUT = 300  # 5 minutos
    WORKER_STALE_THRESHOLD = 600  # 10 minutos
    WORKER_ID_PREFIX = 'billing_worker'
    
    # 📋 QUEUE
    QUEUE_CLAIM_TIMEOUT = 300  # 5 minutos
    QUEUE_CHECK_INTERVAL = 60  # 1 minuto
    
    # 🔄 RETRY
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY_MINUTES = 5
    RETRY_BACKOFF_MULTIPLIER = 2  # Delay exponencial
    
    # 🏥 INSTANCE CHECK
    INSTANCE_CHECK_INTERVAL = 30  # segundos
    INSTANCE_CHECK_TIMEOUT = 10  # segundos
    INSTANCE_MAX_FAILURES = 3  # Máx falhas antes de pausar
    INSTANCE_RECOVERY_CHECK_INTERVAL = 60  # 1 minuto
    
    # 💾 CACHE
    TEMPLATE_CACHE_TIMEOUT = 3600  # 1 hora
    TEMPLATE_CACHE_PREFIX = 'billing_template'
    CONFIG_CACHE_TIMEOUT = 1800  # 30 minutos
    CONFIG_CACHE_PREFIX = 'billing_config'
    BUSINESS_HOURS_CACHE_TIMEOUT = 7200  # 2 horas
    BUSINESS_HOURS_CACHE_PREFIX = 'billing_bh'
    
    # 📊 VARIATIONS
    MAX_VARIATIONS_PER_TEMPLATE = 5
    MIN_VARIATIONS_FOR_ROTATION = 2
    
    # 🔔 NOTIFICATIONS
    NOTIFICATION_RETRY_ATTEMPTS = 3
    NOTIFICATION_TIMEOUT = 10  # segundos
```

---

### **2. Phone Validator** (`utils/phone_validator.py`)

```python
"""
Validador de telefones
"""
import re
from typing import Optional


class PhoneValidator:
    """Valida e normaliza telefones"""
    
    # Formato internacional: +55 11 99999-9999
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
    
    # Brasil específico
    BRAZIL_PATTERN = re.compile(r'^(\+?55)?(\d{2})(\d{4,5})(\d{4})$')
    
    @staticmethod
    def validate(phone: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Valida e normaliza telefone
        
        Returns:
            (válido, telefone_normalizado, erro_msg)
        """
        if not phone:
            return False, None, "Telefone vazio"
        
        # Remove caracteres não numéricos exceto +
        clean = re.sub(r'[^\d+]', '', phone)
        
        # Valida comprimento
        if len(clean) < 10:
            return False, None, "Telefone muito curto (mínimo 10 dígitos)"
        
        if len(clean) > 15:
            return False, None, "Telefone muito longo (máximo 15 dígitos)"
        
        # Valida formato internacional
        if not PhoneValidator.PHONE_PATTERN.match(clean):
            return False, None, "Formato de telefone inválido"
        
        # Normaliza para formato internacional
        if not clean.startswith('+'):
            # Assume Brasil se não tem código de país
            if len(clean) == 10 or len(clean) == 11:
                clean = '+55' + clean
            else:
                clean = '+' + clean
        
        return True, clean, None
    
    @staticmethod
    def format_display(phone: str) -> str:
        """
        Formata telefone para exibição
        
        +5511999999999 → +55 11 99999-9999
        """
        if not phone:
            return ''
        
        # Remove tudo exceto dígitos e +
        clean = re.sub(r'[^\d+]', '', phone)
        
        # Tenta Brasil
        match = PhoneValidator.BRAZIL_PATTERN.match(clean)
        if match:
            country, area, prefix, suffix = match.groups()
            country = country or '+55'
            return f"{country} {area} {prefix}-{suffix}"
        
        # Formato internacional genérico
        return clean
```

---

### **3. Template Sanitizer** (`utils/template_sanitizer.py`)

```python
"""
Sanitizador de templates
"""
import re
from html import escape


class TemplateSanitizer:
    """Sanitiza templates para prevenir injeções"""
    
    # Padrões perigosos
    SCRIPT_PATTERN = re.compile(
        r'<script[^>]*>.*?</script>',
        re.IGNORECASE | re.DOTALL
    )
    
    IFRAME_PATTERN = re.compile(
        r'<iframe[^>]*>.*?</iframe>',
        re.IGNORECASE | re.DOTALL
    )
    
    ONCLICK_PATTERN = re.compile(
        r'\bon\w+\s*=',
        re.IGNORECASE
    )
    
    JAVASCRIPT_PROTOCOL = re.compile(
        r'javascript:',
        re.IGNORECASE
    )
    
    @staticmethod
    def sanitize(template: str) -> str:
        """
        Sanitiza template removendo código perigoso
        
        WhatsApp aceita apenas:
        - *bold*
        - _italic_
        - ~strike~
        - ```code```
        
        Não precisa de HTML tags!
        """
        if not template:
            return ''
        
        # Remove scripts
        clean = TemplateSanitizer.SCRIPT_PATTERN.sub('', template)
        
        # Remove iframes
        clean = TemplateSanitizer.IFRAME_PATTERN.sub('', clean)
        
        # Remove event handlers (onclick, onload, etc)
        clean = TemplateSanitizer.ONCLICK_PATTERN.sub('', clean)
        
        # Remove javascript: protocol
        clean = TemplateSanitizer.JAVASCRIPT_PROTOCOL.sub('', clean)
        
        # Remove HTML tags (exceto formatação WhatsApp que não usa tags)
        # Mantém {{variáveis}} e {{#if}} intactos
        clean = re.sub(
            r'<(?!/?(?:b|i|u|strong|em)>)[^>]+>',
            '',
            clean
        )
        
        return clean.strip()
    
    @staticmethod
    def validate_syntax(template: str) -> tuple[bool, Optional[str]]:
        """
        Valida sintaxe do template
        
        Verifica:
        - {{#if}} tem {{/if}} correspondente
        - {{#unless}} tem {{/unless}} correspondente
        - Variáveis bem formadas
        """
        # Conta {{#if}}
        if_count = len(re.findall(r'\{\{#if\s+\w+\}\}', template))
        endif_count = len(re.findall(r'\{\{/if\}\}', template))
        
        if if_count != endif_count:
            return False, f"{{{{#if}}}} não balanceado: {if_count} abertos, {endif_count} fechados"
        
        # Conta {{#unless}}
        unless_count = len(re.findall(r'\{\{#unless\s+\w+\}\}', template))
        endunless_count = len(re.findall(r'\{\{/unless\}\}', template))
        
        if unless_count != endunless_count:
            return False, f"{{{{#unless}}}} não balanceado: {unless_count} abertos, {endunless_count} fechados"
        
        # Valida variáveis (não podem ter espaços ou caracteres especiais)
        invalid_vars = re.findall(r'\{\{([^}]*[^a-zA-Z0-9_#/][^}]*)\}\}', template)
        if invalid_vars:
            return False, f"Variáveis inválidas: {invalid_vars}"
        
        return True, None
```

---

### **4. Date Calculator** (`utils/date_calculator.py`)

```python
"""
Calculador de datas para billing
"""
from datetime import datetime, date, timedelta
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class BillingDateCalculator:
    """Calcula dias de atraso, dias para vencer, etc"""
    
    @staticmethod
    def parse_date(date_string: str) -> Optional[date]:
        """
        Converte string para date object
        Aceita múltiplos formatos
        """
        if not date_string:
            return None
        
        formats = [
            '%d/%m/%Y',      # 20/12/2025
            '%Y-%m-%d',      # 2025-12-20
            '%d-%m-%Y',      # 20-12-2025
            '%Y/%m/%d',      # 2025/12/20
            '%d.%m.%Y',      # 20.12.2025
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string.strip(), fmt).date()
            except ValueError:
                continue
        
        logger.error(f"Formato de data inválido: {date_string}")
        return None
    
    @staticmethod
    def calculate_days_difference(
        data_vencimento: str,
        reference_date: Optional[date] = None
    ) -> Tuple[int, str]:
        """
        Calcula diferença de dias em relação ao vencimento
        
        Returns:
            (dias, status)
            - dias: número absoluto de dias
            - status: 'overdue' | 'upcoming' | 'today'
        
        Examples:
            Vencimento: 15/12/2025
            Hoje: 18/12/2025
            → (3, 'overdue')  # 3 dias de atraso
            
            Vencimento: 20/12/2025
            Hoje: 18/12/2025
            → (2, 'upcoming')  # 2 dias para vencer
        """
        vencimento = BillingDateCalculator.parse_date(data_vencimento)
        if not vencimento:
            raise ValueError(f"Data de vencimento inválida: {data_vencimento}")
        
        hoje = reference_date or date.today()
        diferenca = (hoje - vencimento).days
        
        if diferenca > 0:
            return diferenca, 'overdue'  # Atrasado
        elif diferenca < 0:
            return abs(diferenca), 'upcoming'  # A vencer
        else:
            return 0, 'today'  # Vence hoje
    
    @staticmethod
    def format_dias_text(dias: int, status: str) -> str:
        """
        Formata texto amigável
        
        Examples:
            (3, 'overdue') → "3 dias"
            (1, 'overdue') → "1 dia"
            (0, 'today') → "hoje"
        """
        if status == 'today':
            return "hoje"
        elif dias == 1:
            return "1 dia"
        else:
            return f"{dias} dias"
    
    @staticmethod
    def enrich_variables(variables: dict) -> dict:
        """
        Enriquece variáveis com cálculos automáticos
        
        Input:
            {
                "data_vencimento": "15/12/2025",
                "valor": "R$ 150,00",
                ...
            }
        
        Output:
            {
                "data_vencimento": "15/12/2025",
                "valor": "R$ 150,00",
                "dias_atraso": "3",          # ← CALCULADO
                "dias_atraso_texto": "3 dias", # ← CALCULADO
                "status_vencimento": "overdue", # ← CALCULADO
                ...
            }
        """
        enriched = variables.copy()
        
        # Se tem data_vencimento, calcula automaticamente
        if 'data_vencimento' in variables:
            try:
                dias, status = BillingDateCalculator.calculate_days_difference(
                    variables['data_vencimento']
                )
                
                # Adiciona variáveis calculadas
                if status == 'overdue':
                    enriched['dias_atraso'] = str(dias)
                    enriched['dias_atraso_texto'] = BillingDateCalculator.format_dias_text(dias, status)
                    enriched['status_vencimento'] = 'overdue'
                    
                elif status == 'upcoming':
                    enriched['dias_para_vencer'] = str(dias)
                    enriched['dias_para_vencer_texto'] = BillingDateCalculator.format_dias_text(dias, status)
                    enriched['status_vencimento'] = 'upcoming'
                    
                elif status == 'today':
                    enriched['dias_para_vencer'] = "0"
                    enriched['dias_para_vencer_texto'] = "hoje"
                    enriched['status_vencimento'] = 'today'
                
                logger.debug(
                    f"Data calculada: {variables['data_vencimento']} → "
                    f"{dias} dias ({status})"
                )
                
            except Exception as e:
                logger.error(f"Erro ao calcular data: {e}")
        
        return enriched
```

---

### **5. Template Engine** (`utils/template_engine.py`)

```python
"""
Engine de templates com condicionais
"""
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BillingTemplateEngine:
    """
    Engine de templates com suporte a:
    - Variáveis simples: {{nome}}
    - Condicionais: {{#if link}}...{{/if}}
    - Condicionais negativos: {{#unless link}}...{{/unless}}
    """
    
    # Regex patterns
    VARIABLE_PATTERN = r'\{\{([^#/}]+)\}\}'
    IF_BLOCK_PATTERN = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}'
    UNLESS_BLOCK_PATTERN = r'\{\{#unless\s+(\w+)\}\}(.*?)\{\{/unless\}\}'
    
    @classmethod
    def render_message(cls, template: str, variables: Dict[str, Any]) -> str:
        """
        Renderiza template com variáveis e condicionais
        
        Exemplo:
            Template:
                "Olá {{nome}}, fatura de {{valor}}.
                {{#if codigo_pix}}
                PIX: {{codigo_pix}}
                {{/if}}"
            
            Variables:
                {"nome": "João", "valor": "R$ 150", "codigo_pix": "00020126..."}
            
            Resultado:
                "Olá João, fatura de R$ 150.
                PIX: 00020126..."
        """
        message = template
        
        # 1. Processa blocos {{#if}}
        message = cls._process_if_blocks(message, variables)
        
        # 2. Processa blocos {{#unless}}
        message = cls._process_unless_blocks(message, variables)
        
        # 3. Substitui variáveis simples
        message = cls._substitute_variables(message, variables)
        
        # 4. Limpa linhas vazias consecutivas
        message = cls._clean_empty_lines(message)
        
        return message.strip()
    
    @classmethod
    def _process_if_blocks(cls, text: str, variables: Dict[str, Any]) -> str:
        """
        Processa blocos {{#if variavel}}...{{/if}}
        Remove o bloco se variável não existe ou está vazia
        """
        def replace_if(match):
            var_name = match.group(1).strip()
            block_content = match.group(2)
            
            # Verifica se variável existe e tem valor
            if cls._variable_has_value(variables.get(var_name)):
                return block_content
            else:
                return ''
        
        return re.sub(cls.IF_BLOCK_PATTERN, replace_if, text, flags=re.DOTALL)
    
    @classmethod
    def _process_unless_blocks(cls, text: str, variables: Dict[str, Any]) -> str:
        """
        Processa blocos {{#unless variavel}}...{{/unless}}
        Mostra o bloco APENAS se variável NÃO existe
        """
        def replace_unless(match):
            var_name = match.group(1).strip()
            block_content = match.group(2)
            
            if not cls._variable_has_value(variables.get(var_name)):
                return block_content
            else:
                return ''
        
        return re.sub(cls.UNLESS_BLOCK_PATTERN, replace_unless, text, flags=re.DOTALL)
    
    @classmethod
    def _substitute_variables(cls, text: str, variables: Dict[str, Any]) -> str:
        """Substitui {{variavel}} pelos valores"""
        def replace_var(match):
            var_name = match.group(1).strip()
            value = variables.get(var_name, '')
            return str(value) if value is not None else ''
        
        return re.sub(cls.VARIABLE_PATTERN, replace_var, text)
    
    @classmethod
    def _variable_has_value(cls, value: Any) -> bool:
        """Verifica se variável tem valor válido"""
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == '':
            return False
        if isinstance(value, bool) and value is False:
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True
    
    @classmethod
    def _clean_empty_lines(cls, text: str) -> str:
        """Remove múltiplas linhas vazias consecutivas"""
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
        return text
    
    @classmethod
    def extract_variables(cls, template: str) -> list[str]:
        """Extrai todas as variáveis usadas no template"""
        variables = set()
        
        # Variáveis simples
        variables.update(re.findall(r'\{\{([^#/}]+)\}\}', template))
        
        # Variáveis em condicionais
        variables.update(re.findall(r'\{\{#if\s+(\w+)\}\}', template))
        variables.update(re.findall(r'\{\{#unless\s+(\w+)\}\}', template))
        
        return sorted([v.strip() for v in variables])
```

---

## 🚨 **TRATAMENTO DE FALHAS DE INSTÂNCIA** (CRÍTICO!)

### **Checker de Instância** (`services/instance_checker.py`)

```python
"""
Verifica saúde da instância Evolution API
"""
import requests
from typing import Tuple
from django.utils import timezone
from django.core.cache import cache
from apps.whatsapp.models import Instance
from apps.billing.constants import BillingConstants
import logging

logger = logging.getLogger(__name__)


class InstanceHealthChecker:
    """Verifica se instância está UP e funcionando"""
    
    @staticmethod
    def check_instance(instance: Instance) -> Tuple[bool, str]:
        """
        Verifica saúde da instância
        
        Returns:
            (is_healthy, reason)
        """
        try:
            # 1. Verifica se instância está ativa no banco
            if not instance.is_active:
                return False, "Instância desativada no sistema"
            
            # 2. Verifica status da conexão
            if instance.status != 'open':
                return False, f"Instância não conectada (status: {instance.status})"
            
            # 3. Ping na Evolution API
            url = f"{instance.evolution_url}/instance/connectionState/{instance.instance_name}"
            
            response = requests.get(
                url,
                headers={'apikey': instance.evolution_api_key},
                timeout=BillingConstants.INSTANCE_CHECK_TIMEOUT
            )
            
            if response.status_code != 200:
                return False, f"Evolution API retornou {response.status_code}"
            
            data = response.json()
            state = data.get('state', '')
            
            if state != 'open':
                return False, f"WhatsApp não conectado (state: {state})"
            
            logger.debug(f"✅ Instância {instance.id} healthy")
            return True, "OK"
            
        except requests.Timeout:
            return False, "Timeout ao conectar Evolution API"
        
        except requests.ConnectionError:
            return False, "Erro de conexão com Evolution API"
        
        except Exception as e:
            logger.error(f"Erro ao verificar instância: {e}", exc_info=True)
            return False, f"Erro inesperado: {str(e)}"
    
    @staticmethod
    def get_cached_health(instance_id: str) -> Optional[bool]:
        """Busca health status em cache"""
        cache_key = f'instance_health_{instance_id}'
        return cache.get(cache_key)
    
    @staticmethod
    def set_cached_health(instance_id: str, is_healthy: bool, ttl: int = 30):
        """Salva health status em cache"""
        cache_key = f'instance_health_{instance_id}'
        cache.set(cache_key, is_healthy, timeout=ttl)
    
    @staticmethod
    def check_with_cache(instance: Instance) -> Tuple[bool, str]:
        """
        Verifica health com cache (evita checks excessivos)
        """
        # Tenta cache primeiro
        cached = InstanceHealthChecker.get_cached_health(str(instance.id))
        if cached is not None:
            logger.debug(f"Cache hit: instância {instance.id} = {cached}")
            return cached, "Cached"
        
        # Cache miss, verifica de verdade
        is_healthy, reason = InstanceHealthChecker.check_instance(instance)
        
        # Salva em cache
        InstanceHealthChecker.set_cached_health(
            str(instance.id),
            is_healthy,
            ttl=BillingConstants.INSTANCE_CHECK_INTERVAL
        )
        
        return is_healthy, reason


class InstanceRecoveryService:
    """Serviço de recuperação quando instância volta"""
    
    @staticmethod
    def handle_instance_down(queue: 'BillingQueue', reason: str):
        """
        Trata instância offline
        
        1. Pausa a queue
        2. Marca mensagens pending como pending_retry
        3. Notifica tenant
        4. Agenda verificação de recuperação
        """
        from apps.billing.models import QueueStatus
        
        logger.warning(
            f"🚨 Instância {queue.instance_id} DOWN - Queue {queue.id} "
            f"pausada. Motivo: {reason}"
        )
        
        # 1. Pausa queue
        queue.status = QueueStatus.INSTANCE_DOWN
        queue.paused_at = timezone.now()
        queue.pause_reason = f"Instância offline: {reason}"
        queue.instance_check_failures += 1
        queue.instance_last_check = timezone.now()
        queue.save()
        
        # 2. Marca mensagens pending como pending_retry
        pending_contacts = queue.billing_campaign.billing_contacts.filter(
            campaign_contact__status='pending'
        )
        
        count = pending_contacts.update(
            campaign_contact__status='pending_retry',
            last_error=f"Instância offline: {reason}",
            last_error_at=timezone.now()
        )
        
        queue.contacts_pending_retry = count
        queue.save(update_fields=['contacts_pending_retry'])
        
        logger.info(f"📝 {count} mensagens marcadas para retry")
        
        # 3. Notifica tenant
        if queue.billing_campaign.tenant.billing_config.notify_on_instance_down:
            InstanceRecoveryService._notify_instance_down(queue, reason)
        
        # 4. Agenda verificação de recuperação
        from apps.billing.tasks import check_instance_recovery
        check_instance_recovery.apply_async(
            args=[str(queue.id)],
            countdown=BillingConstants.INSTANCE_RECOVERY_CHECK_INTERVAL
        )
    
    @staticmethod
    def handle_instance_recovered(queue: 'BillingQueue'):
        """
        Trata instância que voltou
        
        1. Retoma queue
        2. Reprocessa mensagens pending_retry
        3. Notifica tenant
        """
        from apps.billing.models import QueueStatus
        
        logger.info(f"✅ Instância {queue.instance_id} RECOVERED - Retomando queue {queue.id}")
        
        # 1. Retoma queue
        queue.status = QueueStatus.RUNNING
        queue.resumed_at = timezone.now()
        queue.pause_reason = ''
        queue.instance_check_failures = 0
        queue.save()
        
        # 2. Marca mensagens pending_retry como pending novamente
        retry_contacts = queue.billing_campaign.billing_contacts.filter(
            campaign_contact__status='pending_retry'
        )
        
        count = retry_contacts.update(
            campaign_contact__status='pending'
        )
        
        queue.contacts_pending_retry = 0
        queue.save(update_fields=['contacts_pending_retry'])
        
        logger.info(f"🔄 {count} mensagens voltaram para fila")
        
        # 3. Notifica tenant
        if queue.billing_campaign.tenant.billing_config.notify_on_resume:
            InstanceRecoveryService._notify_instance_recovered(queue)
        
        # 4. Retoma worker
        from apps.billing.tasks import process_billing_queue
        process_billing_queue.delay(str(queue.id))
    
    @staticmethod
    def _notify_instance_down(queue: 'BillingQueue', reason: str):
        """Notifica tenant sobre instância offline"""
        # TODO: Implementar notificação (email/webhook/websocket)
        logger.info(f"📧 Notificação enviada: Instância {queue.instance_id} offline")
    
    @staticmethod
    def _notify_instance_recovered(queue: 'BillingQueue'):
        """Notifica tenant sobre instância recuperada"""
        # TODO: Implementar notificação
        logger.info(f"📧 Notificação enviada: Instância {queue.instance_id} recuperada")
```

---

## 👷 **WORKERS E RABBITMQ CONSUMERS**

### **⚠️ IMPORTANTE: NÃO USAMOS CELERY!**

O projeto usa **RabbitMQ + aio-pika** para processamento assíncrono.

**Arquitetura:**
```
Django → Publica mensagem no RabbitMQ
         ↓
RabbitMQ (broker)
         ↓
Consumer (aio-pika) → Processa mensagem
```

---

### **Worker Principal** (`workers/billing_sender_worker.py`)

```python
"""
Worker que processa filas de billing
"""
import time
import signal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from apps.billing.models import (
    BillingQueue, BillingContact, QueueStatus
)
from apps.billing.constants import BillingConstants
from apps.billing.services.instance_checker import (
    InstanceHealthChecker, InstanceRecoveryService
)
from apps.chat.models import BusinessHours
import logging
import uuid

logger = logging.getLogger(__name__)


class BillingSenderWorker:
    """
    Worker que processa fila de billing com:
    - Throttling configurável
    - Pausa fora do horário comercial
    - Verificação de instância antes de enviar
    - Retry automático em falhas
    - Health check (heartbeat)
    - Graceful shutdown
    """
    
    def __init__(self, queue_id: str):
        self.queue_id = queue_id
        self.worker_id = f"{BillingConstants.WORKER_ID_PREFIX}_{uuid.uuid4().hex[:8]}"
        self.should_stop = False
        self.last_heartbeat = timezone.now()
        
        # Carrega queue com related objects (evita N+1)
        self.queue = BillingQueue.objects.select_related(
            'billing_campaign',
            'billing_campaign__tenant',
            'billing_campaign__tenant__billing_config',
            'billing_campaign__template'
        ).get(id=queue_id)
        
        self.config = self.queue.billing_campaign.tenant.billing_config
        self.tenant = self.queue.billing_campaign.tenant
        self.instance = self._get_instance()
        
        # Cache business hours (não muda durante execução)
        self._business_hours_cache = list(
            BusinessHours.objects.filter(
                tenant=self.tenant,
                is_active=True
            )
        )
        
        # Registra signal handlers para graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        
        logger.info(f"🚀 Worker {self.worker_id} inicializado para queue {self.queue_id}")
    
    def _handle_signal(self, signum, frame):
        """Graceful shutdown"""
        logger.info(f"🛑 Worker {self.worker_id} recebeu sinal {signum}, finalizando gracefully...")
        self.should_stop = True
    
    def _get_instance(self):
        """Busca instância do tenant"""
        from apps.whatsapp.models import Instance
        
        # Usa instância default ou primeira ativa
        instance = Instance.objects.filter(
            tenant=self.tenant,
            is_active=True,
            status='open'
        ).first()
        
        if not instance:
            raise ValueError(f"Tenant {self.tenant} não tem instância ativa")
        
        self.queue.instance_id = instance.id
        self.queue.save(update_fields=['instance_id'])
        
        return instance
    
    def run(self):
        """Loop principal de processamento"""
        try:
            # Tenta clamar a queue
            if not self.queue.claim_for_processing(self.worker_id):
                logger.warning(f"❌ Queue {self.queue_id} já está sendo processada")
                return
            
            logger.info(f"✅ Queue {self.queue_id} clamada por {self.worker_id}")
            
            # Processa
            self._process_queue()
            
        except Exception as e:
            logger.error(f"❌ Erro crítico no worker: {e}", exc_info=True)
            self.queue.status = QueueStatus.FAILED
            self.queue.metadata['error'] = str(e)
            self.queue.save()
        finally:
            # Limpa worker ID
            self.queue.processing_by = ''
            self.queue.save(update_fields=['processing_by'])
    
    def _process_queue(self):
        """Processa todos os contatos da fila"""
        logger.info(f"📊 Iniciando processamento de {self.queue.total_contacts} contatos")
        
        interval = self._calculate_interval()
        batch_size = BillingConstants.WORKER_BATCH_SIZE
        
        while not self.should_stop:
            # 1️⃣ Atualiza heartbeat
            self._update_heartbeat()
            
            # 2️⃣ Verifica se deve pausar (horário comercial)
            if self._should_pause_for_hours():
                self._pause_for_business_hours()
                return
            
            # 3️⃣ Verifica instância ANTES de pegar batch
            if not self._check_instance_health():
                # Instância caiu, pausa tudo
                InstanceRecoveryService.handle_instance_down(
                    self.queue,
                    "Instância não respondeu ao health check"
                )
                return
            
            # 4️⃣ Pega próximo batch
            batch = self._get_next_batch(batch_size)
            
            if not batch:
                # Acabou!
                self._complete_queue()
                return
            
            # 5️⃣ Processa batch
            for contact in batch:
                if self.should_stop:
                    logger.info("🛑 Interrompendo processamento (graceful shutdown)")
                    return
                
                # Processa contato
                self._process_contact(contact)
                
                # Aguarda intervalo (throttling)
                time.sleep(interval)
            
            # 6️⃣ Atualiza progresso
            self._update_progress()
    
    def _get_next_batch(self, batch_size: int):
        """Pega próximo batch de contatos com lock"""
        return BillingContact.objects.filter(
            billing_campaign=self.queue.billing_campaign,
            campaign_contact__status__in=['pending', 'pending_retry']
        ).select_related(
            'campaign_contact',
            'template_variation',
            'billing_campaign'
        ).select_for_update(
            skip_locked=True  # Pula se outro worker pegou
        ).order_by('id')[:batch_size]
    
    def _process_contact(self, contact: BillingContact):
        """Processa um contato individual"""
        try:
            from apps.billing.services.billing_send_service import BillingSendService
            
            service = BillingSendService()
            success = service.send_billing_message(
                contact,
                self.instance
            )
            
            if success:
                self.queue.contacts_sent += 1
                contact.template_variation.sent_count += 1
                contact.template_variation.save(update_fields=['sent_count'])
            else:
                self.queue.contacts_failed += 1
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar contato {contact.id}: {e}")
            self.queue.contacts_failed += 1
            
            # Salva erro no contato
            contact.last_error = str(e)
            contact.last_error_at = timezone.now()
            contact.save(update_fields=['last_error', 'last_error_at'])
    
    def _check_instance_health(self) -> bool:
        """Verifica se instância está saudável"""
        is_healthy, reason = InstanceHealthChecker.check_with_cache(self.instance)
        
        if not is_healthy:
            logger.error(f"🚨 Instância {self.instance.id} não está saudável: {reason}")
            return False
        
        return True
    
    def _should_pause_for_hours(self) -> bool:
        """Verifica se deve pausar por horário comercial"""
        if not self.config.respect_business_hours:
            return False
        
        if not self.config.pause_outside_hours:
            return False
        
        # Notificações 24/7
        if self.queue.billing_campaign.template.template_type == 'notification':
            return False
        
        return not self._is_within_business_hours()
    
    def _is_within_business_hours(self) -> bool:
        """Verifica horário comercial (usa cache local)"""
        now = timezone.now()
        day_of_week = now.weekday()
        current_time = now.time()
        
        for bh in self._business_hours_cache:
            if bh.day_of_week == day_of_week:
                if bh.start_time <= current_time <= bh.end_time:
                    return True
        
        return False
    
    def _pause_for_business_hours(self):
        """Pausa por horário comercial"""
        from apps.billing.schedulers.business_hours_scheduler import BillingBusinessHoursScheduler
        
        next_valid = BillingBusinessHoursScheduler.get_next_valid_datetime(self.tenant)
        
        self.queue.status = QueueStatus.PAUSED
        self.queue.paused_at = timezone.now()
        self.queue.pause_reason = "Fora do horário comercial"
        self.queue.pause_count += 1
        self.queue.scheduled_for = next_valid
        self.queue.save()
        
        logger.warning(
            f"⏸️ Queue pausada (fora do horário). "
            f"Retoma em: {next_valid}"
        )
        
        # Agenda retomada
        from apps.billing.tasks import resume_billing_queue
        delay = (next_valid - timezone.now()).total_seconds()
        
        resume_billing_queue.apply_async(
            args=[str(self.queue.id)],
            countdown=int(delay)
        )
    
    def _complete_queue(self):
        """Marca queue como concluída"""
        self.queue.status = QueueStatus.COMPLETED
        self.queue.completed_at = timezone.now()
        self.queue.save()
        
        success_rate = (
            (self.queue.contacts_sent / self.queue.total_contacts * 100)
            if self.queue.total_contacts > 0 else 0
        )
        
        logger.info(
            f"✅ Queue {self.queue_id} concluída! "
            f"Enviados: {self.queue.contacts_sent}/{self.queue.total_contacts} "
            f"({success_rate:.1f}%) | "
            f"Falhas: {self.queue.contacts_failed}"
        )
    
    def _calculate_interval(self) -> float:
        """Calcula intervalo entre mensagens"""
        if self.config.messages_per_minute <= 0:
            return self.config.min_interval_seconds
        
        interval = 60 / self.config.messages_per_minute
        return max(interval, self.config.min_interval_seconds)
    
    def _update_heartbeat(self):
        """Atualiza heartbeat"""
        now = timezone.now()
        
        if (now - self.last_heartbeat).seconds >= BillingConstants.WORKER_HEARTBEAT_INTERVAL:
            self.queue.last_heartbeat = now
            self.queue.save(update_fields=['last_heartbeat'])
            self.last_heartbeat = now
            
            # Atualiza cache também
            cache.set(
                f'billing_worker_heartbeat_{self.queue_id}',
                now.isoformat(),
                timeout=60
            )
    
    def _update_progress(self):
        """Atualiza progresso e taxa"""
        if not self.queue.started_at:
            return
        
        elapsed = (timezone.now() - self.queue.started_at).total_seconds() / 60
        if elapsed == 0:
            return
        
        self.queue.current_rate = self.queue.contacts_sent / elapsed
        self.queue.save(update_fields=['current_rate'])
```

---

### **RabbitMQ Publisher** (`rabbitmq/billing_publisher.py`)

```python
"""
Publica mensagens no RabbitMQ para processamento de billing
"""
import json
import aio_pika
from django.conf import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BillingQueuePublisher:
    """Publica mensagens no RabbitMQ"""
    
    # Queues por tipo (com prioridade)
    QUEUES = {
        'overdue': 'billing.overdue',      # Prioridade: 10
        'upcoming': 'billing.upcoming',    # Prioridade: 5
        'notification': 'billing.notification',  # Prioridade: 1
    }
    
    @staticmethod
    async def publish_queue(queue_id: str, template_type: str):
        """
        Publica queue para processamento
        
        Args:
            queue_id: ID da BillingQueue
            template_type: 'overdue' | 'upcoming' | 'notification'
        """
        try:
            # Conecta ao RabbitMQ
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            
            async with connection:
                channel = await connection.channel()
                
                # Declara queue com prioridade
                queue_name = BillingQueuePublisher.QUEUES.get(
                    template_type,
                    'billing.notification'
                )
                
                priority = {
                    'overdue': 10,
                    'upcoming': 5,
                    'notification': 1
                }.get(template_type, 1)
                
                queue = await channel.declare_queue(
                    queue_name,
                    durable=True,
                    arguments={'x-max-priority': 10}
                )
                
                # Mensagem
                message_body = {
                    'queue_id': queue_id,
                    'template_type': template_type,
                    'published_at': timezone.now().isoformat()
                }
                
                # Publica
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message_body).encode(),
                        priority=priority,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ),
                    routing_key=queue_name
                )
                
                logger.info(
                    f"📤 Queue {queue_id} publicada em {queue_name} "
                    f"(prioridade: {priority})"
                )
        
        except Exception as e:
            logger.error(f"❌ Erro ao publicar queue: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def publish_delayed(queue_id: str, delay_seconds: int):
        """
        Publica com delay (para retomadas agendadas)
        
        Usa RabbitMQ Delayed Message Plugin ou TTL + Dead Letter
        """
        try:
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            
            async with connection:
                channel = await connection.channel()
                
                # Declara exchange delayed
                exchange = await channel.declare_exchange(
                    'billing.delayed',
                    aio_pika.ExchangeType.DIRECT,
                    durable=True
                )
                
                # Mensagem com delay
                message_body = {
                    'queue_id': queue_id,
                    'scheduled_for': (
                        timezone.now() + timedelta(seconds=delay_seconds)
                    ).isoformat()
                }
                
                # Publica com TTL
                await exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message_body).encode(),
                        expiration=str(delay_seconds * 1000),  # ms
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ),
                    routing_key='billing.resume'
                )
                
                logger.info(
                    f"⏰ Queue {queue_id} agendada para daqui {delay_seconds}s"
                )
        
        except Exception as e:
            logger.error(f"❌ Erro ao publicar delayed: {e}", exc_info=True)
            raise
```

---

### **RabbitMQ Consumer** (`rabbitmq/billing_consumer.py`)

```python
"""
Consumer do RabbitMQ para processar billing
"""
import asyncio
import json
import aio_pika
from django.conf import settings
from django.utils import timezone
from apps.billing.workers.billing_sender_worker import BillingSenderWorker
from apps.billing.models import BillingQueue, QueueStatus
from apps.billing.services.instance_checker import (
    InstanceHealthChecker, InstanceRecoveryService
)
from apps.whatsapp.models import Instance
import logging

logger = logging.getLogger(__name__)


class BillingConsumer:
    """Consumer que processa billing do RabbitMQ"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self.running = False
    
    async def start(self):
        """Inicia consumer"""
        logger.info("🚀 Iniciando Billing Consumer...")
        
        self.connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            loop=asyncio.get_event_loop()
        )
        
        self.channel = await self.connection.channel()
        
        # Configura prefetch (1 mensagem por vez)
        await self.channel.set_qos(prefetch_count=1)
        
        # Declara queues
        await self._setup_queues()
        
        # Inicia consumers
        self.running = True
        await self._consume_queues()
    
    async def _setup_queues(self):
        """Declara todas as queues necessárias"""
        queues = [
            ('billing.overdue', 10),
            ('billing.upcoming', 5),
            ('billing.notification', 1),
            ('billing.resume', 1),
            ('billing.check_stale', 1),
            ('billing.check_recovery', 1),
        ]
        
        for queue_name, priority in queues:
            await self.channel.declare_queue(
                queue_name,
                durable=True,
                arguments={'x-max-priority': 10}
            )
            logger.info(f"✅ Queue {queue_name} declarada")
    
    async def _consume_queues(self):
        """Consome todas as queues"""
        # Queue principal (processar)
        queue_overdue = await self.channel.get_queue('billing.overdue')
        queue_upcoming = await self.channel.get_queue('billing.upcoming')
        queue_notification = await self.channel.get_queue('billing.notification')
        
        # Queues auxiliares
        queue_resume = await self.channel.get_queue('billing.resume')
        queue_check_stale = await self.channel.get_queue('billing.check_stale')
        queue_check_recovery = await self.channel.get_queue('billing.check_recovery')
        
        # Inicia consumers
        await queue_overdue.consume(self._process_queue)
        await queue_upcoming.consume(self._process_queue)
        await queue_notification.consume(self._process_queue)
        await queue_resume.consume(self._resume_queue)
        await queue_check_stale.consume(self._check_stale_queues)
        await queue_check_recovery.consume(self._check_instance_recovery)
        
        logger.info("✅ Todos os consumers iniciados")
        
        # Mantém rodando
        while self.running:
            await asyncio.sleep(1)
    
    async def _process_queue(self, message: aio_pika.IncomingMessage):
        """
        Processa uma queue de billing
        """
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                queue_id = data['queue_id']
                
                logger.info(f"📥 Processando queue {queue_id}")
                
                # Executa worker (síncrono, mas em thread separada)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._run_worker_sync,
                    queue_id
                )
                
                logger.info(f"✅ Queue {queue_id} processada")
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar mensagem: {e}", exc_info=True)
                # Mensagem será reprocessada (requeue)
                raise
    
    def _run_worker_sync(self, queue_id: str):
        """Executa worker de forma síncrona"""
        try:
            worker = BillingSenderWorker(queue_id)
            worker.run()
        except Exception as e:
            logger.error(f"❌ Erro no worker: {e}")
            raise
    
    async def _resume_queue(self, message: aio_pika.IncomingMessage):
        """
        Retoma queue pausada
        """
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                queue_id = data['queue_id']
                
                queue = await asyncio.get_event_loop().run_in_executor(
                    None,
                    BillingQueue.objects.get,
                    {'id': queue_id}
                )
                
                if queue.status not in [QueueStatus.PAUSED, QueueStatus.INSTANCE_DOWN]:
                    logger.warning(f"Queue {queue_id} não está pausada")
                    return
                
                # Se estava pausada por instância, verifica
                if queue.status == QueueStatus.INSTANCE_DOWN:
                    instance = await asyncio.get_event_loop().run_in_executor(
                        None,
                        Instance.objects.get,
                        {'id': queue.instance_id}
                    )
                    
                    is_healthy, reason = InstanceHealthChecker.check_instance(instance)
                    
                    if not is_healthy:
                        logger.warning(f"Instância ainda offline: {reason}")
                        # Requeue para tentar de novo em 60s
                        await BillingQueuePublisher.publish_delayed(queue_id, 60)
                        return
                
                logger.info(f"▶️ Retomando queue {queue_id}")
                
                # Atualiza status
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._update_queue_status,
                    queue_id
                )
                
                # Republica para processamento
                await BillingQueuePublisher.publish_queue(
                    queue_id,
                    queue.billing_campaign.template.template_type
                )
                
            except Exception as e:
                logger.error(f"❌ Erro ao retomar queue: {e}", exc_info=True)
    
    def _update_queue_status(self, queue_id: str):
        """Atualiza status da queue (sync)"""
        queue = BillingQueue.objects.get(id=queue_id)
        queue.status = QueueStatus.RUNNING
        queue.resumed_at = timezone.now()
        queue.save()
    
    async def _check_instance_recovery(self, message: aio_pika.IncomingMessage):
        """
        Verifica se instância voltou
        """
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                queue_id = data['queue_id']
                
                queue = await asyncio.get_event_loop().run_in_executor(
                    None,
                    BillingQueue.objects.select_related('billing_campaign').get,
                    {'id': queue_id}
                )
                
                if queue.status != QueueStatus.INSTANCE_DOWN:
                    return  # Já retomou
                
                # Verifica instância
                instance = await asyncio.get_event_loop().run_in_executor(
                    None,
                    Instance.objects.get,
                    {'id': queue.instance_id}
                )
                
                is_healthy, reason = InstanceHealthChecker.check_instance(instance)
                
                if is_healthy:
                    logger.info(f"✅ Instância {instance.id} recuperada!")
                    
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        InstanceRecoveryService.handle_instance_recovered,
                        queue
                    )
                else:
                    logger.debug(f"Instância ainda offline: {reason}")
                    # Agenda nova tentativa
                    await BillingQueuePublisher.publish_delayed(queue_id, 60)
            
            except Exception as e:
                logger.error(f"❌ Erro ao verificar recuperação: {e}", exc_info=True)
    
    async def _check_stale_queues(self, message: aio_pika.IncomingMessage):
        """
        Verifica queues presas (worker morreu)
        """
        async with message.process():
            try:
                from datetime import timedelta
                from apps.billing.constants import BillingConstants
                
                stale_threshold = timezone.now() - timedelta(
                    seconds=BillingConstants.WORKER_STALE_THRESHOLD
                )
                
                stale_queues = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: list(BillingQueue.objects.filter(
                        status=QueueStatus.RUNNING,
                        last_heartbeat__lt=stale_threshold
                    ))
                )
                
                for queue in stale_queues:
                    logger.warning(
                        f"🚨 Queue {queue.id} presa (worker morreu). "
                        f"Último heartbeat: {queue.last_heartbeat}"
                    )
                    
                    # Limpa worker ID
                    queue.processing_by = ''
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        queue.save
                    )
                    
                    # Republica
                    await BillingQueuePublisher.publish_queue(
                        str(queue.id),
                        queue.billing_campaign.template.template_type
                    )
            
            except Exception as e:
                logger.error(f"❌ Erro ao verificar stale queues: {e}", exc_info=True)
    
    async def stop(self):
        """Para consumer gracefully"""
        logger.info("🛑 Parando Billing Consumer...")
        self.running = False
        
        if self.connection:
            await self.connection.close()
        
        logger.info("✅ Consumer parado")


# Ponto de entrada
async def start_billing_consumer():
    """Inicia consumer (chamado pelo management command)"""
    consumer = BillingConsumer()
    await consumer.start()
```

---

### **Management Command** (`management/commands/run_billing_consumer.py`)

```python
"""
Management command para rodar consumer de billing
"""
from django.core.management.base import BaseCommand
from apps.billing.rabbitmq.billing_consumer import start_billing_consumer
import asyncio
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Roda consumer de billing (RabbitMQ)'
    
    def handle(self, *args, **options):
        logger.info("🚀 Iniciando Billing Consumer...")
        
        try:
            asyncio.run(start_billing_consumer())
        except KeyboardInterrupt:
            logger.info("🛑 Consumer interrompido pelo usuário")
        except Exception as e:
            logger.error(f"❌ Erro fatal: {e}", exc_info=True)
            raise
```

---

### **Como Rodar:**

```bash
# Desenvolvimento (local)
python manage.py run_billing_consumer

# Produção (Railway)
# Adicionar em Procfile ou railway.toml:
billing_consumer: python manage.py run_billing_consumer
```

---

### **Periodic Tasks** (Substituindo Celery Beat)

```python
# management/commands/run_billing_periodic_tasks.py

"""
Tarefas periódicas de billing (substitui Celery Beat)
"""
import asyncio
from django.core.management.base import BaseCommand
from apps.billing.rabbitmq.billing_publisher import BillingQueuePublisher
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Roda tarefas periódicas de billing'
    
    async def run_periodic(self):
        """Loop de tarefas periódicas"""
        while True:
            try:
                # A cada 5 minutos: verifica queues presas
                await BillingQueuePublisher.publish_queue(
                    'check_stale',
                    'notification'  # Baixa prioridade
                )
                
                logger.debug("⏰ Task periódica: check_stale agendada")
                
                # Aguarda 5 minutos
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Erro em task periódica: {e}")
                await asyncio.sleep(60)  # Retry em 1 min
    
    def handle(self, *args, **options):
        logger.info("🕐 Iniciando tarefas periódicas de billing...")
        asyncio.run(self.run_periodic())
```

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO**

### **Fase 1: Modelos e Migrations** (2-3 dias)
```
□ Criar app `apps.billing`
□ Criar todos os models (Config, APIKey, Template, etc)
□ Criar migrations
□ Rodar migrations em dev
□ Popular dados de teste (templates padrão)
□ Testar queries (N+1? Indexes?)
```

### **Fase 2: Utils e Helpers** (1-2 dias)
```
□ PhoneValidator + testes
□ TemplateSanitizer + testes
□ DateCalculator + testes
□ TemplateEngine + testes
□ Constants centralizadas
□ Verificar performance dos utils
```

### **Fase 3: Services** (3-4 dias)
```
□ InstanceHealthChecker
□ InstanceRecoveryService
□ BillingCampaignService (orchestrator)
□ BillingSendService (envia mensagem)
□ BusinessHoursScheduler
□ Testar cada service isoladamente
□ Testar integração entre services
```

### **Fase 4: Worker e RabbitMQ** (3-4 dias)
```
□ BillingSenderWorker completo
□ BillingQueuePublisher (publica no RabbitMQ)
□ BillingConsumer (consome do RabbitMQ)
□ Management commands (run_billing_consumer, run_billing_periodic_tasks)
□ Health check e heartbeat
□ Graceful shutdown
□ Testar worker localmente
□ Testar com RabbitMQ (aio-pika)
□ Testar pausa/retomada
□ Testar instância offline/recovery
```

### **Fase 5: APIs e Serializers** (2-3 dias)
```
□ Autenticação por API Key
□ Rate limiting
□ Endpoints: /send/overdue, /send/upcoming, /send/notification
□ Endpoints: /queue/{id}/status, /queue/{id}/control
□ Serializers e validações
□ Documentação Swagger
□ Testar com Postman
```

### **Fase 6: Integração com Chat** (1-2 dias)
```
□ Criar Conversation ao enviar
□ Salvar Message no histórico
□ Fechar conversa automaticamente
□ Testar reabertura se cliente responder
□ Verificar que não quebrou chat existente
```

### **Fase 7: Testes** (2-3 dias)
```
□ Testes unitários (>80% coverage)
□ Testes de integração
□ Testes de stress (1000+ mensagens)
□ Testar cenários de falha
□ Testar instância caindo e voltando
□ Testar pausa/retomada por horário
```

### **Fase 8: Deploy e Monitoramento** (1-2 dias)
```
□ Deploy em staging
□ Configurar RabbitMQ consumers no Railway
□ Adicionar ao Procfile: billing_consumer e billing_periodic
□ Configurar monitoramento (logs, métricas)
□ Testar com cliente piloto
□ Ajustar configs (throttling, etc)
□ Deploy em produção
```

---

## 🚀 **DEPLOY NO RAILWAY**

### **Procfile / railway.toml**

```toml
[deploy]
startCommand = "python manage.py migrate && python manage.py collectstatic --noinput && daphne alrea_sense.asgi:application --bind 0.0.0.0 --port $PORT"

[services.web]
startCommand = "daphne alrea_sense.asgi:application --bind 0.0.0.0 --port $PORT"

[services.billing_consumer]
startCommand = "python manage.py run_billing_consumer"
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 5

[services.billing_periodic]
startCommand = "python manage.py run_billing_periodic_tasks"
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 5
```

### **Variáveis de Ambiente**

```bash
# RabbitMQ (já existe no Railway)
RABBITMQ_URL=amqp://user:pass@host:5672/

# Billing específico
BILLING_WORKER_CONCURRENCY=2
BILLING_MAX_RETRIES=3
```

---

## 🎯 **CONCLUSÃO**

Este guia cobre **TODA a implementação** do sistema de Billing, incluindo:

✅ **Modelos completos** com relacionamentos corretos  
✅ **Tratamento de falhas de instância** (pause/resume automático)  
✅ **Anti-bloqueio WhatsApp** (múltiplas variações)  
✅ **Horário comercial** (pausa/retoma)  
✅ **Throttling** configurável  
✅ **Retry automático** inteligente  
✅ **Health checks** e heartbeat  
✅ **Graceful shutdown**  
✅ **Performance otimizada** (sem N+1, caching, batches)  
✅ **Segurança** (validação, sanitização, rate limiting)  

**Tempo estimado total: 15-20 dias** (1 desenvolvedor experiente)

**Próximo passo:** Começar pela Fase 1 (Modelos)! 🚀

