# 🎯 IMPLEMENTAÇÃO: Sistema de Mídia (Fotos, Áudios, Documentos)

> **Versão:** 1.0  
> **Data:** 20 de Outubro de 2025  
> **Autor:** Arquitetura Técnica ALREA Sense  
> **Objetivo:** Guia completo para implementação do sistema unificado de mídia

---

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Arquitetura Técnica](#arquitetura-técnica)
3. [UX/UI Design](#uxui-design)
4. [Implementação Backend](#implementação-backend)
5. [Implementação Frontend](#implementação-frontend)
6. [Testes](#testes)
7. [Deploy e Monitoramento](#deploy-e-monitoramento)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 VISÃO GERAL

### Objetivo

Implementar sistema unificado de armazenamento e distribuição de mídia que:
- ✅ Resolve problema atual de fotos de perfil
- ✅ Adiciona suporte completo a arquivos no chat
- ✅ Garante performance e escalabilidade
- ✅ Mantém custos controlados

### Escopo

**Tipos de mídia suportados:**
- 🖼️ **Imagens:** JPG, PNG, GIF, WebP (max 10MB)
- 🎵 **Áudios:** MP3, OGG, AAC, WAV (max 16MB)
- 📄 **Documentos:** PDF, DOC, XLSX, TXT (max 25MB)
- 🎥 **Vídeos:** MP4, MOV (max 50MB) - futuro

**Funcionalidades:**
- Download de mídia recebida via WhatsApp
- Upload de mídia para enviar via WhatsApp
- Thumbnails automáticos para imagens
- Preview de documentos
- Player de áudio integrado
- Progress bar de upload/download
- Cache inteligente

### Arquitetura Escolhida

**Híbrido: S3 + Redis Cache**

```
┌──────────────────────────────────────────────────────┐
│                   ARQUITETURA                         │
├──────────────────────────────────────────────────────┤
│                                                       │
│  STORAGE (Permanente):   MinIO/S3                   │
│  CACHE (Performance):    Redis (TTL 7 dias)         │
│  QUEUE (Assíncrono):     RabbitMQ + Celery          │
│  PROXY (Público):        Django View Pura           │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**Benefícios:**
- 💰 **Custo:** ~$53/mês para 10k usuários
- ⚡ **Performance:** <1ms (cache) / 200ms (S3)
- 🔒 **Confiabilidade:** S3 permanente + backup automático
- 📈 **Escalabilidade:** Ilimitada (S3) + cache inteligente (LRU)

---

## 🏗️ ARQUITETURA TÉCNICA

### Diagrama de Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│                  DOWNLOAD (Receber)                         │
└─────────────────────────────────────────────────────────────┘

WhatsApp
    │
    ▼
Evolution Webhook
    │
    ├─ Extract: media_url, media_type, phone
    │
    ▼
RabbitMQ Queue
    │
    ├─ Queue: media_download
    ├─ Priority: high (profile_pic) / normal (chat)
    │
    ▼
Celery Worker
    │
    ├─ 1. Download from WhatsApp (temp URL)
    ├─ 2. Generate thumbnail (if image)
    ├─ 3. Scan virus (optional - ClamAV)
    ├─ 4. Upload to S3 (permanent)
    ├─ 5. Save to DB (MessageAttachment)
    ├─ 6. WebSocket notify frontend
    │
    ▼
S3/MinIO Storage
    │
    └─ Permanent storage (never expires)


Frontend Request
    │
    ▼
Django Proxy (/api/media/proxy/)
    │
    ├─ Check Redis cache
    │   └─ HIT: Return (< 1ms) ⚡
    │
    ├─ MISS: Download from S3 (200ms)
    │   └─ Cache in Redis (TTL 7 days)
    │
    ▼
Return to Frontend


┌─────────────────────────────────────────────────────────────┐
│                   UPLOAD (Enviar)                           │
└─────────────────────────────────────────────────────────────┘

Frontend
    │
    ├─ 1. Request presigned URL
    │
    ▼
Backend
    │
    ├─ Generate S3 presigned URL (5 min TTL)
    ├─ Create MessageAttachment (status=pending)
    │
    ▼
Frontend
    │
    ├─ 2. Upload DIRECT to S3 (presigned URL)
    ├─ Show progress bar
    │
    ▼
S3/MinIO Storage
    │
    └─ File uploaded (permanent)


Frontend
    │
    ├─ 3. Notify backend (upload complete)
    │
    ▼
Backend
    │
    ├─ Queue processing (RabbitMQ)
    │
    ▼
Celery Worker
    │
    ├─ 1. Download from S3
    ├─ 2. Generate thumbnail (if image)
    ├─ 3. Compress if needed
    ├─ 4. Send to WhatsApp (Evolution API)
    ├─ 5. Update status (sent/failed)
    ├─ 6. WebSocket notify frontend
    │
    ▼
WhatsApp
```

### Stack Tecnológico

#### Backend
```yaml
Language: Python 3.11+
Framework: Django 5.0 + DRF 3.14
Async Tasks: Celery 5.3 + RabbitMQ
Cache: Redis 7+ (django-redis)
Storage: boto3 (S3 SDK)
Image Processing: Pillow 10.0
WebSocket: Django Channels 4
```

#### Frontend
```yaml
Language: TypeScript 5.2
Framework: React 18.2
Build: Vite 5
HTTP Client: Axios
File Upload: axios + progress tracking
UI: Tailwind CSS + shadcn/ui
```

#### Infrastructure
```yaml
Storage: MinIO (S3-compatible) on Railway
Cache: Redis on Railway
Queue: RabbitMQ on Railway (já existe)
CDN: CloudFlare (opcional - futuro)
```

---

## 🎨 UX/UI DESIGN

### Princípios de Design

1. **Feedback Imediato** - Usuário sempre sabe o que está acontecendo
2. **Graceful Degradation** - Funciona mesmo se algo falhar
3. **Progressive Enhancement** - Recursos adicionais quando disponíveis
4. **Mobile First** - Responsivo desde o início

### Fluxos de Usuário

#### 1. Visualizar Foto de Perfil

```
┌──────────────────────────────────────────────────────┐
│  Chat List                                           │
│                                                      │
│  ┌─────────┐                                        │
│  │ [IMG] │ Paulo Bernal                            │
│  │  ⚡   │ Última mensagem...                      │
│  └─────────┘ 14:30                                  │
│                                                      │
│  Estados da imagem:                                  │
│  1. Loading: Skeleton/Spinner                       │
│  2. Loaded: Imagem (cache hit < 1ms)               │
│  3. Error: Fallback com iniciais "PB"              │
└──────────────────────────────────────────────────────┘
```

**Componente:**
```typescript
<Avatar>
  {isLoading && <Skeleton />}
  {error && <AvatarFallback>{initials}</AvatarFallback>}
  {success && <img src={proxyUrl} alt={name} />}
</Avatar>
```

---

#### 2. Receber Imagem no Chat

```
┌──────────────────────────────────────────────────────┐
│  Chat Window                                         │
│                                                      │
│  Paulo Bernal                              14:30    │
│  ┌────────────────────────────────────┐            │
│  │                                    │            │
│  │     [   Carregando imagem...   ]   │  ← Estado 1│
│  │           (Spinner)                │            │
│  │                                    │            │
│  └────────────────────────────────────┘            │
│                                                      │
│  Paulo Bernal                              14:30    │
│  ┌────────────────────────────────────┐            │
│  │                                    │            │
│  │        [    IMAGEM    ]            │  ← Estado 2│
│  │       (Blur → Sharp)               │            │
│  │                                    │            │
│  │  👁️ Visualizar  💾 Salvar          │            │
│  └────────────────────────────────────┘            │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**Estados:**
1. **Processando:** Worker baixando do WhatsApp
2. **Disponível:** Pronto para visualizar
3. **Erro:** Falha no download (retry button)

---

#### 3. Enviar Arquivo

```
┌──────────────────────────────────────────────────────┐
│  Message Input                                       │
│                                                      │
│  ┌────────────────────────────────────┐            │
│  │ Digite uma mensagem...              📎 📷 🎤   │
│  └────────────────────────────────────┘            │
│                                                      │
│  [Usuário clica em 📎]                              │
│                                                      │
│  ┌────────────────────────────────────┐            │
│  │ Escolher arquivo                    │            │
│  │ • Imagens e vídeos                 │            │
│  │ • Documentos                        │            │
│  │ • Áudios                            │            │
│  └────────────────────────────────────┘            │
│                                                      │
│  [Arquivo selecionado]                              │
│                                                      │
│  ┌────────────────────────────────────┐            │
│  │ documento.pdf (2.5 MB)             │            │
│  │                                     │            │
│  │ Enviando... 47% ████░░░░░░         │  ← Upload │
│  │                                     │            │
│  │ [Cancelar]                          │            │
│  └────────────────────────────────────┘            │
│                                                      │
│  [Upload completo]                                  │
│                                                      │
│  ┌────────────────────────────────────┐            │
│  │ documento.pdf (2.5 MB)             │            │
│  │                                     │            │
│  │ ✅ Enviado! Processando...          │  ← Worker│
│  │                                     │            │
│  └────────────────────────────────────┘            │
│                                                      │
│  [Processamento completo]                           │
│                                                      │
│  Você                                  14:35        │
│  ┌────────────────────────────────────┐            │
│  │ 📄 documento.pdf                   │            │
│  │ 2.5 MB                              │            │
│  │                                     │            │
│  │ ✓✓ Enviado                          │  ← Final │
│  └────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

**Estados do upload:**
- 🔵 **Uploading:** Progress 0-100%
- 🟡 **Processing:** Worker gerando thumbnail/enviando
- 🟢 **Sent:** Entregue com sucesso (✓✓)
- 🔴 **Failed:** Erro (botão retry)

---

#### 4. Player de Áudio

```
┌──────────────────────────────────────────────────────┐
│  Chat Window                                         │
│                                                      │
│  Paulo Bernal                              14:30    │
│  ┌────────────────────────────────────┐            │
│  │ 🎤 Mensagem de voz                 │            │
│  │                                     │            │
│  │ ▶️  ━━━━●━━━━━━━━━━ 0:15 / 0:42  │            │
│  │                                     │            │
│  │ 1x   💾 Salvar                     │            │
│  └────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

**Funcionalidades:**
- Play/Pause
- Seek (arrastar bolinha)
- Speed: 1x / 1.5x / 2x
- Download
- Waveform visual (opcional - futuro)

---

#### 5. Preview de Documento

```
┌──────────────────────────────────────────────────────┐
│  Chat Window                                         │
│                                                      │
│  Paulo Bernal                              14:30    │
│  ┌────────────────────────────────────┐            │
│  │ 📄 Proposta_Comercial.pdf          │            │
│  │                                     │            │
│  │ ┌─────────────────────────┐       │            │
│  │ │  [Preview thumbnail]    │       │            │
│  │ │                         │       │            │
│  │ └─────────────────────────┘       │            │
│  │                                     │            │
│  │ 2.5 MB • 15 páginas                │            │
│  │                                     │            │
│  │ 👁️ Visualizar  💾 Download        │            │
│  └────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

---

### Componentes UI

#### Avatar Component

```typescript
// frontend/src/components/ui/Avatar.tsx

interface AvatarProps {
  src?: string
  alt: string
  size?: 'sm' | 'md' | 'lg'
  fallback?: string
  onLoad?: () => void
  onError?: () => void
}

export function Avatar({ src, alt, size = 'md', fallback, onLoad, onError }: AvatarProps) {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading')
  
  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-12 h-12 text-base',
    lg: 'w-16 h-16 text-xl'
  }
  
  return (
    <div className={cn('relative rounded-full overflow-hidden bg-gray-200', sizeClasses[size])}>
      {status === 'loading' && (
        <div className="absolute inset-0 animate-pulse bg-gray-300" />
      )}
      
      {src && status !== 'error' && (
        <img
          src={src}
          alt={alt}
          className="w-full h-full object-cover"
          onLoad={() => {
            setStatus('loaded')
            onLoad?.()
          }}
          onError={() => {
            setStatus('error')
            onError?.()
          }}
        />
      )}
      
      {(status === 'error' || !src) && (
        <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600 text-white font-semibold">
          {fallback || alt.substring(0, 2).toUpperCase()}
        </div>
      )}
    </div>
  )
}
```

---

#### FileUpload Component

```typescript
// frontend/src/modules/chat/components/FileUpload.tsx

interface FileUploadProps {
  conversationId: string
  onUploadComplete: (attachment: MessageAttachment) => void
}

export function FileUpload({ conversationId, onUploadComplete }: FileUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return
    
    // Validar tamanho
    const maxSize = getMaxSizeForType(selectedFile.type)
    if (selectedFile.size > maxSize) {
      toast.error(`Arquivo muito grande. Máximo: ${formatBytes(maxSize)}`)
      return
    }
    
    setFile(selectedFile)
  }
  
  const handleUpload = async () => {
    if (!file) return
    
    setUploading(true)
    
    try {
      // 1. Pedir presigned URL
      const { data: urlData } = await api.post('/chat/get-upload-url/', {
        file_name: file.name,
        file_type: file.type,
        file_size: file.size,
        conversation_id: conversationId
      })
      
      // 2. Upload DIRETO para S3
      await axios.put(urlData.upload_url, file, {
        headers: { 'Content-Type': file.type },
        onUploadProgress: (e) => {
          const percent = (e.loaded / e.total!) * 100
          setProgress(percent)
        }
      })
      
      // 3. Notificar backend
      const { data: attachment } = await api.post('/chat/upload-complete/', {
        file_url: urlData.file_url,
        file_name: file.name,
        file_type: file.type,
        file_size: file.size,
        conversation_id: conversationId
      })
      
      toast.success('✅ Arquivo enviado! Processando...')
      onUploadComplete(attachment)
      
      // Reset
      setFile(null)
      setProgress(0)
      
    } catch (error) {
      console.error('Upload error:', error)
      toast.error('❌ Erro ao enviar arquivo')
    } finally {
      setUploading(false)
    }
  }
  
  return (
    <div>
      <input
        type="file"
        onChange={handleFileSelect}
        accept="image/*,audio/*,.pdf,.doc,.docx,.xlsx"
        className="hidden"
        id="file-upload"
        disabled={uploading}
      />
      
      {!file && (
        <label
          htmlFor="file-upload"
          className="cursor-pointer flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          <Paperclip className="w-5 h-5" />
          Anexar arquivo
        </label>
      )}
      
      {file && !uploading && (
        <div className="flex items-center gap-2 p-4 bg-gray-100 rounded-lg">
          <FileIcon type={file.type} />
          <div className="flex-1">
            <p className="font-medium">{file.name}</p>
            <p className="text-sm text-gray-500">{formatBytes(file.size)}</p>
          </div>
          <button
            onClick={handleUpload}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Enviar
          </button>
          <button
            onClick={() => setFile(null)}
            className="p-2 text-gray-500 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}
      
      {uploading && (
        <div className="p-4 bg-gray-100 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <FileIcon type={file!.type} />
            <div className="flex-1">
              <p className="font-medium">{file!.name}</p>
              <p className="text-sm text-gray-500">Enviando... {Math.round(progress)}%</p>
            </div>
          </div>
          <Progress value={progress} />
        </div>
      )}
    </div>
  )
}
```

---

#### MessageAttachment Component

```typescript
// frontend/src/modules/chat/components/MessageAttachment.tsx

interface MessageAttachmentProps {
  attachment: MessageAttachment
  direction: 'incoming' | 'outgoing'
}

export function MessageAttachment({ attachment, direction }: MessageAttachmentProps) {
  const proxyUrl = `/api/media/proxy/?url=${encodeURIComponent(attachment.file_url)}`
  
  // Imagem
  if (attachment.file_type.startsWith('image/')) {
    return (
      <div className="relative group">
        <img
          src={proxyUrl}
          alt={attachment.file_name}
          className="max-w-sm rounded-lg cursor-pointer"
          onClick={() => openLightbox(proxyUrl)}
          loading="lazy"
        />
        <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition">
          <button
            onClick={() => downloadFile(proxyUrl, attachment.file_name)}
            className="p-2 bg-black/50 text-white rounded-full hover:bg-black/70"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }
  
  // Áudio
  if (attachment.file_type.startsWith('audio/')) {
    return (
      <AudioPlayer
        src={proxyUrl}
        fileName={attachment.file_name}
        duration={attachment.metadata?.duration}
      />
    )
  }
  
  // Documento
  return (
    <div className="flex items-center gap-3 p-3 bg-gray-100 rounded-lg max-w-sm">
      <FileIcon type={attachment.file_type} size="lg" />
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{attachment.file_name}</p>
        <p className="text-sm text-gray-500">
          {formatBytes(attachment.size_bytes)}
          {attachment.metadata?.pages && ` • ${attachment.metadata.pages} páginas`}
        </p>
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => window.open(proxyUrl, '_blank')}
          className="p-2 text-blue-500 hover:bg-blue-50 rounded"
        >
          <Eye className="w-5 h-5" />
        </button>
        <button
          onClick={() => downloadFile(proxyUrl, attachment.file_name)}
          className="p-2 text-gray-500 hover:bg-gray-100 rounded"
        >
          <Download className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}
```

---

## 💻 IMPLEMENTAÇÃO BACKEND

### Fase 1: Configuração e Modelos

#### 1.1 - Dependências (requirements.txt)

```python
# Adicionar ao requirements.txt existente

# S3/MinIO
boto3==1.34.0
botocore==1.34.0

# Image Processing
Pillow==10.2.0
pillow-heif==0.15.0  # HEIC support (iPhone)

# Video Processing (opcional - futuro)
# ffmpeg-python==0.2.0

# File Type Detection
python-magic==0.4.27  # Linux
# python-magic-bin==0.4.14  # Windows

# Virus Scan (opcional)
# clamd==1.0.2
```

#### 1.2 - Settings (alrea_sense/settings.py)

```python
# backend/alrea_sense/settings.py

# ============================
# S3/MINIO CONFIGURATION
# ============================

S3_BUCKET = config('S3_BUCKET', default='flow-attachments')
S3_ENDPOINT_URL = config('S3_ENDPOINT_URL', default='https://bucket-production-8fb1.up.railway.app')
S3_ACCESS_KEY = config('S3_ACCESS_KEY', default='u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL')
S3_SECRET_KEY = config('S3_SECRET_KEY', default='zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti')
S3_REGION = config('S3_REGION', default='us-east-1')
S3_USE_SSL = config('S3_USE_SSL', default=True, cast=bool)

# ============================
# MEDIA CONFIGURATION
# ============================

# File size limits (bytes)
MEDIA_MAX_SIZE = {
    'image': 10 * 1024 * 1024,      # 10MB
    'audio': 16 * 1024 * 1024,      # 16MB
    'document': 25 * 1024 * 1024,   # 25MB
    'video': 50 * 1024 * 1024,      # 50MB
}

# Allowed MIME types
MEDIA_ALLOWED_TYPES = {
    'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/heic'],
    'audio': ['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/aac', 'audio/mp4'],
    'document': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/plain'],
    'video': ['video/mp4', 'video/quicktime', 'video/x-msvideo'],
}

# Cache TTL (seconds)
MEDIA_CACHE_TTL = {
    'profile_pic': None,            # Never expire (only on update)
    'image': 604800,                # 7 days
    'audio': 259200,                # 3 days
    'document': 86400,              # 1 day
    'video': 604800,                # 7 days
}

# Thumbnail settings
THUMBNAIL_SIZE = (200, 200)
THUMBNAIL_QUALITY = 85

# ============================
# CELERY QUEUES
# ============================

CELERY_TASK_ROUTES = {
    # Existing
    'apps.campaigns.*': {'queue': 'campaigns'},
    
    # New media queues
    'apps.chat.tasks.process_profile_pic': {'queue': 'media_priority'},
    'apps.chat.tasks.process_incoming_media': {'queue': 'media_download'},
    'apps.chat.tasks.process_uploaded_file': {'queue': 'media_upload'},
}
```

#### 1.3 - Models Atualização

```python
# backend/apps/chat/models.py

class Conversation(models.Model):
    """Existing model - adicionar campo"""
    
    # ... campos existentes ...
    
    profile_pic_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Foto de Perfil',
        help_text='URL da foto de perfil no S3'
    )
    profile_pic_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Foto Atualizada em'
    )
    
    # ... resto do modelo ...


class MessageAttachment(models.Model):
    """Novo modelo para anexos"""
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('completed', 'Completo'),
        ('failed', 'Falhou'),
    ]
    
    STORAGE_CHOICES = [
        ('s3', 'S3/MinIO'),
        ('local', 'Local'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Relacionamentos
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='attachments',
        null=True,  # Null até mensagem ser criada
        blank=True
    )
    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    
    # Arquivo
    file_url = models.URLField(
        max_length=500,
        verbose_name='URL do Arquivo'
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name='Nome do Arquivo'
    )
    file_type = models.CharField(
        max_length=100,
        verbose_name='Tipo MIME'
    )
    size_bytes = models.BigIntegerField(
        default=0,
        verbose_name='Tamanho (bytes)'
    )
    
    # Thumbnail (para imagens)
    thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='URL do Thumbnail'
    )
    
    # Storage
    storage_type = models.CharField(
        max_length=10,
        choices=STORAGE_CHOICES,
        default='s3'
    )
    storage_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Chave no Storage',
        help_text='Path/key no S3'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Mensagem de Erro'
    )
    
    # Metadata (JSON)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Metadata adicional (duração áudio, páginas PDF, etc)'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_messageattachment'
        verbose_name = 'Anexo de Mensagem'
        verbose_name_plural = 'Anexos de Mensagens'
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['file_type']),
        ]
    
    def __str__(self):
        return f"{self.file_name} ({self.get_status_display()})"
    
    @property
    def category(self):
        """Retorna categoria baseada no MIME type"""
        if self.file_type.startswith('image/'):
            return 'image'
        elif self.file_type.startswith('audio/'):
            return 'audio'
        elif self.file_type.startswith('video/'):
            return 'video'
        else:
            return 'document'
```

#### 1.4 - Migration

```bash
# Criar migração
cd backend
python manage.py makemigrations chat --name add_media_support

# Revisar migração gerada
cat apps/chat/migrations/0003_add_media_support.py

# Aplicar localmente
python manage.py migrate

# Aplicar no Railway (via script ou manual)
```

---

### Fase 2: Utilities S3

```python
# backend/apps/chat/utils/s3.py

"""
Utilities para upload/download do S3/MinIO
"""

import boto3
import hashlib
import logging
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Cliente S3 global (singleton)
_s3_client = None

def get_s3_client():
    """Retorna cliente S3 configurado (singleton)"""
    global _s3_client
    
    if _s3_client is None:
        _s3_client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            ),
            use_ssl=settings.S3_USE_SSL
        )
    
    return _s3_client


def upload_file_to_s3(
    file_data: bytes,
    key: str,
    content_type: str = 'application/octet-stream',
    metadata: Optional[dict] = None,
    acl: str = 'public-read'
) -> str:
    """
    Upload de arquivo para S3.
    
    Args:
        file_data: Dados binários do arquivo
        key: Caminho/chave no S3 (ex: chat/tenant_id/file.jpg)
        content_type: MIME type
        metadata: Metadata adicional (opcional)
        acl: Permissões (default: public-read)
    
    Returns:
        URL pública do arquivo no S3
    
    Raises:
        ClientError: Erro ao fazer upload
    """
    
    s3_client = get_s3_client()
    
    try:
        # Parâmetros do upload
        upload_params = {
            'Bucket': settings.S3_BUCKET,
            'Key': key,
            'Body': file_data,
            'ContentType': content_type,
            'ACL': acl,
        }
        
        # Adicionar metadata se fornecida
        if metadata:
            upload_params['Metadata'] = metadata
        
        # Upload
        s3_client.put_object(**upload_params)
        
        # Gerar URL pública
        url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{key}"
        
        logger.info(f"✅ [S3] Upload completo: {key} ({len(file_data)} bytes)")
        
        return url
    
    except ClientError as e:
        logger.error(f"❌ [S3] Erro no upload: {e}")
        raise


def download_file_from_s3(key: str) -> Tuple[bytes, str]:
    """
    Download de arquivo do S3.
    
    Args:
        key: Caminho/chave no S3
    
    Returns:
        Tupla (file_data, content_type)
    
    Raises:
        ClientError: Erro ao fazer download
    """
    
    s3_client = get_s3_client()
    
    try:
        response = s3_client.get_object(
            Bucket=settings.S3_BUCKET,
            Key=key
        )
        
        file_data = response['Body'].read()
        content_type = response.get('ContentType', 'application/octet-stream')
        
        logger.info(f"✅ [S3] Download completo: {key} ({len(file_data)} bytes)")
        
        return file_data, content_type
    
    except ClientError as e:
        logger.error(f"❌ [S3] Erro no download: {e}")
        raise


def download_from_url(url: str) -> Tuple[bytes, str]:
    """
    Extrai key da URL e faz download do S3.
    
    Args:
        url: URL completa do S3
    
    Returns:
        Tupla (file_data, content_type)
    """
    
    # Extrair key da URL
    # Ex: https://bucket.com/flow-attachments/chat/file.jpg → chat/file.jpg
    parts = url.split(f"{settings.S3_BUCKET}/")
    
    if len(parts) < 2:
        raise ValueError(f"URL inválida: {url}")
    
    key = parts[1]
    
    return download_file_from_s3(key)


def generate_presigned_url(
    key: str,
    expiration: int = 300,
    http_method: str = 'PUT'
) -> str:
    """
    Gera URL pré-assinada para upload direto do frontend.
    
    Args:
        key: Caminho/chave no S3
        expiration: Tempo de expiração em segundos (default: 5 min)
        http_method: Método HTTP (PUT para upload)
    
    Returns:
        URL pré-assinada
    """
    
    s3_client = get_s3_client()
    
    try:
        url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.S3_BUCKET,
                'Key': key,
            },
            ExpiresIn=expiration,
            HttpMethod=http_method
        )
        
        logger.info(f"✅ [S3] Presigned URL gerada: {key} (expira em {expiration}s)")
        
        return url
    
    except ClientError as e:
        logger.error(f"❌ [S3] Erro ao gerar presigned URL: {e}")
        raise


def delete_file_from_s3(key: str) -> bool:
    """
    Deleta arquivo do S3.
    
    Args:
        key: Caminho/chave no S3
    
    Returns:
        True se sucesso, False se erro
    """
    
    s3_client = get_s3_client()
    
    try:
        s3_client.delete_object(
            Bucket=settings.S3_BUCKET,
            Key=key
        )
        
        logger.info(f"🗑️ [S3] Arquivo deletado: {key}")
        
        return True
    
    except ClientError as e:
        logger.error(f"❌ [S3] Erro ao deletar: {e}")
        return False


def generate_s3_key(tenant_id: str, conversation_id: str, filename: str) -> str:
    """
    Gera chave única para S3.
    
    Args:
        tenant_id: UUID do tenant
        conversation_id: UUID da conversa
        filename: Nome original do arquivo
    
    Returns:
        Chave no formato: chat/{tenant_id}/{conversation_id}/{hash}_{filename}
    """
    
    # Hash para evitar colisões
    file_hash = hashlib.md5(f"{filename}{timezone.now().isoformat()}".encode()).hexdigest()[:8]
    
    # Limpar nome do arquivo
    safe_filename = "".join(c for c in filename if c.isalnum() or c in '._-')
    
    # Montar key
    key = f"chat/{tenant_id}/{conversation_id}/{file_hash}_{safe_filename}"
    
    return key
```

---

### Fase 3: Image Processing

```python
# backend/apps/chat/utils/image.py

"""
Utilities para processamento de imagens
"""

import io
import logging
from PIL import Image
from typing import Tuple

logger = logging.getLogger(__name__)


def generate_thumbnail(
    image_data: bytes,
    size: Tuple[int, int] = (200, 200),
    quality: int = 85
) -> bytes:
    """
    Gera thumbnail de uma imagem.
    
    Args:
        image_data: Dados binários da imagem original
        size: Tamanho do thumbnail (largura, altura)
        quality: Qualidade JPEG (0-100)
    
    Returns:
        Dados binários do thumbnail
    """
    
    try:
        # Abrir imagem
        image = Image.open(io.BytesIO(image_data))
        
        # Converter RGBA para RGB (para JPEG)
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Gerar thumbnail (mantém aspect ratio)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Salvar em buffer
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
        buffer.seek(0)
        
        thumbnail_data = buffer.read()
        
        logger.info(f"✅ [IMAGE] Thumbnail gerado: {len(thumbnail_data)} bytes")
        
        return thumbnail_data
    
    except Exception as e:
        logger.error(f"❌ [IMAGE] Erro ao gerar thumbnail: {e}")
        raise


def compress_image(
    image_data: bytes,
    max_size_mb: float = 1.0,
    quality: int = 85
) -> bytes:
    """
    Comprime imagem se necessário.
    
    Args:
        image_data: Dados binários da imagem
        max_size_mb: Tamanho máximo em MB
        quality: Qualidade inicial
    
    Returns:
        Dados binários da imagem comprimida
    """
    
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    
    # Se já está abaixo do limite, retornar original
    if len(image_data) <= max_size_bytes:
        return image_data
    
    try:
        image = Image.open(io.BytesIO(image_data))
        
        # Converter RGBA para RGB
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Tentar comprimir com qualidade decrescente
        for q in range(quality, 20, -10):
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=q, optimize=True)
            
            if buffer.tell() <= max_size_bytes:
                buffer.seek(0)
                compressed_data = buffer.read()
                logger.info(f"✅ [IMAGE] Comprimido: {len(image_data)} → {len(compressed_data)} bytes (quality={q})")
                return compressed_data
        
        # Se não conseguiu comprimir o suficiente, redimensionar
        scale = (max_size_bytes / len(image_data)) ** 0.5
        new_size = (int(image.width * scale), int(image.height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=70, optimize=True)
        buffer.seek(0)
        
        compressed_data = buffer.read()
        logger.info(f"✅ [IMAGE] Redimensionado e comprimido: {len(image_data)} → {len(compressed_data)} bytes")
        
        return compressed_data
    
    except Exception as e:
        logger.error(f"❌ [IMAGE] Erro ao comprimir: {e}")
        # Em caso de erro, retornar original
        return image_data


def get_image_dimensions(image_data: bytes) -> Tuple[int, int]:
    """
    Retorna dimensões da imagem.
    
    Args:
        image_data: Dados binários da imagem
    
    Returns:
        Tupla (largura, altura)
    """
    
    try:
        image = Image.open(io.BytesIO(image_data))
        return image.size
    except Exception as e:
        logger.error(f"❌ [IMAGE] Erro ao ler dimensões: {e}")
        return (0, 0)
```

---

### Fase 4: Celery Tasks

```python
# backend/apps/chat/tasks.py

"""
Tasks assíncronas para processamento de mídia
"""

import httpx
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings

from apps.chat.models import Conversation, MessageAttachment
from apps.chat.utils.s3 import (
    upload_file_to_s3,
    download_from_url,
    generate_s3_key
)
from apps.chat.utils.image import (
    generate_thumbnail,
    compress_image,
    get_image_dimensions
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_profile_pic(self, phone: str, whatsapp_url: str, tenant_id: str):
    """
    Processa foto de perfil:
    1. Download do WhatsApp (URL temporária)
    2. Upload para S3 (permanente)
    3. Gerar thumbnail
    4. Atualizar conversa
    5. Invalidar cache Redis
    
    Args:
        phone: Telefone do contato
        whatsapp_url: URL temporária do WhatsApp
        tenant_id: UUID do tenant
    """
    
    try:
        logger.info(f"🖼️ [PROFILE] Processando foto: {phone}")
        
        # 1. Download do WhatsApp
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(whatsapp_url, follow_redirects=True)
            response.raise_for_status()
            image_data = response.content
        
        logger.info(f"✅ [PROFILE] Download completo: {len(image_data)} bytes")
        
        # 2. Gerar thumbnail
        thumbnail_data = generate_thumbnail(image_data, size=(200, 200))
        
        # 3. Upload para S3
        s3_key = f"profile_pics/{phone}.jpg"
        s3_url = upload_file_to_s3(
            file_data=thumbnail_data,
            key=s3_key,
            content_type='image/jpeg',
            acl='public-read'
        )
        
        # 4. Atualizar conversas
        updated = Conversation.objects.filter(
            tenant_id=tenant_id,
            contact_phone=phone
        ).update(
            profile_pic_url=s3_url,
            profile_pic_updated_at=timezone.now()
        )
        
        logger.info(f"✅ [PROFILE] {updated} conversa(s) atualizada(s) com foto: {phone}")
        
        # 5. Invalidar cache Redis
        from django.core.cache import cache
        import hashlib
        
        old_cache_key = f"profile_pic:{hashlib.md5(whatsapp_url.encode()).hexdigest()}"
        cache.delete(old_cache_key)
        
        # 6. Notificar frontend via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        conversations = Conversation.objects.filter(
            tenant_id=tenant_id,
            contact_phone=phone
        )
        
        for conv in conversations:
            async_to_sync(channel_layer.group_send)(
                f"chat_tenant_{tenant_id}",
                {
                    'type': 'conversation_updated',
                    'conversation': {
                        'id': str(conv.id),
                        'profile_pic_url': s3_url
                    }
                }
            )
        
        logger.info(f"✅ [PROFILE] Processamento completo: {phone}")
        
    except Exception as e:
        logger.error(f"❌ [PROFILE] Erro: {e}", exc_info=True)
        
        # Retry automático (max 3x)
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_incoming_media(
    self,
    message_id: str,
    media_url: str,
    media_type: str,
    tenant_id: str,
    conversation_id: str
):
    """
    Processa mídia recebida via WhatsApp:
    1. Download do WhatsApp
    2. Upload para S3
    3. Gerar thumbnail (se imagem)
    4. Criar MessageAttachment
    5. Notificar frontend
    
    Args:
        message_id: UUID da mensagem
        media_url: URL temporária do WhatsApp
        media_type: MIME type
        tenant_id: UUID do tenant
        conversation_id: UUID da conversa
    """
    
    try:
        logger.info(f"📥 [MEDIA] Processando: {media_type} - {media_url[:50]}...")
        
        # 1. Download do WhatsApp
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(media_url, follow_redirects=True)
            response.raise_for_status()
            file_data = response.content
        
        logger.info(f"✅ [MEDIA] Download completo: {len(file_data)} bytes")
        
        # 2. Gerar nome do arquivo
        file_ext = media_type.split('/')[-1]
        filename = f"media_{message_id}.{file_ext}"
        
        # 3. Upload para S3
        s3_key = generate_s3_key(tenant_id, conversation_id, filename)
        s3_url = upload_file_to_s3(
            file_data=file_data,
            key=s3_key,
            content_type=media_type,
            acl='public-read'
        )
        
        # 4. Gerar thumbnail se for imagem
        thumbnail_url = None
        metadata = {}
        
        if media_type.startswith('image/'):
            try:
                thumbnail_data = generate_thumbnail(file_data)
                thumbnail_key = f"{s3_key}_thumb.jpg"
                thumbnail_url = upload_file_to_s3(
                    file_data=thumbnail_data,
                    key=thumbnail_key,
                    content_type='image/jpeg',
                    acl='public-read'
                )
                
                # Dimensões
                width, height = get_image_dimensions(file_data)
                metadata['width'] = width
                metadata['height'] = height
            except Exception as e:
                logger.warning(f"⚠️ [MEDIA] Erro ao gerar thumbnail: {e}")
        
        # 5. Criar/Atualizar attachment
        attachment, created = MessageAttachment.objects.update_or_create(
            message_id=message_id,
            defaults={
                'tenant_id': tenant_id,
                'conversation_id': conversation_id,
                'file_url': s3_url,
                'file_name': filename,
                'file_type': media_type,
                'size_bytes': len(file_data),
                'thumbnail_url': thumbnail_url or '',
                'storage_type': 's3',
                'storage_key': s3_key,
                'status': 'completed',
                'metadata': metadata
            }
        )
        
        logger.info(f"✅ [MEDIA] Attachment {'criado' if created else 'atualizado'}: {attachment.id}")
        
        # 6. Notificar frontend via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.chat.api.serializers import MessageAttachmentSerializer
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_tenant_{tenant_id}_conversation_{conversation_id}",
            {
                'type': 'attachment_ready',
                'attachment': MessageAttachmentSerializer(attachment).data
            }
        )
        
        logger.info(f"✅ [MEDIA] Processamento completo: {attachment.file_name}")
        
    except Exception as e:
        logger.error(f"❌ [MEDIA] Erro: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_uploaded_file(self, attachment_id: str):
    """
    Processa arquivo enviado pelo usuário:
    1. Download do S3
    2. Gerar thumbnail (se imagem)
    3. Comprimir se necessário
    4. Enviar para WhatsApp
    5. Atualizar status
    6. Notificar frontend
    
    Args:
        attachment_id: UUID do attachment
    """
    
    try:
        attachment = MessageAttachment.objects.get(id=attachment_id)
        
        logger.info(f"📤 [UPLOAD] Processando: {attachment.file_name}")
        
        # 1. Download do S3
        file_data, content_type = download_from_url(attachment.file_url)
        
        # 2. Se for imagem, gerar thumbnail
        if content_type.startswith('image/'):
            try:
                thumbnail_data = generate_thumbnail(file_data)
                thumbnail_key = f"{attachment.storage_key}_thumb.jpg"
                thumbnail_url = upload_file_to_s3(
                    file_data=thumbnail_data,
                    key=thumbnail_key,
                    content_type='image/jpeg'
                )
                attachment.thumbnail_url = thumbnail_url
                
                # Dimensões
                width, height = get_image_dimensions(file_data)
                attachment.metadata['width'] = width
                attachment.metadata['height'] = height
            except Exception as e:
                logger.warning(f"⚠️ [UPLOAD] Erro ao gerar thumbnail: {e}")
        
        # 3. Enviar para WhatsApp via Evolution API
        from apps.chat.services import send_media_to_whatsapp
        
        conversation = attachment.conversation
        
        success, whatsapp_message_id = send_media_to_whatsapp(
            instance_id=conversation.instance_id,  # TODO: adicionar campo
            phone=conversation.contact_phone,
            media_url=attachment.file_url,
            media_type=content_type,
            caption=attachment.metadata.get('caption', '')
        )
        
        if success:
            # 4. Criar mensagem no banco
            from apps.chat.models import Message
            
            message = Message.objects.create(
                conversation=conversation,
                content=attachment.metadata.get('caption') or f'[{attachment.file_name}]',
                direction='outgoing',
                status='sent',
                whatsapp_message_id=whatsapp_message_id
            )
            
            # Associar attachment à mensagem
            attachment.message = message
            attachment.status = 'completed'
            attachment.metadata['whatsapp_message_id'] = whatsapp_message_id
        else:
            attachment.status = 'failed'
            attachment.error_message = 'Falha ao enviar para WhatsApp'
        
        attachment.save()
        
        logger.info(f"✅ [UPLOAD] Processamento completo: {attachment.file_name} (status={attachment.status})")
        
        # 5. Notificar frontend via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.chat.api.serializers import MessageSerializer, MessageAttachmentSerializer
        
        channel_layer = get_channel_layer()
        
        if attachment.message:
            async_to_sync(channel_layer.group_send)(
                f"chat_tenant_{attachment.tenant_id}_conversation_{attachment.conversation_id}",
                {
                    'type': 'message_sent',
                    'message': MessageSerializer(attachment.message).data
                }
            )
        else:
            async_to_sync(channel_layer.group_send)(
                f"chat_tenant_{attachment.tenant_id}_conversation_{attachment.conversation_id}",
                {
                    'type': 'attachment_failed',
                    'attachment': MessageAttachmentSerializer(attachment).data
                }
            )
        
    except MessageAttachment.DoesNotExist:
        logger.error(f"❌ [UPLOAD] Attachment não encontrado: {attachment_id}")
    except Exception as e:
        logger.error(f"❌ [UPLOAD] Erro: {e}", exc_info=True)
        
        # Atualizar status
        try:
            attachment = MessageAttachment.objects.get(id=attachment_id)
            attachment.status = 'failed'
            attachment.error_message = str(e)
            attachment.save()
        except:
            pass
        
        raise self.retry(exc=e, countdown=60)
```

---

## ⏱️ **CRONOGRAMA DE IMPLEMENTAÇÃO**

### Sprint 1 - Semana 1 (30-35h)

**Dia 1-2: Setup e Fotos de Perfil (8-10h)**
- [ ] Adicionar dependências (boto3, Pillow)
- [ ] Configurar settings.py
- [ ] Criar modelos (MessageAttachment)
- [ ] Migration
- [ ] Utils S3 básico
- [ ] Task process_profile_pic
- [ ] Webhook enfileirar
- [ ] Proxy view
- [ ] Frontend atualizar Avatar
- [ ] Testar fotos de perfil

**Dia 3-4: Download de Mídia (10-12h)**
- [ ] Utils S3 completo
- [ ] Utils image processing
- [ ] Task process_incoming_media
- [ ] Webhook detectar mídia
- [ ] Serializers
- [ ] Frontend MessageAttachment component
- [ ] Player de áudio
- [ ] Preview de documento
- [ ] Testar download

**Dia 5-6: Upload de Mídia (12-13h)**
- [ ] Endpoint presigned URL
- [ ] Task process_uploaded_file
- [ ] Service send_media_to_whatsapp
- [ ] Frontend FileUpload component
- [ ] Progress bar
- [ ] Estados de upload
- [ ] Testar upload

### Sprint 2 - Semana 2 (15-20h)

**Dia 1-2: Refinamentos Backend (6-8h)**
- [ ] Compressão de imagens
- [ ] Retry automático
- [ ] Error handling
- [ ] Logs estruturados
- [ ] Metrics

**Dia 3-4: Refinamentos Frontend (6-8h)**
- [ ] Lightbox para imagens
- [ ] Waveform para áudio
- [ ] Preview PDF
- [ ] Loading states
- [ ] Error states
- [ ] Animações

**Dia 5: Testes e Deploy (3-4h)**
- [ ] Testes de integração
- [ ] Deploy Railway
- [ ] Monitoramento
- [ ] Documentação

---

## ✅ **TESTES**

### Checklist de Testes

```markdown
## Fotos de Perfil

- [ ] Webhook recebe foto → Worker processa → S3 upload → DB atualiza
- [ ] Frontend exibe foto (cache hit)
- [ ] Frontend exibe foto (cache miss → S3)
- [ ] Fallback quando foto não existe
- [ ] Atualização de foto (invalidar cache)

## Download de Mídia

- [ ] Receber imagem → Thumbnail → Frontend exibe
- [ ] Receber áudio → Frontend player
- [ ] Receber PDF → Frontend preview
- [ ] Cache Redis funciona (2ª requisição rápida)
- [ ] S3 fallback quando cache expira

## Upload de Mídia

- [ ] Frontend → Presigned URL → Upload direto S3
- [ ] Progress bar atualiza
- [ ] Worker processa → Thumbnail → WhatsApp
- [ ] Status atualiza (pending → processing → sent)
- [ ] Erro de upload (retry button)
- [ ] Arquivo muito grande (validação)

## Performance

- [ ] Cache Redis < 5ms
- [ ] S3 download < 200ms
- [ ] Upload grande (25MB) não trava
- [ ] Múltiplos uploads simultâneos

## Edge Cases

- [ ] WhatsApp offline → Retry funciona
- [ ] S3 offline → Error graceful
- [ ] Redis offline → Fallback S3
- [ ] Arquivo corrompido → Error message
- [ ] Token S3 inválido → Error + alert
```

---

## 🚀 **DEPLOY E MONITORAMENTO**

### Variáveis de Ambiente (Railway)

```env
# S3/MinIO
S3_BUCKET=flow-attachments
S3_ENDPOINT_URL=https://bucket-production-8fb1.up.railway.app
S3_ACCESS_KEY=u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL
S3_SECRET_KEY=zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti
S3_REGION=us-east-1
S3_USE_SSL=True

# Redis (já existe)
REDIS_URL=redis://...

# RabbitMQ (já existe)
RABBITMQ_PRIVATE_URL=amqp://...
```

### Logs e Métricas

```python
# Adicionar ao settings.py

LOGGING = {
    'loggers': {
        'apps.chat.tasks': {
            'level': 'INFO',
            'handlers': ['console'],
        },
        'apps.chat.utils': {
            'level': 'INFO',
            'handlers': ['console'],
        },
    }
}
```

### Celery Workers

```bash
# Railway: Adicionar processo (Procfile)

# worker_media: celery -A alrea_sense worker -Q media_priority,media_download,media_upload -c 4 -l info
```

---

## 🐛 **TROUBLESHOOTING**

### Problema: Foto não aparece

**Sintomas:**
- Avatar mostra fallback (iniciais)
- Console: 404 ou CORS error

**Diagnóstico:**
```python
# 1. Verificar se foto está no S3
from apps.chat.utils.s3 import get_s3_client

s3 = get_s3_client()
response = s3.list_objects_v2(Bucket='flow-attachments', Prefix='profile_pics/')
print(response['Contents'])

# 2. Verificar conversa no banco
from apps.chat.models import Conversation
conv = Conversation.objects.get(contact_phone='+5517999999999')
print(conv.profile_pic_url)

# 3. Testar proxy
# Abrir no navegador: /api/media/proxy/?url=https://...
```

**Soluções:**
- Verificar se worker está rodando
- Verificar logs do Celery
- Verificar credenciais S3

---

### Problema: Upload lento

**Sintomas:**
- Progress bar trava em 50%
- Timeout no frontend

**Diagnóstico:**
```python
# 1. Testar velocidade S3
import time
from apps.chat.utils.s3 import upload_file_to_s3

data = b'x' * (10 * 1024 * 1024)  # 10MB
start = time.time()
upload_file_to_s3(data, key='test.bin', content_type='application/octet-stream')
print(f"Upload: {time.time() - start}s")

# 2. Verificar tamanho do arquivo
# Frontend deve validar ANTES de enviar
```

**Soluções:**
- Aumentar timeout (settings.py)
- Validar tamanho no frontend
- Comprimir antes de enviar

---

### Problema: Cache não funciona

**Sintomas:**
- Todas as requisições vão para S3
- X-Cache sempre MISS

**Diagnóstico:**
```python
# 1. Verificar Redis
from django.core.cache import cache

cache.set('test', 'value', timeout=60)
print(cache.get('test'))  # Deve retornar 'value'

# 2. Verificar chave do cache
import hashlib
url = 'https://...'
cache_key = f"media:{hashlib.md5(url.encode()).hexdigest()}"
print(cache.get(cache_key))
```

**Soluções:**
- Verificar se Redis está rodando
- Verificar settings CACHES
- Verificar se chave está correta

---

## 📊 **MÉTRICAS E KPIs**

### Métricas Técnicas

```python
# Dashboard de métricas

MEDIA_METRICS = {
    'uploads_total': 'Total de uploads',
    'uploads_success': 'Uploads com sucesso',
    'uploads_failed': 'Uploads falhados',
    'downloads_total': 'Total de downloads',
    'cache_hit_rate': 'Taxa de cache hit (%)',
    'avg_upload_time': 'Tempo médio de upload (s)',
    'avg_download_time': 'Tempo médio de download (s)',
    's3_storage_used': 'Storage usado no S3 (GB)',
    'redis_cache_size': 'Tamanho do cache Redis (MB)',
}
```

### Alertas

```python
# Configurar alertas (Sentry, DataDog, etc)

ALERTS = [
    {
        'name': 'Upload falhou > 10%',
        'condition': 'uploads_failed / uploads_total > 0.1',
        'action': 'Enviar email para dev team'
    },
    {
        'name': 'S3 storage > 80%',
        'condition': 's3_storage_used > 80GB',
        'action': 'Aumentar storage ou limpar arquivos antigos'
    },
    {
        'name': 'Redis cache > 90%',
        'condition': 'redis_cache_size > 9GB',
        'action': 'Aumentar Redis ou reduzir TTL'
    }
]
```

---

## 🎓 **BOAS PRÁTICAS**

### 1. Segurança

```python
# ✅ BOM: Validar tipo e tamanho
def validate_file(file):
    if file.size > settings.MEDIA_MAX_SIZE.get(category, 10_000_000):
        raise ValidationError('Arquivo muito grande')
    
    if file.content_type not in settings.MEDIA_ALLOWED_TYPES.get(category, []):
        raise ValidationError('Tipo de arquivo não permitido')

# ❌ RUIM: Aceitar qualquer arquivo
```

### 2. Performance

```python
# ✅ BOM: Upload direto para S3 (presigned URL)
url = generate_presigned_url(key)
frontend_upload_direct(url)

# ❌ RUIM: Upload via backend
backend_receive_file()  # 25MB passando pelo backend!
```

### 3. UX

```typescript
// ✅ BOM: Mostrar estados
{status === 'uploading' && <ProgressBar value={progress} />}
{status === 'processing' && <Spinner text="Processando..." />}
{status === 'sent' && <CheckCircle />}

// ❌ RUIM: Sem feedback
await upload(file)  // Usuário não sabe o que está acontecendo
```

### 4. Logs

```python
# ✅ BOM: Logs estruturados
logger.info(f"✅ [UPLOAD] Completo: {filename}", extra={
    'attachment_id': str(attachment.id),
    'file_size': attachment.size_bytes,
    'duration_ms': duration
})

# ❌ RUIM: Logs genéricos
logger.info('Upload ok')
```

---

## 📚 **REFERÊNCIAS**

- [Django Channels Docs](https://channels.readthedocs.io/)
- [Boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [Pillow (PIL) Docs](https://pillow.readthedocs.io/)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices)
- [MinIO Python Client](https://min.io/docs/minio/linux/developers/python/API.html)

---

## ✅ **CONCLUSÃO**

Este documento fornece um guia completo para implementação do sistema de mídia.

**Próximos passos:**
1. ✅ Revisar e aprovar arquitetura
2. 📅 Alocar sprint (3-4 semanas)
3. 🔧 Implementar fase por fase
4. ✅ Testar cada componente
5. 🚀 Deploy em produção

**Resultado esperado:**
- Sistema robusto e escalável
- UX excelente
- Performance otimizada
- Custos controlados

---

**Documento criado:** 20 de Outubro de 2025  
**Versão:** 1.0  
**Autor:** Arquitetura ALREA Sense  
**Status:** ✅ Aprovado para implementação

