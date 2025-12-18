# ⚡ **BILLING SYSTEM - QUICK START**

> **Teste o sistema de billing em 15 minutos!**

---

## 🚀 **SETUP RÁPIDO (DEV)**

### **1. Criar Models**

```bash
# Criar app
python manage.py startapp billing apps/billing

# Copiar models do guia para:
# - apps/billing/models/billing_config.py
# - apps/billing/models/billing_api_key.py
# - apps/billing/models/billing_template.py
# - apps/billing/models/billing_campaign.py
# - apps/billing/models/billing_queue.py
# - apps/billing/models/billing_contact.py

# Criar __init__.py no models
touch apps/billing/models/__init__.py

# Adicionar ao INSTALLED_APPS (settings.py)
INSTALLED_APPS += ['apps.billing']

# Criar migrations
python manage.py makemigrations billing

# Aplicar
python manage.py migrate billing
```

---

### **2. Popular Templates de Teste**

```python
# python manage.py shell

from apps.billing.models import BillingTemplate, BillingTemplateVariation, TemplateType
from apps.tenancy.models import Tenant

# Pegar tenant
tenant = Tenant.objects.first()

# Criar template de cobrança atrasada
template = BillingTemplate.objects.create(
    tenant=tenant,
    name='Cobrança Atrasada Padrão',
    template_type=TemplateType.OVERDUE,
    priority=10,
    allow_retry=True,
    max_retries=3,
    rotation_strategy='random',
    required_fields=['nome_cliente', 'telefone', 'valor', 'data_vencimento'],
    optional_fields=['codigo_pix', 'link_pagamento'],
    is_active=True
)

# Criar variação 1
BillingTemplateVariation.objects.create(
    template=template,
    variation_number=1,
    message_template="""
🔴 *Cobrança Vencida*

Olá {{nome_cliente}}! 👋

Identificamos uma fatura em atraso:

💰 *Valor:* {{valor}}
📅 *Vencimento:* {{data_vencimento}}
⏰ *Atraso:* {{dias_atraso_texto}}

{{#if codigo_pix}}
📱 *PIX Copia e Cola:*
{{codigo_pix}}
{{/if}}

{{#if link_pagamento}}
🔗 *Pagar Online:*
{{link_pagamento}}
{{/if}}

Por favor, regularize seu pagamento. 🙏
    """.strip(),
    is_active=True
)

# Criar variação 2
BillingTemplateVariation.objects.create(
    template=template,
    variation_number=2,
    message_template="""
⚠️ *Fatura em Atraso*

{{nome_cliente}}, sua fatura está vencida há {{dias_atraso_texto}}.

*Detalhes:*
• Valor: {{valor}}
• Venceu em: {{data_vencimento}}

{{#if codigo_pix}}
*Pagar via PIX:*
{{codigo_pix}}
{{/if}}

{{#if link_pagamento}}
*Ou acesse:* {{link_pagamento}}
{{/if}}

Conte conosco! ✨
    """.strip(),
    is_active=True
)

print("✅ Templates criados!")
```

---

### **3. Criar Configuração + API Key**

```python
# python manage.py shell

from apps.billing.models import BillingConfig, BillingAPIKey
from apps.tenancy.models import Tenant

tenant = Tenant.objects.first()

# Criar config
config = BillingConfig.objects.create(
    tenant=tenant,
    messages_per_minute=20,
    min_interval_seconds=3,
    respect_business_hours=False,  # Teste sem restrição de horário
    pause_outside_hours=False,
    max_batch_size=1000,
    enable_auto_retry=True,
    max_retry_attempts=3,
    api_enabled=True,
    api_rate_limit_per_hour=1000
)

# Criar API Key
api_key = BillingAPIKey.objects.create(
    tenant=tenant,
    name='Teste Local',
    description='API Key para testes locais',
    is_active=True
)

print(f"✅ API Key criada: {api_key.key}")
print(f"   Copie e guarde esta key!")
```

---

### **4. Rodar Consumer (Terminal 1)**

```bash
# Criar management command primeiro:
mkdir -p apps/billing/management/commands
touch apps/billing/management/commands/__init__.py

# Copiar código do comando run_billing_consumer.py do guia

# Rodar
python manage.py run_billing_consumer
```

---

### **5. Testar API (Terminal 2)**

```bash
# Salvar API Key em variável
export API_KEY="billing_..."  # Cole a key aqui

# Teste 1: Cobrança atrasada
curl -X POST http://localhost:8000/api/v1/billing/send/overdue \
  -H "X-Billing-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "teste-001",
    "contacts": [
      {
        "nome_cliente": "João Teste",
        "telefone": "+5511999999999",
        "valor": "R$ 150,00",
        "data_vencimento": "10/12/2025",
        "valor_total": "R$ 165,00",
        "codigo_pix": "00020126580014br.gov.bcb.pix2563..."
      }
    ]
  }'
```

**Resposta esperada:**
```json
{
  "success": true,
  "message": "Campanha criada com sucesso",
  "billing_campaign_id": "...",
  "queue_id": "...",
  "total_contacts": 1
}
```

---

### **6. Verificar Status**

```bash
# Pegar queue_id da resposta anterior
export QUEUE_ID="..."

curl -X GET "http://localhost:8000/api/v1/billing/queue/$QUEUE_ID/status" \
  -H "X-Billing-API-Key: $API_KEY"
```

**Resposta:**
```json
{
  "id": "...",
  "status": "completed",
  "total_contacts": 1,
  "contacts_sent": 1,
  "progress_percent": 100.0,
  ...
}
```

---

## 🧪 **TESTES ADICIONAIS**

### **Teste 2: Cobrança a Vencer**

```bash
curl -X POST http://localhost:8000/api/v1/billing/send/upcoming \
  -H "X-Billing-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "teste-002",
    "contacts": [
      {
        "nome_cliente": "Maria Silva",
        "telefone": "+5511988888888",
        "valor": "R$ 200,00",
        "data_vencimento": "25/12/2025",
        "link_pagamento": "https://pay.example.com/invoice/002"
      }
    ]
  }'
```

---

### **Teste 3: Notificação (24/7)**

```bash
curl -X POST http://localhost:8000/api/v1/billing/send/notification \
  -H "X-Billing-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "teste-003",
    "contacts": [
      {
        "nome_cliente": "Pedro Santos",
        "telefone": "+5511977777777",
        "titulo": "Lembrete Importante",
        "mensagem": "Sua consulta está agendada para amanhã às 14h."
      }
    ]
  }'
```

---

### **Teste 4: Controlar Fila (Pause/Resume)**

```bash
# Pausar
curl -X POST "http://localhost:8000/api/v1/billing/queue/$QUEUE_ID/control" \
  -H "X-Billing-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'

# Retomar
curl -X POST "http://localhost:8000/api/v1/billing/queue/$QUEUE_ID/control" \
  -H "X-Billing-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'

# Cancelar
curl -X POST "http://localhost:8000/api/v1/billing/queue/$QUEUE_ID/control" \
  -H "X-Billing-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "cancel"}'
```

---

## 🔍 **DEBUG**

### **Ver Logs do Consumer**

```bash
# No terminal onde está rodando
# Você verá logs como:
# 📥 Processando queue abc-123
# 📤 Enviando billing para +5511999999999
# ✅ Queue abc-123 processada
```

---

### **Verificar no Django Admin**

```python
# python manage.py shell

from apps.billing.models import *

# Ver todas as queues
BillingQueue.objects.all()

# Ver uma específica
queue = BillingQueue.objects.first()
print(f"Status: {queue.status}")
print(f"Progresso: {queue.calculate_progress()}%")
print(f"Enviados: {queue.contacts_sent}/{queue.total_contacts}")

# Ver contatos
billing_contacts = BillingContact.objects.filter(
    billing_campaign__queue=queue
)
for bc in billing_contacts:
    print(f"- {bc.campaign_contact.phone_number}: {bc.campaign_contact.status}")

# Ver mensagem renderizada
print(billing_contacts.first().rendered_message)
```

---

### **Verificar no Chat**

```python
# python manage.py shell

from apps.chat.models import Conversation, Message

# Última conversa criada
conv = Conversation.objects.filter(source='billing').order_by('-created_at').first()
print(f"Conversa: {conv.id}")
print(f"Status: {conv.status}")
print(f"Contato: {conv.phone_number}")

# Mensagens da conversa
for msg in conv.messages.all():
    print(f"\n[{msg.sender}] {msg.content}")
```

---

## 🐛 **TROUBLESHOOTING RÁPIDO**

### **Problema: "API Key inválida"**
```bash
# Verificar se key existe
python manage.py shell
>>> from apps.billing.models import BillingAPIKey
>>> BillingAPIKey.objects.filter(is_active=True)
```

---

### **Problema: "Template não encontrado"**
```python
# Criar template de teste
python manage.py shell
>>> from apps.billing.models import BillingTemplate, TemplateType
>>> from apps.tenancy.models import Tenant
>>> tenant = Tenant.objects.first()
>>> BillingTemplate.objects.filter(
...     tenant=tenant,
...     template_type=TemplateType.OVERDUE,
...     is_active=True
... ).exists()
# Deve retornar True
```

---

### **Problema: "Consumer não está processando"**
```bash
# Verificar se RabbitMQ está rodando
python manage.py shell
>>> from django.conf import settings
>>> print(settings.RABBITMQ_URL)

# Testar conexão
>>> import aio_pika
>>> import asyncio
>>> async def test():
...     conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
...     print("✅ RabbitMQ OK!")
...     await conn.close()
>>> asyncio.run(test())
```

---

### **Problema: "Instância Evolution offline"**
```python
# Verificar instâncias
python manage.py shell
>>> from apps.whatsapp.models import Instance
>>> instances = Instance.objects.filter(is_active=True, status='open')
>>> for i in instances:
...     print(f"{i.id}: {i.instance_name} - {i.status}")
```

---

## ✅ **CHECKLIST DE VALIDAÇÃO**

Antes de considerar o teste concluído, verifique:

- [ ] API Key criada e funcionando
- [ ] Templates cadastrados com variações
- [ ] Consumer rodando sem erros
- [ ] Request retornou `success: true`
- [ ] Queue criada com status `completed`
- [ ] Mensagem apareceu no Evolution API
- [ ] Conversa criada no banco (source='billing')
- [ ] Conversa fechada automaticamente

---

## 🎯 **PRÓXIMOS PASSOS**

1. ✅ **Quick Start completo?** Parabéns!
2. 📚 **Ler documentação completa:**
   - [BILLING_SYSTEM_INDEX.md](./BILLING_SYSTEM_INDEX.md)
   - [Parte 1: Arquitetura + Models](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md)
   - [Parte 2: APIs + Services](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md)
3. 🏗️ **Implementar recursos avançados:**
   - Horário comercial
   - Retry automático
   - Instance health check
   - Prometheus metrics
4. 🚀 **Deploy em staging/produção**

---

**🎉 Sistema funcionando? Agora é hora de escalar!**

