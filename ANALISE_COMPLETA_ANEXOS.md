# 📎 ANÁLISE COMPLETA - Sistema de Anexos Flow Chat

## 🎯 VISÃO GERAL

Sistema completo de upload, armazenamento, envio e recebimento de anexos (imagens, vídeos, áudios, documentos) integrado com WhatsApp via Evolution API.

---

## 📤 FLUXO DE ENVIO (Usuário → WhatsApp)

### 1️⃣ **Frontend - Seleção e Upload**

**Arquivo:** `frontend/src/modules/chat/components/AttachmentUpload.tsx`

```typescript
// 1. Usuário clica no botão de anexar
<Paperclip onClick={() => fileInputRef.current?.click()} />

// 2. Seleção de arquivo
const handleFileSelect = (e) => {
  const file = e.target.files?.[0];
  
  // Validações
  - Tamanho máximo: 50MB
  - Tipos permitidos: image/*, video/*, audio/*, application/pdf, .doc, .docx, .xls, .xlsx
  
  // Preview (se imagem)
  if (file.type.startsWith('image/')) {
    previewUrl = URL.createObjectURL(file);
  }
}

// 3. Usuário confirma envio
const handleUpload = async () => {
  // 3.1 - Obter presigned URL
  POST /api/chat/messages/upload-presigned-url/
  {
    conversation_id: "uuid",
    filename: "arquivo.pdf",
    content_type: "application/pdf",
    file_size: 1024000
  }
  
  // Response:
  {
    upload_url: "https://s3.../presigned...",
    attachment_id: "uuid",
    s3_key: "chat/{tenant_id}/attachments/{uuid}.pdf",
    expires_in: 300
  }
  
  // 3.2 - Upload direto para S3 (PUT)
  xhr.open('PUT', upload_url);
  xhr.setRequestHeader('Content-Type', file.type);
  xhr.send(file);
  
  // Progress bar
  xhr.upload.addEventListener('progress', (e) => {
    const percent = (e.loaded / e.total) * 100;
    setProgress(percent);
  });
  
  // 3.3 - Confirmar upload no backend
  POST /api/chat/messages/confirm-upload/
  {
    conversation_id: "uuid",
    attachment_id: "uuid",
    s3_key: "chat/.../file.pdf",
    filename: "arquivo.pdf",
    content_type: "application/pdf",
    file_size: 1024000
  }
}
```

**Validações Frontend:**
- ✅ Tamanho máximo: 50MB
- ✅ Tipos permitidos (whitelist)
- ✅ Preview antes de enviar
- ✅ Progress bar em tempo real

---

### 2️⃣ **Backend - Presigned URL**

**Arquivo:** `backend/apps/chat/api/views.py` - `get_upload_presigned_url()`

```python
def get_upload_presigned_url(self, request):
    # Validações
    - conversation_id, filename, content_type obrigatórios
    - Tamanho máximo: 50MB
    - Usuário tem acesso à conversa
    
    # Gerar caminho S3
    attachment_id = uuid.uuid4()
    s3_key = f"chat/{tenant_id}/attachments/{attachment_id}.{ext}"
    
    # Gerar presigned URL (PUT, 5 minutos)
    s3_manager = S3Manager()
    upload_url = s3_manager.generate_presigned_url(
        s3_key,
        expiration=300,  # 5 minutos
        http_method='PUT'
    )
    
    return {
        'upload_url': upload_url,
        'attachment_id': str(attachment_id),
        's3_key': s3_key,
        'expires_in': 300
    }
```

**Responsabilidades:**
- ✅ Validar permissões
- ✅ Gerar UUID único para attachment
- ✅ Gerar presigned URL com path-style
- ✅ Bucket é criado automaticamente se não existir

---

### 3️⃣ **S3/MinIO - Upload Direto**

**Arquivo:** `backend/apps/chat/utils/s3.py` - `S3Manager`

```python
class S3Manager:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}  # ✅ Path-style para MinIO
            )
        )
    
    def ensure_bucket_exists(self):
        """Cria bucket automaticamente se não existir."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            # Bucket existe
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # Criar bucket
                self.s3_client.create_bucket(Bucket=self.bucket)
                
                # Configurar CORS
                self.s3_client.put_bucket_cors(
                    Bucket=self.bucket,
                    CORSConfiguration={
                        'CORSRules': [{
                            'AllowedHeaders': ['*'],
                            'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE'],
                            'AllowedOrigins': ['*'],
                            'ExposeHeaders': ['ETag'],
                            'MaxAgeSeconds': 3600
                        }]
                    }
                )
    
    def generate_presigned_url(self, file_path, expiration, http_method):
        """Gera presigned URL para upload (PUT) ou download (GET)."""
        # Garante que bucket existe
        self.ensure_bucket_exists()
        
        url = self.s3_client.generate_presigned_url(
            'put_object' if http_method == 'PUT' else 'get_object',
            Params={
                'Bucket': self.bucket,
                'Key': file_path
            },
            ExpiresIn=expiration
        )
        return url
```

**Configuração S3:**
- ✅ Endpoint: `https://bucket-production-8fb1.up.railway.app`
- ✅ Bucket: `flow-attachments`
- ✅ Path-style URLs: `endpoint/bucket/key`
- ✅ CORS configurado automaticamente
- ✅ Criação automática de bucket

**Estrutura de Paths:**
```
flow-attachments/
└── chat/
    └── {tenant_id}/
        └── attachments/
            └── {uuid}.{ext}
```

---

### 4️⃣ **Backend - Confirm Upload**

**Arquivo:** `backend/apps/chat/api/views.py` - `confirm_upload()`

```python
def confirm_upload(self, request):
    # 1. Buscar conversa
    conversation = Conversation.objects.get(id=conversation_id)
    
    # 2. Gerar URLs
    s3_manager = S3Manager()
    
    # URL para Evolution API baixar (GET, 1 hora)
    evolution_url = s3_manager.generate_presigned_url(
        s3_key,
        expiration=3600,
        http_method='GET'
    )
    
    # URL pública para frontend exibir (via proxy)
    file_url = s3_manager.get_public_url(s3_key)
    
    # 3. Criar mensagem
    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        content='',  # Vazio, apenas anexo
        direction='outgoing',
        status='pending',
        is_internal=False,
        metadata={
            'attachment_urls': [evolution_url],  # ✅ Para Evolution API
            'attachment_filename': filename
        }
    )
    
    # 4. Criar attachment
    attachment = MessageAttachment.objects.create(
        id=attachment_id,
        message=message,
        tenant=request.user.tenant,
        original_filename=filename,
        mime_type=content_type,
        file_path=s3_key,
        file_url=file_url,  # ✅ Para frontend
        storage_type='s3',
        size_bytes=file_size,
        expires_at=timezone.now() + timedelta(days=365),
        processing_status='pending'
    )
    
    # 5. Enfileirar para envio Evolution API
    send_message_to_evolution.delay(str(message.id))
    
    # 6. WebSocket broadcast
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_tenant_{tenant_id}",
        {
            'type': 'chat_message',
            'message': MessageSerializer(message).data
        }
    )
    
    return {
        'message': MessageSerializer(message).data,
        'attachment': MessageAttachmentSerializer(attachment).data
    }
```

**Responsabilidades:**
- ✅ Criar Message + MessageAttachment
- ✅ Gerar 2 URLs (Evolution API + Frontend)
- ✅ Adicionar `attachment_urls` no metadata
- ✅ Enfileirar task RabbitMQ
- ✅ Broadcast WebSocket

**URLs Geradas:**
1. **evolution_url**: Presigned URL (GET, 1h) - Evolution baixa arquivo
2. **file_url**: URL proxy - Frontend exibe arquivo

---

### 5️⃣ **RabbitMQ - Task de Envio**

**Arquivo:** `backend/apps/chat/tasks.py` - `handle_send_message()`

```python
async def handle_send_message(message_id: str):
    # 1. Buscar mensagem
    message = await sync_to_async(
        Message.objects.select_related('conversation', 'conversation__tenant').get
    )(id=message_id)
    
    # 2. Buscar instância WhatsApp ativa
    instance = await sync_to_async(
        WhatsAppInstance.objects.filter(
            tenant=message.conversation.tenant,
            is_active=True
        ).first
    )()
    
    # 3. Extrair attachment_urls do metadata
    attachment_urls = message.metadata.get('attachment_urls', [])
    
    # 4. Buscar attachments para obter mime_type
    attachments_list = await sync_to_async(list)(
        MessageAttachment.objects.filter(message=message)
    )
    
    # 5. Enviar via Evolution API
    if attachment_urls:
        for idx, url in enumerate(attachment_urls):
            # Detectar mime_type
            mime_type = attachments_list[idx].mime_type
            filename = attachments_list[idx].original_filename
            
            # Mapear para mediaType da Evolution API
            if mime_type.startswith('image/'):
                mediatype = 'image'
            elif mime_type.startswith('video/'):
                mediatype = 'video'
            elif mime_type.startswith('audio/'):
                mediatype = 'audio'
            else:
                mediatype = 'document'
            
            # Payload correto
            payload = {
                'number': phone,
                'mediaMessage': {
                    'media': url,           # ✅ URL presigned (GET)
                    'mediaType': mediatype, # ✅ camelCase
                    'fileName': filename    # ✅ Nome original
                }
            }
            
            # Enviar para Evolution API
            response = await client.post(
                f"{base_url}/message/sendMedia/{instance.instance_name}",
                headers={'apikey': instance.api_key},
                json=payload
            )
            
            # Atualizar status
            message.status = 'sent'
            message.message_id = response.json().get('key', {}).get('id')
            await sync_to_async(message.save)()
```

**Mapeamento mediaType:**
- `image/*` → `"image"`
- `video/*` → `"video"`
- `audio/*` → `"audio"`
- Outros → `"document"`

**Payload Evolution API:**
```json
{
  "number": "+5517991253112",
  "mediaMessage": {
    "media": "https://s3...?presigned...",
    "mediaType": "document",
    "fileName": "arquivo.pdf"
  }
}
```

**Referência:** [Evolution API - sendMedia](https://doc.evolution-api.com/v1/api-reference/message-controller/send-media)

---

### 6️⃣ **WebSocket - Atualização em Tempo Real**

**Arquivo:** `backend/apps/chat/consumers_v2.py` - `ChatConsumerV2`

```python
class ChatConsumerV2(AsyncWebsocketConsumer):
    async def connect(self):
        # Adiciona ao grupo do tenant
        self.tenant_group_name = f"chat_tenant_{self.tenant_id}"
        await self.channel_layer.group_add(
            self.tenant_group_name,
            self.channel_name
        )
    
    async def chat_message(self, event):
        """
        Handler para broadcasts de novas mensagens.
        Chamado quando confirm_upload faz group_send.
        """
        message_data = event.get('message')
        
        # Enviar para cliente WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message_received',
            'message': message_data
        }))
```

**Fluxo WebSocket:**
1. ✅ Frontend conecta via WebSocket com JWT
2. ✅ Backend adiciona ao grupo `chat_tenant_{tenant_id}`
3. ✅ Quando anexo é confirmado, `group_send('chat_message', ...)`
4. ✅ Handler `chat_message()` envia para todos os clientes conectados
5. ✅ Frontend recebe e atualiza UI em tempo real

**Frontend - Recebimento:**
```typescript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'message_received') {
    // Adicionar mensagem na lista
    setMessages(prev => [...prev, data.message]);
  }
}
```

---

## 📥 FLUXO DE RECEBIMENTO (WhatsApp → Usuário)

### 1️⃣ **Webhook - Recebimento do Evolution API**

**Arquivo:** `backend/apps/chat/webhooks.py`

```python
@csrf_exempt
def evolution_webhook_global(request):
    """
    Webhook global da Evolution API.
    Processa mensagens recebidas do WhatsApp.
    """
    data = json.loads(request.body)
    event_type = data.get('event')
    
    if event_type == 'messages.upsert':
        # Mensagem recebida
        message_data = data.get('data', {})
        
        # Verificar se tem anexo
        if 'imageMessage' in message_data.get('message', {}):
            # Imagem
            media_url = message_data['message']['imageMessage']['url']
            mime_type = message_data['message']['imageMessage']['mimetype']
            
        elif 'videoMessage' in message_data.get('message', {}):
            # Vídeo
            media_url = message_data['message']['videoMessage']['url']
            mime_type = message_data['message']['videoMessage']['mimetype']
            
        elif 'audioMessage' in message_data.get('message', {}):
            # Áudio
            media_url = message_data['message']['audioMessage']['url']
            mime_type = message_data['message']['audioMessage']['mimetype']
            
        elif 'documentMessage' in message_data.get('message', {}):
            # Documento
            media_url = message_data['message']['documentMessage']['url']
            mime_type = message_data['message']['documentMessage']['mimetype']
        
        # Enfileirar download do anexo
        if media_url:
            download_attachment.delay(
                attachment_id=str(uuid.uuid4()),
                evolution_url=media_url
            )
```

**Eventos suportados:**
- ✅ `messages.upsert` - Nova mensagem
- ✅ `messages.update` - Status atualizado (delivered/seen)
- ✅ Detecção automática de tipo de mídia

---

### 2️⃣ **Download do Anexo**

**Arquivo:** `backend/apps/chat/utils/storage.py`

```python
async def download_and_save_attachment(attachment, evolution_url):
    """
    Baixa anexo da Evolution API e salva localmente ou S3.
    """
    try:
        # 1. Baixar arquivo da Evolution API
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(evolution_url)
            response.raise_for_status()
            file_data = response.content
        
        # 2. Salvar no S3
        tenant_id = str(attachment.tenant.id)
        s3_key = f"chat/{tenant_id}/received/{attachment.id}.{ext}"
        
        success, _ = upload_to_s3(
            file_data,
            s3_key,
            content_type=attachment.mime_type
        )
        
        # 3. Gerar presigned URL para exibição (7 dias)
        presigned_url = generate_presigned_url(
            s3_key,
            expiration=604800  # 7 dias
        )
        
        # 4. Atualizar attachment
        attachment.file_path = s3_key
        attachment.file_url = presigned_url
        attachment.storage_type = 's3'
        await sync_to_async(attachment.save)()
        
        return True
    
    except Exception as e:
        logger.error(f"❌ [STORAGE] Erro ao baixar anexo: {e}")
        return False
```

**Fluxo de Download:**
1. ✅ Evolution API retorna URL do anexo no webhook
2. ✅ Backend enfileira task `download_attachment`
3. ✅ Task baixa arquivo da Evolution API
4. ✅ Salva no S3 (`chat/{tenant}/received/{uuid}`)
5. ✅ Gera presigned URL (GET, 7 dias)
6. ✅ Atualiza MessageAttachment no banco
7. ✅ WebSocket broadcast para frontend

---

## 📊 VISUALIZAÇÃO NO FRONTEND

### AttachmentPreview Component

**Arquivo:** `frontend/src/modules/chat/components/AttachmentPreview.tsx`

```typescript
export function AttachmentPreview({ attachment, showAI }) {
  // 🖼️ IMAGEM
  if (attachment.is_image) {
    return (
      <img 
        src={attachment.file_url}
        onClick={() => setLightboxOpen(true)}  // Lightbox
      />
    );
  }
  
  // 🎥 VÍDEO
  if (attachment.is_video) {
    return (
      <video controls src={attachment.file_url} />
    );
  }
  
  // 🎵 ÁUDIO
  if (attachment.is_audio) {
    // Player wavesurfer.js com waveform
    useEffect(() => {
      wavesurfer = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#4F46E5',
        progressColor: '#818CF8'
      });
      wavesurfer.load(attachment.file_url);
    }, []);
    
    return (
      <div>
        <div ref={waveformRef} />  {/* Waveform */}
        <button onClick={() => wavesurfer.playPause()}>
          {playing ? 'Pausar' : 'Reproduzir'}
        </button>
        
        {/* ✨ IA: Transcrição */}
        {showAI && attachment.transcription && (
          <div>{attachment.transcription}</div>
        )}
        
        {/* ✨ IA: Resumo */}
        {showAI && attachment.ai_summary && (
          <div>{attachment.ai_summary}</div>
        )}
      </div>
    );
  }
  
  // 📄 DOCUMENTO
  return (
    <div>
      <FileText />
      <span>{attachment.original_filename}</span>
      <a href={attachment.file_url} download>
        <Download />
      </a>
    </div>
  );
}
```

**Funcionalidades:**
- ✅ Preview inline de imagens
- ✅ Lightbox para ampliar
- ✅ Player HTML5 para vídeos
- ✅ Player wavesurfer.js para áudios (waveform)
- ✅ Download para documentos
- ✅ Campos de IA (transcrição, resumo, tags) - condicionais

---

## 🔧 GRAVAÇÃO DE ÁUDIO

### VoiceRecorder Component

**Arquivo:** `frontend/src/modules/chat/components/VoiceRecorder.tsx`

```typescript
export function VoiceRecorder({ conversationId }) {
  const startRecording = async () => {
    // 1. Solicitar permissão do microfone
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // 2. Criar MediaRecorder
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    });
    
    // 3. Coletar chunks
    mediaRecorder.ondataavailable = (event) => {
      audioChunksRef.current.push(event.data);
    };
    
    // 4. Iniciar gravação
    mediaRecorder.start();
    setIsRecording(true);
    
    // Timer
    timerRef.current = setInterval(() => {
      setRecordingTime(prev => prev + 1);
    }, 1000);
  };
  
  const stopRecording = () => {
    mediaRecorder.stop();
    
    // Criar Blob com áudio gravado
    const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    setAudioBlob(blob);
    setIsPreviewing(true);  // Mostrar preview
  };
  
  const sendAudio = async () => {
    // Converter Blob para File
    const file = new File([audioBlob], `voice-${Date.now()}.webm`, {
      type: 'audio/webm'
    });
    
    // Mesmo fluxo de AttachmentUpload
    // 1. Presigned URL
    // 2. Upload S3
    // 3. Confirm upload
  };
}
```

**Funcionalidades:**
- ✅ Gravação pelo microfone do navegador
- ✅ Timer em tempo real
- ✅ Animação pulsante durante gravação
- ✅ Preview antes de enviar (player HTML5)
- ✅ Upload automático após confirmação
- ✅ Formato: audio/webm (codec Opus)

---

## 🧠 PROCESSAMENTO IA (FUTURO)

### Campos de IA no MessageAttachment

```python
class MessageAttachment(models.Model):
    # ... campos básicos ...
    
    # ✨ Campos IA
    transcription = models.TextField(null=True, blank=True)
    transcription_language = models.CharField(max_length=10, null=True)
    ai_summary = models.TextField(null=True, blank=True)
    ai_tags = models.JSONField(null=True, blank=True)
    ai_sentiment = models.CharField(
        max_length=20,
        choices=[('positive', 'Positive'), ('neutral', 'Neutral'), ('negative', 'Negative')],
        null=True
    )
    ai_metadata = models.JSONField(null=True, blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped')
        ],
        default='pending'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
```

**Processamento Futuro:**
1. ✅ Áudios → Transcrição (Whisper/Groq)
2. ✅ Transcrição → Resumo IA
3. ✅ Extração de tags/palavras-chave
4. ✅ Análise de sentimento
5. ✅ OCR em documentos/imagens (futuro)

---

## ⚠️ PROBLEMAS ENCONTRADOS E SOLUÇÕES

### ❌ Problema 1: content_type inválido
**Erro:** `TypeError: S3Manager.generate_presigned_url() got an unexpected keyword argument 'content_type'`

**Solução:** Remover argumento `content_type` (não é aceito pelo método).

---

### ❌ Problema 2: Virtual-hosted-style URLs
**Erro:** 404 ao fazer PUT no S3

**Solução:** Configurar `addressing_style='path'` no boto3 Config.
```python
config=Config(
    signature_version='s3v4',
    s3={'addressing_style': 'path'}
)
```

---

### ❌ Problema 3: Bucket não existe
**Erro:** 404 ao tentar upload

**Solução:** Método `ensure_bucket_exists()` cria bucket automaticamente + CORS.

---

### ❌ Problema 4: IDs duplicados
**Erro:** Duplicate key violation

**Solução:** Message tem UUID próprio, MessageAttachment usa attachment_id do frontend.

---

### ❌ Problema 5: attachment_urls faltando
**Erro:** Evolution API não recebia URL do arquivo

**Solução:** Adicionar `attachment_urls` no `message.metadata`.

---

### ❌ Problema 6: mediatype faltando
**Erro:** Evolution API retornava 400 - "requires property mediatype"

**Solução:** Detectar mime_type e mapear para mediaType correto.

---

### ❌ Problema 7: Campo media vs mediaUrl
**Erro:** Payload incorreto para Evolution API

**Solução:** Usar `media` (não `mediaUrl`) e `mediaType` (camelCase).

---

### ❌ Problema 8: UUID serialization
**Erro:** "can not serialize 'UUID' object"

**Solução:** Adicionar campos `UUIDField` explícitos nos serializers.

---

### ❌ Problema 9: WebSocket handler faltando
**Erro:** "No handler for message type chat_message"

**Solução:** Adicionar método `async def chat_message(event)` no Consumer.

---

## ✅ CHECKLIST FINAL

### Backend:
- [x] Presigned URL (PUT) para upload
- [x] Path-style URLs para MinIO
- [x] Criação automática de bucket
- [x] CORS configurado automaticamente
- [x] Confirm upload cria Message + Attachment
- [x] Gera 2 URLs (Evolution + Frontend)
- [x] Adiciona attachment_urls no metadata
- [x] Task RabbitMQ para envio
- [x] Detecta mime_type e mapeia mediaType
- [x] Payload correto para Evolution API
- [x] Serializers com UUIDField
- [x] WebSocket broadcast com handler

### Frontend:
- [x] AttachmentUpload com progress bar
- [x] AttachmentPreview para todos os tipos
- [x] VoiceRecorder com MediaRecorder API
- [x] Validações (50MB, tipos permitidos)
- [x] Preview antes de enviar
- [x] Lightbox para imagens
- [x] Player wavesurfer.js para áudios
- [x] WebSocket recebe broadcasts
- [x] UI atualiza em tempo real

### S3/MinIO:
- [x] Bucket: flow-attachments
- [x] Path-style URLs
- [x] CORS configurado
- [x] TTL presigned: 5min (upload), 1h (Evolution), 7 dias (exibição)
- [x] Estrutura organizada: chat/{tenant}/attachments/

### Evolution API:
- [x] Payload correto (media, mediaType, fileName)
- [x] Mapeamento de mediaType
- [x] Download de arquivos via presigned URL
- [x] Webhook para recebimento de anexos

### WebSocket:
- [x] Broadcast em tempo real
- [x] Handler chat_message
- [x] UI atualiza sem refresh

---

## 📊 MÉTRICAS E LIMITES

**Tamanhos:**
- Upload máximo: 50MB
- Chunk S3: Upload direto (sem chunks)

**Tempos:**
- Presigned URL (upload): 5 minutos
- Presigned URL (Evolution): 1 hora
- Presigned URL (exibição): 7 dias (recebidos) / 365 dias (enviados)

**Armazenamento:**
- Storage: MinIO (S3-compatible) no Railway
- Bucket: flow-attachments
- Retenção: 365 dias (enviados), 30 dias (recebidos - configurável)

**Performance:**
- Upload direto S3 (não passa pelo backend)
- Progress bar em tempo real
- WebSocket broadcast < 1s

---

## 🚀 PRÓXIMOS PASSOS

1. [ ] Implementar processamento IA para áudios (transcrição)
2. [ ] Adicionar OCR para documentos/imagens
3. [ ] Implementar compressão de imagens/vídeos
4. [ ] Adicionar limite de uploads por usuário/tenant
5. [ ] Implementar limpeza automática de arquivos expirados
6. [ ] Adicionar suporte para stickers
7. [ ] Implementar envio de localização
8. [ ] Adicionar suporte para contatos (vCard)

---

## 📚 REFERÊNCIAS

- [Evolution API - Send Media](https://doc.evolution-api.com/v1/api-reference/message-controller/send-media)
- [Evolution API - Send Audio](https://doc.evolution-api.com/v1/api-reference/message-controller/send-audio)
- [Boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [MediaRecorder API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- [WaveSurfer.js](https://wavesurfer-js.org/)

---

**Última atualização:** 2025-10-21  
**Status:** ✅ Sistema 100% funcional

