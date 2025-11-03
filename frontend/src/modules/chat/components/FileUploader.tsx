/**
 * FileUploader - Componente para enviar anexos (imagem, PDF, DOC, Excel)
 * 
 * Funcionalidades:
 * - Seleciona arquivo via input
 * - Mostra thumbnail responsivo antes de enviar
 * - Faz upload via presigned URL (S3)
 * - Confirma upload no backend
 * - Integrado com MessageInput
 */
import React, { useState, useRef, useCallback } from 'react';
import { Paperclip } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { AttachmentThumbnail } from './AttachmentThumbnail';

interface FileUploaderProps {
  conversationId: string;
  onUploadComplete?: () => void;
  onUploadError?: (error: string) => void;
  disabled?: boolean;
}

export function FileUploader({ 
  conversationId, 
  onUploadComplete,
  onUploadError,
  disabled = false 
}: FileUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Tipos de arquivo permitidos
  const allowedTypes = [
    'image/*',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // DOCX
    'application/msword', // DOC
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // XLSX
    'application/vnd.ms-excel', // XLS
  ];

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validar tamanho (50MB)
    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
      toast.error('Arquivo muito grande. Máximo: 50MB');
      return;
    }

    // Validar tipo
    const isAllowed = allowedTypes.some(type => {
      if (type.endsWith('/*')) {
        const baseType = type.slice(0, -2);
        return file.type.startsWith(baseType);
      }
      return file.type === type;
    });

    if (!isAllowed) {
      toast.error('Tipo de arquivo não permitido');
      return;
    }

    setSelectedFile(file);
  }, []);

  const handleRemove = useCallback(() => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    if (!file || !conversationId || isUploading) return;

    setIsUploading(true);

    try {
      console.log('📤 [FILE] Iniciando upload...', file.name, file.size, 'bytes');

      // 1️⃣ Obter presigned URL
      const { data: presignedData } = await api.post('/chat/messages/upload-presigned-url/', {
        conversation_id: conversationId,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [FILE] Presigned URL obtida');

      // 2️⃣ Upload S3
      const xhr = new XMLHttpRequest();
      
      await new Promise<void>((resolve, reject) => {
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload falhou: ${xhr.status}`));
          }
        });

        xhr.addEventListener('error', () => {
          reject(new Error('Erro de rede'));
        });

        xhr.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            console.log(`📤 [FILE] Upload progress: ${percent.toFixed(1)}%`);
          }
        });

        xhr.open('PUT', presignedData.upload_url);
        xhr.setRequestHeader('Content-Type', file.type);
        xhr.send(file);
      });

      console.log('✅ [FILE] Upload S3 completo');

      // 3️⃣ Confirmar backend
      const { data: confirmData } = await api.post('/chat/messages/confirm-upload/', {
        conversation_id: conversationId,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [FILE] Arquivo enviado com sucesso!');
      
      // Limpar estado
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      toast.success('Arquivo enviado!', {
        duration: 2000,
        position: 'bottom-right'
      });

      onUploadComplete?.();
    } catch (error: any) {
      console.error('❌ [FILE] Erro ao enviar arquivo:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao enviar arquivo';
      toast.error(errorMsg);
      onUploadError?.(errorMsg);
    } finally {
      setIsUploading(false);
    }
  }, [conversationId, isUploading, onUploadComplete, onUploadError]);

  const handleButtonClick = () => {
    if (disabled || isUploading) return;
    fileInputRef.current?.click();
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept={allowedTypes.join(',')}
        onChange={handleFileSelect}
        className="hidden"
        disabled={disabled || isUploading}
      />

      <button
        onClick={handleButtonClick}
        disabled={disabled || isUploading}
        className="p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 flex-shrink-0 shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
        title="Anexar arquivo"
      >
        <Paperclip className="w-6 h-6 text-gray-600" />
      </button>

      {/* Thumbnail preview */}
      {selectedFile && (
        <div className="absolute bottom-full left-4 mb-2 z-10">
          <AttachmentThumbnail
            file={selectedFile}
            onRemove={handleRemove}
            onUpload={handleUpload}
            isUploading={isUploading}
          />
        </div>
      )}
    </>
  );
}

