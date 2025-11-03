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

interface FileUploaderProps {
  conversationId: string;
  selectedFile: File | null;
  onFileSelect: (file: File | null) => void;
  onUpload: (file: File) => Promise<void>;
  onUploadComplete?: () => void;
  onUploadError?: (error: string) => void;
  disabled?: boolean;
  isUploading?: boolean;
}

export function FileUploader({ 
  conversationId,
  selectedFile,
  onFileSelect,
  onUpload,
  onUploadComplete,
  onUploadError,
  disabled = false,
  isUploading: externalIsUploading = false
}: FileUploaderProps) {
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

    onFileSelect(file);
  }, [onFileSelect]);

  const handleButtonClick = () => {
    if (disabled || externalIsUploading) return;
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
        disabled={disabled || externalIsUploading}
      />

      <button
        onClick={handleButtonClick}
        disabled={disabled || externalIsUploading}
        className="p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 flex-shrink-0 shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
        title="Anexar arquivo"
      >
        <Paperclip className="w-6 h-6 text-gray-600" />
      </button>
    </>
  );
}

