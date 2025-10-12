# 🔧 PROMPT: Método para Atualizar Webhook de Instância Existente

## 🎯 **OBJETIVO**

Adicionar método para atualizar configuração de webhook em instâncias **já criadas**, usando o endpoint `/webhook/set/{instance}` da Evolution API.

## 📚 **REFERÊNCIA**

Segundo a [documentação oficial](https://doc.evolution-api.com/v2/api-reference/webhook/set):

```bash
POST /webhook/set/{instance}
Headers:
  apikey: <api-key>
  Content-Type: application/json

Body:
{
  "enabled": true,
  "url": "https://example.com/webhook",
  "webhookByEvents": false,
  "webhookBase64": true,
  "events": [
    "messages.upsert",
    "messages.update",
    "connection.update",
    ...
  ]
}
```

---

## 📝 **IMPLEMENTAÇÃO**

### **Arquivo:** `backend/apps/notifications/models.py`

### **Adicionar método na classe `WhatsAppInstance`:**

```python
def update_webhook_config(self):
    """
    Atualiza configuração de webhook em instância já existente.
    Útil para:
    - Atualizar URL do webhook
    - Adicionar/remover eventos
    - Ativar/desativar base64
    
    Returns:
        bool: True se sucesso, False se erro
    """
    import requests
    from django.conf import settings
    from apps.connections.models import EvolutionConnection
    
    # Buscar servidor Evolution
    evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
    if not evolution_server or not evolution_server.base_url or not evolution_server.api_key:
        self.last_error = 'Servidor Evolution não configurado'
        self.save()
        return False
    
    api_url = evolution_server.base_url.rstrip('/')
    api_key = evolution_server.api_key
    
    try:
        print(f"🔧 Atualizando webhook para instância: {self.instance_name}")
        
        # Configuração completa do webhook
        webhook_config = {
            'enabled': True,
            'url': f"{getattr(settings, 'BASE_URL', '')}/api/notifications/webhook/",
            'webhookByEvents': False,
            'webhookBase64': True,
            'events': [
                # Mensagens
                'messages.upsert',
                'messages.update',
                'messages.delete',
                
                # Conexão
                'connection.update',
                
                # Presença
                'presence.update',
                
                # Contatos
                'contacts.upsert',
                'contacts.update',
                
                # Conversas
                'chats.upsert',
                'chats.update',
                'chats.delete',
                
                # Grupos (opcional)
                'groups.upsert',
                'groups.update',
                'group-participants.update',
            ]
        }
        
        response = requests.post(
            f"{api_url}/webhook/set/{self.instance_name}",
            headers={
                'Content-Type': 'application/json',
                'apikey': api_key,
            },
            json=webhook_config,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Webhook atualizado com sucesso!")
            print(f"📋 Resposta: {response.json()}")
            
            # Log
            WhatsAppConnectionLog.objects.create(
                instance=self,
                action='webhook_updated',
                details=f'Webhook atualizado: {len(webhook_config["events"])} eventos ativos',
                user=None
            )
            
            return True
        else:
            error_msg = f'Erro ao atualizar webhook (Status {response.status_code}): {response.text[:200]}'
            print(f"❌ {error_msg}")
            self.last_error = error_msg
            self.save()
            return False
            
    except Exception as e:
        error_msg = f'Exceção ao atualizar webhook: {str(e)}'
        print(f"⚠️  {error_msg}")
        self.last_error = error_msg
        self.save()
        return False


def verify_webhook_config(self):
    """
    Verifica configuração atual do webhook na Evolution API.
    
    Returns:
        dict|None: Configuração do webhook ou None se erro
    """
    import requests
    from apps.connections.models import EvolutionConnection
    
    # Buscar servidor Evolution
    evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
    if not evolution_server:
        return None
    
    api_url = evolution_server.base_url.rstrip('/')
    api_key = evolution_server.api_key
    
    try:
        response = requests.get(
            f"{api_url}/webhook/find/{self.instance_name}",
            headers={'apikey': api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            webhook_data = response.json()
            print(f"📋 Webhook atual: {webhook_data}")
            return webhook_data
        else:
            print(f"⚠️  Webhook não encontrado ou erro: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️  Erro ao verificar webhook: {str(e)}")
        return None
```

---

## 🎯 **CASOS DE USO:**

### **Caso 1: Atualizar webhook de instância antiga**

```python
# Django shell ou management command
from apps.notifications.models import WhatsAppInstance

# Pegar todas as instâncias
instances = WhatsAppInstance.objects.filter(status='active')

for instance in instances:
    print(f"Atualizando webhook: {instance.instance_name}")
    success = instance.update_webhook_config()
    if success:
        print(f"  ✅ Atualizado")
    else:
        print(f"  ❌ Erro: {instance.last_error}")
```

### **Caso 2: Verificar configuração atual**

```python
instance = WhatsAppInstance.objects.first()
config = instance.verify_webhook_config()

if config:
    print(f"URL: {config.get('webhook', {}).get('url')}")
    print(f"Enabled: {config.get('webhook', {}).get('enabled')}")
    print(f"Events: {config.get('webhook', {}).get('events')}")
    print(f"Base64: {config.get('webhook', {}).get('webhookBase64')}")
```

### **Caso 3: Adicionar via admin action**

```python
# backend/apps/notifications/admin.py

@admin.action(description='Atualizar configuração de webhook')
def update_webhook(modeladmin, request, queryset):
    updated = 0
    errors = 0
    
    for instance in queryset:
        if instance.update_webhook_config():
            updated += 1
        else:
            errors += 1
    
    modeladmin.message_user(
        request,
        f'{updated} webhooks atualizados. {errors} erros.'
    )

# Registrar action
class WhatsAppInstanceAdmin(admin.ModelAdmin):
    actions = [update_webhook, ...]
```

---

## 🔄 **FLUXO COMPLETO:**

```
┌─────────────────────────────────────────────────────────────┐
│  CRIAÇÃO DE INSTÂNCIA                                       │
├─────────────────────────────────────────────────────────────┤
│  1. POST /instance/create                                   │
│     • webhook configurado na criação ✅                     │
│     • enabled: true                                         │
│     • events: 10 eventos                                    │
│     • webhookBase64: true                                   │
│                                                             │
│  2. (Opcional) POST /webhook/set/{instance}                │
│     • Atualizar webhook depois                              │
│     • Adicionar/remover eventos                             │
│     • Ativar/desativar                                      │
│                                                             │
│  3. GET /webhook/find/{instance}                           │
│     • Verificar configuração atual                          │
│     • Auditar eventos ativos                                │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ **BENEFÍCIOS DO MÉTODO UPDATE:**

| Benefício | Descrição |
|-----------|-----------|
| **Migração** | Atualizar instâncias antigas sem recriar |
| **Flexibilidade** | Ativar/desativar eventos dinamicamente |
| **Auditoria** | Verificar configuração atual |
| **Manutenção** | Corrigir webhooks quebrados |
| **Evolução** | Adicionar novos eventos quando Evolution API lançar |

---

## 🎯 **RECOMENDAÇÃO:**

Como você vai subir na Railway, sugiro:

1. ✅ **Manter código atual** (webhook na criação já está completo)
2. 🆕 **Adicionar método `update_webhook_config()`** para futuras atualizações
3. 🆕 **Adicionar método `verify_webhook_config()`** para auditoria
4. 🆕 **Criar management command** para atualizar webhooks em massa

---

## 📋 **RESUMO:**

```
✅ Código atual (criação) → Perfeito!
   • enabled: true
   • webhookBase64: true
   • events: 10 eventos

🆕 Documentação mostra endpoint adicional:
   • POST /webhook/set/{instance}
   • Permite atualizar DEPOIS da criação
   • Útil para instâncias antigas
   • Útil para ajustes futuros
```

---

**📄 Criei `PROMPT_UPDATE_WEBHOOK_METHOD.md` com o código completo dos métodos `update_webhook_config()` e `verify_webhook_config()` prontos para implementar quando precisar!**


