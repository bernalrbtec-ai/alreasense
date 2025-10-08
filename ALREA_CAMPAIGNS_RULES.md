# 📋 ALREA CAMPAIGNS - Regras de Desenvolvimento

> **Projeto:** ALREA - Sistema Multi-Produto de Marketing e Analytics  
> **Módulo:** Campaigns (Disparos WhatsApp)  
> **Stack:** Django 5 + DRF + Celery + PostgreSQL + React + TypeScript  
> **Última Atualização:** 2025-10-08

---

## 📚 ÍNDICE

1. [Filosofia do Projeto](#filosofia-do-projeto)
2. [Arquitetura Django](#arquitetura-django)
3. [Workers e Processamento Assíncrono](#workers-e-processamento-assíncrono)
4. [Múltiplas Campanhas Simultâneas](#múltiplas-campanhas-simultâneas)
5. [Sistema de Janelas e Horários](#sistema-de-janelas-e-horários)
6. [Anti-Spam e Proteções](#anti-spam-e-proteções)
7. [UI/UX Guidelines](#uiux-guidelines)
8. [Testes](#testes)
9. [Performance](#performance)
10. [Segurança](#segurança)
11. [Checklist de Code Review](#checklist-de-code-review)

---

## 🎯 FILOSOFIA DO PROJETO

### Princípios Fundamentais

1. **UX-First Development**: Toda feature começa pelo design da experiência do usuário
2. **Progressive Disclosure**: Mostrar apenas o necessário, esconder complexidade
3. **Feedback Instantâneo**: Usuário NUNCA fica sem saber o que está acontecendo
4. **Zero Surpresas**: Sistema deve ser previsível e transparente
5. **Fail Gracefully**: Erros são oportunidades para ajudar o usuário

### Valores de Código

- **Explícito > Implícito**: Código deve ser óbvio, não "esperto"
- **Testável**: Se é difícil testar, está mal arquitetado
- **Performance Consciente**: Otimizar pontos críticos, não tudo
- **Multi-tenant First**: SEMPRE pensar em isolamento de dados
- **Audit Everything**: Cada ação importante deve ser logada

---

## 🏗️ ARQUITETURA DJANGO

### Estrutura de Apps

```
backend/apps/
├── campaigns/          # Sistema de campanhas
│   ├── models.py      # Campaign, CampaignMessage, CampaignContact
│   ├── views.py       # ViewSets DRF
│   ├── serializers.py # Serializers com validações ricas
│   ├── tasks.py       # Celery tasks (scheduler, dispatcher)
│   ├── services.py    # Lógica de negócio (CampaignService)
│   ├── permissions.py # Permissions customizadas
│   ├── validators.py  # Validadores reutilizáveis
│   ├── signals.py     # Hooks de lifecycle
│   └── tests/         # Testes organizados por tipo
│       ├── test_models.py
│       ├── test_views.py
│       ├── test_tasks.py
│       └── test_services.py
│
├── contacts/          # Gestão de contatos
├── connections/       # Instâncias Evolution API
├── tenancy/           # Multi-tenancy
├── billing/           # Planos e pagamentos
└── common/            # Utilitários compartilhados
```

### Regras de Models

#### ✅ SEMPRE FAZER:

```python
# 1. UUIDs como Primary Key (segurança + multi-tenant)
class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
# 2. Tenant isolation em TODOS os models de negócio
class Campaign(models.Model):
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)
    
    class Meta:
        # Sempre indexar tenant + campos de busca frequente
        indexes = [
            models.Index(fields=['tenant', 'status', 'created_at']),
        ]

# 3. Timestamps automáticos
class Campaign(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
# 4. Status como Choices (nunca strings soltas)
class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativa'
        PAUSED = 'paused', 'Pausada'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True  # Status é buscado frequentemente
    )

# 5. Help text descritivo
class Campaign(models.Model):
    delay_min_seconds = models.IntegerField(
        default=20,
        help_text="Delay mínimo entre envios (segundos). Recomendado: 20-30s para parecer natural."
    )

# 6. Validators no model
from django.core.validators import MinValueValidator, MaxValueValidator

class Campaign(models.Model):
    delay_min_seconds = models.IntegerField(
        validators=[MinValueValidator(10), MaxValueValidator(300)]
    )

# 7. Properties para lógica derivada
class Campaign(models.Model):
    sent_messages = models.IntegerField(default=0)
    total_contacts = models.IntegerField(default=0)
    
    @property
    def progress_percentage(self):
        """Percentual de progresso da campanha"""
        if self.total_contacts == 0:
            return 0
        return round((self.sent_messages / self.total_contacts) * 100, 1)
    
    @property
    def can_be_started(self):
        """Verifica se campanha pode ser iniciada"""
        return (
            self.status == Campaign.Status.DRAFT and
            self.total_contacts > 0 and
            self.messages.filter(is_active=True).exists() and
            self.instance.is_connected
        )

# 8. Methods para ações de negócio
class Campaign(models.Model):
    def start(self, user):
        """Inicia a campanha"""
        if not self.can_be_started:
            raise ValidationError("Campanha não pode ser iniciada no estado atual")
        
        self.status = Campaign.Status.ACTIVE
        self.started_at = timezone.now()
        self.started_by = user
        self.save(update_fields=['status', 'started_at', 'started_by'])
        
        # Log de auditoria
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            event_type='campaign_started',
            message=f'Campanha iniciada por {user.email}'
        )
        
        # Signal para side effects
        campaign_started.send(sender=self.__class__, campaign=self, user=user)

# 9. __str__ útil para debugging
def __str__(self):
    return f"{self.name} ({self.get_status_display()}) - {self.tenant.name}"

# 10. Meta ordenada e verbosa
class Meta:
    db_table = 'campaigns_campaign'
    verbose_name = 'Campanha'
    verbose_name_plural = 'Campanhas'
    ordering = ['-created_at']
    
    # Constraints de negócio no banco
    constraints = [
        models.UniqueConstraint(
            fields=['instance'],
            condition=models.Q(status='active'),
            name='unique_active_campaign_per_instance'
        ),
        models.CheckConstraint(
            check=models.Q(delay_min_seconds__lte=models.F('delay_max_seconds')),
            name='delay_min_lte_delay_max'
        ),
    ]
```

#### ❌ NUNCA FAZER:

```python
# ❌ IDs incrementais (vazam informação, não escalam em multi-tenant)
id = models.AutoField(primary_key=True)

# ❌ Strings mágicas
status = 'active'  # Use choices!

# ❌ Lógica de negócio nos views
def create_campaign(request):
    campaign = Campaign.objects.create(...)
    # enviar email
    # criar logs
    # etc
    # ❌ Isso deve estar em um Service!

# ❌ Queries sem select_related/prefetch_related
campaigns = Campaign.objects.all()  # N+1 query problem
for c in campaigns:
    print(c.instance.name)  # 1 query por campanha!

# ✅ CORRETO:
campaigns = Campaign.objects.select_related('instance', 'tenant').all()

# ❌ Uso de .get() sem tratamento
campaign = Campaign.objects.get(id=campaign_id)  # Pode levantar DoesNotExist

# ✅ CORRETO:
from django.shortcuts import get_object_or_404
campaign = get_object_or_404(Campaign, id=campaign_id, tenant=request.tenant)
```

---

### Regras de Services

**Services encapsulam lógica de negócio complexa**

```python
# campaigns/services.py

class CampaignService:
    """Service para operações de campanha"""
    
    def __init__(self, tenant, user=None):
        self.tenant = tenant
        self.user = user
    
    def create_campaign(self, data: dict) -> Campaign:
        """
        Cria uma nova campanha com todas as validações de negócio
        
        Args:
            data: Dicionário com dados da campanha
            
        Returns:
            Campaign criada
            
        Raises:
            ValidationError: Se dados inválidos
            PermissionDenied: Se tenant não tem permissão
        """
        # 1. Validar limites do plano
        if not self.tenant.can_create_campaign():
            raise PermissionDenied(
                "Limite de campanhas atingido. Faça upgrade do plano."
            )
        
        # 2. Validar instância disponível
        instance = data.get('instance')
        if instance.has_active_campaign:
            raise ValidationError({
                'instance': f'Instância ocupada com campanha "{instance.current_campaign.name}"'
            })
        
        # 3. Criar campanha
        with transaction.atomic():
            campaign = Campaign.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                **data
            )
            
            # 4. Criar relacionamentos de contatos
            contacts = data.get('contacts', [])
            campaign_contacts = [
                CampaignContact(
                    campaign=campaign,
                    contact=contact,
                    status=CampaignContact.Status.PENDING
                )
                for contact in contacts
            ]
            CampaignContact.objects.bulk_create(campaign_contacts)
            
            # 5. Atualizar contador
            campaign.total_contacts = len(contacts)
            campaign.save(update_fields=['total_contacts'])
            
            # 6. Log de auditoria
            CampaignLog.objects.create(
                campaign=campaign,
                user=self.user,
                event_type='campaign_created',
                message=f'Campanha criada com {len(contacts)} contatos',
                metadata={'contact_count': len(contacts)}
            )
        
        return campaign
    
    def start_campaign(self, campaign_id: uuid.UUID) -> Campaign:
        """Inicia campanha com todas as validações"""
        campaign = get_object_or_404(
            Campaign,
            id=campaign_id,
            tenant=self.tenant
        )
        
        # Validações
        if not campaign.can_be_started:
            raise ValidationError("Campanha não pode ser iniciada")
        
        # Iniciar
        campaign.start(user=self.user)
        
        return campaign
```

**USO nos Views:**

```python
# views.py

class CampaignViewSet(viewsets.ModelViewSet):
    
    @action(detail=False, methods=['post'])
    def create_and_start(self, request):
        """Criar e iniciar campanha em uma ação"""
        serializer = CampaignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Service encapsula a complexidade
        service = CampaignService(
            tenant=request.tenant,
            user=request.user
        )
        
        try:
            campaign = service.create_campaign(serializer.validated_data)
            campaign = service.start_campaign(campaign.id)
            
            return Response(
                CampaignSerializer(campaign).data,
                status=status.HTTP_201_CREATED
            )
        except PermissionDenied as e:
            return Response(
                {'error': 'PERMISSION_DENIED', 'message': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValidationError as e:
            return Response(
                {'error': 'VALIDATION_ERROR', 'details': e.message_dict},
                status=status.HTTP_400_BAD_REQUEST
            )
```

---

### Regras de Serializers

```python
# serializers.py

class CampaignSerializer(serializers.ModelSerializer):
    """Serializer completo de campanha"""
    
    # Campos derivados (read-only)
    progress_percentage = serializers.ReadOnlyField()
    can_be_started = serializers.ReadOnlyField()
    
    # Relacionamentos nested (apenas leitura)
    instance = EvolutionInstanceSerializer(read_only=True)
    messages = CampaignMessageSerializer(many=True, read_only=True)
    
    # Campos write-only para criação
    instance_id = serializers.UUIDField(write_only=True)
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'status', 'progress_percentage',
            'instance', 'instance_id',
            'messages', 'contact_ids',
            'total_contacts', 'sent_messages', 'failed_messages',
            'can_be_started',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'sent_messages', 'failed_messages']
    
    def validate_instance_id(self, value):
        """Valida que instância existe e está disponível"""
        try:
            instance = EvolutionInstance.objects.get(
                id=value,
                tenant=self.context['request'].tenant
            )
        except EvolutionInstance.DoesNotExist:
            raise serializers.ValidationError("Instância não encontrada")
        
        if not instance.is_connected:
            raise serializers.ValidationError(
                "Instância está desconectada. Conecte-a antes de criar a campanha."
            )
        
        if instance.has_active_campaign:
            raise serializers.ValidationError(
                f'Instância ocupada com a campanha "{instance.current_campaign.name}"'
            )
        
        return value
    
    def validate_contact_ids(self, value):
        """Valida que contatos existem e pertencem ao tenant"""
        if not value:
            return value
        
        contacts = Contact.objects.filter(
            id__in=value,
            tenant=self.context['request'].tenant
        )
        
        if contacts.count() != len(value):
            raise serializers.ValidationError(
                "Um ou mais contatos não foram encontrados"
            )
        
        return value
    
    def validate(self, attrs):
        """Validações cross-field"""
        # Exemplo: se selecionou tag, não pode enviar contact_ids
        if attrs.get('contact_tag') and attrs.get('contact_ids'):
            raise serializers.ValidationError(
                "Selecione apenas tag OU lista de contatos, não ambos"
            )
        
        return attrs
```

---

### Regras de Celery Tasks

```python
# tasks.py

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=60,  # 60s timeout
    time_limit=90,        # 90s hard limit
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
        rendered_message: Mensagem renderizada com variáveis
    
    Returns:
        dict com resultado do envio
    """
    try:
        # 1. Buscar objetos (select_related para performance)
        campaign = Campaign.objects.select_related(
            'instance', 'tenant'
        ).get(id=campaign_id)
        
        contact_relation = CampaignContact.objects.select_related(
            'contact'
        ).get(id=contact_relation_id)
        
        contact = contact_relation.contact
        
        # 2. Validações críticas antes de enviar
        if campaign.is_paused:
            logger.warning(
                f"Campaign {campaign_id} is paused, aborting send",
                extra={'campaign_id': str(campaign_id)}
            )
            return {'status': 'aborted', 'reason': 'paused'}
        
        if campaign.status != Campaign.Status.ACTIVE:
            logger.warning(
                f"Campaign {campaign_id} is not active (status={campaign.status})",
                extra={'campaign_id': str(campaign_id), 'status': campaign.status}
            )
            return {'status': 'aborted', 'reason': 'not_active'}
        
        # 3. Enviar via Evolution API
        logger.info(
            f"Sending message to {contact.name} ({contact.phone})",
            extra={
                'campaign_id': str(campaign_id),
                'contact_id': str(contact.id),
                'instance': campaign.instance.name
            }
        )
        
        response = evolution_api.send_text(
            instance_id=campaign.instance.evolution_instance_id,
            phone=contact.phone,
            message=rendered_message,
            api_key=campaign.instance.api_key
        )
        
        # 4. Atualizar status (usar update para evitar race conditions)
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status=CampaignContact.Status.SENT,
            sent_at=timezone.now(),
            evolution_message_id=response.get('key', {}).get('id')
        )
        
        # 5. Incrementar contadores (F() expressions para atomicidade)
        Campaign.objects.filter(id=campaign_id).update(
            sent_messages=models.F('sent_messages') + 1,
            last_successful_send=timezone.now()
        )
        
        # 6. Log de sucesso
        CampaignLog.objects.create(
            campaign=campaign,
            contact=contact,
            level=CampaignLog.Level.SUCCESS,
            event_type='message_sent',
            message=f'Mensagem enviada para {contact.name}',
            metadata={
                'evolution_response': response,
                'message_length': len(rendered_message)
            }
        )
        
        logger.info(
            f"Message sent successfully to {contact.name}",
            extra={'campaign_id': str(campaign_id), 'contact_id': str(contact.id)}
        )
        
        return {'status': 'success', 'message_id': response.get('key', {}).get('id')}
        
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return {'status': 'error', 'reason': 'campaign_not_found'}
        
    except Exception as e:
        logger.exception(
            f"Error sending message: {str(e)}",
            extra={'campaign_id': str(campaign_id), 'error': str(e)}
        )
        
        # Marcar como falha no banco
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status=CampaignContact.Status.FAILED,
            error_message=str(e)
        )
        
        Campaign.objects.filter(id=campaign_id).update(
            failed_messages=models.F('failed_messages') + 1,
            last_error=str(e),
            last_error_at=timezone.now()
        )
        
        # Retry se for erro temporário
        if isinstance(e, (ConnectionError, TimeoutError)):
            raise self.retry(exc=e, countdown=30)
        
        raise
```

---

## ⚙️ WORKERS E PROCESSAMENTO ASSÍNCRONO

### O que são Workers?

**Workers NÃO são backends separados.** São processos Celery que rodam dentro do mesmo backend Django.

### Arquitetura de Processos

```
BACKEND (Django)
├── Processo 1: Django Web (Gunicorn)
│   └── Recebe requests HTTP, retorna API REST
│       ❌ NÃO envia mensagens diretamente
│
├── Processo 2: Celery Beat (Scheduler)
│   └── Roda a cada 10s, busca campanhas prontas
│       ❌ NÃO envia mensagens
│       ✅ Enfileira tasks no Redis
│
└── Processos 3-N: Celery Workers (Dispatchers)
    └── ⭐ AQUI que as mensagens são ENVIADAS
        ✅ Pega tasks da fila Redis
        ✅ Envia via WhatsApp Gateway API
        ✅ Atualiza banco de dados
```

### Fluxo Completo de Envio

```python
# 1. Frontend → Django API
POST /api/campaigns/123/start/
  ↓ Django atualiza: status='active', next_scheduled_send=NOW()+10s
  ↓ Retorna 200 OK
  ❌ NENHUMA mensagem enviada ainda

# 2. Celery Beat (10s depois)
@shared_task  # Roda a cada 10s
def campaign_scheduler():
    campaigns = Campaign.objects.filter(
        status='active',
        is_paused=False,
        next_scheduled_send__lte=NOW()
    )
    
    for campaign in campaigns:
        # Pega próximo contato
        contact = get_next_contact(campaign)
        
        # ❌ NÃO envia aqui
        # ✅ Enfileira task
        send_message_task.apply_async(
            kwargs={'campaign_id': ..., 'contact_id': ...}
        )
        # Task vai para Redis

# 3. Celery Worker (pega da fila)
@shared_task
def send_message_task(campaign_id, contact_id, message):
    # Buscar dados
    campaign = Campaign.objects.get(id=campaign_id)
    
    # Validar
    if campaign.is_paused:
        return 'aborted'
    
    # ⭐ ENVIAR (comunicação real com WhatsApp)
    response = whatsapp_gateway.send_message(
        instance=campaign.instance,
        phone=contact.phone,
        message=message
    )
    
    # Atualizar banco
    CampaignContact.objects.update(status='sent')
    
    return 'success'
```

### Escalabilidade com Workers

```bash
# 1 worker = ~20 msgs/minuto
celery -A alrea_sense worker -c 1

# 3 workers = ~60 msgs/minuto
celery -A alrea_sense worker -c 3

# 10 workers = ~200 msgs/minuto
celery -A alrea_sense worker -c 10

# ⭐ "Adicionar workers" = aumentar concurrency (-c)
# Mais workers = mais throughput
```

### Configuração em Produção

```yaml
# docker-compose.yml

services:
  # Django API
  web:
    command: gunicorn alrea_sense.wsgi:application --workers 4
  
  # Celery Beat (apenas 1 instância)
  celery-beat:
    command: celery -A alrea_sense beat -l info
  
  # Celery Workers (escalável)
  celery-worker:
    command: celery -A alrea_sense worker -c 10 -l info
    # Escalar: docker-compose up --scale celery-worker=5
```

### Regras de Workers

```python
# ✅ SEMPRE FAZER

# 1. Validar estado ANTES de enviar (worker pode pegar task antiga)
@shared_task
def send_message_task(self, campaign_id, ...):
    campaign = Campaign.objects.get(id=campaign_id)  # Fresh do banco
    
    if campaign.is_paused:  # Dupla validação
        return 'aborted'
    
    # Só envia se passou validação

# 2. Usar retry automático para erros temporários
@shared_task(
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=3
)
def send_message_task(self, ...):
    # ...

# 3. Liberar locks em finally
try:
    # enviar mensagem
    pass
finally:
    redis.delete(f'lock:{phone}')  # SEMPRE libera

# ❌ NUNCA FAZER

# 1. Enviar mensagem no endpoint da API
@action(detail=True, methods=['post'])
def start(self, request, pk=None):
    campaign.status = 'active'
    campaign.save()
    
    # ❌ NUNCA fazer isso:
    # for contact in contacts:
    #     send_message(contact)  # Bloqueia request!
    
    return Response({'status': 'started'})

# 2. Processar no scheduler
@shared_task
def campaign_scheduler():
    # ❌ NUNCA:
    # send_message(...)  # Bloqueia outros schedulers
    
    # ✅ CORRETO:
    send_message_task.apply_async(...)  # Enfileira
```

---

## 🔄 MÚLTIPLAS CAMPANHAS SIMULTÂNEAS

### Regras de Negócio

```
✅ 1 instância WhatsApp = 1 campanha ativa por vez
✅ Cliente pode ter N campanhas ativas (limitado por instâncias)
✅ Mesmo contato pode estar em múltiplas campanhas
```

### Separação no Banco de Dados

```python
# Cada campanha totalmente isolada por campaign_id

# Campanha A: Black Friday
Campaign(id='uuid-A', name='Black Friday', instance=inst1, status='active')
CampaignContact(campaign='uuid-A', contact='joao', status='pending')

# Campanha B: Natal (pode ter João também)
Campaign(id='uuid-B', name='Natal', instance=inst2, status='active')
CampaignContact(campaign='uuid-B', contact='joao', status='pending')

# ✅ Constraint: UNIQUE(campaign_id, contact_id)
# ✅ João pode estar em ambas
# ❌ João não pode estar 2x na mesma campanha
```

### Processamento Simultâneo

```python
@shared_task
def campaign_scheduler():
    """Processa TODAS as campanhas prontas"""
    
    ready_campaigns = Campaign.objects.filter(
        status='active',
        is_paused=False,
        next_scheduled_send__lte=NOW()
    )
    
    # LOOP: Cada campanha independente
    for campaign in ready_campaigns:
        try:
            process_single_campaign(campaign)
        except Exception as e:
            # ⭐ Erro em 1 campanha NÃO afeta outras
            logger.exception(f"Erro em {campaign.name}")
            continue  # Próxima campanha
```

### Pausar Uma Campanha

```python
# Pausar Campanha B

Campaign.objects.filter(id='uuid-B').update(is_paused=True)

# Próximo scheduler:
ready = Campaign.objects.filter(
    status='active',
    is_paused=False,  # ⭐ Campanha B não aparece
    next_scheduled_send__lte=NOW()
)
# Resultado: [Campanha A, Campanha C]
# ✅ Apenas B pausada, A e C continuam
```

### Performance com Múltiplas Campanhas

```sql
-- Índice otimizado para scheduler
CREATE INDEX idx_campaign_scheduler ON campaigns(
    status, is_paused, next_scheduled_send
);

-- Query do scheduler (10 campanhas ativas)
SELECT * FROM campaigns 
WHERE status='active' 
  AND is_paused=FALSE 
  AND next_scheduled_send <= NOW();
  
-- Execution time: ~5ms ✅ (com índice)
```

---

## 🛡️ ANTI-SPAM E PROTEÇÕES

### Problema: Mesmo Contato em Múltiplas Campanhas

```
João está em 3 campanhas ativas:
- Black Friday
- Natal
- Ano Novo

Sem proteção: Pode receber 3 mensagens ao mesmo tempo!
```

### Solução: Lock por Telefone (Redis)

```python
@shared_task
def send_message_task(self, campaign_id, contact_relation_id, ...):
    
    contact = get_contact(contact_relation_id)
    
    # ⭐ Tentar adquirir lock no número
    lock_key = f'phone_lock:{contact.phone}'
    lock_acquired = redis.set(
        lock_key,
        campaign_id,
        nx=True,  # Só seta se NÃO existir
        ex=60     # Expira em 60s
    )
    
    if not lock_acquired:
        # ⭐ Outro worker está usando este número AGORA
        logger.warning(f"Número {contact.phone} em uso, aguardando 20s")
        
        # Reagendar para 20s depois
        send_message_task.apply_async(
            kwargs={...},
            countdown=20
        )
        
        return 'deferred'
    
    # ✅ Lock adquirido, pode enviar
    try:
        send_message(contact.phone, message)
    finally:
        # ⭐ SEMPRE liberar lock
        redis.delete(lock_key)
```

### Timeline com Lock

```
T=0s
  Worker 1 (Campanha A): Tenta lock +5511999999999
    → SET phone_lock:+5511999 = "camp-A" NX
    → ✅ Sucesso! Envia mensagem
    
  Worker 2 (Campanha B): Tenta lock +5511999999999
    → SET phone_lock:+5511999 = "camp-B" NX
    → ❌ Falhou! Lock já existe
    → Reagenda para T=20s

T=3s
  Worker 1 finaliza
    → DELETE phone_lock:+5511999
    → 🔓 Lock liberado

T=20s
  Worker 2 (retry): Tenta lock novamente
    → SET phone_lock:+5511999 = "camp-B" NX
    → ✅ Sucesso! Envia mensagem

Resultado: 20 segundos entre mensagens ✅
```

### Regras de Lock

```python
# ✅ SEMPRE

# 1. Lock com TTL (expira automaticamente)
redis.set(key, value, nx=True, ex=60)  # 60s TTL

# 2. Liberar em finally
try:
    send_message()
finally:
    redis.delete(lock_key)  # Mesmo se der erro

# 3. Reagendar se bloqueado
if not lock_acquired:
    task.apply_async(countdown=20)  # Retry

# ❌ NUNCA

# 1. Lock sem TTL
redis.set(key, value, nx=True)  # ❌ Se crashar, trava forever

# 2. Não liberar lock
send_message()
# ❌ Lock nunca é liberado

# 3. Bloquear aguardando lock
while not redis.set(...):  # ❌ Trava worker
    time.sleep(1)
```

---

## 🕐 SISTEMA DE JANELAS E HORÁRIOS

### Tipos de Agendamento

```python
class Campaign(models.Model):
    class ScheduleType(models.TextChoices):
        IMMEDIATE = 'immediate', 'Imediato'
        BUSINESS_DAYS = 'business_days', 'Apenas Dias Úteis'
        BUSINESS_HOURS = 'business_hours', 'Horário Comercial'
        CUSTOM_PERIOD = 'custom_period', 'Período Personalizado'
```

### Validações Combinadas

```python
def is_allowed_to_send(campaign, current_datetime):
    """
    Valida MÚLTIPLAS condições simultaneamente:
    1. Dia da semana (útil ou não)
    2. Feriado
    3. Horário do dia
    
    TODAS as condições ativas devem passar!
    """
    hour = current_datetime.hour
    weekday = current_datetime.weekday()  # 0=seg, 6=dom
    today = current_datetime.date()
    
    # TIPO: BUSINESS_DAYS (dias úteis 9h-18h)
    if campaign.schedule_type == 'business_days':
        
        # ⭐ CONDIÇÃO 1: Dia útil
        if weekday >= 5:  # Sábado ou Domingo
            return False, "fim_de_semana"
        
        # ⭐ CONDIÇÃO 2: Não é feriado
        if Holiday.is_holiday(today):
            return False, "feriado"
        
        # ⭐ CONDIÇÃO 3: Horário comercial
        if not (9 <= hour < 18):
            return False, "fora_horario"
        
        # ✅ Todas passaram
        return True, "OK"
    
    # TIPO: CUSTOM_PERIOD (janelas personalizadas)
    if campaign.schedule_type == 'custom_period':
        
        # ⭐ CONDIÇÃO 1: Fim de semana (se configurado)
        if campaign.skip_weekends and weekday >= 5:
            return False, "fim_de_semana"
        
        # ⭐ CONDIÇÃO 2: Feriado (se configurado)
        if campaign.skip_holidays and Holiday.is_holiday(today):
            return False, "feriado"
        
        # ⭐ CONDIÇÃO 3: Janela manhã OU tarde
        current_time = current_datetime.time()
        
        in_morning = (
            campaign.morning_start <= current_time < campaign.morning_end
        )
        in_afternoon = (
            campaign.afternoon_start <= current_time < campaign.afternoon_end
        )
        
        if not (in_morning or in_afternoon):
            return False, "fora_janela"
        
        # ✅ Todas passaram
        return True, "OK"
```

### Retomada Automática

```python
def calculate_next_send_time(campaign, current_datetime):
    """
    Calcula próxima janela válida
    
    Exemplo: Sexta 18h → Segunda 9h
    """
    
    # Se pode enviar agora, apenas delay normal
    can_send, reason = is_allowed_to_send(campaign, current_datetime)
    if can_send:
        return current_datetime + timedelta(seconds=random(20, 50))
    
    # ⭐ Fora da janela, buscar próximo dia/horário válido
    
    # 1. Busca próximo dia válido
    next_day = current_datetime.date() + timedelta(days=1)
    
    for attempt in range(30):  # Máximo 30 dias
        weekday = next_day.weekday()
        
        # Pula fim de semana?
        if campaign.skip_weekends and weekday >= 5:
            next_day += timedelta(days=1)
            continue
        
        # Pula feriado?
        if campaign.skip_holidays and Holiday.is_holiday(next_day):
            next_day += timedelta(days=1)
            continue
        
        # ✅ Dia válido encontrado
        break
    
    # 2. Horário de início
    start_hour = campaign.morning_start or time(9, 0)
    
    # 3. Combina data + hora
    next_send = datetime.combine(next_day, start_hour)
    
    return make_aware(next_send)
```

### Exemplo: Sexta 17h → Segunda 9h

```
SEXTA 17:45 - Enviando normalmente
  ↓ is_allowed_to_send(sexta 17:45) → True
  ✅ Envia mensagem #450

SEXTA 18:00 - Janela fechou
  ↓ is_allowed_to_send(sexta 18:00) → False (hour >= 18)
  ↓ calculate_next_send_time(sexta 18:00)
    ├─ Busca próximo dia:
    │   Sábado → ❌ Fim de semana (pula)
    │   Domingo → ❌ Fim de semana (pula)
    │   Segunda → ✅ Dia útil
    └─ Retorna: Segunda 09:00
  ↓ UPDATE next_scheduled_send = Segunda 09:00

SÁBADO/DOMINGO - Scheduler roda mas:
  ↓ WHERE next_scheduled_send <= NOW()
  ❌ Campanha não aparece (next_send = Segunda 09:00)

SEGUNDA 09:00 - Retoma automaticamente
  ↓ WHERE next_scheduled_send <= NOW()
  ✅ Campanha aparece!
  ↓ is_allowed_to_send(segunda 09:00) → True
  ✅ Retoma do contato #451 (onde parou)
```

### Regras de Janelas

```python
# ✅ SEMPRE

# 1. Validar antes de enfileirar (scheduler)
if is_allowed_to_send(campaign, now):
    enqueue_task(...)
else:
    next_time = calculate_next_send_time(campaign, now)
    campaign.next_scheduled_send = next_time
    campaign.save()

# 2. Calcular próxima janela válida (não apenas +1 dia)
def calculate_next_send_time(...):
    # Loop até encontrar dia válido
    while True:
        if is_valid_day(next_day):
            break
        next_day += timedelta(days=1)

# 3. Sempre combinar data + hora
next_send = datetime.combine(next_day, start_hour)
next_send = make_aware(next_send)  # Timezone

# ❌ NUNCA

# 1. Apenas pausar campanha (perde estado)
if not is_allowed_to_send(...):
    campaign.is_paused = True  # ❌ Perde controle

# 2. Calcular próximo horário sem validar dia
next_send = now + timedelta(hours=15)  # ❌ Pode cair em feriado

# 3. Ignorar timezone
next_send = datetime.combine(...)  # ❌ Naive datetime
```

### Configuração de Feriados

```python
class Holiday(models.Model):
    date = models.DateField()
    name = models.CharField(max_length=200)
    is_national = models.BooleanField(default=False)
    tenant = models.ForeignKey(Tenant, null=True)  # null = nacional
    
    @classmethod
    def is_holiday(cls, date, tenant=None):
        query = Q(date=date, is_active=True)
        
        if tenant:
            # Feriados nacionais OU do tenant
            query &= (Q(tenant=tenant) | Q(is_national=True, tenant__isnull=True))
        else:
            query &= Q(is_national=True)
        
        return cls.objects.filter(query).exists()

# Seed inicial
Holiday.objects.bulk_create([
    Holiday(date='2025-01-01', name='Ano Novo', is_national=True),
    Holiday(date='2025-04-21', name='Tiradentes', is_national=True),
    Holiday(date='2025-12-25', name='Natal', is_national=True),
])
```

---

## 🎨 UI/UX GUIDELINES

### Princípios de Design

#### 1. **Feedback Imediato**

```typescript
// ❌ MAU: Sem feedback
const handleStart = async () => {
  await api.startCampaign(id);
}

// ✅ BOM: Feedback visual
const handleStart = async () => {
  setIsStarting(true);
  try {
    await api.startCampaign(id);
    toast.success('Campanha iniciada com sucesso!');
  } catch (error) {
    toast.error(error.message);
  } finally {
    setIsStarting(false);
  }
}

// ✅ MELHOR: Loading states específicos
const handleStart = async () => {
  setButtonState('starting'); // Botão mostra "Iniciando..."
  
  try {
    await api.startCampaign(id);
    setButtonState('started'); // Mostra checkmark por 2s
    setTimeout(() => setButtonState('active'), 2000);
    toast.success('Campanha iniciada!');
  } catch (error) {
    setButtonState('error'); // Mostra erro no botão
    setTimeout(() => setButtonState('idle'), 3000);
    toast.error(error.message);
  }
}
```

#### 2. **Estados Vazios Amigáveis**

```tsx
// ✅ Empty states construtivos
{campaigns.length === 0 ? (
  <EmptyState
    icon={<MegaphoneIcon />}
    title="Nenhuma campanha criada"
    description="Campanhas permitem enviar mensagens em massa para seus contatos"
    action={{
      label: "Criar Primeira Campanha",
      onClick: () => navigate('/campaigns/new')
    }}
    helpLink={{
      label: "Como funcionam as campanhas?",
      href: "/docs/campaigns"
    }}
  />
) : (
  <CampaignList campaigns={campaigns} />
)}
```

#### 3. **Validação Progressiva**

```tsx
// ✅ Validar enquanto usuário digita
const [name, setName] = useState('');
const [nameError, setNameError] = useState('');

const validateName = (value: string) => {
  if (value.length === 0) {
    setNameError('');
  } else if (value.length < 3) {
    setNameError('Nome muito curto (mínimo 3 caracteres)');
  } else if (value.length > 100) {
    setNameError('Nome muito longo (máximo 100 caracteres)');
  } else {
    setNameError('');
  }
}

<Input
  label="Nome da Campanha"
  value={name}
  onChange={(e) => {
    setName(e.target.value);
    validateName(e.target.value);
  }}
  error={nameError}
  helperText={nameError || `${name.length}/100 caracteres`}
  success={name.length >= 3 && !nameError}
/>
```

#### 4. **Preview em Tempo Real**

```tsx
// ✅ Mostrar preview de mensagens com variáveis
<MessageEditor
  value={messageText}
  onChange={setMessageText}
  variables={['nome', 'quem_indicou', 'saudacao']}
  renderPreview={(text) => (
    <MessagePreview
      text={text}
      sampleContact={{
        nome: 'João Silva',
        quem_indicou: 'Maria Santos'
      }}
      currentTime={new Date()}
    />
  )}
/>

// Resultado visual:
// Editor: "{{saudacao}}, {{nome}}! Vi que {{quem_indicou}} te indicou..."
// Preview: "Bom dia, João Silva! Vi que Maria Santos te indicou..."
```

#### 5. **Confirmações Contextuais**

```tsx
// ✅ Confirmação com contexto
<ConfirmDialog
  open={showCancelDialog}
  title="Encerrar Campanha?"
  description={`
    A campanha "${campaign.name}" será cancelada.
    ${campaign.sent_messages} de ${campaign.total_contacts} mensagens foram enviadas.
    ${campaign.total_contacts - campaign.sent_messages} contatos NÃO receberão mensagens.
  `}
  severity="warning"
  confirmText="Sim, Encerrar"
  cancelText="Continuar Campanha"
  onConfirm={handleCancel}
  onClose={() => setShowCancelDialog(false)}
/>
```

#### 6. **Loading States Específicos**

```tsx
// ❌ Loading genérico
{isLoading && <Spinner />}

// ✅ Loading específico com skeleton
{isLoading ? (
  <CampaignCardSkeleton count={3} />
) : (
  campaigns.map(c => <CampaignCard campaign={c} />)
)}

// ✅ Loading inline
<Button loading={isSaving}>
  {isSaving ? 'Salvando...' : 'Salvar Campanha'}
</Button>
```

#### 7. **Cores Semânticas Consistentes**

```css
/* tailwind.config.js - Extend colors */
colors: {
  // Estados de campanha
  campaign: {
    draft: '#9CA3AF',      // Gray
    active: '#10B981',     // Green
    paused: '#F59E0B',     // Amber
    completed: '#3B82F6',  // Blue
    cancelled: '#EF4444',  // Red
  },
  
  // Feedback
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',
  
  // Actions
  primary: '#6366F1',    // Indigo
  secondary: '#8B5CF6',  // Purple
}
```

---

### Components Pattern

```tsx
// ✅ Componente bem estruturado

interface CampaignCardProps {
  campaign: Campaign;
  onStart?: (id: string) => void;
  onPause?: (id: string) => void;
  onCancel?: (id: string) => void;
  onViewDetails?: (id: string) => void;
}

export function CampaignCard({
  campaign,
  onStart,
  onPause,
  onCancel,
  onViewDetails
}: CampaignCardProps) {
  // 1. Estados locais
  const [isActionLoading, setIsActionLoading] = useState(false);
  
  // 2. Lógica derivada
  const statusColor = {
    draft: 'bg-gray-100 text-gray-800',
    active: 'bg-green-100 text-green-800',
    paused: 'bg-amber-100 text-amber-800',
    completed: 'bg-blue-100 text-blue-800',
    cancelled: 'bg-red-100 text-red-800',
  }[campaign.status];
  
  const canStart = campaign.status === 'draft' && campaign.can_be_started;
  const canPause = campaign.status === 'active';
  const canResume = campaign.status === 'paused';
  
  // 3. Handlers
  const handleAction = async (action: () => Promise<void>) => {
    setIsActionLoading(true);
    try {
      await action();
    } finally {
      setIsActionLoading(false);
    }
  };
  
  // 4. Render
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold">{campaign.name}</h3>
            <Badge className={statusColor}>
              {campaign.status_display}
            </Badge>
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <IconButton icon={<EllipsisVerticalIcon />} />
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => onViewDetails?.(campaign.id)}>
                Ver Detalhes
              </DropdownMenuItem>
              {/* Mais opções... */}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      
      <CardContent>
        {/* Progress bar */}
        <ProgressBar 
          value={campaign.progress_percentage} 
          label={`${campaign.sent_messages} / ${campaign.total_contacts}`}
        />
        
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mt-4">
          <Stat 
            label="Enviadas" 
            value={campaign.sent_messages}
            icon={<CheckIcon className="text-green-500" />}
          />
          <Stat 
            label="Respondidas" 
            value={campaign.responded_count}
            subtitle={`${campaign.response_rate}%`}
            icon={<ChatBubbleIcon className="text-blue-500" />}
          />
          <Stat 
            label="Falhas" 
            value={campaign.failed_messages}
            icon={<XMarkIcon className="text-red-500" />}
          />
        </div>
      </CardContent>
      
      <CardFooter>
        <div className="flex gap-2 w-full">
          {canStart && (
            <Button 
              onClick={() => handleAction(() => onStart!(campaign.id))}
              loading={isActionLoading}
              className="flex-1"
            >
              <PlayIcon className="w-4 h-4 mr-2" />
              Iniciar
            </Button>
          )}
          
          {canPause && (
            <Button
              variant="warning"
              onClick={() => handleAction(() => onPause!(campaign.id))}
              loading={isActionLoading}
            >
              <PauseIcon className="w-4 h-4 mr-2" />
              Pausar
            </Button>
          )}
          
          {canResume && (
            <Button
              variant="success"
              onClick={() => handleAction(() => onStart!(campaign.id))}
              loading={isActionLoading}
              className="flex-1"
            >
              <PlayIcon className="w-4 h-4 mr-2" />
              Retomar
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
```

---

## 🧪 TESTES

### Testes de Models

```python
# tests/test_models.py

class CampaignModelTest(TestCase):
    
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.instance = EvolutionInstance.objects.create(
            tenant=self.tenant,
            name="Test Instance",
            is_connected=True
        )
        self.campaign = Campaign.objects.create(
            tenant=self.tenant,
            name="Test Campaign",
            instance=self.instance
        )
    
    def test_campaign_creation(self):
        """Testa criação de campanha"""
        self.assertEqual(self.campaign.status, Campaign.Status.DRAFT)
        self.assertEqual(self.campaign.sent_messages, 0)
        self.assertIsNotNone(self.campaign.id)
    
    def test_progress_percentage(self):
        """Testa cálculo de progresso"""
        self.campaign.total_contacts = 100
        self.campaign.sent_messages = 50
        self.assertEqual(self.campaign.progress_percentage, 50.0)
    
    def test_can_be_started_requires_contacts(self):
        """Campanha não pode iniciar sem contatos"""
        self.assertFalse(self.campaign.can_be_started)
        
        # Adicionar contatos
        contact = Contact.objects.create(
            tenant=self.tenant,
            name="Test",
            phone="5511999999999"
        )
        CampaignContact.objects.create(
            campaign=self.campaign,
            contact=contact
        )
        self.campaign.total_contacts = 1
        
        # Ainda falta mensagem
        self.assertFalse(self.campaign.can_be_started)
        
        # Adicionar mensagem
        CampaignMessage.objects.create(
            campaign=self.campaign,
            message_text="Test message"
        )
        
        # Agora pode iniciar
        self.assertTrue(self.campaign.can_be_started)
    
    def test_unique_active_campaign_per_instance(self):
        """Só pode ter 1 campanha ativa por instância"""
        self.campaign.status = Campaign.Status.ACTIVE
        self.campaign.save()
        
        # Tentar criar outra campanha ativa na mesma instância
        with self.assertRaises(IntegrityError):
            Campaign.objects.create(
                tenant=self.tenant,
                name="Another Campaign",
                instance=self.instance,
                status=Campaign.Status.ACTIVE
            )
```

### Testes de API

```python
# tests/test_views.py

class CampaignAPITest(APITestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.user.tenant = self.tenant
        self.user.save()
        
        self.client.force_authenticate(user=self.user)
    
    def test_list_campaigns(self):
        """Testa listagem de campanhas"""
        Campaign.objects.create(
            tenant=self.tenant,
            name="Campaign 1",
            instance=self.instance
        )
        
        response = self.client.get('/api/campaigns/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Campaign 1")
    
    def test_create_campaign(self):
        """Testa criação de campanha"""
        data = {
            'name': 'New Campaign',
            'instance_id': str(self.instance.id),
            'contact_ids': [str(self.contact.id)]
        }
        
        response = self.client.post('/api/campaigns/', data, format='json')
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Campaign.objects.count(), 1)
    
    def test_start_campaign_validation(self):
        """Testa que campanha sem mensagens não pode iniciar"""
        campaign = Campaign.objects.create(
            tenant=self.tenant,
            name="Test",
            instance=self.instance,
            total_contacts=1
        )
        
        response = self.client.post(f'/api/campaigns/{campaign.id}/start/')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
```

---

## 📊 PERFORMANCE

### Database Optimization

```python
# ✅ Sempre usar select_related para ForeignKey
campaigns = Campaign.objects.select_related('instance', 'tenant').all()

# ✅ Sempre usar prefetch_related para ManyToMany e reverse ForeignKey
campaigns = Campaign.objects.prefetch_related('messages', 'contacts').all()

# ✅ Usar only() quando só precisa de alguns campos
campaigns = Campaign.objects.only('id', 'name', 'status').all()

# ✅ Usar defer() para excluir campos pesados
campaigns = Campaign.objects.defer('metadata').all()

# ✅ Usar annotate para cálculos no banco
from django.db.models import Count, Avg

campaigns = Campaign.objects.annotate(
    message_count=Count('messages'),
    avg_response_time=Avg('campaign_contacts__response_time')
)

# ✅ Usar bulk_create para inserções em massa
contacts_to_create = [
    CampaignContact(campaign=campaign, contact=c)
    for c in contacts
]
CampaignContact.objects.bulk_create(contacts_to_create, batch_size=1000)

# ✅ Usar update() para atualizações em massa (evita signals)
Campaign.objects.filter(status='draft', created_at__lt=old_date).update(
    status='cancelled'
)

# ✅ Usar F() expressions para operações atômicas
from django.db.models import F
Campaign.objects.filter(id=campaign_id).update(
    sent_messages=F('sent_messages') + 1
)
```

### Caching Strategy

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'alrea',
        'TIMEOUT': 300,  # 5 minutos default
    }
}

# Uso em views
from django.core.cache import cache
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)  # Cache por 5 minutos
def campaign_stats(request):
    # ...

# Uso manual
def get_tenant_campaign_limit(tenant_id):
    cache_key = f'tenant:{tenant_id}:campaign_limit'
    limit = cache.get(cache_key)
    
    if limit is None:
        tenant = Tenant.objects.get(id=tenant_id)
        limit = tenant.plan.max_campaigns
        cache.set(cache_key, limit, timeout=3600)  # 1 hora
    
    return limit

# Invalidar cache quando necessário
def update_tenant_plan(tenant_id, new_plan):
    # ... atualizar plano ...
    cache.delete(f'tenant:{tenant_id}:campaign_limit')
```

---

## 🔒 SEGURANÇA

### Multi-tenant Isolation

```python
# middleware.py - Sempre injetar tenant no request

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            request.tenant = request.user.tenant
        return self.get_response(request)

# permissions.py - Sempre validar tenant

class IsTenantOwner(permissions.BasePermission):
    """Permite acesso apenas a objetos do próprio tenant"""
    
    def has_object_permission(self, request, view, obj):
        return obj.tenant == request.tenant

# views.py - Sempre filtrar por tenant

class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsTenantOwner]
    
    def get_queryset(self):
        # SEMPRE filtrar por tenant
        return Campaign.objects.filter(tenant=self.request.tenant)
    
    def perform_create(self, serializer):
        # SEMPRE injetar tenant na criação
        serializer.save(tenant=self.request.tenant, created_by=self.request.user)
```

### Input Validation

```python
# validators.py

from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Número de telefone deve estar no formato: '+999999999'. Até 15 dígitos permitidos."
)

# Sanitização de dados
import bleach

def sanitize_html(text):
    """Remove HTML perigoso de texto"""
    allowed_tags = ['b', 'i', 'u', 'em', 'strong']
    return bleach.clean(text, tags=allowed_tags, strip=True)
```

---

## 📝 LOGGING E MONITORING

```python
# settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'json',
        },
    },
    'loggers': {
        'campaigns': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Uso nos arquivos

import logging
logger = logging.getLogger('campaigns')

logger.info(
    "Campaign started",
    extra={
        'campaign_id': str(campaign.id),
        'tenant_id': str(tenant.id),
        'user_id': str(user.id),
        'total_contacts': campaign.total_contacts
    }
)
```

---

## ✅ CHECKLIST DE CODE REVIEW

Antes de fazer Pull Request, verifique:

### Models
- [ ] UUID como PK
- [ ] tenant_id em todos os models de negócio
- [ ] Timestamps (created_at, updated_at)
- [ ] Choices para campos com valores finitos
- [ ] Help text descritivo
- [ ] Validators no model
- [ ] Properties para lógica derivada
- [ ] __str__ útil
- [ ] Meta com ordering e constraints
- [ ] Indexes nos campos de busca

### Views/Serializers
- [ ] Permissões configuradas
- [ ] Queryset filtra por tenant
- [ ] select_related / prefetch_related
- [ ] Validações customizadas
- [ ] Tratamento de erros
- [ ] Logging de ações importantes

### Frontend
- [ ] Loading states
- [ ] Error handling
- [ ] Empty states
- [ ] Feedback visual
- [ ] Validação de formulários
- [ ] TypeScript sem `any`
- [ ] Componentes reutilizáveis
- [ ] Acessibilidade (ARIA labels)

### Testes
- [ ] Testes de models
- [ ] Testes de API
- [ ] Testes de tasks
- [ ] Cobertura > 80%

### Segurança
- [ ] Input sanitization
- [ ] Multi-tenant isolation
- [ ] Rate limiting em endpoints críticos
- [ ] CORS configurado corretamente

### Performance
- [ ] N+1 queries resolvidos
- [ ] Indexes criados
- [ ] Cache onde apropriado
- [ ] Paginação implementada

---

**Última Atualização:** 2025-10-08  
**Versão:** 1.0.0  
**Mantenedor:** ALREA Development Team

