# 🎯 WEBHOOK PARA RASTREAMENTO DE ENTREGAS - PRIORIDADE 1

## 📋 **OBJETIVO:**

Implementar o rastreamento de status das mensagens de campanhas:
- ✅ **Enviada** (sent) - Já temos (Celery task)
- ✅ **Entregue** (delivered) - Via webhook
- ✅ **Lida** (read) - Via webhook
- ✅ **Falhou** (failed) - Via webhook (timeout ou erro)

**NÃO incluir nesta implementação:**
- ❌ Respostas de contatos (CampaignReply) → Semana que vem
- ❌ Análise IA (Sense) → Futuro
- ❌ Chat visual → Futuro

---

## 🔄 **FLUXO COMPLETO:**

```
1. CELERY TASK ENVIA MENSAGEM
   ├─ POST /message/sendText/{instance}
   ├─ Recebe response: { "key": { "id": "3EB0B431..." } }
   ├─ Salva em CampaignContact:
   │   ├─ whatsapp_message_id = "3EB0B431..."
   │   ├─ status = 'sent'
   │   └─ sent_at = now()
   └─ Campaign.sent_count += 1

2. WHATSAPP ENTREGA MENSAGEM (15 segundos depois)
   ├─ Evolution API recebe status do WhatsApp
   └─ Evolution envia webhook para nossa app

3. WEBHOOK RECEBE UPDATE
   POST /api/webhooks/evolution/
   {
     "event": "messages.update",
     "instance": "tenant_abc_inst_1",
     "data": {
       "key": { "id": "3EB0B431..." },
       "update": { "status": 2 }  ← 2=delivered, 3=read
     }
   }

4. PROCESSAR UPDATE (Backend)
   ├─ Buscar: CampaignContact.objects.get(whatsapp_message_id="3EB0B431...")
   ├─ Atualizar:
   │   ├─ status = 'delivered'
   │   ├─ delivered_at = now()
   │   └─ save()
   ├─ Atualizar Campaign:
   │   └─ delivered_count += 1
   ├─ Atualizar Instance:
   │   └─ health_score (aumentar)
   └─ Log: CampaignLog.log_message_delivered(...)

5. FRONTEND ATUALIZA (Polling ou WebSocket)
   ├─ Dashboard atualiza métricas
   └─ Página da campanha atualiza contadores
```

---

## 📊 **STATUS CODES DO WHATSAPP:**

```python
WHATSAPP_STATUS_CODES = {
    0: 'error',      # Erro
    1: 'pending',    # Pendente (servidor Evolution recebeu)
    2: 'delivered',  # Entregue (chegou no WhatsApp do contato)
    3: 'read',       # Lida (contato abriu)
}
```

---

## 🗄️ **CAMPOS JÁ EXISTENTES (CampaignContact):**

```python
class CampaignContact(models.Model):
    # ... campos existentes ...
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendente'),
            ('sending', 'Enviando'),
            ('sent', 'Enviada'),
            ('delivered', 'Entregue'),  ← Atualizado via webhook
            ('read', 'Lida'),            ← Atualizado via webhook
            ('failed', 'Falhou'),
        ]
    )
    
    # Timestamps (já existem!)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)  ← Atualizado via webhook
    read_at = models.DateTimeField(null=True, blank=True)        ← Atualizado via webhook
    failed_at = models.DateTimeField(null=True, blank=True)
    
    # ID crucial para cruzamento
    whatsapp_message_id = models.CharField(max_length=255)  ← CHAVE!
```

**✅ Modelo já está pronto! Não precisa migration!**

---

## 📊 **CAMPOS JÁ EXISTENTES (Campaign):**

```python
class Campaign(models.Model):
    # ... campos existentes ...
    
    # Contadores (já existem!)
    total_contacts = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)  ← Atualizado via webhook
    read_count = models.IntegerField(default=0)        ← Atualizado via webhook
    failed_count = models.IntegerField(default=0)
    
    # Métricas calculadas (properties já existem?)
    @property
    def delivery_rate(self):
        if self.sent_count == 0:
            return 0
        return (self.delivered_count / self.sent_count) * 100
    
    @property
    def read_rate(self):
        if self.delivered_count == 0:
            return 0
        return (self.read_count / self.delivered_count) * 100
```

**✅ Modelo já está pronto! Só atualizar contadores!**

---

## 🔧 **IMPLEMENTAÇÃO:**

### **1. Criar Webhook Handler (Backend)**

**Arquivo:** `backend/apps/campaigns/webhook_handler.py` (NOVO)

```python
"""
Webhook handler para eventos de campanhas (Flow).
Focado em rastreamento de entregas: sent → delivered → read
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction

from apps.campaigns.models import Campaign, CampaignContact, CampaignLog
from apps.notifications.models import WhatsAppInstance
from apps.contacts.models import Contact

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def campaign_webhook_handler(request):
    """
    Handler principal para webhooks do Evolution API (campanhas).
    Processa apenas messages.update para rastreamento de entregas.
    """
    try:
        data = json.loads(request.body)
        event = data.get('event')
        
        logger.info(f"[WEBHOOK] Evento recebido: {event}")
        
        # Roteamento de eventos
        if event == 'messages.update':
            return handle_message_status_update(data)
        
        else:
            # Ignorar outros eventos (Sense processará depois)
            logger.debug(f"[WEBHOOK] Evento ignorado: {event}")
            return JsonResponse({'status': 'ignored', 'event': event})
    
    except json.JSONDecodeError as e:
        logger.error(f"[WEBHOOK] JSON inválido: {e}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    except Exception as e:
        logger.error(f"[WEBHOOK] Erro: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


def handle_message_status_update(data):
    """
    Processa atualizações de status de mensagens.
    
    Payload esperado:
    {
        "event": "messages.update",
        "instance": "tenant_abc_inst_1",
        "data": {
            "key": {
                "id": "3EB0B431E4B3F7E7BE49E97F7B8E5C8B"
            },
            "update": {
                "status": 2  # 2=delivered, 3=read
            }
        }
    }
    """
    try:
        message_id = data['data']['key']['id']
        status_code = data['data']['update'].get('status')
        instance_name = data.get('instance')
        
        logger.info(f"[WEBHOOK] Status update: message_id={message_id}, status={status_code}")
        
        # Buscar CampaignContact pelo whatsapp_message_id
        try:
            campaign_contact = CampaignContact.objects.select_related(
                'campaign', 'contact', 'instance_used'
            ).get(whatsapp_message_id=message_id)
        except CampaignContact.DoesNotExist:
            # Mensagem não é de campanha (pode ser do Sense ou manual)
            logger.debug(f"[WEBHOOK] Mensagem {message_id} não é de campanha")
            return JsonResponse({'status': 'not_campaign_message'})
        
        # Mapear status code para status text
        STATUS_MAP = {
            2: 'delivered',
            3: 'read',
            0: 'failed',
        }
        
        new_status = STATUS_MAP.get(status_code)
        if not new_status:
            logger.warning(f"[WEBHOOK] Status code desconhecido: {status_code}")
            return JsonResponse({'status': 'unknown_status_code', 'code': status_code})
        
        # Evitar reprocessamento (se já está neste status ou posterior)
        STATUS_ORDER = ['pending', 'sending', 'sent', 'delivered', 'read', 'failed']
        current_index = STATUS_ORDER.index(campaign_contact.status) if campaign_contact.status in STATUS_ORDER else 0
        new_index = STATUS_ORDER.index(new_status)
        
        if new_status != 'failed' and new_index <= current_index:
            logger.debug(f"[WEBHOOK] Status já processado: {campaign_contact.status} -> {new_status}")
            return JsonResponse({'status': 'already_processed'})
        
        # Processar atualização
        with transaction.atomic():
            old_status = campaign_contact.status
            campaign = campaign_contact.campaign
            instance = campaign_contact.instance_used
            contact = campaign_contact.contact
            
            # Atualizar CampaignContact
            campaign_contact.status = new_status
            
            if new_status == 'delivered':
                campaign_contact.delivered_at = timezone.now()
                campaign_contact.save(update_fields=['status', 'delivered_at'])
                
                # Atualizar contador da campanha
                Campaign.objects.filter(id=campaign.id).update(
                    delivered_count=models.F('delivered_count') + 1
                )
                
                # Health da instância
                if instance:
                    instance.msgs_delivered_today = models.F('msgs_delivered_today') + 1
                    instance.consecutive_errors = 0  # Reset
                    instance.save(update_fields=['msgs_delivered_today', 'consecutive_errors'])
                
                # Log
                CampaignLog.log_message_delivered(
                    campaign=campaign,
                    instance=instance,
                    contact=contact,
                    campaign_contact=campaign_contact
                )
                
                logger.info(f"[WEBHOOK] Mensagem entregue: {contact.name} ({campaign.name})")
            
            elif new_status == 'read':
                campaign_contact.read_at = timezone.now()
                campaign_contact.save(update_fields=['status', 'read_at'])
                
                # Atualizar contador da campanha
                Campaign.objects.filter(id=campaign.id).update(
                    read_count=models.F('read_count') + 1
                )
                
                # Health da instância
                if instance:
                    instance.msgs_read_today = models.F('msgs_read_today') + 1
                    instance.save(update_fields=['msgs_read_today'])
                
                # Log
                CampaignLog.log_message_read(
                    campaign=campaign,
                    instance=instance,
                    contact=contact,
                    campaign_contact=campaign_contact
                )
                
                # Atualizar engajamento do contato
                contact.last_interaction_date = timezone.now()
                contact.save(update_fields=['last_interaction_date'])
                
                logger.info(f"[WEBHOOK] Mensagem lida: {contact.name} ({campaign.name})")
            
            elif new_status == 'failed':
                campaign_contact.failed_at = timezone.now()
                campaign_contact.error_message = data.get('error', 'Erro desconhecido')
                campaign_contact.save(update_fields=['status', 'failed_at', 'error_message'])
                
                # Atualizar contador da campanha
                Campaign.objects.filter(id=campaign.id).update(
                    failed_count=models.F('failed_count') + 1
                )
                
                # Health da instância (degradar)
                if instance:
                    instance.msgs_failed_today = models.F('msgs_failed_today') + 1
                    instance.consecutive_errors = models.F('consecutive_errors') + 1
                    instance.save(update_fields=['msgs_failed_today', 'consecutive_errors'])
                
                # Log
                CampaignLog.log_message_failed(
                    campaign=campaign,
                    instance=instance,
                    contact=contact,
                    campaign_contact=campaign_contact,
                    error_msg=campaign_contact.error_message
                )
                
                logger.warning(f"[WEBHOOK] Mensagem falhou: {contact.name} ({campaign.name})")
        
        return JsonResponse({
            'status': 'updated',
            'message_id': message_id,
            'old_status': old_status,
            'new_status': new_status,
            'campaign': str(campaign.id),
            'contact': contact.name
        })
    
    except KeyError as e:
        logger.error(f"[WEBHOOK] Campo ausente no payload: {e}")
        return JsonResponse({'error': f'Missing field: {e}'}, status=400)
    
    except Exception as e:
        logger.error(f"[WEBHOOK] Erro ao processar update: {e}", exc_info=True)
        return JsonResponse({'error': 'Processing failed'}, status=500)
```

---

### **2. Registrar URL (Backend)**

**Arquivo:** `backend/alrea_sense/urls.py`

```python
from django.urls import path
from apps.campaigns import webhook_handler

urlpatterns = [
    # ... URLs existentes ...
    
    # Webhook para campanhas (Flow)
    path(
        'api/webhooks/evolution/',
        webhook_handler.campaign_webhook_handler,
        name='campaign_webhook'
    ),
]
```

**URL final:** `https://alreasense-production.up.railway.app/api/webhooks/evolution/`

---

### **3. Configurar Webhook na Evolution (Railway)**

**Quando criar instância:**
- URL: `https://alreasense-production.up.railway.app/api/webhooks/evolution/`
- Eventos: ✅ `messages.update` (essencial!)
- Ativo: ✅ Sim
- Base64: ✅ Sim

**Já está implementado em `WhatsAppInstance.generate_qr_code()`? Verificar!**

---

### **4. Adicionar F() Import (Se necessário)**

**Arquivo:** `backend/apps/campaigns/webhook_handler.py`

```python
from django.db.models import F
```

Para usar:
```python
Campaign.objects.filter(id=campaign.id).update(
    delivered_count=F('delivered_count') + 1
)
```

**Vantagem:** Atômica, evita race conditions.

---

### **5. Verificar Logs do CampaignLog (Se faltam métodos)**

**Arquivo:** `backend/apps/campaigns/models.py`

Verificar se existem:
- ✅ `CampaignLog.log_message_delivered()`
- ✅ `CampaignLog.log_message_read()`
- ✅ `CampaignLog.log_message_failed()`

**Já existem! Ver linhas 493-548 do models.py**

---

## 🧪 **TESTES NO RAILWAY:**

### **1. Testar Webhook Manualmente (cURL):**

```bash
curl -X POST https://alreasense-production.up.railway.app/api/webhooks/evolution/ \
  -H "Content-Type: application/json" \
  -d '{
    "event": "messages.update",
    "instance": "seu_instance_name",
    "data": {
      "key": {
        "id": "SEU_MESSAGE_ID_REAL"
      },
      "update": {
        "status": 2
      }
    }
  }'
```

**Resultado esperado:**
```json
{
  "status": "updated",
  "message_id": "SEU_MESSAGE_ID_REAL",
  "old_status": "sent",
  "new_status": "delivered",
  "campaign": "uuid-da-campanha",
  "contact": "João Silva"
}
```

---

### **2. Testar Campanha Real:**

**Passo a passo:**

1. **Criar campanha:**
   - 1 ou 2 contatos (seu número de teste)
   - 1 mensagem simples
   - Agendar para daqui 1 minuto

2. **Iniciar campanha:**
   - Status: draft → active
   - Celery envia mensagem
   - `CampaignContact.status = 'sent'`
   - `whatsapp_message_id` salvo

3. **Aguardar webhook (15-30 segundos):**
   - Evolution recebe confirmação do WhatsApp
   - Evolution envia webhook para nossa app
   - Backend atualiza: `status = 'delivered'`

4. **Abrir mensagem no WhatsApp:**
   - Você abre a mensagem
   - WhatsApp notifica Evolution
   - Evolution envia webhook
   - Backend atualiza: `status = 'read'`

5. **Verificar no Dashboard:**
   - Campanha: 1 enviada, 1 entregue, 1 lida ✅
   - Logs: "Mensagem entregue", "Mensagem lida"

---

### **3. Verificar Logs (Railway):**

```bash
# Via Railway CLI:
railway logs --tail 100

# Ou via Dashboard:
# Railway → Seu projeto → Logs (tempo real)
```

**Buscar por:**
```
[WEBHOOK] Evento recebido: messages.update
[WEBHOOK] Status update: message_id=..., status=2
[WEBHOOK] Mensagem entregue: João Silva (Teste Campaign)
```

---

## 📊 **VERIFICAÇÕES:**

### **Checklist Backend:**

- [ ] Arquivo `webhook_handler.py` criado
- [ ] URL `/api/webhooks/evolution/` configurada
- [ ] Import `from django.db.models import F` adicionado
- [ ] Métodos de log existem em `CampaignLog`
- [ ] Fields em `CampaignContact`: `delivered_at`, `read_at`
- [ ] Fields em `Campaign`: `delivered_count`, `read_count`
- [ ] Deploy no Railway

---

### **Checklist Evolution API:**

- [ ] Webhook URL configurada: `https://alreasense-production.up.railway.app/api/webhooks/evolution/`
- [ ] Evento `messages.update` ativado ✅
- [ ] Webhook ativo ✅
- [ ] Base64 ativo ✅

---

### **Checklist Frontend:**

- [ ] Dashboard mostra: Enviadas, Entregues, Lidas
- [ ] Página da campanha mostra contadores atualizados
- [ ] Taxa de entrega: `(delivered / sent) * 100`
- [ ] Taxa de leitura: `(read / delivered) * 100`

---

## 🚀 **PRÓXIMOS PASSOS (PÓS-RAILWAY):**

### **Semana que vem:**
1. ✅ Webhook de entregas funcionando
2. ⏳ Implementar `CampaignReply` (respostas de contatos)
3. ⏳ Aba "Respostas" na campanha
4. ⏳ Notificações de respostas

---

## 📋 **RESUMO EXECUTIVO:**

```
┌─────────────────────────────────────────────────────┐
│  WEBHOOK DE ENTREGAS - IMPLEMENTAÇÃO                │
├─────────────────────────────────────────────────────┤
│  OBJETIVO:                                           │
│  Rastrear status: sent → delivered → read           │
│                                                      │
│  ARQUIVOS:                                           │
│  ✅ backend/apps/campaigns/webhook_handler.py (NOVO)│
│  ✅ backend/alrea_sense/urls.py (atualizar)         │
│                                                      │
│  EVENTO ESSENCIAL:                                   │
│  ✅ messages.update (status 2=delivered, 3=read)    │
│                                                      │
│  CHAVE DE CRUZAMENTO:                                │
│  whatsapp_message_id (salvo no envio, busca no hook)│
│                                                      │
│  ATUALIZA:                                           │
│  ├─ CampaignContact (status, timestamps)            │
│  ├─ Campaign (contadores)                           │
│  ├─ WhatsAppInstance (health)                       │
│  └─ CampaignLog (auditoria)                         │
│                                                      │
│  TESTES:                                             │
│  1. cURL manual                                      │
│  2. Campanha real (seu número)                      │
│  3. Verificar logs (Railway)                        │
│  4. Dashboard atualiza métricas                     │
│                                                      │
│  NÃO INCLUI (AGORA):                                 │
│  ❌ Respostas (CampaignReply) → Semana que vem     │
│  ❌ Opt-out automático → Semana que vem            │
│  ❌ Chat visual → Futuro                            │
└─────────────────────────────────────────────────────┘
```

---

**📄 Criei `IMPLEMENTACAO_WEBHOOK_ENTREGAS.md` com implementação completa!**

**Está pronto para Railway! 🚀 Qualquer dúvida, só chamar!**


