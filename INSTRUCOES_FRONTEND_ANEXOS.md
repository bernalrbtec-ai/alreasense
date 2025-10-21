# 📎 INSTRUÇÕES FRONTEND - Sistema de Anexos Flow Chat

**PARA O PRÓXIMO AGENTE:** Siga estas instruções **EXATAMENTE** como estão escritas.

**CONTEXTO:** Backend 100% pronto e deployado. Migration aplicada. Endpoints funcionando. Falta APENAS o frontend.

---

## 🎯 OBJETIVO

Implementar 2 componentes React + integrações:
1. ✅ `AttachmentPreview` - Visualizar anexos (imagens, áudio, vídeo, docs)
2. ✅ `AttachmentUpload` - Upload de arquivos com progress bar
3. ✅ Integrar em `MessageList` e `MessageInput`

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

Siga esta ordem EXATAMENTE:

- [ ] 1. Instalar dependência `wavesurfer.js` (npm)
- [ ] 2. Criar `AttachmentPreview.tsx` (200 linhas)
- [ ] 3. Criar `AttachmentUpload.tsx` (300 linhas)
- [ ] 4. Atualizar `MessageList.tsx` (adicionar preview)
- [ ] 5. Atualizar `MessageInput.tsx` (adicionar botão upload)
- [ ] 6. Atualizar `types.ts` (tipo MessageAttachment)
- [ ] 7. Testar localmente
- [ ] 8. Commit + Push

---

## 📦 PASSO 1: INSTALAR DEPENDÊNCIA

```bash
cd frontend
npm install wavesurfer.js
```

**POR QUÊ:** Player de áudio com waveform visual (para transcrições futuras).

---

## 📄 PASSO 2: CRIAR `AttachmentPreview.tsx`

**Arquivo:** `frontend/src/modules/chat/components/AttachmentPreview.tsx`

**CÓDIGO COMPLETO:**

```typescript
/**
 * AttachmentPreview - Visualiza diferentes tipos de anexos
 * 
 * Suporta:
 * - Imagens: Preview inline + lightbox
 * - Vídeos: Player HTML5
 * - Áudios: Player wavesurfer.js
 * - Documentos: Ícone + download
 * - IA: Transcrição + Resumo (se addon ativo)
 */
import React, { useState, useEffect, useRef } from 'react';
import { Download, FileText, Image, Video, Music, X } from 'lucide-react';
import WaveSurfer from 'wavesurfer.js';

interface Attachment {
  id: string;
  original_filename: string;
  mime_type: string;
  file_url: string;
  size_bytes: number;
  is_image: boolean;
  is_video: boolean;
  is_audio: boolean;
  is_document: boolean;
  // ✨ Campos IA (podem ser null)
  transcription?: string | null;
  ai_summary?: string | null;
  ai_tags?: string[] | null;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
}

interface AttachmentPreviewProps {
  attachment: Attachment;
  showAI?: boolean;  // Se tenant tem addon Flow AI
}

export function AttachmentPreview({ attachment, showAI = false }: AttachmentPreviewProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);

  // 🎵 Inicializar WaveSurfer para áudios
  useEffect(() => {
    if (attachment.is_audio && waveformRef.current && !wavesurferRef.current) {
      wavesurferRef.current = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#4F46E5',
        progressColor: '#818CF8',
        cursorColor: '#312E81',
        barWidth: 2,
        barRadius: 3,
        cursorWidth: 1,
        height: 60,
        barGap: 2,
      });

      wavesurferRef.current.load(attachment.file_url);

      wavesurferRef.current.on('play', () => setAudioPlaying(true));
      wavesurferRef.current.on('pause', () => setAudioPlaying(false));
      wavesurferRef.current.on('finish', () => setAudioPlaying(false));
    }

    return () => {
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  }, [attachment.is_audio, attachment.file_url]);

  // 🖼️ IMAGEM
  if (attachment.is_image) {
    return (
      <div className="attachment-preview image">
        <img
          src={attachment.file_url}
          alt={attachment.original_filename}
          className="max-w-xs rounded-lg cursor-pointer hover:opacity-90 transition"
          onClick={() => setLightboxOpen(true)}
        />
        
        {/* Lightbox */}
        {lightboxOpen && (
          <div 
            className="fixed inset-0 bg-black bg-opacity-90 z-50 flex items-center justify-center p-4"
            onClick={() => setLightboxOpen(false)}
          >
            <button
              className="absolute top-4 right-4 text-white hover:text-gray-300"
              onClick={() => setLightboxOpen(false)}
            >
              <X size={32} />
            </button>
            <img
              src={attachment.file_url}
              alt={attachment.original_filename}
              className="max-w-full max-h-full object-contain"
            />
          </div>
        )}
      </div>
    );
  }

  // 🎥 VÍDEO
  if (attachment.is_video) {
    return (
      <div className="attachment-preview video max-w-md">
        <video
          controls
          className="w-full rounded-lg"
          preload="metadata"
        >
          <source src={attachment.file_url} type={attachment.mime_type} />
          Seu navegador não suporta vídeo.
        </video>
        <p className="text-xs text-gray-500 mt-1">{attachment.original_filename}</p>
      </div>
    );
  }

  // 🎵 ÁUDIO
  if (attachment.is_audio) {
    return (
      <div className="attachment-preview audio max-w-md bg-gray-50 p-4 rounded-lg">
        <div className="flex items-center gap-3 mb-2">
          <Music className="text-indigo-600" size={20} />
          <div className="flex-1">
            <p className="text-sm font-medium">{attachment.original_filename}</p>
            <p className="text-xs text-gray-500">
              {(attachment.size_bytes / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        </div>

        {/* Waveform */}
        <div ref={waveformRef} className="mb-2"></div>

        {/* Controles */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (wavesurferRef.current) {
                wavesurferRef.current.playPause();
              }
            }}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm"
          >
            {audioPlaying ? 'Pausar' : 'Reproduzir'}
          </button>
          <a
            href={attachment.file_url}
            download={attachment.original_filename}
            className="p-2 text-gray-600 hover:text-gray-900"
          >
            <Download size={18} />
          </a>
        </div>

        {/* ✨ TRANSCRIÇÃO IA (se disponível e addon ativo) */}
        {showAI && attachment.transcription && (
          <div className="mt-3 p-3 bg-white rounded border border-gray-200">
            <p className="text-xs font-semibold text-gray-700 mb-1">📝 Transcrição:</p>
            <p className="text-sm text-gray-600">{attachment.transcription}</p>
          </div>
        )}

        {/* ✨ RESUMO IA */}
        {showAI && attachment.ai_summary && (
          <div className="mt-2 p-3 bg-indigo-50 rounded border border-indigo-200">
            <p className="text-xs font-semibold text-indigo-700 mb-1">🧠 Resumo IA:</p>
            <p className="text-sm text-indigo-900">{attachment.ai_summary}</p>
          </div>
        )}

        {/* ✨ TAGS IA */}
        {showAI && attachment.ai_tags && attachment.ai_tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {attachment.ai_tags.map((tag, i) => (
              <span
                key={i}
                className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 📄 DOCUMENTO
  return (
    <div className="attachment-preview document flex items-center gap-3 p-3 bg-gray-50 rounded-lg max-w-md">
      <FileText className="text-gray-600" size={24} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{attachment.original_filename}</p>
        <p className="text-xs text-gray-500">
          {(attachment.size_bytes / 1024).toFixed(0)} KB
        </p>
      </div>
      <a
        href={attachment.file_url}
        download={attachment.original_filename}
        className="p-2 bg-white border border-gray-300 rounded hover:bg-gray-100"
      >
        <Download size={18} />
      </a>
    </div>
  );
}
```

**IMPORTANTE:**
- ✅ Suporta todos os tipos (imagem, vídeo, áudio, doc)
- ✅ Lightbox para imagens (clique para ampliar)
- ✅ Player wavesurfer.js para áudio
- ✅ Campos IA condicionais (só mostra se `showAI=true`)
- ✅ Download para docs e áudios

---

## 📤 PASSO 3: CRIAR `AttachmentUpload.tsx`

**Arquivo:** `frontend/src/modules/chat/components/AttachmentUpload.tsx`

**CÓDIGO COMPLETO:**

```typescript
/**
 * AttachmentUpload - Upload de arquivos com progress
 * 
 * Fluxo:
 * 1. Usuário seleciona arquivo
 * 2. Preview + validação
 * 3. Obter presigned URL do backend
 * 4. Upload direto para S3 (PUT)
 * 5. Confirmar upload no backend
 * 6. WebSocket broadcast → UI atualiza
 */
import React, { useState, useRef } from 'react';
import { Paperclip, X, Upload, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface AttachmentUploadProps {
  conversationId: string;
  onUploadStart?: () => void;
  onUploadComplete?: (attachment: any) => void;
  onUploadError?: (error: string) => void;
}

export function AttachmentUpload({
  conversationId,
  onUploadStart,
  onUploadComplete,
  onUploadError,
}: AttachmentUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [preview, setPreview] = useState<{
    file: File;
    previewUrl?: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Validações
  const MAX_SIZE = 50 * 1024 * 1024; // 50MB
  const ALLOWED_TYPES = [
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'video/mp4', 'video/webm',
    'audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/mp3',
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ];

  // Selecionar arquivo
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validar tipo
    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error('Tipo de arquivo não suportado');
      return;
    }

    // Validar tamanho
    if (file.size > MAX_SIZE) {
      toast.error(`Arquivo muito grande. Máximo: ${MAX_SIZE / 1024 / 1024}MB`);
      return;
    }

    // Criar preview para imagens
    let previewUrl: string | undefined;
    if (file.type.startsWith('image/')) {
      previewUrl = URL.createObjectURL(file);
    }

    setPreview({ file, previewUrl });
  };

  // Cancelar
  const handleCancel = () => {
    if (preview?.previewUrl) {
      URL.revokeObjectURL(preview.previewUrl);
    }
    setPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Upload
  const handleUpload = async () => {
    if (!preview) return;

    setUploading(true);
    setProgress(0);
    onUploadStart?.();

    try {
      const { file } = preview;

      // 1️⃣ Obter presigned URL
      console.log('📤 [UPLOAD] Solicitando presigned URL...');
      const { data: presignedData } = await api.post('/chat/messages/upload-presigned-url/', {
        conversation_id: conversationId,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [UPLOAD] Presigned URL obtida:', presignedData.attachment_id);

      // 2️⃣ Upload direto para S3
      console.log('📤 [UPLOAD] Enviando para S3...');
      const xhr = new XMLHttpRequest();

      // Progress
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percent = (e.loaded / e.total) * 100;
          setProgress(Math.round(percent));
          console.log(`📊 [UPLOAD] Progresso: ${Math.round(percent)}%`);
        }
      });

      // Promise wrapper para XMLHttpRequest
      await new Promise<void>((resolve, reject) => {
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload falhou: ${xhr.status}`));
          }
        });

        xhr.addEventListener('error', () => {
          reject(new Error('Erro de rede ao fazer upload'));
        });

        xhr.open('PUT', presignedData.upload_url);
        xhr.setRequestHeader('Content-Type', file.type);
        xhr.send(file);
      });

      console.log('✅ [UPLOAD] Arquivo enviado para S3');

      // 3️⃣ Confirmar no backend
      console.log('📤 [UPLOAD] Confirmando upload...');
      const { data: confirmData } = await api.post('/chat/messages/confirm-upload/', {
        conversation_id: conversationId,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [UPLOAD] Upload confirmado:', confirmData);

      // Sucesso!
      toast.success('Arquivo enviado com sucesso!');
      onUploadComplete?.(confirmData.attachment);

      // Limpar
      handleCancel();
    } catch (error: any) {
      console.error('❌ [UPLOAD] Erro:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao enviar arquivo';
      toast.error(errorMsg);
      onUploadError?.(errorMsg);
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <div className="attachment-upload">
      {/* Botão Anexar */}
      {!preview && (
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
          title="Anexar arquivo"
          disabled={uploading}
        >
          <Paperclip size={20} />
        </button>
      )}

      {/* Input escondido */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,video/*,audio/*,application/pdf,.doc,.docx,.xls,.xlsx"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Preview + Confirmação */}
      {preview && !uploading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Enviar Arquivo</h3>
              <button
                onClick={handleCancel}
                className="text-gray-400 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>

            {/* Preview */}
            {preview.previewUrl ? (
              <img
                src={preview.previewUrl}
                alt="Preview"
                className="w-full h-48 object-contain bg-gray-100 rounded mb-4"
              />
            ) : (
              <div className="w-full h-48 bg-gray-100 rounded mb-4 flex items-center justify-center">
                <Upload className="text-gray-400" size={48} />
              </div>
            )}

            {/* Info */}
            <p className="text-sm font-medium mb-1">{preview.file.name}</p>
            <p className="text-xs text-gray-500 mb-4">
              {(preview.file.size / 1024 / 1024).toFixed(2)} MB
            </p>

            {/* Ações */}
            <div className="flex gap-2">
              <button
                onClick={handleCancel}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleUpload}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Enviar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress */}
      {uploading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <div className="text-center mb-4">
              <Loader2 className="animate-spin mx-auto mb-2 text-indigo-600" size={32} />
              <p className="text-lg font-semibold">Enviando arquivo...</p>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-center text-gray-600">{progress}%</p>
          </div>
        </div>
      )}
    </div>
  );
}
```

**IMPORTANTE:**
- ✅ Validação de tipo e tamanho (50MB max)
- ✅ Preview de imagem antes de enviar
- ✅ Progress bar com XMLHttpRequest
- ✅ Upload direto S3 (PUT com presigned URL)
- ✅ Confirmação backend após upload
- ✅ Toasts de sucesso/erro

---

## 🔗 PASSO 4: ATUALIZAR `MessageList.tsx`

**Arquivo:** `frontend/src/modules/chat/components/MessageList.tsx`

**ADICIONAR no render de cada mensagem:**

```typescript
import { AttachmentPreview } from './AttachmentPreview';
import { useUserAccess } from '@/hooks/useUserAccess';

// ... dentro do componente
const { canAccess: hasFlowAI } = useUserAccess('flow-ai');

// ... no render de mensagem
{msg.attachments && msg.attachments.length > 0 && (
  <div className="message-attachments mt-2 space-y-2">
    {msg.attachments.map((attachment) => (
      <AttachmentPreview
        key={attachment.id}
        attachment={attachment}
        showAI={hasFlowAI}
      />
    ))}
  </div>
)}
```

**LOCALIZAÇÃO EXATA:**
Procure por `<div className="message-content">` e adicione DEPOIS do conteúdo da mensagem.

---

## 🔗 PASSO 5: ATUALIZAR `MessageInput.tsx`

**Arquivo:** `frontend/src/modules/chat/components/MessageInput.tsx`

**ADICIONAR botão de anexar:**

```typescript
import { AttachmentUpload } from './AttachmentUpload';

// ... dentro do componente, antes do textarea
<div className="message-input flex items-center gap-2 p-4 border-t">
  {/* Botão Anexar */}
  <AttachmentUpload
    conversationId={activeConversation.id}
    onUploadComplete={() => {
      console.log('✅ Upload completo! WebSocket vai atualizar UI');
    }}
  />
  
  {/* Textarea existente */}
  <textarea ... />
  
  {/* Botão Enviar existente */}
  <button ... />
</div>
```

**LOCALIZAÇÃO EXATA:**
Adicione o `<AttachmentUpload />` como **primeiro elemento** dentro do container do input.

---

## 📝 PASSO 6: ATUALIZAR `types.ts`

**Arquivo:** `frontend/src/modules/chat/types.ts`

**ADICIONAR tipo:**

```typescript
export interface MessageAttachment {
  id: string;
  message: string;
  tenant: string;
  original_filename: string;
  mime_type: string;
  file_path: string;
  file_url: string;
  thumbnail_path?: string;
  storage_type: 'local' | 's3';
  size_bytes: number;
  expires_at: string;
  created_at: string;
  is_expired: boolean;
  is_image: boolean;
  is_video: boolean;
  is_audio: boolean;
  is_document: boolean;
  // ✨ Campos IA
  transcription?: string | null;
  transcription_language?: string | null;
  ai_summary?: string | null;
  ai_tags?: string[] | null;
  ai_sentiment?: 'positive' | 'neutral' | 'negative' | null;
  ai_metadata?: any | null;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  processed_at?: string | null;
}

// Adicionar ao tipo Message existente:
export interface Message {
  // ... campos existentes
  attachments?: MessageAttachment[];
}
```

---

## 🧪 PASSO 7: TESTAR

### **Checklist de Testes:**

1. **Upload de Imagem:**
   - [ ] Selecionar imagem → Preview aparece
   - [ ] Confirmar → Progress bar funciona
   - [ ] Upload completo → Imagem aparece na mensagem
   - [ ] Clicar imagem → Lightbox abre

2. **Upload de Áudio:**
   - [ ] Selecionar MP3 → Preview confirma
   - [ ] Upload completo → Waveform aparece
   - [ ] Clicar play → Áudio toca

3. **Upload de Documento:**
   - [ ] Selecionar PDF → Preview confirma
   - [ ] Upload completo → Ícone + download aparecem
   - [ ] Clicar download → Arquivo baixa

4. **Validações:**
   - [ ] Arquivo > 50MB → Erro
   - [ ] Tipo não suportado → Erro
   - [ ] Cancelar upload → Preview fecha

5. **WebSocket:**
   - [ ] Upload em uma aba → Outra aba recebe via WebSocket

---

## 📦 PASSO 8: COMMIT + PUSH

```bash
git add frontend/src/modules/chat/components/AttachmentPreview.tsx
git add frontend/src/modules/chat/components/AttachmentUpload.tsx
git add frontend/src/modules/chat/components/MessageList.tsx
git add frontend/src/modules/chat/components/MessageInput.tsx
git add frontend/src/modules/chat/types.ts
git add frontend/package.json
git add frontend/package-lock.json

git commit -m "feat(attachments): implementar frontend completo de anexos

COMPONENTES:
- AttachmentPreview: visualizacao de imagens/audio/video/docs
- AttachmentUpload: upload direto S3 com progress bar

FEATURES:
- Lightbox para imagens
- Player wavesurfer.js para audio
- Download para docs
- Validacao tipo/tamanho (50MB max)
- Progress bar em tempo real
- Preview antes de enviar
- Campos IA condicionais (transcricao/resumo)

INTEGRACAO:
- MessageList exibe anexos com AttachmentPreview
- MessageInput tem botao anexar com AttachmentUpload
- Types atualizados com MessageAttachment completo

TESTADO:
- Upload imagem/audio/doc funcionando
- Progress bar OK
- WebSocket broadcast OK
- Validacoes OK"

git push origin main
```

---

## ⚠️ TROUBLESHOOTING

### **Erro: `wavesurfer is not defined`**
**Solução:** Importar corretamente:
```typescript
import WaveSurfer from 'wavesurfer.js';
```

### **Erro: `api.post is not a function`**
**Solução:** Verificar import:
```typescript
import { api } from '@/lib/api';
```

### **Erro: S3 PUT retorna 403**
**Solução:** Verificar:
1. Presigned URL está correto
2. Content-Type no header está correto
3. URL não expirou (5min)

### **Anexo não aparece na UI**
**Solução:**
1. Verificar WebSocket conectado
2. Verificar `msg.attachments` no `MessageList`
3. Verificar console do navegador para erros

---

## 📚 REFERÊNCIAS RÁPIDAS

### **Endpoints Backend:**
- `POST /api/chat/messages/upload-presigned-url/`
- `POST /api/chat/messages/confirm-upload/`

### **Estrutura S3:**
- Key: `chat/{tenant_id}/attachments/{uuid}.{ext}`
- Bucket: MinIO em Railway
- TTL presigned: 5min
- Expires attachment: 365 dias

### **Tipos MIME Suportados:**
- Imagens: `image/jpeg`, `image/png`, `image/gif`, `image/webp`
- Vídeos: `video/mp4`, `video/webm`
- Áudios: `audio/mpeg`, `audio/ogg`, `audio/wav`
- Docs: `application/pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`

---

## ✅ CHECKLIST FINAL

Antes de considerar completo:

- [ ] `npm install wavesurfer.js` executado
- [ ] 2 componentes criados (`AttachmentPreview` + `AttachmentUpload`)
- [ ] 3 arquivos atualizados (`MessageList`, `MessageInput`, `types.ts`)
- [ ] Testado upload de imagem (lightbox funciona)
- [ ] Testado upload de áudio (player funciona)
- [ ] Testado upload de documento (download funciona)
- [ ] Validações funcionando (tamanho/tipo)
- [ ] Progress bar aparece durante upload
- [ ] WebSocket atualiza UI automaticamente
- [ ] Commit + Push realizado
- [ ] Deploy Railway concluído

---

**🚀 BOA SORTE! SIGA AS INSTRUÇÕES EXATAMENTE COMO ESCRITAS!**

**❓ SE TIVER DÚVIDAS:**
1. Leia `IMPLEMENTACAO_ANEXOS_FLOW_CHAT.md` (documentação técnica backend)
2. Verifique console do navegador para erros
3. Verifique logs Railway para erros backend
4. Teste endpoints backend com Postman primeiro

