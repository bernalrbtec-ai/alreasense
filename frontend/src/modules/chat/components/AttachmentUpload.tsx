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

