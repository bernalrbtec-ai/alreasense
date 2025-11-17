# 📎 ANÁLISE COMPLETA - Recebimento de Anexos no Chat

## 🎯 VISÃO GERAL DO FLUXO

### Fluxo Completo de Recebimento (WhatsApp → Frontend)

```
1. WEBHOOK (Evolution API)
   ↓
   Evolution API envia evento 'messages.upsert' com mensagem contendo anexo
   ↓
   backend/apps/chat/webhooks.py → handle_message_upsert()
   
2. CRIAÇÃO DE PLACEHOLDER
   ↓
   - Cria Message com content
   - Cria MessageAttachment PLACEHOLDER com:
     * file_url = '' (vazio)
     * file_path = '' (vazio)
     * metadata = {'processing': True, 'media_type': 'image/audio/video/document'}
     * storage_type = 's3'
   ↓
   Frontend recebe mensagem via WebSocket → mostra "Processando..."
   
3. ENFILEIRAMENTO ASSÍNCRONO
   ↓
   process_incoming_media.delay(
       tenant_id=tenant_id,
       message_id=message_id,
       media_url=attachment_url,  # URL temporária do WhatsApp
       media_type=incoming_media_type
   )
   ↓
   RabbitMQ → QUEUE_PROCESS_INCOMING_MEDIA
   
4. PROCESSAMENTO (Worker)
   ↓
   backend/apps/chat/media_tasks.py → handle_process_incoming_media()
   
   a) DOWNLOAD (com retry)
      - Baixa mídia da URL temporária do WhatsApp
      - Retry até 3 vezes (backoff exponencial: 2s, 4s, 6s)
      
   b) PROCESSAMENTO
      - Imagem: thumbnail + resize + optimize → JPEG
      - Áudio: OGG/WEBM → MP3 (compatibilidade universal)
      - Vídeo: mantém original
      - Documento: mantém original
      
   c) UPLOAD S3 (com retry)
      - Upload arquivo processado → S3
      - Upload thumbnail (se imagem) → S3
      - Retry até 2 vezes (backoff: 1s, 2s)
      
   d) ATUALIZAÇÃO BANCO
      - Busca MessageAttachment placeholder (por message_id)
      - Atualiza com:
        * file_url = proxy URL (via get_public_url)
        * file_path = s3_path
        * thumbnail_path = thumb_s3_path (se houver)
        * size_bytes = len(processed_data)
        * mime_type = content_type (audio/mpeg se convertido)
        * metadata = {'media_type': 'image'} (remove 'processing')
      
   e) CACHE REDIS
      - Cache arquivo processado por 30 dias
      - Cache flag "existe no S3" por 5 minutos
      
   f) WEBSOCKET BROADCAST
      - Envia evento 'attachment_updated' para:
        * Grupo: chat_tenant_{tenant_id}_conversation_{conversation_id}
      - Payload:
        {
          'message_id': str,
          'attachment_id': str,
          'file_url': proxy_url,
          'thumbnail_url': thumb_url (ou None),
          'mime_type': str,
          'file_type': str,
          'metadata': dict (sem 'processing')
        }
   
5. FRONTEND ATUALIZAÇÃO
   ↓
   frontend/src/modules/chat/hooks/useChatSocket.ts
   ↓
   Listener 'attachment_updated' → handleAttachmentUpdated()
   ↓
   - Atualiza attachment na mensagem no Zustand store
   - Força re-render da mensagem completa (clonar para garantir mudança de referência)
   ↓
   frontend/src/modules/chat/components/AttachmentPreview.tsx
   ↓
   - Detecta que isProcessing = false (metadata.processing removido)
   - Detecta que fileUrl é válido (proxy URL, não WhatsApp URL)
   - Renderiza imagem/áudio/vídeo
```

---

## 📋 DETALHAMENTO TÉCNICO

### 1. WEBHOOK (webhooks.py)

**Arquivo:** `backend/apps/chat/webhooks.py`

**Função:** `handle_message_upsert()`

**Quando dispara:** Evolution API envia evento `messages.upsert` com mensagem contendo anexo.

**Processo:**
```python
# 1. Detecta tipo de mídia
if message_type == 'imageMessage':
    attachment_url = message_info.get('imageMessage', {}).get('url')
    mime_type = message_info.get('imageMessage', {}).get('mimetype', 'image/jpeg')
    incoming_media_type = 'image'
elif message_type == 'audioMessage':
    attachment_url = message_info.get('audioMessage', {}).get('url')
    mime_type = message_info.get('audioMessage', {}).get('mimetype', 'audio/ogg')
    incoming_media_type = 'audio'
# ... (video, document)

# 2. Cria MessageAttachment PLACEHOLDER
attachment = MessageAttachment.objects.create(
    message=message,
    tenant=tenant,
    original_filename=filename,
    mime_type=mime_type,
    file_path='',  # ✅ Será preenchido após processamento
    file_url='',  # ✅ Será preenchido com URL proxy após processamento
    storage_type='s3',
    size_bytes=0,
    metadata={'processing': True, 'media_type': incoming_media_type}  # ✅ Flag para frontend
)

# 3. Enfileira processamento ASSÍNCRONO
transaction.on_commit(lambda: process_incoming_media.delay(
    tenant_id=tenant_id,
    message_id=message_id,
    media_url=attachment_url,
    media_type=incoming_media_type
))
```

**Importante:**
- ✅ Placeholder é criado ANTES de processar (para frontend mostrar loading)
- ✅ `transaction.on_commit()` garante que placeholder está no banco antes de enfileirar
- ✅ `metadata={'processing': True}` indica ao frontend que está processando

---

### 2. PROCESSAMENTO ASSÍNCRONO (media_tasks.py)

**Arquivo:** `backend/apps/chat/media_tasks.py`

**Função:** `handle_process_incoming_media()`

**Fila:** `QUEUE_PROCESS_INCOMING_MEDIA`

**Processo:**

#### 2.1. DOWNLOAD (com retry)

```python
max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(media_url)
            response.raise_for_status()
            media_data = response.content
            content_type = response.headers.get('content-type', 'application/octet-stream')
        break  # ✅ Sucesso
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        retry_count += 1
        if retry_count < max_retries:
            wait_time = retry_count * 2  # Backoff: 2s, 4s, 6s
            await asyncio.sleep(wait_time)
        else:
            raise
```

**Características:**
- ✅ Retry até 3 vezes
- ✅ Backoff exponencial: 2s, 4s, 6s
- ✅ Timeout de 30 segundos

---

#### 2.2. PROCESSAMENTO

```python
# IMAGEM: thumbnail + resize + optimize
if media_type == 'image' and is_valid_image(media_data):
    result = process_image(media_data, create_thumb=True, resize=True, optimize=True)
    if result['success']:
        processed_data = result['processed_data']  # JPEG otimizado
        thumbnail_data = result['thumbnail_data']  # Thumbnail JPEG
    # Forçar content-type seguro
    if not content_type or content_type.startswith('application/octet-stream'):
        content_type = 'image/jpeg'

# ÁUDIO: OGG/WEBM → MP3
if media_type == 'audio':
    if should_convert_audio(content_type, filename):
        source_format = "webm" if ('webm' in content_type or filename.endswith('.webm')) else "ogg"
        success_conv, mp3_data, conv_msg = convert_ogg_to_mp3(processed_data, source_format=source_format)
        if success_conv and mp3_data:
            processed_data = mp3_data
            content_type = 'audio/mpeg'  # ✅ Sempre MP3 para compatibilidade
            filename = get_converted_filename(filename)  # .ogg → .mp3
```

**Características:**
- ✅ Imagens: sempre JPEG otimizado (thumbnail opcional)
- ✅ Áudio: sempre MP3 (compatibilidade universal)
- ✅ Vídeo/Documento: mantém original

---

#### 2.3. UPLOAD S3 (com retry)

```python
upload_success = False
upload_retries = 0
max_upload_retries = 2

while upload_retries <= max_upload_retries and not upload_success:
    success, msg = s3_manager.upload_to_s3(
        processed_data,
        s3_path,
        content_type=content_type
    )
    if success:
        upload_success = True
    else:
        upload_retries += 1
        if upload_retries <= max_upload_retries:
            wait_time = upload_retries * 1  # Backoff: 1s, 2s
            await asyncio.sleep(wait_time)
```

**Características:**
- ✅ Retry até 2 vezes
- ✅ Backoff: 1s, 2s
- ✅ Upload separado para thumbnail (se houver)

---

#### 2.4. ATUALIZAÇÃO BANCO

```python
# Buscar placeholder criado no webhook
existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
    message__id=message_id
).order_by('-created_at').first())()

if existing:
    # ✅ ATUALIZAR placeholder existente
    existing.file_url = public_url  # Proxy URL
    existing.file_path = s3_path
    existing.thumbnail_path = thumb_s3_path  # Se houver
    existing.size_bytes = len(processed_data)
    existing.mime_type = content_type
    existing.original_filename = filename
    existing.storage_type = 's3'
    
    # ✅ Remover flag 'processing' do metadata
    metadata = normalize_metadata(existing.metadata)
    metadata.pop('processing', None)
    metadata['media_type'] = media_type
    existing.metadata = metadata
    
    await sync_to_async(existing.save)(update_fields=[...])
else:
    # ✅ Criar novo se placeholder não existir (fallback)
    attachment = await sync_to_async(MessageAttachment.objects.create)(...)
```

**Importante:**
- ✅ Busca placeholder por `message_id` (ordem por `created_at DESC`)
- ✅ Remove `metadata.processing` após processar
- ✅ Garante `metadata` é sempre dict (normalização)

---

#### 2.5. CACHE REDIS

```python
# Cache arquivo processado por 30 dias
cache_key = f"media:{media_hash}"
cache_data = {
    'data': processed_data,
    'content_type': content_type,
}
cache_ttl = settings.ATTACHMENTS_REDIS_TTL_DAYS * 24 * 60 * 60  # 30 dias
cache.set(cache_key, cache_data, cache_ttl)

# Cache flag "existe no S3" por 5 minutos
exists_cache_key = f"s3_exists:{s3_path}"
cache.set(exists_cache_key, True, 300)  # 5 minutos
```

**Características:**
- ✅ Cache de arquivo: 30 dias (alinhado com envio)
- ✅ Cache de verificação S3: 5 minutos (performance)

---

#### 2.6. WEBSOCKET BROADCAST

```python
await channel_layer.group_send(
    f'chat_tenant_{tenant_id}_conversation_{message.conversation_id}',
    {
        'type': 'attachment_updated',
        'data': {
            'message_id': str(message_id),
            'attachment_id': str(attachment.id),
            'file_url': public_url,  # ✅ Proxy URL
            'thumbnail_url': thumbnail_url_for_ws,  # Se houver
            'mime_type': content_type,
            'file_type': media_type,
            'metadata': metadata_for_ws  # ✅ Sem 'processing'
        }
    }
)
```

**Importante:**
- ✅ Grupo: `chat_tenant_{tenant_id}_conversation_{conversation_id}`
- ✅ Evento: `attachment_updated`
- ✅ Metadata normalizado (sem `processing`)

---

### 3. FRONTEND RECEBIMENTO

**Arquivo:** `frontend/src/modules/chat/hooks/useChatSocket.ts`

**Função:** `handleAttachmentUpdated()`

```typescript
const handleAttachmentUpdated = (data: WebSocketMessage) => {
  if (data.data?.attachment_id) {
    const attachmentId = data.data.attachment_id;
    const fileUrl = data.data.file_url || '';
    
    // ✅ Atualizar attachment na mensagem
    const { messages } = useChatStore.getState();
    const messageWithAttachment = messages.find(m => 
      m.attachments?.some(a => a.id === attachmentId)
    );
    
    if (messageWithAttachment) {
      // 1. Atualizar attachment específico via updateAttachment
      updateAttachment(attachmentId, {
        file_url: fileUrl,
        thumbnail_url: data.data.thumbnail_url,
        mime_type: data.data.mime_type,
        metadata: data.data.metadata || {},
      });
      
      // 2. ✅ Forçar re-render da mensagem completa (clonar)
      const updatedMessage = {
        ...messageWithAttachment,
        attachments: messageWithAttachment.attachments?.map(att => 
          att.id === attachmentId 
            ? { ...att, file_url: fileUrl, metadata: data.data.metadata || {} }
            : att
        )
      };
      addMessage(updatedMessage);  // ✅ Clonar para garantir mudança de referência
    }
  }
};
```

**Importante:**
- ✅ Atualiza attachment específico no store
- ✅ Força re-render clonando mensagem completa

---

### 4. FRONTEND RENDERIZAÇÃO

**Arquivo:** `frontend/src/modules/chat/components/AttachmentPreview.tsx`

**Lógica de Detecção:**

```typescript
const fileUrl = (attachment.file_url || '').trim();
const metadata = attachment.metadata || {};
const hasError = Boolean(metadata.error);
const isProcessing = metadata.processing || !fileUrl || 
                     fileUrl.includes('whatsapp.net') || 
                     fileUrl.includes('evo.');

if (hasError) {
  // Mostrar erro
} else if (isProcessing) {
  // Mostrar loading skeleton
} else {
  // ✅ Renderizar imagem/áudio/vídeo
}
```

**Importante:**
- ✅ Detecta `metadata.processing` para mostrar loading
- ✅ Detecta URLs inválidas (whatsapp.net, evo.) para mostrar loading
- ✅ Renderiza apenas quando `file_url` é proxy URL válida

---

## 🔍 PROBLEMAS IDENTIFICADOS

### 1. Código Duplicado

#### a) `convert_uuids_to_str()`
- ✅ Já existe em `backend/apps/chat/utils/serialization.py`
- ❌ Duplicado em:
  - `webhooks.py` (linha 549)
  - `consumers.py` (linha 365)
  - `consumers_v2.py` (linha 438)
  - `tasks.py` (linha 461)

**Solução:** Usar `from apps.chat.utils.serialization import convert_uuids_to_str`

---

#### b) Normalização de Metadata
- ❌ Implementada inline em múltiplos lugares:
  - `media_tasks.py` (linhas 289-296, 405-412, 426-434)
  - `serializers.py` (linhas 99-109)

**Solução:** Criar utilitário `normalize_metadata()` em `utils/serialization.py`

---

### 2. Código Não Utilizado

#### a) `download_attachment` e `migrate_to_s3`
- ❌ Classes e handlers ainda existem em `tasks.py`
- ✅ Não são mais usados (substituídos por `process_incoming_media`)
- ❌ Filas ainda declaradas: `QUEUE_DOWNLOAD_ATTACHMENT`, `QUEUE_MIGRATE_S3`

**Solução:** Remover código obsoleto

---

#### b) `attachment_downloaded` Handler (Frontend)
- ❌ Handler `handleAttachmentDownloaded()` em `useChatSocket.ts`
- ✅ Não é mais usado (só `attachment_updated` é usado)

**Solução:** Remover handler não utilizado

---

#### c) `ChatConsumer` (consumers.py)
- ❌ Classe completa ainda existe
- ✅ Substituída por `ChatConsumerV2`
- ✅ Não está sendo usada no routing

**Solução:** Verificar se pode ser removida (ou marcar como deprecated)

---

#### d) `TenantChatConsumer`
- ❌ Importado em `routing.py` mas não usado
- ✅ `ChatConsumerV2` já faz o trabalho de tenant

**Solução:** Remover import não utilizado

---

## ✅ MELHORIAS SUGERIDAS

### 1. Utilitários Centralizados

```python
# backend/apps/chat/utils/serialization.py

def normalize_metadata(metadata: Any) -> dict:
    """
    Normaliza metadata para garantir que sempre seja dict.
    
    Args:
        metadata: dict, str (JSON), None ou qualquer outro tipo
        
    Returns:
        dict: Metadata normalizado (sempre dict)
    """
    if metadata is None:
        return {}
    
    if isinstance(metadata, str):
        try:
            return json.loads(metadata) if metadata else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    
    if isinstance(metadata, dict):
        return metadata
    
    # Outros tipos → dict vazio
    return {}
```

---

### 2. Remover Código Obsoleto

- ❌ Remover `download_attachment`, `migrate_to_s3` de `tasks.py`
- ❌ Remover `handleAttachmentDownloaded` de `useChatSocket.ts`
- ❌ Remover filas não utilizadas

---

### 3. Documentação

- ✅ Documentar fluxo completo de recebimento
- ✅ Documentar retry policies
- ✅ Documentar cache strategies

---

## 📊 ESTATÍSTICAS

- **Retries:** 3 tentativas para download, 2 para upload
- **Timeouts:** 30s para download, 10s para upload
- **Cache:** 30 dias para arquivo, 5 minutos para verificação S3
- **Formato Áudio:** Sempre MP3 (compatibilidade universal)
- **Formato Imagem:** Sempre JPEG otimizado (thumbnail opcional)

---

## 🎯 CONCLUSÃO

O fluxo de recebimento está bem estruturado, mas há oportunidades de melhoria:

1. ✅ **Centralizar utilitários** (evitar duplicação)
2. ✅ **Remover código obsoleto** (limpeza)
3. ✅ **Melhorar documentação** (manutenibilidade)

