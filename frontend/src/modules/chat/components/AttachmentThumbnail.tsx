/**
 * AttachmentThumbnail - Thumbnail responsivo de anexos antes de enviar
 * 
 * Suporta:
 * - Imagens: Thumbnail gerado no frontend (canvas)
 * - PDF: Ícone ou primeira página (se possível)
 * - DOC/DOCX: Logo do Word
 * - XLS/XLSX: Logo do Excel
 * 
 * Responsivo: ajusta tamanho ao viewport (mobile, tablet, desktop)
 */
import React, { useState, useEffect } from 'react';
import { X, FileText, File, FileSpreadsheet } from 'lucide-react';

interface AttachmentThumbnailProps {
  file: File;
  onRemove: () => void;
  onUpload: (file: File) => Promise<void>;
  isUploading?: boolean;
}

export function AttachmentThumbnail({ 
  file, 
  onRemove, 
  onUpload,
  isUploading = false 
}: AttachmentThumbnailProps) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mimeType = file.type;
  const isImage = mimeType.startsWith('image/');
  const isPDF = mimeType === 'application/pdf';
  const isWord = mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
                 mimeType === 'application/msword';
  const isExcel = mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                 mimeType === 'application/vnd.ms-excel';

  // Gerar thumbnail para imagens
  useEffect(() => {
    if (isImage) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new window.Image();
        img.onload = () => {
          // Criar canvas para thumbnail responsivo
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            setError('Não foi possível criar thumbnail');
            return;
          }

          // Calcular dimensões responsivas
          // Mobile: max 200px, Tablet: max 300px, Desktop: max 400px
          const maxWidth = window.innerWidth < 640 ? 200 : window.innerWidth < 1024 ? 300 : 400;
          const maxHeight = maxWidth;

          let { width, height } = img;
          
          // Manter aspect ratio
          if (width > height) {
            if (width > maxWidth) {
              height = (height * maxWidth) / width;
              width = maxWidth;
            }
          } else {
            if (height > maxHeight) {
              width = (width * maxHeight) / height;
              height = maxHeight;
            }
          }

          canvas.width = width;
          canvas.height = height;

          // Desenhar imagem redimensionada
          ctx.drawImage(img, 0, 0, width, height);

          // Converter para URL
          const thumbnailDataUrl = canvas.toDataURL('image/jpeg', 0.8);
          setThumbnailUrl(thumbnailDataUrl);
        };
        img.onerror = () => {
          setError('Erro ao carregar imagem');
        };
        img.src = e.target?.result as string;
      };
      reader.onerror = () => {
        setError('Erro ao ler arquivo');
      };
      reader.readAsDataURL(file);
    }
  }, [file, isImage]);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Estilos responsivos
  const thumbnailContainerClass = `
    relative rounded-lg overflow-hidden shadow-md
    w-full max-w-[200px] sm:max-w-[300px] md:max-w-[400px]
    h-auto
    bg-gray-100 dark:bg-gray-800
    group
  `.trim().replace(/\s+/g, ' ');

  const thumbnailImageClass = `
    w-full h-auto object-cover
    max-h-[200px] sm:max-h-[300px] md:max-h-[400px]
  `.trim().replace(/\s+/g, ' ');

  // Imagem com thumbnail
  if (isImage && thumbnailUrl) {
    return (
      <div className={thumbnailContainerClass}>
        <img
          src={thumbnailUrl}
          alt={file.name}
          className={thumbnailImageClass}
        />
        
        {/* Overlay com info e remover */}
        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-opacity duration-200 flex items-center justify-center">
          <button
            onClick={onRemove}
            disabled={isUploading}
            className="opacity-0 group-hover:opacity-100 p-2 bg-red-500 text-white rounded-full hover:bg-red-600 transition-opacity duration-200 disabled:opacity-50"
            title="Remover"
          >
            <X size={16} />
          </button>
        </div>

        {/* Loading overlay */}
        {isUploading && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div className="text-white text-sm">Enviando...</div>
          </div>
        )}

        {/* Info no canto */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2 text-white text-xs">
          <div className="truncate">{file.name}</div>
          <div className="text-gray-300">{formatFileSize(file.size)}</div>
        </div>
      </div>
    );
  }

  // PDF
  if (isPDF) {
    return (
      <div className={thumbnailContainerClass}>
        <div className="flex flex-col items-center justify-center p-8 h-[200px] sm:h-[250px] md:h-[300px]">
          <FileText size={64} className="text-red-500 mb-4" />
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate w-full text-center px-2">
            {file.name}
          </p>
          <p className="text-xs text-gray-500 mt-1">{formatFileSize(file.size)}</p>
        </div>
        
        {/* Overlay com remover */}
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onRemove}
            disabled={isUploading}
            className="p-1.5 bg-red-500 text-white rounded-full hover:bg-red-600 disabled:opacity-50"
            title="Remover"
          >
            <X size={14} />
          </button>
        </div>

        {/* Loading overlay */}
        {isUploading && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div className="text-white text-sm">Enviando...</div>
          </div>
        )}
      </div>
    );
  }

  // Word
  if (isWord) {
    return (
      <div className={thumbnailContainerClass}>
        <div className="flex flex-col items-center justify-center p-8 h-[200px] sm:h-[250px] md:h-[300px]">
          <div className="w-16 h-16 sm:w-20 sm:h-20 md:w-24 md:h-24 bg-blue-500 rounded flex items-center justify-center mb-4">
            <FileWord size={32} className="text-white" />
          </div>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate w-full text-center px-2">
            {file.name}
          </p>
          <p className="text-xs text-gray-500 mt-1">{formatFileSize(file.size)}</p>
        </div>
        
        {/* Overlay com remover */}
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onRemove}
            disabled={isUploading}
            className="p-1.5 bg-red-500 text-white rounded-full hover:bg-red-600 disabled:opacity-50"
            title="Remover"
          >
            <X size={14} />
          </button>
        </div>

        {/* Loading overlay */}
        {isUploading && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div className="text-white text-sm">Enviando...</div>
          </div>
        )}
      </div>
    );
  }

  // Excel
  if (isExcel) {
    return (
      <div className={thumbnailContainerClass}>
        <div className="flex flex-col items-center justify-center p-8 h-[200px] sm:h-[250px] md:h-[300px]">
          <div className="w-16 h-16 sm:w-20 sm:h-20 md:w-24 md:h-24 bg-green-500 rounded flex items-center justify-center mb-4">
            <FileSpreadsheet size={32} className="text-white" />
          </div>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate w-full text-center px-2">
            {file.name}
          </p>
          <p className="text-xs text-gray-500 mt-1">{formatFileSize(file.size)}</p>
        </div>
        
        {/* Overlay com remover */}
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onRemove}
            disabled={isUploading}
            className="p-1.5 bg-red-500 text-white rounded-full hover:bg-red-600 disabled:opacity-50"
            title="Remover"
          >
            <X size={14} />
          </button>
        </div>

        {/* Loading overlay */}
        {isUploading && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div className="text-white text-sm">Enviando...</div>
          </div>
        )}
      </div>
    );
  }

  // Outros tipos (fallback)
  return (
    <div className={thumbnailContainerClass}>
      <div className="flex flex-col items-center justify-center p-8 h-[200px] sm:h-[250px] md:h-[300px]">
        <File size={64} className="text-gray-500 mb-4" />
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate w-full text-center px-2">
          {file.name}
        </p>
        <p className="text-xs text-gray-500 mt-1">{formatFileSize(file.size)}</p>
      </div>
      
      {/* Overlay com remover */}
      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onRemove}
          disabled={isUploading}
          className="p-1.5 bg-red-500 text-white rounded-full hover:bg-red-600 disabled:opacity-50"
          title="Remover"
        >
          <X size={14} />
        </button>
      </div>

      {/* Loading overlay */}
      {isUploading && (
        <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="text-white text-sm">Enviando...</div>
        </div>
      )}
    </div>
  );
}

