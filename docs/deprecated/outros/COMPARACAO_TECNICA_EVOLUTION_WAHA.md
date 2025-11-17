# 🔬 COMPARAÇÃO TÉCNICA DETALHADA: EVOLUTION API vs WAHA

> **Complemento à Análise de Migração**  
> **Data:** 22 de Outubro de 2025  

---

## 📡 ENDPOINTS - COMPARAÇÃO COMPLETA

### 1. GERENCIAMENTO DE INSTÂNCIAS/SESSÕES

#### Criar Instância

**Evolution API:**
```http
POST https://evo.rbtec.com.br/instance/create
Headers:
  apikey: <MASTER_API_KEY>
  Content-Type: application/json

Body:
{
  "instanceName": "6c663f61-e344-4296-ab7a-f4fd6844749e",
  "qrcode": true,
  "integration": "WHATSAPP-BAILEYS",
  "webhook": {
    "enabled": true,
    "url": "https://backend.railway.app/api/connections/webhooks/evolution/",
    "webhook_by_events": false,
    "webhook_base64": true,
    "events": [
      "messages.upsert",
      "messages.update",
      "connection.update",
      "presence.update",
      "contacts.update"
    ]
  },
  "settings": {
    "reject_call": true,
    "msg_call": "Desculpe, não atendemos chamadas.",
    "groups_ignore": false,
    "always_online": false,
    "read_messages": false
  }
}

Response: 200 OK
{
  "instance": {
    "instanceName": "6c663f61-e344-4296-ab7a-f4fd6844749e",
    "apikey": "B6D711FCDE4D4FD5936544120E713976",  ← API KEY ESPECÍFICA!
    "integration": "WHATSAPP-BAILEYS",
    "status": "created"
  },
  "hash": {
    "apikey": "B6D711..."
  },
  "webhook": {
    "url": "https://backend.railway.app/api/connections/webhooks/evolution/",
    "enabled": true
  }
}
```

**WAHA:**
```http
POST https://waha.server.com/api/sessions/start
Headers:
  X-Api-Key: <GLOBAL_API_KEY>  ← SÓ TEM GLOBAL!
  Content-Type: application/json

Body:
{
  "name": "6c663f61-e344-4296-ab7a-f4fd6844749e",
  "config": {
    "proxy": null,
    "webhooks": [
      {
        "url": "https://backend.railway.app/api/webhooks/waha/",
        "events": [
          "message",
          "message.status",
          "session.status"
        ]
      }
    ]
  }
}

Response: 200 OK
{
  "name": "6c663f61-e344-4296-ab7a-f4fd6844749e",
  "status": "STARTING",
  "config": {
    "webhooks": [...]
  }
  // ❌ NÃO retorna API key específica!
}
```

**Diferenças Críticas:**
- ❌ WAHA não retorna API key específica da sessão
- ⚠️ Campo `instanceName` vs `name`
- ⚠️ Estrutura de webhook diferente
- ⚠️ Eventos de webhook diferentes

---

#### Buscar QR Code

**Evolution API:**
```http
GET https://evo.rbtec.com.br/instance/connect/{instanceName}
Headers:
  apikey: <INSTANCE_API_KEY>  ← Pode usar Master ou Specific

Response: 200 OK
{
  "code": "2@aB1cD2eF3...",  ← Base64 do QR
  "base64": "data:image/png;base64,iVBORw0KGgo..."
}
```

**WAHA:**
```http
GET https://waha.server.com/api/{session}/auth/qr
Headers:
  X-Api-Key: <GLOBAL_API_KEY>

Response: 200 OK
{
  "value": "2@aB1cD2eF3...",  ← QR code text
  "base64": "data:image/png;base64,iVBORw0KGgo..."
}
```

**Diferenças:**
- ⚠️ Campo `code` vs `value`
- ✅ `base64` é igual

---

#### Verificar Status de Conexão

**Evolution API:**
```http
GET https://evo.rbtec.com.br/instance/connectionState/{instanceName}
Headers:
  apikey: <INSTANCE_API_KEY>

Response: 200 OK
{
  "instance": "6c663f61-e344-4296-ab7a-f4fd6844749e",
  "state": "open"  ← Estados: close, connecting, open
}
```

**WAHA:**
```http
GET https://waha.server.com/api/{session}
Headers:
  X-Api-Key: <GLOBAL_API_KEY>

Response: 200 OK
{
  "name": "6c663f61-e344-4296-ab7a-f4fd6844749e",
  "status": "WORKING",  ← Estados: STOPPED, STARTING, SCAN_QR_CODE, WORKING, FAILED
  "me": {
    "id": "5517991253112@c.us",
    "pushName": "Paulo Bernal"
  }
}
```

**Diferenças:**
- ⚠️ Estados diferentes!
  * Evolution: `close`, `connecting`, `open`
  * WAHA: `STOPPED`, `STARTING`, `SCAN_QR_CODE`, `WORKING`, `FAILED`
- ✅ WAHA já retorna dados do WhatsApp conectado

---

#### Listar Instâncias

**Evolution API:**
```http
GET https://evo.rbtec.com.br/instance/fetchInstances
Headers:
  apikey: <MASTER_API_KEY>

Response: 200 OK
[
  {
    "instance": {
      "instanceName": "instance-1",
      "status": "open"
    },
    "hash": {
      "apikey": "ABC123..."
    }
  },
  {
    "instance": {
      "instanceName": "instance-2",
      "status": "close"
    }
  }
]
```

**WAHA:**
```http
GET https://waha.server.com/api/sessions
Headers:
  X-Api-Key: <GLOBAL_API_KEY>

Response: 200 OK
[
  {
    "name": "instance-1",
    "status": "WORKING",
    "me": {
      "id": "5511999999999@c.us",
      "pushName": "User 1"
    }
  },
  {
    "name": "instance-2",
    "status": "STOPPED"
  }
]
```

**Diferenças:**
- ⚠️ Estrutura flat vs nested
- ⚠️ Campos diferentes

---

#### Deletar Instância

**Evolution API:**
```http
DELETE https://evo.rbtec.com.br/instance/delete/{instanceName}
Headers:
  apikey: <MASTER_API_KEY>

Response: 200 OK
{
  "status": "deleted",
  "instance": "instance-name"
}
```

**WAHA:**
```http
DELETE https://waha.server.com/api/{session}
Headers:
  X-Api-Key: <GLOBAL_API_KEY>

Response: 200 OK
{
  "name": "instance-name",
  "status": "deleted"
}
```

**Diferenças:**
- ✅ Funcionalmente equivalente

---

### 2. ENVIO DE MENSAGENS

#### Enviar Texto

**Evolution API:**
```http
POST https://evo.rbtec.com.br/message/sendText/{instanceName}
Headers:
  apikey: <INSTANCE_API_KEY>  ← Específica ou Master
  Content-Type: application/json

Body:
{
  "number": "5517991253112",  ← Sem @c.us
  "text": "Olá, esta é uma mensagem de teste!",
  "delay": 1200  ← Delay antes de enviar (opcional)
}

Response: 200 OK
{
  "key": {
    "remoteJid": "5517991253112@s.whatsapp.net",
    "fromMe": true,
    "id": "3EB0C5A71BEFC4B5774D"
  },
  "message": {
    "conversation": "Olá, esta é uma mensagem de teste!"
  },
  "messageTimestamp": 1697200000,
  "status": "PENDING"
}
```

**WAHA:**
```http
POST https://waha.server.com/api/sendText
Headers:
  X-Api-Key: <GLOBAL_API_KEY>
  Content-Type: application/json

Body:
{
  "session": "6c663f61-e344-4296-ab7a-f4fd6844749e",  ← Obrigatório!
  "chatId": "5517991253112@c.us",  ← Precisa do @c.us
  "text": "Olá, esta é uma mensagem de teste!"
}

Response: 201 Created
{
  "id": "true_5517991253112@c.us_3EB0C5A71BEFC4B5774D",
  "timestamp": 1697200000,
  "body": "Olá, esta é uma mensagem de teste!",
  "fromMe": true,
  "to": "5517991253112@c.us",
  "ack": 1  ← 1=SENT, 2=DELIVERED, 3=READ
}
```

**Diferenças:**
- ❌ `number` vs `chatId` (formato diferente)
- ❌ Campo `session` obrigatório no body
- ❌ Endpoint não usa path param
- ⚠️ IDs completamente diferentes
- ⚠️ Status diferentes (`PENDING` vs `ack: 1`)

**Código Atual:**
```python
# backend/apps/campaigns/rabbitmq_consumer.py:634
url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
headers = {
    "Content-Type": "application/json",
    "apikey": instance.api_key  ← Precisa mudar!
}
message_data = {
    "number": contact_phone,  ← Precisa adicionar @c.us
    "text": message_text
}
```

**Código Novo (WAHA):**
```python
url = f"{waha_url}/api/sendText"  ← Sem path param!
headers = {
    "Content-Type": "application/json",
    "X-Api-Key": global_api_key  ← Global!
}
message_data = {
    "session": instance.session_name,  ← Novo campo!
    "chatId": f"{contact_phone}@c.us",  ← Formato diferente
    "text": message_text
}
```

---

#### Enviar Imagem

**Evolution API:**
```http
POST https://evo.rbtec.com.br/message/sendMedia/{instanceName}
Headers:
  apikey: <INSTANCE_API_KEY>
  Content-Type: application/json

Body:
{
  "number": "5517991253112",
  "mediatype": "image",
  "media": "https://example.com/image.jpg"  ← URL ou Base64
  // OU
  "media": "data:image/jpeg;base64,/9j/4AAQ..."
}

Response: 200 OK
{
  "key": {...},
  "message": {
    "imageMessage": {
      "url": "...",
      "mimetype": "image/jpeg"
    }
  }
}
```

**WAHA:**
```http
POST https://waha.server.com/api/sendImage
Headers:
  X-Api-Key: <GLOBAL_API_KEY>
  Content-Type: application/json

Body:
{
  "session": "6c663f61-e344-4296-ab7a-f4fd6844749e",
  "chatId": "5517991253112@c.us",
  "file": {
    "url": "https://example.com/image.jpg"
    // OU
    "mimetype": "image/jpeg",
    "filename": "photo.jpg",
    "data": "/9j/4AAQ..."  ← Base64 sem prefixo!
  },
  "caption": "Legenda da imagem"  ← Opcional
}

Response: 201 Created
{
  "id": "...",
  "timestamp": 1697200000,
  "ack": 1
}
```

**Diferenças:**
- ❌ Endpoint diferente (`/message/sendMedia` vs `/api/sendImage`)
- ❌ Campo `mediatype` vs estrutura `file`
- ⚠️ Base64 sem prefixo `data:image/jpeg;base64,`
- ⚠️ MIME type obrigatório para base64

---

#### Enviar Documento

**Evolution API:**
```http
POST https://evo.rbtec.com.br/message/sendMedia/{instanceName}
Body:
{
  "number": "5517991253112",
  "mediatype": "document",
  "media": "data:application/pdf;base64,JVBERi0x...",
  "fileName": "arquivo.pdf"
}
```

**WAHA:**
```http
POST https://waha.server.com/api/sendFile
Body:
{
  "session": "...",
  "chatId": "5517991253112@c.us",
  "file": {
    "mimetype": "application/pdf",
    "filename": "arquivo.pdf",
    "data": "JVBERi0x..."  ← Sem prefixo
  }
}
```

---

#### Enviar Áudio

**Evolution API:**
```http
POST https://evo.rbtec.com.br/message/sendMedia/{instanceName}
Body:
{
  "number": "5517991253112",
  "mediatype": "audio",
  "media": "data:audio/ogg;base64,T2dnUw..."
}
```

**WAHA:**
```http
POST https://waha.server.com/api/sendAudio
Body:
{
  "session": "...",
  "chatId": "5517991253112@c.us",
  "file": {
    "mimetype": "audio/ogg; codecs=opus",
    "filename": "audio.ogg",
    "data": "T2dnUw..."
  }
}
```

**Diferenças:**
- ❌ Endpoints separados por tipo de mídia!
  * WAHA: `/sendImage`, `/sendFile`, `/sendAudio`, `/sendVideo`
  * Evolution: Tudo em `/sendMedia` (campo `mediatype`)

---

### 3. WEBHOOKS

#### Mensagem Recebida

**Evolution API:**
```json
{
  "event": "messages.upsert",
  "instance": "instance-name",
  "data": {
    "key": "INSTANCE_KEY...",
    "messages": [
      {
        "key": {
          "remoteJid": "5517991253112@s.whatsapp.net",
          "fromMe": false,
          "id": "3EB0C5A71BEFC4B5774D"
        },
        "message": {
          "messageType": "conversation",
          "conversation": "Olá!"
        },
        "messageTimestamp": 1697200000,
        "pushName": "Paulo Bernal",
        "status": "PENDING"
      }
    ]
  }
}
```

**WAHA:**
```json
{
  "event": "message",
  "session": "instance-name",
  "payload": {
    "id": "true_5517991253112@c.us_3EB0C5A71BEFC4B5774D",
    "timestamp": 1697200000,
    "from": "5517991253112@c.us",
    "fromMe": false,
    "body": "Olá!",
    "hasMedia": false,
    "ack": 1,
    "_data": {
      "notifyName": "Paulo Bernal"
    }
  }
}
```

**Diferenças Estruturais:**

| Campo | Evolution | WAHA |
|-------|-----------|------|
| Root event | `messages.upsert` | `message` |
| Instance ID | `instance` | `session` |
| Data wrapper | `data.messages[]` | `payload` (flat) |
| Message ID | `key.id` | `id` |
| Sender | `key.remoteJid` | `from` |
| Direction | `key.fromMe` | `fromMe` |
| Text | `message.conversation` | `body` |
| Timestamp | `messageTimestamp` | `timestamp` |
| Sender name | `pushName` | `_data.notifyName` |

**Refatoração Necessária:**

```python
# ANTES (Evolution)
def handle_message_upsert(self, data):
    instance = data.get('instance')
    messages = data.get('data', {}).get('messages', [])
    
    for msg in messages:
        remote_jid = msg['key']['remoteJid']
        from_me = msg['key']['fromMe']
        msg_id = msg['key']['id']
        text = msg['message'].get('conversation', '')
        timestamp = msg['messageTimestamp']
        sender_name = msg.get('pushName', '')

# DEPOIS (WAHA)
def handle_message(self, data):
    session = data.get('session')
    payload = data.get('payload', {})  ← Flat!
    
    remote_jid = payload['from']
    from_me = payload['fromMe']
    msg_id = payload['id']
    text = payload.get('body', '')
    timestamp = payload['timestamp']
    sender_name = payload.get('_data', {}).get('notifyName', '')
```

---

#### Mensagem com Mídia

**Evolution API:**
```json
{
  "event": "messages.upsert",
  "data": {
    "messages": [{
      "message": {
        "messageType": "imageMessage",
        "imageMessage": {
          "url": "https://mmg.whatsapp.net/...",
          "mimetype": "image/jpeg",
          "caption": "Veja esta foto",
          "fileLength": 123456,
          "height": 1920,
          "width": 1080
        }
      }
    }]
  }
}
```

**WAHA:**
```json
{
  "event": "message",
  "payload": {
    "hasMedia": true,
    "body": "Veja esta foto",  ← Caption
    "mediaUrl": "https://waha.server/api/files/...",
    "_data": {
      "type": "image",
      "mimetype": "image/jpeg",
      "size": 123456
    }
  }
}
```

**Diferenças:**
- ❌ Campo `messageType` vs `hasMedia` + `_data.type`
- ❌ URL diferente (WhatsApp direto vs servidor WAHA)
- ⚠️ WAHA faz proxy da mídia

---

#### Status de Mensagem

**Evolution API:**
```json
{
  "event": "messages.update",
  "instance": "instance-name",
  "data": {
    "messages": [{
      "key": {
        "remoteJid": "5517991253112@s.whatsapp.net",
        "id": "3EB0C5A71BEFC4B5774D"
      },
      "update": {
        "status": "READ"  ← PENDING, SENT, DELIVERED, READ
      }
    }]
  }
}
```

**WAHA:**
```json
{
  "event": "message.ack",
  "session": "instance-name",
  "payload": {
    "id": "true_5517991253112@c.us_3EB0C5A71BEFC4B5774D",
    "ack": 3,  ← 1=SENT, 2=DELIVERED, 3=READ, 4=PLAYED
    "chatId": "5517991253112@c.us"
  }
}
```

**Diferenças:**
- ❌ Evento diferente (`messages.update` vs `message.ack`)
- ❌ Status em texto vs número

**Mapeamento:**
```python
WAHA_TO_EVOLUTION_STATUS = {
    1: 'SENT',
    2: 'DELIVERED',
    3: 'READ',
    4: 'READ'  # PLAYED = READ para nosso sistema
}
```

---

#### Status de Conexão

**Evolution API:**
```json
{
  "event": "connection.update",
  "instance": "instance-name",
  "data": {
    "state": "open"  ← close, connecting, open
  }
}
```

**WAHA:**
```json
{
  "event": "session.status",
  "session": "instance-name",
  "payload": {
    "status": "WORKING"  ← STOPPED, STARTING, SCAN_QR_CODE, WORKING, FAILED
  }
}
```

**Mapeamento:**
```python
WAHA_TO_EVOLUTION_STATE = {
    'STOPPED': 'close',
    'STARTING': 'connecting',
    'SCAN_QR_CODE': 'connecting',
    'WORKING': 'open',
    'FAILED': 'close'
}
```

---

### 4. FEATURES AVANÇADAS

#### Presença (Typing/Recording)

**Evolution API:** ✅
```http
POST https://evo.rbtec.com.br/chat/presence/{instanceName}
Headers:
  apikey: <INSTANCE_API_KEY>

Body:
{
  "number": "5517991253112",
  "state": "composing",  ← composing, recording, paused
  "delay": 5000  ← Tempo em ms
}

Response: 200 OK
```

**WAHA:** ❌ NÃO SUPORTADO

**Workaround:** Nenhum - Feature será perdida

**Impacto no Código:**
```python
# backend/apps/campaigns/rabbitmq_consumer.py:613
async def _send_typing_presence(self, instance, phone, seconds):
    # ❌ Esta função precisa ser REMOVIDA ou desabilitada
    pass
```

---

#### Ler Mensagem

**Evolution API:**
```http
POST https://evo.rbtec.com.br/chat/markMessageAsRead/{instanceName}
Body:
{
  "key": {
    "remoteJid": "5517991253112@s.whatsapp.net",
    "id": "3EB0C5A71BEFC4B5774D",
    "fromMe": false
  }
}
```

**WAHA:**
```http
POST https://waha.server.com/api/sendSeen
Body:
{
  "session": "instance-name",
  "chatId": "5517991253112@c.us",
  "messageId": "true_5517991253112@c.us_3EB0C5A71BEFC4B5774D"
}
```

**Diferenças:**
- ⚠️ Endpoint diferente
- ⚠️ Formato de ID diferente
- ✅ Funcionalidade equivalente

---

#### Buscar Foto de Perfil

**Evolution API:** ✅ (via webhook `contacts.update`)
```json
{
  "event": "contacts.update",
  "data": {
    "profilePicUrl": "https://pps.whatsapp.net/v/..."
  }
}
```

**WAHA:** ⚠️ Precisa buscar manualmente
```http
GET https://waha.server.com/api/{session}/contacts/{phone}/profile-picture
Headers:
  X-Api-Key: <GLOBAL_API_KEY>

Response: 200 OK
{
  "profilePictureUrl": "https://pps.whatsapp.net/v/..."
}
```

**Impacto:**
- ❌ Foto NÃO vem automaticamente no webhook
- ⚠️ Precisa fazer request adicional
- ⚠️ Aumenta latência

**Workaround:**
```python
# Criar job periódico para atualizar fotos
@shared_task
def sync_profile_pictures():
    conversations = Conversation.objects.filter(
        profile_pic_url__isnull=True
    )[:100]
    
    for conv in conversations:
        # Buscar foto via WAHA API
        url = f"{waha_url}/api/{session}/contacts/{conv.contact_phone}/profile-picture"
        response = httpx.get(url, headers={'X-Api-Key': api_key})
        
        if response.status_code == 200:
            data = response.json()
            conv.profile_pic_url = data.get('profilePictureUrl')
            conv.save()
```

---

## 🔐 AUTENTICAÇÃO E SEGURANÇA

### Evolution API

```
┌─────────────────────────────────────┐
│  MODELO DE AUTENTICAÇÃO             │
├─────────────────────────────────────┤
│                                      │
│  Master API Key (Servidor)          │
│    - Criar instâncias                │
│    - Deletar instâncias              │
│    - Listar todas as instâncias      │
│                                      │
│  Instance API Key (Por Instância)   │
│    - Enviar mensagens                │
│    - Gerar QR Code                   │
│    - Verificar status                │
│    - Configurar webhook              │
│                                      │
│  ✅ Isolamento por instância         │
│  ✅ Tenant A não acessa Tenant B     │
│                                      │
└─────────────────────────────────────┘
```

**Implementação Atual:**
```python
# backend/apps/notifications/models.py:141
class WhatsAppInstance(models.Model):
    api_key = models.CharField(max_length=255)  ← Específica!
    
# backend/apps/campaigns/rabbitmq_consumer.py:636
headers = {
    "apikey": instance.api_key  ← Cada instância tem sua key
}
```

---

### WAHA

```
┌─────────────────────────────────────┐
│  MODELO DE AUTENTICAÇÃO             │
├─────────────────────────────────────┤
│                                      │
│  Global API Key ÚNICA                │
│    - Criar sessões                   │
│    - Deletar sessões                 │
│    - Listar sessões                  │
│    - Enviar mensagens                │
│    - TUDO!                           │
│                                      │
│  ⚠️ Sem isolamento por sessão        │
│  ⚠️ Precisa validar no backend       │
│                                      │
└─────────────────────────────────────┘
```

**Implementação Nova:**
```python
# backend/apps/waha/middleware.py
class WAHASessionMiddleware:
    def validate_session_access(self, user, session_name):
        """
        Garantir que usuário só acessa suas próprias sessões.
        """
        instance = WhatsAppInstance.objects.get(
            session_name=session_name
        )
        
        if instance.tenant_id != user.tenant_id:
            raise PermissionDenied("Acesso negado")
```

**Risco:**
- ⚠️ Se backend não validar corretamente, tenant A pode enviar mensagens como tenant B!
- ⚠️ Superfície de ataque maior
- ⚠️ Necessário middleware de segurança adicional

---

## 📊 RESUMO DAS MUDANÇAS

### Endpoints Afetados

| Funcionalidade | Arquivos Backend | Linhas Afetadas | Complexidade |
|----------------|------------------|-----------------|--------------|
| Criação de instâncias | 3 | ~300 | ALTA |
| Envio de texto | 4 | ~400 | MÉDIA |
| Envio de mídia | 2 | ~200 | ALTA |
| Webhook mensagens | 2 | ~600 | MUITO ALTA |
| Webhook status | 2 | ~200 | MÉDIA |
| Presença (typing) | 2 | ~100 | BAIXA (remover) |
| Foto de perfil | 3 | ~300 | ALTA |
| **TOTAL** | **15+** | **~2.100** | **MUITO ALTA** |

---

## 🚨 ALERTAS CRÍTICOS

### 1. IDs de Mensagem Incompatíveis

```
Evolution: "3EB0C5A71BEFC4B5774D"
WAHA:      "true_5517991253112@c.us_3EB0C5A71BEFC4B5774D"

Impacto:
- ❌ Tabela campaign_contact tem whatsapp_message_id
- ❌ Tracking de status vai quebrar
- ⚠️ Precisa migração de dados!
```

**Migration Script:**
```python
# Adicionar campo novo
class Migration:
    operations = [
        AddField('CampaignContact', 'waha_message_id', nullable=True)
    ]

# Durante transição, salvar ambos
contact.whatsapp_message_id = msg_id  # Evolution format
contact.waha_message_id = waha_msg_id  # WAHA format
```

---

### 2. Formato de Telefone

```
Evolution: "5517991253112"
WAHA:      "5517991253112@c.us"

Impacto em:
- ✅ Envio de mensagens (adicionar @c.us)
- ✅ Webhooks (remover @c.us)
- ✅ Busca de conversas
```

**Helper Function:**
```python
def normalize_phone(phone: str, for_waha: bool = False) -> str:
    """
    Normalizar formato de telefone.
    
    Evolution: 5517991253112
    WAHA: 5517991253112@c.us
    """
    # Remover caracteres especiais
    phone = re.sub(r'[^0-9]', '', phone)
    
    if for_waha and '@c.us' not in phone:
        return f"{phone}@c.us"
    elif not for_waha and '@c.us' in phone:
        return phone.replace('@c.us', '')
    
    return phone
```

---

### 3. Estados de Conexão

```
Evolution: close, connecting, open
WAHA:      STOPPED, STARTING, SCAN_QR_CODE, WORKING, FAILED

Impacto:
- ⚠️ WhatsAppInstance.connection_state precisa mudar
- ⚠️ Frontend exibe estados
- ⚠️ Lógica de rotação de instâncias depende de 'open'
```

**Adapter Pattern:**
```python
class ConnectionStateAdapter:
    @staticmethod
    def from_waha(waha_status: str) -> str:
        """Converter status WAHA para formato Evolution."""
        mapping = {
            'STOPPED': 'close',
            'STARTING': 'connecting',
            'SCAN_QR_CODE': 'connecting',
            'WORKING': 'open',
            'FAILED': 'close'
        }
        return mapping.get(waha_status, 'close')
    
    @staticmethod
    def to_waha(evolution_state: str) -> str:
        """Converter estado Evolution para WAHA."""
        mapping = {
            'close': 'STOPPED',
            'connecting': 'STARTING',
            'open': 'WORKING'
        }
        return mapping.get(evolution_state, 'STOPPED')
```

---

## ✅ CHECKLIST DE MIGRAÇÃO

### Preparação
- [ ] Instalar WAHA em ambiente de staging
- [ ] Testar criação de sessão
- [ ] Testar envio de mensagens
- [ ] Testar webhooks
- [ ] Documentar todas as diferenças

### Models
- [ ] Criar campo `session_name`
- [ ] Remover dependência de `api_key` por instância
- [ ] Migration script para IDs de mensagem
- [ ] Adapter para estados de conexão

### Backend - Instâncias
- [ ] Refatorar `generate_qr_code()`
- [ ] Refatorar `check_connection_status()`
- [ ] Refatorar `perform_destroy()`
- [ ] Remover `update_webhook_config()` (ou adaptar)

### Backend - Envio
- [ ] Refatorar envio de texto
- [ ] Refatorar envio de imagem
- [ ] Refatorar envio de áudio
- [ ] Refatorar envio de documento
- [ ] Adicionar normalização de telefone
- [ ] Remover feature de "typing"

### Backend - Webhooks
- [ ] Criar `WAHAWebhookView`
- [ ] Parser de evento `message`
- [ ] Parser de evento `message.ack`
- [ ] Parser de evento `session.status`
- [ ] Remover handlers não suportados

### Segurança
- [ ] Middleware de validação de sessão
- [ ] Logs de acesso
- [ ] Rate limiting por tenant

### Frontend
- [ ] Renomear páginas
- [ ] Atualizar labels
- [ ] Remover campo "API Key da Instância"

### Testes
- [ ] Teste de criação de instância
- [ ] Teste de envio de mensagem
- [ ] Teste de recebimento de webhook
- [ ] Teste de campanha completa
- [ ] Teste de múltiplos tenants
- [ ] Teste de segurança

---

**Data:** 22 de Outubro de 2025  
**Autor:** AI Assistant  
**Status:** Análise Técnica Completa

