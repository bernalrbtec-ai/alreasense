# 🛡️ **REVISÃO FINAL - PREVENÇÃO DE ERROS E MELHORIAS**

> **Revisão Final Completa - Prevenção de Erros e Edge Cases**  
> **Data:** Janeiro 2025  
> **Status:** ✅ **REVISÃO FINAL COMPLETA**

---

## 🎯 **OBJETIVO**

Identificar e prevenir **todos os possíveis erros, edge cases e situações problemáticas** antes da implementação, garantindo um sistema robusto e resiliente.

---

## 🚨 **EDGE CASES E SITUAÇÕES PROBLEMÁTICAS**

### **1. DUPLICAÇÃO DE CICLOS**

#### **Problema:**
Cliente envia mesmo `external_billing_id` duas vezes (retry, erro de rede, etc).

#### **Cenário:**
```json
// Request 1 (10:00)
POST /billing/v1/billing/send/batch
{
  "contacts": [{
    "external_billing_id": "BILL-001",
    ...
  }]
}

// Request 2 (10:01) - Duplicado por erro
POST /billing/v1/billing/send/batch
{
  "contacts": [{
    "external_billing_id": "BILL-001",  // MESMO ID!
    ...
  }]
}
```

#### **Solução:**
```python
from django.db import IntegrityError, transaction

@transaction.atomic
def create_billing_cycle(tenant, external_id, **data):
    """
    Cria ciclo com proteção contra duplicação.
    """
    try:
        # Tentar criar
        cycle = BillingCycle.objects.create(
            tenant=tenant,
            external_billing_id=external_id,
            **data
        )
        return cycle, True  # (cycle, created)
    
    except IntegrityError:
        # Já existe - buscar existente
        existing = BillingCycle.objects.get(
            tenant=tenant,
            external_billing_id=external_id
        )
        
        # Se está ativo, retornar erro
        if existing.status == 'active':
            raise ValueError(
                f"Ciclo {external_id} já existe e está ativo. "
                f"Use endpoint de cancelamento se necessário."
            )
        
        # Se foi cancelado/completado, permitir recriar?
        # OU retornar erro informando que já existe
        raise ValueError(
            f"Ciclo {external_id} já existe com status '{existing.status}'. "
            f"ID do ciclo: {existing.id}"
        )
```

#### **Validação no Serializer:**
```python
def validate_contacts(self, contacts):
    """Valida duplicatas no batch"""
    external_ids = [c.get('external_billing_id') for c in contacts]
    
    # Verificar duplicatas no próprio batch
    if len(external_ids) != len(set(external_ids)):
        duplicates = [id for id in external_ids if external_ids.count(id) > 1]
        raise serializers.ValidationError(
            f"external_billing_id duplicados no batch: {set(duplicates)}"
        )
    
    # Verificar duplicatas no banco (opcional - pode ser feito no service)
    tenant = self.context['request'].tenant
    existing_ids = set(
        BillingCycle.objects.filter(
            tenant=tenant,
            external_billing_id__in=external_ids,
            status='active'
        ).values_list('external_billing_id', flat=True)
    )
    
    if existing_ids:
        raise serializers.ValidationError(
            f"external_billing_id já existem e estão ativos: {existing_ids}"
        )
    
    return contacts
```

---

### **2. RACE CONDITION NO SCHEDULER**

#### **Problema:**
Dois schedulers executando simultaneamente podem processar a mesma mensagem.

#### **Cenário:**
```
Scheduler 1: Busca mensagens pendentes (10:00:00)
Scheduler 2: Busca mensagens pendentes (10:00:01) - MESMAS mensagens!
Scheduler 1: Marca como 'sending' e envia (10:00:02)
Scheduler 2: Marca como 'sending' e envia (10:00:03) - DUPLICADO!
```

#### **Solução - Lock Pessimista:**
```python
from django.db import transaction
from django.db.models import F, Q

def process_pending_messages(tenant):
    """
    Processa mensagens com lock para evitar race condition.
    """
    today = timezone.now().date()
    
    # Usar select_for_update para lock pessimista
    pending_messages = BillingContact.objects.filter(
        scheduled_date__lte=today,
        status='pending',
        billing_cycle__status='active',
        billing_cycle__tenant=tenant
    ).select_for_update(skip_locked=True).select_related(
        'billing_cycle', 'template_variation'
    ).order_by('scheduled_date', 'cycle_index')[:100]  # Limitar batch
    
    for message in pending_messages:
        try:
            with transaction.atomic():
                # Tentar atualizar status (falha se já foi atualizado)
                updated = BillingContact.objects.filter(
                    id=message.id,
                    status='pending'  # Só atualiza se ainda está pending
                ).update(status='sending')
                
                if not updated:
                    # Já foi processado por outro scheduler
                    logger.info(f"⏭️ Mensagem {message.id} já processada, pulando")
                    continue
                
                # Processar mensagem
                send_cycle_message(message)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem {message.id}: {e}")
            # Marcar como failed após retries
            message.status = 'failed'
            message.save(update_fields=['status', 'updated_at'])
```

#### **Solução Alternativa - Lock Otimista:**
```python
def process_pending_messages_optimistic(tenant):
    """
    Usa version field para lock otimista.
    """
    # Adicionar campo 'version' em BillingContact
    pending_messages = BillingContact.objects.filter(...)
    
    for message in pending_messages:
        current_version = message.version
        
        # Tentar atualizar com verificação de versão
        updated = BillingContact.objects.filter(
            id=message.id,
            status='pending',
            version=current_version  # Só atualiza se versão não mudou
        ).update(
            status='sending',
            version=F('version') + 1
        )
        
        if not updated:
            # Versão mudou - outro processo já processou
            continue
        
        # Processar...
```

---

### **3. DATAS INVÁLIDAS OU INCONSISTENTES**

#### **Problema:**
- `due_date` no passado muito distante
- `due_date` no futuro muito distante
- `due_date` igual a hoje (border case)
- Timezone inconsistente

#### **Solução:**
```python
from django.core.exceptions import ValidationError
from datetime import date, timedelta

def validate_due_date(due_date: date, tenant: Tenant) -> date:
    """
    Valida e normaliza data de vencimento.
    """
    today = timezone.now().date()
    max_future = today + timedelta(days=365)  # 1 ano no futuro
    max_past = today - timedelta(days=365)    # 1 ano no passado
    
    # Validar range
    if due_date > max_future:
        raise ValidationError(
            f"Data de vencimento muito no futuro: {due_date}. "
            f"Máximo permitido: {max_future}"
        )
    
    if due_date < max_past:
        raise ValidationError(
            f"Data de vencimento muito no passado: {due_date}. "
            f"Mínimo permitido: {max_past}"
        )
    
    return due_date

def calculate_scheduled_dates_safe(due_date: date, tenant: Tenant):
    """
    Calcula datas agendadas com validações.
    """
    # Validar due_date primeiro
    due_date = validate_due_date(due_date, tenant)
    
    today = timezone.now().date()
    
    # Se due_date = hoje, tratar como "vencido hoje"
    if due_date == today:
        # Não criar mensagens "a vencer" (já venceu)
        # Criar apenas mensagens "vencido" (1d, 3d, 5d depois)
        pass
    
    # Calcular datas com proteção
    dates = []
    
    # Upcoming: 5d, 3d, 1d antes
    for days in [5, 3, 1]:
        raw_date = due_date - timedelta(days=days)
        
        # Se data calculada já passou, não criar
        if raw_date < today:
            logger.warning(
                f"Data agendada {raw_date} já passou para vencimento {due_date}. "
                f"Pulando mensagem upcoming_{days}d"
            )
            continue
        
        # Recalcular para dia útil
        scheduled_date = get_last_business_day_before(raw_date, tenant)
        dates.append(('upcoming', days, scheduled_date))
    
    # Overdue: 1d, 3d, 5d depois (só se já venceu)
    if due_date < today:
        for days in [1, 3, 5]:
            raw_date = due_date + timedelta(days=days)
            scheduled_date = get_next_business_day_after(raw_date, tenant)
            dates.append(('overdue', days, scheduled_date))
    
    return dates
```

---

### **4. TELEFONE INVÁLIDO OU NORMALIZAÇÃO FALHA**

#### **Problema:**
- Telefone vazio ou None
- Telefone com formato inválido
- `normalize_phone` retorna None ou erro
- Telefone muito curto/longo

#### **Solução:**
```python
from apps.common.utils.phone import normalize_phone
from django.core.exceptions import ValidationError

def validate_and_normalize_phone(phone: str, tenant: Tenant) -> str:
    """
    Valida e normaliza telefone com tratamento de erros.
    """
    if not phone:
        raise ValidationError("Telefone não pode ser vazio")
    
    if not isinstance(phone, str):
        raise ValidationError(f"Telefone deve ser string, recebido: {type(phone)}")
    
    # Normalizar
    try:
        normalized = normalize_phone(phone)
    except Exception as e:
        raise ValidationError(f"Erro ao normalizar telefone '{phone}': {e}")
    
    if not normalized:
        raise ValidationError(f"Telefone '{phone}' não pôde ser normalizado")
    
    # Validar comprimento (exemplo: mínimo 10, máximo 15)
    if len(normalized) < 10:
        raise ValidationError(
            f"Telefone '{normalized}' muito curto (mínimo 10 dígitos)"
        )
    
    if len(normalized) > 15:
        raise ValidationError(
            f"Telefone '{normalized}' muito longo (máximo 15 dígitos)"
        )
    
    return normalized
```

---

### **5. TEMPLATE NÃO ENCONTRADO OU SEM VARIAÇÕES**

#### **Problema:**
- Template não existe para o tenant
- Template existe mas está inativo
- Template não tem variações ativas
- Template específico não existe (fallback para genérico também falha)

#### **Solução:**
```python
def select_template_safe(
    tenant: Tenant,
    cycle_message_type: str,
    template_type: str
) -> BillingTemplate:
    """
    Seleciona template com fallbacks e validações.
    """
    # 1. Tentar template específico
    specific_template = BillingTemplate.objects.filter(
        tenant=tenant,
        template_type=template_type,
        template_scope='specific',
        specific_day=cycle_message_type,
        is_active=True
    ).first()
    
    if specific_template:
        # Validar que tem variações
        if not specific_template.variations.filter(is_active=True).exists():
            logger.warning(
                f"Template específico {specific_template.id} não tem variações ativas. "
                f"Usando fallback genérico."
            )
        else:
            return specific_template
    
    # 2. Fallback: template genérico
    generic_template = BillingTemplate.objects.filter(
        tenant=tenant,
        template_type=template_type,
        template_scope='generic',
        is_active=True
    ).first()
    
    if generic_template:
        if not generic_template.variations.filter(is_active=True).exists():
            raise ValueError(
                f"Template genérico {generic_template.id} não tem variações ativas"
            )
        return generic_template
    
    # 3. Erro: nenhum template encontrado
    raise ValueError(
        f"Nenhum template {template_type} encontrado para tenant {tenant.id}. "
        f"Configure templates antes de criar ciclos."
    )
```

---

### **6. CONTATO JÁ EXISTE MAS COM DADOS DIFERENTES**

#### **Problema:**
- Contato existe mas nome mudou
- Contato existe mas telefone mudou (mesmo número normalizado)
- Contato existe mas está `opted_out`
- Contato existe mas está inativo

#### **Solução:**
```python
def create_or_update_billing_contact_safe(
    tenant: Tenant,
    nome: str,
    telefone: str
) -> Contact:
    """
    Cria ou atualiza contato com validações.
    """
    # Normalizar telefone
    normalized_phone = validate_and_normalize_phone(telefone, tenant)
    
    # Buscar contato existente
    contact = Contact.objects.filter(
        tenant=tenant,
        phone=normalized_phone
    ).first()
    
    if contact:
        # Verificar se está opted_out
        if contact.opted_out:
            logger.warning(
                f"Contato {contact.id} está opted_out. "
                f"Permitindo criação de ciclo mas não enviará mensagens."
            )
            # OU: raise ValidationError("Contato optou por não receber mensagens")
        
        # Verificar se está inativo
        if not contact.is_active:
            logger.warning(
                f"Contato {contact.id} está inativo. "
                f"Ativando para permitir envio."
            )
            contact.is_active = True
            contact.save(update_fields=['is_active', 'updated_at'])
        
        # Atualizar nome se mudou
        if contact.name != nome:
            logger.info(
                f"Atualizando nome do contato {contact.id}: "
                f"'{contact.name}' → '{nome}'"
            )
            contact.name = nome
            contact.save(update_fields=['name', 'updated_at'])
        
        return contact
    
    # Criar novo contato
    contact = Contact.objects.create(
        tenant=tenant,
        name=nome,
        phone=normalized_phone,
        source='billing_api',
        is_active=True
    )
    
    # Garantir TAG "COBRANÇA"
    tag, _ = Tag.objects.get_or_create(
        tenant=tenant,
        name='COBRANÇA',
        defaults={'color': '#FF0000'}
    )
    contact.tags.add(tag)
    
    return contact
```

---

### **7. SCHEDULER FALHA NO MEIO DO PROCESSAMENTO**

#### **Problema:**
- Scheduler crasha no meio do batch
- Algumas mensagens foram enviadas, outras não
- Mensagens ficam em status 'sending' indefinidamente

#### **Solução:**
```python
def process_pending_messages_with_recovery(tenant):
    """
    Processa mensagens com recuperação de falhas.
    """
    # 1. Primeiro, recuperar mensagens "presas" em 'sending'
    stuck_messages = BillingContact.objects.filter(
        billing_cycle__tenant=tenant,
        status='sending',
        updated_at__lt=timezone.now() - timedelta(hours=1)  # Presas há mais de 1h
    )
    
    for message in stuck_messages:
        logger.warning(
            f"🔄 Recuperando mensagem presa {message.id} "
            f"(última atualização: {message.updated_at})"
        )
        # Verificar se realmente foi enviada (consultar Evolution API?)
        # OU: assumir que não foi enviada e retentar
        message.status = 'pending'
        message.retry_count += 1
        message.save(update_fields=['status', 'retry_count', 'updated_at'])
    
    # 2. Processar mensagens pendentes normalmente
    process_pending_messages(tenant)
```

---

### **8. CANCELAMENTO DE CICLO JÁ COMPLETADO**

#### **Problema:**
- Cliente tenta cancelar ciclo que já foi completado
- Cliente tenta cancelar ciclo que já foi cancelado
- Race condition: ciclo é completado enquanto está sendo cancelado

#### **Solução:**
```python
@transaction.atomic
def cancel_cycle_safe(
    cycle: BillingCycle,
    reason: str,
    force: bool = False
) -> dict:
    """
    Cancela ciclo com validações e tratamento de edge cases.
    """
    # Validar reason
    valid_reasons = ['cancelled', 'paid', 'refunded']
    if reason not in valid_reasons:
        raise ValueError(f"Reason inválido: {reason}. Válidos: {valid_reasons}")
    
    # Verificar status atual
    if cycle.status == 'completed':
        if not force:
            raise ValueError(
                f"Ciclo {cycle.id} já foi completado. "
                f"Use force=True para cancelar mesmo assim."
            )
        logger.warning(
            f"⚠️ Cancelando ciclo {cycle.id} que já foi completado (force=True)"
        )
    
    if cycle.status in ['cancelled', 'paid']:
        if cycle.status == reason:
            # Já está no status desejado
            return {
                'success': True,
                'message': f"Ciclo já está {reason}",
                'cancelled_count': 0
            }
        else:
            raise ValueError(
                f"Ciclo {cycle.id} já está {cycle.status}, "
                f"não pode ser alterado para {reason}"
            )
    
    # Lock pessimista para evitar race condition
    cycle = BillingCycle.objects.select_for_update().get(id=cycle.id)
    
    # Verificar novamente status (pode ter mudado durante lock)
    if cycle.status not in ['active', 'completed']:
        raise ValueError(f"Ciclo {cycle.id} não está ativo (status: {cycle.status})")
    
    # Cancelar
    cycle.status = reason
    cycle.cancelled_at = timezone.now()
    
    # Cancelar apenas mensagens pendentes
    pending_messages = cycle.billing_contacts.filter(status='pending')
    cancelled_count = pending_messages.update(
        status='cancelled',
        billing_status=reason
    )
    
    # Atualizar contadores
    cycle.sent_messages = cycle.billing_contacts.filter(status='sent').count()
    cycle.failed_messages = cycle.billing_contacts.filter(status='failed').count()
    cycle.total_messages = cycle.billing_contacts.count()
    
    cycle.save()
    
    return {
        'success': True,
        'message': f"Ciclo cancelado: {cancelled_count} mensagens pendentes canceladas",
        'cancelled_count': cancelled_count
    }
```

---

### **9. BATCH MUITO GRANDE OU TIMEOUT**

#### **Problema:**
- Cliente envia batch com 10.000 cobranças
- Processamento demora muito e timeout
- Algumas cobranças são processadas, outras não

#### **Solução:**
```python
# 1. Validação no Serializer
MAX_BATCH_SIZE = 1000

def validate_contacts(self, contacts):
    if len(contacts) > MAX_BATCH_SIZE:
        raise serializers.ValidationError(
            f"Batch muito grande: {len(contacts)} > {MAX_BATCH_SIZE}. "
            f"Envie em lotes menores."
        )
    return contacts

# 2. Processamento Assíncrono
@transaction.atomic
def create_billing_cycles_batch(tenant, contacts_data):
    """
    Cria ciclos em batch com processamento em chunks.
    """
    created = []
    errors = []
    
    # Processar em chunks de 100
    chunk_size = 100
    for i in range(0, len(contacts_data), chunk_size):
        chunk = contacts_data[i:i + chunk_size]
        
        for contact_data in chunk:
            try:
                cycle = create_billing_cycle(tenant, **contact_data)
                created.append(cycle.id)
            except Exception as e:
                errors.append({
                    'external_billing_id': contact_data.get('external_billing_id'),
                    'error': str(e)
                })
        
        # Commit parcial a cada chunk
        transaction.commit()
    
    return {
        'created': len(created),
        'errors': len(errors),
        'created_ids': created,
        'error_details': errors
    }
```

---

### **10. BUSINESS HOURS NÃO CONFIGURADO**

#### **Problema:**
- Tenant não tem `BusinessHours` configurado
- `BusinessHoursService.is_business_hours()` retorna None ou erro
- Scheduler não sabe se pode enviar

#### **Solução:**
```python
def is_business_hours_safe(tenant: Tenant, check_time: datetime = None) -> tuple[bool, Optional[str]]:
    """
    Verifica horário comercial com fallback seguro.
    """
    try:
        is_open, next_open = BusinessHoursService.is_business_hours(tenant, None, check_time)
        
        # Se retornou None (não configurado), assumir sempre aberto
        if is_open is None:
            logger.warning(
                f"⚠️ BusinessHours não configurado para tenant {tenant.id}. "
                f"Assumindo sempre aberto."
            )
            return True, None
        
        return is_open, next_open
    
    except Exception as e:
        logger.error(
            f"❌ Erro ao verificar BusinessHours para tenant {tenant.id}: {e}"
        )
        # Em caso de erro, assumir sempre aberto (fail open)
        return True, None
```

---

### **11. EVOLUTION API OFFLINE OU INSTÂNCIA INATIVA**

#### **Problema:**
- Evolution API está offline
- Instância está desconectada
- Health check falha
- Mensagens ficam presas

#### **Solução:**
```python
def send_cycle_message_with_retry(message: BillingContact, max_retries: int = 3):
    """
    Envia mensagem com retry e tratamento de falhas de instância.
    """
    # 1. Verificar se instância está disponível
    instance = select_instance_for_tenant(message.billing_cycle.tenant)
    
    if not instance:
        logger.warning(
            f"⚠️ Nenhuma instância disponível para tenant {message.billing_cycle.tenant.id}. "
            f"Mensagem {message.id} será retentada mais tarde."
        )
        # Marcar para retry (não incrementar retry_count ainda)
        message.status = 'pending'
        message.save(update_fields=['status', 'updated_at'])
        return False
    
    # 2. Health check
    if instance.connection_state != 'open':
        logger.warning(
            f"⚠️ Instância {instance.id} não está conectada. "
            f"Mensagem {message.id} será retentada."
        )
        message.status = 'pending'
        message.save(update_fields=['status', 'updated_at'])
        return False
    
    # 3. Tentar enviar
    try:
        result = send_message_via_evolution_api(message, instance)
        
        if result['success']:
            message.status = 'sent'
            message.sent_at = timezone.now()
            message.save(update_fields=['status', 'sent_at', 'updated_at'])
            return True
        else:
            # Falha no envio
            raise Exception(result.get('error', 'Erro desconhecido'))
    
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem {message.id}: {e}")
        
        # Incrementar retry
        message.retry_count += 1
        message.last_retry_at = timezone.now()
        
        if message.retry_count >= max_retries:
            # Esgotou tentativas
            message.status = 'failed'
            logger.error(
                f"❌ Mensagem {message.id} falhou após {max_retries} tentativas"
            )
        else:
            # Retentar mais tarde
            message.status = 'pending'
            logger.info(
                f"🔄 Mensagem {message.id} será retentada "
                f"(tentativa {message.retry_count}/{max_retries})"
            )
        
        message.save(update_fields=['status', 'retry_count', 'last_retry_at', 'updated_at'])
        return False
```

---

### **12. CÁLCULO DE DATAS RESULTA EM DATAS PASSADAS**

#### **Problema:**
- Cobrança já vencida há muito tempo
- Datas "a vencer" calculadas já passaram
- Mensagens nunca serão enviadas

#### **Solução:**
```python
def calculate_scheduled_dates_with_validation(
    due_date: date,
    tenant: Tenant,
    notify_before_due: bool,
    notify_after_due: bool
) -> List[Tuple[str, int, date]]:
    """
    Calcula datas agendadas validando se ainda fazem sentido.
    """
    today = timezone.now().date()
    dates = []
    
    # Upcoming: só criar se ainda faz sentido
    if notify_before_due:
        for days in [5, 3, 1]:
            raw_date = due_date - timedelta(days=days)
            
            # Se data já passou, não criar
            if raw_date < today:
                logger.info(
                    f"⏭️ Pulando mensagem upcoming_{days}d: "
                    f"data {raw_date} já passou (vencimento: {due_date})"
                )
                continue
            
            scheduled_date = get_last_business_day_before(raw_date, tenant)
            
            # Validar que scheduled_date não é no passado
            if scheduled_date < today:
                logger.warning(
                    f"⚠️ Data agendada {scheduled_date} está no passado. "
                    f"Usando hoje como fallback."
                )
                scheduled_date = today
            
            dates.append(('upcoming', days, scheduled_date))
    
    # Overdue: só criar se já venceu
    if notify_after_due and due_date < today:
        for days in [1, 3, 5]:
            raw_date = due_date + timedelta(days=days)
            scheduled_date = get_next_business_day_after(raw_date, tenant)
            
            # Se scheduled_date é hoje ou passado, enviar hoje
            if scheduled_date <= today:
                scheduled_date = today
            
            dates.append(('overdue', days, scheduled_date))
    
    return dates
```

---

## 🔒 **VALIDAÇÕES E SEGURANÇA**

### **1. Validação de Tenant**
```python
def validate_tenant_access(tenant: Tenant, api_key: BillingAPIKey):
    """Valida se API key pertence ao tenant"""
    if api_key.tenant != tenant:
        raise PermissionDenied("API Key não pertence a este tenant")
```

### **2. Rate Limiting por Tenant**
```python
from django.core.cache import cache

def check_rate_limit(tenant: Tenant, api_key: BillingAPIKey):
    """Verifica rate limit"""
    cache_key = f"billing_rate_limit:{tenant.id}:{api_key.id}"
    requests = cache.get(cache_key, 0)
    
    limit = api_key.rate_limit_per_hour or 1000
    
    if requests >= limit:
        raise Throttled(f"Rate limit excedido: {limit} requisições/hora")
    
    cache.set(cache_key, requests + 1, 3600)  # 1 hora
```

### **3. Validação de Dados de Entrada**
```python
def validate_billing_data(data: dict) -> dict:
    """Valida e sanitiza dados de cobrança"""
    # Validar campos obrigatórios
    required = ['external_billing_id', 'nome', 'telefone', 'data_vencimento']
    for field in required:
        if field not in data:
            raise ValidationError(f"Campo obrigatório faltando: {field}")
    
    # Validar tipos
    if not isinstance(data.get('valor'), (str, int, float)):
        raise ValidationError("Campo 'valor' deve ser número")
    
    # Sanitizar strings
    if 'nome' in data:
        data['nome'] = data['nome'].strip()[:255]  # Limitar tamanho
    
    return data
```

---

## 📊 **MONITORAMENTO E ALERTAS**

### **1. Métricas a Monitorar**
```python
# Métricas importantes
- Ciclos criados por hora
- Mensagens enviadas/falhadas
- Taxa de erro no scheduler
- Tempo médio de processamento
- Mensagens presas em 'sending'
- Ciclos duplicados detectados
- Rate limit hits
- Evolution API downtime
```

### **2. Alertas Críticos**
```python
def check_critical_alerts():
    """Verifica condições críticas e envia alertas"""
    alerts = []
    
    # Mensagens presas há mais de 2 horas
    stuck_count = BillingContact.objects.filter(
        status='sending',
        updated_at__lt=timezone.now() - timedelta(hours=2)
    ).count()
    
    if stuck_count > 0:
        alerts.append({
            'level': 'warning',
            'message': f"{stuck_count} mensagens presas em 'sending'",
            'action': 'Verificar scheduler e Evolution API'
        })
    
    # Taxa de erro alta (>10%)
    total = BillingContact.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    failed = BillingContact.objects.filter(
        status='failed',
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    if total > 0 and (failed / total) > 0.1:
        alerts.append({
            'level': 'error',
            'message': f"Taxa de erro alta: {failed}/{total} ({failed/total*100:.1f}%)",
            'action': 'Verificar Evolution API e templates'
        })
    
    return alerts
```

---

## ✅ **CHECKLIST FINAL DE IMPLEMENTAÇÃO**

### **Validações:**
- [ ] Validação de duplicatas (external_billing_id)
- [ ] Validação de telefone e normalização
- [ ] Validação de datas (range, formato)
- [ ] Validação de templates (existência, variações)
- [ ] Validação de tenant e API key
- [ ] Rate limiting implementado

### **Tratamento de Erros:**
- [ ] Try/except em todas as operações críticas
- [ ] Logging estruturado de erros
- [ ] Retry com backoff exponencial
- [ ] Fallbacks para casos de falha
- [ ] Recuperação de mensagens presas

### **Concorrência:**
- [ ] Lock pessimista ou otimista no scheduler
- [ ] Transações atômicas
- [ ] Validação de status antes de atualizar
- [ ] Skip locked para evitar deadlocks

### **Performance:**
- [ ] Batch processing em chunks
- [ ] Índices de banco otimizados
- [ ] Select_related/prefetch_related
- [ ] Cache para queries frequentes
- [ ] Limite de batch size

### **Monitoramento:**
- [ ] Métricas de sucesso/falha
- [ ] Alertas para condições críticas
- [ ] Logs estruturados
- [ ] Dashboard de status

---

**Status:** ✅ **REVISÃO FINAL COMPLETA - PRONTO PARA IMPLEMENTAÇÃO SEGURA**

