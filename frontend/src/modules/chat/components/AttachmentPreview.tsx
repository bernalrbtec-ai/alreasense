/**
 * AttachmentPreview - Visualiza diferentes tipos de anexos
 * 
 * Suporta:
 * - Imagens: Preview inline + lightbox
 * - Vídeos: Player HTML5
 * - Áudios: Player HTML5 nativo (mais confiável que WaveSurfer)
 * - Documentos: Ícone + download
 * - IA: Transcrição + Resumo (se addon ativo)
 */
import React, { useState } from 'react';
import { Download, FileText, Image, Video, Music, X } from 'lucide-react';

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

        {/* Player Nativo HTML5 (mais confiável para MP3) */}
        <audio
          controls
          className="w-full mb-2"
          preload="metadata"
        >
          <source src={attachment.file_url} type={attachment.mime_type} />
          Seu navegador não suporta áudio.
        </audio>
        
        {/* Botão Download */}
        <div className="flex justify-end">
          <a
            href={attachment.file_url}
            download={attachment.original_filename}
            className="p-2 text-gray-600 hover:text-gray-900 inline-flex items-center gap-1 text-sm"
          >
            <Download size={16} />
            Download
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


