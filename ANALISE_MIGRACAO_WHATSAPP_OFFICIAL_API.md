# 📋 Análise: Migração para WhatsApp Business API Oficial

## 🎯 Resumo Executivo

**Resposta curta:** **NÃO**, não é só conectar e usar. Seria necessário fazer **mudanças significativas** no código, mas a **arquitetura geral pode ser mantida**.

A Evolution API é uma **camada de abstração** sobre o WhatsApp Web (via Baileys), enquanto a WhatsApp Business API oficial usa um protocolo completamente diferente (Graph API).

---

## 🔍 Situação Atual: Evolution API

### Como funciona hoje:

1. **Criação de Instância:**
   - `POST /instance/create` → Retorna API key da instância
   - QR Code gerado via `GET /instance/connect/{uuid}`

2. **Envio de Mensagens:**
   - `POST /message/sendText/{instance_name}` → Texto
   - `POST /message/sendMedia/{instance_name}` → Mídia
   - `POST /message/sendWhatsAppAudio/{instance_name}` → Áudio PTT
   - `POST /message/sendReaction/{instance_name}` → Reações

3. **Webhooks:**
   - Recebe eventos em `/connections/webhooks/evolution/`
   - Eventos: `messages.upsert`, `messages.update`, `connection.update`, etc.

4. **Estrutura de Payload:**
   ```json
   {
     "number": "5517991253112",
     "text": "Mensagem",
     "options": {
       "quoted": {
         "key": {
           "remoteJid": "...",
           "fromMe": false,
           "id": "..."
         }
       }
     }
   }
   ```

---

## 🔄 WhatsApp Business API Oficial

### Diferenças Principais:

1. **Autenticação:**
   - ✅ Evolution API: API Key simples no header `apikey`
   - ❌ WhatsApp API: OAuth 2.0 + Access Token + App ID/Secret

2. **Estrutura de Endpoints:**
   - ✅ Evolution API: `/message/sendText/{instance_name}`
   - ❌ WhatsApp API: `/v21.0/{phone-number-id}/messages`

3. **Estrutura de Payload:**
   ```json
   {
     "messaging_product": "whatsapp",
     "to": "5517991253112",
     "type": "text",
     "text": {
       "body": "Mensagem"
     }
   }
   ```

4. **Webhooks:**
   - ✅ Evolution API: Recebe eventos diretos do WhatsApp Web
   - ❌ WhatsApp API: Webhooks via Meta (requer verificação, assinatura)

5. **Mensagens de Mídia:**
   - ✅ Evolution API: URL direta no payload
   - ❌ WhatsApp API: Upload para Media API primeiro, depois usar Media ID

6. **Templates:**
   - ✅ Evolution API: Envia mensagens normais livremente
   - ❌ WhatsApp API: **Obrigatório usar templates** para primeira mensagem (24h window)

---

## 📝 O Que Precisaria Ser Alterado

### 🔴 CRÍTICO (Obrigatório)

#### 1. **Camada de Envio de Mensagens** (`backend/apps/chat/tasks.py`)

**Arquivos afetados:**
- `backend/apps/chat/tasks.py` (linhas ~1000-2000)
- `backend/apps/campaigns/services.py` (linha ~778)
- `backend/apps/campaigns/apps.py` (linhas ~744, ~886)
- `backend/apps/notifications/views.py` (linha ~313)

**Mudanças necessárias:**

```python
# ❌ ANTES (Evolution API)
endpoint = f"{base_url}/message/sendText/{instance_name}"
payload = {
    "number": "5517991253112",
    "text": "Mensagem"
}

# ✅ DEPOIS (WhatsApp API)
endpoint = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
payload = {
    "messaging_product": "whatsapp",
    "to": "5517991253112",
    "type": "text",
    "text": {
        "body": "Mensagem"
    }
}
```

**Complexidade:** 🔴 **ALTA** - ~500 linhas de código afetadas

---

#### 2. **Sistema de Webhooks** (`backend/apps/connections/webhook_views.py`)

**Arquivos afetados:**
- `backend/apps/connections/webhook_views.py` (todo o arquivo)
- `backend/apps/chat/webhooks.py` (linhas ~636-945)

**Mudanças necessárias:**

```python
# ❌ ANTES (Evolution API)
# Eventos diretos do WhatsApp Web
event_type = data.get('event')  # 'messages.upsert'
message_data = data.get('data', {})

# ✅ DEPOIS (WhatsApp API)
# Webhooks via Meta com estrutura diferente
entry = data.get('entry', [{}])[0]
changes = entry.get('changes', [{}])[0]
value = changes.get('value', {})
messages = value.get('messages', [])
```

**Complexidade:** 🔴 **ALTA** - Reestruturação completa do parser de webhooks

---

#### 3. **Autenticação e Configuração**

**Arquivos afetados:**
- `backend/apps/notifications/models.py` (modelo `WhatsAppInstance`)
- `backend/apps/notifications/views.py` (criação de instâncias)
- `backend/alrea_sense/settings.py` (variáveis de ambiente)

**Mudanças necessárias:**

```python
# ❌ ANTES (Evolution API)
class WhatsAppInstance(models.Model):
    api_key = models.CharField(...)  # API key simples
    api_url = models.CharField(...)   # URL do servidor Evolution
    instance_name = models.UUIDField(...)

# ✅ DEPOIS (WhatsApp API)
class WhatsAppInstance(models.Model):
    phone_number_id = models.CharField(...)  # Phone Number ID do Meta
    access_token = models.CharField(...)     # OAuth Access Token
    app_id = models.CharField(...)           # App ID do Meta
    app_secret = models.CharField(...)       # App Secret (criptografado)
    verify_token = models.CharField(...)     # Token para verificação de webhook
```

**Complexidade:** 🟡 **MÉDIA** - Migração de modelo + ajustes de UI

---

#### 4. **Sistema de Mídia** (`backend/apps/chat/media_tasks.py`)

**Arquivos afetados:**
- `backend/apps/chat/media_tasks.py`
- `backend/apps/chat/tasks.py` (processamento de mídia)

**Mudanças necessárias:**

```python
# ❌ ANTES (Evolution API)
# URL direta no payload
payload = {
    "media": "https://s3.amazonaws.com/...",
    "mediatype": "image"
}

# ✅ DEPOIS (WhatsApp API)
# 1. Upload para Media API primeiro
upload_response = requests.post(
    f"https://graph.facebook.com/v21.0/{media_id}/media",
    files={"file": file_data},
    data={"messaging_product": "whatsapp", "type": "image"}
)
media_id = upload_response.json()["id"]

# 2. Usar Media ID no envio
payload = {
    "type": "image",
    "image": {
        "id": media_id
    }
}
```

**Complexidade:** 🔴 **ALTA** - Fluxo de 2 etapas para mídia

---

#### 5. **Sistema de Templates (24h Window)**

**NOVO REQUISITO:** WhatsApp API oficial **obriga** uso de templates para primeira mensagem.

**Arquivos afetados:**
- `backend/apps/chat/tasks.py` (lógica de envio)
- `backend/apps/campaigns/services.py` (campanhas)
- **NOVO:** `backend/apps/notifications/models.py` (modelo `WhatsAppTemplate`)

**Mudanças necessárias:**

```python
# ✅ NOVO: Verificar se contato está na janela de 24h
# Se não estiver, usar template obrigatoriamente

if not is_within_24h_window(contact):
    # Usar template
    payload = {
        "type": "template",
        "template": {
            "name": "welcome_message",
            "language": {"code": "pt_BR"},
            "components": [...]
        }
    }
else:
    # Mensagem normal permitida
    payload = {
        "type": "text",
        "text": {"body": "Mensagem"}
    }
```

**Complexidade:** 🔴 **ALTA** - Lógica complexa de janela de 24h + gerenciamento de templates

---

### 🟡 MÉDIO (Importante mas menos crítico)

#### 6. **QR Code e Conexão**

**Arquivos afetados:**
- `backend/apps/notifications/views.py` (geração de QR code)

**Mudanças necessárias:**

```python
# ❌ ANTES (Evolution API)
# QR Code gerado pelo Evolution API
GET /instance/connect/{uuid}

# ✅ DEPOIS (WhatsApp API)
# Não há QR Code - conexão é via OAuth 2.0
# Usuário precisa autorizar app no Meta Business Manager
```

**Complexidade:** 🟡 **MÉDIA** - Remover lógica de QR Code, adicionar OAuth flow

---

#### 7. **Reações e Edição de Mensagens**

**Arquivos afetados:**
- `backend/apps/chat/tasks.py` (send_reaction_to_evolution)
- `backend/apps/chat/tasks.py` (edit_message)

**Mudanças necessárias:**

```python
# ❌ ANTES (Evolution API)
# Reações e edição suportadas nativamente

# ✅ DEPOIS (WhatsApp API)
# Reações: ✅ Suportado (emoji diferente)
# Edição: ❌ NÃO suportado pela API oficial
```

**Complexidade:** 🟡 **MÉDIA** - Remover funcionalidade de edição

---

#### 8. **Status de Conexão**

**Arquivos afetados:**
- `backend/apps/notifications/views.py` (verificação de status)
- `backend/apps/chat/utils/instance_state.py`

**Mudanças necessárias:**

```python
# ❌ ANTES (Evolution API)
# Status: "open", "connecting", "close"
GET /instance/connectionState/{uuid}

# ✅ DEPOIS (WhatsApp API)
# Status via webhook ou verificação de token
# Não há "connecting" - ou está conectado ou não
```

**Complexidade:** 🟡 **BAIXA** - Simplificar lógica de status

---

### 🟢 BAIXO (Ajustes menores)

#### 9. **Variáveis de Ambiente**

**Arquivos afetados:**
- `backend/alrea_sense/settings.py`
- `WHATSAPP_CONFIG.md`

**Mudanças necessárias:**

```bash
# ❌ ANTES (Evolution API)
EVOLUTION_API_URL=https://evo.rbtec.com.br
EVOLUTION_API_KEY=...

# ✅ DEPOIS (WhatsApp API)
WHATSAPP_API_VERSION=v21.0
WHATSAPP_APP_ID=...
WHATSAPP_APP_SECRET=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_WEBHOOK_SECRET=...
```

**Complexidade:** 🟢 **BAIXA** - Apenas atualizar variáveis

---

#### 10. **Documentação**

**Arquivos afetados:**
- `WHATSAPP_CONFIG.md`
- Documentação de API

**Complexidade:** 🟢 **BAIXA** - Atualizar docs

---

## 📊 Resumo de Impacto

| Componente | Complexidade | Linhas Afetadas | Tempo Estimado |
|------------|--------------|-----------------|----------------|
| Envio de Mensagens | 🔴 ALTA | ~500 | 2-3 dias |
| Webhooks | 🔴 ALTA | ~300 | 2-3 dias |
| Autenticação | 🟡 MÉDIA | ~100 | 1 dia |
| Sistema de Mídia | 🔴 ALTA | ~200 | 1-2 dias |
| Templates (24h) | 🔴 ALTA | ~300 | 2-3 dias |
| QR Code/OAuth | 🟡 MÉDIA | ~50 | 1 dia |
| Reações/Edição | 🟡 MÉDIA | ~50 | 0.5 dia |
| Status | 🟡 BAIXA | ~30 | 0.5 dia |
| Variáveis | 🟢 BAIXA | ~10 | 0.5 dia |
| **TOTAL** | | **~1540 linhas** | **12-16 dias** |

---

## ⚠️ Considerações Importantes

### 1. **Limitações da API Oficial:**

- ❌ **Templates obrigatórios** para primeira mensagem (janela de 24h)
- ❌ **Sem edição de mensagens** (não suportado)
- ❌ **Sem QR Code** (OAuth 2.0 obrigatório)
- ❌ **Rate limits mais restritivos** (dependendo do tier)
- ❌ **Custo por mensagem** (após tier gratuito)

### 2. **Vantagens da API Oficial:**

- ✅ **Conformidade oficial** com Meta
- ✅ **Suporte oficial** da Meta
- ✅ **Recursos avançados** (templates, catálogos, etc.)
- ✅ **Escalabilidade** garantida
- ✅ **Segurança** auditada pela Meta

### 3. **Vantagens da Evolution API (atual):**

- ✅ **Sem templates obrigatórios** (mensagens livres)
- ✅ **Edição de mensagens** suportada
- ✅ **QR Code simples** para conexão
- ✅ **Sem custo por mensagem** (apenas infraestrutura)
- ✅ **Mais flexível** (menos restrições)

---

## 🎯 Recomendação

### Se você quer migrar para API oficial:

1. **Fase 1 (Preparação):**
   - Criar conta Meta Business
   - Configurar App no Meta Developers
   - Obter Phone Number ID e Access Token
   - Criar templates iniciais

2. **Fase 2 (Desenvolvimento):**
   - Implementar camada de abstração para envio
   - Migrar webhooks
   - Implementar sistema de templates
   - Migrar sistema de mídia

3. **Fase 3 (Testes):**
   - Testar envio de mensagens
   - Testar recebimento de webhooks
   - Testar templates
   - Testar mídia

4. **Fase 4 (Migração):**
   - Migrar instâncias existentes
   - Atualizar configurações
   - Monitorar erros

**Tempo total estimado:** 2-3 semanas de desenvolvimento + tempo de aprovação de templates

---

## ✅ Conclusão

**NÃO é só conectar e usar.** Seria necessário:

- ✅ Refatorar ~1540 linhas de código
- ✅ Implementar sistema de templates (novo)
- ✅ Migrar webhooks completamente
- ✅ Implementar OAuth 2.0
- ✅ Ajustar sistema de mídia (2 etapas)
- ✅ Remover funcionalidades não suportadas (edição)

**Mas a arquitetura geral pode ser mantida:**
- ✅ Mesma estrutura de filas (Redis/RabbitMQ)
- ✅ Mesmos modelos de dados (com ajustes)
- ✅ Mesma lógica de negócio (com adaptações)
- ✅ Mesmo frontend (sem mudanças)

**Recomendação:** Se a Evolution API está funcionando bem, **não migre** a menos que tenha necessidade específica de conformidade oficial ou recursos avançados da API oficial.





