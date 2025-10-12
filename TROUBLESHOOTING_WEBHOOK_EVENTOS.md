# 🔍 TROUBLESHOOTING: Webhook Não Marca Eventos

## ⚠️ **PROBLEMA REPORTADO**

"O botão de editar apareceu, mas não marcou os eventos"

---

## 🎯 **DIAGNÓSTICO**

O código tem **2 camadas** de configuração:

### **Camada 1: Na criação (via `/instance/create`)** ✅
```python
# Linha 331-361 de models.py
POST /instance/create
{
  'webhook': {
    'enabled': True,
    'events': [...10 eventos...],
    'webhook_base64': True
  }
}
```
**Status:** ✅ Implementado corretamente

### **Camada 2: Após criar (via `/webhook/set`)** ⚠️ PODE ESTAR FALHANDO
```python
# Linha 395-397 de models.py
self._update_webhook_after_create(api_url, system_api_key)

# Linha 479-487
POST /webhook/set/{instance_name}
{
  'enabled': True,
  'events': [...],
  'webhookBase64': True
}
```
**Status:** ⚠️ Pode estar falhando silenciosamente

---

## 🔍 **POSSÍVEIS CAUSAS**

### **Causa 1: Endpoint `/webhook/set` não existe na sua versão**
- Evolution API v1 não tem esse endpoint
- Só existe em Evolution API v2+
- **Solução:** Verificar versão da Evolution API

### **Causa 2: Falha silenciosa (exceção capturada)**
```python
except Exception as e:
    print(f"   ⚠️  Erro ao configurar webhook (não crítico): {str(e)}")
    return False  # ← Falha mas continua
```
- O erro é tratado como "não crítico"
- Não impede criação da instância
- **Solução:** Verificar logs

### **Causa 3: URL ou formato incorreto**
- Evolution API espera formato específico
- **Solução:** Verificar documentação

---

## 🧪 **COMO DIAGNOSTICAR**

### **Teste 1: Verificar versão Evolution API**
```bash
# No Postman ou curl:
GET https://seu-evolution.com/

# Verificar campo "version" na resposta
```

### **Teste 2: Testar endpoint manualmente**
```bash
POST https://seu-evolution.com/webhook/set/nome_da_instancia
Headers:
  apikey: SUA_API_KEY
  Content-Type: application/json

Body:
{
  "enabled": true,
  "url": "https://seu-app.up.railway.app/api/notifications/webhook/",
  "webhookByEvents": false,
  "webhookBase64": true,
  "events": [
    "messages.upsert",
    "messages.update",
    "connection.update"
  ]
}

Resposta esperada: 200 ou 201
```

### **Teste 3: Verificar no painel Evolution**
```
1. Acesse painel Evolution
2. Vá em Instâncias
3. Selecione a instância
4. Clique em "Webhook"
5. Verifique:
   - ✅ Enabled: true?
   - ✅ URL está correta?
   - ✅ Events estão marcados?
   - ✅ Base64 está ativo?
```

---

## 🔧 **SOLUÇÕES**

### **Solução 1: Adicionar Logs Detalhados (Debugging)**

Modificar `_update_webhook_after_create()` para logar mais:

```python
def _update_webhook_after_create(self, api_url, api_key):
    """..."""
    import requests
    from django.conf import settings
    
    try:
        webhook_config = {
            'enabled': True,
            'url': f"{getattr(settings, 'BASE_URL', '')}/api/notifications/webhook/",
            'webhookByEvents': False,
            'webhookBase64': True,
            'events': [...]
        }
        
        # 🆕 LOG DETALHADO
        print(f"🔧 Configurando webhook via /webhook/set")
        print(f"   URL: {api_url}/webhook/set/{self.instance_name}")
        print(f"   Webhook URL: {webhook_config['url']}")
        print(f"   Eventos: {len(webhook_config['events'])}")
        
        response = requests.post(
            f"{api_url}/webhook/set/{self.instance_name}",
            headers={
                'Content-Type': 'application/json',
                'apikey': api_key,
            },
            json=webhook_config,
            timeout=10
        )
        
        # 🆕 LOG DA RESPOSTA
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {response.text[:500]}")
        
        if response.status_code in [200, 201]:
            print(f"   ✅ Webhook configurado com sucesso!")
            print(f"   📋 Dados: {response.json()}")
            return True
        else:
            print(f"   ❌ ERRO ao configurar webhook!")
            print(f"   Status: {response.status_code}")
            print(f"   Body: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ EXCEÇÃO ao configurar webhook!")
        print(f"   Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
```

### **Solução 2: Verificar se Evolution v2**

```bash
# Verificar versão da Evolution API
curl https://seu-evolution.com/ | jq .version

# Se for v1.x → Endpoint /webhook/set NÃO existe
# Se for v2.x → Endpoint /webhook/set existe
```

### **Solução 3: Alternativa - Configurar apenas na criação**

Se `/webhook/set` não funciona, confiar apenas na configuração inicial:

```python
# Remover chamada de _update_webhook_after_create
# Manter apenas o webhook completo em /instance/create

# A configuração da linha 335-361 JÁ tem tudo:
'webhook': {
    'enabled': True,
    'webhookBase64': True,
    'events': [...10 eventos...]
}
```

### **Solução 4: Usar endpoint correto da v2**

Segundo documentação v2, o formato correto é:

```python
# Endpoint correto (sem barra no final do api_url)
f"{api_url.rstrip('/')}/webhook/set/{self.instance_name}"

# Headers corretos
headers={
    'Content-Type': 'application/json',
    'apikey': api_key,  # API Master ou da instância
}

# Body correto (camelCase)
{
  "enabled": true,              # boolean
  "url": "https://...",         # string
  "webhookByEvents": false,     # boolean (camelCase!)
  "webhookBase64": true,        # boolean (camelCase!)
  "events": [...]               # array
}
```

---

## 🎯 **SOLUÇÃO IMEDIATA (SEM ESPERAR LOGS)**

Como você está testando agora, vou criar um **comando de diagnóstico**:

### **Comando Django Shell:**
```python
# Entrar no shell
docker exec -it alrea_sense_backend_local python manage.py shell

# Testar webhook manualmente
from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

# Pegar instância
instance = WhatsAppInstance.objects.first()
print(f"Instância: {instance.instance_name}")

# Pegar Evolution config
evo = EvolutionConnection.objects.filter(is_active=True).first()
print(f"Evolution URL: {evo.base_url}")

# Testar chamada de webhook
success = instance.update_webhook_config()
print(f"Sucesso: {success}")
print(f"Erro: {instance.last_error}")
```

---

## 📊 **CHECKLIST DE VERIFICAÇÃO**

### **No Evolution API:**
- [ ] Versão é v2.x? (v1 não tem /webhook/set)
- [ ] Endpoint /webhook/set existe?
- [ ] API Key tem permissão?
- [ ] BASE_URL está configurado corretamente?

### **No Código:**
- [x] Webhook na criação tem eventos ✅
- [x] Webhook na criação tem base64 ✅
- [x] Método _update_webhook_after_create existe ✅
- [x] Método é chamado após criar ✅
- [ ] Logs mostram erro? (precisa verificar)

### **Testes Manuais:**
- [ ] Criar instância e verificar logs
- [ ] Chamar update_webhook_config() no shell
- [ ] Testar endpoint /webhook/set direto (Postman)
- [ ] Verificar no painel Evolution

---

## 💡 **HIPÓTESE MAIS PROVÁVEL**

**O endpoint `/webhook/set` pode estar retornando erro 404** (não existe na versão da Evolution).

**Solução:**
1. Verificar versão Evolution API
2. Se v1: Remover chamada de _update_webhook_after_create (confiar só no create)
3. Se v2: Adicionar logs para ver erro exato

---

## 🚀 **AÇÃO RECOMENDADA**

**Opção A (Rápida):** Remover chamada de `/webhook/set` e confiar só na criação
**Opção B (Completa):** Adicionar logs detalhados e investigar

---

**📋 Qual versão da Evolution API você está usando? v1 ou v2?**



