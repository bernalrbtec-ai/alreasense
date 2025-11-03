# 📊 COMPARAÇÃO: Fluxos de ENVIO vs RECEBIMENTO de Anexos

## 🎯 OBJETIVO

Analisar as diferenças entre os fluxos de ENVIO e RECEBIMENTO para identificar inconsistências e padronizar o código.

---

## 📤 FLUXO DE ENVIO (Frontend → S3 → WhatsApp)

### Arquivos Principais:
- `frontend/src/modules/chat/components/MessageInput.tsx` - Upload frontend
- `backend/apps/chat/api/views.py` - `get_upload_presigned_url()` e `confirm_upload()`

### Passos:

1. **Frontend: POST `/upload-presigned-url/`**
   - Valida tamanho (50MB) e MIME type
   - Retorna: `{upload_url, attachment_id, s3_key, expires_in}`
   - **Path S3:** `chat/{tenant_id}/attachments/{attachment_id}.{ext}` ⚠️

2. **Frontend: PUT direto para S3**
   - Upload via presigned URL
   - Progress tracking via XMLHttpRequest

3. **Frontend: POST `/confirm-upload/`**
   - Envia: `{conversation_id, attachment_id, s3_key, filename, content_type, file_size}`
   - Backend:
     - ✅ Converte áudio OGG/WEBM → MP3 (se necessário)
     - ✅ Cria Message + MessageAttachment
     - ✅ Gera proxy URL: `get_public_url(s3_key)`
     - ✅ Enfileira envio para Evolution API
     - ✅ WebSocket broadcast

### Características:
- ✅ Upload direto frontend → S3 (sem passar pelo backend)
- ✅ Conversão de áudio OGG/WEBM → MP3
- ✅ Path S3: `chat/{tenant_id}/attachments/{uuid}.{ext}`
- ✅ URL pública: `get_public_url(s3_key)`
- ✅ Cache Redis opcional (não implementado no envio)

---

## 📥 FLUXO DE RECEBIMENTO (WhatsApp → Backend → S3)

### Arquivos Principais:
- `backend/apps/chat/webhooks.py` - `handle_message_upsert()` - Cria placeholder
- `backend/apps/chat/media_tasks.py` - `handle_process_incoming_media()` - Processa mídia
- `backend/apps/chat/tasks.py` - Enfileira `process_incoming_media`

### Passos:

1. **Webhook: Evolution API envia mensagem**
   - Contém `media_url` (temporária do WhatsApp)
   - Cria Message + MessageAttachment **placeholder**:
     ```python
     MessageAttachment.objects.create(
         message=message,
         file_path='',  # ⚠️ Vazio
         file_url='',   # ⚠️ Vazio
         metadata={'processing': True}  # ⚠️ Flag de processamento
     )
     ```

2. **Webhook: Enfileira processamento**
   ```python
   process_incoming_media.delay(
       tenant_id, message_id, media_url, media_type
   )
   ```

3. **Worker: `handle_process_incoming_media()`**
   - ✅ Baixa do WhatsApp (httpx.AsyncClient, com retry)
   - ✅ Valida tamanho antes de baixar (HEAD request)
   - ✅ Processa imagem (thumbnail, resize, optimize)
   - ✅ Converte áudio OGG/WEBM → MP3
   - ✅ Upload para S3
   - ✅ **Path S3:** `generate_media_path(tenant_id, f'chat_{media_type}s', filename)` ⚠️
   - ✅ URL pública: `get_public_url(s3_path)`
   - ✅ Cache Redis (30 dias TTL)
   - ✅ Atualiza MessageAttachment (remove `processing` flag)
   - ✅ WebSocket broadcast `attachment_updated`

### Características:
- ✅ Download assíncrono via worker
- ✅ Retry automático (3 tentativas download, 2 tentativas upload)
- ✅ Validação de tamanho antes de baixar
- ✅ Processamento de imagem (thumbnail + resize)
- ✅ Conversão de áudio
- ⚠️ **Path S3 diferente:** `chat_{media_type}s/{tenant_id}/...` (ex: `chat_images/...`, `chat_audios/...`)
- ✅ Cache Redis implementado
- ✅ Tratamento de erros robusto (marca attachment como erro)

---

## ⚠️ INCONSISTÊNCIAS IDENTIFICADAS

### 1. **Path S3 DIFERENTE** 🔴

**ENVIO:**
```python
# views.py linha 1159
s3_key = f"chat/{tenant_id}/attachments/{attachment_id}.{ext}"
# Resultado: chat/{uuid}/attachments/{uuid}.pdf
```

**RECEBIMENTO:**
```python
# media_tasks.py linha 300
s3_path = generate_media_path(tenant_id, f'chat_{media_type}s', filename)
# Resultado: chat_images/{uuid}/media_123.jpg
# OU: chat_audios/{uuid}/audio_456.mp3
```

**Impacto:**
- ❌ Anexos enviados e recebidos ficam em pastas diferentes
- ❌ Dificulta manutenção e limpeza
- ❌ `generate_media_path` usa estrutura diferente

**Solução:**
- ✅ Padronizar para: `chat/{tenant_id}/attachments/{uuid}.{ext}` (mesmo do ENVIO)

---

### 2. **Cache Redis** 🟡

**ENVIO:**
- ❌ Não implementa cache Redis

**RECEBIMENTO:**
- ✅ Implementa cache Redis (30 dias TTL)
- ✅ Cacheia dados processados
- ✅ Cacheia verificação de existência S3 (5 min)

**Solução:**
- 🟡 Opcional: Adicionar cache no ENVIO (não crítico, upload já é rápido)

---

### 3. **Tratamento de Erros** 🟢

**ENVIO:**
- ✅ Validação no frontend (tamanho, MIME type)
- ✅ Try/catch no backend
- ⚠️ Erros retornam HTTP status code

**RECEBIMENTO:**
- ✅ Validação antes de baixar (HEAD request)
- ✅ Retry automático (download: 3x, upload: 2x)
- ✅ Marca attachment como erro no metadata
- ✅ WebSocket notifica erro

**Solução:**
- ✅ Manter tratamento robusto do RECEBIMENTO
- 🟡 Opcional: Melhorar feedback de erro no ENVIO

---

### 4. **Processamento de Imagem** 🟡

**ENVIO:**
- ❌ Não processa imagem (upload direto)

**RECEBIMENTO:**
- ✅ Processa imagem (thumbnail, resize, optimize)
- ✅ Upload thumbnail separado

**Solução:**
- 🟡 Opcional: Adicionar processamento no ENVIO (thumbnail para preview rápido)
- ✅ Manter processamento no RECEBIMENTO (otimização importante)

---

### 5. **Conversão de Áudio** 🟢

**ENVIO:**
- ✅ Converte OGG/WEBM → MP3 (em `confirm_upload`)

**RECEBIMENTO:**
- ✅ Converte OGG/WEBM → MP3 (em `handle_process_incoming_media`)

**Status:**
- ✅ **JÁ PADRONIZADO** - Ambos convertem para MP3

---

### 6. **WebSocket Broadcast** 🟢

**ENVIO:**
- ✅ Broadcast via `send_message_to_evolution` → `handle_send_message` → WebSocket

**RECEBIMENTO:**
- ✅ Broadcast `attachment_updated` após processamento

**Status:**
- ✅ **JÁ PADRONIZADO** - Ambos fazem broadcast

---

## ✅ PROPOSTA DE REFATORAÇÃO

### Prioridade ALTA 🔴

1. **Padronizar Path S3**
   - Modificar `handle_process_incoming_media` para usar: `chat/{tenant_id}/attachments/{uuid}.{ext}`
   - Remover uso de `generate_media_path` com prefixos `chat_{media_type}s`
   - Usar mesmo padrão do ENVIO

### Prioridade MÉDIA 🟡

2. **Padronizar Uso de `generate_media_path`**
   - Verificar se `generate_media_path` deve ser usado ou se devemos usar path direto
   - Se manter `generate_media_path`, garantir que ambos os fluxos usam o mesmo

3. **Tratamento de Erros Consistente**
   - Adicionar marcação de erro no metadata do ENVIO (similar ao RECEBIMENTO)
   - WebSocket broadcast de erro no ENVIO

### Prioridade BAIXA 🟢

4. **Cache Redis Opcional no ENVIO**
   - Adicionar cache se necessário (não crítico)

5. **Processamento de Imagem no ENVIO**
   - Adicionar thumbnail opcional (melhora UX)

---

## 📝 ESTRUTURA ATUAL DOS PATHS S3

### ENVIO (atual):
```
chat/
└── {tenant_id}/
    └── attachments/
        └── {uuid}.pdf
        └── {uuid}.jpg
        └── {uuid}.mp3
```

### RECEBIMENTO (atual):
```
chat_images/
└── {tenant_id}/
    └── media_123.jpg
    └── thumb_media_123.jpg

chat_audios/
└── {tenant_id}/
    └── audio_456.mp3

chat_documents/
└── {tenant_id}/
    └── doc_789.pdf
```

### PROPOSTA (padronizado):
```
chat/
└── {tenant_id}/
    └── attachments/
        └── {uuid}.pdf      # Enviado OU recebido
        └── {uuid}.jpg      # Enviado OU recebido
        └── {uuid}_thumb.jpg # Thumbnail (se imagem recebida)
        └── {uuid}.mp3      # Enviado OU recebido
```

**Benefícios:**
- ✅ Estrutura unificada
- ✅ Facilita limpeza/manutenção
- ✅ Mesma organização para ambos os fluxos

---

## 🔍 CHECKLIST DE REFATORAÇÃO

- [ ] 🔴 Padronizar path S3 para `chat/{tenant_id}/attachments/...`
- [ ] 🔴 Atualizar `handle_process_incoming_media` para usar path unificado
- [ ] 🟡 Verificar uso de `generate_media_path` em todos os lugares
- [ ] 🟡 Adicionar tratamento de erro consistente (metadata)
- [ ] 🟢 Adicionar cache Redis no ENVIO (opcional)
- [ ] 🟢 Adicionar thumbnail no ENVIO (opcional)
- [ ] ✅ Testar fluxo completo de ENVIO
- [ ] ✅ Testar fluxo completo de RECEBIMENTO
- [ ] ✅ Verificar compatibilidade com arquivos existentes

---

## 📚 REFERÊNCIAS

- `backend/apps/chat/api/views.py` - ENVIO
- `backend/apps/chat/webhooks.py` - RECEBIMENTO (webhook)
- `backend/apps/chat/media_tasks.py` - RECEBIMENTO (processamento)
- `backend/apps/chat/utils/s3.py` - S3Manager e helpers

