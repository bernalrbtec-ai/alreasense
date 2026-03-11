/**
 * FileUploader - Componente para enviar anexos (tipos WhatsApp + XML, JSON, ZIP, RAR, 7z)
 *
 * Suporta seleção de um ou vários arquivos (máx. ATTACHMENTS_MAX_FILES).
 */
import React, { useRef, useCallback } from 'react';
import { Paperclip } from 'lucide-react';
import { toast } from 'sonner';

const ATTACHMENTS_MAX_FILES = 10;

interface FileUploaderProps {
  conversationId: string;
  selectedFiles: File[];
  onFileSelect: (files: File[]) => void;
  onUpload: (file: File) => Promise<void>;
  onUploadComplete?: () => void;
  onUploadError?: (error: string) => void;
  disabled?: boolean;
  isUploading?: boolean;
}

export function FileUploader({
  conversationId,
  selectedFiles,
  onFileSelect,
  onUpload,
  onUploadComplete,
  onUploadError,
  disabled = false,
  isUploading: externalIsUploading = false,
}: FileUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  // WhatsApp (documentos, imagens, áudio, vídeo) + extras: XML, JSON, ZIP, RAR, 7z
  const allowedTypes = [
    'text/plain',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg',
    'image/png',
    'audio/aac',
    'audio/amr',
    'audio/mpeg',
    'audio/mp4',
    'audio/ogg',
    'video/3gpp',
    'video/mp4',
    'application/xml',
    'text/xml',
    'application/json',
    'application/zip',
    'application/vnd.rar',
    'application/x-rar-compressed',
    'application/x-7z-compressed',
  ];
  const acceptAttr = [
    '.txt',
    '.pdf',
    '.doc',
    '.docx',
    '.xls',
    '.xlsx',
    '.ppt',
    '.pptx',
    '.jpg',
    '.jpeg',
    '.png',
    '.aac',
    '.amr',
    '.mp3',
    '.m4a',
    '.ogg',
    '.3gp',
    '.mp4',
    '.xml',
    '.json',
    '.zip',
    '.rar',
    '.7z',
  ].join(',');

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const fileList = e.target.files;
      if (!fileList?.length) return;

      import('../utils/messageUtils').then(({ validateFileSize, validateFileType }) => {
        const files = Array.from(fileList);
        const valid: File[] = [];
        for (const file of files) {
          const sizeValidation = validateFileSize(file, 50);
          if (!sizeValidation.valid) {
            toast.error(sizeValidation.error ?? 'Arquivo muito grande. Máximo: 50MB');
            e.target.value = '';
            return;
          }
          const typeValidation = validateFileType(file, allowedTypes);
          if (!typeValidation.valid) {
            toast.error(typeValidation.error ?? 'Tipo de arquivo não permitido');
            e.target.value = '';
            return;
          }
          valid.push(file);
        }
        const toAdd = valid.slice(0, ATTACHMENTS_MAX_FILES);
        if (valid.length > ATTACHMENTS_MAX_FILES) {
          toast.info(`Máximo ${ATTACHMENTS_MAX_FILES} arquivos. Foram adicionados os primeiros ${ATTACHMENTS_MAX_FILES}.`);
        }
        onFileSelect(toAdd);
        e.target.value = '';
      });
    },
    [onFileSelect, allowedTypes]
  );

  const handleButtonClick = () => {
    if (disabled || externalIsUploading) return;
    fileInputRef.current?.click();
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept={acceptAttr}
        multiple
        onChange={handleFileSelect}
        className="hidden"
        disabled={disabled || externalIsUploading}
      />

      <button
        onClick={handleButtonClick}
        disabled={disabled || externalIsUploading}
        className="p-2 hover:bg-gray-200 dark:hover:bg-gray-600 active:scale-95 rounded-full transition-all duration-150 flex-shrink-0 shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
        title="Anexar arquivo"
      >
        <Paperclip className="w-6 h-6 text-gray-600 dark:text-gray-400" />
      </button>
    </>
  );
}

