# 🔍 **REVISÃO E MELHORIAS - CICLO DE MENSAGENS**

> **Revisão Completa da Proposta Arquitetural**  
> **Data:** Janeiro 2025  
> **Status:** ✅ **REVISADO COM MELHORIAS**

---

## 📋 **INCONSISTÊNCIAS IDENTIFICADAS E CORRIGIDAS**

### **1. Status do Documento Principal** ❌→✅
**Problema:** Documento principal ainda marcado como "PROPOSTA - SEM IMPLEMENTAÇÃO"  
**Correção:** Atualizar para "APROVADO - PRONTO PARA IMPLEMENTAÇÃO"

### **2. Cálculo de Datas - Regra de Antecipação** ⚠️→✅
**Problema:** Regra de antecipação não estava clara no documento principal  
**Correção:** Adicionar seção detalhada com exemplos e funções auxiliares

### **3. Integração com BusinessHoursService** ⚠️→✅
**Problema:** Não especifica como usar o serviço existente  
**Correção:** Documentar métodos específicos a usar

### **4. Cadastro de Destinatário - TAG** ⚠️→✅
**Problema:** Não especifica como criar/verificar TAG "COBRANÇA"  
**Correção:** Adicionar detalhes sobre modelo de Tags

### **5. Rotação de Variações** ⚠️→✅
**Problema:** Não especifica algoritmo de rotação  
**Correção:** Documentar algoritmo round-robin com índice

---

## 🎯 **MELHORIAS PROPOSTAS**

### **1. ESTRUTURA DE DADOS - Campos Adicionais**

#### **BillingCycle - Campos Adicionais:**
```sql
-- Campos já propostos ✅
-- Adicionar:
total_messages INTEGER DEFAULT 0,  -- Total de mensagens do ciclo (6 se ambos ativos)
sent_messages INTEGER DEFAULT 0,    -- Mensagens enviadas com sucesso
failed_messages INTEGER DEFAULT 0, -- Mensagens falhadas
completed_at TIMESTAMP,            -- Quando ciclo foi completado
contact_id UUID,                    -- FK para Contact (cadastrado automaticamente)
```

**Justificativa:**
- `total_messages`, `sent_messages`, `failed_messages`: Facilita relatórios e status
- `completed_at`: Histórico de quando ciclo terminou
- `contact_id`: Link direto com Contact cadastrado

#### **BillingContact - Campos Adicionais:**
```sql
-- Campos já propostos ✅
-- Adicionar:
cycle_index INTEGER,                -- 1, 2, 3, 4, 5, 6 (posição no ciclo)
template_variation_index INTEGER,   -- Índice da variação usada (para rotação)
retry_count INTEGER DEFAULT 0,     -- Contador de tentativas
last_retry_at TIMESTAMP,            -- Última tentativa de retry
```

**Justificativa:**
- `cycle_index`: Facilita ordenação e visualização
- `template_variation_index`: Rastreia qual variação foi usada
- `retry_count`, `last_retry_at`: Controle de retry

---

### **2. CÁLCULO DE DATAS - Melhorias**

#### **Problema Identificado:**
A regra de "antecipação" pode ser confusa. Precisamos distinguir:
- **Upcoming (A Vencer):** ANTECIPAR se cair em fim de semana
- **Overdue (Vencido):** POSTERGAR se cair em fim de semana (não faz sentido antecipar)

#### **Solução Proposta:**
```python
def calculate_scheduled_date(due_date: date, days_offset: int, is_upcoming: bool) -> date:
    """
    Calcula data agendada respeitando dias úteis.
    
    Args:
        due_date: Data de vencimento
        days_offset: Dias antes (-) ou depois (+) do vencimento
        is_upcoming: True se é mensagem "a vencer", False se "vencido"
    
    Returns:
        date: Data agendada (sempre dia útil)
    """
    # Calcular data bruta
    if is_upcoming:
        raw_date = due_date - timedelta(days=abs(days_offset))
    else:
        raw_date = due_date + timedelta(days=abs(days_offset))
    
    # Ajustar para dia útil
    if is_upcoming:
        # ANTECIPAR: Se cair em fim de semana, usar último dia útil ANTES
        scheduled_date = get_last_business_day_before(raw_date)
    else:
        # POSTERGAR: Se cair em fim de semana, usar próximo dia útil DEPOIS
        scheduled_date = get_next_business_day_after(raw_date)
    
    return scheduled_date
```

---

### **3. INTEGRAÇÃO COM BusinessHoursService**

#### **Métodos a Usar:**
```python
from apps.chat.services.business_hours_service import BusinessHoursService

# 1. Verificar se é dia útil
def is_business_day(date: date, tenant: Tenant) -> bool:
    """Verifica se data é dia útil"""
    check_datetime = datetime.combine(date, time.min).replace(tzinfo=timezone.utc)
    is_open, _ = BusinessHoursService.is_business_hours(tenant, None, check_datetime)
    return is_open

# 2. Obter próximo dia útil
def get_next_business_day_after(date: date, tenant: Tenant) -> date:
    """Retorna próximo dia útil depois da data"""
    current = datetime.combine(date, time.min).replace(tzinfo=timezone.utc)
    next_open = BusinessHoursService._get_next_open_datetime(
        BusinessHoursService.get_business_hours(tenant, None),
        current
    )
    return next_open.date() if next_open else date

# 3. Obter último dia útil antes
def get_last_business_day_before(date: date, tenant: Tenant) -> date:
    """Retorna último dia útil antes da data"""
    # Iterar para trás até encontrar dia útil
    check_date = date
    while not is_business_day(check_date, tenant):
        check_date = check_date - timedelta(days=1)
    return check_date
```

---

### **4. CADASTRO DE DESTINATÁRIO - Detalhamento**

#### **Processo Completo:**
```python
from apps.contacts.models import Contact, Tag
from apps.common.utils.phone import normalize_phone

def create_or_update_billing_contact(
    tenant: Tenant,
    nome: str,
    telefone: str
) -> Contact:
    """
    Cria ou atualiza contato para cobrança.
    
    Processo:
    1. Normaliza telefone
    2. Busca Contact existente
    3. Se não existe, cria novo
    4. Garante TAG "COBRANÇA"
    5. Atualiza nome se mudou
    """
    # 1. Normalizar telefone
    normalized_phone = normalize_phone(telefone)
    
    # 2. Buscar Contact existente
    contact = Contact.objects.filter(
        tenant=tenant,
        phone=normalized_phone
    ).first()
    
    # 3. Criar se não existe
    if not contact:
        contact = Contact.objects.create(
            tenant=tenant,
            name=nome,
            phone=normalized_phone,
            source='billing_api'  # Identificar origem
        )
    
    # 4. Atualizar nome se mudou
    if contact.name != nome:
        contact.name = nome
        contact.save(update_fields=['name', 'updated_at'])
    
    # 5. Garantir TAG "COBRANÇA"
    tag, _ = Tag.objects.get_or_create(
        tenant=tenant,
        name='COBRANÇA',
        defaults={'color': '#FF0000'}  # Vermelho para cobrança
    )
    if tag not in contact.tags.all():
        contact.tags.add(tag)
    
    return contact
```

---

### **5. ROTAÇÃO DE VARIAÇÕES - Algoritmo**

#### **Problema Identificado:**
Não especifica como rotacionar variações entre mensagens do ciclo.

#### **Solução Proposta:**
```python
def select_template_variation(
    template: BillingTemplate,
    cycle_index: int
) -> BillingTemplateVariation:
    """
    Seleciona variação de template usando round-robin.
    
    Algoritmo:
    - Usa cycle_index (1-6) para determinar qual variação usar
    - Rotaciona: variação 1, 2, 3, 1, 2, 3...
    - Se template tiver menos variações, repete
    """
    variations = list(template.variations.all().order_by('order'))
    
    if not variations:
        raise ValueError(f"Template {template.id} não tem variações")
    
    # Round-robin: usar índice baseado em cycle_index
    variation_index = (cycle_index - 1) % len(variations)
    return variations[variation_index]
```

**Exemplo:**
- Template tem 3 variações (A, B, C)
- Ciclo tem 6 mensagens (1, 2, 3, 4, 5, 6)
- Rotação: A, B, C, A, B, C

---

### **6. SCHEDULER - Melhorias**

#### **Problema Identificado:**
Scheduler verifica apenas `scheduled_date = hoje`, mas não considera:
- Mensagens que deveriam ter sido enviadas ontem (atrasadas)
- Mensagens que podem ser enviadas hoje (dentro do horário)

#### **Solução Proposta:**
```python
def get_pending_messages_for_today(tenant: Tenant) -> QuerySet:
    """
    Busca mensagens que devem ser enviadas hoje.
    
    Inclui:
    - Mensagens com scheduled_date = hoje
    - Mensagens com scheduled_date < hoje (atrasadas)
    - Apenas ciclos ativos
    - Apenas status pending
    """
    today = timezone.now().date()
    
    return BillingContact.objects.filter(
        billing_cycle__tenant=tenant,
        billing_cycle__status='active',
        status='pending',
        scheduled_date__lte=today  # <= hoje (inclui atrasadas)
    ).select_related(
        'billing_cycle',
        'template_variation'
    ).order_by('scheduled_date', 'cycle_index')
```

#### **Verificação de Horário Comercial:**
```python
def should_send_now(tenant: Tenant) -> bool:
    """
    Verifica se pode enviar agora (horário comercial).
    """
    is_open, next_open = BusinessHoursService.is_business_hours(tenant, None)
    
    if not is_open:
        logger.info(f"⏰ Fora do horário comercial. Próximo horário: {next_open}")
        return False
    
    return True
```

---

### **7. STATUS DO CICLO - Melhorias**

#### **Problema Identificado:**
Não especifica quando marcar ciclo como 'completed'.

#### **Solução Proposta:**
```python
def check_and_complete_cycle(cycle: BillingCycle):
    """
    Verifica se ciclo deve ser marcado como 'completed'.
    
    Condições:
    1. Todas as mensagens foram processadas (sent ou failed)
    2. Nenhuma mensagem pendente
    """
    total = cycle.billing_contacts.count()
    sent = cycle.billing_contacts.filter(status='sent').count()
    failed = cycle.billing_contacts.filter(status='failed').count()
    pending = cycle.billing_contacts.filter(status='pending').count()
    
    # Se todas foram processadas (sent + failed = total)
    if (sent + failed) == total and pending == 0:
        cycle.status = 'completed'
        cycle.completed_at = timezone.now()
        cycle.sent_messages = sent
        cycle.failed_messages = failed
        cycle.save(update_fields=['status', 'completed_at', 'sent_messages', 'failed_messages'])
        
        logger.info(f"✅ Ciclo {cycle.id} completado: {sent} enviadas, {failed} falhadas")
```

---

### **8. CANCELAMENTO - Melhorias**

#### **Problema Identificado:**
Não especifica o que fazer com mensagens já enviadas.

#### **Solução Proposta:**
```python
def cancel_cycle(cycle: BillingCycle, reason: str):
    """
    Cancela ciclo completo.
    
    Processo:
    1. Marca ciclo como cancelled/paid
    2. Cancela apenas mensagens pendentes (não mexe nas enviadas)
    3. Atualiza contadores
    """
    # 1. Atualizar status do ciclo
    cycle.status = reason  # 'cancelled' ou 'paid'
    cycle.cancelled_at = timezone.now()
    
    # 2. Cancelar apenas mensagens pendentes
    pending_messages = cycle.billing_contacts.filter(status='pending')
    cancelled_count = pending_messages.update(
        status='cancelled',
        billing_status=reason
    )
    
    # 3. Atualizar contadores
    cycle.total_messages = cycle.billing_contacts.count()
    cycle.sent_messages = cycle.billing_contacts.filter(status='sent').count()
    cycle.failed_messages = cycle.billing_contacts.filter(status='failed').count()
    
    cycle.save()
    
    logger.info(
        f"🚫 Ciclo {cycle.id} cancelado: {cancelled_count} mensagens pendentes canceladas"
    )
```

---

### **9. TEMPLATE SELECTION - Melhorias**

#### **Problema Identificado:**
Não especifica como escolher entre template genérico e específico.

#### **Solução Proposta:**
```python
def select_template_for_message(
    tenant: Tenant,
    cycle_message_type: str,  # upcoming_5d, overdue_1d, etc
    template_type: str  # 'overdue' ou 'upcoming'
) -> BillingTemplate:
    """
    Seleciona template para mensagem do ciclo.
    
    Lógica:
    1. Se template_scope = 'specific': busca template com specific_day = cycle_message_type
    2. Se template_scope = 'generic': busca template genérico do tipo
    3. Se não encontrar específico, usa genérico como fallback
    """
    # Tentar buscar template específico primeiro
    specific_template = BillingTemplate.objects.filter(
        tenant=tenant,
        template_type=template_type,
        template_scope='specific',
        specific_day=cycle_message_type,
        is_active=True
    ).first()
    
    if specific_template:
        return specific_template
    
    # Fallback: template genérico
    generic_template = BillingTemplate.objects.filter(
        tenant=tenant,
        template_type=template_type,
        template_scope='generic',
        is_active=True
    ).first()
    
    if not generic_template:
        raise ValueError(
            f"Nenhum template {template_type} encontrado para tenant {tenant.id}"
        )
    
    return generic_template
```

---

### **10. RETRY - Melhorias**

#### **Problema Identificado:**
Não especifica estratégia de retry para mensagens do ciclo.

#### **Solução Proposta:**
```python
def retry_failed_message(contact: BillingContact, max_retries: int = 3):
    """
    Tenta reenviar mensagem falhada.
    
    Estratégia:
    - Retry imediato: 1 tentativa
    - Retry com delay: 2 tentativas (1h, 4h depois)
    - Após max_retries, marca como failed permanentemente
    """
    if contact.retry_count >= max_retries:
        contact.status = 'failed'
        contact.save(update_fields=['status', 'updated_at'])
        logger.warning(f"❌ Mensagem {contact.id} falhou após {max_retries} tentativas")
        return False
    
    # Incrementar contador
    contact.retry_count += 1
    contact.last_retry_at = timezone.now()
    contact.status = 'pending'  # Voltar para pending para tentar novamente
    contact.save(update_fields=['retry_count', 'last_retry_at', 'status', 'updated_at'])
    
    logger.info(f"🔄 Retentando mensagem {contact.id} (tentativa {contact.retry_count}/{max_retries})")
    return True
```

---

## 📊 **MELHORIAS DE PERFORMANCE**

### **1. Índices Adicionais:**
```sql
-- Índice composto para scheduler
CREATE INDEX idx_contact_scheduled_status_cycle 
ON billing_api_contact(scheduled_date, status, billing_cycle_id) 
WHERE status = 'pending';

-- Índice para busca de ciclos por external_id
CREATE INDEX idx_cycle_tenant_external 
ON billing_api_cycle(tenant_id, external_billing_id);

-- Índice para relatórios
CREATE INDEX idx_cycle_status_created 
ON billing_api_cycle(status, created_at);
```

### **2. Batch Processing:**
```python
# Processar em batches de 100
def process_pending_messages_batch(tenant: Tenant, batch_size: int = 100):
    """Processa mensagens pendentes em batches"""
    pending = get_pending_messages_for_today(tenant)
    
    for batch in chunked(pending, batch_size):
        for message in batch:
            try:
                send_cycle_message(message)
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem {message.id}: {e}")
                # Continuar com próxima mensagem
```

---

## 🔒 **MELHORIAS DE SEGURANÇA**

### **1. Validação de External Billing ID:**
```python
def validate_external_billing_id(tenant: Tenant, external_id: str) -> bool:
    """
    Valida se external_billing_id é único por tenant.
    """
    existing = BillingCycle.objects.filter(
        tenant=tenant,
        external_billing_id=external_id
    ).exists()
    
    if existing:
        raise ValueError(
            f"external_billing_id '{external_id}' já existe para este tenant"
        )
    
    return True
```

### **2. Rate Limiting no Batch:**
```python
# Limitar tamanho do batch
MAX_BATCH_SIZE = 1000

def validate_batch_size(contacts: List[Dict]) -> bool:
    """Valida tamanho do batch"""
    if len(contacts) > MAX_BATCH_SIZE:
        raise ValueError(
            f"Batch muito grande: {len(contacts)} > {MAX_BATCH_SIZE}"
        )
    return True
```

---

## 📝 **MELHORIAS DE DOCUMENTAÇÃO**

### **1. Adicionar Diagramas:**
- Diagrama de sequência do fluxo completo
- Diagrama de estados do ciclo
- Diagrama de relacionamento de modelos

### **2. Adicionar Exemplos:**
- Exemplo completo de payload de batch
- Exemplo de resposta de cancelamento
- Exemplo de template genérico vs específico

### **3. Adicionar Troubleshooting:**
- O que fazer se scheduler não executar
- O que fazer se mensagens não forem enviadas
- Como debugar problemas de cálculo de datas

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO ATUALIZADO**

### **Fase 1: Modelos e Estrutura** ✅
- [x] Criar modelo `BillingCycle` (com campos adicionais)
- [x] Modificar `BillingContact` (com campos de ciclo)
- [x] Adicionar campos de template (template_scope, specific_day)
- [x] Criar migrations SQL
- [x] Criar serializers

### **Fase 2: Services** ✅
- [x] Criar `BillingCycleService`
  - [x] Método para criar ciclo e mensagens agendadas
  - [x] Método para cancelar ciclo
  - [x] Método para calcular `scheduled_date` (com dias úteis)
  - [x] Método para verificar e completar ciclo
- [x] Criar `BillingContactService` (cadastro automático)
- [x] Criar `BillingTemplateService` (seleção de template)
- [x] Modificar `BillingCampaignService` para suportar ciclos
- [x] Criar `BillingCycleScheduler` (verificação diária)

### **Fase 3: APIs** ✅
- [x] Criar endpoint `POST /billing/v1/billing/send/batch`
- [x] Criar endpoint `POST /billing/v1/billing/cancel`
- [x] Criar endpoint `GET /billing/v1/billing/cycles/` (admin)
- [x] Criar endpoint `GET /billing/v1/billing/cycles/{cycle_id}/` (admin)

### **Fase 4: Scheduler** ✅
- [x] Implementar verificação diária
- [x] Integrar com BusinessHoursService
- [x] Processar mensagens atrasadas
- [x] Integrar com RabbitMQ para envio
- [x] Tratamento de erros e retry

### **Fase 5: Frontend** ✅
- [x] Página `/billing-api/cycles`
- [x] Dashboard com estatísticas
- [x] Filtros e busca
- [x] Detalhes do ciclo

---

## 🎯 **PRÓXIMOS PASSOS**

1. ✅ **Revisão Completa** - FEITO
2. ⏳ **Atualizar Documento Principal** - Aplicar melhorias
3. ⏳ **Validar com Stakeholders** - Confirmar decisões
4. ⏳ **Iniciar Implementação** - Seguir checklist

---

**Status:** ✅ **REVISADO E MELHORADO - PRONTO PARA IMPLEMENTAÇÃO**

