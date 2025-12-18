# 🔄 **ANÁLISE DE REUTILIZAÇÃO - SISTEMA DE BILLING**

> **O que já existe e pode ser aproveitado?**  
> **O que precisa ser adaptado?**  
> **O que precisa ser criado do zero?**

---

## 📋 **RESUMO EXECUTIVO**

| Categoria | Reutilizar | Adaptar | Criar do Zero |
|-----------|------------|---------|---------------|
| **Phone Validation** | ✅ 100% | - | - |
| **Template Rendering** | ⚠️ 70% | ✅ 30% | - |
| **Business Hours** | ✅ 100% | - | - |
| **Rate Limiting** | ✅ 100% | - | - |
| **RabbitMQ Consumer** | ⚠️ 50% | ✅ 50% | - |
| **Evolution API** | ✅ 100% | - | - |
| **Models** | - | - | ✅ 100% |
| **Services** | - | ⚠️ 20% | ✅ 80% |

**Economia estimada:** ~40% do tempo de desenvolvimento

---

## ✅ **1. PHONE VALIDATION - REUTILIZAR 100%**

### **O que já existe:**

**Arquivo:** `backend/apps/contacts/utils.py` (linha 96-124)

```python
def normalize_phone(phone):
    """
    Normaliza telefone para formato E.164
    
    Exemplos:
    - (11) 99999-9999  → +5511999999999
    - 11999999999      → +5511999999999
    - +5511999999999   → +5511999999999 (já correto)
    """
    if not phone:
        return phone
    
    # Remover formatação (parênteses, hífens, espaços)
    clean = re.sub(r'[^\d+]', '', phone)
    
    # Adicionar +55 se não tiver código de país
    if not clean.startswith('+'):
        if clean.startswith('55'):
            clean = f'+{clean}'
        else:
            clean = f'+55{clean}'
    
    return clean
```

**Também existe:** `backend/apps/common/validators.py` (linha 118-148)
- `SecureInputValidator.validate_phone()` - Validação mais rigorosa

### **✅ AÇÃO: REUTILIZAR DIRETO**

**No Billing:**
```python
# apps/billing/services/billing_campaign_service.py

from apps.contacts.utils import normalize_phone  # ← REUTILIZAR!

# Usar:
phone = normalize_phone(contact_data.get('telefone', ''))
```

**❌ NÃO CRIAR:** `apps/billing/utils/phone_validator.py`  
**✅ USAR:** `apps/contacts/utils.py::normalize_phone`

---

## ⚠️ **2. TEMPLATE RENDERING - ADAPTAR 30%**

### **O que já existe:**

**Arquivo:** `backend/apps/campaigns/services.py` (linha 816-901)

```python
class MessageVariableService:
    """Renderiza variáveis em mensagens de campanha"""
    
    @staticmethod
    def render_message(template: str, contact, extra_vars: dict = None) -> str:
        """
        Renderiza template com variáveis {{variavel}}
        
        Suporta:
        - Variáveis padrão: {{nome}}, {{email}}, etc.
        - Custom fields: {{clinica}}, {{valor}}, etc.
        - Sistema: {{saudacao}}, {{dia_semana}}
        """
        rendered = template
        
        # 1. Variáveis padrão
        for var_name, getter in MessageVariableService.STANDARD_VARIABLES.items():
            value = getter(contact)
            rendered = rendered.replace(f'{{{{{var_name}}}}}', str(value))
        
        # 2. Custom fields
        if hasattr(contact, 'custom_fields') and contact.custom_fields:
            for key, value in contact.custom_fields.items():
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        
        # 3. Sistema
        rendered = rendered.replace('{{saudacao}}', MessageVariableService.get_greeting())
        rendered = rendered.replace('{{dia_semana}}', MessageVariableService.get_day_of_week())
        
        # 4. Extra vars
        if extra_vars:
            for key, value in extra_vars.items():
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        
        return rendered
```

### **⚠️ PROBLEMA: Não suporta condicionais!**

**Billing precisa:**
- `{{#if codigo_pix}}...{{/if}}` ❌ Não suporta
- `{{#unless link}}...{{/unless}}` ❌ Não suporta

### **✅ AÇÃO: ADAPTAR + EXTENDER**

**Opção 1: Estender MessageVariableService (RECOMENDADO)**
```python
# apps/campaigns/services.py (ADICIONAR método)

class MessageVariableService:
    # ... código existente ...
    
    @staticmethod
    def render_message_with_conditionals(template: str, variables: dict) -> str:
        """
        Renderiza template com condicionais (para Billing)
        
        Suporta:
        - {{#if variavel}}...{{/if}}
        - {{#unless variavel}}...{{/unless}}
        - {{variavel}} (simples)
        """
        from apps.billing.utils.template_engine import BillingTemplateEngine
        
        # Usa o engine de billing para condicionais
        return BillingTemplateEngine.render_message(template, variables)
```

**Opção 2: Criar BillingTemplateEngine (do guia)**
- ✅ Criar `apps/billing/utils/template_engine.py` (do guia)
- ✅ Usar apenas para billing (não quebra campanhas)

**✅ RECOMENDAÇÃO:** Opção 2 (separar responsabilidades)

---

## ✅ **3. BUSINESS HOURS - REUTILIZAR 100%**

### **O que já existe:**

**Model:** `backend/apps/chat/models_business_hours.py`
- ✅ `BusinessHours` model completo
- ✅ Campos por dia da semana
- ✅ Feriados (JSON)
- ✅ Timezone support

**Service:** `backend/apps/chat/services/business_hours_service.py`
- ✅ `BusinessHoursService.is_business_hours()` - Verifica se está aberto
- ✅ `BusinessHoursService._get_next_open_datetime()` - Próximo horário válido
- ✅ Suporta tenant + department

### **✅ AÇÃO: REUTILIZAR DIRETO**

**No Billing:**
```python
# apps/billing/schedulers/business_hours_scheduler.py

from apps.chat.services.business_hours_service import BusinessHoursService  # ← REUTILIZAR!

class BillingBusinessHoursScheduler:
    @staticmethod
    def is_within_business_hours(tenant, check_time=None):
        """Usa service existente"""
        is_open, next_open = BusinessHoursService.is_business_hours(
            tenant, 
            department=None,  # Billing usa horário geral do tenant
            check_datetime=check_time
        )
        return is_open
    
    @staticmethod
    def get_next_valid_datetime(tenant):
        """Usa service existente"""
        business_hours = BusinessHoursService.get_business_hours(tenant)
        if not business_hours:
            # Fallback
            return timezone.now() + timedelta(days=1)
        
        next_open = BusinessHoursService._get_next_open_datetime(
            business_hours,
            timezone.now()
        )
        return next_open or (timezone.now() + timedelta(days=1))
```

**❌ NÃO CRIAR:** Novo model ou service de business hours  
**✅ USAR:** `apps/chat/services/business_hours_service.py`

---

## ✅ **4. RATE LIMITING - REUTILIZAR 100%**

### **O que já existe:**

**Arquivo:** `backend/apps/common/rate_limiting.py`
- ✅ `rate_limit()` decorator
- ✅ `rate_limit_by_user()` helper
- ✅ `rate_limit_by_ip()` helper
- ✅ Suporta formatos: `'10/m'`, `'100/h'`, `'1000/d'`

**Arquivo:** `backend/apps/common/validators.py`
- ✅ `RateLimitValidator.check_rate_limit()` - Validação baseada em Redis

### **✅ AÇÃO: REUTILIZAR DIRETO**

**No Billing:**
```python
# apps/billing/throttling.py (SIMPLIFICADO)

from apps.common.rate_limiting import rate_limit_by_ip  # ← REUTILIZAR!

# Ou criar wrapper específico:
class BillingAPIRateThrottle(BaseThrottle):
    def allow_request(self, request, view):
        # Usa RateLimitValidator existente
        from apps.common.validators import RateLimitValidator
        
        api_key = getattr(request, 'auth', None)
        if not api_key:
            return True
        
        cache_key = f"billing_api_{api_key.id}"
        limit = api_key.tenant.billing_config.api_rate_limit_per_hour
        
        allowed, remaining = RateLimitValidator.check_rate_limit(
            cache_key,
            limit,
            window=3600  # 1 hora
        )
        
        return allowed
```

**❌ NÃO CRIAR:** Novo sistema de rate limiting  
**✅ USAR:** `apps/common/rate_limiting.py` + `apps/common/validators.py`

---

## ⚠️ **5. RABBITMQ CONSUMER - ADAPTAR 50%**

### **O que já existe:**

**Arquivo:** `backend/apps/campaigns/rabbitmq_consumer.py`
- ✅ `RabbitMQConsumer` class completa
- ✅ Async/await com aio-pika
- ✅ Health checks
- ✅ Error handling
- ✅ Graceful shutdown

**Padrão usado:**
```python
class RabbitMQConsumer:
    async def start(self):
        self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        # ...
    
    async def _process_message(self, message):
        # Processa mensagem
        pass
```

### **⚠️ DIFERENÇAS:**

| Aspecto | Campanhas | Billing |
|---------|-----------|---------|
| **Queue names** | `campaign.{id}.messages` | `billing.overdue`, `billing.upcoming`, etc. |
| **Prioridades** | Não usa | ✅ Usa (10, 5, 1) |
| **Worker** | Async direto | Sync worker em thread |
| **Múltiplas queues** | 1 por campanha | 6 queues fixas |

### **✅ AÇÃO: ADAPTAR BASE EXISTENTE**

**Criar:** `apps/billing/rabbitmq/billing_consumer.py`

```python
# Baseado em campaigns/rabbitmq_consumer.py, mas adaptado

from apps.campaigns.rabbitmq_consumer import RabbitMQConsumer  # ← Inspiração

class BillingConsumer:
    """Consumer específico para billing"""
    
    def __init__(self):
        # Mesma estrutura base
        self.connection = None
        self.channel = None
        self.running = False
    
    async def start(self):
        # Mesmo padrão de conexão
        self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        
        # ✅ DIFERENÇA: Declara múltiplas queues com prioridade
        await self._setup_queues()
        await self._consume_queues()
    
    async def _setup_queues(self):
        """Declara queues com prioridade (NOVO)"""
        queues = [
            ('billing.overdue', 10),
            ('billing.upcoming', 5),
            ('billing.notification', 1),
            # ...
        ]
        
        for queue_name, priority in queues:
            await self.channel.declare_queue(
                queue_name,
                durable=True,
                arguments={'x-max-priority': 10}  # ← NOVO
            )
    
    async def _process_queue(self, message):
        """Processa mensagem (ADAPTADO)"""
        # ✅ DIFERENÇA: Executa worker sync em thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._run_worker_sync,
            queue_id
        )
```

**✅ REUTILIZAR:** Estrutura base, padrão de conexão, error handling  
**✅ ADAPTAR:** Múltiplas queues, prioridades, worker sync

---

## ✅ **6. EVOLUTION API - REUTILIZAR 100%**

### **O que já existe:**

**Arquivo:** `backend/apps/campaigns/services.py` (linha 354-393)

```python
# Padrão usado em campanhas:
url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
headers = {
    'apikey': instance.api_key,
    'Content-Type': 'application/json'
}
payload = {
    'number': phone,
    'text': message_text
}

# Retry com backoff exponencial
max_retries = 3
base_delay = 1

for attempt in range(max_retries + 1):
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        break
    except requests.exceptions.RequestException as e:
        if attempt == max_retries:
            raise e
        delay = base_delay * (2 ** attempt)
        time.sleep(delay)
```

### **✅ AÇÃO: REUTILIZAR PADRÃO EXATO**

**No Billing:**
```python
# apps/billing/services/billing_send_service.py

import requests
import time

class BillingSendService:
    def send_billing_message(self, billing_contact, instance):
        """Usa MESMO padrão de campanhas"""
        
        # Preparar número (mesmo padrão)
        phone = billing_contact.campaign_contact.phone_number.replace('+', '').replace('-', '').replace(' ', '')
        if not phone.startswith('55'):
            phone = f'55{phone}'
        
        message_text = billing_contact.rendered_message
        
        # ✅ COPIAR CÓDIGO EXATO DE CAMPANHAS
        url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
        headers = {
            'apikey': instance.api_key,
            'Content-Type': 'application/json'
        }
        payload = {
            'number': phone,
            'text': message_text
        }
        
        # Retry com backoff (mesmo padrão)
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    raise e
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
        
        response_data = response.json()
        # ... resto do código ...
```

**❌ NÃO CRIAR:** Novo EvolutionAPIService  
**✅ USAR:** Padrão direto de campanhas (já testado em produção)

---

## 📦 **7. MODELS - CRIAR DO ZERO (100%)**

### **O que já existe relacionado:**

- ✅ `apps/contacts/models.py::Contact` - Contato base
- ✅ `apps/campaigns/models.py::Campaign` - Campanha base
- ✅ `apps/campaigns/models.py::CampaignContact` - Relação campanha-contato
- ✅ `apps/chat/models_business_hours.py::BusinessHours` - Horário comercial

### **✅ AÇÃO: CRIAR NOVOS MODELS (do guia)**

**Models a criar:**
1. ✅ `BillingConfig` - Configurações por tenant
2. ✅ `BillingAPIKey` - API Keys
3. ✅ `BillingTemplate` + `BillingTemplateVariation` - Templates
4. ✅ `BillingCampaign` - Campanha de billing (OneToOne com Campaign)
5. ✅ `BillingQueue` - Fila de processamento
6. ✅ `BillingContact` - Contato de billing (OneToOne com CampaignContact)

**Relacionamentos:**
```python
# BillingCampaign usa Campaign existente
billing_campaign = BillingCampaign.objects.create(
    tenant=tenant,
    template=template,
    campaign=campaign,  # ← Usa Campaign existente!
    external_id='fatura-123'
)

# BillingContact usa CampaignContact existente
billing_contact = BillingContact.objects.create(
    billing_campaign=billing_campaign,
    campaign_contact=campaign_contact,  # ← Usa CampaignContact existente!
    template_variation=variation,
    rendered_message=message
)
```

**✅ REUTILIZAR:** Models existentes (Contact, Campaign, CampaignContact)  
**✅ CRIAR:** Models específicos de billing (do guia)

---

## 🔧 **8. SERVICES - CRIAR 80%, ADAPTAR 20%**

### **O que já existe relacionado:**

- ✅ `apps/campaigns/services.py::RotationService` - Seleção de instâncias
- ✅ `apps/campaigns/services.py::MessageVariableService` - Renderização (adaptar)
- ✅ `apps/chat/services/business_hours_service.py` - Horário comercial (reutilizar)

### **✅ AÇÃO: CRIAR NOVOS SERVICES**

**Services a criar (do guia):**
1. ✅ `BillingCampaignService` - Orchestrator (NOVO)
2. ✅ `BillingSendService` - Envio (NOVO, mas usa padrão de campanhas)
3. ✅ `BillingBusinessHoursScheduler` - Wrapper do BusinessHoursService (ADAPTAR)

**Services a adaptar:**
- ⚠️ `MessageVariableService` - Adicionar suporte a condicionais (ou criar BillingTemplateEngine separado)

---

## 📊 **RESUMO FINAL - O QUE FAZER**

### **✅ REUTILIZAR DIRETO (sem mudanças):**

1. ✅ **Phone Validation:** `apps/contacts/utils.py::normalize_phone`
2. ✅ **Business Hours:** `apps/chat/services/business_hours_service.py`
3. ✅ **Rate Limiting:** `apps/common/rate_limiting.py`
4. ✅ **Evolution API:** Padrão de `apps/campaigns/services.py` (linha 354-393)

### **⚠️ ADAPTAR (pequenas mudanças):**

1. ⚠️ **Template Engine:** 
   - Opção A: Estender `MessageVariableService` com condicionais
   - Opção B: Criar `BillingTemplateEngine` separado (RECOMENDADO)
   
2. ⚠️ **RabbitMQ Consumer:**
   - Baseado em `campaigns/rabbitmq_consumer.py`
   - Adaptar para múltiplas queues + prioridades

3. ⚠️ **Business Hours Scheduler:**
   - Wrapper simples do `BusinessHoursService` existente

### **✅ CRIAR DO ZERO:**

1. ✅ **Models:** Todos os 6 models de billing (do guia)
2. ✅ **Services:** `BillingCampaignService`, `BillingSendService`
3. ✅ **APIs:** Endpoints REST (do guia Parte 2)
4. ✅ **Serializers:** Request/Response (do guia Parte 2)
5. ✅ **Worker:** `BillingSenderWorker` (do guia)

---

## 🎯 **PLANO DE IMPLEMENTAÇÃO OTIMIZADO**

### **Fase 1: Reutilizar o que já existe (1 dia)**
```
□ Importar normalize_phone de contacts/utils
□ Importar BusinessHoursService de chat/services
□ Importar rate_limit de common/rate_limiting
□ Testar imports funcionando
```

### **Fase 2: Adaptar o que precisa (2 dias)**
```
□ Criar BillingTemplateEngine (com condicionais)
□ Criar BillingBusinessHoursScheduler (wrapper)
□ Adaptar RabbitMQConsumer base
□ Testar adaptações
```

### **Fase 3: Criar o novo (12-15 dias)**
```
□ Models (2-3 dias)
□ Services principais (3-4 dias)
□ Worker + RabbitMQ (3-4 dias)
□ APIs + Serializers (2-3 dias)
□ Testes (2-3 dias)
```

**Tempo total:** 15-18 dias (vs 20 dias sem reutilização)  
**Economia:** ~2-5 dias

---

## ✅ **CHECKLIST DE REUTILIZAÇÃO**

Antes de criar algo novo, verificar:

- [ ] Já existe em `apps/common/`? → Reutilizar
- [ ] Já existe em `apps/contacts/`? → Reutilizar
- [ ] Já existe em `apps/campaigns/`? → Adaptar ou reutilizar
- [ ] Já existe em `apps/chat/`? → Reutilizar
- [ ] Precisa de mudanças? → Adaptar
- [ ] Não existe? → Criar do zero

---

## 🚀 **PRÓXIMOS PASSOS**

1. ✅ **Atualizar ERRATA** com essas descobertas
2. ✅ **Atualizar guias** para referenciar código existente
3. ✅ **Começar implementação** reutilizando o máximo possível

---

**💡 Dica:** Sempre que for criar algo, fazer uma busca no código primeiro:
```bash
# Buscar por funcionalidade similar
grep -r "normalize_phone" backend/apps/
grep -r "rate_limit" backend/apps/
grep -r "business_hours" backend/apps/
```

**🎯 Resultado:** Código mais limpo, menos duplicação, implementação mais rápida!

