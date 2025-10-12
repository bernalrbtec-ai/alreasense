# 📅 ALREA SCHEDULED MESSAGES - Especificação Técnica Completa

> **Projeto:** ALREA - Plataforma Multi-Produto SaaS  
> **Módulo:** Sistema de Disparos Agendados  
> **Versão:** 1.0.0  
> **Data:** 2025-10-10  
> **Prioridade:** 🟡 MÉDIA - Complemento de Campanhas

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Diferença: Campanhas vs Agendados](#diferença-campanhas-vs-agendados)
3. [Modelagem de Dados](#modelagem-de-dados)
4. [Regras de Negócio](#regras-de-negócio)
5. [API REST](#api-rest)
6. [Celery Tasks](#celery-tasks)
7. [Frontend Components](#frontend-components)
8. [Casos de Uso](#casos-de-uso)

---

## 🎯 VISÃO GERAL

### Propósito

O módulo **ALREA Scheduled Messages** permite agendar disparos de mensagens WhatsApp para **data e hora específicas**, diferente das campanhas em massa que rodam continuamente.

**Casos de uso:**
- ✅ Lembretes de consulta/reunião
- ✅ Follow-ups pós-venda agendados
- ✅ Mensagens de aniversário automáticas
- ✅ Notificações de renovação/vencimento
- ✅ Disparos únicos para grupos específicos

### Diferencial

| Característica | Campanhas | Agendados |
|----------------|-----------|-----------|
| **Quando enviar** | Janelas configuráveis (horários, dias úteis) | Data/hora exata |
| **Destinatários** | Centenas/milhares (listas, tags) | Individual ou pequenos grupos |
| **Duração** | Dias/semanas até completar | Único disparo |
| **Mensagens** | Até 5 com rotação | 1 mensagem fixa |
| **Complexidade** | Alta (Celery Beat contínuo) | Baixa (trigger único) |

---

## 🆚 DIFERENÇA: CAMPANHAS VS AGENDADOS

### Campanha (Bulk)

```
Cenário: Black Friday - 10.000 contatos
├── Inicio: 20/11/2024
├── Término: Quando completar todos
├── Horários: Seg-Sex, 9h-18h
├── Delays: 20-50s entre cada envio
├── Mensagens: 5 variações (rotação)
├── Duração estimada: 3-4 dias
└── Status: active → completed
```

### Agendado (Scheduled)

```
Cenário: Lembrete de consulta - 15 pacientes
├── Agendado para: 10/11/2024 às 14:00
├── Destinatários: Lista "Consultas Amanhã"
├── Mensagem: 1 única (com variáveis)
├── Delays: Opcional (se múltiplos)
├── Duração: ~5-10 minutos
└── Status: pending → sending → completed
```

---

## 🗄️ MODELAGEM DE DADOS

### 1. ScheduledMessage (Principal)

```python
# apps/campaigns/models.py (adicionar ao arquivo existente)

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid


class ScheduledMessage(models.Model):
    """
    Disparo agendado de mensagens WhatsApp
    
    Diferente de Campaign:
    - Executa em data/hora específica
    - Pode ser individual ou grupo pequeno
    - Mensagem única (sem rotação)
    - Ciclo de vida mais simples
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        SCHEDULED = 'scheduled', 'Agendado'
        SENDING = 'sending', 'Enviando'
        COMPLETED = 'completed', 'Concluído'
        FAILED = 'failed', 'Falhou'
        CANCELLED = 'cancelled', 'Cancelado'
    
    # ==================== IDENTIFICAÇÃO ====================
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='scheduled_messages',
        help_text="Tenant proprietário"
    )
    
    instance = models.ForeignKey(
        'notifications.WhatsAppInstance',
        on_delete=models.PROTECT,
        related_name='scheduled_messages',
        help_text="Instância WhatsApp para envio"
    )
    
    # ==================== METADADOS ====================
    name = models.CharField(
        max_length=200,
        help_text="Nome interno do agendamento (ex: 'Lembrete Consultas 10/11')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Descrição opcional"
    )
    
    # ==================== DESTINATÁRIOS ====================
    
    # Opção 1: Usar contatos cadastrados
    contacts = models.ManyToManyField(
        'contacts.Contact',
        blank=True,
        related_name='scheduled_messages',
        help_text="Contatos cadastrados no sistema"
    )
    
    # Opção 2: Números avulsos (não cadastrados)
    manual_phones = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de telefones avulsos. Ex: ['+5511999999999', '+5511988888888']"
    )
    
    # ==================== MENSAGEM ====================
    message_content = models.TextField(
        help_text="Conteúdo da mensagem (suporta variáveis: {name}, {greeting}, etc)"
    )
    
    # Opcional: Anexos
    has_attachment = models.BooleanField(
        default=False,
        help_text="Mensagem tem anexo (imagem, PDF, etc)"
    )
    
    attachment_url = models.URLField(
        null=True,
        blank=True,
        help_text="URL do anexo (se houver)"
    )
    
    attachment_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('image', 'Imagem'),
            ('document', 'Documento'),
            ('video', 'Vídeo'),
            ('audio', 'Áudio')
        ]
    )
    
    # ==================== AGENDAMENTO ====================
    scheduled_for = models.DateTimeField(
        db_index=True,
        help_text="Data e hora exata do envio"
    )
    
    timezone = models.CharField(
        max_length=50,
        default='America/Sao_Paulo',
        help_text="Timezone para o agendamento"
    )
    
    # ==================== OPÇÕES (Para múltiplos destinatários) ====================
    apply_delays = models.BooleanField(
        default=True,
        help_text="Aplicar delays entre envios (se múltiplos destinatários)"
    )
    
    min_delay_seconds = models.IntegerField(
        default=20,
        validators=[MinValueValidator(5)],
        help_text="Delay mínimo entre envios (segundos)"
    )
    
    max_delay_seconds = models.IntegerField(
        default=50,
        validators=[MinValueValidator(5)],
        help_text="Delay máximo entre envios (segundos)"
    )
    
    respect_business_hours = models.BooleanField(
        default=False,
        help_text="Respeitar horário comercial (se passar da hora, aguardar próxima janela)"
    )
    
    business_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Início do horário comercial (ex: 09:00)"
    )
    
    business_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text="Fim do horário comercial (ex: 18:00)"
    )
    
    # ==================== STATUS E CONTADORES ====================
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    
    sent_count = models.IntegerField(
        default=0,
        help_text="Número de mensagens enviadas com sucesso"
    )
    
    failed_count = models.IntegerField(
        default=0,
        help_text="Número de mensagens que falharam"
    )
    
    # ==================== CONTROLE DE EXECUÇÃO ====================
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando iniciou o envio"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando completou o envio"
    )
    
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando foi cancelado"
    )
    
    # ==================== METADADOS ====================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_messages_created',
        help_text="Usuário que criou o agendamento"
    )
    
    # ==================== META ====================
    class Meta:
        db_table = 'campaigns_scheduled_message'
        verbose_name = 'Disparo Agendado'
        verbose_name_plural = 'Disparos Agendados'
        ordering = ['-scheduled_for']
        
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['scheduled_for', 'status']),
            models.Index(fields=['tenant', 'scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.scheduled_for.strftime('%d/%m/%Y %H:%M')})"
    
    # ==================== PROPERTIES ====================
    
    @property
    def total_recipients(self):
        """Total de destinatários (contatos + números avulsos)"""
        return self.contacts.count() + len(self.manual_phones)
    
    @property
    def is_due(self):
        """Chegou a hora de enviar?"""
        if self.status != self.Status.SCHEDULED:
            return False
        
        now = timezone.now()
        return now >= self.scheduled_for
    
    @property
    def is_in_business_hours(self):
        """Está dentro do horário comercial?"""
        if not self.respect_business_hours:
            return True
        
        if not self.business_hours_start or not self.business_hours_end:
            return True
        
        now = timezone.now()
        current_time = now.time()
        
        return self.business_hours_start <= current_time <= self.business_hours_end
    
    @property
    def minutes_until_send(self):
        """Quantos minutos faltam para o envio"""
        if self.status != self.Status.SCHEDULED:
            return None
        
        now = timezone.now()
        if now >= self.scheduled_for:
            return 0
        
        delta = self.scheduled_for - now
        return int(delta.total_seconds() / 60)
    
    @property
    def success_rate(self):
        """Taxa de sucesso do envio (%)"""
        total = self.sent_count + self.failed_count
        if total == 0:
            return 0
        return (self.sent_count / total) * 100
    
    # ==================== MÉTODOS ====================
    
    def can_cancel(self):
        """Pode cancelar?"""
        return self.status in [self.Status.PENDING, self.Status.SCHEDULED]
    
    def cancel(self):
        """Cancela o agendamento"""
        if not self.can_cancel():
            raise ValueError(f'Não pode cancelar agendamento com status: {self.status}')
        
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancelled_at', 'updated_at'])
    
    def mark_as_scheduled(self):
        """Marca como agendado (pronto para disparar)"""
        self.status = self.Status.SCHEDULED
        self.save(update_fields=['status', 'updated_at'])
    
    def start_sending(self):
        """Inicia o envio"""
        self.status = self.Status.SENDING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])
    
    def mark_as_completed(self):
        """Marca como concluído"""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
    
    def mark_as_failed(self, reason=''):
        """Marca como falhou"""
        self.status = self.Status.FAILED
        self.save(update_fields=['status', 'updated_at'])
    
    def get_all_recipients(self):
        """
        Retorna lista de todos os destinatários
        
        Returns:
            list: Lista de dicts com {phone, name, contact_obj}
        """
        recipients = []
        
        # Contatos cadastrados
        for contact in self.contacts.filter(is_active=True, opted_out=False):
            recipients.append({
                'phone': contact.phone,
                'name': contact.name,
                'contact': contact
            })
        
        # Números avulsos
        for phone in self.manual_phones:
            recipients.append({
                'phone': phone,
                'name': None,
                'contact': None
            })
        
        return recipients
```

### 2. ScheduledMessageLog (Log de Envios)

```python
class ScheduledMessageLog(models.Model):
    """
    Log individual de cada envio do agendamento
    """
    
    class Status(models.TextChoices):
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Falhou'
        SKIPPED = 'skipped', 'Pulado'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    scheduled_message = models.ForeignKey(
        ScheduledMessage,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    
    # Destinatário
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Contato (se houver)"
    )
    
    phone = models.CharField(
        max_length=20,
        help_text="Telefone (backup se contact for deletado)"
    )
    
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Nome (backup)"
    )
    
    # Resultado
    status = models.CharField(
        max_length=20,
        choices=Status.choices
    )
    
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Quando foi enviado"
    )
    
    # Detalhes
    rendered_message = models.TextField(
        help_text="Mensagem renderizada (com variáveis substituídas)"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Mensagem de erro (se falhou)"
    )
    
    # Resposta da API do WhatsApp Gateway
    gateway_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Resposta completa da API"
    )
    
    gateway_message_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID da mensagem no gateway"
    )
    
    class Meta:
        db_table = 'campaigns_scheduled_message_log'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['scheduled_message', 'status']),
            models.Index(fields=['sent_at']),
        ]
    
    def __str__(self):
        return f"Log: {self.phone} - {self.status}"
```

---

## 📐 REGRAS DE NEGÓCIO

### RN01: Validação de Data/Hora

**Regra:** Não pode agendar para data passada

```python
def clean(self):
    if self.scheduled_for <= timezone.now():
        raise ValidationError('Não pode agendar para data/hora passada')
```

### RN02: Respeito ao Opt-Out

**Regra:** Contatos com `opted_out=True` são automaticamente **excluídos** da lista

```python
def get_all_recipients(self):
    # ...
    for contact in self.contacts.filter(is_active=True, opted_out=False):  # ✅
        # ...
```

### RN03: Horário Comercial (Opcional)

**Regra:** Se `respect_business_hours=True` e horário atual está **fora** da janela:
- Aguardar até o próximo horário válido
- Não enviar (manter status `scheduled`)

```python
# No Celery task
if scheduled_msg.respect_business_hours:
    if not scheduled_msg.is_in_business_hours:
        # Não enviar agora, aguardar próxima verificação
        logger.info(f'Fora do horário comercial. Aguardando...')
        return
```

### RN04: Delays entre Envios (Opcional)

**Regra:** Se `apply_delays=True` e múltiplos destinatários:
- Aplicar delay aleatório entre `min_delay_seconds` e `max_delay_seconds`
- Evitar detecção como spam

```python
import random
import time

if scheduled_msg.apply_delays and len(recipients) > 1:
    for recipient in recipients:
        send_message(recipient)
        
        # Delay aleatório
        delay = random.randint(
            scheduled_msg.min_delay_seconds,
            scheduled_msg.max_delay_seconds
        )
        time.sleep(delay)
```

### RN05: Cancelamento

**Regra:** Só pode cancelar se status for `pending` ou `scheduled`

```python
def can_cancel(self):
    return self.status in [
        ScheduledMessage.Status.PENDING,
        ScheduledMessage.Status.SCHEDULED
    ]
```

### RN06: Variáveis de Mensagem

**Regra:** Suporta as mesmas variáveis de campanhas:
- `{name}`: Nome do contato
- `{greeting}`: Saudação automática
- `{first_name}`: Primeiro nome
- `{custom.campo}`: Campos customizados

**Para números avulsos:** Variáveis que dependem de contato ficam vazias

---

## 🔌 API REST

### Endpoints

```python
# apps/campaigns/urls.py (adicionar)

urlpatterns = [
    # ... campanhas existentes ...
    
    # Scheduled Messages
    path('scheduled-messages/', ScheduledMessageListCreateView.as_view()),
    path('scheduled-messages/<uuid:pk>/', ScheduledMessageDetailView.as_view()),
    path('scheduled-messages/<uuid:pk>/cancel/', CancelScheduledMessageView.as_view()),
    path('scheduled-messages/<uuid:pk>/logs/', ScheduledMessageLogsView.as_view()),
]
```

### ViewSet

```python
# apps/campaigns/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ScheduledMessage, ScheduledMessageLog
from .serializers import ScheduledMessageSerializer, ScheduledMessageLogSerializer


class ScheduledMessageViewSet(viewsets.ModelViewSet):
    """
    CRUD de disparos agendados
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = ScheduledMessageSerializer
    
    def get_queryset(self):
        """Apenas agendamentos do tenant"""
        return ScheduledMessage.objects.filter(
            tenant=self.request.user.tenant
        ).prefetch_related('contacts', 'logs')
    
    def perform_create(self, serializer):
        """Associa tenant e usuário"""
        scheduled_msg = serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
        
        # Marcar como agendado
        scheduled_msg.mark_as_scheduled()
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancela agendamento
        
        POST /api/campaigns/scheduled-messages/{id}/cancel/
        """
        scheduled_msg = self.get_object()
        
        if not scheduled_msg.can_cancel():
            return Response(
                {'error': f'Não pode cancelar agendamento com status: {scheduled_msg.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        scheduled_msg.cancel()
        
        return Response({
            'status': 'cancelled',
            'message': 'Agendamento cancelado com sucesso'
        })
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """
        Retorna logs de envio
        
        GET /api/campaigns/scheduled-messages/{id}/logs/
        """
        scheduled_msg = self.get_object()
        logs = scheduled_msg.logs.all()
        
        serializer = ScheduledMessageLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Retorna próximos agendamentos (próximas 24h)
        
        GET /api/campaigns/scheduled-messages/upcoming/
        """
        from datetime import timedelta
        
        now = timezone.now()
        next_24h = now + timedelta(hours=24)
        
        upcoming = self.get_queryset().filter(
            status=ScheduledMessage.Status.SCHEDULED,
            scheduled_for__gte=now,
            scheduled_for__lte=next_24h
        ).order_by('scheduled_for')
        
        serializer = self.get_serializer(upcoming, many=True)
        return Response(serializer.data)
```

### Serializers

```python
# apps/campaigns/serializers.py

from rest_framework import serializers
from .models import ScheduledMessage, ScheduledMessageLog
from apps.contacts.serializers import ContactSerializer

class ScheduledMessageSerializer(serializers.ModelSerializer):
    # Computed fields
    total_recipients = serializers.ReadOnlyField()
    is_due = serializers.ReadOnlyField()
    minutes_until_send = serializers.ReadOnlyField()
    success_rate = serializers.ReadOnlyField()
    
    # Relations
    contacts = ContactSerializer(many=True, read_only=True)
    contact_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Contact.objects.all(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = ScheduledMessage
        fields = [
            'id', 'tenant', 'instance',
            'name', 'description',
            'contacts', 'contact_ids', 'manual_phones',
            'message_content', 'has_attachment', 'attachment_url', 'attachment_type',
            'scheduled_for', 'timezone',
            'apply_delays', 'min_delay_seconds', 'max_delay_seconds',
            'respect_business_hours', 'business_hours_start', 'business_hours_end',
            'status', 'sent_count', 'failed_count',
            'started_at', 'completed_at', 'cancelled_at',
            'created_at', 'updated_at',
            'total_recipients', 'is_due', 'minutes_until_send', 'success_rate'
        ]
        read_only_fields = [
            'id', 'tenant', 'status',
            'sent_count', 'failed_count',
            'started_at', 'completed_at', 'cancelled_at',
            'created_at', 'updated_at'
        ]
    
    def validate_scheduled_for(self, value):
        """Não pode agendar para o passado"""
        if value <= timezone.now():
            raise serializers.ValidationError('Não pode agendar para data/hora passada')
        return value
    
    def create(self, validated_data):
        contact_ids = validated_data.pop('contact_ids', [])
        
        scheduled_msg = ScheduledMessage.objects.create(**validated_data)
        
        if contact_ids:
            scheduled_msg.contacts.set(contact_ids)
        
        return scheduled_msg


class ScheduledMessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledMessageLog
        fields = '__all__'
```

---

## ⚙️ CELERY TASKS

### Task Principal: Verificar e Processar Agendamentos

```python
# apps/campaigns/tasks.py

from celery import shared_task
from django.utils import timezone
from .models import ScheduledMessage, ScheduledMessageLog
from apps.campaigns.services import MessageVariableService
import random
import time


@shared_task
def check_scheduled_messages():
    """
    Celery Beat task que roda a cada minuto
    Verifica se há agendamentos para processar
    """
    now = timezone.now()
    
    # Buscar agendamentos que chegaram na hora
    due_messages = ScheduledMessage.objects.filter(
        status=ScheduledMessage.Status.SCHEDULED,
        scheduled_for__lte=now
    )
    
    for scheduled_msg in due_messages:
        # Disparar task assíncrona para processar
        process_scheduled_message.delay(scheduled_msg.id)


@shared_task
def process_scheduled_message(scheduled_message_id):
    """
    Processa um agendamento específico
    
    Args:
        scheduled_message_id: UUID do ScheduledMessage
    """
    try:
        scheduled_msg = ScheduledMessage.objects.get(id=scheduled_message_id)
    except ScheduledMessage.DoesNotExist:
        logger.error(f'ScheduledMessage {scheduled_message_id} não encontrado')
        return
    
    # Verificar status
    if scheduled_msg.status != ScheduledMessage.Status.SCHEDULED:
        logger.warning(f'Agendamento {scheduled_msg.id} não está com status SCHEDULED')
        return
    
    # Verificar horário comercial (se configurado)
    if scheduled_msg.respect_business_hours:
        if not scheduled_msg.is_in_business_hours:
            logger.info(f'Agendamento {scheduled_msg.id} fora do horário comercial. Aguardando...')
            return
    
    # Iniciar envio
    scheduled_msg.start_sending()
    
    # Pegar todos os destinatários
    recipients = scheduled_msg.get_all_recipients()
    
    if not recipients:
        scheduled_msg.mark_as_failed(reason='Nenhum destinatário encontrado')
        return
    
    # Processar cada destinatário
    for i, recipient in enumerate(recipients):
        try:
            # Renderizar mensagem com variáveis
            if recipient['contact']:
                rendered = MessageVariableService.render_message(
                    template=scheduled_msg.message_content,
                    contact=recipient['contact']
                )
            else:
                # Número avulso: substituir variáveis por vazio
                rendered = scheduled_msg.message_content
                rendered = rendered.replace('{name}', '')
                rendered = rendered.replace('{greeting}', _get_greeting())
                # ... outras variáveis
            
            # Enviar via WhatsApp Gateway
            from apps.connections.services import WhatsAppGatewayService
            
            gateway_service = WhatsAppGatewayService(scheduled_msg.instance)
            result = gateway_service.send_text_message(
                phone=recipient['phone'],
                message=rendered
            )
            
            # Log de sucesso
            ScheduledMessageLog.objects.create(
                scheduled_message=scheduled_msg,
                contact=recipient['contact'],
                phone=recipient['phone'],
                name=recipient.get('name', ''),
                status=ScheduledMessageLog.Status.SENT,
                rendered_message=rendered,
                gateway_response=result,
                gateway_message_id=result.get('messageId', '')
            )
            
            scheduled_msg.sent_count += 1
            scheduled_msg.save(update_fields=['sent_count'])
            
        except Exception as e:
            logger.error(f'Erro ao enviar para {recipient["phone"]}: {e}')
            
            # Log de erro
            ScheduledMessageLog.objects.create(
                scheduled_message=scheduled_msg,
                contact=recipient['contact'],
                phone=recipient['phone'],
                name=recipient.get('name', ''),
                status=ScheduledMessageLog.Status.FAILED,
                rendered_message=rendered if 'rendered' in locals() else '',
                error_message=str(e)
            )
            
            scheduled_msg.failed_count += 1
            scheduled_msg.save(update_fields=['failed_count'])
        
        # Delay entre envios (se configurado)
        if scheduled_msg.apply_delays and i < len(recipients) - 1:
            delay = random.randint(
                scheduled_msg.min_delay_seconds,
                scheduled_msg.max_delay_seconds
            )
            time.sleep(delay)
    
    # Marcar como concluído
    scheduled_msg.mark_as_completed()
    
    logger.info(
        f'Agendamento {scheduled_msg.id} concluído. '
        f'Enviados: {scheduled_msg.sent_count}, '
        f'Falhas: {scheduled_msg.failed_count}'
    )


def _get_greeting():
    """Retorna saudação baseada na hora"""
    from datetime import datetime
    
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return 'Bom dia'
    elif 12 <= hour < 18:
        return 'Boa tarde'
    else:
        return 'Boa noite'
```

### Configuração do Celery Beat

```python
# backend/alrea_sense/celery.py

from celery.schedules import crontab

app.conf.beat_schedule = {
    # ... schedules existentes ...
    
    'check-scheduled-messages': {
        'task': 'apps.campaigns.tasks.check_scheduled_messages',
        'schedule': crontab(minute='*/1'),  # A cada minuto
    },
}
```

---

## 🎨 FRONTEND COMPONENTS

### ScheduledMessagesPage (Lista)

```tsx
// frontend/src/pages/ScheduledMessagesPage.tsx

import { useState, useEffect } from 'react'
import { Plus, Calendar, Clock, Users, CheckCircle, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { api } from '@/lib/api'

export default function ScheduledMessagesPage() {
  const [scheduledMessages, setScheduledMessages] = useState([])
  const [filter, setFilter] = useState('all') // all | upcoming | completed
  
  const fetchScheduledMessages = async () => {
    const response = await api.get('/campaigns/scheduled-messages/')
    setScheduledMessages(response.data.results)
  }
  
  const statusColors = {
    pending: 'gray',
    scheduled: 'blue',
    sending: 'yellow',
    completed: 'green',
    failed: 'red',
    cancelled: 'gray'
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Disparos Agendados</h1>
          <p className="text-gray-500">Agende mensagens para data/hora específica</p>
        </div>
        
        <Button onClick={() => navigate('/scheduled-messages/new')}>
          <Plus className="h-4 w-4 mr-2" />
          Novo Agendamento
        </Button>
      </div>
      
      {/* Filters */}
      <div className="flex gap-2">
        <Button 
          variant={filter === 'all' ? 'primary' : 'outline'}
          onClick={() => setFilter('all')}
        >
          Todos
        </Button>
        <Button 
          variant={filter === 'upcoming' ? 'primary' : 'outline'}
          onClick={() => setFilter('upcoming')}
        >
          Próximos
        </Button>
        <Button 
          variant={filter === 'completed' ? 'primary' : 'outline'}
          onClick={() => setFilter('completed')}
        >
          Concluídos
        </Button>
      </div>
      
      {/* List */}
      <div className="space-y-4">
        {scheduledMessages.map(msg => (
          <Card key={msg.id} className="p-6">
            <div className="flex justify-between items-start">
              {/* Info */}
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-lg font-semibold">{msg.name}</h3>
                  <Badge color={statusColors[msg.status]}>
                    {msg.status}
                  </Badge>
                </div>
                
                <div className="flex items-center gap-6 text-sm text-gray-600">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    {new Date(msg.scheduled_for).toLocaleDateString('pt-BR')}
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    {new Date(msg.scheduled_for).toLocaleTimeString('pt-BR', {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    {msg.total_recipients} destinatários
                  </div>
                </div>
                
                {/* Preview */}
                <div className="mt-3 p-3 bg-gray-50 rounded text-sm">
                  {msg.message_content.substring(0, 100)}
                  {msg.message_content.length > 100 && '...'}
                </div>
                
                {/* Stats (se enviado) */}
                {msg.status === 'completed' && (
                  <div className="mt-3 flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-1 text-green-600">
                      <CheckCircle className="h-4 w-4" />
                      {msg.sent_count} enviados
                    </div>
                    
                    {msg.failed_count > 0 && (
                      <div className="flex items-center gap-1 text-red-600">
                        <XCircle className="h-4 w-4" />
                        {msg.failed_count} falhas
                      </div>
                    )}
                    
                    <span className="text-gray-500">
                      Taxa: {msg.success_rate.toFixed(1)}%
                    </span>
                  </div>
                )}
                
                {/* Countdown (se pendente) */}
                {msg.status === 'scheduled' && msg.minutes_until_send !== null && (
                  <div className="mt-2 text-sm text-blue-600">
                    ⏱️ Dispara em {msg.minutes_until_send} minutos
                  </div>
                )}
              </div>
              
              {/* Actions */}
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => viewLogs(msg.id)}>
                  Ver Logs
                </Button>
                
                {msg.status === 'scheduled' && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    className="text-red-600"
                    onClick={() => cancelScheduled(msg.id)}
                  >
                    Cancelar
                  </Button>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

### NewScheduledMessageModal

```tsx
// frontend/src/components/scheduled-messages/NewScheduledMessageModal.tsx

import { useState } from 'react'
import { Calendar, Clock, Users, MessageSquare } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import ContactSelector from '@/components/contacts/ContactSelector'
import WhatsAppPreview from '@/components/campaigns/WhatsAppPreview'

export default function NewScheduledMessageModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: '',
    message_content: '',
    scheduled_for_date: '',
    scheduled_for_time: '',
    contact_ids: [],
    manual_phones: [],
    apply_delays: true,
    min_delay_seconds: 20,
    max_delay_seconds: 50
  })
  
  const handleSubmit = async () => {
    // Combinar data + hora
    const scheduled_for = new Date(`${formData.scheduled_for_date}T${formData.scheduled_for_time}`)
    
    await api.post('/campaigns/scheduled-messages/', {
      ...formData,
      scheduled_for: scheduled_for.toISOString()
    })
    
    onSuccess()
  }
  
  return (
    <Modal onClose={onClose}>
      <h2 className="text-xl font-bold mb-4">Novo Disparo Agendado</h2>
      
      {/* Nome */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-1">
          Nome do Agendamento
        </label>
        <input
          type="text"
          value={formData.name}
          onChange={e => setFormData({...formData, name: e.target.value})}
          placeholder="Ex: Lembrete Consultas 10/11"
          className="w-full px-3 py-2 border rounded"
        />
      </div>
      
      {/* Data/Hora */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-sm font-medium mb-1">
            <Calendar className="h-4 w-4 inline mr-1" />
            Data
          </label>
          <input
            type="date"
            value={formData.scheduled_for_date}
            onChange={e => setFormData({...formData, scheduled_for_date: e.target.value})}
            className="w-full px-3 py-2 border rounded"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1">
            <Clock className="h-4 w-4 inline mr-1" />
            Horário
          </label>
          <input
            type="time"
            value={formData.scheduled_for_time}
            onChange={e => setFormData({...formData, scheduled_for_time: e.target.value})}
            className="w-full px-3 py-2 border rounded"
          />
        </div>
      </div>
      
      {/* Destinatários */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-1">
          <Users className="h-4 w-4 inline mr-1" />
          Destinatários
        </label>
        <ContactSelector
          selectedContacts={formData.contact_ids}
          onChange={contacts => setFormData({...formData, contact_ids: contacts})}
        />
      </div>
      
      {/* Mensagem */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-1">
          <MessageSquare className="h-4 w-4 inline mr-1" />
          Mensagem
        </label>
        <div className="grid grid-cols-2 gap-4">
          <textarea
            value={formData.message_content}
            onChange={e => setFormData({...formData, message_content: e.target.value})}
            rows={6}
            placeholder="Olá {name}, {greeting}!&#10;&#10;Lembrete: você tem consulta agendada para amanhã às 14h."
            className="w-full px-3 py-2 border rounded font-mono text-sm"
          />
          
          <WhatsAppPreview message={formData.message_content} />
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Variáveis: {'{name}'}, {'{greeting}'}, {'{first_name}'}
        </p>
      </div>
      
      {/* Opções Avançadas */}
      <div className="mb-4">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={formData.apply_delays}
            onChange={e => setFormData({...formData, apply_delays: e.target.checked})}
          />
          <span className="text-sm">Aplicar delays entre envios (se múltiplos destinatários)</span>
        </label>
        
        {formData.apply_delays && (
          <div className="ml-6 mt-2 grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-600">Delay mínimo (seg)</label>
              <input
                type="number"
                value={formData.min_delay_seconds}
                onChange={e => setFormData({...formData, min_delay_seconds: parseInt(e.target.value)})}
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            
            <div>
              <label className="block text-xs text-gray-600">Delay máximo (seg)</label>
              <input
                type="number"
                value={formData.max_delay_seconds}
                onChange={e => setFormData({...formData, max_delay_seconds: parseInt(e.target.value)})}
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        )}
      </div>
      
      {/* Actions */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button onClick={handleSubmit}>
          Agendar Disparo
        </Button>
      </div>
    </Modal>
  )
}
```

---

## 💡 CASOS DE USO

### Caso 1: Lembrete de Consulta

```
Cliente: Clínica Odontológica
Cenário: Lembrar pacientes do dia seguinte

Processo:
1. Todo dia às 18h, buscar consultas de amanhã
2. Criar ScheduledMessage automático
3. Agendar para 14h do dia da consulta
4. Enviar lembrete 1h antes
```

### Caso 2: Follow-up Pós-Venda

```
Cliente: E-commerce
Cenário: Pedir avaliação 3 dias após entrega

Processo:
1. Ao marcar entrega como concluída
2. Criar ScheduledMessage para daqui 3 dias
3. Mensagem: "Olá {name}, recebeu seu pedido? Avalie!"
```

### Caso 3: Aniversário Automático

```
Cliente: Loja de Varejo
Cenário: Parabenizar clientes

Processo:
1. Celery Beat diário: buscar aniversariantes de amanhã
2. Criar ScheduledMessage para 9h da manhã
3. Mensagem: "🎂 {name}, parabéns! Ganhe 15% OFF hoje!"
```

---

## ⏱️ ESTIMATIVA DE IMPLEMENTAÇÃO

| Fase | Tarefas | Tempo |
|------|---------|-------|
| **Backend** | Models + Migrations | 2h |
| | Serializers + Views | 2h |
| | Celery Tasks | 3h |
| | Testes | 2h |
| **Frontend** | Página de listagem | 3h |
| | Modal de criação | 4h |
| | Integração API | 2h |
| **Total** | | **18-20h (~2-3 dias)** |

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### Backend
- [ ] Model `ScheduledMessage`
- [ ] Model `ScheduledMessageLog`
- [ ] Migrations
- [ ] Serializers
- [ ] ViewSet + URLs
- [ ] Celery task `check_scheduled_messages`
- [ ] Celery task `process_scheduled_message`
- [ ] Configurar Celery Beat
- [ ] Testes unitários

### Frontend
- [ ] Página `ScheduledMessagesPage`
- [ ] Modal `NewScheduledMessageModal`
- [ ] Component `ContactSelector`
- [ ] Integração com API
- [ ] Preview de mensagem
- [ ] Cancelamento de agendamento
- [ ] Visualização de logs

---

**Este módulo complementa perfeitamente o sistema de Campanhas!** 📅🚀




