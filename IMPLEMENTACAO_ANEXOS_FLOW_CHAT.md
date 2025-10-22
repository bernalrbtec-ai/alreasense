# 📎 Implementação de Anexos - Flow Chat

**Status:** Backend ✅ Completo | Frontend ⏳ Em Progresso  
**Data:** 21/10/2025  
**Arquitetura:** S3/MinIO + Presigned URLs + IA Ready

---

## 🎯 OBJETIVO

Implementar sistema completo de anexos para o Flow Chat:
- ✅ Upload direto para S3 (sem passar pelo backend)
- ✅ Suporte para imagens, vídeos, áudios, documentos
- ✅ Estrutura pronta para IA (transcrição + resumo)
- ⏳ Frontend para visualização e envio

---

## ✅ BACKEND IMPLEMENTADO

### 1. MODELO & MIGRATION

**Arquivo:** `backend/apps/chat/models.py`

Campos adicionados ao `MessageAttachment`:

```python
# ✨ Campos para IA (Flow AI addon)
transcription = models.TextField(null=True, blank=True)
transcription_language = models.CharField(max_length=10, null=True, blank=True)
ai_summary = models.TextField(null=True, blank=True)
ai_tags = models.JSONField(null=True, blank=True)
ai_sentiment = models.CharField(max_length=20, null=True, blank=True, choices=[...])
ai_metadata = models.JSONField(null=True, blank=True)
processing_status = models.CharField(max_length=20, default='pending', choices=[...])
processed_at = models.DateTimeField(null=True, blank=True)
```

**Migration:** `0004_add_ai_fields_to_attachment.py`
- ALTER TABLE `chat_attachment` com novos campos
- Índices para `processing_status`
- Constraints para `ai_sentiment` e `processing_status`

---

### 2. ENDPOINTS

**Base URL:** `/api/chat/messages/`

#### **POST `/upload-presigned-url/`** - Gerar URL de Upload

Gera presigned URL para upload direto no S3.

**Request:**
```json
{
  "conversation_id": "uuid",
  "filename": "foto.jpg",
  "content_type": "image/jpeg",
  "file_size": 1024000
}
```

**Response:**
```json
{
  "upload_url": "https://minio.../...",
  "attachment_id": "uuid",
  "s3_key": "chat/{tenant_id}/attachments/{uuid}.jpg",
  "expires_in": 300,
  "instructions": {
    "method": "PUT",
    "headers": {
      "Content-Type": "image/jpeg"
    }
  }
}
```

**Validações:**
- Conversa existe e pertence ao tenant
- Tamanho máximo: 50MB
- URL expira em 5 minutos

---

#### **POST `/confirm-upload/`** - Confirmar Upload

Cria Message + MessageAttachment após upload bem-sucedido.

**Request:**
```json
{
  "conversation_id": "uuid",
  "attachment_id": "uuid",
  "s3_key": "chat/.../...",
  "filename": "foto.jpg",
  "content_type": "image/jpeg",
  "file_size": 1024000
}
```

**Response:**
```json
{
  "message": {
    "id": "uuid",
    "content": "📎 foto.jpg",
    "direction": "outgoing",
    "status": "pending",
    ...
  },
  "attachment": {
    "id": "uuid",
    "file_url": "https://...",
    "storage_type": "s3",
    "processing_status": "pending",
    ...
  }
}
```

**Ações:**
1. Cria `Message` com conteúdo "📎 {filename}"
2. Cria `MessageAttachment` com URL pública S3
3. Enfileira para envio Evolution API via RabbitMQ
4. Retorna dados completos (broadcast via WebSocket)

---

### 3. SERIALIZER

**Arquivo:** `backend/apps/chat/api/serializers.py`

`MessageAttachmentSerializer` atualizado:

```python
fields = [
    'id', 'message', 'tenant', 'original_filename', 'mime_type',
    'file_path', 'file_url', 'thumbnail_path', 'storage_type',
    'size_bytes', 'expires_at', 'created_at',
    'is_expired', 'is_image', 'is_video', 'is_audio', 'is_document',
    # ✨ Campos IA (read-only)
    'transcription', 'transcription_language', 'ai_summary',
    'ai_tags', 'ai_sentiment', 'ai_metadata',
    'processing_status', 'processed_at'
]
```

Todos campos IA são **read-only** (processados pelo backend).

---

## 🔄 FLUXO DE UPLOAD (Frontend → S3 → Backend)

```
1. Usuário seleciona arquivo
   ↓
2. Frontend → POST /upload-presigned-url/
   ← {upload_url, attachment_id, s3_key}
   ↓
3. Frontend → PUT {upload_url} (upload direto S3)
   ✅ Arquivo no S3
   ↓
4. Frontend → POST /confirm-upload/ {attachment_id, s3_key, ...}
   ↓
5. Backend:
   - Cria Message + MessageAttachment
   - Enfileira envio Evolution API
   - Broadcast via WebSocket
   ↓
6. Frontend recebe via WebSocket
   - Atualiza UI com anexo
   - Mostra status de envio
```

---

## 🎨 FRONTEND (A IMPLEMENTAR)

### 1. COMPONENTE `AttachmentPreview`

**Arquivo:** `frontend/src/modules/chat/components/AttachmentPreview.tsx`

**Função:** Exibir diferentes tipos de anexos

**Features:**
- 🖼️ **Imagens:** Preview inline, lightbox ao clicar
- 🎥 **Vídeos:** Player HTML5 com controles
- 🎤 **Áudios:** Player com wavesurfer.js (waveform visual)
- 📄 **Documentos:** Ícone + nome + botão download
- 📝 **Transcrição:** Exibir se `attachment.transcription` existe
- 🧠 **Resumo IA:** Exibir se `attachment.ai_summary` existe (gated por addon)

**Props:**
```typescript
interface AttachmentPreviewProps {
  attachment: MessageAttachment;
  onDownload?: () => void;
  showAI?: boolean;  // Se tem addon Flow AI
}
```

---

### 2. COMPONENTE `AttachmentUpload`

**Arquivo:** `frontend/src/modules/chat/components/AttachmentUpload.tsx`

**Função:** Upload de arquivos com progress

**Features:**
- 📎 Botão "Anexar" no `MessageInput`
- 📂 Input file + drag & drop
- 👁️ Preview antes de enviar
- 📊 Progress bar durante upload
- ✅ Validação tamanho (50MB) e tipo
- ❌ Cancelar upload

**Fluxo:**
```typescript
1. Selecionar arquivo → Gerar preview
2. Usuário confirma → Obter presigned URL
3. Upload S3 direto → Progress bar
4. Upload completo → Confirm backend
5. Broadcast WebSocket → Atualizar UI
```

---

### 3. INTEGRAÇÃO

#### **MessageList.tsx:**
```typescript
{message.attachments?.map(attachment => (
  <AttachmentPreview
    key={attachment.id}
    attachment={attachment}
    showAI={hasFlowAI}
  />
))}
```

#### **MessageInput.tsx:**
```typescript
<div className="message-input">
  <AttachmentUpload
    conversationId={activeConversation.id}
    onUploadComplete={(attachment) => {
      // Attachment já foi broadcasteado via WebSocket
      // Apenas scroll para última mensagem
    }}
  />
  <textarea />
  <button>Enviar</button>
</div>
```

---

## 🤖 IA (FLOW AI ADDON)

### PROCESSAMENTO FUTURO

Quando addon Flow AI estiver ativo:

```python
# apps/chat/media_tasks.py (RabbitMQ handler)

if attachment.is_audio and tenant_has_flow_ai():
    # 1. Transcrição (Whisper API)
    transcription = whisper_api.transcribe(audio_url)
    
    # 2. Resumo + Tags (Grok Free)
    summary = grok_api.summarize(transcription)
    
    # 3. Salvar
    attachment.transcription = transcription
    attachment.ai_summary = summary
    attachment.ai_tags = extract_tags(summary)
    attachment.processing_status = 'completed'
    attachment.save()
    
    # 4. Broadcast update
    broadcast_attachment_update(attachment)
```

---

## 📊 MULTI-TENANT & SEGURANÇA

### ISOLAMENTO:
- ✅ S3 key inclui `tenant_id`: `chat/{tenant_id}/attachments/{uuid}.ext`
- ✅ Presigned URL expira em 5min
- ✅ Validação de tenant em todos endpoints
- ✅ QuerySets filtrados por tenant

### STORAGE:
- ✅ `storage_type='s3'` (MinIO em Railway)
- ✅ `expires_at = now() + 365 days` (1 ano)
- ✅ URL pública gerada via `S3Manager.get_public_url()`

### PERMISSÕES:
- ✅ `IsAuthenticated` + `CanAccessChat`
- ✅ Gerente/Agente só acessa conversas dos seus departamentos
- ✅ Admin acessa tudo do tenant

---

## 🧪 TESTES

### TESTAR BACKEND (Postman/cURL):

1. **Gerar presigned URL:**
```bash
curl -X POST https://.../api/chat/messages/upload-presigned-url/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "uuid",
    "filename": "test.jpg",
    "content_type": "image/jpeg",
    "file_size": 50000
  }'
```

2. **Upload para S3:**
```bash
curl -X PUT "{upload_url}" \
  -H "Content-Type: image/jpeg" \
  --data-binary @test.jpg
```

3. **Confirmar upload:**
```bash
curl -X POST https://.../api/chat/messages/confirm-upload/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "uuid",
    "attachment_id": "uuid",
    "s3_key": "chat/.../.../uuid.jpg",
    "filename": "test.jpg",
    "content_type": "image/jpeg",
    "file_size": 50000
  }'
```

---

## 📝 PRÓXIMOS PASSOS

### IMEDIATO (Frontend):
- [ ] Criar `AttachmentPreview.tsx`
- [ ] Criar `AttachmentUpload.tsx`
- [ ] Integrar em `MessageList` e `MessageInput`
- [ ] Testar upload end-to-end

### FUTURO (IA):
- [ ] Criar produto "Flow AI" em billing
- [ ] Implementar handler RabbitMQ para processamento
- [ ] Integrar Whisper API (transcrição)
- [ ] Integrar Grok Free (resumo/tags)
- [ ] UI condicional (só mostra se tenant tem addon)

---

## 📚 REFERÊNCIAS

- S3Manager: `backend/apps/chat/utils/s3.py`
- Evolution API: `backend/apps/connections/`
- RabbitMQ: `backend/apps/chat/tasks.py`
- WebSocket: `backend/apps/chat/consumers_v2.py`

---

**🚀 BACKEND 100% PRONTO! FRONTEND EM PROGRESSO...**


