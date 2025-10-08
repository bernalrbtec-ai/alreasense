# 🚀 ALREA CAMPAIGNS - Especificação Técnica Completa

> **Projeto:** ALREA - Plataforma Multi-Produto SaaS  
> **Módulo:** Sistema de Campanhas de Disparo WhatsApp  
> **Versão:** 2.0.0  
> **Data:** 2025-10-08  
> **Autor:** ALREA Development Team  
> **Confidencial:** Não mencionar infraestrutura específica externamente

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Modelagem de Dados](#modelagem-de-dados)
4. [API REST Endpoints](#api-rest-endpoints)
5. [Celery Tasks](#celery-tasks)
6. [Frontend Components](#frontend-components)
7. [Fluxos de Negócio](#fluxos-de-negócio)
8. [Sistema de Métricas](#sistema-de-métricas)
9. [Segurança e Performance](#segurança-e-performance)
10. [Deploy e Infraestrutura](#deploy-e-infraestrutura)

---

## 🎯 VISÃO GERAL

### Objetivo do Sistema

O módulo **ALREA Campaigns** permite aos clientes criar e gerenciar campanhas de disparo em massa via WhatsApp, com:

- ✅ Múltiplas instâncias WhatsApp simultâneas
- ✅ Rotação inteligente de mensagens (até 5 por campanha)
- ✅ Controle granular de horários e períodos
- ✅ Delays randomizados entre envios
- ✅ Pausar/Retomar/Encerrar em tempo real
- ✅ Logs completos e métricas detalhadas
- ✅ Preview de mensagens com variáveis
- ✅ Multi-tenant com isolamento total

### Premissas de Negócio

1. **1 instância = 1 campanha ativa por vez**
2. **Campanhas são criadas como RASCUNHO** (draft)
3. **Usuário escolhe quando iniciar** após criação
4. **Cada instância tem configurações próprias** (horários, delays)
5. **Sistema respeita rigorosamente** pausas, horários e feriados
6. **Logs auditáveis** de todas as ações

---

## 🏗️ ARQUITETURA DO SISTEMA

### Stack Tecnológico

```yaml
Backend:
  - Framework: Django 5.0+
  - API: Django REST Framework 3.14+
  - Tasks: Celery 5.3+ com Redis/RabbitMQ
  - Database: PostgreSQL 15+
  - Cache: Redis 7+
  - WebSocket: Django Channels 4+

Frontend:
  - Framework: React 18+
  - Language: TypeScript 5+
  - Build: Vite 5+
  - Styling: Tailwind CSS 3+
  - Components: shadcn/ui
  - State: Zustand
  - Forms: React Hook Form + Zod

Integrations:
  - WhatsApp: Gateway API Externo
  - Billing: Gateway de Pagamento
  - Auth: JWT
```

### Diagrama de Arquitetura

```
┌────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Dashboard │  │Campaigns │  │ Contacts │  │ Metrics  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└───────┼─────────────┼─────────────┼─────────────┼─────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │ HTTP/REST
        ┌─────────────▼─────────────────────────────────────┐
        │           DJANGO REST API                         │
        │  ┌─────────────────────────────────────────────┐ │
        │  │ ViewSets (Campaigns, Contacts, Instances)   │ │
        │  │ - Permissions (Multi-tenant)                │ │
        │  │ - Serializers (Validation)                  │ │
        │  │ - Services (Business Logic)                 │ │
        │  └─────────────────────────────────────────────┘ │
        └────────┬──────────────────────────┬───────────────┘
                 │                          │
                 ▼                          ▼
        ┌────────────────┐        ┌────────────────────────┐
        │   PostgreSQL   │        │  CELERY + Redis/RMQ    │
        │                │        │                        │
        │ - Campaigns    │        │ ┌──────────────────┐  │
        │ - Contacts     │        │ │ Scheduler Task   │  │
        │ - Messages     │◄───────┤ │ (cada 10s)       │  │
        │ - Logs         │        │ └──────────────────┘  │
        │ - Metrics      │        │                        │
        │                │        │ ┌──────────────────┐  │
        │                │◄───────┤ │ Dispatcher Tasks │  │
        │                │        │ │ (workers/inst.)  │  │
        │                │        │ └──────────────────┘  │
        └────────────────┘        │                        │
                                  │ ┌──────────────────┐  │
                                  │ │ Metrics Task     │  │
                                  │ │ (cada 1h)        │  │
                                  │ └──────────────────┘  │
                                  └────────┬───────────────┘
                                           │
                                           ▼
                                  ┌────────────────────────┐
                                  │   WhatsApp Gateway     │
                                  │   (API Externa)        │
                                  │                        │
                                  │ - Send Messages        │
                                  │ - WebSocket Events     │
                                  │ - Instance Status      │
                                  └────────────────────────┘
```

### Fluxo de Dados - Envio de Mensagem

```
1. Scheduler (Celery Beat - cada 10s)
   ↓
2. Busca campanhas ativas (status='active', is_paused=False)
   ↓
3. Para cada campanha:
   ├─ Verifica horário permitido
   ├─ Verifica instância conectada
   ├─ Pega próximo contato (status='pending')
   ├─ Seleciona mensagem (rotação)
   ├─ Renderiza variáveis
   └─ Enfileira task de envio
   ↓
4. Dispatcher Task (Celery Worker)
   ├─ Valida estado da campanha (dupla checagem)
   ├─ Envia via WhatsApp Gateway API
   ├─ Atualiza status do contato (sent/failed)
   ├─ Incrementa contadores
   └─ Cria log detalhado
   ↓
5. WhatsApp Gateway WebSocket
   ├─ Recebe eventos (delivered, read, responded)
   ├─ Atualiza status em tempo real
   └─ Alimenta métricas
```

---

## 📊 MODELAGEM DE DADOS

### Diagrama ER

```
┌────────────────┐
│    Tenant      │
└───────┬────────┘
        │ 1
        │
        │ N
┌───────▼────────┐         ┌─────────────────┐
│   Campaign     │ 1    N  │ CampaignMessage │
│                │◄────────┤                 │
│ - id (UUID)    │         │ - message_text  │
│ - name         │         │ - order (1-5)   │
│ - status       │         │ - times_sent    │
│ - is_paused    │         │ - response_rate │
│ - instance ───►│         └─────────────────┘
│   (FK)         │
│ - total_       │         ┌─────────────────┐
│   contacts     │ 1    N  │ CampaignContact │
│ - sent_        │◄────────┤                 │
│   messages     │         │ - campaign (FK) │
│                │         │ - contact (FK)  │
│                │         │ - status        │
│                │         │ - sent_at       │
└────────────────┘         │ - responded_at  │
        │                  └─────────────────┘
        │
        │ 1                ┌─────────────────┐
        ├──────────────────┤  CampaignLog    │
        │               N  │                 │
        │                  │ - level         │
        │                  │ - event_type    │
        │                  │ - message       │
        │                  │ - metadata      │
        │                  └─────────────────┘
        │
        │ 1                ┌─────────────────┐
        └──────────────────┤ CampaignMetrics │
                        N  │                 │
                           │ - metric_date   │
                           │ - hour_of_day   │
                           │ - messages_sent │
                           │ - response_rate │
                           └─────────────────┘

┌────────────────┐
│   Contact      │
│                │
│ - name         │
│ - phone        │
│ - tags         │
│ - quem_indicou │
│ - custom_vars  │
└────────────────┘

┌────────────────────┐
│ WhatsAppInstance   │
│                    │
│ - name             │
│ - is_connected     │
│ - morning_start    │
│ - morning_end      │
│ - afternoon_start  │
│ - afternoon_end    │
│ - delay_min_sec    │
│ - delay_max_sec    │
└────────────────────┘

┌────────────────┐
│    Holiday     │
│                │
│ - date         │
│ - name         │
│ - is_national  │
└────────────────┘
```

### Models Detalhados

#### 1. Campaign

```python
# apps/campaigns/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

class Campaign(models.Model):
    """
    Campanha de disparo em massa
    
    Regras:
    - Sempre criada como DRAFT
    - Precisa de pelo menos 1 mensagem e 1 contato para iniciar
    - Só pode ter 1 campanha ACTIVE por instância
    - Pode ser pausada/retomada/cancelada a qualquer momento
    """
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativa'
        PAUSED = 'paused', 'Pausada'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'
    
    class ScheduleType(models.TextChoices):
        IMMEDIATE = 'immediate', 'Imediato'
        BUSINESS_DAYS = 'business_days', 'Apenas Dias Úteis'
        BUSINESS_HOURS = 'business_hours', 'Horário Comercial'
        CUSTOM_PERIOD = 'custom_period', 'Período Personalizado'
    
    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='campaigns'
    )
    name = models.CharField(
        max_length=200,
        help_text="Nome descritivo da campanha"
    )
    description = models.TextField(
        blank=True,
        help_text="Descrição opcional da campanha"
    )
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    is_paused = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag de pausa. Valida antes de CADA envio."
    )
    
    # Relacionamentos
    instance = models.ForeignKey(
        'connections.WhatsAppInstance',
        on_delete=models.PROTECT,
        related_name='campaigns',
        help_text="Instância WhatsApp que executará a campanha"
    )
    
    # Configurações de agendamento
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.IMMEDIATE
    )
    
    # Usado apenas se schedule_type = CUSTOM_PERIOD
    morning_start = models.TimeField(null=True, blank=True, default='09:00')
    morning_end = models.TimeField(null=True, blank=True, default='12:00')
    afternoon_start = models.TimeField(null=True, blank=True, default='14:00')
    afternoon_end = models.TimeField(null=True, blank=True, default='17:00')
    skip_weekends = models.BooleanField(default=True)
    skip_holidays = models.BooleanField(default=True)
    
    # Contadores
    total_contacts = models.IntegerField(
        default=0,
        help_text="Total de contatos na campanha"
    )
    current_contact_index = models.IntegerField(
        default=0,
        help_text="Índice do próximo contato a processar"
    )
    sent_messages = models.IntegerField(
        default=0,
        help_text="Quantidade de mensagens enviadas com sucesso"
    )
    failed_messages = models.IntegerField(
        default=0,
        help_text="Quantidade de mensagens que falharam"
    )
    responded_count = models.IntegerField(
        default=0,
        help_text="Quantidade de contatos que responderam"
    )
    
    # Controle de processamento
    next_scheduled_send = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp do próximo envio agendado"
    )
    last_send_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp do último envio realizado"
    )
    last_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que o scheduler processou esta campanha"
    )
    is_processing = models.BooleanField(
        default=False,
        help_text="Lock para evitar processamento duplicado"
    )
    
    # Timestamps de lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    resumed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Auditoria
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='campaigns_created'
    )
    started_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns_started'
    )
    
    # Tracking de erros
    last_error = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    auto_pause_reason = models.TextField(
        blank=True,
        help_text="Motivo de pausa automática (ex: instância desconectada)"
    )
    
    class Meta:
        db_table = 'campaigns_campaign'
        verbose_name = 'Campanha'
        verbose_name_plural = 'Campanhas'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['tenant', 'status', 'created_at']),
            models.Index(fields=['status', 'is_paused', 'next_scheduled_send']),
            models.Index(fields=['instance', 'status']),
        ]
        
        constraints = [
            # Só 1 campanha ativa por instância
            models.UniqueConstraint(
                fields=['instance'],
                condition=models.Q(status=Status.ACTIVE),
                name='unique_active_campaign_per_instance'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) - {self.tenant.name}"
    
    # Properties
    
    @property
    def progress_percentage(self):
        """Percentual de progresso (0-100)"""
        if self.total_contacts == 0:
            return 0
        return round((self.sent_messages / self.total_contacts) * 100, 1)
    
    @property
    def response_rate(self):
        """Taxa de resposta (%)"""
        if self.sent_messages == 0:
            return 0
        return round((self.responded_count / self.sent_messages) * 100, 1)
    
    @property
    def can_be_started(self):
        """Verifica se campanha pode ser iniciada"""
        return (
            self.status == self.Status.DRAFT and
            self.total_contacts > 0 and
            self.messages.filter(is_active=True).exists() and
            self.instance.is_connected
        )
    
    @property
    def can_be_paused(self):
        """Verifica se campanha pode ser pausada"""
        return self.status == self.Status.ACTIVE and not self.is_paused
    
    @property
    def can_be_resumed(self):
        """Verifica se campanha pode ser retomada"""
        return self.status == self.Status.ACTIVE and self.is_paused
    
    @property
    def can_be_cancelled(self):
        """Verifica se campanha pode ser cancelada"""
        return self.status in [self.Status.DRAFT, self.Status.ACTIVE, self.Status.PAUSED]
    
    @property
    def remaining_contacts(self):
        """Quantidade de contatos restantes"""
        return self.total_contacts - self.sent_messages
    
    # Methods
    
    def start(self, user):
        """
        Inicia a campanha
        
        Raises:
            ValidationError: Se campanha não pode ser iniciada
        """
        from django.core.exceptions import ValidationError
        
        if not self.can_be_started:
            raise ValidationError("Campanha não pode ser iniciada no estado atual")
        
        self.status = self.Status.ACTIVE
        self.is_paused = False
        self.started_at = timezone.now()
        self.started_by = user
        self.next_scheduled_send = timezone.now() + timezone.timedelta(seconds=10)
        self.save(update_fields=[
            'status', 'is_paused', 'started_at', 'started_by', 'next_scheduled_send'
        ])
        
        # Log
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.INFO,
            event_type='campaign_started',
            message=f'Campanha iniciada por {user.email}',
            metadata={'total_contacts': self.total_contacts}
        )
    
    def pause(self, user, reason=''):
        """Pausa a campanha"""
        from django.core.exceptions import ValidationError
        
        if not self.can_be_paused:
            raise ValidationError("Campanha não pode ser pausada")
        
        self.is_paused = True
        self.paused_at = timezone.now()
        self.save(update_fields=['is_paused', 'paused_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.WARNING,
            event_type='campaign_paused',
            message=f'Campanha pausada por {user.email}',
            metadata={'reason': reason}
        )
    
    def resume(self, user):
        """Retoma a campanha"""
        from django.core.exceptions import ValidationError
        
        if not self.can_be_resumed:
            raise ValidationError("Campanha não pode ser retomada")
        
        self.is_paused = False
        self.resumed_at = timezone.now()
        self.next_scheduled_send = timezone.now() + timezone.timedelta(seconds=10)
        self.auto_pause_reason = ''
        self.save(update_fields=[
            'is_paused', 'resumed_at', 'next_scheduled_send', 'auto_pause_reason'
        ])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.INFO,
            event_type='campaign_resumed',
            message=f'Campanha retomada por {user.email}'
        )
    
    def cancel(self, user, reason=''):
        """Cancela a campanha"""
        from django.core.exceptions import ValidationError
        
        if not self.can_be_cancelled:
            raise ValidationError("Campanha não pode ser cancelada")
        
        self.status = self.Status.CANCELLED
        self.is_paused = True
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'is_paused', 'cancelled_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.ERROR,
            event_type='campaign_cancelled',
            message=f'Campanha cancelada por {user.email}',
            metadata={'reason': reason, 'sent_messages': self.sent_messages}
        )
    
    def complete(self):
        """Marca campanha como concluída"""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            level=CampaignLog.Level.SUCCESS,
            event_type='campaign_completed',
            message='Campanha concluída com sucesso',
            metadata={
                'total_contacts': self.total_contacts,
                'sent_messages': self.sent_messages,
                'failed_messages': self.failed_messages,
                'response_rate': self.response_rate
            }
        )
```

#### 2. CampaignMessage

```python
class CampaignMessage(models.Model):
    """
    Mensagem de uma campanha (até 5 por campanha)
    
    Sistema rotaciona entre as mensagens cadastradas.
    Permite medir qual mensagem performa melhor.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    message_text = models.TextField(
        help_text="Texto da mensagem. Use variáveis: {{nome}}, {{quem_indicou}}, {{saudacao}}"
    )
    order = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Ordem da mensagem (1-5)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Se False, não será enviada"
    )
    
    # Métricas
    times_sent = models.IntegerField(
        default=0,
        help_text="Quantas vezes esta mensagem foi enviada"
    )
    response_count = models.IntegerField(
        default=0,
        help_text="Quantas respostas esta mensagem gerou"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_message'
        verbose_name = 'Mensagem de Campanha'
        verbose_name_plural = 'Mensagens de Campanha'
        ordering = ['campaign', 'order']
        
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'order'],
                name='unique_message_order_per_campaign'
            )
        ]
    
    def __str__(self):
        return f"Mensagem {self.order} - {self.campaign.name}"
    
    @property
    def response_rate(self):
        """Taxa de resposta desta mensagem"""
        if self.times_sent == 0:
            return 0
        return round((self.response_count / self.times_sent) * 100, 1)
    
    def render_variables(self, contact, current_datetime=None):
        """
        Renderiza variáveis da mensagem
        
        Variáveis disponíveis:
        - {{nome}}: Nome do contato
        - {{quem_indicou}}: Quem indicou o contato
        - {{saudacao}}: Saudação baseada na hora (Bom dia/Boa tarde/Boa noite)
        - {{dia_semana}}: Dia da semana por extenso
        - Variáveis customizadas do contato
        """
        if current_datetime is None:
            current_datetime = timezone.now()
        
        # Saudação baseada na hora
        hour = current_datetime.hour
        if hour < 12:
            saudacao = "Bom dia"
        elif hour < 18:
            saudacao = "Boa tarde"
        else:
            saudacao = "Boa noite"
        
        # Dia da semana
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 
                'Sexta-feira', 'Sábado', 'Domingo']
        dia_semana = dias[current_datetime.weekday()]
        
        # Renderizar
        rendered = self.message_text
        rendered = rendered.replace('{{nome}}', contact.name or '')
        rendered = rendered.replace('{{quem_indicou}}', contact.quem_indicou or '')
        rendered = rendered.replace('{{saudacao}}', saudacao)
        rendered = rendered.replace('{{dia_semana}}', dia_semana)
        
        # Variáveis customizadas (JSONB)
        if contact.custom_vars:
            for key, value in contact.custom_vars.items():
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        
        return rendered
```

#### 3. CampaignContact

```python
class CampaignContact(models.Model):
    """
    Relacionamento N:N entre Campaign e Contact
    Controla status de envio individual
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        SENT = 'sent', 'Enviada'
        DELIVERED = 'delivered', 'Entregue'
        READ = 'read', 'Lida'
        RESPONDED = 'responded', 'Respondeu'
        FAILED = 'failed', 'Falhou'
        SKIPPED = 'skipped', 'Pulado'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='campaign_contacts'
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.CASCADE,
        related_name='campaigns_participated'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    
    # Qual mensagem foi enviada
    message_sent = models.ForeignKey(
        CampaignMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_to_contacts'
    )
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking Evolution API
    evolution_message_id = models.CharField(max_length=255, blank=True)
    
    # Erros
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_contact'
        verbose_name = 'Contato da Campanha'
        verbose_name_plural = 'Contatos da Campanha'
        
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['contact', 'campaign']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'contact'],
                name='unique_contact_per_campaign'
            )
        ]
    
    def __str__(self):
        return f"{self.contact.name} - {self.campaign.name} ({self.get_status_display()})"
    
    @property
    def response_time_minutes(self):
        """Tempo de resposta em minutos"""
        if not self.sent_at or not self.responded_at:
            return None
        delta = self.responded_at - self.sent_at
        return round(delta.total_seconds() / 60, 1)
```

#### 4. CampaignLog

```python
class CampaignLog(models.Model):
    """
    Log detalhado de eventos da campanha
    Para auditoria e debugging
    """
    
    class Level(models.TextChoices):
        DEBUG = 'debug', 'Debug'
        INFO = 'info', 'Info'
        SUCCESS = 'success', 'Sucesso'
        WARNING = 'warning', 'Aviso'
        ERROR = 'error', 'Erro'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_logs'
    )
    user = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.INFO,
        db_index=True
    )
    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Tipo do evento: campaign_started, message_sent, etc."
    )
    message = models.TextField()
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dados adicionais do evento"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'campaigns_log'
        verbose_name = 'Log de Campanha'
        verbose_name_plural = 'Logs de Campanha'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['campaign', '-created_at']),
            models.Index(fields=['level', '-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.level.upper()}] {self.campaign.name} - {self.message[:50]}"
```

#### 5. CampaignMetrics

```python
class CampaignMetrics(models.Model):
    """
    Métricas agregadas por campanha e hora do dia
    Permite análise de melhor horário de disparo
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    metric_date = models.DateField(db_index=True)
    hour_of_day = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)]
    )
    
    # Métricas
    messages_sent = models.IntegerField(default=0)
    messages_delivered = models.IntegerField(default=0)
    messages_read = models.IntegerField(default=0)
    messages_responded = models.IntegerField(default=0)
    messages_failed = models.IntegerField(default=0)
    
    avg_response_time_minutes = models.FloatField(
        null=True,
        blank=True,
        help_text="Tempo médio de resposta em minutos"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_metrics'
        verbose_name = 'Métrica de Campanha'
        verbose_name_plural = 'Métricas de Campanha'
        
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'metric_date', 'hour_of_day'],
                name='unique_metrics_per_campaign_date_hour'
            )
        ]
        
        indexes = [
            models.Index(fields=['campaign', 'metric_date', 'hour_of_day']),
        ]
    
    @property
    def response_rate(self):
        """Taxa de resposta nesta hora"""
        if self.messages_sent == 0:
            return 0
        return round((self.messages_responded / self.messages_sent) * 100, 1)
```

#### 6. Holiday

```python
class Holiday(models.Model):
    """
    Feriados nacionais/estaduais/municipais
    Sistema pula envios em feriados se configurado
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='holidays',
        null=True,
        blank=True,
        help_text="Se null, é feriado nacional válido para todos"
    )
    
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=200)
    is_national = models.BooleanField(
        default=False,
        help_text="Feriado nacional (vale para todos os tenants)"
    )
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'campaigns_holiday'
        verbose_name = 'Feriado'
        verbose_name_plural = 'Feriados'
        ordering = ['date']
        
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'tenant'],
                name='unique_holiday_per_date_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.date})"
    
    @classmethod
    def is_holiday(cls, date, tenant=None):
        """Verifica se uma data é feriado"""
        query = models.Q(date=date, is_active=True)
        
        if tenant:
            query &= (models.Q(tenant=tenant) | models.Q(is_national=True, tenant__isnull=True))
        else:
            query &= models.Q(is_national=True, tenant__isnull=True)
        
        return cls.objects.filter(query).exists()
```

---

## 🔌 API REST ENDPOINTS

### Base URL
```
/api/v1/campaigns/
```

### Endpoints Principais

#### 1. **Campanhas**

```yaml
GET /api/v1/campaigns/
  Descrição: Lista campanhas do tenant
  Query Params:
    - status: filter by status (draft, active, paused, completed, cancelled)
    - instance_id: filter by instance
    - search: busca por nome
    - ordering: -created_at, name, status
    - page: pagination
    - page_size: default 20
  Response: PaginatedResponse<Campaign[]>

GET /api/v1/campaigns/{id}/
  Descrição: Detalhes de uma campanha
  Response: Campaign (com nested messages, stats)

POST /api/v1/campaigns/
  Descrição: Cria nova campanha (status=draft)
  Body:
    {
      "name": "string",
      "description": "string?",
      "instance_id": "uuid",
      "schedule_type": "immediate|business_days|business_hours|custom_period",
      "morning_start": "09:00",  // se custom_period
      "morning_end": "12:00",
      "afternoon_start": "14:00",
      "afternoon_end": "17:00",
      "skip_weekends": boolean,
      "skip_holidays": boolean,
      "contact_ids": ["uuid"],  // OU contact_tag
      "contact_tag": "string?",
      "messages": [
        {
          "message_text": "string",
          "order": 1
        }
      ]
    }
  Response: 201 Created (Campaign)

PATCH /api/v1/campaigns/{id}/
  Descrição: Atualiza campanha (apenas se status=draft)
  Body: Partial<Campaign>
  Response: 200 OK (Campaign)

DELETE /api/v1/campaigns/{id}/
  Descrição: Deleta campanha (apenas se status=draft)
  Response: 204 No Content

POST /api/v1/campaigns/{id}/start/
  Descrição: Inicia campanha
  Validações:
    - status == draft
    - has messages
    - has contacts
    - instance is connected
    - instance has no other active campaign
  Response: 200 OK (Campaign)

POST /api/v1/campaigns/{id}/pause/
  Descrição: Pausa campanha
  Body: { "reason": "string?" }
  Response: 200 OK (Campaign)

POST /api/v1/campaigns/{id}/resume/
  Descrição: Retoma campanha pausada
  Response: 200 OK (Campaign)

POST /api/v1/campaigns/{id}/cancel/
  Descrição: Cancela campanha
  Body: { "reason": "string?" }
  Response: 200 OK (Campaign)

GET /api/v1/campaigns/{id}/logs/
  Descrição: Logs da campanha
  Query Params:
    - level: debug|info|success|warning|error
    - page, page_size
  Response: PaginatedResponse<CampaignLog[]>

GET /api/v1/campaigns/{id}/metrics/
  Descrição: Métricas agregadas da campanha
  Response:
    {
      "best_message": {
        "message_id": "uuid",
        "message_text": "string",
        "response_rate": 45.2
      },
      "best_hour": {
        "hour": 14,
        "response_rate": 38.5
      },
      "hourly_breakdown": [
        { "hour": 9, "sent": 120, "responded": 35, "rate": 29.2 },
        ...
      ],
      "daily_breakdown": [
        { "date": "2025-10-08", "sent": 450, "responded": 120, "rate": 26.7 },
        ...
      ]
    }

GET /api/v1/campaigns/{id}/contacts/
  Descrição: Lista contatos da campanha com status
  Query Params:
    - status: pending|sent|delivered|read|responded|failed
  Response: PaginatedResponse<CampaignContact[]>
```

#### 2. **Mensagens**

```yaml
GET /api/v1/campaigns/{campaign_id}/messages/
  Descrição: Lista mensagens da campanha
  Response: CampaignMessage[]

POST /api/v1/campaigns/{campaign_id}/messages/
  Descrição: Adiciona mensagem à campanha
  Body:
    {
      "message_text": "string",
      "order": 1-5
    }
  Response: 201 Created (CampaignMessage)

PATCH /api/v1/campaigns/{campaign_id}/messages/{id}/
  Descrição: Atualiza mensagem
  Response: 200 OK (CampaignMessage)

DELETE /api/v1/campaigns/{campaign_id}/messages/{id}/
  Descrição: Remove mensagem
  Response: 204 No Content

POST /api/v1/campaigns/{campaign_id}/messages/{id}/preview/
  Descrição: Preview da mensagem renderizada
  Body:
    {
      "contact_id": "uuid",  // opcional, usa sample se não informado
      "datetime": "2025-10-08T14:30:00Z"  // opcional
    }
  Response:
    {
      "original": "{{saudacao}}, {{nome}}!",
      "rendered": "Boa tarde, João Silva!",
      "variables_used": ["saudacao", "nome"]
    }
```

#### 3. **Instâncias**

```yaml
GET /api/v1/instances/
  Descrição: Lista instâncias do tenant
  Response: WhatsAppInstance[]

GET /api/v1/instances/{id}/availability/
  Descrição: Verifica disponibilidade da instância
  Response:
    {
      "is_connected": true,
      "has_active_campaign": false,
      "available": true,
      "current_campaign": null | {
        "id": "uuid",
        "name": "string",
        "progress": 45.2
      }
    }
```

---

## ⚙️ CELERY TASKS

### Configuração

```python
# settings.py

CELERY_BROKER_URL = env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', 'redis://localhost:6379/0')

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'America/Sao_Paulo'

# Filas por instância
CELERY_TASK_ROUTES = {
    'campaigns.tasks.send_message_task': {
        'queue': 'default',  # Ou dinâmico baseado em instance_id
    },
}

# Beat schedule
CELERY_BEAT_SCHEDULE = {
    'campaign-scheduler': {
        'task': 'campaigns.tasks.campaign_scheduler',
        'schedule': 10.0,  # A cada 10 segundos
    },
    'aggregate-metrics': {
        'task': 'campaigns.tasks.aggregate_metrics_task',
        'schedule': crontab(minute='*/60'),  # A cada hora
    },
}
```

### Tasks

#### 1. **Scheduler Task**

```python
# campaigns/tasks.py

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db.models import F
import random

logger = get_task_logger(__name__)

@shared_task
def campaign_scheduler():
    """
    Task principal que agenda envios de mensagens
    Roda a cada 10 segundos (Celery Beat)
    
    Fluxo:
    1. Busca campanhas ativas e prontas
    2. Para cada campanha:
       - Valida horário
       - Valida estado
       - Pega próximo contato
       - Seleciona mensagem
       - Enfileira task de envio
       - Calcula próximo agendamento
    """
    from apps.campaigns.models import Campaign, CampaignContact
    from apps.campaigns.services import CampaignSchedulerService
    
    now = timezone.now()
    
    # Buscar campanhas prontas para processar
    ready_campaigns = Campaign.objects.filter(
        status=Campaign.Status.ACTIVE,
        is_paused=False,
        next_scheduled_send__lte=now
    ).select_related('instance', 'tenant')
    
    logger.info(f"📊 Scheduler: {ready_campaigns.count()} campanhas prontas")
    
    scheduler_service = CampaignSchedulerService()
    
    for campaign in ready_campaigns:
        try:
            # Heartbeat
            Campaign.objects.filter(id=campaign.id).update(
                last_heartbeat=now
            )
            
            # Processar campanha
            result = scheduler_service.process_campaign(campaign, now)
            
            if result['status'] == 'sent':
                logger.info(
                    f"📤 Enfileirado: {campaign.name} → {result['contact_name']}",
                    extra={'campaign_id': str(campaign.id)}
                )
            elif result['status'] == 'completed':
                logger.info(
                    f"✅ Campanha {campaign.name} concluída!",
                    extra={'campaign_id': str(campaign.id)}
                )
            elif result['status'] == 'skipped':
                logger.debug(
                    f"⏭ Campanha {campaign.name} pulada: {result['reason']}",
                    extra={'campaign_id': str(campaign.id), 'reason': result['reason']}
                )
                
        except Exception as e:
            logger.exception(
                f"❌ Erro ao processar campanha {campaign.id}: {str(e)}",
                extra={'campaign_id': str(campaign.id), 'error': str(e)}
            )
            
            # Auto-pause em caso de erro crítico
            Campaign.objects.filter(id=campaign.id).update(
                is_paused=True,
                auto_pause_reason=f"Erro no scheduler: {str(e)}"
            )
    
    return {
        'processed': ready_campaigns.count(),
        'timestamp': now.isoformat()
    }
```

#### 2. **Dispatcher Task**

```python
@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=90,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def send_message_task(self, campaign_id, contact_relation_id, message_id, rendered_message):
    """
    Envia uma mensagem via Evolution API
    
    Args:
        campaign_id: UUID da campanha
        contact_relation_id: UUID do CampaignContact
        message_id: UUID da CampaignMessage
        rendered_message: Mensagem já renderizada com variáveis
    
    Returns:
        dict com status do envio
    """
    from apps.campaigns.models import Campaign, CampaignContact, CampaignMessage, CampaignLog
    from apps.campaigns.services import EvolutionAPIService
    
    try:
        # Buscar objetos
        campaign = Campaign.objects.select_related('instance', 'tenant').get(id=campaign_id)
        contact_relation = CampaignContact.objects.select_related('contact').get(id=contact_relation_id)
        message = CampaignMessage.objects.get(id=message_id)
        contact = contact_relation.contact
        
        # ⭐ VALIDAÇÃO CRÍTICA antes de enviar
        if campaign.is_paused:
            logger.warning(
                f"🛑 Campanha {campaign.name} pausada, abortando envio",
                extra={'campaign_id': str(campaign_id)}
            )
            return {'status': 'aborted', 'reason': 'paused'}
        
        if campaign.status != Campaign.Status.ACTIVE:
            logger.warning(
                f"🛑 Campanha {campaign.name} não ativa (status={campaign.status})",
                extra={'campaign_id': str(campaign_id)}
            )
            return {'status': 'aborted', 'reason': 'not_active'}
        
        if not campaign.instance.is_connected:
            logger.error(
                f"🛑 Instância {campaign.instance.name} desconectada",
                extra={'campaign_id': str(campaign_id)}
            )
            
            # Auto-pause
            Campaign.objects.filter(id=campaign_id).update(
                is_paused=True,
                auto_pause_reason="Instância desconectada"
            )
            return {'status': 'aborted', 'reason': 'instance_disconnected'}
        
        # Enviar via WhatsApp Gateway
        logger.info(
            f"📱 Enviando para {contact.name} ({contact.phone}) via {campaign.instance.name}",
            extra={'campaign_id': str(campaign_id), 'contact_id': str(contact.id)}
        )
        
        gateway_service = WhatsAppGatewayService()
        response = gateway_service.send_text_message(
            instance=campaign.instance,
            phone=contact.phone,
            message=rendered_message
        )
        
        # Atualizar status
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status=CampaignContact.Status.SENT,
            sent_at=timezone.now(),
            evolution_message_id=response.get('message_id'),
            message_sent=message
        )
        
        # Incrementar contadores (atomic)
        Campaign.objects.filter(id=campaign_id).update(
            sent_messages=F('sent_messages') + 1,
            last_send_at=timezone.now()
        )
        
        CampaignMessage.objects.filter(id=message_id).update(
            times_sent=F('times_sent') + 1
        )
        
        # Log de sucesso
        CampaignLog.objects.create(
            campaign=campaign,
            contact=contact,
            level=CampaignLog.Level.SUCCESS,
            event_type='message_sent',
            message=f'Mensagem enviada para {contact.name}',
            metadata={
                'evolution_response': response,
                'message_length': len(rendered_message),
                'instance': campaign.instance.name
            }
        )
        
        logger.info(
            f"✅ Enviado com sucesso: {contact.name}",
            extra={'campaign_id': str(campaign_id), 'message_id': response.get('message_id')}
        )
        
        return {'status': 'success', 'message_id': response.get('message_id')}
        
    except Campaign.DoesNotExist:
        logger.error(f"❌ Campanha {campaign_id} não encontrada")
        return {'status': 'error', 'reason': 'campaign_not_found'}
    
    except Exception as e:
        logger.exception(
            f"❌ Erro ao enviar mensagem: {str(e)}",
            extra={'campaign_id': str(campaign_id), 'error': str(e)}
        )
        
        # Marcar como falha
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status=CampaignContact.Status.FAILED,
            error_message=str(e),
            retry_count=F('retry_count') + 1
        )
        
        Campaign.objects.filter(id=campaign_id).update(
            failed_messages=F('failed_messages') + 1,
            last_error=str(e),
            last_error_at=timezone.now()
        )
        
        CampaignLog.objects.create(
            campaign_id=campaign_id,
            contact_id=contact_relation.contact_id if 'contact_relation' in locals() else None,
            level=CampaignLog.Level.ERROR,
            event_type='message_failed',
            message=f'Falha ao enviar: {str(e)}',
            metadata={'error': str(e), 'retry_attempt': self.request.retries}
        )
        
        # Retry se for erro temporário
        if isinstance(e, (ConnectionError, TimeoutError)) and self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
        
        return {'status': 'error', 'reason': str(e)}
```

#### 3. **Metrics Aggregation Task**

```python
@shared_task
def aggregate_metrics_task():
    """
    Agrega métricas de campanhas ativas
    Roda a cada hora
    
    Calcula:
    - Mensagens enviadas/respondidas por hora
    - Taxa de resposta por hora
    - Tempo médio de resposta
    """
    from apps.campaigns.models import Campaign, CampaignMetrics, CampaignContact
    from django.db.models import Count, Avg, Q
    
    now = timezone.now()
    today = now.date()
    current_hour = now.hour
    
    # Campanhas ativas
    active_campaigns = Campaign.objects.filter(
        status__in=[Campaign.Status.ACTIVE, Campaign.Status.PAUSED]
    )
    
    for campaign in active_campaigns:
        # Buscar mensagens enviadas nesta hora
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timezone.timedelta(hours=1)
        
        stats = CampaignContact.objects.filter(
            campaign=campaign,
            sent_at__gte=hour_start,
            sent_at__lt=hour_end
        ).aggregate(
            total_sent=Count('id'),
            total_delivered=Count('id', filter=Q(status__in=['delivered', 'read', 'responded'])),
            total_read=Count('id', filter=Q(status__in=['read', 'responded'])),
            total_responded=Count('id', filter=Q(status='responded')),
            total_failed=Count('id', filter=Q(status='failed')),
            avg_response_time=Avg(
                F('responded_at') - F('sent_at'),
                filter=Q(responded_at__isnull=False)
            )
        )
        
        # Converter timedelta para minutos
        avg_response_minutes = None
        if stats['avg_response_time']:
            avg_response_minutes = stats['avg_response_time'].total_seconds() / 60
        
        # Criar ou atualizar métrica
        CampaignMetrics.objects.update_or_create(
            campaign=campaign,
            metric_date=today,
            hour_of_day=current_hour,
            defaults={
                'messages_sent': stats['total_sent'],
                'messages_delivered': stats['total_delivered'],
                'messages_read': stats['total_read'],
                'messages_responded': stats['total_responded'],
                'messages_failed': stats['total_failed'],
                'avg_response_time_minutes': avg_response_minutes
            }
        )
        
        logger.info(
            f"📊 Métricas agregadas: {campaign.name} ({today} {current_hour}h)",
            extra={'campaign_id': str(campaign.id), 'metrics': stats}
        )
    
    return {
        'campaigns_processed': active_campaigns.count(),
        'date': today.isoformat(),
        'hour': current_hour
    }
```

---

## 🎨 FRONTEND COMPONENTS

### Estrutura de Pastas

```
frontend/src/
├── pages/
│   ├── campaigns/
│   │   ├── CampaignsListPage.tsx
│   │   ├── CampaignCreatePage.tsx
│   │   ├── CampaignEditPage.tsx
│   │   └── CampaignDetailsPage.tsx
│   └── ...
│
├── components/
│   ├── campaigns/
│   │   ├── CampaignCard.tsx
│   │   ├── CampaignForm.tsx
│   │   ├── MessageEditor.tsx
│   │   ├── MessagePreview.tsx
│   │   ├── ContactSelector.tsx
│   │   ├── ScheduleConfig.tsx
│   │   ├── CampaignStats.tsx
│   │   ├── CampaignLogs.tsx
│   │   └── CampaignMetrics.tsx
│   └── ui/
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Input.tsx
│       ├── Select.tsx
│       ├── ProgressBar.tsx
│       ├── Badge.tsx
│       └── ...
│
├── services/
│   ├── api/
│   │   ├── campaigns.ts
│   │   ├── messages.ts
│   │   ├── contacts.ts
│   │   └── instances.ts
│   └── websocket.ts
│
├── hooks/
│   ├── useCampaigns.ts
│   ├── useCampaignDetails.ts
│   ├── useCampaignLogs.ts
│   ├── useCampaignMetrics.ts
│   └── useRealTimeUpdates.ts
│
├── stores/
│   ├── campaignStore.ts
│   ├── contactStore.ts
│   └── instanceStore.ts
│
└── types/
    ├── campaign.ts
    ├── message.ts
    └── contact.ts
```

### Componente Principal: CampaignForm

```typescript
// components/campaigns/CampaignForm.tsx

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { MessageEditor } from './MessageEditor';
import { MessagePreview } from './MessagePreview';
import { ContactSelector } from './ContactSelector';
import { ScheduleConfig } from './ScheduleConfig';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Tabs';

const campaignSchema = z.object({
  name: z.string().min(3, 'Nome muito curto').max(200, 'Nome muito longo'),
  description: z.string().optional(),
  instance_id: z.string().uuid('Selecione uma instância'),
  schedule_type: z.enum(['immediate', 'business_days', 'business_hours', 'custom_period']),
  morning_start: z.string().optional(),
  morning_end: z.string().optional(),
  afternoon_start: z.string().optional(),
  afternoon_end: z.string().optional(),
  skip_weekends: z.boolean(),
  skip_holidays: z.boolean(),
  contact_ids: z.array(z.string().uuid()).min(1, 'Selecione pelo menos 1 contato'),
  messages: z.array(z.object({
    message_text: z.string().min(1, 'Mensagem não pode estar vazia'),
    order: z.number().min(1).max(5)
  })).min(1, 'Adicione pelo menos 1 mensagem').max(5, 'Máximo 5 mensagens')
});

type CampaignFormData = z.infer<typeof campaignSchema>;

interface CampaignFormProps {
  onSubmit: (data: CampaignFormData) => Promise<void>;
  initialData?: Partial<CampaignFormData>;
  mode: 'create' | 'edit';
}

export function CampaignForm({ onSubmit, initialData, mode }: CampaignFormProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const form = useForm<CampaignFormData>({
    resolver: zodResolver(campaignSchema),
    defaultValues: initialData || {
      messages: [{ message_text: '', order: 1 }],
      skip_weekends: true,
      skip_holidays: true,
      schedule_type: 'immediate'
    }
  });
  
  const handleSubmit = async (data: CampaignFormData) => {
    setIsSubmitting(true);
    try {
      await onSubmit(data);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const steps = [
    {
      title: 'Informações Básicas',
      component: <BasicInfoStep form={form} />
    },
    {
      title: 'Mensagens',
      component: <MessagesStep form={form} />
    },
    {
      title: 'Contatos',
      component: <ContactsStep form={form} />
    },
    {
      title: 'Agendamento',
      component: <ScheduleStep form={form} />
    },
    {
      title: 'Revisão',
      component: <ReviewStep form={form} />
    }
  ];
  
  return (
    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
      {/* Stepper */}
      <div className="flex items-center justify-between mb-8">
        {steps.map((step, index) => (
          <div
            key={index}
            className={cn(
              "flex items-center",
              index <= currentStep && "text-primary font-semibold",
              index > currentStep && "text-gray-400"
            )}
          >
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center",
                index < currentStep && "bg-green-500 text-white",
                index === currentStep && "bg-primary text-white",
                index > currentStep && "bg-gray-200 text-gray-500"
              )}
            >
              {index < currentStep ? <CheckIcon /> : index + 1}
            </div>
            <span className="ml-2">{step.title}</span>
            {index < steps.length - 1 && (
              <div className="w-20 h-0.5 mx-4 bg-gray-200" />
            )}
          </div>
        ))}
      </div>
      
      {/* Step Content */}
      <Card className="p-6">
        {steps[currentStep].component}
      </Card>
      
      {/* Navigation */}
      <div className="flex justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => setCurrentStep(prev => Math.max(0, prev - 1))}
          disabled={currentStep === 0}
        >
          Voltar
        </Button>
        
        {currentStep < steps.length - 1 ? (
          <Button
            type="button"
            onClick={() => setCurrentStep(prev => Math.min(steps.length - 1, prev + 1))}
          >
            Próximo
          </Button>
        ) : (
          <Button type="submit" loading={isSubmitting}>
            {mode === 'create' ? 'Criar Campanha' : 'Salvar Alterações'}
          </Button>
        )}
      </div>
    </form>
  );
}
```

---

## 🔐 SEGURANÇA E PERFORMANCE

### Multi-Tenant Security

```python
# Sempre filtrar por tenant em TODAS as queries

class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """SEMPRE filtrar por tenant do usuário"""
        return Campaign.objects.filter(
            tenant=self.request.tenant
        ).select_related('instance', 'created_by')
    
    def perform_create(self, serializer):
        """SEMPRE injetar tenant na criação"""
        serializer.save(
            tenant=self.request.tenant,
            created_by=self.request.user
        )
```

### Rate Limiting

```python
# settings.py

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'campaign_start': '10/hour',  # Custom
    }
}

# views.py

from rest_framework.throttling import UserRateThrottle

class CampaignStartThrottle(UserRateThrottle):
    rate = '10/hour'

class CampaignViewSet(viewsets.ModelViewSet):
    
    @action(detail=True, methods=['post'], throttle_classes=[CampaignStartThrottle])
    def start(self, request, pk=None):
        # ...
```

### Database Optimization

```python
# Use connection pooling
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 600,  # 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Índices importantes
class Campaign(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'status', '-created_at']),
            models.Index(fields=['status', 'is_paused', 'next_scheduled_send']),
            models.Index(fields=['instance', 'status']),
        ]
```

---

**Última Atualização:** 2025-10-08  
**Versão:** 2.0.0  
**Autor:** ALREA Development Team

